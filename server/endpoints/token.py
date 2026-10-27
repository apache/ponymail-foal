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
Session token endpoint for Pony Mail codename Foal.

Mints, lists and revokes short-term session tokens (see plugins/tokens.py).

    action=info    - token support and lifetimes (no login needed)
    action=create  - mint a token for the current browser session (default action)
    action=list    - list the user's tokens, from whichever browser session minted them
    action=revoke  - revoke a token: the calling token itself when authenticated with one,
                     otherwise `id=<token id>`, or `id=*` for all of the user's tokens
"""

import json
import re
import typing
import urllib.parse

import aiohttp.web

import plugins.server
import plugins.session
import plugins.tokens


def reply(status: int, **payload: typing.Any) -> aiohttp.web.Response:
    return aiohttp.web.Response(
        headers={"content-type": "application/json", "cache-control": "no-store"},
        status=status,
        text=json.dumps(payload),
    )


def error(status: int, code: str, message: str) -> aiohttp.web.Response:
    return reply(status, okay=False, error=code, message=message)


def parse_ttl(value: typing.Any) -> typing.Optional[int]:
    """A whole number of seconds, from JSON (int) or a form (digits); None for anything else"""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value.strip()):
        return int(value)
    return None


def same_origin(request: aiohttp.web.BaseRequest, session: plugins.session.SessionObject) -> bool:
    """Browsers always send Origin on POST; refuse token minting initiated from another site"""
    origin = request.headers.get("origin")
    if not origin:
        return True  # Not a browser, or a same-origin request from an older browser
    return urllib.parse.urlsplit(origin).netloc.lower() == session.host.lower()


async def process(
    server: plugins.server.BaseServer,
    request: aiohttp.web.BaseRequest,
    session: plugins.session.SessionObject,
    indata: dict,
) -> aiohttp.web.Response:
    config = server.config.tokens
    action = indata.get("action", "create")

    if action == "info":
        return reply(
            200,
            okay=True,
            enabled=config.enabled,
            ttl=config.ttl,
            min_ttl=plugins.tokens.MIN_TTL,
            max_ttl=config.max_ttl,
        )

    if not config.enabled:
        return error(403, "tokens_disabled", "Session tokens are not enabled on this server.")

    if request.method != "POST":
        return error(405, "method_not_allowed", "Use POST for this endpoint.")

    if not same_origin(request, session):
        return error(403, "cross_origin", "Session tokens can only be requested from this site.")

    # A session token may only revoke itself; every other action needs the browser session
    if session.token:
        if action != "revoke":
            return error(403, "token_not_allowed", "A session token cannot be used to manage session tokens.")
        server.data.tokens.revoke_id(session.token.cid, session.token.token_hash)
        return reply(200, okay=True, revoked=1)

    if not session.credentials:
        return error(403, "login_required", "You need to be logged in to use session tokens.")

    if action == "create":
        redirect_uri = None
        if indata.get("redirect_uri"):
            redirect_uri = plugins.tokens.validate_redirect_uri(indata.get("redirect_uri"))
            if not redirect_uri:
                return error(
                    400, "invalid_redirect_uri", "Tokens can only be handed to a loopback address with a port."
                )
        invalid_ttl = "ttl must be a number of seconds between %d and %d." % (plugins.tokens.MIN_TTL, config.max_ttl)
        # Only an omitted ttl falls back to the default; any value that is given must be valid
        ttl = parse_ttl(indata["ttl"]) if "ttl" in indata else config.ttl
        if ttl is None:
            return error(400, "invalid_ttl", invalid_ttl)
        assert session.cid, "Logged in session without an account id"
        try:
            token, record = server.data.tokens.issue(
                session.cookie, session.cid, indata.get("client", ""), ttl, config.max_ttl
            )
        except ValueError:
            return error(400, "invalid_ttl", invalid_ttl)
        payload = {"okay": True, "token": token, "ttl": record.expires - record.created, **record.public()}
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri
        return reply(200, **payload)

    if action == "list":
        assert session.cid, "Logged in session without an account id"
        tokens = [
            {**r.public(), "this_session": r.session_id == session.cookie}
            for r in server.data.tokens.for_account(session.cid)
        ]
        return reply(200, okay=True, tokens=tokens)

    if action == "revoke":
        token_id = str(indata.get("id") or "")
        if not token_id:
            return error(400, "missing_id", "Give the id of the token to revoke, or * for all of them.")
        assert session.cid, "Logged in session without an account id"
        if token_id == "*":
            return reply(200, okay=True, revoked=server.data.tokens.revoke_account(session.cid))
        revoked = server.data.tokens.revoke_id(session.cid, token_id)
        return reply(200, okay=True, revoked=int(revoked))

    return error(400, "unknown_action", "Unknown action.")


def register(_server: plugins.server.BaseServer):
    return plugins.server.StreamingEndpoint(process, token_allowed=True)
