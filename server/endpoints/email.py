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

"""
Simple endpoint that returns an email or an attachment from one

THIS ONLY DEALS WITH PUBLIC EMAILS FOR NOW - AAA IS BEING WORKED ON
"""

import plugins.server
import plugins.session
import plugins.messages
import plugins.database
import aiohttp.web
import plugins.aaa
import base64
import typing


async def process(
    _server: plugins.server.BaseServer, session: plugins.session.SessionObject, indata: dict,
) -> typing.Union[dict, aiohttp.web.Response]:

    # Has a list id been provided?
    listid = indata.get("listid", "")

    # lookup by message id must always include a list id for disambiguation
    if listid:
        email = await plugins.messages.get_email(session, messageid=indata.get("id"), listid=listid)
    else: # Else assume permalink and look up the email based on that
        email = await plugins.messages.get_email(session, permalink=indata.get("id"))

    if email is None:
        return aiohttp.web.Response(headers={}, status=404, text="Email not found")

    # If email was found, process the request
    if email:
        # Are we fetching an attachment?
        if not indata.get("attachment"):
            if not email.get("gravatar"):
                email["gravatar"] = plugins.messages.gravatar(email)
            return email
        else:
            fid = indata.get("file")
            for entry in email.get("attachments", []):
                if entry.get("hash") == fid:
                    ct = entry.get("content_type") or "application/binary"
                    headers = {
                        "Content-Type": ct,
                        "Content-Length": str(entry.get("size")),
                    }
                    if "image/" not in ct and "text/" not in ct:
                        headers["Content-Disposition"] = f"attachment; filename=\"{entry.get('filename')}\""
                    try:
                        assert session.database, "Database not connected!"
                        attachment = await session.database.get(
                            index=session.database.dbs.db_attachment, id=indata.get("file")
                        )
                        if attachment:
                            blob = base64.decodebytes(attachment["_source"].get("source").encode("utf-8"))
                            return aiohttp.web.Response(headers=headers, status=200, body=blob)
                    except plugins.database.DBError:
                        pass  # attachment not found
            return aiohttp.web.Response(headers={}, status=404, text="Attachment not found")

    return aiohttp.web.Response(headers={}, status=404, text="Email not found")


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process, token_allowed=True)
