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

# Apache Pony Mail (Foal) — API Documentation

This document describes the HTTP API for Pony Mail Foal. All endpoints
accept JSON request bodies (POST) and return JSON unless otherwise noted.

The formal OpenAPI 3.0 specification is available at
[`server/openapi.yaml`](../server/openapi.yaml).

---

## Table of Contents

- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [stats.json — Search/list emails](#statsjson)
  - [email.json — Fetch a single email](#emailjson)
  - [thread.json — Fetch an email thread](#threadjson)
  - [source.json — Fetch raw email source](#sourcejson)
  - [mbox.json — Download mbox archive](#mboxjson)
  - [compose.json — Send an email](#composejson)
  - [preferences.json — User preferences and list overview](#preferencesjson)
  - [mgmt.json — Administrative operations](#mgmtjson)
  - [token.json — Short-term session tokens](#tokenjson)
  - [pminfo.json — Server activity info](#pminfojson)
  - [gravatar.json — Avatar image proxy](#gravatarjson)
  - [plain.json — Plain HTML for search engines](#plainjson)
- [Common Parameters](#common-parameters)
  - [Date/Timespan Parameters](#datetimespan-parameters)
  - [Search Query Syntax](#search-query-syntax)
- [Differences from Legacy PonyMail API](#differences-from-legacy-ponymail-api)

---

## Authentication

Foal uses cookie-based sessions via OAuth. The session cookie is named
`ponymail`. Most read endpoints work without authentication for public
lists. Private list access and write operations (compose, management)
require an authenticated session via an authoritative OAuth provider.

When `tokens.enabled` is set in `ponymail.yaml`, a logged-in user can also
mint a short-term **session token** for an external client (see
[token.json](#tokenjson)). Clients send it as:

```
Authorization: Bearer pmt_...
```

A request with a `Bearer` token is authenticated by the token alone; any
cookie sent with it is ignored. Tokens carry the read access of the session
that created them and die with it. They cannot be used for `compose.json`,
`mgmt.json` or to create further tokens.

---

## Endpoints

### stats.json

**Search the archives and return matching results.**

```
POST /api/stats.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `list` | string | **yes** | List name prefix (e.g. `dev`). Use `*` for wildcard. |
| `domain` | string | **yes** | List domain (e.g. `httpd.apache.org`). Use `*` for wildcard. |
| `d` | string | no | Date/timespan (see [below](#datetimespan-parameters)) |
| `s` | string | no | Start month (`yyyy-mm`) |
| `e` | string | no | End month (`yyyy-mm`) |
| `dfrom` | string | no | Start date as days ago |
| `dto` | string | no | Number of days to include from `dfrom` |
| `q` | string | no | Free-text search query (see [syntax](#search-query-syntax)) |
| `header_from` | string | no | Filter by `From:` header |
| `header_to` | string | no | Filter by `To:` header |
| `header_subject` | string | no | Filter by `Subject:` header |
| `header_body` | string | no | Filter by message body |
| `header_messageid` | string | no | Filter by `Message-ID:` header |
| `quick` | (presence) | no | Return statistics only (omit emails, thread_struct, word cloud, participants) |
| `emailsOnly` | (presence) | no | Return email summaries only (omit thread_struct, participants, word cloud) |
| `since` | integer | no | UNIX epoch; returns `{"changed": false}` if no emails are newer |

#### Response (StatsResponse)

```json
{
  "hits": 134,
  "numparts": 28,
  "no_threads": 35,
  "firstYear": 2018,
  "firstMonth": 1,
  "lastYear": 2021,
  "lastMonth": 11,
  "name": "dev",
  "domain": "lists.example.org",
  "list": "dev@lists.example.org",
  "searchlist": "<dev.lists.example.org>",
  "active_months": [{"2021-01": 15}, {"2021-02": 23}],
  "emails": [ /* array of CompactEmailResponse */ ],
  "thread_struct": [ /* threaded representation */ ],
  "participants": [
    {"email": "jane@example.org", "name": "Jane Doe", "count": 10, "gravatar": "..."}
  ],
  "cloud": {"word1": 25, "word2": 10},
  "searchParams": {"list": "dev", "domain": "lists.example.org", "d": "gte=2018-01"},
  "unixtime": 1506761839
}
```

#### Example

```bash
curl -X POST https://lists.apache.org/api/stats.json \
  -H "Content-Type: application/json" \
  -d '{"list": "dev", "domain": "ponymail.apache.org", "d": "lte=3M"}'
```

---

### email.json

**Fetch a single email by permalink ID or Message-ID.**

```
POST /api/email.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **yes** | Email permalink ID or Message-ID header value |
| `listid` | string | conditional | Required when looking up by Message-ID (for disambiguation) |
| `attachment` | boolean | no | Set to `true` to fetch an attachment |
| `file` | string | no | Attachment hash (required when `attachment=true`) |

#### Response (SingleEmailResponse)

```json
{
  "id": "r8cmj7vm5n8z5r3xda5ebd",
  "mid": "r8cmj7vm5n8z5r3xda5ebd",
  "dbid": "08c4e61930db221d...",
  "message-id": "<521062724.28.1506761839312.JavaMail.jenkins@host>",
  "from": "Jane Doe <jane@example.org>",
  "from_raw": "Jane Doe <jane@example.org>",
  "to": "dev@example.org",
  "cc": "announce@example.org",
  "subject": "Re: weekly meeting",
  "date": "2017/09/30 08:57:19",
  "epoch": 1506761839,
  "list": "<dev.example.org>",
  "list_raw": "<dev.example.org>",
  "body": "Full message body...",
  "body_short": "Truncated to 201 chars...",
  "private": false,
  "references": "<parent-message-id>",
  "in-reply-to": "<parent-message-id>",
  "attachments": [],
  "permalinks": ["r8cmj7vm5n8z5r3xda5ebd", "..."],
  "gravatar": "69eea47c5083c2e4945a2704fc7b658c"
}
```

**Notes:**
- `date` and `epoch` are in UTC.
- When `attachment=true` and a matching `file` hash is found, the raw
  attachment binary is returned with appropriate Content-Type and
  Content-Disposition headers.

---

### thread.json

**Fetch a complete email thread starting from a given email.**

```
POST /api/thread.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **yes** | Email permalink ID or Message-ID |
| `listid` | string | no | List-ID for disambiguation when using Message-ID |
| `find_parent` | boolean | no | If `true`, navigate up to the thread root before fetching |

#### Response (ThreadResponse)

```json
{
  "thread": {
    "from": "...",
    "subject": "...",
    "id": "...",
    "epoch": 1506761839,
    "children": [ /* nested CompactEmailResponse objects */ ]
  },
  "emails": [ /* flat array of all emails in the thread */ ]
}
```

---

### source.json

**Fetch the raw mbox source of an email.**

```
POST /api/source.json
```

#### Request Parameters

Same as [email.json](#emailjson) (`id`, optional `listid`).

#### Response

Returns the raw RFC 2822 email source as `text/plain`. This includes all
original headers and the unmodified message body.

Returns HTTP 404 if the email is not found.

---

### mbox.json

**Download a set of emails in mbox format.**

```
POST /api/mbox.json
```

#### Request Parameters

Same as [stats.json](#statsjson) — all search/date parameters apply.

#### Response

Returns the matching emails as a single mbox-format file (`text/plain`).

---

### compose.json

**Compose and send an email to a list.** Requires authentication via
an authoritative OAuth provider.

```
POST /api/compose.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to` | string | **yes** | Recipient address (must match `sender_domains` config) |
| `subject` | string | **yes** | Email subject |
| `body` | string | **yes** | Email message body |
| `references` | string | no | Message-ID reference (if not a direct reply) |
| `in-reply-to` | string | no | Message-ID of the email being directly replied to |

#### Response (ActionResponse)

```json
{"okay": true, "message": "Email dispatched"}
```

**Note:** The `sender_domains` configuration controls which recipient
domains are permitted. See [INSTALL.md](../INSTALL.md#setting-up-web-replies).

---

### preferences.json

**Fetch user preferences, list overview, and OAuth provider configuration.**

```
POST /api/preferences.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `oauth` | boolean | no | If `true`, return only OAuth provider configuration |

#### Response

```json
{
  "login": {
    "credentials": {"fullname": "Jane Doe", "email": "jane@example.org"}
  },
  "lists": {
    "httpd.apache.org": {"dev": 1523, "users": 890},
    "ponymail.apache.org": {"dev": 36}
  },
  "versions": {
    "foal": "abc123",
    "server": "def456",
    "elasticsearch_engine": "8.11.0",
    "elasticsearch_library": "8.11.0"
  }
}
```

**Notes:**
- `versions.server`, `elasticsearch_engine`, and `elasticsearch_library`
  are only returned for authenticated users (admin-only for OpenSearch versions).
- When `oauth=true`, returns the configured OAuth providers for the login UI.

---

### token.json

**Create, list and revoke short-term session tokens.** Only available when
`tokens.enabled` is set in `ponymail.yaml`.

```
POST /api/token.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | no | `create` (default), `info`, `list` or `revoke` |
| `client` | string | no | Name of the client the token is for; shown to the user (`create`). Default: `unknown client` |
| `ttl` | integer | no | Requested lifetime in seconds (`create`). Default: `tokens.ttl` (3600 unless configured); clamped to between 60 and `tokens.max_ttl` (86400 unless configured) |
| `redirect_uri` | string | no | Loopback URL the web UI hands the token to (`create`, see below); omit for manual copy |
| `id` | string | for `revoke` from a browser session | Token id to revoke, or `*` for every token of the browser session (`revoke`, browser session only) |

`info` needs no login and returns `{"okay": true, "enabled": true, "ttl": 3600, "max_ttl": 86400}`.
`create` and `list` need a logged-in **browser session** (not a token) and a
POST; requests with a foreign `Origin` header are refused. `revoke` sent with
a `Bearer` token revokes that token.

#### Response (`create`)

```json
{
  "okay": true,
  "token": "pmt_3q2...",
  "id": "a1b2c3d4e5f6",
  "client": "ponymail-mcp",
  "created": 1790000000,
  "expires": 1790003600,
  "ttl": 3600
}
```

The raw token is returned once and never again. Errors are returned as
`{"okay": false, "error": "<code>", "message": "..."}` with codes
`tokens_disabled`, `login_required`, `token_not_allowed`, `cross_origin`,
`method_not_allowed`, `invalid_redirect_uri`, `invalid_ttl` and `missing_id`.

#### Browser hand-off (`webui/token.html`)

A local client that cannot see the browser's cookie obtains a token with
the user's explicit approval, in the style of RFC 8252 loopback redirects:

1. The client listens on a loopback port and opens
   `https://<host>/token.html?client=<name>&redirect_uri=http://127.0.0.1:<port>/<path>&state=<random>`.
2. The page shows who is logged in, which client is asking and for how
   long, and asks the user to **Approve** or **Deny** (logging in first if
   needed).
3. On approval it calls `token.json` and hands the result to `redirect_uri`
   with a form POST of `token`, `state` and `expires`. On denial it posts
   `error=access_denied` and `state`.
4. The client checks that `state` matches the value it generated.

`redirect_uri` must be `http(s)` on `127.0.0.1` or `[::1]` (not
`localhost`, per RFC 8252 section 8.3), with an explicit port and no
credentials or fragment, and must be at most 512 characters; the server
enforces this. Without a `redirect_uri` the page shows the token for the user
to copy.

A token-authenticated `preferences.json` response includes
`login.token` (`id`, `client`, `created`, `expires`), and `logout=true` sent
with a token revokes only that token.

---

### mgmt.json

**Administrative endpoint for email management (GDPR operations).**
Requires admin authentication.

```
POST /api/mgmt.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | **yes** | One of: `log`, `delete`, `hide`, `unhide`, `edit` |
| `document` | string | no | Single document permalink ID |
| `documents` | array | no | Array of document permalink IDs (batch operations) |
| `size` | integer | no | Number of audit log entries (for `action=log`, default: 50) |
| `page` | integer | no | Page offset for audit log |
| `filter` | string | no | Filter audit log by action type |

**Actions:**

- `log` — View the audit log of past admin actions
- `delete` — Permanently delete emails (if `allow_delete` is configured) or hide them
- `hide` — Hide emails from public view (recoverable)
- `unhide` — Restore previously hidden emails
- `edit` — Edit email metadata (list-id, etc.)

#### Response

Varies by action. For `log`:

```json
{"entries": [ /* audit log entries */ ]}
```

For mutations: returns an `ActionResponse` with `okay` and `message`.

---

### pminfo.json

**Return server activity statistics.** No authentication required.

```
POST /api/pminfo.json
```

Returns the server's gathered activity data (list counts, processing stats).

---

### gravatar.json

**Caching proxy for Gravatar images.**

```
POST /api/gravatar.json
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `md5` | string | **yes** | MD5 hash of the email address (lowercased) |

Returns a `image/png` response with 24-hour cache headers. Falls back to
a default avatar if the hash is unknown.

---

### plain.json

**Plain HTML rendering for search engine indexing.**

This endpoint serves publicly available lists and threads as simple HTML
with canonical link elements, enabling search engines to index the archive
content and link to the standard JS-based UI URLs.

---

## Common Parameters

### Date/Timespan Parameters

The `d` parameter supports several formats:

| Format | Meaning | Example |
|--------|---------|---------|
| `yyyy-mm` | Specific month | `2021-06` |
| `lte=N[wMyd]` | Less than N weeks/Months/years/days ago | `lte=3M` |
| `gte=N[wMyd]` | More than N weeks/Months/years/days ago | `gte=1y` |
| `dfr=yyyy-mm-dd\|dto=yyyy-mm-dd` | Date range (inclusive) | `dfr=2021-09-01\|dto=2021-09-30` |

The `s` and `e` parameters provide an alternative way to specify a
month range: `s=2021-01&e=2021-06`.

The `dfrom`/`dto` pair specifies days: `dfrom=31` (31 days ago) with
`dto=10` (10 days of data starting from that point).

**Units:** `w` = weeks, `M` = Months, `y` = years, `d` = days.

`lte` and `gte` are mutually exclusive. `dfr` and `dto` are normally
used together.

### Search Query Syntax

The `q` parameter supports:

| Syntax | Meaning | Example |
|--------|---------|---------|
| `word` | Must contain word | `apples` |
| `+word` | Word must be present | `+oranges` |
| `-word` | Word must NOT be present | `-bananas` |
| `"phrase"` | Exact phrase match | `"weekly meeting"` |

Additional filters can narrow results:

- `header_from` — match sender address
- `header_to` — match recipient address
- `header_subject` — match subject line
- `header_body` — match message body only
- `header_messageid` — match Message-ID header

---

## Differences from Legacy PonyMail API

Foal's API is largely compatible with the original Lua-based PonyMail,
with the following notable differences:

| Change | Details |
|--------|---------|
| Endpoint suffix | Foal uses `.json` (e.g. `/api/stats.json`) instead of `.lua` |
| Method | All endpoints use POST with JSON body (legacy used GET with query params) |
| `notifications.lua` | **Not available** in Foal |
| `atom.lua` | **Not available** in Foal |
| Additional email fields | `dbid`, `permalinks`, `body_short`, `from_raw`, `list_raw` are new in Foal |
| `find_parent` | New parameter on `thread.json` to navigate to thread root |
| `versions` in preferences | New — shows Foal, server, and OpenSearch version info |
| `mgmt.json` | New — admin/GDPR management endpoint (not in legacy PM) |
| `token.json` | New — short-term session tokens for external clients |
| `gravatar.json` | New — caching proxy (legacy embedded gravatar handling differently) |
| `plain.json` | New — search engine indexing support |

---

## Related Resources

- [OpenAPI Specification](../server/openapi.yaml) — formal schema definition
- [Installation Guide](../INSTALL.md) — setup and configuration
- [Server README](../server/README.md) — running the backend
