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

# Configuration Reference

The Pony Mail Foal server is configured via a YAML file (default:
`server/ponymail.yaml`). A sample file is provided at
`server/ponymail.yaml.example`.

This document describes all available configuration keys, their types,
defaults, and behavior. Keys are grouped by section.

---

## `server`

Controls the HTTP API server binding.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `port` | integer | `8080` | TCP port the API server listens on |
| `bind` | string | `0.0.0.0` | IP address to bind to. Use `127.0.0.1` to restrict to localhost, or `0.0.0.0` for all interfaces |

Example:
```yaml
server:
  port: 8080
  bind: 127.0.0.1
```

---

## `database`

OpenSearch connection settings. You can connect either by full URL
(`dburl`) or by individual host/port/prefix components.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dburl` | string | `""` | Full OpenSearch URL (e.g. `http://localhost:9200/`). When set, takes precedence over `server`/`port`/`secure` |
| `server` | string | `localhost` | OpenSearch hostname (used when `dburl` is not set) |
| `port` | integer | `9200` | OpenSearch port (used when `dburl` is not set) |
| `secure` | boolean | `false` | Use SSL/TLS for the OpenSearch connection (used when `dburl` is not set) |
| `url_prefix` | string | `""` | URL path prefix for OpenSearch (used when `dburl` is not set, e.g. for reverse-proxied OpenSearch) |
| `db_prefix` | string | `ponymail` | Index name prefix. Indices will be named `{db_prefix}-mbox`, `{db_prefix}-source`, etc. |
| `max_hits` | integer | `5000` | Maximum number of emails returned in a single search query |
| `pool_size` | integer | `15` | Number of async OpenSearch connections in the pool. Must be ≥ 1 |
| `max_lists` | integer | `8192` | Maximum number of mailing lists to track |

Example:
```yaml
database:
  dburl: http://localhost:9200/
  db_prefix: ponymail
  max_hits: 15000
  pool_size: 15
  max_lists: 8192
```

---

## `tasks`

Background task scheduling.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `refresh_rate` | integer | `150` | Interval in seconds between background index refreshes (list counts, activity stats) |

Example:
```yaml
tasks:
  refresh_rate: 150
```

---

## `ui`

Controls UI behavior, email composition, and administration features.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `wordcloud` | boolean | `false` | Enable word cloud generation in search results |
| `mailhost` | string | `""` (disabled) | SMTP host for sending replies via the web UI. Format: `hostname` or `hostname:port` (default port 25). Leave empty to disable web replies |
| `sender_domains` | string | `""` (disabled) | Space-separated list of allowed recipient domains for web replies. Use `*` to allow all. Supports glob patterns (e.g. `*.apache.org`) |
| `traceback` | boolean | `true` | When `true`, API errors show full Python tracebacks to the client. Set to `false` in production to log tracebacks to stderr instead (an error ID is shown to the client for correlation) |
| `mgmtconsole` | boolean | `false` | Enable the administrative management console (hide/unhide/delete/edit emails via the web UI). Requires admin OAuth credentials |
| `allow_delete` | boolean | `false` | When `true`, deleted emails are fully expunged from OpenSearch (GDPR compliance). When `false`, deleted emails are merely hidden and can be recovered |
| `focus_domain` | string | `*` | Restrict the list overview to a specific domain. Use `*` for all domains. Supports glob patterns (e.g. `*.apache.org`). Useful for single-project deployments |

Example:
```yaml
ui:
  wordcloud: true
  mailhost: smtp.example.org:25
  sender_domains: "example.org *.example.org"
  traceback: false
  mgmtconsole: true
  allow_delete: true
  focus_domain: "*.apache.org"
```

---

## `oauth`

OAuth authentication configuration. Controls which OAuth providers are
available, which are authoritative (grant access to private lists), and
who has admin privileges.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `authoritative_domains` | list | `[]` | OAuth provider domains that grant access to private lists and compose features. Must be defined as a YAML array |
| `admins` | list | `[]` | Email addresses (as seen via OAuth) that have administrative privileges (management console access). Must be defined as a YAML array |
| `google_client_id` | string | `""` | Google OAuth2 client ID (from Google Developers Console) |
| `github_client_id` | string | `""` | GitHub OAuth app client ID |
| `github_client_secret` | string | `""` | GitHub OAuth app client secret |
| `providers` | dict | `{}` | OAuth provider definitions (see below) |

### OAuth Provider Definition

