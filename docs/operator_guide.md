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

# Operator Guide

Two paths to get Foal running: Docker (quick, for development/testing)
or a production deployment.

---

## Quick Start (Docker)

```bash
git clone https://github.com/apache/ponymail-foal.git ponymail-foal
cd ponymail-foal
docker compose build
docker compose up
```

In a second terminal, set up the database (one-time):

```bash
docker compose exec pmfoal bash -c 'cd tools; python3 setup.py --devel'
```

Import some test data:

```bash
mkdir mbox-testdata && cd mbox-testdata
wget "https://lists.apache.org/api/mbox.lua?list=dev&domain=community.apache.org"
cd ..
docker compose exec pmfoal bash -c 'cd tools; python3 import-mbox.py --source /var/maildata/mbox-testdata/*.mbox'
```

Start the API server:

```bash
docker compose exec pmfoal bash -c 'cd server; python3 main.py --testendpoints'
```

Browse to `http://localhost:1080/`.

For Docker details (env vars, volume mounts, test auth), see [DOCKER.md](../DOCKER.md).

---

## Production Deployment

### Requirements

- Linux (or FreeBSD/macOS)
- Python 3.8+
- OpenSearch 2.x (client pinned to `<7.14` due to strict version checks)
- A reverse proxy (Apache httpd or nginx)
- PipEnv or pip for dependency management

### Install

```bash
git clone https://github.com/apache/ponymail-foal.git /opt/ponymail-foal
cd /opt/ponymail-foal/tools
pip install -r requirements.txt
python3 setup.py          # Interactive — creates OpenSearch indices + ponymail.yaml

cd /opt/ponymail-foal/server
pip install -r requirements.txt
```

### Configure

Edit `server/ponymail.yaml`. See [configuration.md](configuration.md) for
all options. At minimum:

```yaml
server:
  port: 8080
  bind: 127.0.0.1

database:
  dburl: http://localhost:9200/

ui:
  traceback: false
```

### Run as a systemd Service

Create `/etc/systemd/system/ponymail.service`:

```ini
[Unit]
Description=Apache Pony Mail Foal API Server
After=network.target opensearch.service

[Service]
Type=simple
User=ponymail
Group=ponymail
WorkingDirectory=/opt/ponymail-foal/server
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ponymail
```

### Reverse Proxy (Apache httpd)

```apache
<VirtualHost *:443>
    ServerName lists.example.org
    DocumentRoot /opt/ponymail-foal/webui/
    AcceptPathInfo On
    AllowEncodedSlashes On

    ProxyPass /api/ http://127.0.0.1:8080/api/
    ProxyPassReverse /api/ http://127.0.0.1:8080/api/

    <Directory /opt/ponymail-foal/webui/>
        Require all granted
        Options +MultiViews
    </Directory>
</VirtualHost>
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name lists.example.org;
    root /opt/ponymail-foal/webui/;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
    }
}
```

---

## Archiving New Emails

Add a pipe alias in `/etc/aliases`:

```
mylist: "| /opt/ponymail-foal/tools/archiver.py"
```

Run `newaliases`. For private lists, use `--private`. To override the
list ID: `--lid mylist@example.org`.

For full archiving options (OAuth, web replies, management console),
see [INSTALL.md](../INSTALL.md).

---

## Operations

### Health Check

The API server responds to any valid endpoint. A simple check:

```bash
curl -s http://localhost:8080/api/pminfo.json | jq .
```

This returns activity data (list counts, processing stats).

### Logs

- **API server**: stdout/stderr (captured by systemd journal)
- **Archiver**: stderr (captured by MTA's pipe logging)
- **OpenSearch queries**: Enable with `--logger INFO` or `--trace DEBUG` flags on `main.py`
- **API request log**: Enable with `--apilog INFO` flag

View server logs:

```bash
journalctl -u ponymail -f
```

### Background Tasks

The server runs a background refresh task (interval set by
`tasks.refresh_rate`, default 150 seconds) that updates:

- List message counts
- Activity statistics (used by `pminfo.json`)

### Importing Existing Archives

```bash
cd /opt/ponymail-foal/tools
python3 import-mbox.py --source /path/to/mbox-files/
```

Use `--lid listname@domain` to override list detection. For migration
from old PonyMail, see [MIGRATING.md](../MIGRATING.md).
