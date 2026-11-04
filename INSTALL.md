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

# Installation instructions

<!-- toc -->

- [Installation instructions](#installation-instructions)
  - [Basic requirements](#basic-requirements)
  - [Installation steps:](#installation-steps)
- [Load required modules](#load-required-modules)
  - [Archiving new emails via Postfix or the likes](#archiving-new-emails-via-postfix-or-the-likes)
  - [Setting up OAuth](#setting-up-oauth)
    - [Setting up Google OAuth](#setting-up-google-oauth)
    - [Setting up GitHub OAuth](#setting-up-github-oauth)
  - [Setting up web replies](#setting-up-web-replies)
  - [Online Management Console](#online-management-console)
  - [Hiding tracebacks from users](#hiding-tracebacks-from-users)
  - [Archiving options](#archiving-options)

<!-- tocstop -->

## Basic requirements
- Linux or other UNIX-like operating system
- ElasticSearch 7.x or higher installed
- Python 3.7.3 or higher
- PipEnv program (typically `apt install pipenv` or `yum install pipenv` etc)
- A web server of your choice with proxy capabilities

Warning: the ElasticSearch client libraries from 7.14 have strict server version checking
and will not run with the wrong version.
You may need to update the requirements.txt files in tools/ and server/ accordingly.

## Installation steps:

- Clone the Foal git repository to your machine: `git clone https://github.com/apache/ponymail-foal.git foal`
- Install the Python requirements for the setup:
~~~shell script
cd foal/tools
pipenv install -r requirements.txt
~~~
- Install any desired optional dependencies, for example:
  - html2text (GNU GPL 3) - convert HTML to plain text
  - mailman (GPLv3+) - interface with Mailman lists
  - zope (Zope Public Licence 2.1) - required for Mailman integration
- Run the setup process:
~~~shell script
pipenv run python3 setup.py
cd ..
~~~
- Import any mailboxes you need to, using `tools/import-mbox.py` OR migrate your old Pony Mail database
  using the [Foal migrator](MIGRATING.md). 
- Install the server requirements:
~~~shell script
cd server/
pipenv install -r requirements.txt
~~~
- start the server:
~~~shell script
pipenv run python3 main.py
~~~
- use a web server like httpd or nginx to serve UI and proxy to the API. A sample httpd configuration could be:
~~~apache
# Load required modules
LoadModule proxy_module ...
LoadModule proxy_http_module ...
...
<VirtualHost *:80>
    ServerName ponymail.example.org
    DocumentRoot /var/www/ponymail-foal/webui/
    ProxyPass /api/ http://localhost:8080/api/
    # PathInfo is needed for threads
    AcceptPathInfo On
    # Also needed for threads to be able to handle message-ids with embedded /:
    AllowEncodedSlashes On # (or NoDecode)
</VirtualHost>
~~~

A sample nginx config could be:
~~~nginx
server {
    root /var/www/ponymail-foal/webui/;
    index index.html index.htm;
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
    }
}
~~~


## Archiving new emails via Postfix or the likes
To set up archiving, the easiest path is to edit your `/etc/aliases` file on the machine
that receives email. If your receiving address for email is `inbox@yourmachine.tld`, your 
alias entry should look like this:
~~~text
inbox: "| /path/to/foal/tools/archiver.py"
~~~

For privately archived emails, use the `--private` flag for your command:

~~~text
inbox: "| /path/to/foal/tools/archiver.py --private"
~~~

Once you have added the entry, be sure to run the `newaliases` command to update the compiled alias list.
`archiver.py` will automatically sort out which list the email is for, if there is a List-ID header.
You can override or manually set a list using the `--lid` flag:
~~~text
inbox-somealias: "| /path/to/foal/tools/archiver.py --lid somealias@mydomain.tld"
~~~

## Setting up OAuth
By default, OAuth is enabled for the following providers:

- Google
- GitHub
- Generic (like oauth.apache.org)

None of these are marked as _authoritative_ by default. Authoritative OAuth domains 
allow users to compose emails via the UI and see private emails (unless you reshape the 
AAA plugin). Non-authoritative domains only allows the user to log in, nothing more.

To set an OAuth provider as authoritative, you need to add or uncomment the 
`authoritative_domains` section of the `oauth` configuration in `server/ponymail.yaml`:

~~~yaml
oauth:
  authoritative_domains:
    - googleapis.com
    - myoauthprovider.tld
~~~

For administrative access to certain features, such as deleting/moving email via the UI,
you can set a list of people who, via an authoritative oauth provider, will have access to
this, as such:

~~~yaml
oauth:
  authoritative_domains:
    - googleapis.com
  admins:
    - humbedooh@gmail.com
    - example@gmail.com
~~~


### Setting up Google OAuth
To begin using Google OAuth, you must procure an OAUth2 client id from the 
[Gooogle Developers Console](https://console.developers.google.com/apis/credentials/oauthclient/).
Callback URL must be oauth.html in your webui installation.

Once you have a `Client ID`, you should set it in `server/ponymail.yaml`  in the 
`google_client_id` directive.

After this is done, OAuth should work with Google, and you may enable authoritativeness by adding 
`googleapis.com` to the `authoritative_domains` section in `server/ponymail.yaml`.

### Setting up GitHub OAuth
To begin using GitHub OAuth, create an OAuth app at the 
[GitHub Developer Console](https://github.com/settings/developers).
Callback URL must be oauth.html in your webui installation.

Once you have created your OAuth app, copy the client ID and client secret to your 
`server/ponymail.yaml` oauth section, as `github_client_id` and `github_client_secret` 
respectively.

## Setting up web replies
It is possible to reply to emails on a list via the web interface, provided you have enabled
this feature. To do so, you must set a `mailhost` option as well as designate certain 
domains and subdomains as allowed recipients of email. This is done in the `server/ponymail.yaml`
file, under ui:
~~~yaml
ui:
  wordcloud: true
  mailhost: smtp.mydomain.tld:25
  sender_domains: mydomain.tld *.mydomain.tld
~~~

You may use wildcards in your domain names, as per standard GLOB/fnmatch rules, 
separating each entry with a single space:
- to allow email for list@mydomain.tld, sender_domains must include `mydomain.tld`
- to allow email for list@sub.mydomain.tld, you should add `sub.mydomain.tld`
- to allow email for all lists at any subdomain under mydomain.tld, you should add `*.mydomain.tld`

Only users logged in via authoritative OAuth will be able to compose replies via the
web interface.

## Online Management Console
the `ui` paragraph of the server configuration allows for enabling an administrative interface
for editing or removing emails from the archives. To enable this, set `mgmtconsole` to `true`.
For GDPR compliance (deleting an email deletes from disk), set `allow_delete` to `true`. 
If left out or set to false, deleted emails are merely hidden, and can be recovered at a later 
stage by an administrator.

~~~yaml
ui:
  mgmtconsole:     true
  allow_delete:       true
~~~

The administrative interface can be accessed by clicking on the yellow cog in the context menu 
of an email. Admins are defined in the [OAuth](#setting-up-oauth) configuration.


## Hiding tracebacks from users
By default, API errors will include a full traceback for debugging purposes. If you wish to 
instead have this be printed to the system journal (`stderr`), you can set the `traceback`
option to `false` in `server/ponymail.yaml`. This will instead print an error ID to the user, 
corresponding to a traceback in stderr. 

If the error ID is, for instance, `a06f7d4b-3a82-4ecf`, you can find the corresponding traceback
by grepping your programs output. If you are running Foal as a systemd service, you could find 
the traceback with: `journalctl --no-pager -u yourservicename | grep a06f7d4b-3a82-4ecf`

## Archiving options
To enable the storage in elasticsearch of extra properties related to
threading, the following configuation snippet can be used in the
`server/ponymail.yaml` file:
~~~yaml
archiver:
  threadinfo: yes
  threadparents: 10
  threadtimeout: 5
~~~
The `threadparents` value limits the number of existing messages that
will be queried for thread information at archive time when a new
message is received. The `threadtimeout` value limits the duration of
each query to elasticsearch.

Enabling `threadinfo` means that `top`, `thread`, and `previous`
properties will be added to each stored message. The `top` property is
a boolean, indicating whether or not the message is the start of a new
thread. The `thread` property gives the generated Foal ID of the top
of the current thread; this will be the same as the ID of the current
message if `top` is true. The `previous` property gives the generated
Foal ID of either the most recent parent message if the message is not
the top of a thread, or the top of the most recent thread otherwise.
