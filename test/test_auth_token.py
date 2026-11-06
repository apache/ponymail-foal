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

# To be run as: python3 -m pytest test/test_auth_token.py

import asyncio
import base64
import datetime
import os
import sys
import time
import types

import elasticsearch.exceptions
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# The server plugins import each other as plugins.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import plugins.aaa
import plugins.auth_token
import plugins.configuration
import plugins.session

KEY = ed25519.Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(
    KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
).decode("ascii")


def make_server():
    config = plugins.configuration.Configuration(
        {
            "tokens": {
                "keys": {
                    "bot": {"public_key": PUBLIC, "uid": "reader", "authoritative": True},
                    "guest": {"public_key": PUBLIC},
                },
            },
        }
    )
    dbpool: asyncio.Queue = asyncio.Queue()
    dbpool.put_nowait("connection")
    return types.SimpleNamespace(config=config, dbpool=dbpool)


class FakeRequest:
    """Just enough of aiohttp.web.BaseRequest for get_session"""

    def __init__(self, method, target, header=None, body=b""):
        self.method = method
        self.raw_path = target
        self.headers = {"Authorization": header} if header else {}
        self.body = body
        self.host = "localhost"
        self.remote = "127.0.0.1"

    async def read(self):
        return self.body


def sign(method, target, body=b"", ts=None, key=KEY, key_id="bot", nonce="n1"):
    ts = str(ts if ts is not None else int(time.time()))
    msg = plugins.auth_token.signing_message(ts, nonce, method, target, body)
    sig = base64.b64encode(key.sign(msg)).decode("ascii")
    return f"PonyMail-Ed25519 key={key_id},ts={ts},nonce={nonce},sig={sig}"


def test_valid_signature():
    target = "/api/stats.lua?list=private&domain=example.org"
    signed = plugins.auth_token.verify(make_server(), "GET", target, sign("GET", target), b"")
    assert signed.key_id == "bot" and signed.nonce == "n1"


def test_replay_refused_memory():
    server = make_server()
    header = sign("POST", "/api/email.json", b'{"id": "x"}', nonce="mem1")
    signed = plugins.auth_token.verify(server, "POST", "/api/email.json", header, b'{"id": "x"}')
    plugins.auth_token.check_replay_memory(server, signed)
    with pytest.raises(plugins.auth_token.TokenError, match="already been used"):
        plugins.auth_token.check_replay_memory(server, signed)
    # The same request with a fresh nonce is fine
    header = sign("POST", "/api/email.json", b'{"id": "x"}', nonce="mem2")
    signed = plugins.auth_token.verify(server, "POST", "/api/email.json", header, b'{"id": "x"}')
    plugins.auth_token.check_replay_memory(server, signed)


class FakeDatabase:
    """Just enough of plugins.database.Database for the database replay check"""

    def __init__(self):
        self.dbs = types.SimpleNamespace(db_session="ponymail-session")
        self.docs = {}
        self.cleanups = 0
        self.client = types.SimpleNamespace(delete_by_query=self.delete_by_query)

    async def create(self, index, id, body):
        if (index, id) in self.docs:
            raise elasticsearch.exceptions.ConflictError(409, "version_conflict_engine_exception", {})
        self.docs[(index, id)] = body

    async def delete_by_query(self, **kwargs):
        self.cleanups += 1


def test_replay_refused_database():
    server = make_server()
    database = FakeDatabase()
    signed = plugins.auth_token.SignedRequest("bot", "db1", int(time.time()))
    asyncio.run(plugins.auth_token.check_replay_database(server, database, signed))
    assert database.docs[("ponymail-session", "token:bot:db1")]["cookie"] == "token:bot:db1"
    with pytest.raises(plugins.auth_token.TokenError, match="already been used"):
        asyncio.run(plugins.auth_token.check_replay_database(server, database, signed))
    other = plugins.auth_token.SignedRequest("bot", "db2", int(time.time()))
    asyncio.run(plugins.auth_token.check_replay_database(server, database, other))
    assert database.cleanups == 1  # At most once per NONCE_CLEANUP_INTERVAL


@pytest.mark.parametrize(
    "method,target,body",
    [
        ("POST", "/api/stats.lua?list=private&domain=example.org", b""),  # other method
        ("GET", "/api/stats.lua?list=secret&domain=example.org", b""),  # other target
        ("GET", "/api/stats.lua?list=private&domain=example.org", b"x"),  # other body
    ],
)
def test_tampered_request(method, target, body):
    header = sign("GET", "/api/stats.lua?list=private&domain=example.org")
    with pytest.raises(plugins.auth_token.TokenError, match="Invalid signature"):
        plugins.auth_token.verify(make_server(), method, target, header, body)


def test_wrong_key():
    other = ed25519.Ed25519PrivateKey.generate()
    with pytest.raises(plugins.auth_token.TokenError, match="Invalid signature"):
        plugins.auth_token.verify(make_server(), "GET", "/api/x", sign("GET", "/api/x", key=other), b"")
    with pytest.raises(plugins.auth_token.TokenError, match="Unknown token key"):
        plugins.auth_token.verify(make_server(), "GET", "/api/x", sign("GET", "/api/x", key_id="nobody"), b"")


