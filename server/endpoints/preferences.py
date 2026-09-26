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

import plugins.server
import plugins.aaa
import plugins.session
import aiohttp.web
import typing
import fnmatch

"""
Generic preferences endpoint for Pony Mail codename Foal

This is incomplete, but will work for anonymous tests.
"""


async def process(
    server: plugins.server.BaseServer, session: plugins.session.SessionObject, indata: dict
) -> typing.Union[dict, aiohttp.web.Response]:

    versions: dict = {
        "foal": server.foal_version, # type: ignore [attr-defined]
    }

    # Require login for this info
    if session.credentials and session.credentials.authoritative:
        versions["server"] = server.server_version  # type: ignore [attr-defined]
        if session.credentials.admin:
            versions["elasticsearch_engine"] = server.engine_version
            versions["elasticsearch_library"] = server.library_version

    prefs: dict = {"login": {}}
    prefs['versions'] = versions
    if indata.get('oauth'):
        # filter subkeys starting with .
        # the providers is a dict of dicts; we want to filter out keys in the inner dict that start with '.'
        prefs['oauth'] = { provider:{ k:v for k,v in entry.items() if not k.startswith('.')} 
                  for provider,entry in server.config.oauth.providers.items()}
        return prefs
    lists: dict = {}
    for ml, entry in server.data.lists.items():
        if "@" in ml:
            lname, ldomain = ml.split("@", 1)
            can_access = True
            if entry.get("private", True):
                can_access = plugins.aaa.can_access_list(session, ml)
            if server.config.ui.focus_domain != "*":
                if '*' in server.config.ui.focus_domain:
                    if not fnmatch.fnmatch(ldomain, server.config.ui.focus_domain):
                        continue
                elif ldomain != (server.config.ui.focus_domain or session.host):
                    continue
            if can_access:
                if ldomain not in lists:
                    lists[ldomain] = {}
                lists[ldomain][lname] = entry["count"]
    prefs["lists"] = lists
    if session and session.credentials:
        prefs["login"] = {
            "credentials": {
                "uid": session.credentials.uid,
                "email": session.credentials.email,
                "fullname": session.credentials.name,
            }
        }
        if session.credentials.admin is True:
            prefs["login"]["credentials"]["admin"] = True
            if server.config.ui.fully_delete:  # Needed by the UI
                prefs["login"]["credentials"]["fully_delete"] = True
        if session.token:
            prefs["login"]["token"] = session.token.public()

    # Logging out??
    if indata.get("logout"):
        # A session token logging out only revokes itself, never the browser session behind it
        if session.token:
            server.data.tokens.revoke_id(session.token.session_id, session.token.token_hash)
            return {"okay": True}

        # Tokens minted from this session die with it
        server.data.tokens.revoke_session(session.cookie)

        # Remove session from ElasticSearch
        await plugins.session.remove_session(session)

        # If stored in memory, remove from there.
        if session.cookie in server.data.sessions:
            del server.data.sessions[session.cookie]
        session.credentials = None
        return aiohttp.web.Response(
            headers={
                "set-cookie": "ponymail=deleted; path=/api; expires=Thu, 01 Jan 1970 00:00:00 GMT",
                "content-type": "application/json",
            },
            status=200,
            text='{"okay": true}',
        )

    return prefs


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process)
