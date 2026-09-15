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

""" Publish notifications about mails to pony mail.

Copy this file to $mailman_plugin_dir/mailman_ponymail/__init__.py
Also copy ponymail.cfg to that dir.
Enable the module by adding the following to your mailman.cfg file::

[archiver.ponymail]
# The class implementing the IArchiver interface.
class: mailman_ponymail_plugin.Archiver
enable: yes

and by adding the following to archiver.yaml:

[mailman]
plugin: true

OR, to use the STDIN version (non-MM3 mailing list managers),
sub someone to the list(s) and add this to their .forward file:
"|/usr/bin/env python3 /path/to/archiver.py"

"""

import argparse
import base64
import collections
import email.header
import email.utils
import email.policy
import email.headerregistry
import fnmatch
import hashlib
import json
import logging
import os
import re
import sys
import time
import traceback
import typing
import uuid
import mimetypes

import elasticsearch
import formatflowed
import netaddr

if not __package__:
    from plugins import ponymailconfig # pylint: disable=no-name-in-module
    from plugins import generators, textlib # pylint: disable=no-name-in-module
    from plugins.elastic import Elastic # pylint: disable=no-name-in-module
else:
    from .plugins import ponymailconfig # pylint: disable=no-name-in-module
    from .plugins import generators, textlib # pylint: disable=no-name-in-module
    from .plugins.elastic import Elastic # pylint: disable=no-name-in-module

# This is what we will default to if we are presented with emails without character sets and US-ASCII doesn't work.
DEFAULT_CHARACTER_SET = 'utf-8'

# Standard "short body" max length for email aggregations
SHORT_BODY_MAX_LEN = 200 # This must be the same as server.plugins.messages.SHORT_BODY_MAX_LEN

# Fetch config from same dir as archiver.py
config = ponymailconfig.PonymailConfig()

# Set some vars before we begin
logger = None

normalize_lid = textlib.normalize_lid  # Unit test fallback

# If MailMan is enabled, import and set it up
if config.has_option("mailman", "plugin"):
    from mailman.interfaces.archiver import ArchivePolicy, IArchiver
    from zope.interface import implementer

    logger = logging.getLogger("mailman.archiver")

# Access URL once archived
aURL = config.get("archiver", "baseurl")

# Get/Set email parsing policy (primarily ascii/7bit vs native utf8)
# (used by import-mbox)
policy_choice = config.get("archiver", "policy", fallback="default")
policy: typing.Any
if policy_choice == "compat32":
    policy = email.policy.compat32   # 7bit lines
else:
    if policy_choice == "smtputf8":
        policy = email.policy.SMTPUTF8.clone()   # 8bit/unicode lines
    else:
        policy = email.policy.default.clone()    # Default (8bit) lines in Python >=3.3
    # email parsing is currently too strict; override the classes
    policy.header_factory.map_to_type('references', email.headerregistry.UnstructuredHeader)
    policy.header_factory.map_to_type('message-id', email.headerregistry.UnstructuredHeader)


def encode_base64(buff: bytes) -> str:
    """ Convert bytes to base64 as text string (no newlines) """
    return base64.standard_b64encode(buff).decode("ascii", "ignore")


def mbox_source(b: bytes) -> str:
    # Common method shared with import-mbox
    try:
        # Can we store as ASCII?
        return b.decode("ascii", errors="strict")
    except UnicodeError:
        # No, so must use base64 to avoid corruption on re-encoding
        return encode_base64(b)

# Common method shared with import-mbox to ensure consistency
def parse_message(raw_message):
    return email.message_from_bytes(raw_message, policy=policy)

def parse_attachment(
    part: email.message.Message,
) -> typing.Tuple[typing.Optional[dict], typing.Optional[str]]:
    """
    Parses an attachment in an email, turns it into a dict with a content-type, sha256 digest, file size and file name.
    Also returns the attachment contents as base64 encoded string.
    :param part: The message part to parse
    :return: attachment info and contents as b64 string
    """
    cd = part.get("Content-Disposition", None)
    if cd:
        # Use str() in case the name is not in ASCII.
        # In such cases, the get() method returns a Header not a string
        dispositions = str(cd).strip().split(";")
        cdtype = dispositions[0].lower()
        if cdtype in {"attachment", "inline"}:
            fd = part.get_payload(decode=True)
            filename = part.get_filename()
            # If attachment is without a name, invent it.
            ctype = part.get_content_type()
            if ctype and not filename:
                ext = mimetypes.guess_extension(ctype)
                if not ext:  # dunno this extension, fake .txt
                    ext = ".txt"
                filename = f"{cdtype}{ext}"
                if not fd and cdtype == "inline":  # If inline, convert to source
                    fd = part.as_bytes()
            # Allow for empty string
            if fd is None:
                return None, None
            assert(isinstance(fd, bytes)) # decode=True generates bytes
            if filename:
                attachment = {
                    "content_type": part.get_content_type(),
                    "size": len(fd),
                    "filename": filename,
                }
                h = hashlib.sha256(fd).hexdigest()
                b64 = encode_base64(fd)
                attachment["hash"] = h
                return attachment, b64  # Return meta data and contents separately
    return None, None