def test_expired():
    old = int(time.time()) - 3600
    with pytest.raises(plugins.auth_token.TokenError, match="outside of the allowed window"):
        plugins.auth_token.verify(make_server(), "GET", "/api/x", sign("GET", "/api/x", ts=old), b"")


def test_malformed_header():
    with pytest.raises(plugins.auth_token.TokenError):
        plugins.auth_token.verify(make_server(), "GET", "/api/x", "PonyMail-Ed25519 key=bot", b"")


def test_session_credentials():
    server = make_server()
    target = "/api/stats.lua?list=private&domain=example.org"
    session = asyncio.run(
        plugins.auth_token.get_session(server, FakeRequest("GET", target, sign("GET", target, nonce="s1")), "stats")
    )
    assert session.credentials.uid == "reader" and session.credentials.name == "reader"
    assert session.credentials.authoritative and not session.credentials.admin
    assert session.credentials.oauth_provider == "token" and session.credentials.key_id == "bot"
    assert session.database == "connection"


def test_not_token_signed():
    server = make_server()
    assert asyncio.run(plugins.auth_token.get_session(server, FakeRequest("GET", "/api/stats.lua"), "stats")) is None
    request = FakeRequest("GET", "/api/stats.lua", "Bearer xyz")
    assert asyncio.run(plugins.auth_token.get_session(server, request, "stats")) is None


def test_read_only():
    server = make_server()
    request = FakeRequest("POST", "/api/compose.json", sign("POST", "/api/compose.json", b"{}", nonce="ro1"), b"{}")
    with pytest.raises(plugins.auth_token.TokenError, match="read-only"):
        asyncio.run(plugins.auth_token.get_session(server, request, "compose"))


def test_authorization_by_aaa():
    # Token credentials are authorized by the access control module, like any other login
    server = make_server()
    session = plugins.session.SessionObject(None)
    email = {"private": True, "list_raw": "<private.example.org>"}
    session.credentials = plugins.auth_token.TokenCredentials(server.config.tokens.keys["bot"])
    assert plugins.aaa.can_access_list(session, "private@example.org")
    assert plugins.aaa.can_access_email(session, email)
    session.credentials = plugins.auth_token.TokenCredentials(server.config.tokens.keys["guest"])
    assert not plugins.aaa.can_access_list(session, "private@example.org")
    assert not plugins.aaa.can_access_email(session, email)


def test_key_defaults():
    pem = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    config = plugins.configuration.Configuration({"tokens": {"keys": {"pem": {"public_key": pem.decode("ascii")}}}})
    key = config.tokens.keys["pem"]
    assert key.uid == "pem" and key.name == "pem" and key.email == ""
    assert not key.authoritative and key.expires is None
    with pytest.raises(ValueError, match="authoritative must be true or false"):
        plugins.configuration.Configuration({"tokens": {"keys": {"k": {"public_key": PUBLIC, "authoritative": "yes"}}}})


def test_disabled_by_default():
    assert plugins.configuration.Configuration({}).tokens.keys == {}


def test_replay_check_config():
    tokens = plugins.configuration.Configuration({}).tokens
    assert tokens.replay_check == "memory" and tokens.max_skew == 60
    tokens = plugins.configuration.Configuration({"tokens": {"replay_check": "database"}}).tokens
    assert tokens.replay_check == "database"
    with pytest.raises(ValueError, match="tokens.replay_check must be one of"):
        plugins.configuration.Configuration({"tokens": {"replay_check": "redis"}})


def make_key(**extra):
    config = plugins.configuration.Configuration({"tokens": {"keys": {"k": dict({"public_key": PUBLIC}, **extra)}}})
    return config.tokens.keys["k"]


def test_expiry_parsing():
    assert make_key().expires is None
    jan1 = int(datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
    assert make_key(expires=datetime.date(2027, 1, 1)).expires == jan1  # YAML: expires: 2027-01-01
    assert make_key(expires=datetime.datetime(2027, 1, 1, 0, 0)).expires == jan1  # No timezone means UTC
    assert make_key(expires="2027-01-01").expires == jan1
    assert make_key(expires="2027-01-01T02:00:00+02:00").expires == jan1
    assert make_key(expires="2027-01-01T00:00:00Z").expires == jan1
    for bad in ("next year", 1798761600, ["2027-01-01"]):
        with pytest.raises(ValueError, match="expires must be"):
            make_key(expires=bad)


def test_expired_key_refused():
    server = make_server()
    target = "/api/stats.lua?list=private&domain=example.org"
    server.config.tokens.keys["bot"].expires = int(time.time()) - 1
    with pytest.raises(plugins.auth_token.TokenError, match="Token key has expired"):
        plugins.auth_token.verify(server, "GET", target, sign("GET", target, nonce="exp1"), b"")
    server.config.tokens.keys["bot"].expires = int(time.time()) + 3600
    assert plugins.auth_token.verify(server, "GET", target, sign("GET", target, nonce="exp2"), b"").key_id == "bot"
