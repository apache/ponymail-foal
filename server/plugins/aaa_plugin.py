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
Access control (AAA) plugins for Pony Mail Foal.

An access control plugin is a subclass of AAAPlugin, selected by its dotted path with
`aaa: plugin: <module>.<class>` in ponymail.yaml, e.g. plugins.aaa_public.PublicAAA.
The default is plugins.aaa.AuthoritativeAAA. The server creates one instance at startup,
as server.aaa, which endpoints and plugins ask whether the current session may read a list
or an email. A plugin must implement both methods itself.
"""

import abc
import importlib
import typing

import plugins.server
import plugins.session

DEFAULT_PLUGIN = "plugins.aaa.AuthoritativeAAA"


class AAAPlugin(abc.ABC):
    """Base class of access control plugins"""

    server: plugins.server.BaseServer

    def __init__(self, server: plugins.server.BaseServer):
        self.server = server

    @abc.abstractmethod
    def can_access_email(self, session: plugins.session.SessionObject, email: dict) -> bool:
        """Determine if an email can be accessed by the current user"""

    @abc.abstractmethod
    def can_access_list(self, session: plugins.session.SessionObject, listid: typing.Optional[str]) -> bool:
        """Determine if a private list can be accessed by the current user"""


def load(server: plugins.server.BaseServer, plugin: typing.Optional[str]) -> AAAPlugin:
    """Create the access control plugin named by aaa.plugin, raising ValueError if it is not a usable AAAPlugin"""
    plugin = plugin or DEFAULT_PLUGIN
    module_name, _, class_name = plugin.rpartition(".")
    try:
        cls = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError, ValueError) as e:
        raise ValueError(f"aaa.plugin {plugin!r} not found: {e}")
    if not isinstance(cls, type) or not issubclass(cls, AAAPlugin):
        raise ValueError(f"aaa.plugin {plugin!r} is not a subclass of plugins.aaa_plugin.AAAPlugin")
    missing = getattr(cls, "__abstractmethods__", None)
    if missing:
        raise ValueError(f"aaa.plugin {plugin!r} does not implement {', '.join(sorted(missing))}")
    return cls(server)
