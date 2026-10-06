#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Endpoint for returning emails in mbox format as a single archive"""
import asyncio
import plugins.server
import plugins.session
import plugins.messages
import plugins.defuzzer
import re
import typing
import aiohttp.web
from asyncio.exceptions import CancelledError
import email.utils as eutils
import datetime


def convert_source(source) -> str:
    if source:
        source_as_text = source["_source"]["source"]
        # Ensure it starts with "From "...or fake it
        if not source_as_text.startswith("From "):
            from_line = "From MAILER-DAEMON Thu Jan  1 00:00:00 1970\n"  # Fallback in case no date found
            # If we have any Received: headers, we can extrapolate an approximate time from the last (top) one.
            from_match = re.search(r"(?:[\r\n]|^)Received:\s+from[^;]+?;\s+(.+?)[\r\n]", source_as_text)
            if from_match:
                recv_time = eutils.parsedate_tz(from_match.group(1))
                if recv_time:
                    dt_tuple = datetime.datetime(*recv_time[:7])
                    if recv_time[9]:  # If we have a timezone offset, apply via timedelta
                        dt_tuple += datetime.timedelta(seconds=recv_time[9])
                    # Set using ctime, as per https://datatracker.ietf.org/doc/html/rfc4155#appendix-A
                    from_line = "From MAILER-DAEMON %s\n" % dt_tuple.ctime()
            source_as_text = from_line + source_as_text
        # Convert to mboxrd format
        mboxrd_source = ""
        line_no = 0
        for line in source_as_text.split("\n"):
            line_no += 1
            if line_no > 1 and re.match(r"^>*From\s+", line):
                line = ">" + line
            mboxrd_source += line + "\n"
        return mboxrd_source
    return ""


async def process(
    server: plugins.server.BaseServer,
    request: aiohttp.web.BaseRequest,
    session: plugins.session.SessionObject,
    indata: dict,
) -> typing.Union[dict, aiohttp.web.Response, aiohttp.web.StreamResponse]:

    lid = indata.get("list", "_")
    if lid == '*':
        lid = 'all'
    domain = indata.get("domain", "_")
    if domain == '*':
        domain = 'all'
    # may be provided as d= or date=
    yyyymm = indata.get("d") or indata.get("date") # e.g. 2019-9; can also be lte=1M etc
    q = indata.get("q")

    try:
        query_defuzzed = plugins.defuzzer.defuzz(indata, list_override="@" in lid and lid or None)
    except ValueError as ve:  # If defuzzer encounters syntax errors, it will throw a ValueError
        return aiohttp.web.Response(headers={"content-type": "text/plain",}, status=400, text=str(ve))
    except AssertionError as ae:  # If defuzzer encounters internal errors, it will throw an AssertionError
        return aiohttp.web.Response(headers={"content-type": "text/plain",}, status=500, text=str(ae))

    dlstem = f"{lid}_{domain}"
    if yyyymm:
        if len(yyyymm) == 6 and yyyymm[4] == '-': # assume yyyy-m, convert to yyyy-mm
            yyyymm = yyyymm[0:-1] + "0" + yyyymm[-1]
        dlstem = f"{dlstem}_{yyyymm}"
    if q:
        dlstem = f"{dlstem}_{q}"
    # Figure out a sane filename stem (don't keep '.')
    dlstem = re.sub(r"[^-_a-zA-Z0-9]+", "_", dlstem)
    headers = {"Content-Type": "application/mbox", "Content-Disposition": f"attachment; filename={dlstem}.mbox"}

    # Return mbox archive with filename as a stream
    response = aiohttp.web.StreamResponse(status=200, headers=headers)
    response.enable_chunked_encoding()
    await response.prepare(request)

    async for emails in plugins.messages.query_batch(
        session,
        query_defuzzed,
        metadata_only=True,
        epoch_order="asc"
    ):
        for email in emails:
            source = await plugins.messages.get_source(session, permalink=email.get("dbid"))
            mboxrd_source = convert_source(source)
            # Ensure each non-empty source ends with a blank line
            if not mboxrd_source.endswith("\n\n"):
                mboxrd_source += "\n"
            try:
                async with server.streamlock:
                    await asyncio.wait_for(response.write(mboxrd_source.encode("utf-8")), timeout=5)
            except (TimeoutError, RuntimeError, CancelledError):
                break  # Writing stream failed, break it off.
    return response


def register(_server: plugins.server.BaseServer):
    # Note that this is a StreamingEndpoint!
    return plugins.server.StreamingEndpoint(process, token_allowed=True)