def message_attachments(msg: email.message.Message) -> typing.Tuple[list, dict]:
    """
    Parses an email and returns all attachments found as a tuple of metadata and contents
    :param msg: The email to parse
    :return: a tuple of attachment metadata and their content
    """
    attachments = []
    contents = {}
    for part in msg.walk():
        part_meta, part_file = parse_attachment(part)
        if part_meta:
            attachments.append(part_meta)
            contents[part_meta["hash"]] = part_file
    return attachments, contents


class Body:
    def __init__(self, part: email.message.Message):
        self.content_type = part.get_content_type()
        self.charsets = [part.get_content_charset()]  # Part's charset
        parent_charset = part.get_charsets()[0] # type: ignore [index] # (awaiting typedef fix)
        if parent_charset and parent_charset != self.charsets[0]:
            self.charsets.append(
                parent_charset
            )  # Parent charset as fallback if any/different
        self.character_set = None
        self.string: typing.Optional[str] = None
        self.flowed = "format=flowed" in part.get("content-type", "")
        self.bytes = part.get_payload(decode=True)
        self.html_as_source = False
        if self.bytes is not None:
            assert(isinstance(self.bytes, bytes)) # decode=True generates bytes
            valid_encodings = [x for x in self.charsets if x]
            if valid_encodings:
                for cs in valid_encodings:
                    try:
                        self.string = self.bytes.decode(cs)
                        self.character_set = str(cs)
                        break
                    except UnicodeDecodeError:
                        pass
                    except LookupError:
                        print("Body detected invalid encoding: %s" % cs)
            # If no character set was defined, the email MUST be US-ASCII by RFC822 defaults
            # This isn't always the case, as we're about to discover.
            if not self.string:
                try:
                    self.string = self.bytes.decode("us-ascii", errors="strict")
                    if valid_encodings:
                        self.character_set = "us-ascii"
                except UnicodeDecodeError:
                    # If us-ascii strict fails, it's probably undeclared UTF-8 (it happens!).
                    # Set the .string, but not a character set, as we don't know it for sure.
                    # This is mainly so the older generators won't barf, as the generator will
                    # be fed the message body as a bytes object if no encoding is set, while
                    # the resulting metadoc will always use the string version.
                    self.string = self.bytes.decode(DEFAULT_CHARACTER_SET, "replace")

    def __repr__(self):
        return self.string

    def __len__(self):
        return len(self.string or "")

    def assign(self, new_string):
        self.string = new_string

    def encode(self, encoding=DEFAULT_CHARACTER_SET, errors="strict"):
        return self.string.encode(encoding=encoding, errors=errors)

    def unflow(self, convert_lf=False):
        """Unflows text of type format=flowed.
           By default, lines ending in LF (mbox imports) are not converted to CRLF, and thus
           not unflowed. This is to be consistent with previous versions of Pony Mail, and
           can be enabled for any new installations that that not reimaging their database.
           """
        if self.string:
            if self.flowed:
                # Use provider character set or fall back to our sane default.
                character_set = self.character_set or DEFAULT_CHARACTER_SET
                # Convert lone LF to CRLF if found
                conversion_was_needed = None # avoid pylint warning
                if convert_lf:
                    fixed_string = "\r\n".join(
                        [x.rstrip("\r") for x in self.string.split("\n")]
                    )
                    conversion_was_needed = fixed_string != self.string
                else:
                    fixed_string = self.string
                flow_fixed = formatflowed.convertToWrapped(
                    fixed_string.encode(character_set, errors="ignore"),
                    wrap_fixed=False,
                    character_set=character_set,
                )
                # If we "upconverted" from LF to CRLF, convert back after flow decoding
                if convert_lf and conversion_was_needed:
                    flow_fixed = "\n".join(
                        [x.rstrip("\r") for x in self.string.split("\n")]
                    )
                return flow_fixed
        return self.string


