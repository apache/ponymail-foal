#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import importlib.util
import logging
import os.path
import shutil
import sys
import yaml

if sys.version_info < (3, 8):
    print("This script requires Python 3.8 or higher in order to work!")
    sys.exit(-1)

DEFAULT_DB_URL = "http://localhost:9200/"
dburl = ""
dbname = ""
mlserver = ""
mldom = ""
wc = ""
genname = ""
wce = False
shards = 0
replicas = -1
nonce = None
supported_generators = ["dkim", "full"]


def create_indices():
    """Creates new indices for a fresh pony mail installation, it possible"""
    # Check if index already exists
    if es.indices.exists(dbname + "-mbox"):
        if args.soe:
            print(
                "ElasticSearch indices with prefix '%s' already exists and SOE set, exiting quietly"
                % dbname
            )
            sys.exit(0)
        else:
            print(
                "Error: Existing ElasticSearch indices with prefix '%s' already exist!"
                % dbname
            )
            sys.exit(-1)

    print(f"Creating indices {dbname}-*...")

    settings = {"number_of_shards": shards, "number_of_replicas": replicas}
    mapping_file = yaml.safe_load(open("mappings.yaml", "r"))
    for index, mappings in mapping_file.items():
        res = es.indices.create(
            index=f"{dbname}-{index}", body={"mappings": mappings, "settings": settings}
        )

        print(f"Index {dbname}-{index} created! %s " % res)


# Check for all required Python packages
wanted_pkgs = [
    "elasticsearch",  # used by setup.py, archiver.py and elastic.py
    "formatflowed",  # used by archiver.py
    "netaddr",  # used by archiver.py
    "certifi",  # used by archiver.py and elastic.py
]

missing_pkgs = list(wanted_pkgs)  # copy to avoid corruption
for pkg in wanted_pkgs:
    if importlib.util.find_spec(pkg):
        missing_pkgs.remove(pkg)

if missing_pkgs:
    print("It looks like you need to install some Python modules first")
    print("The following packages are required: ")
    for pkg in missing_pkgs:
        print(" - %s" % pkg)
    print("You may use your package manager, or run the following command:")
    print("pip3 install %s" % " ".join(missing_pkgs))
    sys.exit(-1)


# at this point we can assume elasticsearch is present
from elasticsearch import VERSION as ES_VERSION  # noqa: E402
from elasticsearch import ConnectionError as ES_ConnectionError  # noqa: E402
from elasticsearch import Elasticsearch, ElasticsearchException  # noqa: E402

ES_MAJOR = ES_VERSION[0]

# CLI arg parsing
parser = argparse.ArgumentParser(description="Command line options.")

parser.add_argument(
    "--defaults", dest="defaults", action="store_true", help="Use default settings"
)
parser.add_argument(
    "--devel", dest="devel", action="store_true", help="Use developer settings (shards=1, replicas=0)"
)
parser.add_argument(
    "--clobber",
    dest="clobber",
    action="store_true",
    help="Allow overwrite of ponymail.yaml & ../site/api/lib/config.lua (default: create *.tmp if either exists)",
)
parser.add_argument("--dburl", dest="dburl", type=str, help="ES backend URL")
parser.add_argument("--dbname", dest="dbname", type=str, help="ES DB prefix")
parser.add_argument("--dbshards", dest="dbshards", type=int, help="DB Shard Count")
parser.add_argument(
    "--dbreplicas", dest="dbreplicas", type=int, help="DB Replica Count"
)
parser.add_argument(
    "--mailserver",
    dest="mailserver",
    type=str,
    help="Host name of outgoing mail server",
)
parser.add_argument(
    "--mldom", dest="mldom", type=str, help="Domains to accept mail for via UI"
)
parser.add_argument(
    "--wordcloud", dest="wc", action="store_true", help="Enable word cloud"
)
parser.add_argument(
    "--skiponexist",
    dest="soe",
    action="store_true",
    help="Skip setup if ES index exists",
)
parser.add_argument(
    "--noindex",
    dest="noi",
    action="store_true",
    help="Don't create ElasticSearch indices, assume they exist",
)
parser.add_argument(
    "--nocloud", dest="nwc", action="store_true", help="Do not enable word cloud"
)
parser.add_argument(
    "--generator",
    dest="generator",
    type=str,
    help="Document ID Generator to use (dkim, full)",
)
parser.add_argument(
    "--nonce",
    dest="nonce",
    type=str,
    help="Cryptographic nonce to use if generator is DKIM/RFC-6376 (--generator dkim)",
)
args = parser.parse_args()

