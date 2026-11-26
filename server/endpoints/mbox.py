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
import time
import typing
import aiohttp.web
from asyncio.exceptions import CancelledError
import email.utils as eutils
import datetime

# Start of any line but the first that would otherwise look like the start of a new message in mboxrd format
# (">*From " followed by whitespace other than a line break)
MBOXRD_FROM_LINE_RE = re.compile(r"(?<=\n)(?=>*From[^\S\n])")
MBOX_CHUNK_SIZE = 16 * 1024  # Bytes per write when sending, so throttled downloads flow smoothly
MBOX_BURST_SIZE = 64 * 1024  # Bytes a throttled download may send in one go, e.g. at the start
MBOX_WRITE_TIMEOUT = 5  # Seconds a client may take to accept a chunk before we give up on it


class Throttle:
    """Token bucket that paces one download to `rate` bytes per second, with bursts of up to `burst` bytes.
    Waiting is done with asyncio.sleep, so the server carries on with other requests in the meantime."""

    def __init__(self, rate: int, burst: int):
        self.rate = rate
        self.burst = burst
        self.allowance = float(burst)
        self.last = time.monotonic()

    async def consume(self, nbytes: int) -> None:
        now = time.monotonic()
        self.allowance = min(self.burst, self.allowance + (now - self.last) * self.rate)
        self.last = now
        self.allowance -= nbytes
        if self.allowance < 0:  # Over budget: wait until the bucket has refilled enough to cover this chunk
            await asyncio.sleep(-self.allowance / self.rate)


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
        # Convert to mboxrd format: quote every line but the first that starts with ">*From ", with an extra ">".
        # One regex pass instead of a Python loop per line, as sources with large attachments have many lines.
        return MBOXRD_FROM_LINE_RE.sub(">", source_as_text) + "\n"
    return ""


def _return_database(server: plugins.server.BaseServer, session: plugins.session.SessionObject) -> None:
    """Hands the session's pooled database connection back to the pool (as main.py does after a request)."""
    if session.database:
        server.dbpool.put_nowait(session.database)
        server.dbpool.task_done()
        session.database = None


async def _fetch_source(server: plugins.server.BaseServer, session: plugins.session.SessionObject, dbid):
    """Fetches one email's source, borrowing a pooled database connection just for the duration of the fetch,
    so that long (throttled) downloads do not keep connections from other requests."""
    session.database = await server.dbpool.get()
    try:
        return await plugins.messages.get_source(session, permalink=dbid)
    finally:
        _return_database(server, session)


async def _send(response: aiohttp.web.StreamResponse, data: bytes, throttle: typing.Optional[Throttle]) -> bool:
    """Writes data to the client in chunks, paced by the throttle if any. Returns False if the client is gone."""
    view = memoryview(data)
    for offset in range(0, len(view), MBOX_CHUNK_SIZE):
        chunk = view[offset:offset + MBOX_CHUNK_SIZE]
        if throttle:
            await throttle.consume(len(chunk))
        try:
            await asyncio.wait_for(response.write(chunk), timeout=MBOX_WRITE_TIMEOUT)
        except (TimeoutError, ConnectionError, RuntimeError, CancelledError):
            return False  # Writing stream failed, break it off.
    return True


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

    # Find the emails to send first (whole batches, until at least max_hits). Sending can take a long time when
    # throttled, so we don't keep a scroll open (it would expire) or hold on to a pooled database connection
    # meanwhile; each source is fetched with a connection borrowed just for that.
    max_hits = session.database and session.database.config.max_hits or 0
    dbids: list[str] = []
    async for emails in plugins.messages.query_batch(
        session,
        query_defuzzed,
        metadata_only=True,
        epoch_order="asc"
    ):
        dbids.extend(email.get("dbid") for email in emails)
        if len(dbids) >= max_hits:
            break
    _return_database(server, session)

    # Return mbox archive with filename as a stream
    response = aiohttp.web.StreamResponse(status=200, headers=headers)
    response.enable_chunked_encoding()
    await response.prepare(request)

    rate_limit = server.config.ui.mbox_rate_limit  # bytes per second, per download; 0 means unlimited
    throttle = Throttle(rate_limit, MBOX_BURST_SIZE) if rate_limit > 0 else None
    for dbid in dbids:
        source = await _fetch_source(server, session, dbid)
        mboxrd_source = convert_source(source)
        # Ensure each non-empty source ends with a blank line
        if not mboxrd_source.endswith("\n\n"):
            mboxrd_source += "\n"
        if not await _send(response, mboxrd_source.encode("utf-8"), throttle):
            break

    return response


def register(_server: plugins.server.BaseServer):
    # Note that this is a StreamingEndpoint!
    return plugins.server.StreamingEndpoint(process, token_allowed=True)