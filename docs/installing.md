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

# Installing PonyMail Foal

A step-by-step guide to getting PonyMail Foal running from scratch.
This guide uses **OpenSearch** (the Apache 2.0-licensed fork of
OpenSearch). OpenSearch 2.x works identically — just substitute
the package names.

---

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| OS | Linux (tested: Alma/RHEL 9, Debian 12, Ubuntu 22.04+) | macOS works for dev |
| Python | 3.8+ | 3.11+ recommended |
| OpenSearch | 2.x (or ElasticSearch 7.x) | API-compatible; Foal uses the `elasticsearch` Python client |
| Web server | Apache httpd or nginx | Reverse proxy for the API + static file serving |
| SMTP | Any MTA (Postfix, sendmail) | Only needed if you want web-based replies |

---

## Step 1: Install OpenSearch

### RHEL / Alma Linux 9

```bash
# Import GPG key and add repo
curl -SL https://artifacts.opensearch.org/publickeys/opensearch.pgp | \
  gpg --dearmor -o /usr/share/keyrings/opensearch-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring.gpg] \
  https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/yum" \
  > /etc/yum.repos.d/opensearch.repo

# Or use the RPM directly:
curl -SL https://artifacts.opensearch.org/releases/bundle/opensearch/2.17.0/opensearch-2.17.0-linux-x64.rpm \
  -o opensearch.rpm
rpm -ivh opensearch.rpm
```

### Debian / Ubuntu

```bash
curl -SL https://artifacts.opensearch.org/publickeys/opensearch.pgp | \
  gpg --dearmor -o /usr/share/keyrings/opensearch-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring.gpg] \
  https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/apt stable main" \
  | tee /etc/apt/sources.list.d/opensearch.list

apt update && apt install opensearch
```

### Configure and start

For a single-node development install, disable security (TLS/auth)
to simplify setup:

```bash
# /etc/opensearch/opensearch.yml
cat >> /etc/opensearch/opensearch.yml << 'EOF'
discovery.type: single-node
plugins.security.disabled: true
EOF

systemctl enable --now opensearch
```

Verify it's running:

```bash
curl http://localhost:9200/
# Should return a JSON blob with version info
```

---

## Step 2: Clone PonyMail Foal

```bash
git clone https://github.com/apache/ponymail-foal.git /opt/ponymail
cd /opt/ponymail
```

---

## Step 3: Install Python Dependencies

```bash
cd /opt/ponymail/tools
pip install -r requirements.txt

cd /opt/ponymail/server
pip install -r requirements.txt
```

> **Note on OpenSearch client version**: The `requirements.txt` pins
> `elasticsearch[async]>=7.13.1,<7.14.0` because 7.14+ introduces
> strict server version checking. This version works with both
> OpenSearch 2.x (the `elasticsearch` Python client is compatible
> with both without code changes).

---

## Step 4: Run Setup

The setup script creates the database indices and generates your
configuration files.

```bash
cd /opt/ponymail/tools
python3 setup.py
```

It will ask you:
- **OpenSearch/OpenSearch URL**: `http://localhost:9200/` (default)
- **Index prefix**: `ponymail` (default)
- **Outgoing mail server**: your SMTP host (or `localhost` if local)
- **Accepted domains**: domains you'll allow web replies to (or `*`)
- **Word cloud**: Y/N
- **ID generator**: choose `dkim` (recommended)
- **Shards/replicas**: 1 shard, 0 replicas for single-node dev

This creates:
- `tools/archiver.yaml` — archiver configuration
- `server/ponymail.yaml` — server configuration

For automated/non-interactive setup:

```bash
python3 setup.py --devel   # Single-node dev defaults (1 shard, 0 replicas)
python3 setup.py --defaults  # Production defaults (3 shards, 1 replica)
```

---

## Step 5: Import Some Mail

You need mbox files to populate the archive. You can download from an
existing PonyMail instance:

```bash
cd /opt/ponymail/tools

# Download a month of a public list
curl -o dev_community.mbox \
  "https://lists.apache.org/api/mbox.lua?list=dev&domain=community.apache.org&date=2025-01"

# Import it
python3 import-mbox.py --source dev_community.mbox
```

