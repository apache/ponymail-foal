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
Token authentication for Pony Mail Foal: read-only API access with asymmetric (Ed25519) token keys,
enabled by configuring keys under `tokens` in ponymail.yaml.

This only authenticates: a valid request gets a session with the credentials configured for its key
(uid, authoritative). Which lists those credentials may read is decided by the access control module
(plugins/aaa.py), exactly as for an OAuth login, so changes to the rights of a uid apply to its tokens too.

The client keeps the private key; ponymail.yaml holds only the public key.
Each request carries a signature over the request itself:

    Authorization: PonyMail-Ed25519 key=<key id>,ts=<unix time>,nonce=<random string>,sig=<base64 signature>

The signed message is (lines joined with "\\n"):

    <ts>
    <nonce>
    <HTTP method, upper case>
    <request target as sent, i.e. path plus query string>
    <hex sha256 of the request body>

Requests older than tokens.max_skew seconds are rejected, as is a nonce the key has used before.
Used nonces are remembered per server process (tokens.replay_check: memory), or in the session
index (tokens.replay_check: database) so that several server instances share them.
"""

import base64
import binascii
import hashlib
import time
import typing

import aiohttp.web
import elasticsearch.exceptions

import plugins.configuration
import plugins.database
import plugins.server
import plugins.session

AUTH_SCHEME = "PonyMail-Ed25519"
TOKEN_PROVIDER = "token"

# Endpoints a token may call. Everything else (compose, mgmt, oauth, ...) is refused.
READONLY_ENDPOINTS = {"stats", "email", "thread", "source", "mbox", "preferences", "pminfo", "gravatar"}

# Prefix of the session index document ids that record used nonces (replay_check: database).
# Cookies can never look like this, as get_session only accepts [a-g0-9-] in them.
NONCE_ID_PREFIX = "token:"
NONCE_CLEANUP_INTERVAL = 3600  # Seconds between removals of expired nonce docs

# Nonces already used ("key:nonce"), mapped to the time after which they can be forgotten (replay_check: memory)
_seen_nonces: typing.Dict[str, int] = {}
_nonce_cleanup = {"next": 0}  # When to next remove expired nonce docs (replay_check: database)


class SignedRequest(typing.NamedTuple):
    key_id: str
    nonce: str
    timestamp: int


class TokenError(PermissionError):
    """Raised when a token-signed request cannot be authenticated"""


class TokenCredentials(plugins.session.SessionCredentials):
    """Credentials of a token key, as configured for it. Never admin."""

    key_id: str

    def __init__(self, key: plugins.configuration.TokenKey):
        super().__init__(
            {
                "uid": key.uid,
                "name": key.name,
                "email": key.email,
                "oauth_provider": TOKEN_PROVIDER,
                "authoritative": key.authoritative,
            }
        )
        self.key_id = key.key_id


def signing_message(timestamp: str, nonce: str, method: str, target: str, body: bytes) -> bytes:
    """Construct the message that a client signs (shared with tools/api-token.py)"""
    # Ed25519 signatures are deterministic, so the nonce keeps identical requests from looking like replays
    return "\n".join((timestamp, nonce, method.upper(), target, hashlib.sha256(body).hexdigest())).encode("utf-8")


def parse_header(header: str) -> typing.Dict[str, str]:
    """Parse 'PonyMail-Ed25519 key=..,ts=..,nonce=..,sig=..' into a dict"""
    params: typing.Dict[str, str] = {}
    for part in header[len(AUTH_SCHEME) :].split(","):
        if "=" not in part:
            raise TokenError("Malformed Authorization header")
        name, value = part.strip().split("=", 1)
        params[name] = value.strip('"')
    if not all(params.get(x) for x in ("key", "ts", "nonce", "sig")):
        raise TokenError("Authorization header must contain key, ts, nonce and sig")
    return params


def verify(server: plugins.server.BaseServer, method: str, target: str, header: str, body: bytes) -> SignedRequest:
    """Check a request signature and its age, raising TokenError if not valid. Replays are checked separately."""
    params = parse_header(header)
    key = server.config.tokens.keys.get(params["key"])
    if not key:
        raise TokenError("Unknown token key")
    if key.expires is not None and time.time() >= key.expires:
        raise TokenError("Token key has expired")
    try:
        timestamp = int(params["ts"])
        signature = base64.b64decode(params["sig"], validate=True)
    except (ValueError, binascii.Error):
        raise TokenError("Malformed ts or sig")
    if abs(int(time.time()) - timestamp) > server.config.tokens.max_skew:
        raise TokenError("Request timestamp outside of the allowed window")

    # Imported here so the dependency is only needed when this module is selected
    import cryptography.exceptions

    try:
        key.public_key.verify(signature, signing_message(params["ts"], params["nonce"], method, target, body))
    except cryptography.exceptions.InvalidSignature:
        raise TokenError("Invalid signature")
    return SignedRequest(key.key_id, params["nonce"], timestamp)


def check_replay_memory(server: plugins.server.BaseServer, signed: SignedRequest) -> None:
    """Refuse a nonce this server process has seen before, within the allowed window"""
    now = int(time.time())
    for seen, expiry in list(_seen_nonces.items()):
        if expiry < now:
            del _seen_nonces[seen]
    seen_id = f"{signed.key_id}:{signed.nonce}"
    if seen_id in _seen_nonces:
        raise TokenError("Nonce has already been used")
    _seen_nonces[seen_id] = signed.timestamp + server.config.tokens.max_skew


async def check_replay_database(
    server: plugins.server.BaseServer, database: plugins.database.Database, signed: SignedRequest
) -> None:
    """Refuse a nonce any server instance has seen before, by recording it in the session index"""
    nonce_id = f"{NONCE_ID_PREFIX}{signed.key_id}:{signed.nonce}"
    try:
        # Creating a document with a fixed id fails if it exists, atomically across all instances.
        # The id is repeated in the (keyword) cookie field so the cleanup can find these docs.
        await database.create(
            index=database.dbs.db_session,
            id=nonce_id,
            body={"cookie": nonce_id, "cid": None, "updated": signed.timestamp},
        )
    except elasticsearch.exceptions.ConflictError:
        raise TokenError("Nonce has already been used")

    now = int(time.time())
    if now >= _nonce_cleanup["next"]:
        _nonce_cleanup["next"] = now + NONCE_CLEANUP_INTERVAL
        # Nonces older than the window can't be replayed anyway, as their timestamp is refused.
        # A failed cleanup is simply retried next interval.
        try:
            await database.client.delete_by_query(
                index=database.dbs.db_session,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"prefix": {"cookie": NONCE_ID_PREFIX}},
                                {"range": {"updated": {"lt": now - server.config.tokens.max_skew}}},
                            ]
                        }
                    }
                },
                conflicts="proceed",
            )
        except plugins.database.DBError:
            pass


async def get_session(
    server: plugins.server.BaseServer, request: aiohttp.web.BaseRequest, handler: str
) -> typing.Optional[plugins.session.SessionObject]:
    """
    Build a read-only session for a token-signed request.
    Returns None if the request is not token-signed, raises TokenError if it is but is not allowed.
    """
    if not request.headers.get("Authorization", "").startswith(AUTH_SCHEME + " "):
        return None
    if handler not in READONLY_ENDPOINTS:
        raise TokenError("Token access is read-only")
    body = await request.read()  # Already read (and cached by aiohttp) when parsing form data
    signed = verify(server, request.method, request.raw_path, request.headers["Authorization"], body)
    if server.config.tokens.replay_check == "memory":
        check_replay_memory(server, signed)

    # Sessions for tokens are per request and are never stored
    session = plugins.session.SessionObject(server)
    session.credentials = TokenCredentials(server.config.tokens.keys[signed.key_id])
    session.database = await server.dbpool.get()
    if server.config.tokens.replay_check == "database":
        try:
            await check_replay_database(server, session.database, signed)
        except Exception:
            # Return the connection, as the caller never gets this session
            server.dbpool.put_nowait(session.database)
            server.dbpool.task_done()
            raise
    session.host = request.headers.get("X-Forwarded-Host", request.host or "??")
    session.remote = request.remote or "??"
    return session
