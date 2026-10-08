#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""Caching proxy for Gravatars"""

import plugins.server
import plugins.session
import aiohttp
import aiohttp.web
import base64
import string
import typing

CACHE_LIMIT = 25000  # Store a maximum of 25,000 gravatars in memory at any given time (25k x 5kb ≃125mb)
GRAVATAR_URL = "https://secure.gravatar.com/avatar/%s.png?s=96&r=g&d=mm"

gravatars: list[str] = []
gravatar_cache: dict[str, typing.Any] = {}
gravatar_default = base64.b64decode("""\
/9j/4AAQSkZJRgABAQEAYABgAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlB
FRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCg
sLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/9sAQwEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUF
BQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAYABgAwEiAAIRAQMR
Af/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwA
EEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSE
lKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4u
brCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAA
AAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaG
xwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdH
V2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2
uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A+t/yo49qO1FABR+VFFAB+VH5UUUAH5Uce1H4
0fjQAce1H5Uv40n40AHHtRx7UfjS/jQAnaiiigAopa6j4eeGF8R61mdd1nbASSg9GP8ACv4/yBoAn8J
/Dm88Qxrc3Dmysm5VyMvIP9kenuf1r0Gy+GegWaANaNct/fmkYk/gCB+ldSqhFCqAFHAA6Cj/AD1oA5
e8+Gnh+7QhbQ27f34ZGBH4EkfpXn/iz4b3nh+N7q1c3tkvLEDDxj3Hce4r2j/PWggMCDgg9QaAPmaiu
s+I3hhPD2sCS3ULZ3QLoo6I38S/qD+NclQAtFJ/npRQAUUUtACV7D8IbVYvDk8wHzy3DZPsAAB/P868
er1r4PagsukXlmSPMhm8zH+ywA/mp/OgD0Gik/z0ooAWiko/z0oA4r4t2qzeGElI+aGdSD7EEEfqPyr
xqvXvi/qCwaFbWgI8yebdj/ZUHP6kV5FQAn+etFLRQAlFHaigArY8J+IpPDOsRXaAvEfkljB+8h6/j3
H0rIrR0Lw7feI7ryLKEuR9+RuEQepNAH0Bp2o2+q2cd1ayrNBIMqwP6H0NWP8APWuX8G+CB4VVnN7NP
K4+dFO2L/vnufeupoAT/PWoL+/t9MtJLm5lWGCMZZ2NWK5fxl4K/wCEqRWF7NBJH9yNjuiz6lfX3oA8
o8XeJJPE+sSXRBSBRshjP8Kj19z1rErS13w7feHLryL2EoT9yReUceoNZtABRRRQAhoopcZNAGv4W8N
3HifVEtYfkjHzSy44Rf8AH0Fe7aRo9podjHaWcQjiT82PqT3NZXgXw4vhzQoo3UC7mAknPfJ6L+A4/O
uh/wA9aAD/AD0opf8APWk/z1oAKP8APSj/AD1pf89aAKWr6Pa65YvaXkQkib81PYg9jXhXijw3P4Y1R
7Wb54z80UuOHX/H1FfQP+etc9458OL4j0OWNFBu4QZID3yOq/iOPyoA8HooIwaKAE7V0PgLShq/iqyi
dd0Ubec49l5/ngfjXPGvQ/g3bB9U1G4xzHEqA/7xz/7LQB6xRSUUALRSf56UUALRSUf56UALRSUUAeD
ePNKGkeKb2JF2xSN5yD2bn+eR+Fc/Xofxktgmp6fcY5khZCf905/9mrzygD//2Q==
""")

async def fetch_gravatar(gid: str) -> None:
    headers = {"User-Agent": "Pony Mail Agent/0.1"}
    fetch_url = GRAVATAR_URL % gid
    # Fetch image and store internally
    try:
        async with aiohttp.client.request("GET", fetch_url, headers=headers) as rv:
            img_data = await rv.read()
            gravatars.append(gid)
            gravatar_cache[gid] = img_data
    except aiohttp.ClientError:  # Client error, bail.
        pass


async def gravatar_exists_in_db(session: plugins.session.SessionObject, gid: str) -> bool:
    assert session.database is not None # make mypy happy
    res = await session.database.search(
        index=session.database.dbs.db_mbox,
        size=1,
        body={"query": {"bool": {"must": [{"term": {"gravatar": gid}}]}}},
    )
    if res and len(res["hits"]["hits"]) == 1:
        return True
    return False


async def process(_server: plugins.server.BaseServer, session: plugins.session.SessionObject, indata: dict) -> aiohttp.web.Response:
    gid = indata.get("md5", "null")
    # Ensure md5 hash is valid
    is_valid_md5 = len(gid) == 32 and all(letter in string.hexdigits for letter in gid)

    # Valid and in cache??
    in_cache = gid in gravatars
    should_fetch = False

    # If valid but not cached, check if gravatar exists in the pony mail db
    if is_valid_md5 and not in_cache:
        should_fetch = await gravatar_exists_in_db(session, gid)
    # If valid and not in cache, fetch from gravatar.com
    if not in_cache and should_fetch:
        await fetch_gravatar(gid)
        # If we've hit the cache limit, pop the oldest element.
        if len(gravatars) > CACHE_LIMIT:
            to_pop = gravatars.pop(0)
            del gravatar_cache[to_pop]
    # if in cache, serve it.
    headers = {
      "Cache-Control": "max-age=86400",  # Expire gravatar in one day
    }
    if is_valid_md5 and gid in gravatars:
        img = gravatar_cache[gid]
        return aiohttp.web.Response(headers=headers, content_type="image/png", body=img)
    return aiohttp.web.Response(headers=headers, content_type="image/png", body=gravatar_default)


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process, token_allowed=True)
