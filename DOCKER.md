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
Checkout Ponymail Foal from Git:

```
$ git clone https://github.com/apache/incubator-ponymail-foal.git ponymail-foal
$ cd ponymail-foal
```

Start Docker (e.g. [on macOS] open ~/Applications/Docker.app). Build the image:

```$ docker compose build```

Resolve any issues (e.g., ensure Docker has access to the required directories) and rebuild.

Start ElasticSearch and the main server
=======================================

Open a new terminal session:

```
$ cd ponymail-foal
$ [MAIL_DATA=/path/to/mailboxes] docker compose up
```

If provided, the directory at MAIL_DATA is mapped onto /var/maildata
This is to allow easy access to mailboxes on the host system, e.g. for importing.
[If not provided, then the source code directory is mapped]

To stop the server, either use `^C`, or issue the following in another terminal session:

```$ docker compose stop```

Setup the ElasticSearch database
================================

The following step only needs to be done once.
(The output is cached under elastic/)
The container must already be running.

Open a new terminal session and start a shell in the container:

```
$ docker compose exec pmfoal bash
# cd tools
# python3 setup.py --devel
```

Or you can do it all in one command:

```$ docker compose exec pmfoal bash -c 'cd tools; python3 setup.py --devel'```

Or you can set up the database from the host.
The container must be running, and the Python packages (as per tools/requirements.txt)
must have been installed.

```
$ cd ponymail-foal; cd tools
$ python3 setup.py --devel
```

You can then use archiver.py or import-mbox.py to populate the database.

Importing mbox files for testing
================================

To test existing mbox files, you can use the import-mbox.py script.
You can download a publicly available file using this link:

```
mkdir mbox-testdata
cd mbox-testdata
wget https://lists.apache.org/api/mbox.lua?list=dev&domain=community.apache.org
cd ..
```

Then import it:

```
$ tools/import-mbox.py --source mbox-testdata/dev_community_apache_org.mbox
```

This will import the mbox file into the database.

Start the Ponymail api server
=============================

Open a new terminal session start a shell in the container:

```
$ docker compose exec pmfoal bash
# cd server
# python3 main.py --testendpoints
```

Or you can combine them:

```$ docker compose exec pmfoal bash -c 'cd server; python3 main.py --testendpoints'```

Update config.js to allow local login
=====================================

If you wish to test functions that require log in, update config.js to enable the two logins.

For testing email and admin functions, you may need to update server/ponymail.yaml

Connect to the server
=====================

Browse to http://localhost:1080/
