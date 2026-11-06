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
Plain text endpoint for enabling some search engines to index mail archives

This feature shows all publicly available lists and threads as plain HTML, 
   which may be needed for some search engines to index the lists. It has a
   canonical link to the standard corresponding URLs, which should make 
   the indexed data available under the right URLs when searching.
"""

import plugins.server
import plugins.session
import plugins.messages
import plugins.defuzzer
import aiohttp.web
import html


def count_replies(thread):
    """Simple function for counting how many replies an email thread has"""
    count = 0
    for child in thread["children"]:
        count += count_replies(child) + 1
    return count


async def process(
    server: plugins.server.BaseServer,
    session: plugins.session.SessionObject,
    indata: dict,
) -> aiohttp.web.Response:

    output = ""
    canonical_link = None
    title = "Apache Pony Mail"

    # Has a list or thread id been provided?
    list_id = html.escape(indata.get("list", ""))
    thread_id = html.escape(indata.get("thread", ""))

    # Show an email (or thread)
    if thread_id:
        canonical_link = f"""/thread.html/{thread_id}"""
        email = await plugins.messages.get_email(session, permalink=thread_id)
        if email:
            listname = html.escape(
                "@".join(email.get("list_raw", "").strip("<>").split(".", 1))
            )
            date = html.escape(email.get("date", ""))
            author = html.escape(email.get("from", ""))
            output += f"""Posted to <a href="/list.html?{listname}">{listname}</a> by {author} on {date} UTC<br/>"""
            title = html.escape(email.get("subject", ""))
            body = html.escape(email.get("body", ""))
            _thread, _emails, pdocs = await plugins.messages.fetch_children(
                session, email
            )
            output += f"""<h1>{email["subject"]}</h1><pre>{body}</pre><hr/>\n"""
            for _tid, childemail in pdocs.items():
                body = html.escape(childemail.get("body", ""))
                author = html.escape(childemail.get("from", ""))
                output += f"""<h2>{childemail["subject"]}</h2>\n<b>Posted by {author}.</b><hr/><pre>{body}</pre><hr/>\n"""
    # Show a list
    elif list_id:
        # Make sure we can actually index this list
        can_view = False
        if list_id in server.data.lists:
            if not server.data.lists[list_id].get("private", True):
                can_view = True
        if can_view:
            l, d = list_id.split("@", 1)
            month = indata.get("date")
            mydata = {
                "list": l,
                "domain": d,
            }

            # Do we have a specific month to show?
            if month:
                title = html.escape(f"{list_id}, {month}")
                mydata["date"] = month
                query_defuzzed = plugins.defuzzer.defuzz(mydata)
                canonical_link = f"/list.html?{list_id}:{month}"
                results = await plugins.messages.query(
                    session,
                    query_defuzzed,
                    query_limit=server.config.database.max_hits,
                )
                threads = plugins.messages.ThreadConstructor(results)
                thread_struct, _authors = await server.runners.run(threads.construct)
                for (
                    thread
                ) in (
                    thread_struct
                ):  # Make a list item for each thread (not for each email)
                    author = "Unknown"
                    date = "Unknown"
                    count = count_replies(thread)
                    # Find the email in the results pile and grab author and date
                    for k in results:
                        if k["id"] == thread["tid"]:
                            author = html.escape(k["from"])
                            date = html.escape(k["date"])
                            break
                    output += f"""- <a href="?thread={thread["tid"]}">{thread["subject"]}</a> - posted by {author} on {date} UTC, {count} replies.<br/>\n"""
            # No month specified, which means just show all months with email in 'em
            else:
                title = list_id
                canonical_link = f"/list.html?{list_id}"
                output = f"""<link rel="canonical" href="/list.html?{list_id}" />\n"""
                query_defuzzed_nodate = plugins.defuzzer.defuzz(mydata, nodate=True)
                (
                    _oldest,
                    _youngest,
                    active_months,
                ) = await plugins.messages.get_activity_span(
                    session, query_defuzzed_nodate
                )
                for month, _activity in active_months.items():
                    output += (
                        f"""<a href="?list={list_id}&date={month}">{month}</a><br/>"""
                    )
    else:  # Just list all lists?
        canonical_link = "/"
        output = """<link rel="canonical" href="/" />\n"""
        # Sort by domain, then by list name
        for ml in sorted(server.data.lists.keys(), key=lambda x: x.split("@", 1)[-1] + "-" + x.split("@", 1)[0]):
            entry = server.data.lists[ml]
            if "@" in ml:
                if not entry.get("private", True):  # Only index public lists
                    output += f"<a href='?list={ml}'>{ml}</a><br/>\n"

    if output and canonical_link:
        output_interpolated = f"""
        <html>
            <head>
                <link rel="canonical" href="{canonical_link}" />
                <title>{title}</title>
            </head>
            <body>
                <i>You are viewing a plain text version of this content. The canonical link for it is <a href="{canonical_link}">here</a>.</i><hr/>
                {output}
            </body>
        </html>        
        """
        return aiohttp.web.Response(
            headers={"Content-Type": "text/html; charset=utf-8"},
            status=200,
            text=output_interpolated,
        )
    else:
        return aiohttp.web.Response(
            headers={"Content-Type": "text/plain"},
            status=200,
            text="No data",
        )


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process, token_allowed=True)
