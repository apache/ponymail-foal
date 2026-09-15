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
"""

from typing import Optional
import plugins.session


def can_access_email(session: plugins.session.SessionObject, email: dict) -> bool:
    """Determine if an email can be accessed by the current user"""
    # If public email, it can always be accessed
    if not email.get("private", True): # Assume private if the flag is missing
        return True
    # If user can access the list, they can read the email
    return can_access_list(session, email.get("list_raw", None))

def can_access_list(session: plugins.session.SessionObject, listid: Optional[str]) -> bool:
    """Determine if a list can be accessed by the current user"""
    # Being authoritative (logged in via a configured OAuth domain) is REQUIRED
    # but NOT sufficient: a user may only read a private list they are actually
    # authorized for. Anything else fails closed.
    if not (session.credentials and session.credentials.authoritative):
        return False
    if not listid:
        return False
    return is_list_member(session, listid)


def is_list_member(session: plugins.session.SessionObject, listid: str) -> bool:
    """Determine whether the current user is authorized for THIS specific private list.

    Wire _list_acl() to the deployment's source of truth (a per-list
    owner/moderator/subscriber roster, or an explicit config ACL). Until a
    membership model exists, only globally-configured admins are granted, and
    everyone else is denied. Never grant a private list to every authoritative
    user again.
    """
    user = getattr(session.credentials, "email", None) or getattr(
        session.credentials, "uid", None
    )
    if not user:
        return False
    acl = _list_acl(listid)
    if acl is not None:
        return user in acl
    try:
        admins = set(getattr(server.config, "admins", None) or [])
    except NameError:
        admins = set()
    return user in admins


def _list_acl(listid: str):
    """Return the set of identities authorized for listid, or None if unknown.

    TODO(ponymail): wire this to the real per-list membership / subscriber /
    moderator source. Returning None (the default) makes is_list_member() fall
    back to the admin-only check above, which is safe (fail closed).
    """
    return None
