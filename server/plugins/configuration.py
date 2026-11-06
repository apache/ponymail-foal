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

import base64
import datetime
import typing


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


def parse_expiry(key_id: str, value: typing.Any) -> typing.Optional[int]:
    """
    Turn a YAML expiry into a UNIX timestamp, None if not set.
    A date (2027-01-01) expires at the start of that day, UTC. A date and time without a timezone is taken as UTC.
    """
    if value is None:
        return None
    if isinstance(value, str):  # Quoted in YAML, or a form YAML doesn't recognise
        try:
            value = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Token key {key_id}: expires must be a date (YYYY-MM-DD) or ISO 8601 date and time")
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return int(value.timestamp())
    if isinstance(value, datetime.date):
        return int(datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc).timestamp())
    raise ValueError(f"Token key {key_id}: expires must be a date (YYYY-MM-DD) or ISO 8601 date and time")


class TokenKey:
    """A single API token: an Ed25519 public key, the credentials it authenticates as and when it expires"""

    key_id: str
    public_key: typing.Any  # cryptography Ed25519PublicKey
    uid: str
    name: str
    email: str
    authoritative: bool  # As for an OAuth provider: whether the access control module may trust this login
    expires: typing.Optional[int]  # UNIX timestamp from which the key is refused, None for no expiry

    def __init__(self, key_id: str, subyaml: dict):
        # Imported here so the dependency is only needed when tokens are configured
        import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519
        import cryptography.hazmat.primitives.serialization as serialization

        self.key_id = key_id
        pubkey = str(subyaml.get("public_key", "")).strip()
        if pubkey.startswith("-----BEGIN"):
            loaded = serialization.load_pem_public_key(pubkey.encode("ascii"))
            if not isinstance(loaded, ed25519.Ed25519PublicKey):
                raise ValueError(f"Token key {key_id}: public_key must be an Ed25519 key")
            self.public_key = loaded
        else:  # Base64-encoded raw 32 byte key
            self.public_key = ed25519.Ed25519PublicKey.from_public_bytes(base64.b64decode(pubkey))
        self.uid = str(subyaml.get("uid", key_id))
        self.name = str(subyaml.get("name", self.uid))
        self.email = str(subyaml.get("email", ""))
        self.authoritative = subyaml.get("authoritative", False)
        if not isinstance(self.authoritative, bool):
            raise ValueError(f"Token key {key_id}: authoritative must be true or false")
        self.expires = parse_expiry(key_id, subyaml.get("expires"))


class TokenConfig:
    REPLAY_CHECKS = ("memory", "database")
    max_skew: int
    replay_check: str
    keys: typing.Dict[str, TokenKey]

    def __init__(self, subyaml: dict):
        self.max_skew = int(subyaml.get("max_skew", 60))  # Max age (seconds) of a signed request
        # Where used nonces are remembered: "memory" (per server process) or "database" (shared by all instances)
        self.replay_check = str(subyaml.get("replay_check", "memory"))
        if self.replay_check not in self.REPLAY_CHECKS:
            raise ValueError(f"tokens.replay_check must be one of {', '.join(self.REPLAY_CHECKS)}")
        # Token authentication is enabled by configuring keys; cryptography is only needed then
        self.keys = {key_id: TokenKey(key_id, entry) for key_id, entry in (subyaml.get("keys") or {}).items()}


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
    tokens: TokenConfig

    def __init__(self, yml: dict):
        self.server = ServerConfig(yml.get("server", {}))
        self.database = DBConfig(yml.get("database", {}))
        self.tasks = TaskConfig(yml.get("tasks", {}))
        self.oauth = OAuthConfig(yml.get("oauth", {}))
        self.ui = UIConfig(yml.get("ui", {}))
        self.tokens = TokenConfig(yml.get("tokens", {}))


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
