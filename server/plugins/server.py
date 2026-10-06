#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import asyncio
import typing

import aiohttp
from elasticsearch import AsyncElasticsearch

import plugins.configuration
import plugins.offloader


class Endpoint:
    exec: typing.Callable
    token_allowed: bool  # May be called with a session token; off unless the endpoint opts in

    def __init__(self, executor, token_allowed: bool = False):
        self.exec = executor
        self.token_allowed = token_allowed


class StreamingEndpoint:
    exec: typing.Callable
    token_allowed: bool  # May be called with a session token; off unless the endpoint opts in

    def __init__(self, executor, token_allowed: bool = False):
        self.exec = executor
        self.token_allowed = token_allowed


class BaseServer:
    """Main server class, base def"""

    config: plugins.configuration.Configuration
    server: typing.Optional[aiohttp.web.Server]
    data: plugins.configuration.InterData
    handlers: typing.Dict[str, Endpoint]
    database: AsyncElasticsearch
    dbpool: asyncio.Queue
    runners: plugins.offloader.ExecutorPool
    streamlock: asyncio.Lock
    # provided by background.py
    library_version: str
    engine_version: str
    background_event: asyncio.Event # tell background.py to stop