Each key under `providers` defines an OAuth provider. The key name is
used as the provider identifier (e.g. `apache`, `google`, `github`).

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Display name shown on the login screen |
| `oauth_portal` | string | URL of the OAuth authorization page |
| `.oauth_url` | string | Token exchange URL (note the leading dot — keys starting with `.` are hidden from the frontend) |
| `client_id` | string | OAuth client ID (for providers that need it in the URL) |
| `scope` | string | OAuth scope to request |
| `construct` | boolean | When `true`, all provider keys are URL-encoded into the authorization request |
| `fullname_key` | string | JSON key in the OAuth response containing the user's full name |
| `email_key` | string | JSON key in the OAuth response containing the user's email |

Example:
```yaml
oauth:
  authoritative_domains:
    - googleapis.com
    - github.com
  admins:
    - admin@example.org
  google_client_id: "123456.apps.googleusercontent.com"
  github_client_id: "abc123"
  github_client_secret: "secret456"
  providers:
    google:
      name: Google OAuth
      oauth_portal: https://accounts.google.com/o/oauth2/auth
      fullname_key: name
      email_key: email
      client_id: "123456.apps.googleusercontent.com"
    github:
      name: GitHub OAuth
      oauth_portal: https://github.com/login/oauth/authorize
      client_id: "abc123"
      scope: "user:email"
      construct: true
```

---

## `tokens`

Token authentication: gives scripts and bots read-only API access using
Ed25519 key pairs. It is enabled by configuring `keys`. The client keeps the
private key; the server only holds the public key and the credentials the
key logs in as. Every request is signed, see
[API Client Guide](api_client_guide.md#api-tokens). Generate a key pair with
`tools/api-token.py generate <key id>`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_skew` | int | `60` | Seconds a signed request remains valid. Clocks of client and server must agree within this margin |
| `replay_check` | string | `memory` | Where used nonces are remembered, so each request is accepted only once. `memory`: per server process, enough for a single instance. `database`: in the session index, shared by all instances behind one proxy (one small write per token request; expired entries are removed hourly) |
| `keys` | dict | `{}` | Token keys, by key id (see below) |

Each entry in `keys`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `public_key` | string | | Ed25519 public key, base64 of the raw 32 bytes or PEM |
| `uid` | string | key id | User id the key logs in as |
| `name` | string | `uid` | Full name the key logs in as |
| `email` | string | `""` | Email address the key logs in as |
| `authoritative` | bool | `false` | As for an OAuth provider: whether access control may trust this login. With the default access control (`plugins/aaa.py`), an authoritative login can read all private lists |
| `expires` | date | | From this moment the key is refused (`401`). A date (`2027-01-01`) means the start of that day, UTC; a date and time (`2027-01-01T12:00:00+02:00`) is taken as UTC if it has no timezone. Without it, the key never expires |

```yaml
tokens:
  keys:
    reader-bot:
      public_key: "in+3wOW6DMtNOXhBKYZ0k4vBm1cJWbQkej7nFe75W6I="
      uid: "reader"
      authoritative: true
      expires: 2027-01-01
```

Tokens only authenticate. What a token may read is decided by the access
control module, from the credentials above, in the same way as for an OAuth
login. If access control looks up the rights of a `uid` when it is asked,
a change in those rights applies to the tokens of that `uid` straight away.

Token requests are limited to read-only endpoints (`stats`, `email`,
`thread`, `source`, `mbox`, `preferences`, `pminfo`, `gravatar`); any other
endpoint, or a bad signature, gets a `401`. A token never has admin rights.
Requests without a token signature are unaffected. Expiry is checked on
every request, so it takes effect without a restart. To revoke a key early,
remove it and restart the server.

---

## `archiver`

Controls threading behavior when archiving new emails. These settings
affect `tools/archiver.py` and are read from `ponymail.yaml`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `threadinfo` | boolean | `false` | Enable storage of threading metadata (`top`, `thread`, `previous` properties) in OpenSearch |
| `threadparents` | integer | `10` | Maximum number of existing messages to query for thread information when a new message arrives |
| `threadtimeout` | integer | `5` | Timeout in seconds for each thread-parent query to OpenSearch |

Example:
```yaml
archiver:
  threadinfo: yes
  threadparents: 10
  threadtimeout: 5
```

---

## Notes

- The YAML file is loaded once at server startup. Changes require a
  server restart.
- Keys starting with `.` (dot) in OAuth provider definitions are
  filtered out before being sent to the frontend — use these for
  server-side-only secrets like token exchange URLs.
- The `ponymail.yaml.example` file does not contain all possible keys.
  This reference documents every option recognized by the server code
  (as of `server/plugins/configuration.py`).
