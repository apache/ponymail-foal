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

Docker execution instructions
=============================

These are initial instructions; so far, they have only been tested on macOS (M1).

Note that the ```docker compose``` commands must be issued from the top-level directory
of the source checkout, i.e. where DockerFile and compose.yaml are located.

Build Docker image
==================
Checkout Pony Mail Foal from Git:

```shell
$ git clone https://github.com/apache/ponymail-foal.git ponymail-foal
$ cd ponymail-foal
```

Start Docker (e.g. [on macOS] open ~/Applications/Docker.app).

Build the image:

```shell
$ docker compose build
```

Resolve any issues (e.g., ensure Docker has access to the required directories) and rebuild.

Start ElasticSearch, httpd and the API
======================================

Open a new terminal session:

```shell
$ cd ponymail-foal
$ [MAIL_DATA=/path/to/mailboxes] docker compose up
```

If provided, the directory at MAIL_DATA is mapped onto /var/maildata
This is to allow easy access to mailboxes on the host system, e.g. for importing.
[If not provided, then the source code directory is mapped]

The ElasticSearch server and httpd server will be started.

The ElasticSearch database will automatically be created if necessary.

Then the PonyMail API server will be started.

Stopping the server
===================

To stop the server issue the following in another terminal session:

```shell
$ cd ponymail-foal
$ docker compose down
```

This ensures that the container is shut down and removed.
You can also use '^C' in the original terminal session,
but that will leave the container intact, which may interfere with subsequent startups.

[You can use `docker compose down` to remove the contaier]

Importing mbox files for testing
================================

To test existing mbox files, you can use the import-mbox.py script.
You can download a publicly available file using this link:

```shell
mkdir mbox-testdata
cd mbox-testdata
wget https://lists.apache.org/api/mbox.lua?list=dev&domain=community.apache.org
cd ..
```

Then import it:

```shell
$ tools/import-mbox.py --source mbox-testdata/dev_community_apache_org.mbox
```

This will import the mbox file into the database.

Note that the script requires the Python modules noted in `tools/requirements.txt'

You can also load the mbox files in the container:

```shell
$ docker compose exec pmfoal tools/import-mbox.py --source /var/maildata/path-to-mbox
```

This assumes that the mbox file is located under the path specified in the 
MAIL_DATA environment variable used when starting the container.
[If not provided, then the source folder is mapped to /var/maildata instead]

Connect to the server
=====================

Browse to http://localhost:1080/