Or import a local mbox file:

```bash
python3 import-mbox.py --source /var/mail/lists/dev.mbox --lid dev@yourproject.org
```

---

## Step 6: Start the API Server

```bash
cd /opt/ponymail/server
python3 main.py
```

The server listens on `127.0.0.1:8080` by default. Edit
`server/ponymail.yaml` to change the bind address or port (see
[configuration reference](configuration.md)).

For production, create a systemd unit:

```ini
# /etc/systemd/system/ponymail.service
[Unit]
Description=Apache Pony Mail Foal API Server
After=network.target opensearch.service

[Service]
Type=simple
User=ponymail
WorkingDirectory=/opt/ponymail/server
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now ponymail
```

---

## Step 7: Configure the Web Server

The web UI is static HTML/JS in `webui/`. The API server runs
separately and needs to be proxied.

### Apache httpd

```apache
<VirtualHost *:80>
    ServerName lists.example.org
    DocumentRoot /opt/ponymail/webui

    # Proxy API requests to the Python backend
    ProxyPass /api/ http://127.0.0.1:8080/api/
    ProxyPassReverse /api/ http://127.0.0.1:8080/api/

    # Required for thread URLs containing encoded slashes
    AllowEncodedSlashes On
    # Required for /thread/message-id path info
    AcceptPathInfo On

    <Directory /opt/ponymail/webui>
        Require all granted
        Options +MultiViews
    </Directory>
</VirtualHost>
```

---

## Step 8: Set Up Archiving (Live Email)

To archive incoming mail in real time, pipe it to the archiver from
your MTA.

### Postfix

Edit `/etc/aliases`:

```
mylist: "| /opt/ponymail/tools/archiver.py"
```

Run `newaliases` after editing.

The archiver reads `List-ID` headers to determine which list the
email belongs to. You can override with `--lid`:

```
mylist: "| /opt/ponymail/tools/archiver.py --lid mylist@example.org"
```

For private lists:

```
private-list: "| /opt/ponymail/tools/archiver.py --private"
```

---

## Step 9: Verify

Browse to `http://lists.example.org/` — you should see the list
overview with any lists you've imported.

---

## Optional: OAuth Authentication

OAuth is needed for:
- Viewing private lists
- Composing replies via the web UI
- Admin management console

See the [configuration reference](configuration.md#oauth) for
provider setup (Google, GitHub, or generic OAuth).

Quick checklist:
1. Register an OAuth app with your provider
2. Set `client_id` (and `client_secret` for GitHub) in `server/ponymail.yaml`
3. Add your provider's domain to `authoritative_domains`
4. Add admin email addresses to `admins` if you want management console access

---

## Troubleshooting

### "Connection refused" on port 9200

OpenSearch isn't running. Check:
```bash
systemctl status opensearch
journalctl -u opensearch --no-pager -n 50
```

Common cause: insufficient heap memory. Edit
`/etc/opensearch/jvm.options` and set `-Xms512m -Xmx512m` (minimum).

### Import hangs or is very slow

Check that OpenSearch is healthy:
```bash
curl http://localhost:9200/_cluster/health
```

If status is `red`, you may have unassigned shards from a previous
failed setup. Delete and re-run setup:
```bash
curl -X DELETE http://localhost:9200/ponymail-*
cd /opt/ponymail/tools && python3 setup.py --devel
```

### API returns "API Endpoint not found!"

The request path is wrong. Foal expects `/api/{endpoint}.json` (POST)
or `/api/{endpoint}.lua` (GET). Check your proxy config is passing
the full path through.

### Web UI shows but no lists appear

The background indexer hasn't run yet. Wait 2–3 minutes (controlled
by `tasks.refresh_rate` in ponymail.yaml), or restart the server.

---

## Next Steps

- [Configuration Reference](configuration.md) — all `ponymail.yaml` options
- [User Guide](user_guide.md) — how to use the web interface
- [Admin Guide](admin_guide.md) — management console and GDPR operations
- [API Documentation](API.md) — HTTP API reference
