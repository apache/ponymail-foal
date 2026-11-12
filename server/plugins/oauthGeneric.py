#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Generic OAuth plugin
import re
import typing
import aiohttp.client


async def process(formdata: dict, _session, server) -> typing.Optional[dict]:
    provider = server.config.oauth.providers.get(formdata["key"])
    if not provider:
        # should not happen, but just in case of client error
        return None
    oauth_url = provider.get('.oauth_url', '')
    # Extract domain, allowing for :port
    # Does not handle user/password prefix etc
    m = re.match(r"https?://([^/:]+)(?::\d+)?/", oauth_url)
    if not m:
        return None
    oauth_domain = m.group(1)
    headers = {"User-Agent": "Pony Mail OAuth Agent/0.1", "Accept": "application/json"}
    client_secret = provider.get('.client_secret')
    if client_secret:
        # Standard authorization code exchange (RFC 6749 section 4.1.3)
        data = {
            "grant_type": "authorization_code",
            "code": formdata.get("code", ""),
            "client_id": provider.get("client_id", ""),
            "client_secret": client_secret,
        }
        # Must match the redirect_uri used on the authorization request
        if formdata.get("redirect_uri"):
            data["redirect_uri"] = formdata["redirect_uri"]
    else:
        # No client secret: pass the callback parameters through as-is. This is the
        # non-standard ASF OAuth flow used by lists.apache.org, preserved unchanged.
        data = formdata
    async with aiohttp.client.request("POST", oauth_url, headers=headers, data=data) as rv:
        js = await rv.json()
    # Identity is either in the token response, or fetched from a userinfo endpoint
    userinfo_url = provider.get('.userinfo_url')
    if userinfo_url and js.get("access_token"):
        headers["Authorization"] = "Bearer %s" % js["access_token"]
        async with aiohttp.client.request("GET", userinfo_url, headers=headers) as rv:
            js = await rv.json()
    js["oauth_domain"] = oauth_domain
    return js
