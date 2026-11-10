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
This is the AAA library for Pony Mail codename Foal
It handles rights management for lists.
AuthoritativeAAA is the default access control plugin (see plugins/aaa_plugin.py).
"""

import typing

import plugins.aaa_plugin
import plugins.session


class AuthoritativeAAA(plugins.aaa_plugin.AAAPlugin):
    """Private lists are readable by users of an authoritative OAuth provider"""

    def can_access_email(self, session: plugins.session.SessionObject, email: dict) -> bool:
        """Determine if an email can be accessed by the current user"""
        # If public email, it can always be accessed
        if not email.get("private", True):  # Assume private if the flag is missing
            return True
        # If user can access the list, they can read the email
        return self.can_access_list(session, email.get("list_raw", None))

    def can_access_list(self, session: plugins.session.SessionObject, _listid: typing.Optional[str]) -> bool:
        """Determine if a list can be accessed by the current user"""
        # If logged in via a known oauth, we assume access for now...TO BE CHANGED
        if session.credentials and session.credentials.authoritative:
            return True
        return False
