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

"""This is the user session handler for PyPony"""

import http.cookies
import time
import typing
import uuid

import aiohttp.web

import plugins.database
import plugins.server
import copy

FOAL_MAX_SESSION_AGE = 86400 * 7  # Max 1 week between visits before voiding a session
FOAL_SAVE_SESSION_INTERVAL = 3600  # Update sessions on disk max once per hour
DATABASE_NOT_CONNECTED = "Database not connected!"
OAUTH_PROVIDER_DEFAULT = "generic"
FOAL_COOKIE_NAME = "ponymail" # Name of cookie that stores the session id

class SessionCredentials:
    uid: str
    name: str
    email: str
    provider: str
    authoritative: bool
    admin: bool
    oauth_data: dict

    def __init__(self, doc):
        if doc:
            self.uid = doc.get("uid", "")
            self.name = doc.get("name", "")
            self.email = doc.get("email", "")
            self.oauth_provider = doc.get("oauth_provider", OAUTH_PROVIDER_DEFAULT)
            self.authoritative = doc.get("authoritative", False)
            self.admin = doc.get("admin", False)
            self.oauth_data = doc.get("oauth_data", {})
        else:
            self.uid = ""
            self.name = ""
            self.email = ""
            self.oauth_provider = OAUTH_PROVIDER_DEFAULT
            self.authoritative = False
            self.admin = False
            self.oauth_data = {}


class SessionObject:
    cid: typing.Optional[str]
    cookie: str
    created: int
    last_accessed: int
    credentials: typing.Optional[SessionCredentials]
    database: typing.Optional[plugins.database.Database]
    remote: str
    host: str
    server: plugins.server.BaseServer

    def __init__(self, server: plugins.server.BaseServer, **kwargs):
        self.database = None
        self.server = server
        self.created = int(time.time())
        self.host = "??"
        self.remote = "??"
        if kwargs:
            self.last_accessed = kwargs.get("last_accessed", 0)
            self.credentials = SessionCredentials(kwargs.get("credentials"))
            self.cookie = kwargs.get("cookie", "___")
            self.cid = kwargs.get("cid")
        else:
            self.last_accessed = self.created
            self.credentials = None
            self.cookie = str(uuid.uuid4())
            self.cid = None


async def get_session(
    server: plugins.server.BaseServer, request: aiohttp.web.BaseRequest
) -> SessionObject:
    session_id = None
    session = None
    now = int(time.time())
    if request.headers.get("cookie"):
        for cookie_header in request.headers.getall("cookie"):
            cookies: http.cookies.SimpleCookie = http.cookies.SimpleCookie(
                cookie_header
            )
            if FOAL_COOKIE_NAME in cookies:
                session_id = cookies[FOAL_COOKIE_NAME].value
                if not all(c in "abcdefg1234567890-" for c in session_id):
                    session_id = None
                break

    # Do we have the session in local memory?
    if session_id and session_id in server.data.sessions:
        x_session = server.data.sessions[session_id]
        if (now - x_session.last_accessed) > FOAL_MAX_SESSION_AGE:
            del server.data.sessions[session_id]
        else:

            # Make a copy so we don't have a race condition with the database pool object
            # In case the session is used twice within the same loop
            session = copy.copy(x_session)
            session.database = await server.dbpool.get()
            session.host = request.headers.get("X-Forwarded-Host", request.host)
            session.remote = request.remote

            # Do we need to update the timestamp in ES?
            if (now - session.last_accessed) > FOAL_SAVE_SESSION_INTERVAL:
                # Update the cached object too, or this fires on every request past the interval
                x_session.last_accessed = session.last_accessed = now
                await save_session(session)

            return session

    # If not in local memory, start a new session object
    session = SessionObject(server)
    session.database = await server.dbpool.get()
    session.host = request.headers.get("X-Forwarded-Host", request.host or "??")
    session.remote = request.remote or "??"

    # If a cookie was supplied, look for a session object in ES
    if session_id and session.database:
        try:
            session_doc = await session.database.get(
                session.database.dbs.db_session, id=session_id
            )
            last_update = session_doc["_source"]["updated"]
            session.cookie = session_id
            # Check that this cookie ain't too old. If it is, delete it and return bare-bones session object
            if (now - last_update) > FOAL_MAX_SESSION_AGE:
                await session.database.delete(
                    index=session.database.dbs.db_session, id=session_id
                )
                return session

            # Get CID and fecth the account data
            cid = session_doc["_source"]["cid"]
            if cid:
                account_doc = await session.database.get(
                    session.database.dbs.db_account, id=cid
                )
                creds = account_doc["_source"]["credentials"]
                internal = account_doc["_source"]["internal"]

                # Set session data
                session.cid = cid
                session.last_accessed = last_update
                creds["authoritative"] = (
                    internal.get("oauth_provider")
                    in server.config.oauth.authoritative_domains
                )
                creds["oauth_provider"] = internal.get("oauth_provider", OAUTH_PROVIDER_DEFAULT)
                creds["oauth_data"] = internal.get("oauth_data", {})
                # We update admin boolean whenever we fetch session doc, as they may have changed in yaml but not in ES.
                creds["admin"] = creds["authoritative"] and creds.get('email') in server.config.oauth.admins
                session.credentials = SessionCredentials(creds)

                # Save in memory storage
                server.data.sessions[session_id] = session

        except plugins.database.DBError:
            pass
    return session


async def set_session(server: plugins.server.BaseServer, cid: str, **credentials):
    """Create a new user session in the database"""
    session_id = str(uuid.uuid4())
    cookie: http.cookies.SimpleCookie = http.cookies.SimpleCookie()
    cookie[FOAL_COOKIE_NAME] = session_id
    session = SessionObject(
        server, last_accessed=int(time.time()), cookie=session_id, cid=cid
    )
    session.credentials = SessionCredentials(credentials)
    server.data.sessions[session_id] = session

    # Grab temporary DB handle since session objects at init do not have this
    # We just need this to be able to save the session in ES.
    session.database = await server.dbpool.get()

    # Save session and account data
    await save_session(session)
    await save_credentials(session)

    # Put DB handle back into the pool
    server.dbpool.put_nowait(session.database)
    return cookie[FOAL_COOKIE_NAME].OutputString()


async def save_session(session: SessionObject):
    """Save a session object in the ES database"""
    assert session.database, DATABASE_NOT_CONNECTED
    await session.database.index(
        index=session.database.dbs.db_session,
        id=session.cookie,
        body={
            "cookie": session.cookie,
            "cid": session.cid,
            "updated": session.last_accessed,
        },
    )


async def remove_session(session: SessionObject):
    """Remove a session object in the ES database"""
    assert session.database, DATABASE_NOT_CONNECTED
    await session.database.delete(index=session.database.dbs.db_session, id=session.cookie)


async def save_credentials(session: SessionObject):
    """Save a user account object in the ES database"""
    assert session.database, DATABASE_NOT_CONNECTED
    assert session.credentials, "Session object without credentials, cannot save!"
    await session.database.index(
        index=session.database.dbs.db_account,
        id=session.cid,
        body={
            "cid": session.cid,
            "credentials": {
                "email": session.credentials.email,
                "name": session.credentials.name,
                "uid": session.credentials.uid,
            },
            "internal": {
                "oauth_provider": session.credentials.oauth_provider,
                "oauth_data": session.credentials.oauth_data,
                "admin": session.credentials.admin,
            },
        },
    )
