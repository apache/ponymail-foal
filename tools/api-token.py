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
Create and use read-only API token keys (see server/plugins/auth_token.py).

  api-token.py generate reader-bot --uid reader --authoritative --expires 2027-01-01
      Writes reader-bot.key (keep it secret) and prints the ponymail.yaml snippet.

  api-token.py header reader-bot.key reader-bot GET '/api/stats.lua?list=private&domain=example.org'
      Prints an Authorization header for that exact request (valid for tokens.max_skew seconds, once).

  api-token.py fetch reader-bot.key reader-bot https://lists.example.org/api/email.json --data '{"id": "..."}'
      Signs and performs the request, printing the response body.
"""

import argparse
import base64
import datetime
import hashlib
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

AUTH_SCHEME = "PonyMail-Ed25519"


def signing_message(timestamp: str, nonce: str, method: str, target: str, body: bytes) -> bytes:
    """Must match plugins.auth_token.signing_message in the server"""
    return "\n".join((timestamp, nonce, method.upper(), target, hashlib.sha256(body).hexdigest())).encode("utf-8")


def load_key(path: str) -> ed25519.Ed25519PrivateKey:
    with open(path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        sys.exit(f"{path} is not an Ed25519 private key")
    return key


def make_header(key: ed25519.Ed25519PrivateKey, key_id: str, method: str, target: str, body: bytes) -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(8)
    sig = base64.b64encode(key.sign(signing_message(timestamp, nonce, method, target, body))).decode("ascii")
    return f"{AUTH_SCHEME} key={key_id},ts={timestamp},nonce={nonce},sig={sig}"


def generate(args: argparse.Namespace) -> None:
    if args.expires:
        try:
            datetime.date.fromisoformat(args.expires)
        except ValueError:
            sys.exit(f"--expires must be a date as YYYY-MM-DD, not {args.expires!r}")
    path = args.out or f"{args.key_id}.key"
    if os.path.exists(path):
        sys.exit(f"{path} already exists, not overwriting it")
    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print(f"Private key written to {path}. Add this to ponymail.yaml:\n")
    print("tokens:\n  keys:")
    print(f"    {args.key_id}:")
    print(f"      public_key: \"{base64.b64encode(raw).decode('ascii')}\"")
    if args.uid:
        print(f'      uid: "{args.uid}"')
    if args.authoritative:
        print("      authoritative: true")
    if args.expires:
        print(f"      expires: {args.expires}")


def header(args: argparse.Namespace) -> None:
    body = (args.data or "").encode("utf-8")
    print("Authorization: " + make_header(load_key(args.keyfile), args.key_id, args.method, args.target, body))


def fetch(args: argparse.Namespace) -> None:
    body = (args.data or "").encode("utf-8")
    method = "POST" if args.data is not None else "GET"
    url = urllib.parse.urlsplit(args.url)
    target = url.path + (f"?{url.query}" if url.query else "")
    req = urllib.request.Request(args.url, data=body if method == "POST" else None, method=method)
    req.add_header("Authorization", make_header(load_key(args.keyfile), args.key_id, method, target, body))
    if method == "POST":
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as response:
        sys.stdout.buffer.write(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Pony Mail read-only API token helper")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Create a new key pair")
    gen.add_argument("key_id", help="Name of the key, as used in ponymail.yaml")
    gen.add_argument("--uid", help="User id the key authenticates as, for the yaml snippet (default: the key id)")
    gen.add_argument(
        "--authoritative", action="store_true", help="Let the access control module trust this login, as for OAuth"
    )
    gen.add_argument("--out", help="Private key file (default: <key_id>.key)")
    gen.add_argument("--expires", help="Date (YYYY-MM-DD, UTC) from which the key is refused, for the yaml snippet")
    gen.set_defaults(func=generate)

    hdr = sub.add_parser("header", help="Print an Authorization header for one request")
    hdr.add_argument("keyfile")
    hdr.add_argument("key_id")
    hdr.add_argument("method", help="GET or POST")
    hdr.add_argument("target", help="Path and query string exactly as sent, e.g. /api/stats.lua?list=dev&domain=x.org")
    hdr.add_argument("--data", help="Request body, if any")
    hdr.set_defaults(func=header)

    get = sub.add_parser("fetch", help="Sign and perform a request")
    get.add_argument("keyfile")
    get.add_argument("key_id")
    get.add_argument("url")
    get.add_argument("--data", help="JSON body; makes the request a POST")
    get.set_defaults(func=fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
