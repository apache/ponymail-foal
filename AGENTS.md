# AGENTS.md

Guidance for AI coding agents working on this repository.

## Project Overview

Apache Pony Mail Foal is a mailing list archive system. It consists of:

- **`server/`** — Python async HTTP API (aiohttp) that queries ElasticSearch
- **`webui/`** — Static JavaScript/HTML frontend served by a reverse proxy
- **`tools/`** — Python CLI utilities for archiving, importing, and migrating email

## Repository Layout

```
server/
├── main.py                    # Entry point, request routing, endpoint discovery
├── ponymail.yaml.example      # Sample configuration
├── openapi.yaml               # OpenAPI 3.0 specification
├── server_version.py          # Auto-generated version from git
├── endpoints/                 # API endpoint handlers (one file per endpoint)
│   ├── stats.py               # Search/list emails
│   ├── email.py               # Fetch single email
│   ├── thread.py              # Fetch email thread
│   ├── source.py              # Raw RFC 2822 source
│   ├── mbox.py                # Mbox download
│   ├── compose.py             # Send email (authenticated)
│   ├── preferences.py         # User prefs + list overview
│   ├── mgmt.py                # Admin GDPR operations
│   ├── oauth.py               # OAuth login flow
│   ├── pminfo.py              # Server activity info
│   ├── gravatar.py            # Avatar caching proxy
│   └── plain.py               # SEO-friendly HTML rendering
├── plugins/                   # Shared server internals
│   ├── configuration.py       # YAML config parsing (source of truth for all config keys)
│   ├── database.py            # ElasticSearch async client pool
│   ├── messages.py            # Email query, threading, trimming logic
│   ├── session.py             # Cookie-based sessions + OAuth credential tracking
│   ├── aaa.py                 # Access control (public vs private lists)
│   ├── defuzzer.py            # Date/query parameter normalization
│   ├── background.py          # Periodic index refresh tasks
│   ├── formdata.py            # Request body parsing (form vs JSON)
│   ├── offloader.py           # Thread pool for CPU-bound JSON serialization
│   ├── auditlog.py            # Admin action logging
│   └── oauth*.py              # Provider-specific OAuth token exchange
└── testendpoints/             # Extra endpoints loaded with --testendpoints

tools/
├── archiver.py                # Pipe-based email archiver (called from /etc/aliases)
├── import-mbox.py             # Bulk mbox file importer
├── migrate.py                 # Migration from old PonyMail databases
├── setup.py                   # First-time ES index setup
├── rethread.py                # Re-compute threading for existing emails
├── bulk-edit.py               # Batch metadata edits
├── archiver.yaml              # Archiver configuration
└── plugins/                   # Shared archiver internals
    ├── elastic.py             # Synchronous ES client for tools
    ├── generators.py          # Email ID generation (DKIM-based)
    ├── dkim_id.py             # DKIM permalink generation
    ├── textlib.py             # Text normalization, list-ID handling
    └── mboxo_patch.py         # Mbox format quirks

webui/
├── index.html                 # Front page (list of lists)
├── list.html                  # List view (emails in a list)
├── thread.html                # Thread view
├── admin.html                 # Management console
├── oauth.html                 # OAuth callback handler
├── js/
│   ├── ponymail.js            # Built/concatenated JS (from source/)
│   ├── config.js              # Client-side config
│   └── source/                # Individual JS source files (concatenated by build.sh)
│       ├── build.sh           # Concatenation build script
│       ├── search.js          # Search functionality
│       ├── composer.js        # Email compose UI
│       └── ...                # ~24 source files
├── css/
└── images/

test/
├── test_archiver.py           # Unit tests for archiver
├── test_defuzzer.py           # Unit tests for date/query parsing
├── test_msgid.py              # Unit tests for message ID handling
├── itest_integration.py       # Integration tests (requires running ES + server)
└── resources/                 # Test fixtures (sample emails)

docs/
├── index.md                   # Documentation home page
├── architecture.md            # Component diagram, data model, request lifecycle
├── operator_guide.md          # Install & deploy (Docker + production)
├── user_guide.md              # Browse, search, reply
├── admin_guide.md             # Management console, GDPR, bulk ops
├── plugins.md                 # Endpoint & plugin development guide
├── API.md                     # HTTP API endpoint reference
├── api_client_guide.md        # Curl examples, integration patterns
├── search.md                  # Search query syntax
├── configuration.md           # All ponymail.yaml options
├── releases.md                # Versioning & release process
└── STYLEGUIDE.md              # Code style conventions
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Server | Python 3.8+, aiohttp, async/await |
| Database | ElasticSearch 7.x+ (async client) |
| Frontend | Vanilla JavaScript (ES2018), jQuery 1.12, Bootstrap |
| Build (JS) | Shell concatenation (`webui/js/source/build.sh`) |
| Config | YAML (`ponymail.yaml` for server, `archiver.yaml` for tools) |
| Tests | pytest (unit + integration) |
| Linting | pylint (`pylintrc`), black (line length 120), mypy (type checking) |
| CI | GitHub Actions (linting, type tests, unit tests, integration tests) |

## Code Conventions

### Python (server + tools)

- **PEP 8** with 120-char line limit
- **Format with** `black -l 120`
- **Type annotations** required on all functions; checked with `mypy`
- **Endpoint pattern**: each endpoint is a module in `server/endpoints/` with:
  - `async def process(server, session, indata) -> dict | Response`
  - `def register(server) -> plugins.server.Endpoint`
- **Config access**: via `server.config.<section>.<key>` (never raw YAML dicts)
- **ES queries**: use `session.database` (async); never construct raw HTTP calls to ES
- **Dependencies**: must be Apache 2.0 compatible (see comments in `requirements.txt`)

### JavaScript (webui)

- **ECMAScript 2018** (ES9) — no transpilation
- **Global variables** prefixed with `G_` (e.g. `G_apiURL`, `G_current_json`)
- **No module bundler** — files in `webui/js/source/` are concatenated by `build.sh` into `ponymail.js`
- **After editing source files**: commit the source changes first, then run `build.sh` and commit the built `ponymail.js` separately
- **jQuery 1.12** is available but new code should prefer vanilla DOM APIs

## How to Run Locally

```bash
# Docker (easiest)
git clone https://github.com/apache/ponymail-foal.git
cd ponymail-foal
docker compose build
docker compose up
# Browse to http://localhost:1080/
```

## How to Run Tests

```bash
# Unit tests
cd test
pip install -r requirements.txt
pytest test_archiver.py test_defuzzer.py test_msgid.py

