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

# To be run as: python3 -m pytest test/test_aaa.py

import importlib
import os
import sys

import pytest

# The server plugins import each other as plugins.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import plugins.configuration
import plugins.session

PRIVATE_EMAIL = {"private": True, "list_raw": "<secret.example.org>"}
PUBLIC_EMAIL = {"private": False, "list_raw": "<dev.example.org>"}


def session_with(credentials):
    session = plugins.session.SessionObject(None)
    session.credentials = plugins.session.SessionCredentials(credentials) if credentials else None
    return session


ANONYMOUS = session_with(None)
OAUTH = session_with({"uid": "u", "authoritative": False})
AUTHORITATIVE = session_with({"uid": "u", "authoritative": True})


def load(name):
    return importlib.import_module(plugins.configuration.Configuration({"aaa": {"module": name}}).aaa.module_name)


def test_simple_by_default():
    assert plugins.configuration.Configuration({}).aaa.module_name == "plugins.aaa"


def test_unknown_module():
    with pytest.raises(ValueError, match="aaa.module must be one of"):
        plugins.configuration.Configuration({"aaa": {"module": "os"}})


@pytest.mark.parametrize("name", list(plugins.configuration.AAAConfig.MODULES))
def test_modules_provide_interface(name):
    aaa = load(name)
    assert callable(aaa.can_access_list) and callable(aaa.can_access_email)
    for session in (ANONYMOUS, OAUTH, AUTHORITATIVE):
        assert aaa.can_access_email(session, PUBLIC_EMAIL)
    assert not aaa.can_access_email(ANONYMOUS, {"list_raw": "<secret.example.org>"})  # Private if flag missing


def test_simple():
    aaa = load("simple")
    assert aaa.can_access_list(AUTHORITATIVE, "secret@example.org")
    assert aaa.can_access_email(AUTHORITATIVE, PRIVATE_EMAIL)
    for session in (ANONYMOUS, OAUTH):
        assert not aaa.can_access_list(session, "secret@example.org")
        assert not aaa.can_access_email(session, PRIVATE_EMAIL)


def test_public():
    aaa = load("public")
    for session in (ANONYMOUS, OAUTH, AUTHORITATIVE):
        assert not aaa.can_access_list(session, "secret@example.org")
        assert not aaa.can_access_email(session, PRIVATE_EMAIL)
