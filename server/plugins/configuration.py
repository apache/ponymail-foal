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

class ServerConfig:
    port: int
    ip: str

    def __init__(self, subyaml: dict):
        self.ip = subyaml.get("bind", "0.0.0.0")
        self.port = int(subyaml.get("port", 8080))


class TaskConfig:
    refresh_rate: int

    def __init__(self, subyaml: dict):
        self.refresh_rate = int(subyaml.get("refresh_rate", 150))


class UIConfig:
    wordcloud: bool
    mailhost: str
    sender_domains: str
    traceback: bool
    mgmt_enabled: bool
    focus_domain: str
    fully_delete: bool

    def __init__(self, subyaml: dict):
        self.wordcloud = bool(subyaml.get("wordcloud", False))
        self.mailhost = subyaml.get("mailhost", "")  # Default to nothing (disabled)
        self.sender_domains = subyaml.get(
            "sender_domains", ""
        )  # Default to nothing (disabled)
        # Default to spitting out traceback to web clients
        # Set to false in yaml to redirect to stderr instead.
        self.traceback = subyaml.get("traceback", True)
        self.mgmt_enabled = bool(subyaml.get("mgmtconsole", False))  # Whether to enable online mgmt component or not
        self.fully_delete = bool(subyaml.get("allow_delete", False))  # Whether to enforce full expunging of deleted emails
        # Default to all lists, "*". Use "" for host. Wildcard subdomain globs also supported
        self.focus_domain = subyaml.get("focus_domain", "*")


class OAuthConfig:
    authoritative_domains: list
    admins: list
    google_client_id: str
    github_client_id: str
    github_client_secret: str
    providers: dict # generic providers

    def __init__(self, subyaml: dict):
        self.authoritative_domains = subyaml.get("authoritative_domains", [])
        self.admins = subyaml.get("admins", [])
        self.google_client_id = subyaml.get("google_client_id", "")
        self.github_client_id = subyaml.get("github_client_id", "")
        self.github_client_secret = subyaml.get("github_client_secret", "")
        self.providers = subyaml.get("providers", {})


class AAAConfig:
    # Access control implementations that can be selected, by name
    MODULES = {
        "simple": "plugins.aaa",  # Private lists readable by users of an authoritative OAuth provider, the default
        "public": "plugins.aaa_public",  # No access to private lists for anyone
    }
    module: str
    module_name: str

    def __init__(self, subyaml: dict):
        self.module = str(subyaml.get("module", "simple"))
        if self.module not in self.MODULES:
            raise ValueError(f"aaa.module must be one of {', '.join(self.MODULES)}, not {self.module!r}")
        self.module_name = self.MODULES[self.module]


class DBConfig:
    dburl: str
    hostname: str
    port: int
    secure: bool
    url_prefix: str
    db_prefix: str
    max_hits: int
    max_lists: int
    pool_size: int

    def __init__(self, subyaml: dict):
        self.dburl = str(subyaml.get("dburl", ""))
        self.hostname = str(subyaml.get("server", "localhost"))
        self.port = int(subyaml.get("port", 9200))
        self.secure = bool(subyaml.get("secure", False))
        self.url_prefix = subyaml.get("url_prefix", "")
        self.db_prefix = str(subyaml.get("db_prefix", "ponymail"))
        self.max_hits = int(subyaml.get("max_hits", 5000))
        self.max_lists = int(subyaml.get("max_lists", 8192))
        self.pool_size = int(subyaml.get("pool_size", 15))


class Configuration:
    server: ServerConfig
    database: DBConfig
    tasks: TaskConfig
    oauth: OAuthConfig
    ui: UIConfig
    aaa: AAAConfig

    def __init__(self, yml: dict):
        self.server = ServerConfig(yml.get("server", {}))
        self.database = DBConfig(yml.get("database", {}))
        self.tasks = TaskConfig(yml.get("tasks", {}))
        self.oauth = OAuthConfig(yml.get("oauth", {}))
        self.ui = UIConfig(yml.get("ui", {}))
        self.aaa = AAAConfig(yml.get("aaa", {}))


class InterData:
    """
        A mix of various global variables used throughout processes
    """

    lists: dict
    sessions: dict
    activity: dict

    def __init__(self):
        self.lists = {}
        self.sessions = {}
        self.activity = {}
