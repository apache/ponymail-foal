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

# utility to check mappings, report differences and create missing mappings

#  ** INITIAL VERSION, liable to change **

import argparse
import sys
import yaml
from plugins.elastic import Elastic # pylint: disable=no-name-in-module

if sys.version_info < (3, 8):
    print("This script requires Python 3.8 or higher in order to work!")
    sys.exit(-1)

# the desired mappings
mapping_file = yaml.safe_load(open("mappings.yaml", "r"))

elastic = Elastic()
major = elastic.engineMajor()
if major != 7 and elastic.engineDistribution() != "opensearch":
    print("This script requires ElasticSearch 7 API in order to work!")
    sys.exit(-1)

parser = argparse.ArgumentParser(description="Command line options.")
parser.add_argument(
    "--create",
    dest="create",
    action="store_true",
    help="Create the missing mapping(s)",
)
parser.add_argument(
    "--shards",
    dest="shards",
    type=int,
    help="Create the missing indices",
)
parser.add_argument(
    "--replicas",
    dest="replicas",
    type=int,
    help="Create the missing indices",
)
parser.add_argument('names', nargs='*')
args = parser.parse_args()

def descend(hsh, mapping, parent):
    for k,v in mapping.items():
        keys=parent.copy()
        keys.append(k)
        if 'properties' in v:
            descend(hsh, v['properties'], keys)
        else:
            key = ".".join(keys)
            hsh[key] = v

def check_mapping(index):
    # expected mappings
    mappings_expected = mapping_file[index]['properties']

    index_name = elastic.index_name(index)

    # Check that index exists
    if not elastic.indices.exists(index_name):
        if args.shards and args.replicas is not None:
            print("Creating index")
            settings = {"number_of_shards": args.shards, "number_of_replicas": args.replicas}
            elastic.indices.create(
              index=index_name, body={"mappings": mapping_file[index], "settings": settings}
            )
            print("Created index!")
            return
        else:
            print("Index not found!")
            print("Specify --shards and --replicas to create the index")
            return

    # actual mappings
    mappings = elastic.indices.get_mapping(index=index_name)[index_name]['mappings']['properties']

    expected = yaml.dump(mappings_expected, sort_keys = True)
    actual = yaml.dump(mappings, sort_keys = True).replace("'true'","true")

    if actual == expected:
        print("Mappings are as expected, hoorah!")
    else:
        print("Mappings differ:")

        exp = dict()
        descend(exp, mappings_expected,[])
        act = dict()
        descend(act, mappings,[])

        for k,v in exp.items():
            if k not in act:
                if v == {'dynamic': True, 'type': 'object'}:
                    print(f' Key {k} is dynamic')
                else:
                    print(f"Expected {k} {v}; not found")
            else:
                if not v == act[k]:
                    print(f"Expected {k} {v},  found {k} {act[k]}")


for maptype in args.names if len(args.names) > 0 else mapping_file.keys():
    print("Checking " + maptype)
    check_mapping(maptype)
