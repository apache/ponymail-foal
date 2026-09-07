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
This is the mbox library for Pony Mail.
It handles fetching (the right) emails for
pages that need it.
"""


import base64
import binascii
import datetime
import email.utils
import functools
import hashlib

# Main imports
import re
import typing


import plugins.aaa
import plugins.session
import plugins.database
import plugins.configuration

PYPONY_RE_PREFIX = re.compile(r"^([a-zA-Z]+:\s*)+")  # Prefixes on subjects, such as Re: Fwd:, etc.
DATABASE_NOT_CONNECTED = "Database not connected!"
OLD_SHORTENED_ID_LENGTH = 18  # Thread IDs of 18 char length (deprecated) need special care in searches
NEEDS_QUOTES = re.compile(r'[][\\()<>@,:;".]')  # If these characters are present in an email display name, quote it
ESCAPES_RE = re.compile(r'[\\"]')  # Characters to escape with backslash in make_address()

mbox_cache_privacy: typing.Dict[str, bool] = {}

# This is used to detect if the '...' truncation marker is to be added
SHORT_BODY_MAX_LEN = 200  # This must be the same as Archiver.SHORT_BODY_MAXLEN

# Social stats: the terms that count as an upvote are configurable (ui.social_terms
# in ponymail.yaml, default ["+1"]). Terms may start or end with a non-word
# character, as the default "+1" does, so whole-word matching cannot rely on \b;
# these lookarounds reject a term glued to a word character, a plus or a dash
# instead, so "+1" matches in "+1 from me" but not in "+10" or "++1".
SOCIAL_TERM_RE = r"(?<![\w+-])(?:%s)(?![\w+-])"

# Only these fields are returned by the API:
# (keep this list sorted)
USED_UI_FIELDS = [
    "attachments",
    "body",
    "children",
    "epoch",
    "from",
    "gravatar",
    "id",
    "in-reply-to",
    "list_raw",
    "list",
    "message-id",
    "mid",
    "private",
    "social_upvotes",
    "subject",
]
# The following fields are currently excluded:
# cc, date, dbid, forum, html_source_only, from_raw, permalinks, references, size, to
# The body_short contents may replace the body contents, but it is not returned separately

# must always fetch private and deleted
# list_raw is needed for authentication
MUST_HAVE = [ 'private', 'deleted', 'list_raw']


def trim_email(doc: dict, external: bool = False) -> None:
    """Trims away document fields not used by the UI"""
    for header in list(doc.keys()):
        # Remove meta data fields which start with an underscore
        if header.startswith("_"):
            del doc[header]

        # Remove other fields not used by the UI, if for external consumption
        elif external and header not in USED_UI_FIELDS:
            del doc[header]


# Format an email address given a name (optional) and an email address.
# Same as email.utils.formataddr except no Unicode escaping happens.
def make_address(name: str, mailaddress: str) -> str:
    if name and mailaddress:
        quotes = ''
        if NEEDS_QUOTES.search(name):
            quotes = '"'
        name = ESCAPES_RE.sub(r'\\\g<0>', name)
        return f'{quotes}{name}{quotes} <{mailaddress}>'
    elif mailaddress:
        return mailaddress
    else:
        return ""


# anonymise a string of email entries
def anonymize_mail_address(emailstring: str) -> str:
    out = []
    if not emailstring:
        return ""
    # split the email list into individual entries
    for real, addr in email.utils.getaddresses([emailstring]):
        # generate the anonymised entries
        anon = re.sub(r"(\S{1,2})\S*@([-a-zA-Z0-9_.]+)", "\\1...@\\2", addr)
        out.append(make_address(real, anon))

    # rejoin one per line
    return ",\n ".join(out)

def anonymize(doc: dict) -> dict:
    """ Anonymizes an email, hiding author email addresses."""
    # ES direct hit?
    ptr: typing.Dict[str, str] = doc
    if "_source" in doc:
        ptr = doc["_source"]

    if "from" in ptr:
        ptr["from"] = anonymize_mail_address(ptr["from"])
    if "to" in ptr:
        ptr["to"] = anonymize_mail_address(ptr["to"])
    if "cc" in ptr:
        ptr["cc"] = anonymize_mail_address(ptr["cc"])
    if "body" in ptr and ptr["body"]:
        ptr["body"] = re.sub(
            r"<(\S{1,2})\S*@([-a-zA-Z0-9_.]+)>", "<\\1...@\\2>", ptr["body"]
        )
    return doc


async def find_parent(session, doc: typing.Dict[str, str]):
    """
    Locates the first email in a thread by going back through all the
    in-reply-to headers and finding their ancestor.
    """
    step = 0
    # max 50 steps up in the hierarchy
    while step < 50:
        step = step + 1
        irt: typing.Optional[str] = doc["in-reply-to"] if "in-reply-to" in doc else None
        if not irt:
            break  # Shouldn't happen because irt is always present currently
        # Extract the reference, if any
        m = re.search(r"(<[^>]+>)", irt)
        if not m:
            break
        ref = m.group(1)
        newdoc = await get_email(session, messageid=ref)
        # Did we find something accessible?
        if not newdoc:
            break
        doc = newdoc
    return doc


async def fetch_children(session: plugins.session.SessionObject,
        pdoc: dict,
        counter: int = 0,
        pdocs: typing.Optional[dict] = None,
        short: bool = False) -> typing.Tuple[list,list,dict]:
    """
    Fetches all accessible child messages of a parent email
    """
    if pdocs is None:
        pdocs = {}
    counter = counter + 1
    if counter > 250:
        return [], [], {}
    docs: typing.List[dict] = await get_email_irt(session, pdoc["message-id"])

    thread = []
    emails = []
    for doc in docs:
        if doc["mid"] not in pdocs:
            mykids, _myemails, pdocs = await fetch_children(
                session, doc, counter, pdocs, short=short
            )
            if short:
                xdoc = {
                    "tid": doc["mid"],
                    "mid": doc["mid"],
                    "message-id": doc["message-id"],
                    "subject": doc["subject"],
                    "from": doc["from"],
                    "id": doc["mid"],
                    "epoch": doc["epoch"],
                    "children": mykids,
                    "irt": doc["in-reply-to"],
                    "list_raw": doc["list_raw"],
                }
                thread.append(xdoc)
                pdocs[doc["mid"]] = xdoc
            else:
                thread.append(doc)
                pdocs[doc["mid"]] = doc
            for kid in mykids:
                if kid["mid"] not in pdocs:
                    pdocs[kid["mid"]] = kid
                    emails.append(kid)
    return thread, emails, pdocs


async def get_email(
    session: plugins.session.SessionObject,
    permalink: typing.Optional[str] = None,
    messageid: typing.Optional[str] = None,
    listid: typing.Optional[str] = None,
) -> typing.Optional[dict]:
    """
    Returns a single matching mbox document or None
    """
    assert session.database, DATABASE_NOT_CONNECTED
    doctype = session.database.dbs.db_mbox
    doc = None
    if permalink:
        try:
            doc = await session.database.get(index=doctype, id=permalink)
        # Email not found through primary ID, look for other permalinks?
        except plugins.database.DBError:
            # If using old shortened hex IDs, regexp for them instead of a direct match
            if len(permalink) == OLD_SHORTENED_ID_LENGTH and re.match(r"^[a-f0-9]+$", permalink):
                permalink += ".+"
                matchtype = "regexp"
            else:
                matchtype = "term"
            res = await session.database.search(
                index=doctype,
                size=1,
                body={
                    "query": {"bool": {"must": [{matchtype: {"permalinks": permalink}}]}}
                },
            )
            if len(res["hits"]["hits"]) == 1:
                doc = res["hits"]["hits"][0]
    elif messageid:
        bquery = {"query": {"bool": {"must": [{"term": {"message-id": messageid}}]}}}
        if listid:  # Specific List ID required?
            bquery = {"query": {"bool": {"must": [{"term": {"message-id": messageid}}, {"term": {"list_raw": listid}}]}}}
        res = await session.database.search(
            index=doctype,
            size=1,
            body=bquery,
        )
        if len(res["hits"]["hits"]) == 1:
            doc = res["hits"]["hits"][0]

    # Did we find a single doc?
    if doc and isinstance(doc, dict):
        doc = doc["_source"]
        doc["id"] = doc["mid"]
        # If deleted by UI, only return if session is admin
        is_admin = session.credentials and session.credentials.admin
        if doc.get("deleted", False) and not is_admin:
            return None
        if doc and plugins.aaa.can_access_email(session, doc):
            trim_email(doc)
            if not session.credentials:
                doc = anonymize(doc)
            return doc

    # no doc?
    return None

async def get_email_irt(
    session: plugins.session.SessionObject,
    irt: str,
) -> typing.List[dict]:
    """
    Returns a list of mbox document(s) that are related,
    i.e. where the parameter matches 'in-reply-to' or 'references'
    May be empty.
    Docs have been checked for accessibility.
    """
    assert session.database, DATABASE_NOT_CONNECTED
    doctype = session.database.dbs.db_mbox

    xirt = '"%s"' % irt.replace('"', '\\"')
    res = await session.database.search(
        index=doctype,
        size=250,
        body={"query": {"bool": {"must": [ {"simple_query_string": { "query": xirt, "fields":["in-reply-to", "references"]}}]}}},
    )
    docs = res["hits"]["hits"]

    is_admin = session.credentials and session.credentials.admin
    docs_returned = []
    for doc in docs:
        doc = doc["_source"]
        doc["id"] = doc["mid"]
        if doc.get("deleted", False) and not is_admin:
            continue
        if doc and plugins.aaa.can_access_email(session, doc):
            trim_email(doc)
            if not session.credentials:
                doc = anonymize(doc)
            docs_returned.append(doc)
    return docs_returned


async def get_source(session: plugins.session.SessionObject, permalink: str, raw=False):
    """
        Get the source document for an email, or None
    """
    assert session.database, DATABASE_NOT_CONNECTED
    try:
        doc = await session.database.get(index=session.database.dbs.db_source, id=permalink)
    except plugins.database.DBError:
        doc = None
    if doc:
        # If hidden, only return source if session is admin
        is_admin = session.credentials and session.credentials.admin
        if doc["_source"].get("deleted", False) and not is_admin:
            return None
        if raw:
            return doc
        # Check for base64-encoded source
        if ":" not in doc["_source"]["source"]:
            try:
                doc["_source"]["source"] = base64.standard_b64decode(
                    doc["_source"]["source"]
                ).decode("utf-8", "replace")
            except binascii.Error:
                pass  # If it wasn't base64 after all, just return as is
        return doc
    return None


@functools.lru_cache(maxsize=8)
def social_term_regex(terms: typing.Tuple[str, ...]) -> typing.Optional[typing.Pattern]:
    """Compiles the configured upvote terms into a single alternation regex, or
    returns None if no terms are configured (feature disabled). The result is
    cached, as the term list only changes when the server is reconfigured."""
    if not terms:
        return None
    # Longest terms first, so the most specific alternative is tried first
    alternation = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    return re.compile(SOCIAL_TERM_RE % alternation, re.IGNORECASE)


def social_upvotes(body: typing.Optional[str], term_regex: typing.Pattern) -> int:
    """
    Returns 1 if one of the configured upvote terms occurs as a whole word in an
    email body, otherwise 0. Matches inside quoted text (a line whose first
    non-blank character is '>') do not count, as they are someone else's words.
    Most bodies hold no match at all, so the regex does the scanning and only
    the (rare) matches are checked for quoting.
    """
    if not body:
        return 0
    for match in term_regex.finditer(body):
        start = match.start()
        # Back up to the start of the line the match is on, then skip past any
        # indentation; a '>' at that point means we are inside quoted text.
        offset = body.rfind("\n", 0, start) + 1
        while offset < start and body[offset] in " \t":
            offset += 1
        if offset < start and body[offset] == ">":
            continue
        return 1
    return 0


async def query_batch(
        session: plugins.session.SessionObject,
        query_defuzzed: dict,
        metadata_only: bool = False,
        epoch_order: str = "desc",
        source_fields: typing.Optional[typing.List[str]] = None,
        social_stats: bool = False
):
    """
    Advanced query and grab for stats.py
    Also called by mbox.py (using metadata_only=True)
    Yields batches of scan results, filtered to remove inaccessible mails
    If social_stats is set, each doc gets a 'social_upvotes' key (see
    social_upvotes()). The scan needs body text, so callers passing source_fields
    must ask for 'body' (scans the entire email) or 'body_short' (limits the scan
    to the teaser the archiver stored, SHORT_BODY_MAX_LEN+1 characters).
    """
    assert session.database, DATABASE_NOT_CONNECTED
    preserve_order = True if epoch_order == "asc" else False
    es_query = {
        "query": {"bool": query_defuzzed},
        "sort": [{"epoch": {"order": epoch_order}}],
    }
    if metadata_only:  # Only doc IDs and AAA fields.
        es_query["_source"] = ["deleted", "private", "mid", "dbid", "list_raw"]
    elif source_fields is not None:
        temp = source_fields.copy()
        for hdr in MUST_HAVE:
            if hdr not in source_fields:
                temp.append(hdr)
        es_query["_source"] = temp
    else:
        es_query["_source"] = { "excludes": ["body"] }
    # Upvote scanning is opt-in per query, and only runs if terms are configured
    term_regex = social_term_regex(tuple(plugins.configuration.ui.social_terms)) if social_stats else None
    async for hits in session.database.scan(
            query=es_query,
            preserve_order=preserve_order
    ):
        is_admin = session.credentials and session.credentials.admin
        docs = []
        for hit in hits:
            doc = hit["_source"]
            # If email was delete/hidden and we're not doing an admin query, ignore it
            if doc.get("deleted", False) and not is_admin:
                continue
            if plugins.aaa.can_access_email(session, doc):
                if "mid" in doc: # might be missing when using source_fields
                    doc["id"] = doc["mid"]
                # Calculate gravatars if not present in _source
                if not metadata_only and source_fields is None and "gravatar" not in doc:
                    doc["gravatar"] = gravatar(doc)
                if term_regex is not None:
                    # Scan the body as stored, before truncation below trims it
                    doc["social_upvotes"] = social_upvotes(doc.get("body") or doc.get("body_short"), term_regex)
                if not session.credentials:
                    doc = anonymize(doc)
                if "body_short" in doc:
                    # The body_short field is set to SHORT_BODY_MAX_LEN+1 if the body is longer
                    # than SHORT_BODY_MAX_LEN, so we know if it has been truncated
                    if len(doc["body_short"] or "") > SHORT_BODY_MAX_LEN:
                        doc["body"] = doc["body_short"][:SHORT_BODY_MAX_LEN] + '...'
                    else:
                        doc["body"] = doc["body_short"]
                    # stats.py is expecting doc['body'], not body_short
                    del doc["body_short"]
                trim_email(doc)
                # drop any added fields
                if source_fields is not None:
                    for hdr in MUST_HAVE:
                        if hdr not in source_fields and hdr in doc:
                            del doc[hdr]
                docs.append(doc)
        if len(docs) > 0:
            yield docs


async def query(
        session: plugins.session.SessionObject,
        query_defuzzed: dict,
        query_limit: int,
        metadata_only: bool = False,
        epoch_order: str = "desc",
        source_fields: typing.Optional[typing.List[str]] = None,
        social_stats: bool = False
) -> typing.List[dict]:
    """
    Advanced query and grab for stats.py
    Also called by mbox.py (using metadata_only=True)
    """
    docs = []
    hits = 0
    async for batch in query_batch(
            session,
            query_defuzzed,
            metadata_only=metadata_only,
            epoch_order=epoch_order,
            source_fields=source_fields,
            social_stats=social_stats
    ):
        for doc in batch:
            docs.append(doc)
            hits += 1
            if hits > query_limit:
                break
        if hits > query_limit:
            break
    return docs


async def wordcloud(session: plugins.session.SessionObject, query_defuzzed: dict) -> dict:
    """
    Wordclouds via significant terms query in ES
    The query must include a private mail filter if necessary
    """
    # Filter out common stopwords and email-specific noise from the word cloud.
    # OpenSearch's significant_terms can still surface these because on mailing
    # lists, terms like "re" (from Re: subjects) are statistically frequent in
    # both foreground and background sets.
    STOPWORDS = frozenset({
        # English stopwords
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
        "if", "in", "into", "is", "it", "no", "not", "of", "on", "or",
        "such", "that", "the", "their", "then", "there", "these", "they",
        "this", "to", "was", "will", "with", "from", "has", "have", "had",
        "been", "would", "could", "should", "do", "does", "did", "can",
        "may", "might", "shall", "we", "you", "he", "she", "its", "our",
        "your", "my", "me", "him", "her", "us", "them", "who", "what",
        "which", "when", "where", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "any", "only", "own",
        "same", "so", "than", "too", "very", "just", "about", "above",
        "after", "again", "also", "because", "before", "between", "down",
        "during", "here", "new", "now", "off", "old", "one", "out",
        "over", "still", "under", "up", "well",
        # Email-specific junk (Re:, Fwd:, Fw:, Aw: prefixes after tokenization)
        "re", "fwd", "fw", "aw",
    })
    wc = {}
    try:

        assert session.database, DATABASE_NOT_CONNECTED
        res = await session.database.search(
            body={
                "size": 0,
                "query": {"bool": query_defuzzed},
                "aggregations": {
                    "cloud": {"significant_terms": {"field": "subject", "size": 10}}
                },
            }
        )

        for hit in res["aggregations"]["cloud"]["buckets"]:
            term = hit["key"]
            if term not in STOPWORDS and len(term) > 2:
                wc[term] = hit["doc_count"]

    except plugins.database.Timeout:  # If we time out, just return empty WC.
        pass
    return wc

async def get_accessible_filter(session: plugins.session.SessionObject, query_defuzzed: dict) -> typing.Optional[list]:
    """
    Return a filter to be applied to the query to exclude inaccessible mails.
    If no filter is needed, return None
    e.g. 
    query_filter = get_accessible_filter(session, query)
    if query_filter:
        query['filter'] = query_filter
    """
    if not session.credentials:
        # if no credentials, only need to search public mails
        return [{"term": {"private": False}}]
    # which private lists might be involved in the search?
    fuzz_private_only = dict(query_defuzzed)
    fuzz_private_only["filter"] = [{"term": {"private": True}}]
    assert session.database, DATABASE_NOT_CONNECTED
    max_lists = session.database.config.max_lists
    res = await session.database.search(
        index=session.database.dbs.db_mbox,
        size=0,
        body={
            "query": {"bool": fuzz_private_only},
            "aggs": {"listnames": {"terms": {"field": "list_raw", "size": max_lists}}},
        },
    )
    private_lists_found = []
    for entry in res["aggregations"]["listnames"]["buckets"]:
        listname = entry["key"].lower()
        private_lists_found.append(listname)

    # If we can access all private lists found, or if no private lists, we can do a complete search.
    # If not, we adjust the search here to only include public emails OR private lists we can access.
    private_lists_accessible = []
    for listname in private_lists_found:
        if plugins.aaa.can_access_list(session, listname):
            private_lists_accessible.append(listname)
    
    # If we can't access all private lists found, either only public emails or lists we can access.
    if not private_lists_accessible:  # No private lists accessible, just filter for public
        return [{"term": {"private": False}}]
    elif private_lists_found != private_lists_accessible:  # Some private lists, search for public OR those..
        return [
            {"bool": {"should": [{"term": {"private": False}}, {"terms": {"list_raw": private_lists_accessible}}]}}
        ]

    return None


async def get_activity_span(session: plugins.session.SessionObject, query_defuzzed: dict) -> typing.Tuple[datetime.datetime, datetime.datetime, dict]:
    """
    Fetches the activity span of a search as well as active months within that span
    The query must include a private filter if necessary
    """

    # Get oldest and youngest doc in single scan, as well as a monthly histogram
    assert session.database, DATABASE_NOT_CONNECTED
    res = await session.database.search(
        index=session.database.dbs.db_mbox,
        size=0,
        body={"query": {"bool": query_defuzzed},
            "aggs": {
                "first": {"min": {"field": "epoch"}},
                "last": {"max": {"field": "epoch"}},
                "active_months": {
                    "date_histogram": {
                        "field": "date",
                        "calendar_interval": "month",
                        "format": "yyyy-MM"
                    }
                }
            },
        }
    )

    oldest = datetime.datetime.fromtimestamp(0)
    youngest = datetime.datetime.fromtimestamp(0)
    monthly_activity = {}
    if res["aggregations"]:
        aggs = res["aggregations"]
        oldest = datetime.datetime.fromtimestamp(aggs["first"]["value"] or 0)
        youngest = datetime.datetime.fromtimestamp(aggs["last"]["value"] or 0)
        for bucket in aggs["active_months"].get("buckets", []):
            if bucket["doc_count"]:
                monthly_activity[bucket["key_as_string"]] = bucket["doc_count"]

    return oldest, youngest, monthly_activity


class ThreadConstructor:
    def __init__(self, emails: typing.List[typing.Dict]):
        self.emails = emails
        self.threads: typing.List[dict] = []
        # this now includes the gravatar, to avoid issues with address anonymisation
        self.authors: typing.Dict[str, list] = {}
        self.hashed_by_msg_id: typing.Dict[str, dict] = {}
        self.hashed_by_subject: typing.Dict[str, dict] = {}

    def construct(self):
        """Turns a flat array of emails into a nested structure of threads"""
        for cur_email in sorted(self.emails, key=lambda x: x["epoch"]):
            author = cur_email.get("from")
            assert(author)
            if author not in self.authors:
                self.authors[author] = [0, cur_email.get("gravatar", "")]
            self.authors[author][0] += 1
            subject = cur_email.get("subject", "").replace(
                "\n", ""
            )  # Crop multi-line subjects
            tsubject = (
                PYPONY_RE_PREFIX.sub("", subject)
                + "_"
                + cur_email.get("list_raw", "<a.b.c.d>")
            )
            parent = self.find_root_subject(cur_email, tsubject)
            xemail = {
                "children": [],
                "tid": cur_email.get("mid"),
                "subject": subject,
                "tsubject": tsubject,
                "epoch": cur_email.get("epoch"),
                "nest": 1,
            }
            if not parent:
                self.threads.append(xemail)
            else:
                xemail["nest"] = parent["nest"] + 1
                parent["children"].append(xemail)
            self.hashed_by_msg_id[cur_email.get("message-id", "??")] = xemail
            if tsubject not in self.hashed_by_subject:
                self.hashed_by_subject[tsubject] = xemail
        return self.threads, self.authors

    
    def find_root_subject(self, root_email: typing.Dict[str, str], osubject: typing.Optional[str] = None) -> typing.Optional[dict]:
        """Finds the discussion origin of an email, if present"""
        irt = root_email.get("in-reply-to",'')
        subject = root_email.get("subject",'')
        subject = subject.replace("\n", "").strip()  # Crop multi-line subjects and surrounding whitespace
        subject = PYPONY_RE_PREFIX.sub("", subject) + "_" + root_email.get("list_raw",'')

        # First, the obvious - look for an in-reply-to in our existing dict with a matching subject
        if irt and irt in self.hashed_by_msg_id:
            if self.hashed_by_msg_id[irt].get("subject") == subject:
                return self.hashed_by_msg_id[irt]

        # If that failed, we break apart our subject
        if osubject:
            rsubject = osubject
        else:
            rsubject = subject
        if rsubject and rsubject in self.hashed_by_subject:
            return self.hashed_by_subject[rsubject]
        return None



def gravatar(eml: typing.Union[str, dict]) -> str:
    """Generates a gravatar hash from an email address"""
    if isinstance(eml, str):
        header_from = eml
    else:
        header_from = eml.get("from", "??")
    mailaddr = email.utils.parseaddr(header_from)[1]
    ghash = hashlib.md5(mailaddr.encode("utf-8")).hexdigest()
    return ghash
