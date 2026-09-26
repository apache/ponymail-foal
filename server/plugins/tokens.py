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
Short-term session tokens for Pony Mail codename Foal.

A session token is a short-lived bearer credential minted from an existing,
logged-in browser session. It lets an external client (a CLI, an MCP server,
a script) act on behalf of that session without ever seeing the session
cookie:

    Authorization: Bearer pmt_<random>

Properties:
- Bound to the browser session that minted it. Logging out of that session
  (or the session expiring) invalidates every token minted from it.
- Short-lived: expires after `tokens.ttl` seconds (capped by `tokens.max_ttl`).
- Read-only: a token-authenticated request cannot mint further tokens, send
  email (compose) or use the management console.
- Stored only as a SHA-256 hash, in memory. A server restart revokes all
  outstanding tokens, which is acceptable for credentials this short-lived.
"""

import hashlib
import hmac
import secrets
import time
import typing
import urllib.parse

TOKEN_PREFIX = "pmt_"
TOKEN_BYTES = 32  # 256 bits of entropy
MAX_CLIENT_NAME_LENGTH = 64
# Loopback IP literals only: "localhost" is refused, as RFC 8252 section 8.3 recommends,
# since it can be resolved to something other than the loopback interface.
LOOPBACK_HOSTS = ("127.0.0.1", "::1")


class TokenRecord:
    """An issued token. The raw token is never stored, only its hash."""

    token_hash: str
    session_id: str
    cid: str
    client: str
    created: int
    expires: int

    def __init__(self, token_hash: str, session_id: str, cid: str, client: str, created: int, expires: int):
        self.token_hash = token_hash
        self.session_id = session_id
        self.cid = cid
        self.client = client
        self.created = created
        self.expires = expires

    def expired(self, now: typing.Optional[int] = None) -> bool:
        return (now if now is not None else int(time.time())) >= self.expires

    def public(self) -> dict:
        """Metadata that is safe to show to the token holder or session owner"""
        return {
            "id": self.token_hash[:12],
            "client": self.client,
            "created": self.created,
            "expires": self.expires,
        }


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(token: str) -> bool:
    """Cheap syntactic check before touching the token store"""
    if not token.startswith(TOKEN_PREFIX):
        return False
    body = token[len(TOKEN_PREFIX):]
    return 0 < len(body) <= 128 and all(c.isalnum() or c in "-_" for c in body)


def bearer_from_header(value: typing.Optional[str]) -> typing.Optional[str]:
    """Extract a Pony Mail token from an Authorization header value, if any"""
    if not value:
        return None
    scheme, _, credentials = value.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    credentials = credentials.strip()
    return credentials if looks_like_token(credentials) else None


def sanitize_client_name(name: typing.Any) -> str:
    """Client names are shown on the approval page and in token listings; keep them boring"""
    if not isinstance(name, str):
        return "unknown client"
    cleaned = "".join(c for c in name if c.isalnum() or c in " ._-:/@()").strip()
    return cleaned[:MAX_CLIENT_NAME_LENGTH] or "unknown client"


def validate_redirect_uri(uri: typing.Any) -> typing.Optional[str]:
    """
    Validate a browser hand-off target. Only http(s) URLs on a loopback IP literal with
    an explicit port are allowed (RFC 8252 sections 7.3 and 8.3), so a token can only ever be handed
    to a process running on the user's own machine. Returns the normalized URI or None.
    """
    if not isinstance(uri, str) or len(uri) > 512:
        return None
    try:
        parts = urllib.parse.urlsplit(uri)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username is not None or parts.password is not None:
        return None
    if parts.fragment:
        return None
    if not port:
        return None
    host = (parts.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        return None
    return urllib.parse.urlunsplit(parts)


class TokenStore:
    """In-memory token store, keyed by token hash"""

    tokens: typing.Dict[str, TokenRecord]

    def __init__(self):
        self.tokens = {}

    def issue(self, session_id: str, cid: str, client: str, ttl: int) -> typing.Tuple[str, TokenRecord]:
        self.purge()
        now = int(time.time())
        token = TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_BYTES)
        record = TokenRecord(
            token_hash=hash_token(token),
            session_id=session_id,
            cid=cid,
            client=sanitize_client_name(client),
            created=now,
            expires=now + ttl,
        )
        self.tokens[record.token_hash] = record
        return token, record

    def lookup(self, token: str) -> typing.Optional[TokenRecord]:
        if not looks_like_token(token):
            return None
        token_hash = hash_token(token)
        record = self.tokens.get(token_hash)
        # compare_digest is belt and braces here: the dict lookup is on a hash already
        if not record or not hmac.compare_digest(record.token_hash, token_hash):
            return None
        if record.expired():
            del self.tokens[token_hash]
            return None
        return record

    def revoke(self, token: str) -> bool:
        return self.tokens.pop(hash_token(token), None) is not None

    def revoke_id(self, session_id: str, token_id: str) -> bool:
        """Revoke a token by its public id, but only if it belongs to the given session"""
        for token_hash, record in list(self.tokens.items()):
            if record.session_id == session_id and token_hash.startswith(token_id) and len(token_id) >= 12:
                del self.tokens[token_hash]
                return True
        return False

    def revoke_session(self, session_id: str) -> int:
        doomed = [h for h, r in self.tokens.items() if r.session_id == session_id]
        for token_hash in doomed:
            del self.tokens[token_hash]
        return len(doomed)

    def for_session(self, session_id: str) -> typing.List[TokenRecord]:
        self.purge()
        return [r for r in self.tokens.values() if r.session_id == session_id]

    def purge(self) -> None:
        now = int(time.time())
        for token_hash in [h for h, r in self.tokens.items() if r.expired(now)]:
            del self.tokens[token_hash]
