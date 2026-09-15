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

"""
Simple endpoint that returns the server's gathered activity data

THIS ONLY DEALS WITH PUBLIC EMAILS FOR NOW - AAA IS BEING WORKED ON
"""

import plugins.server
import plugins.session
import plugins.messages
import plugins.defuzzer
import plugins.offloader
import email.utils
import typing
import aiohttp.web
import time

async def process(
    server: plugins.server.BaseServer, session: plugins.session.SessionObject, indata: dict,
) -> typing.Union[dict, aiohttp.web.Response]:

    # must provide list and domain
    xlist = indata.get("list", None)
    xdomain = indata.get("domain", None)
    social = indata.get("social", None) == "yes"
    if not xlist or not xdomain:
        return aiohttp.web.Response(headers={"content-type": "application/json",}, text='{}')

    try:
        query_defuzzed = plugins.defuzzer.defuzz(indata)
        query_defuzzed_nodate = plugins.defuzzer.defuzz(indata, nodate=True)
    except ValueError as ve:  # If defuzzer encounters syntax errors, it will throw a ValueError
        return aiohttp.web.Response(headers={"content-type": "text/plain",}, status=400, text=str(ve))
    except AssertionError as ae:  # If defuzzer encounters internal errors, it will throw an AssertionError
        return aiohttp.web.Response(headers={"content-type": "text/plain",}, status=500, text=str(ae))
    
    # get a filter for use with get_activity_span (no date)
    # It can also be used with dated queries
    query_filter = await plugins.messages.get_accessible_filter(session, query_defuzzed_nodate)
    if query_filter:
        query_defuzzed['filter'] = query_filter
        query_defuzzed_nodate['filter'] = query_filter

    # since: check if there have been recent updates to the data
    if 'since' in indata:
        since = indata.get('since', None)
        if since:
            epoch = int(since)
        else:
            epoch = int(time.time())
        query_since = query_defuzzed.copy()
        query_since['must'].append({"range" : { "epoch": { "gt": epoch}}})
        results = await plugins.messages.query(
            session, query_since, query_limit=1, social_stats=social, source_fields=[] # don't need any fields
        )
        if len(results) == 0:
            return {"changed" : False}

    # statsOnly: Whether to only send statistical info (for n-grams etc), and not the
    # thread struct and message bodies
    # Param: quick
    statsOnly = 'quick' in indata
    # emailsOnly: return email summaries only, not derived data:
    # i.e. omit thread_struct, top 10 participants and word-cloud   
    emailsOnly = 'emailsOnly' in indata

    source_fields = None
    if statsOnly:
        source_fields = ['epoch']

    results = await plugins.messages.query(
        session,
        query_defuzzed,
        query_limit=server.config.database.max_hits,
        source_fields=source_fields,
        social_stats=social,
    )

    wordcloud = None
    if server.config.ui.wordcloud and not emailsOnly and not statsOnly:
        wordcloud = await plugins.messages.wordcloud(session, query_defuzzed)
    oldest, youngest, active_months = await plugins.messages.get_activity_span(session, query_defuzzed_nodate)

    authors = {}
    tstruct = {}
    top10_authors = None
    if not statsOnly and not emailsOnly:
        threads = plugins.messages.ThreadConstructor(results)
        tstruct, authors = await server.runners.run(threads.construct)

        # author entries are now [count, gravatar]
        # as we cannot reconstruct the correct gravatar from an anonymised address
        all_authors = sorted(authors.items(), key=lambda x: x[1][0], reverse=True)  # sort in reverse by author count
        top10_authors = []
        for author, data in all_authors[:10]:
            name, address = email.utils.parseaddr(author)
            top10_authors.append(
                {"email": address, "name": name, "count": data[0], "gravatar": data[1]}
            )

    # Trim email data so as to reduce download sizes
    for msg in results:
        if statsOnly:
            for header in list(msg.keys()):
                if not header == 'epoch':
                    del msg[header]
        else:
            plugins.messages.trim_email(msg, external=True)

    output = {
        "firstYear": oldest.year,
        "lastYear": youngest.year,
        "firstMonth": oldest.month,
        "lastMonth": youngest.month,
        "active_months": active_months,
        "hits": len(results),
        "numparts": len(authors),
        "no_threads": len(tstruct),
        "emails": list(sorted(results, key=lambda x: x["epoch"])),
        "participants": top10_authors or {},
        "searchlist": f"<{xlist}.{xdomain}>",
        "domain": xdomain,
        "name": xlist,
        "list": f"{xlist}@{xdomain}",
        "searchParams": indata,
        "unixtime": int(time.time()),
    }
    if not statsOnly and not emailsOnly:
        output['thread_struct'] = tstruct
    if wordcloud:
        output['cloud'] = wordcloud
    return output


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process)