def message_identifiers(header, reverse=False):
    if "<" not in header:
        return []
    parts = header.split("<")
    identifier_junks = parts[1:]
    identifiers = []
    for identifier_junk in identifier_junks:
        identifier = identifier_junk.split(">").pop(0)
        identifiers.append("<" + identifier + ">")
    if reverse is True:
        identifiers = list(reversed(identifiers))
    return identifiers


def get_parent_identifiers(ojson):
    identifiers = []
    mirt = ojson.get("in-reply-to", "")
    for irt in message_identifiers(mirt, reverse=True):
        identifiers.append(irt)
    mref = ojson.get("references", "")
    for ref in message_identifiers(mref, reverse=True):
        identifiers.append(ref)
    return identifiers


def get_by_message_id(elastic, msgid, timeout="5s"):
    data = elastic.search(index=elastic.db_mbox, body={
        "query": {
            "bool": {
                "must": {"term": {"message-id": msgid}}
            }
        }
    }, timeout=timeout)
    if data["hits"]["total"]["value"] == 1:
        return data["hits"]["hits"][0]["_source"]
    return None


def get_parent_info(elastic, ojson, timeout=5, limit=10):
    parent_identifiers = get_parent_identifiers(ojson)
    if not parent_identifiers:
        return None
    for parent_identifier in parent_identifiers:
        parent_info = get_by_message_id(elastic, parent_identifier, timeout)
        if parent_info is not None:
            return parent_info
        limit -= 1
        if limit < 1:
            break
    return None


def get_previous_mid(elastic, ojson, timeout="5s"):
    forum = ojson["forum"]
    latest = ojson.get("epoch", 1) - 1
    data = elastic.search(index=elastic.db_mbox, body={
        "query": {
            "bool": {
                "must": [
                    {"range": {"epoch": {"lte": latest}}},
                    {"term": {"forum": forum}},
                    {"term": {"top": True}}
                ]
            }
        },
        "sort": [{"epoch": "desc"}],
        "size": 1,
        "_source": "mid",
    }, timeout=timeout)
    for hit in data["hits"]["hits"]:
        return hit["_source"]["mid"]
    return None


def add_thread_properties(elastic, ojson, timeout="5s", limit=5):
    parent_info = get_parent_info(elastic, ojson, timeout, limit)
    if parent_info is None:
        top = True
        thread = ojson["mid"]
        previous = get_previous_mid(elastic, ojson, timeout)
    else:
        top = False
        thread = parent_info.get("thread")
        previous = parent_info["mid"]

    ojson["top"] = top
    ojson["thread"] = thread
    ojson["previous"] = previous
    return ojson


