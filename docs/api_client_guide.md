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

# API Client Guide

Practical examples for consuming the Pony Mail Foal API programmatically.
For the full endpoint reference, see [API.md](API.md).

---

## Two Access Modes

Every endpoint supports two URL patterns:

| Suffix | Method | Body | Use when |
|--------|--------|------|----------|
| `.json` | POST | JSON | Preferred — native Foal protocol |
| `.lua` | GET | Query params | Legacy compatibility |

All examples below show both modes.

---

## Authentication

Public lists require no authentication. For private lists or write
operations, include a session cookie:

```
Cookie: ponymail=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Obtain the cookie by completing an OAuth flow via the web UI, then
extract it from your browser's DevTools (Network tab → Request Headers).

### API Tokens

For unattended, read-only access, ask the operator for a token key (see
[`tokens`](configuration.md#tokens)). Each key has an Ed25519 key pair; you
keep the private key. A signed request is logged in as the user the operator
configured for the key, and can read the private lists that user can. Every
request carries a signature:

```
Authorization: PonyMail-Ed25519 key=<key id>,ts=<unix time>,nonce=<random>,sig=<base64>
```

`sig` is the Ed25519 signature over these lines, joined with `\n`:

```
<ts>
<nonce>
<HTTP method, upper case>
<path and query string exactly as sent, e.g. /api/stats.lua?list=dev&domain=example.org>
<hex SHA-256 of the request body (of the empty string for GET)>
```

A signature is valid for 1 minute (by default) and its nonce only once, so
sign each request separately, with a fresh random nonce. `tools/api-token.py` does this for you:

```bash
# Generate a key pair (prints the ponymail.yaml snippet for the operator)
python3 tools/api-token.py generate reader-bot --uid reader

# Sign and perform a request
python3 tools/api-token.py fetch reader-bot.key reader-bot \
  'https://lists.example.org/api/stats.lua?list=private&domain=example.org'
python3 tools/api-token.py fetch reader-bot.key reader-bot \
  https://lists.example.org/api/email.json --data '{"id": "<permalink>"}'

# Or just print a header to use with curl
curl -H "$(python3 tools/api-token.py header reader-bot.key reader-bot GET \
  '/api/stats.lua?list=private&domain=example.org')" \
  'https://lists.example.org/api/stats.lua?list=private&domain=example.org'
```

A key may have an expiry date; after it, requests get `401 Token key has
expired` and you need a new key from the operator. Tokens are read-only: they can't compose emails, use the management
console or log in to the web UI.

---

## Common Operations

### List All Mailing Lists

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/preferences.json \
  -H "Content-Type: application/json" \
  -d '{}' | jq '.lists | keys'
```

**.lua (GET):**
```bash
curl -s "https://lists.apache.org/api/preferences.lua" | jq '.lists | keys'
```

Returns domain → list → message count mappings.

---

### Search a List

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/stats.json \
  -H "Content-Type: application/json" \
  -d '{
    "list": "dev",
    "domain": "httpd.apache.org",
    "d": "lte=30d",
    "q": "mod_proxy"
  }' | jq '.hits, .emails[0].subject'
```

**.lua (GET):**
```bash
curl -s "https://lists.apache.org/api/stats.lua?list=dev&domain=httpd.apache.org&d=lte%3D30d&q=mod_proxy" \
  | jq '.hits, .emails[0].subject'
```

#### Useful Parameters

| Parameter | Example | Effect |
|-----------|---------|--------|
| `d` | `2026-06` | Specific month |
| `d` | `lte=7d` | Last 7 days |
| `d` | `dfr=2026-01-01\|dto=2026-06-30` | Date range |
| `q` | `+proxy -balancer` | Required/excluded terms |
| `header_from` | `rbowen@apache.org` | Filter by sender |
| `header_subject` | `[VOTE]` | Filter by subject |
| `quick` | `1` | Stats only (faster, no emails/threads) |
| `emailsOnly` | `1` | Emails only (no thread_struct, participants, word cloud) |

---

### Fetch a Single Email

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/email.json \
  -H "Content-Type: application/json" \
  -d '{"id": "rt6hrlhc4cwz0bwzf4lys43cb7lz30h6"}' | jq '.subject, .from, .date'
```

**.lua (GET):**
```bash
curl -s "https://lists.apache.org/api/email.lua?id=rt6hrlhc4cwz0bwzf4lys43cb7lz30h6" \
  | jq '.subject, .from, .date'
```

---

### Fetch a Thread

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/thread.json \
  -H "Content-Type: application/json" \
  -d '{"id": "rt6hrlhc4cwz0bwzf4lys43cb7lz30h6"}' \
  | jq '.emails | length'
```

Use `"find_parent": true` to navigate from any reply up to the thread root.

---

### Fetch Raw Email Source

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/source.json \
  -H "Content-Type: application/json" \
  -d '{"id": "rt6hrlhc4cwz0bwzf4lys43cb7lz30h6"}'
```

Returns `text/plain` — the raw RFC 2822 message.

---

### Download Mbox Archive

**.json (POST):**
```bash
curl -s -X POST https://lists.apache.org/api/mbox.json \
  -H "Content-Type: application/json" \
  -d '{"list": "dev", "domain": "httpd.apache.org", "d": "2026-06"}' \
  -o dev-2026-06.mbox
```

**.lua (GET):**
```bash
curl -s "https://lists.apache.org/api/mbox.lua?list=dev&domain=httpd.apache.org&date=2026-06" \
  -o dev-2026-06.mbox
```

---

## Rate Limiting

There is no rate limiting on the API. However, be respectful:

- Use `quick=1` or `emailsOnly=1` when you don't need full results
- Cache responses where appropriate
- Avoid tight polling loops — use the `since` parameter for change detection

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (malformed parameters) |
| 403 | Forbidden (admin endpoint, insufficient permissions) |
| 404 | Email/thread not found, or invalid endpoint |
| 500 | Server error (check `traceback` setting) |

---

## Related

- [API.md](API.md) — Full endpoint reference with response schemas
- [search.md](search.md) — Search query syntax
- GitHub issue [#312](https://github.com/apache/ponymail-foal/issues/312) — API token support (not yet implemented)
