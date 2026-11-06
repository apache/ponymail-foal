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
Prepare the servers for test/itest_auth_token.py.

Run from the top directory, after tools/setup.py has written server/ponymail.yaml:

    python3 test/itest_token_setup.py 8081 8082

Generates the token keys in test/itest-keys/ and writes server/ponymail-token-<port>.yaml for each port:
a copy of ponymail.yaml with the token keys and the database replay check, so that all
instances share the used nonces. Then start each with: main.py --config ponymail-token-<port>.yaml
"""

import base64
import os
import sys

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

KEY_DIR = "test/itest-keys"

# Key id: credentials and expiry of the key
KEYS = {
    "itest-reader": {"uid": "reader", "name": "Token Reader", "authoritative": True, "expires": "2099-01-01"},
    "itest-guest": {"uid": "guest"},  # Authenticated, but not authorized for private lists by plugins/aaa.py
    "itest-expired": {"uid": "reader", "authoritative": True, "expires": "2020-01-01"},
}


def main(ports):
    os.makedirs(KEY_DIR, exist_ok=True)
    keys = {}
    for key_id, settings in KEYS.items():
        key = ed25519.Ed25519PrivateKey.generate()
        with open(os.path.join(KEY_DIR, f"{key_id}.key"), "wb") as f:
            f.write(
                key.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                )
            )
        raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        keys[key_id] = dict(settings, public_key=base64.b64encode(raw).decode("ascii"))

    with open("server/ponymail.yaml") as f:
        config = yaml.safe_load(f)
    config["tokens"] = {"replay_check": "database", "keys": keys}
    for port in ports:
        config["server"]["port"] = int(port)
        path = f"server/ponymail-token-{port}.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(config, f)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["8081", "8082"])