print("")
print("Welcome to the Pony Mail setup script!")
print("Let's start by determining some settings...")
print("")


# If called with --defaults (like from Docker), use default values
if args.defaults:
    dburl =  DEFAULT_DB_URL
    dbname = "ponymail"
    mlserver = "localhost"
    mldom = "example.org"
    wc = "Y"
    wce = True
    shards = 3
    replicas = 1
    genname = "dkim"
    urlPrefix = ""
    nonce = None

if args.devel:
    dburl =  DEFAULT_DB_URL
    dbname = "ponymail"
    mlserver = "localhost"
    mldom = "example.org"
    wc = "Y"
    wce = True
    shards = 1
    replicas = 0
    genname = "dkim"
    urlPrefix = ""
    nonce = None

# Accept CLI args, copy them
if args.dburl:
    dburl = args.dburl
if args.dbname:
    dbname = args.dbname
if args.mailserver:
    mlserver = args.mailserver
if args.mldom:
    mldom = args.mldom
if args.wc:
    wc = "y"
    wce = True
if args.nwc:
    wc = "n"
    wce = False
if args.dbshards:
    shards = args.dbshards
if args.dbreplicas is not None: # Allow for 0 value
    replicas = args.dbreplicas
if args.generator:
    if all(x in supported_generators for x in args.generator.split(' ')):
        genname = args.generator
    else:
        sys.stderr.write(
            "Invalid generator specified. Must be one of: "
            + ", ".join(supported_generators)
            + "\n"
        )
        sys.exit(-1)
if args.generator and any(x == "dkim" for x in args.generator.split(' ')) and args.nonce is not None:
    nonce = args.nonce

if not dburl:
    dburl = input("What is the URL of the ElasticSearch server? [%s]: " % DEFAULT_DB_URL)
    if not dburl:
        dburl =  DEFAULT_DB_URL

if not dbname:
    dbname = input("What would you like to call the mail index [ponymail]: ")
    if not dbname:
        dbname = "ponymail"

if not mlserver:
    mlserver = input(
        "What is the hostname of the outgoing mailserver hostname? [localhost]: "
    )
    if not mlserver:
        mlserver = "localhost"

if not mldom:
    mldom = input("Which domains would you accept mail to from web-replies? [*]: ")
    if not mldom:
        mldom = "*"

while wc.lower() not in ["y", "n"]:
    wc = input("Would you like to enable the word cloud feature? (Y/N) [Y]: ").lower()
    if not wc:
        wc = "y"
    if wc.lower() == "y":
        wce = True

while genname == "":
    print("Please select a document ID generator:")
    print(
        "1  [RECOMMENDED] DKIM/RFC-6376: Short SHA3 hash useful for cluster setups with permalink usage"
    )
    print(
        "2  FULL: Full message digest with MTA trail. Not recommended for clustered setups."
    )
    try:
        ans = input("Please select a generator (1 or 2) [1]: ")
        if ans:
            gno = int(ans)
        else:
            gno = 1
        if gno <= len(supported_generators) and supported_generators[gno - 1]:
            genname = supported_generators[gno - 1]
    except ValueError:
        pass

if genname == "dkim" and (nonce is None and not args.defaults and not args.devel):
    print(
        "DKIM hasher chosen. It is recommended you set a cryptographic nonce for this generator, though not required."
    )
    print(
        "If you set a nonce, you will need this same nonce for future installations if you intend to preserve "
    )
    print("permalinks from imported messages.")
    nonce = (
        input("Enter your nonce or hit [enter] to continue without a nonce: ") or None
    )

while shards < 1:
    try:
        ans = input("How many shards for the ElasticSearch index? [3]: ")
        if ans:
            shards = int(ans)
        else:
            shards = 3
    except ValueError:
        pass

while replicas < 0:
    try:
        ans = input("How many replicas for each shard? [1]: ")
        if ans:
            replicas = int(ans)
        else:
            replicas = 1
    except ValueError:
        pass

print("Okay, I got all I need, setting up Pony Mail...")

# we need to connect to database to determine the engine version
es = Elasticsearch(
    [dburl],
    max_retries=5,
    retry_on_timeout=True,
)

# elasticsearch logs lots of warnings on retries/connection failure
logging.getLogger("elasticsearch").setLevel(logging.ERROR)

try:
    DB_VERSION = es.info()["version"]["number"]
except ES_ConnectionError:
    print("WARNING: Connection error: could not determine the engine version.")
    DB_VERSION = "0.0.0"

