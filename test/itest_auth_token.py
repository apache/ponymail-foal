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

# Integration tests for plugins/auth_token.py, against ElasticSearch with the test data loaded.
# Run as: python3 -m pytest [-s] test/itest_auth_token.py
# Needs, besides the server of itest_integration.py on port 8080 (no token keys):
#   python3 test/itest_token_setup.py 8081 8082
#   (cd server; python3 main.py --config ponymail-token-8081.yaml &)
#   (cd server; python3 main.py --config ponymail-token-8082.yaml &)

import importlib.util
import os

import pytest
import requests
import yaml

import itest_integration

# The defaults match .github/workflows/integration-tests.yml
API_NO_TOKENS = os.environ.get("PONYMAIL_API", "http://localhost:8080/api")  # No token keys configured
API_TOKEN = os.environ.get("PONYMAIL_TOKEN_API", "http://localhost:8081/api")  # Token keys, replay_check: database
API_TOKEN2 = os.environ.get("PONYMAIL_TOKEN_API2", "http://localhost:8082/api")  # Second instance, same database
itest_integration.API_BASE = API_NO_TOKENS  # Used by get_cookies()
KEY_DIR = "test/itest-keys"
TEST_DOMAIN = "ponymail.apache.org"
TEST_LIST = "users"
PRIVATE_MONTH = "2019-09"  # The users@ emails of this month were imported as private
PRIVATE_HITS = 4

if not os.path.exists(os.path.join(KEY_DIR, "itest-reader.key")):
    pytest.skip("Token keys not found, run test/itest_token_setup.py first", allow_module_level=True)

# Sign with the client tool itself (the file name has a dash, so it can't be imported normally)
_spec = importlib.util.spec_from_file_location("api_token", "tools/api-token.py")
assert _spec and _spec.loader
api_token = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_token)


def token_request(api, endpoint, key_id, params=None, json_body=None, header=None, target=None):
    """Send a request signed with the given key; returns the response and the Authorization header used"""
    method = "GET" if json_body is None else "POST"
    req = requests.Request(method, f"{api}/{endpoint}", params=params, json=json_body).prepare()
    if header is None:
        key = api_token.load_key(os.path.join(KEY_DIR, f"{key_id}.key"))
        header = api_token.make_header(key, key_id, method, target or req.path_url, req.body or b"")
    req.headers["Authorization"] = header
    return requests.Session().send(req), header


def private_stats(api, key_id=None, cookies=None):
    params = {"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": PRIVATE_MONTH}
    if key_id:
        res, _ = token_request(api, "stats.lua", key_id, params=params)
    else:
        res = requests.get(f"{api}/stats.lua", params=params, cookies=cookies)
    assert res.status_code == 200, res.text
    return res.json()


def test_token_reads_private_list():
    jzon = private_stats(API_TOKEN, "itest-reader")
    assert jzon["hits"] == PRIVATE_HITS
    for email in jzon["emails"]:
        assert email["private"]
        assert email["list_raw"] == "<users.ponymail.apache.org>"
        res, _ = token_request(API_TOKEN, "email.lua", "itest-reader", params={"id": email["mid"]})
        assert res.status_code == 200, email["mid"]
        assert res.json()["private"]
        res, _ = token_request(API_TOKEN, "source.lua", "itest-reader", params={"id": email["mid"]})
        assert res.status_code == 200, email["mid"]
        assert "Message-ID:" in res.text or "Message-Id:" in res.text


def test_token_credentials():
    res, _ = token_request(API_TOKEN, "preferences.lua", "itest-reader")
    assert res.status_code == 200, res.text
    assert res.json()["login"]["credentials"] == {"uid": "reader", "email": "", "fullname": "Token Reader"}


def test_token_authorized_by_aaa():
    # itest-guest authenticates fine, but plugins/aaa.py only grants private lists to authoritative logins
    mids = [email["mid"] for email in private_stats(API_TOKEN, "itest-reader")["emails"]]
    assert private_stats(API_TOKEN, "itest-guest")["hits"] == 0
    for mid in mids:
        res, _ = token_request(API_TOKEN, "email.lua", "itest-guest", params={"id": mid})
        assert res.status_code == 404, mid


def test_token_post_json():
    res, _ = token_request(
        API_TOKEN,
        "stats.json",
        "itest-reader",
        json_body={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": PRIVATE_MONTH},
    )
    assert res.status_code == 200, res.text
    assert res.json()["hits"] == PRIVATE_HITS


def test_other_sessions_unchanged():
    assert private_stats(API_TOKEN)["hits"] == 0  # anonymous
    assert (
        private_stats(API_TOKEN, cookies=itest_integration.get_cookies("user"))["hits"] == PRIVATE_HITS
    )  # OAuth login


def test_tokens_ignored_without_keys():
    assert private_stats(API_NO_TOKENS, "itest-reader")["hits"] == 0


def test_replay_refused_across_instances():
    res, header = token_request(API_TOKEN, "preferences.lua", "itest-reader")
    assert res.status_code == 200, res.text
    for api in (API_TOKEN, API_TOKEN2):
        res, _ = token_request(api, "preferences.lua", "itest-reader", header=header)
        assert res.status_code == 401
        assert "already been used" in res.text

    # The nonce is recorded in the session index
    nonce = dict(part.split("=", 1) for part in header.split(" ", 1)[1].split(","))["nonce"]
    with open("server/ponymail.yaml") as f:
        dbconfig = yaml.safe_load(f)["database"]
    url = dbconfig["dburl"].rstrip("/") + f"/{dbconfig['db_prefix']}-session/_doc/token:itest-reader:{nonce}"
    res = requests.get(url)
    assert res.status_code == 200, res.text
    assert res.json()["_source"]["cookie"] == f"token:itest-reader:{nonce}"


def test_expired_key_refused():
    res, _ = token_request(API_TOKEN, "preferences.lua", "itest-expired")
    assert res.status_code == 401
    assert "expired" in res.text


def test_tampered_request_refused():
    # Signed for the dev list, sent for the users list
    target = f"/api/stats.lua?list=dev&domain={TEST_DOMAIN}&d={PRIVATE_MONTH}"
    res, _ = token_request(
        API_TOKEN,
        "stats.lua",
        "itest-reader",
        params={"list": "users", "domain": TEST_DOMAIN, "d": PRIVATE_MONTH},
        target=target,
    )
    assert res.status_code == 401
    assert "Invalid signature" in res.text


def test_write_endpoints_refused():
    for endpoint in ("compose.json", "mgmt.json"):
        res, _ = token_request(API_TOKEN, endpoint, "itest-reader", json_body={})
        assert res.status_code == 401, endpoint
        assert "read-only" in res.text
