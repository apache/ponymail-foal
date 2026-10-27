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
Sample client for Pony Mail session tokens (see docs/session_tokens.md).

Gets a token with the user's approval in the browser, lists the last month's emails
of a list with it - private lists included, if the user can read them - and revokes the
token when done. Uses the Python standard library only.

    python3 token-client.py https://lists.example.org dev@project.example.org
    python3 token-client.py --manual https://lists.example.org dev@project.example.org

With --manual the token is pasted in instead: create one from the "Session tokens"
entry of the user menu in the web UI.
"""

import argparse
import getpass
import http.server
import json
import secrets
import sys
import typing
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CLIENT_NAME = "token-client.py"
APPROVAL_TIMEOUT = 300  # Seconds to wait for the user to approve the request in the browser


def api(base: str, endpoint: str, token: str, **params: typing.Any) -> dict:
    """POST a JSON request to the API, authenticated with the session token"""
    req = urllib.request.Request(
        f"{base}/api/{endpoint}",
        data=json.dumps(params).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        return json.load(res)


def revoke(base: str, token: str) -> None:
    """A token may always revoke itself. Never let cleanup hide the outcome of the main work."""
    try:
        api(base, "token.json", token, action="revoke")
        print("Token revoked.")
    except urllib.error.HTTPError as e:
        if e.code == 403:  # Expired or already revoked: the server no longer knows the token
            print("Token was already invalid.")
        else:
            print(f"Could not revoke the token (HTTP {e.code}); it stays valid until it expires.", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Could not revoke the token ({e.reason}); it stays valid until it expires.", file=sys.stderr)


def token_from_browser(base: str, ttl: typing.Optional[int]) -> str:
    """Loopback hand-off: ask the user to approve the request in the browser, receive the token here"""
    state = secrets.token_urlsafe(16)
    result: typing.Dict[str, str] = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", 0))
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            result.update({k: v[0] for k, v in fields.items()})
            self.send_response(200)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab and return to the terminal.\n")

        def log_message(self, *args: typing.Any) -> None:
            pass  # Keep the token out of the terminal

    # Port 0: let the OS pick a free port. Only ever listen on the loopback interface.
    server = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    server.timeout = APPROVAL_TIMEOUT
    query = {
        "client": CLIENT_NAME,
        "redirect_uri": f"http://127.0.0.1:{server.server_port}/callback",
        "state": state,
    }
    if ttl:
        query["ttl"] = str(ttl)
    url = f"{base}/token.html?{urllib.parse.urlencode(query)}"
    print(f"Approve the request in your browser. If it does not open, visit:\n  {url}", file=sys.stderr)
    webbrowser.open(url)
    server.handle_request()  # Wait for the one hand-off POST (or time out)
    server.server_close()

    if not result:
        sys.exit("No answer from the browser in time.")
    if not secrets.compare_digest(result.get("state", ""), state):
        sys.exit("State mismatch: ignoring a hand-off this script did not ask for.")
    if result.get("error"):
        sys.exit(f"Request refused in the browser: {result['error']}")
    return result["token"]


def main() -> None:
    parser = argparse.ArgumentParser(description="List the newest emails of a list using a Pony Mail session token")
    parser.add_argument("base", help="Base URL of the Pony Mail site, e.g. https://lists.example.org")
    parser.add_argument("list", help="List address, e.g. dev@project.example.org")
    parser.add_argument("--manual", action="store_true", help="Paste a token instead of approving in the browser")
    parser.add_argument("--ttl", type=int, help="Requested token lifetime in seconds (server default if omitted)")
    parser.add_argument("--keep", action="store_true", help="Do not revoke the token when done")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    listname, _, domain = args.list.partition("@")

    token = getpass.getpass("Session token: ") if args.manual else token_from_browser(base, args.ttl)
    try:
        me = api(base, "preferences.json", token).get("login", {})
        if not me.get("credentials"):
            sys.exit("The token was not accepted (expired, revoked or mistyped).")
        print(f"Authenticated as {me['credentials']['email']}, token expires at epoch {me['token']['expires']}")

        stats = api(base, "stats.json", token, list=listname, domain=domain, d="lte=1M", emailsOnly=True)
        print(f"{stats.get('hits', 0)} emails in {args.list} in the last month, newest first:")
        for email in sorted(stats.get("emails", []), key=lambda e: e["epoch"], reverse=True)[:10]:
            print(f"  {email['subject']}  ({email['from']})")
    finally:
        if not args.keep:
            revoke(base, token)


if __name__ == "__main__":
    main()
