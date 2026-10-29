<!---
 Licensed to the Apache Software Foundation (ASF) under one or more
 contributor license agreements.  See the NOTICE file distributed with
 this work for additional information regarding copyright ownership.
 The ASF licenses this file to You under the Apache License, Version 2.0
 (the "License"); you may not use this file except in compliance with
 the License.  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# Session Tokens

A session token is a short-lived credential that lets a script, a command-line
tool or an MCP server read the archives **as you**, including the private
lists you can read, without ever seeing your browser cookie. The tool sends it
with each request:

```
Authorization: Bearer pmt_...
```

Session tokens are off by default. An operator turns them on with
`tokens.enabled` in `ponymail.yaml` (see [configuration.md](configuration.md#tokens)).

## What a token can and cannot do

A token can call the read-only endpoints: `stats`, `email`, `thread`,
`source`, `mbox`, `plain`, `preferences`, `pminfo` and `gravatar`. Every other
endpoint refuses it with `403`, so a token **cannot**:

- send email (`compose`),
- use the management console (`mgmt`),
- log in or create, list or revoke other tokens (`oauth`, `token`).

The one exception is that a token may revoke **itself**.

## Getting a token

### From the user menu (copy and paste)

1. Log in to the web UI.
2. Open the user menu and choose **Session tokens**.
3. Under **Create a token**, give it a name you will recognise later, pick a
   lifetime and click **Create token**.
4. Copy the token. It is shown **once** and cannot be shown again.

### Handed to a local program (browser approval)

A program running on your computer can ask for a token itself. It opens
`token.html` in your browser with its name, a loopback `redirect_uri` and a
random `state` value. The page shows which program is asking and for how
long. If you click **Approve**, the token is posted back to the program on
`127.0.0.1`. If you click **Deny**, the program is told so. The protocol is
described in [API.md](API.md#browser-hand-off-webuitokenhtml).

Only approve a request you started yourself, just now, from a tool you trust.

## Lifecycle

| Event | Effect on tokens |
|-------|------------------|
| Token created | Valid for its lifetime: `tokens.ttl` seconds by default (3600). A client may ask for any lifetime from 60 seconds up to `tokens.max_ttl` (86400). A lifetime outside that range is refused, not adjusted. You can hold at most `tokens.max_per_user` live tokens (10); creating another is refused until you revoke one or one expires. |
| Lifetime ends | The token stops working. Nothing needs to be done. |
| The token revokes itself (`token.json` with `action=revoke`, or `preferences` with `logout`, sent with the token) | That token stops working. The browser session it came from is not affected. |
| You log out of the browser session that created it | Every token created from that session stops working. |
| That browser session expires on the server (one week without a visit) | Every token created from that session stops working. |
| You revoke it from **Session tokens** (or `token.json` with `action=revoke` and its `id`) | That token stops working. This works from **any** browser session you are logged in to. |
| You click **Revoke all tokens** (or `token.json` with `action=revoke`, `id=*`) | **All** your tokens stop working, whichever browser session created them. |
| The server restarts | All tokens stop working (they are only held in memory). |

### If you closed the browser without logging out

Closing the browser discards its session cookie, so you can no longer log out
of that session, and the tokens created from it stay valid until they expire.
To end them sooner, log in again (from any browser), open **Session tokens**
from the user menu and revoke them. The list shows every token you hold,
including those created from other browser sessions, which are marked as
such.

## Using a token

With `curl`:

```bash
TOKEN=pmt_...   # from the Session tokens page

# Who am I, and when does the token expire?
curl -s -H "Authorization: Bearer $TOKEN" https://lists.example.org/api/preferences.json

# Last month's emails of a (possibly private) list
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://lists.example.org/api/stats.json?list=dev&domain=project.example.org&d=lte%3D1M&emailsOnly"

# Revoke the token when you are done
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action": "revoke"}' https://lists.example.org/api/token.json
```

If the token has expired or has been revoked, the request is handled as an
anonymous one: it still succeeds, but private lists return no results.
`preferences.json` returning no `login.credentials` tells you the token is no
longer accepted.

### Sample script

[`tools/token-client.py`](../tools/token-client.py) is a complete client that
uses only the Python standard library. It gets a token through browser
approval, lists a list's emails from the last month, and revokes the token
when it is done:

```bash
python3 tools/token-client.py https://lists.example.org dev@project.example.org

# Or paste a token created from the Session tokens page:
python3 tools/token-client.py --manual https://lists.example.org dev@project.example.org
```

Its `token_from_browser` function shows the browser hand-off from the
client side: listen on `127.0.0.1` on a free port, open `token.html`, accept
one form POST and check that `state` matches.

## Security notes

- Treat a token like a password. Anyone holding it can read what you can
  read until it expires or is revoked.
- Tokens are stored on the server only as SHA-256 hashes. A token is shown to
  you once, when it is created.
- Tokens can only be handed off automatically to a program on your own
  computer (a `127.0.0.1` or `[::1]` address with a port). The approval page
  refuses any other address, and so does the server.
