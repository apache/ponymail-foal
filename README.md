# Apache Pony Mail Foal
<img src="https://github.com/apache/ponymail-foal/blob/master/webui/images/foal.png" width="72" align="left"/>

_Next-generation suite of services and tools for Apache Pony Mail_

[![Linting](https://github.com/apache/ponymail-foal/actions/workflows/linting.yml/badge.svg)](https://github.com/apache/ponymail-foal/actions/workflows/linting.yml)
[![Foal Type Tests](https://github.com/apache/ponymail-foal/actions/workflows/type-tests.yml/badge.svg)](https://github.com/apache/ponymail-foal/actions/workflows/type-tests.yml)
[![Unit Tests](https://github.com/apache/ponymail-foal/actions/workflows/unittest.yml/badge.svg)](https://github.com/apache/ponymail-foal/actions/workflows/unittest.yml)
[![Integration Tests](https://github.com/apache/ponymail-foal/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/apache/ponymail-foal/actions/workflows/integration-tests.yml)


This repository aims to contain the next generation of Apache Pony Mail,
a pure Python version of Apache Pony Mail with support for ElasticSearch 
7.x and above.

<img src="https://github.com/apache/ponymail-foal/blob/master/webui/images/foal-demo1.png" style="width: 95%"/>

<img src="https://github.com/apache/ponymail-foal/blob/master/webui/images/foal-demo2.png" style="width: 95%"/>


## New features in Foal:
Among other things, Foal sports the following new features:

* Improved archiver and import tools
* New, sleeker UI for the end user
* Migration tools for moving to Foal
* 100% Python backend, no Lua required
* In-place editing of emails via web UI

## Installation Guide
Please see the [installation documentation](INSTALL.md) for setup instructions.

## Documentation
Full documentation is available in the [docs/](docs/index.md) directory, including:
- [Operator Guide](docs/operator_guide.md) — Install and deploy
- [User Guide](docs/user_guide.md) — Browse, search, reply
- [API Reference](docs/API.md) — HTTP endpoint specs
- [Configuration Reference](docs/configuration.md) — All config options

### Current setup requirements:

* An operating system, such as:
  * Linux
  * FreeBSD
  * Windows
  * Mac OS
* Python 3.8 or higher with dependencies from `requirements.txt` in tools/ and server/ as needed.
* Web server with proxy capabilities for the UI.
* ElasticSearch 7.x or higher.


### Migration disclaimer:
_While compatible with the original Pony Mail, this will not be a drop-in replacement.
Migration of the old database is required, and most older ID generators have 
been dropped in favor of collision-secure generators._

### Known Limitations:
* Emails are filed according to the Date: header rather than arrival time.
  This can cause emails to appear in the wrong month or year or even be future-dated.
* While the underlying database can handle any number of emails a month, 
  the UI and much of the API do not scale well beyond 10,000 emails per month per list.
* Re-archiving/importing a previously hidden email will unhide it in the archive.

#### Known limitations when migrating from older Pony Mail instances:
* The database entry is entirely replaced if an email is re-imported or re-archived after a migration.
  This can result in the loss of attributes such as alternate Permalinks.
* The migration tool can drop Permalinks if two existing entries point to a sufficiently similar email
* The migration tool does not fix up badly parsed message IDs etc
* There is no longer a 1-to-1 relationship between mbox and source entries.
  This can result in orphan source entries, which has implications for privacy redaction.
* Header parsing is stricter than before; some unusual message IDs are not handled correctly.
  This affects using Foal as a replacement for Apache mod_mbox mail archives.
