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

# Plugin & Endpoint Development Guide

## Adding a New API Endpoint

### 1. Create the module

Create a new Python file in `server/endpoints/`:

```python
# server/endpoints/myendpoint.py

import plugins.server
import plugins.session
import typing
import aiohttp.web


async def process(
    server: plugins.server.BaseServer,
    session: plugins.session.SessionObject,
    indata: dict,
) -> typing.Union[dict, aiohttp.web.Response]:
    """Handle the request and return a JSON-serializable dict or a Response."""
    
    name = indata.get("name", "world")
    return {"greeting": f"Hello, {name}!"}


def register(server: plugins.server.BaseServer):
    """Called once at startup. Return an Endpoint or StreamingEndpoint."""
    return plugins.server.Endpoint(process)
```

### 2. That's it

The server auto-discovers endpoints on startup by scanning the
`server/endpoints/` directory. Any `.py` file with a `register()`
function is loaded and mapped to `/api/{filename}`.

Your endpoint is now available at:
- `POST /api/myendpoint.json` (JSON body)
- `GET /api/myendpoint.lua?name=Rich` (query params)

### Key Conventions

| Concern | Pattern |
|---------|---------|
| Return JSON | Return a `dict` — the server serializes it automatically |
| Return custom response | Return an `aiohttp.web.Response` (e.g. for binary data, redirects) |
| Access config | `server.config.ui.mailhost`, `server.config.database.max_hits`, etc. |
| Query OpenSearch | Use `session.database` (an async OpenSearch client from the pool) |
| Check auth | `session.credentials` is `None` (anonymous) or has `.authoritative`, `.admin`, `.email` |
| Error response | Return `aiohttp.web.Response(status=400, text="message")` |

### Streaming Endpoints

For large responses (like mbox downloads), use `StreamingEndpoint`:

```python
async def process(server, request, session, indata):
    response = aiohttp.web.StreamResponse()
    await response.prepare(request)
    # Write chunks...
    await response.write(b"data chunk")
    return response

def register(server):
    return plugins.server.StreamingEndpoint(process)
```

Note: streaming endpoints receive the raw `request` object instead of
parsed `indata`.

---

## Server Plugins (`server/plugins/`)

These are shared internal modules used by endpoints. They are **not**
user-installable — to extend behavior, add endpoints instead.

### Commonly Used

| Module | What you use it for |
|--------|-------------------|
| `plugins.messages` | `get_email()`, `fetch_children()`, `find_parent()`, `query()` |
| `server.aaa` | `can_access_list()`, `can_access_email()` — checks private list permissions, using the class set by `aaa.plugin` (`plugins.aaa` by default) |
| `plugins.session` | `SessionObject` with `.credentials`, `.database` |
| `plugins.defuzzer` | `defuzz(indata)` — normalizes date/search parameters into OpenSearch queries |
| `plugins.server` | `BaseServer`, `Endpoint`, `StreamingEndpoint` base classes |

### Adding to an Existing Plugin

If you need shared logic used by multiple endpoints, add it to the
appropriate plugin module. Follow the existing patterns:

- Type annotations on all functions
- Async where OpenSearch queries are involved
- Use `session.database` for queries (never create your own OpenSearch client)

---

## Tools Plugins (`tools/plugins/`)

These support the CLI tools (archiver, importer, migrator):

| Module | Purpose |
|--------|---------|
| `elastic.py` | Synchronous OpenSearch client wrapper (tools don't use async) |
| `generators.py` | ID generation strategies for emails |
| `dkim_id.py` | DKIM-based permalink generation |
| `textlib.py` | Text normalization, List-ID parsing, character encoding |
| `mboxo_patch.py` | Workaround for `mboxo` format quirks (unescaped "From " lines) |
| `ponymailconfig.py` | Reads `archiver.yaml` (INI-style config, separate from server's YAML) |

---

## OAuth Provider Plugins

To add a new OAuth provider, create a module in `server/plugins/`:

```python
# server/plugins/oauthMyProvider.py

async def process(server, formdata):
    """Exchange auth code for user info.
    
    Returns:
        dict with 'email' and 'name' keys on success,
        or dict with 'error' key on failure.
    """
    code = formdata.get("code")
    # Exchange code for token, fetch user info...
    return {"email": "user@example.org", "name": "Jane Doe"}
```

Then register it in `server/endpoints/oauth.py`'s dispatch logic and
add a provider entry in `ponymail.yaml`:

```yaml
oauth:
  providers:
    myprovider:
      name: My OAuth
      oauth_portal: https://auth.example.org/authorize
      client_id: your-client-id
```

---

## Access Control Plugins

Who may read private lists is decided by an access control plugin: a
subclass of `plugins.aaa_plugin.AAAPlugin`. It can live anywhere Python can
import it from, so a site can keep its own outside the Pony Mail tree:

```python
# mysite/aaa.py

import typing

import plugins.aaa_plugin
import plugins.session


READERS = {"jdoe", "asmith"}  # e.g. looked up in a directory instead


class SiteAAA(plugins.aaa_plugin.AAAPlugin):
    def can_access_list(self, session: plugins.session.SessionObject, listid: typing.Optional[str]) -> bool:
        """listid is 'list@domain' or '<list.domain>' (list_raw)"""
        creds = session.credentials
        return bool(creds and creds.authoritative and creds.uid in READERS)
```

Select it in `ponymail.yaml`:

```yaml
aaa:
  plugin: mysite.aaa.SiteAAA
```

- `can_access_list(session, listid)` is required. `can_access_email(session, email)`
  defaults to: public emails for everyone, private ones if `can_access_list`
  allows their list. Override it to decide per email.
- One instance is created at startup, as `server.aaa`; `self.server` gives
  access to the configuration.
- The server refuses to start if the class can't be imported, isn't an
  `AAAPlugin`, or doesn't implement `can_access_list`.
- Without `aaa.plugin`, the server uses the functions `can_access_list` and
  `can_access_email` in `plugins/aaa.py`, so a site's own version of that
  file keeps working.

---

## Testing

### Unit Tests

```bash
cd test
pip install -r requirements.txt
pytest test_archiver.py test_defuzzer.py test_msgid.py -v
```

### Integration Tests

Require a running OpenSearch instance and server with `--testendpoints`:

```bash
pytest itest_integration.py -v
```

### Linting & Type Checking

```bash
black -l 120 --check server/ tools/
mypy server/
pylint server/ tools/
```