class Archiver(object):  # N.B. Also used by import-mbox.py
    """The general archiver class. Compatible with MailMan3 archiver classes."""

    if config.has_option("mailman", "plugin"):
        implementer(IArchiver)
        name = "foal"

    # This is a list of headers which are stored in msg_metadata
    HDR_KEYS = [
        "archived-at",
        "from",
        "cc",
        "to",
        "date",
        "in-reply-to",
        "message-id",
        "subject",
        "references",
    ]
    # keys that need to be decoded
    HDR_KEYS_DECODE = ["to", "from", "subject", "message-id"]

    def __init__(
        self, generator=None, parse_html=False, ignore_body=None, verbose=False
    ):
        """ Just initialize ES. """
        self.html = parse_html
        # Fall back to full hashing if nothing is set.
        self.generator = generator or config.get(
            "archiver", "generator", fallback="full"
        )
        self.cropout = config.get("debug", "cropout")
        self.verbose = verbose
        self.ignore_body = ignore_body
        if self.html:
            import html2text

            self.html2text = html2text.html2text

    def message_body(self, msg: email.message.Message) -> typing.Optional[Body]:
        """
            Fetches the proper text body from an email as an archiver.Body object
        :param msg: The email or part of it to examine for proper body
        :return: archiver.Body object
        """
        body = None
        first_html = None
        last_random = None
        for part in msg.walk():
            # can be called from importer
            if self.verbose:
                print("Content-Type: %s" % part.get_content_type())
            """
                Find the first body part and the first HTML part
                Note: cannot use break here because firstHTML is needed if len(body) <= 1
            """
            try:
                if body is None and part.get_content_type() in [
                    "text/plain",
                    "text/enriched",
                ]:
                    body = Body(part)
                elif (
                    not first_html
                    and part.get_content_type() == "text/html"
                ):
                    first_html = Body(part)
                elif (
                    body is None
                ):
                    last_random = Body(part)
            except Exception as err:
                entry = sys.exc_info()[-1]
                if entry: # avoid mypy complaint
                    print('Error on line {}:'.format(entry.tb_lineno), type(err).__name__, err)
                else: # Should not happen, but just in case
                    print('Failed to create Body(part):',type(err).__name__, err)


        if last_random and not first_html and body is None:
            if bool(config.get("debug","allow_nontext_body", False)):
                print("No text or html body found, using what we have")
                body = last_random

        # this requires a GPL lib, user will have to install it themselves
        if first_html and (
            body is None
            or len(body) <= 1
            or (self.ignore_body and str(body).find(str(self.ignore_body)) != -1)
        ):
            body = first_html
            body.html_as_source = True

            # Convert HTML to text if mod is installed and enabled, otherwise keep the source as-is
            if self.html:
                body.assign(self.html2text(str(body)))
                body.html_as_source = False
        return body

    # N.B. this is also called by import-mbox.py
    def compute_updates(
        self,
        lid: typing.Optional[str],
        private: bool,
        msg: email.message.Message,
        raw_msg: bytes,
        default_epoch: typing.Union[None, str, int] = None
    ) -> typing.Tuple[typing.Optional[dict], dict, dict, typing.Optional[str], bool]:
        """Determine what needs to be sent to the archiver.
        :param lid: The list id
        :param private: Whether privately archived email or not (bool)
        :param msg: The message object
        :param raw_msg: The raw message bytes

        :return None if the message could not be parsed, otherwise a four-tuple consisting of:
                the digested email as a dict, its attachments, its metadata fields and any
                in-reply-to data found.
        """
        notes = []  # Put debug notes in here, for later...

        if not lid:
            lid = textlib.normalize_lid(msg.get("list-id"), strict=True)
            if lid is None:
                raise ValueError(f"Invalid list-id {lid} provided")
        if self.cropout:
            crops = self.cropout.split(" ")
            # Regex replace?
            if len(crops) == 2:
                lid = re.sub(crops[0], crops[1], lid)
            # Standard crop out?
            else:
                lid = lid.replace(self.cropout, "")

        def default_empty_string(value):
            return str(value) if value else ""
        msg_metadata = dict([(k, default_empty_string(msg.get(k))) for k in self.HDR_KEYS])
        mid = (
            hashlib.sha224(
                str("%s-%s" % (lid, msg_metadata["archived-at"])).encode("utf-8")
            ).hexdigest()
            + "@"
            + (lid if lid else "none")
        )
        for key in self.HDR_KEYS_DECODE:
            try:
                hval = ""
                if msg_metadata.get(key):
                    for t in email.header.decode_header(msg_metadata[key]):
                        if t[1] is None or t[1].find("8bit") != -1:
                            hval += str(
                                t[0].decode("utf-8") if type(t[0]) is bytes else t[0]
                            )
                        else:
                            hval += t[0].decode(t[1], errors="ignore")
                    msg_metadata[key] = hval.strip()
            except Exception as err:
                print("Could not decode headers, ignoring..: %s" % err)
        message_date = None
        try:
            message_date = email.utils.parsedate_tz(str(msg_metadata.get("date")))
        except ValueError:
            pass
        if not message_date and msg_metadata.get("archived-at"):
            message_date = email.utils.parsedate_tz(
                str(msg_metadata.get("archived-at"))
            )
        if not message_date:
            print("No message date could be derived from the Date: header, looking elsewhere.")
            bad_date_original = str(msg_metadata.get("date"))
            if bad_date_original:
                notes.append(["BADDATE: Original email Date: header was set to invalid value: %s" % bad_date_original])
            # See if we have a "From" header line in the raw email, we can use
            first_line = raw_msg.split(b"\n", 1)[0].decode("us-ascii")
            if first_line.startswith("From "):
                # If we have one, the date must be the third element when splitting by single space.
                env_from_date = first_line.split(" ", 2)[-1]  # Split twice, grab last element.
                message_date = email.utils.parsedate_tz(env_from_date)
                if message_date:
                    print("Found date in envelope FROM header: %s" % env_from_date)
                    notes.append(["BADDATE: Used envelope FROM header for email date: %s" % env_from_date])
            # Otherwise, look for a Received: header we can scan
            if not message_date:
                for recv_from in msg.get_all('received', []):  # We may have multiple of these, not all have "from".
                    m = re.match(r"from[^;]+?;\s+(.+?)(?:$|[\r\n])", recv_from)
                    if m:
                        message_date = email.utils.parsedate_tz(m.group(1))
                        if message_date:
                            print("Found date in Received header: %s" % m.group(1))
                            notes.append(["BADDATE: Used Received header for email date: %s" % m.group(1)])
                            break
            if not message_date:
                # Current time makes most sense for live archiving.
                # If --defaultepoch is defined, use that instead.
                if default_epoch is not None:
                    if default_epoch == "skip":  # If we are to skip emails with bad dates...
                        return {"foo": "bar"}, {}, {}, None, True  # return fake set with skipit == True
                    else:
                        print("Could not find any valid dates in email headers, using --defaultepoch parameter %s" % default_epoch)
                        epoch = int(default_epoch)
                        notes.append(["BADDATE: Falling back to default epoch specified by --defaultepoch: %s" % default_epoch])
                else:
                    print("Could not find any valid dates in email headers, using current time")
                    notes.append(["BADDATE: Falling back to default UNIX epoch"])
                    epoch = int(time.time())
            else:
                epoch = int(email.utils.mktime_tz(message_date))
        else:
            epoch = int(email.utils.mktime_tz(message_date))
        # message_date calculations are all done, prepare the index entry
        date_as_string = time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime(epoch))
        body = self.message_body(msg)
        attachments, contents = message_attachments(msg)
        irt = ""

        output_json = None
        if body is not None or attachments:
            pmid = mid
            id_set = list()
            # The body used for generators differ from the body put into the meta doc,
            # for historical reasons. In the older generators where it is actively used,
            # it would be UTF-8 bytes in cases of charset-less message bodies. It would
            # also be nothing in case of html-only emails where html2text is not enabled.
            generator_body = body if body and body.character_set else body and body.bytes or ""
            if body and body.html_as_source:
                generator_body = ""
            for generator in self.generator.split(" "):
                if generator:
                    try:
                        mid = generators.generate(
                            generator,
                            msg,
                            generator_body,
                            lid,
                            attachments,
                            raw_msg,
                        )
                    except Exception as err:
                        if logger:
                            # N.B. use .get just in case there is no message-id
                            logger.info(
                                "Could not generate MID: %s. MSGID: %s",
                                err,
                                msg_metadata.get("message-id", "?").strip(),
                            )
                        mid = pmid
                    if mid not in id_set:
                        id_set.append(mid)

            if "in-reply-to" in msg_metadata:
                try:
                    irt_original = msg_metadata["in-reply-to"]
                    if isinstance(irt_original, list):
                        irt = "".join(irt_original)
                    else:
                        irt = str(irt_original)
                    if irt:
                        irt = irt.strip()
                except ValueError:
                    irt = ""
            document_id = id_set[0]

            # Pre-calculate gravatar
            mailaddr = email.utils.parseaddr(msg_metadata["from"])[1]
            ghash = hashlib.md5(mailaddr.encode("utf-8")).hexdigest()

            notes.append(["ARCHIVE: Email archived as %s at %u" % (document_id, time.time())])
            body_unflowed = body.unflow() if body else ""
            body_shortened = body_unflowed[:SHORT_BODY_MAX_LEN+1]  # +1 so that we can tell if larger than std short body.

            output_json = {
                "from_raw": msg_metadata["from"],
                "from": msg_metadata["from"],
                "gravatar": ghash,
                "to": msg_metadata["to"],
                "subject": msg_metadata["subject"],
                "message-id": msg_metadata["message-id"],
                "mid": document_id,
                "permalinks": id_set,
                "dbid": hashlib.sha3_256(raw_msg).hexdigest(),
                "cc": msg_metadata.get("cc"),
                "epoch": epoch,
                "list": lid,
                "list_raw": lid,
                "date": date_as_string,
                "private": private,
                "references": msg_metadata["references"],
                "in-reply-to": irt,
                "body": body_unflowed,
                "body_short": body_shortened,
                "html_source_only": body and body.html_as_source or False,
                "attachments": attachments,
                "forum": (lid or "").strip("<>").replace(".", "@", 1),
                "size": len(raw_msg),
                "_notes": notes,
                "_archived_at": int(time.time()),
            }

        return output_json, contents, msg_metadata, irt, False

    def archive_message(self, mlist, msg, raw_message=None, dry=False, dump=None, defaultepoch=None, digest=False):
        """Send the message to the archiver.

        :param mlist: The IMailingList object.
        :param msg: The message object.
        :param raw_message: Raw message bytes
        :param dry: Whether or not to actually run
        :param dump: Optional path for dump on fail

        :return (lid, mid)
        """

        lid = textlib.normalize_lid(mlist.list_id, strict=True)
        if lid is None:
            raise ValueError(f"Invalid list id {lid}")

        private = False
        if hasattr(mlist, "archive_public") and mlist.archive_public is True:
            private = False
        elif hasattr(mlist, "archive_public") and mlist.archive_public is False:
            private = True
        elif (
            hasattr(mlist, "archive_policy")
            and mlist.archive_policy is not ArchivePolicy.public # pylint: disable=possibly-used-before-assignment
        ):
            private = True

        if raw_message is None:
            raw_message = msg.as_bytes()
        ojson, contents, msg_metadata, irt, skipit = self.compute_updates(
            lid, private, msg, raw_message, defaultepoch
        )
        if not ojson:
            _id = msg.get("message-id") or msg.get("Subject") or msg.get("Date")
            raise ValueError("Could not parse message %s for %s" % (_id, lid))
        if skipit:
            print("Skipping archiving of email due to invalid date and default date set to skip")
            return lid, "(skipped)"
        if digest:
            return lid, ojson["mid"]
        if dry:
            print("**** Dry run, not saving message to database *****")
            return lid, ojson["mid"]

        if dump:
            try:
                elastic = Elastic()
            except elasticsearch.exceptions.ElasticsearchException as e:
                print(e)
                print(
                    "ES connection failed, but dumponfail specified, dumping to %s"
                    % dump
                )
        else:
            elastic = Elastic()

        if config.get("archiver", "threadinfo"):
            try:
                timeout = int(config.get("archiver", "threadtimeout") or 5)
                timeout = str(timeout) + "s"
                limit = int(config.get("archiver", "threadparents") or 10)
                ojson = add_thread_properties(elastic, ojson, timeout, limit)
            except Exception as err:
                print("Could not add thread info", err)
                if logger:
                    logger.info("Could not add thread info %s", err)
            else:
                print("Added thread info successfully", ojson["mid"])
                if logger:
                    logger.info("Added thread info successfully %s", ojson["mid"])

        try:
            if contents:
                for key in contents:
                    elastic.index(
                        index=elastic.db_attachment,
                        id=key,
                        body={"source": contents[key]},
                    )

            elastic.index(
                index=elastic.db_mbox, id=ojson["mid"], body=ojson,
            )

            elastic.index(
                index=elastic.db_source,
                id=ojson["dbid"],
                body={
                    "message-id": msg_metadata["message-id"],
                    "source": mbox_source(raw_message),
                },
            )
            # Write to audit log
            try:
                auditlog_exists = elastic.indices.exists(index=elastic.db_auditlog)
            except elasticsearch.exceptions.AuthorizationException:
                auditlog_exists = False
            if auditlog_exists:
                elastic.index(
                    index=elastic.db_auditlog,
                    body={
                        "date": time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime(time.time())),
                        "action": "index",
                        "remote": "internal",
                        "author": "archiver.py",
                        "target": ojson["mid"],
                        "lid": lid,
                        "log": f"Indexed email {ojson['message-id']} for {lid} as {ojson['mid']}",
                    }
                )

        # If we have a dump dir and ES failed, push to dump dir instead as a JSON object
        # We'll leave it to another process to pick up the slack.
        except Exception as err:
            print('Error on line {}:'.format(sys.exc_info()[-1].tb_lineno), type(err).__name__, err)
            if dump:
                print(
                    "Pushing to ES failed, but dumponfail specified, dumping JSON docs"
                )
                uid = uuid.uuid4()
                mbox_path = os.path.join(dump, "%s.json" % uid)
                with open(mbox_path, "w") as f:
                    json.dump(
                        {
                            "id": ojson["mid"],
                            "mbox": ojson,
                            "mbox_source": {
                                "id": ojson["dbid"],
                                "permalink": ojson["mid"],
                                "message-id": msg_metadata["message-id"],
                                "source": mbox_source(raw_message),
                            },
                            "attachments": contents,
                        },
                        f,
                        indent=2,
                    )
                    f.close()
                sys.exit(0)  # We're exiting here, the rest can't be done without ES
            # otherwise fail as before
            raise err

        if logger:
            logger.info("Pony Mail archived message %s successfully", ojson["mid"])
        oldrefs = []

        # Is this a direct reply to a pony mail email?
        if irt != "":
            dm = re.search(r"pony-([a-f0-9]+)-([a-f0-9]+)@", irt)
            if dm:
                cid = dm.group(1)
                mid = dm.group(2)
                if elastic.exists(index=elastic.db_account, id=cid):
                    doc = elastic.get(index=elastic.db_account, id=cid)
                    if doc:
                        oldrefs.append(cid)
                        # N.B. no index is supplied, so ES will generate one
                        elastic.index(
                            index=elastic.db_notification,
                            body={
                                "type": "direct",
                                "recipient": cid,
                                "list": lid,
                                "private": private,
                                "date": ojson["date"],
                                "from": msg_metadata["from"],
                                "to": msg_metadata["to"],
                                "subject": msg_metadata["subject"],
                                "message-id": msg_metadata["message-id"],
                                "in-reply-to": irt,
                                "epoch": ojson["epoch"],
                                "mid": mid,
                                "seen": 0,
                            },
                        )
                        if logger:
                            logger.info("Notification sent to %s for %s", cid, mid)

        # Are there indirect replies to pony emails?
        if msg_metadata.get("references"):
            for im in re.finditer(
                r"pony-([a-f0-9]+)-([a-f0-9]+)@", msg_metadata.get("references")
            ):
                cid = im.group(1)
                mid = im.group(2)
                # TODO: Fix this to work with pibbles
                if elastic.exists(index=elastic.db_mbox, id=cid):
                    doc = elastic.get(index=elastic.db_mbox, id=cid)

                    # does the user want to be notified of indirect replies?
                    if (
                        doc
                        and "preferences" in doc["_source"]
                        and doc["_source"]["preferences"].get("notifications")
                        == "indirect"
                        and cid not in oldrefs
                    ):
                        oldrefs.append(cid)
                        # N.B. no index mapping is supplied, so ES will generate one
                        elastic.index(
                            index=elastic.db_notification,
                            body={
                                "type": "indirect",
                                "recipient": cid,
                                "list": lid,
                                "private": private,
                                "date": ojson["date"],
                                "from": msg_metadata["from"],
                                "to": msg_metadata["to"],
                                "subject": msg_metadata["subject"],
                                "message-id": msg_metadata["message-id"],
                                "in-reply-to": irt,
                                "epoch": ojson["epoch"],
                                "mid": mid,
                                "seen": 0,
                            },
                        )
                        if logger:
                            logger.info("Notification sent to %s for %s", cid, mid)
        return lid, ojson["mid"]

    def list_url(self, _mlist):
        """ Required by MM3 plugin API
        """
        return None

    def permalink(self, _mlist, _msg):
        """ Required by MM3 plugin API
        """
        return None


