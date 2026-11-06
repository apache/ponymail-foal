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
Alternative AAA library for Pony Mail Foal, selected with `aaa: module: acl` in ponymail.yaml.
Private lists are readable per user: aaa.acl maps the uid of an authoritative login to the lists
(list@domain, shell wildcards allowed) it may read. Any other login can read no private lists.
An example of authorization by list, whatever the way the user logged in (OAuth, token, ...).
"""

import fnmatch
from typing import Optional
import plugins.session


def normalize_listid(listid: str) -> str:
    """Turn either '<dev.example.org>' (list_raw) or 'dev@example.org' into 'dev@example.org'"""
    listid = listid.strip().strip("<>").lower()
    if "@" not in listid:
        listid = listid.replace(".", "@", 1)
    return listid


def can_access_email(session: plugins.session.SessionObject, email: dict) -> bool:
    """Determine if an email can be accessed by the current user"""
    # If public email, it can always be accessed
    if not email.get("private", True):  # Assume private if the flag is missing
        return True
    # If user can access the list, they can read the email
    return can_access_list(session, email.get("list_raw", None))


def can_access_list(session: plugins.session.SessionObject, listid: Optional[str]) -> bool:
    """Determine if a list can be accessed by the current user"""
    # Only trust the uid of an authoritative login, as anyone can choose their uid with other providers
    if not listid or not session.credentials or not session.credentials.authoritative:
        return False
    patterns = session.server.config.aaa.acl.get(session.credentials.uid, [])
    name = normalize_listid(listid)
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
