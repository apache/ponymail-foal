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

import os
import sys
import typing

import pytest

# The server plugins import each other as plugins.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import plugins.aaa
import plugins.aaa_plugin
import plugins.aaa_public
import plugins.configuration
import plugins.session

PRIVATE_EMAIL = {"private": True, "list_raw": "<secret.example.org>"}
PUBLIC_EMAIL = {"private": False, "list_raw": "<dev.example.org>"}
SERVER: typing.Any = object()  # The plugins here don't use the server


def session_with(credentials):
    session = plugins.session.SessionObject(None)
    session.credentials = plugins.session.SessionCredentials(credentials) if credentials else None
    return session


ANONYMOUS = session_with(None)
OAUTH = session_with({"uid": "u", "authoritative": False})
AUTHORITATIVE = session_with({"uid": "u", "authoritative": True})


def load(plugin):
    return plugins.aaa_plugin.load(SERVER, plugins.configuration.Configuration({"aaa": {"plugin": plugin}}).aaa.plugin)


class OnlyDev(plugins.aaa_plugin.AAAPlugin):
    """Test plugin: anyone may read the dev list"""

    def can_access_email(self, session, email):
        return not email.get("private", True) or self.can_access_list(session, email.get("list_raw"))

    def can_access_list(self, session, listid):
        return listid in ("dev@example.org", "<dev.example.org>")


class NoListCheck(plugins.aaa_plugin.AAAPlugin):
    """Test plugin that forgot can_access_list"""

    def can_access_email(self, session, email):
        return True


class NoEmailCheck(plugins.aaa_plugin.AAAPlugin):
    """Test plugin that forgot can_access_email"""

    def can_access_list(self, session, listid):
        return True


class NotAPlugin:
    def can_access_list(self, session, listid):
        return True


def test_default():
    assert plugins.configuration.Configuration({}).aaa.plugin is None
    assert plugins.configuration.Configuration({"aaa": None}).aaa.plugin is None
    aaa = load(None)
    assert type(aaa) is plugins.aaa.AuthoritativeAAA and aaa.server is SERVER
    assert type(load("plugins.aaa.AuthoritativeAAA")) is plugins.aaa.AuthoritativeAAA
    assert aaa.can_access_list(AUTHORITATIVE, "secret@example.org")
    assert aaa.can_access_email(AUTHORITATIVE, PRIVATE_EMAIL)
    for session in (ANONYMOUS, OAUTH):
        assert not aaa.can_access_list(session, "secret@example.org")
        assert not aaa.can_access_email(session, PRIVATE_EMAIL)
        assert aaa.can_access_email(session, PUBLIC_EMAIL)


def test_public():
    aaa = load("plugins.aaa_public.PublicAAA")
    assert isinstance(aaa, plugins.aaa_public.PublicAAA) and aaa.server is SERVER
    assert not isinstance(aaa, plugins.aaa.AuthoritativeAAA)  # A sibling, not a variant of the default
    for session in (ANONYMOUS, OAUTH, AUTHORITATIVE):
        assert not aaa.can_access_list(session, "secret@example.org")
        assert not aaa.can_access_email(session, PRIVATE_EMAIL)
        assert not aaa.can_access_email(session, {"list_raw": "<secret.example.org>"})  # Private if flag missing
        assert aaa.can_access_email(session, PUBLIC_EMAIL)


def test_any_importable_plugin():
    aaa = load(f"{__name__}.OnlyDev")
    assert aaa.can_access_email(ANONYMOUS, {"private": True, "list_raw": "<dev.example.org>"})
    assert not aaa.can_access_email(ANONYMOUS, PRIVATE_EMAIL)


@pytest.mark.parametrize(
    "plugin,error",
    [
        ("plugins.nonexistent.AAA", "not found"),
        ("plugins.aaa_public.Nonexistent", "not found"),
        ("PublicAAA", "not found"),  # No module
        ("plugins.aaa", "is not a subclass"),  # A module, not a class
        ("plugins.aaa_plugin.load", "is not a subclass"),  # A function
        (f"{__name__}.NotAPlugin", "is not a subclass"),
        ("plugins.aaa_plugin.AAAPlugin", "does not implement can_access_email, can_access_list"),
        (f"{__name__}.NoListCheck", "does not implement can_access_list"),
        (f"{__name__}.NoEmailCheck", "does not implement can_access_email"),
        ("plugins.aaa.AAAPlugin", "not found"),  # The base class lives in plugins.aaa_plugin
    ],
)
def test_unusable_plugin(plugin, error):
    with pytest.raises(ValueError, match=error):
        load(plugin)