def main():
    parser = argparse.ArgumentParser(description="Command line options.")
    parser.add_argument(
        "--lid", dest="lid", type=str, nargs=1, help="Alternate specific list ID"
    )
    parser.add_argument(
        "--digest",
        dest="digest",
        action="store_true",
        help="Only digest the email and spit out the generated ID, do not archive",
    )
    parser.add_argument(
        "--altheader",
        dest="altheader",
        type=str,
        nargs=1,
        help="Alternate header for list ID",
    )
    parser.add_argument(
        "--allowfrom",
        dest="allowfrom",
        type=str,
        nargs=1,
        help="(optional) source IP (mail server) to allow posts from, ignore if no match",
    )
    parser.add_argument(
        "--ignore",
        dest="ignorefrom",
        type=str,
        nargs=1,
        help="Sender/list to ignore input from (owner etc)",
    )
    parser.add_argument(
        "--private",
        dest="private",
        action="store_true",
        help="This is a private archive",
    )
    parser.add_argument(
        "--makedate",
        dest="makedate",
        action="store_true",
        help="Use the archive timestamp as the email date instead of the Date header",
    )
    parser.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Do not exit -1 if the email could not be parsed",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Output additional log messages",
    )
    parser.add_argument(
        "--html2text",
        dest="html2text",
        action="store_true",
        help="Try to convert HTML to text if no text/plain message is found",
    )
    parser.add_argument(
        "--dry",
        dest="dry",
        action="store_true",
        help="Do not save emails to elasticsearch, only test parsing",
    )
    parser.add_argument(
        "--ignorebody",
        dest="ibody",
        type=str,
        nargs=1,
        help="Optional email bodies to treat as empty (in conjunction with --html2text)",
    )
    parser.add_argument(
        "--dumponfail",
        dest="dump",
        help="If pushing to ElasticSearch fails, dump documents in JSON format to this directory and "
        "fail silently.",
    )
    parser.add_argument(
        "--defaultepoch",
        dest="defaultepoch",
        help="If no date could be found in the email, use this epoch. Set to 'skip' to skip importing on bad date",
    )
    parser.add_argument("--generator", dest="generator", help="Override the generator.")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    archie = Archiver(
        generator=args.generator,
        parse_html=args.html2text,
        ignore_body=args.ibody,
        verbose=args.verbose,
    )
    # use binary input so parser can use appropriate charset
    input_stream = sys.stdin.buffer

    try:
        raw_message = input_stream.read()
        
        try:
            msg = parse_message(raw_message)
        except Exception as err:
            print("STDIN parser exception: %s" % err)
            sys.exit(-1)

        if args.altheader:
            alt_header = args.altheader[0]
            if alt_header in msg:
                try:
                    msg.replace_header("List-ID", msg.get(alt_header))
                except KeyError:
                    msg.add_header("list-id", msg.get(alt_header))
        elif "altheader" in sys.argv:
            alt_header = sys.argv[len(sys.argv) - 1]
            if alt_header in msg:
                try:
                    msg.replace_header("List-ID", msg.get(alt_header))
                except KeyError:
                    msg.add_header("list-id", msg.get(alt_header))

        # Set specific LID?
        if args.lid and len(args.lid[0]) > 3:
            try:
                msg.replace_header("List-ID", args.lid[0])
            except KeyError:
                msg.add_header("list-id", args.lid[0])

        # Ignore based on --ignore flag?
        if args.ignorefrom:
            ignore_from = args.ignorefrom[0]
            if fnmatch.fnmatch(msg.get("from"), ignore_from) or (
                msg.get("list-id") and fnmatch.fnmatch(msg.get("list-id"), ignore_from)
            ):
                print("Ignoring message as instructed by --ignore flag")
                sys.exit(0)

        # Check CIDR if need be
        if args.allowfrom:

            c = netaddr.IPNetwork(args.allowfrom[0])
            good = False
            for line in msg.get_all("received") or []:
                m = re.search(r"from .+\[(.+)]", line)
                if m:
                    try:
                        ip = netaddr.IPAddress(m.group(1))
                        if ip in c:
                            good = True
                            msg.add_header("ip-whitelisted", "yes")
                            break
                    except ValueError:
                        pass
                    except netaddr.AddrFormatError:
                        pass
            if not good:
                print("No whitelisted IP found in message, aborting")
                sys.exit(-1)
        # Replace date header with $now?
        if args.makedate:
            msg.replace_header("date", email.utils.formatdate())
        is_public = True
        if args.private:
            is_public = False
        if "list-id" in msg:
            list_data = collections.namedtuple(
                "importmsg",
                [
                    "list_id",
                    "archive_public",
                    "archive_policy",
                    "list_name",
                    "description",
                ],
            )(
                list_id=msg.get("list-id"),
                archive_public=is_public,
                archive_policy=None,
                list_name=msg.get("list-id"),
                description=msg.get("list-id"),
            )

            try:
                lid, mid = archie.archive_message(list_data, msg, raw_message, args.dry, args.dump, args.defaultepoch, args.digest)
                if args.digest:
                    print(mid)
                else:
                    print(
                        "%s: Done archiving to %s as %s!"
                        % (email.utils.formatdate(), lid, mid)
                    )
            except Exception as err:
                if args.verbose:
                    traceback.print_exc()
                print("Archiving failed!: %s" % err)
                raise OSError("Archiving to ES failed") from err
        else:
            print("Nothing to import (no list-id found!)")
    except Exception as err:
        # extract the len number without using variables (which may cause issues?)
        #                           last traceback    1st entry, 2nd field
        line = traceback.extract_tb(sys.exc_info()[2])[0][1]
        if args.quiet:
            print(
                "Could not parse email, but exiting quietly as --quiet is on: %s (@ %s)"
                % (err, line)
            )
        else:
            print("Could not parse email: %s (@ %s)" % (err, line))
            sys.exit(-1)


if __name__ == "__main__":
    main()
