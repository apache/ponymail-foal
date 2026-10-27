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

import time

import pytest

from server.plugins import tokens


def test_issue_and_lookup():
    store = tokens.TokenStore()
    token, record = store.issue("session-1", "cid-1", "my client", 3600)
    assert token.startswith(tokens.TOKEN_PREFIX)
    assert store.lookup(token) is record
    assert record.session_id == "session-1"
    assert record.cid == "cid-1"
    assert record.client == "my client"
    assert record.expires - record.created == 3600


def test_raw_token_is_not_stored():
    store = tokens.TokenStore()
    token, _ = store.issue("s", "c", "x", 60)
    assert token not in store.tokens
    assert all(token not in vars(r).values() for r in store.tokens.values())


@pytest.mark.parametrize(
    "ttl, max_ttl",
    [(tokens.MIN_TTL, 7200), (600, 7200), (7200, 7200)],
)
def test_issue_accepts_ttl_in_range(ttl, max_ttl):
    store = tokens.TokenStore()
    _, record = store.issue("s", "c", "x", ttl, max_ttl)
    assert record.expires - record.created == ttl


@pytest.mark.parametrize(
    "ttl, max_ttl",
    [(-5, 7200), (0, 7200), (tokens.MIN_TTL - 1, 7200), (7201, 7200), (tokens.DEFAULT_MAX_TTL + 1, None)],
)
def test_issue_rejects_ttl_out_of_range(ttl, max_ttl):
    store = tokens.TokenStore()
    with pytest.raises(ValueError):
        if max_ttl is None:
            store.issue("s", "c", "x", ttl)  # Default cap is DEFAULT_MAX_TTL
        else:
            store.issue("s", "c", "x", ttl, max_ttl)
    assert not store.tokens


def test_tokens_are_unique():
    store = tokens.TokenStore()
    issued = {store.issue("s", "c", "x", 60)[0] for _ in range(100)}
    assert len(issued) == 100


def test_lookup_unknown_and_malformed():
    store = tokens.TokenStore()
    store.issue("s", "c", "x", 60)
    assert store.lookup("pmt_doesnotexist") is None
    assert store.lookup("not-a-token") is None
    assert store.lookup("pmt_") is None
    assert store.lookup("pmt_bad chars!") is None


def test_expired_tokens_are_rejected_and_purged():
    store = tokens.TokenStore()
    token, record = store.issue("s", "c", "x", 60)
    record.expires = int(time.time()) - 1
    assert store.lookup(token) is None
    assert not store.tokens


def test_revoke():
    store = tokens.TokenStore()
    token, _ = store.issue("s", "c", "x", 60)
    assert store.revoke(token)
    assert store.lookup(token) is None
    assert not store.revoke(token)


def test_revoke_session_only_hits_that_session():
    store = tokens.TokenStore()
    a1, _ = store.issue("a", "c", "x", 60)
    a2, _ = store.issue("a", "c", "x", 60)
    b1, _ = store.issue("b", "c", "x", 60)
    assert store.revoke_session("a") == 2
    assert store.lookup(a1) is None
    assert store.lookup(a2) is None
    assert store.lookup(b1) is not None


def test_revoke_account_hits_every_session_of_that_account():
    store = tokens.TokenStore()
    a1, _ = store.issue("session-a", "cid-1", "x", 60)
    b1, _ = store.issue("session-b", "cid-1", "x", 60)  # Same user, another (lost) browser session
    other, _ = store.issue("session-c", "cid-2", "x", 60)
    assert store.revoke_account("cid-1") == 2
    assert store.lookup(a1) is None
    assert store.lookup(b1) is None
    assert store.lookup(other) is not None


def test_revoke_id_is_scoped_to_account():
    store = tokens.TokenStore()
    token, record = store.issue("session-a", "cid-1", "x", 60)
    token_id = record.public()["id"]
    assert not store.revoke_id("cid-2", token_id)
    assert not store.revoke_id("cid-1", token_id[:4])  # too short to be unambiguous
    assert store.lookup(token) is not None
    assert store.revoke_id("cid-1", token_id)  # Works from any session of the same account
    assert store.lookup(token) is None


def test_for_account_and_public_view():
    store = tokens.TokenStore()
    token, _ = store.issue("session-a", "cid-1", "x", 60)
    store.issue("session-b", "cid-1", "y", 60)
    store.issue("session-c", "cid-2", "z", 60)
    listed = store.for_account("cid-1")
    assert {r.client for r in listed} == {"x", "y"}
    public = listed[0].public()
    assert set(public) == {"id", "client", "created", "expires"}
    assert token not in public.values()


@pytest.mark.parametrize(
    "header, expected",
    [
        ("Bearer pmt_abc-DEF_123", "pmt_abc-DEF_123"),
        ("bearer   pmt_abc", "pmt_abc"),
        ("Basic pmt_abc", None),
        ("Bearer sometoken", None),
        ("Bearer", None),
        ("", None),
        (None, None),
    ],
)
def test_bearer_from_header(header, expected):
    assert tokens.bearer_from_header(header) == expected


@pytest.mark.parametrize(
    "uri, ok",
    [
        ("http://127.0.0.1:39818/callback", True),
        ("http://localhost:1234/", False),  # RFC 8252 8.3: IP literals only
        ("http://[::1]:1234/cb", True),
        ("https://127.0.0.1:1234/cb", True),
        ("http://127.0.0.1/callback", False),  # no port
        ("http://example.org:1234/cb", False),
        ("http://127.0.0.1.example.org:1234/cb", False),
        ("http://user:pw@127.0.0.1:1234/cb", False),
        ("http://127.0.0.1:1234/cb#frag", False),
        ("javascript:alert(1)", False),
        ("ftp://127.0.0.1:21/", False),
        ("http://127.0.0.1:99999/", False),  # invalid port
        ("", False),
        (None, False),
        (1234, False),
    ],
)
def test_validate_redirect_uri(uri, ok):
    assert (tokens.validate_redirect_uri(uri) is not None) == ok


def test_validate_redirect_uri_length_limit():
    prefix = "http://127.0.0.1:1234/"
    uri = prefix + "x" * (tokens.MAX_REDIRECT_URI_LENGTH - len(prefix))
    assert tokens.validate_redirect_uri(uri) == uri
    assert tokens.validate_redirect_uri(uri + "x") is None


def test_sanitize_client_name():
    assert tokens.sanitize_client_name("ponymail-mcp 1.2 (Claude)") == "ponymail-mcp 1.2 (Claude)"
    assert tokens.sanitize_client_name("<script>x</script>") == "scriptx/script"
    assert tokens.sanitize_client_name("x" * 200) == "x" * tokens.MAX_CLIENT_NAME_LENGTH
    assert tokens.sanitize_client_name("") == "unknown client"
    assert tokens.sanitize_client_name(None) == "unknown client"
