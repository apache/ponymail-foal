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
Alternative access control for Pony Mail Foal, selected with
`aaa: plugin: plugins.aaa_public.PublicAAA` in ponymail.yaml.
No one can access private lists, whatever their login, e.g. for a public mirror of an archive.
It is also the smallest example of an access control plugin (see plugins/aaa_plugin.py).
"""

import typing

import plugins.aaa_plugin
import plugins.session


class PublicAAA(plugins.aaa_plugin.AAAPlugin):
    """Private lists are readable by no one"""

    def can_access_email(self, session: plugins.session.SessionObject, email: dict) -> bool:
        return not email.get("private", True)  # Assume private if the flag is missing

    def can_access_list(self, session: plugins.session.SessionObject, _listid: typing.Optional[str]) -> bool:
        return False