# Integration tests (requires running ES + server)
pytest itest_integration.py
```

## API Pattern

All endpoints accept both `.lua` (GET + query params) and `.json` (POST + JSON body) suffixes. The suffix determines how the request body is parsed — both route to the same handler:

```
GET  /api/stats.lua?list=dev&domain=httpd.apache.org    → form parsing
POST /api/stats.json  {"list":"dev","domain":"httpd.apache.org"}  → JSON parsing
```

See `docs/API.md` for the full reference and `server/openapi.yaml` for the formal schema.

## Key Design Decisions

- **No external framework** for the frontend — vanilla JS concatenated into a single file
- **Async everywhere** on the server — aiohttp + async ES client, connection pool
- **Backward compatibility** with original Lua-based PonyMail API (`.lua` suffix support)
- **Privacy model**: emails can be `private: true` (hidden from unauthenticated users). OAuth providers marked `authoritative` grant access to private lists. Admin users can hide/delete emails.
- **Email IDs**: generated from DKIM signatures for collision resistance (see `tools/plugins/dkim_id.py`)
- **Threading**: stored as `in-reply-to`/`references` in ES; thread tree constructed at query time. Known limitation: threading can be inconsistent (see GitHub issues #244, #304)

## Common Pitfalls

- **ElasticSearch version sensitivity**: The ES client library from 7.14+ has strict server version checking. Pin to `<7.14.0` as in requirements.txt.
- **`ponymail.js` is generated**: Don't edit it directly. Edit files in `webui/js/source/` then run `build.sh`.
- **Server version file is generated**: Don't edit `server_version.py` directly. Commit endpoint changes first, then run `server/update_version.sh`.
- **Config key names don't always match YAML keys**: e.g. YAML `mgmtconsole` → Python `config.ui.mgmt_enabled`, YAML `allow_delete` → Python `config.ui.fully_delete`. Check `plugins/configuration.py` for the mapping.
- **Two separate config systems**: The server uses `ponymail.yaml` (parsed by `plugins/configuration.py`). The tools use `archiver.yaml` (parsed by `tools/plugins/ponymailconfig.py` via ConfigParser — INI-style, not YAML).
