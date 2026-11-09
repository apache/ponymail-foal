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

    def can_access_list(self, session, listid):
        return listid in ("dev@example.org", "<dev.example.org>")


class Incomplete(plugins.aaa_plugin.AAAPlugin):
    """Test plugin that forgot can_access_list"""


class NotAPlugin:
    def can_access_list(self, session, listid):
        return True


def test_default_is_plugins_aaa():
    assert plugins.configuration.Configuration({}).aaa.plugin is None
    assert plugins.configuration.Configuration({"aaa": None}).aaa.plugin is None
    aaa = load(None)
    assert isinstance(aaa, plugins.aaa_plugin.ModuleAAA) and aaa.module is plugins.aaa
    assert aaa.can_access_list(AUTHORITATIVE, "secret@example.org")
    assert aaa.can_access_email(AUTHORITATIVE, PRIVATE_EMAIL)
    for session in (ANONYMOUS, OAUTH):
        assert not aaa.can_access_list(session, "secret@example.org")
        assert not aaa.can_access_email(session, PRIVATE_EMAIL)
        assert aaa.can_access_email(session, PUBLIC_EMAIL)


def test_public():
    aaa = load("plugins.aaa_public.PublicAAA")
    assert isinstance(aaa, plugins.aaa_public.PublicAAA) and aaa.server is SERVER
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
        ("plugins.aaa.can_access_list", "is not a subclass"),
        (f"{__name__}.NotAPlugin", "is not a subclass"),
        ("plugins.aaa_plugin.AAAPlugin", "does not implement can_access_list"),
        (f"{__name__}.Incomplete", "does not implement can_access_list"),
    ],
)
def test_unusable_plugin(plugin, error):
    with pytest.raises(ValueError, match=error):
        load(plugin)