DB_MAJOR = int(DB_VERSION.split(".")[0])
print(
    "Versions: library %d (%s), engine %d (%s)"
    % (ES_MAJOR, ".".join(map(str, ES_VERSION)), DB_MAJOR, DB_VERSION)
)
if DB_MAJOR < 7:
    print("This version of Pony Mail requires ElasticSearch 7.x or higher")

if not DB_MAJOR == ES_MAJOR:
    print("WARNING: library version does not agree with engine version!")

if DB_MAJOR == 0:  # not known
    if args.noi:
        # allow setup to be used without engine running
        print(
            "Could not determine the engine version. Assume it is the same as the library version."
        )
        DB_MAJOR = ES_MAJOR
    else:
        # if we cannot connect to get the version, we cannot create the index later
        print("Could not connect to the engine. Fatal.")
        sys.exit(1)

if not args.noi:
    try:
        create_indices()
    except ElasticsearchException as e:
        print("Index creation failed: %s" % e)
        sys.exit(1)

ponymail_cfg = "archiver.yaml"
if not args.clobber and os.path.exists(ponymail_cfg):
    print("%s exists and clobber is not set" % ponymail_cfg)
    ponymail_cfg = "archiver.yaml.tmp"

print("Writing importer config (%s)" % ponymail_cfg)

with open(ponymail_cfg, "w") as f:
    f.write(
        """
---
###############################################################
# An archiver.yaml is needed to run this project. This sample config file was
# originally generated by tools/setup.py.
# 
# Run the tools/setup.py script and an archiver.yaml which looks a lot like this 
# one will be generated. If, for whatever reason, that script is not working 
# for you, you may use this archiver.yaml as a starting point.
# 
# Contributors should strive to keep this sample updated. One way to do this 
# would be to run the tools/setup.py, rename the generated config to
# archiver.yaml.sample, and then pasting this message or a modified form of 
# this message at the top.
###############################################################

###############################################################
# Pony Mail Archiver Configuration file


# Main ES configuration
elasticsearch:
    dburl:                  %s
    dbname:                 %s
    #wait:                  active shard count
    #backup:                database name

archiver:
    #generator:             dkim|full (dkim recommended)
    generator:              %s
    nonce:                  %s
    policy:                 default   # message parsing policy: default, compat32, smtputf8

debug:
    #cropout:               string to crop from list-id

            """
        % (dburl, dbname, genname, nonce or "~")
    )

print("Copying sample JS config to config.js (if needed)...")
if not os.path.exists("../site/js/config.js") and os.path.exists(
    "../site/js/config.js.sample"
):
    shutil.copy("../site/js/config.js.sample", "../site/js/config.js")

server_cfg  = "../server/ponymail.yaml"
if not args.clobber and os.path.exists(server_cfg):
    print("%s exists and clobber is not set" % server_cfg)
    server_cfg = "../server/ponymail.yaml.tmp"

print("Writing UI backend configuration file %s" % server_cfg)
with open(server_cfg, "w") as f:
    f.write("""
server:
  port: 8080             # Port to bind to
  bind: 127.0.0.1        # IP to bind to - typically 127.0.0.1 for localhost or 0.0.0.0 for all IPs


database:
  dburl: %s      # The URL of the ElasticSearch database
  db_prefix: %s    # DB prefix, usually 'ponymail'
  max_hits: 15000        # Maximum number of emails to process in a search
  pool_size: 15          # number of connections for async queries
  max_lists: 8192        # max number of lists to allow for

ui:
  wordcloud:       %s
  mailhost:        %s
  sender_domains:  "%s"
  traceback:       true
  mgmtconsole:     true # enable email admin
  true_gdpr:       true # fully delete emails instead of marking them deleted

tasks:
  refresh_rate:  150     # Background indexer run interval, in seconds

# Fill in OAuth data as needed
oauth:
# If using OAuth, set the authoritative domains here. These are the OAuth domains that 
# will provide access to private emails.
#  authoritative_domains:
#    - googleapis.com  # OAuth via google is authoritative
#    - github.com      # GitHub OAuth is authoritative
#  admins:
#    - foo@example.org
  google_client_id:     ~
  github_client_id:     ~
  github_client_secret: ~

""" % (dburl, dbname, "true" if wce else "false", mlserver, mldom))


print("All done, Pony Mail should...work now :)")
print(
    "If you are using an external mail inbound server, \nmake sure to copy the contents of this tools directory to it"
)
