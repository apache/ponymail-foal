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

"""Management endpoint for GDPR operations"""

import plugins.server
import plugins.session
import plugins.messages
import plugins.auditlog
import re
import typing
import aiohttp.web

# N.B. the update/delete database operations are performed with the setting refresh='wait_for'
# This is was done to make testing easier.
# There are very few such changes so this should not affect performance unduly

LISTID_RE = re.compile(r"\A<?[-_a-z0-9]+[.@][-_a-z0-9.]+>?\Z")

def user_error(msg):
    return aiohttp.web.Response(headers={}, status=400, text=msg)

async def process(
    server: plugins.server.BaseServer, session: plugins.session.SessionObject, indata: dict,
) -> typing.Union[dict, aiohttp.web.Response]:
    action = indata.get("action")
    docs = indata.get("documents", [])
    doc = indata.get("document")
    if not docs and doc:
        docs = [doc]
    if not session.credentials or not session.credentials.admin or not server.config.ui.mgmt_enabled:
        return aiohttp.web.Response(headers={}, status=403, text="You need administrative access to use this feature.")
    assert session.database, "No session database connection could be found!"

    # Viewing audit log?
    if action == "log":
        numentries = int(indata.get("size", 50))
        page = int(indata.get("page", 0))
        a_filter = indata.get("filter")
        if a_filter:
            actionFilter = (a_filter)
        else:
            actionFilter = ("edit","delete","hide","unhide")
        out = []
        async for entry in plugins.auditlog.view(session, page=page, num_entries=numentries, raw=True, filter=actionFilter):
            out.append(entry)
        return {
            "entries": out
        }

    # Deleting a document?
    elif action == "delete":
        delcount = 0
        for doc in docs:
            assert isinstance(doc, str), "Document ID must be a string"
            email = await plugins.messages.get_email(session, permalink=doc)
            if email:
                if "id" in email: # id is not a valid property for mbox
                    del email["id"]
                if server.config.ui.fully_delete and email["mid"] and email["dbid"]:  # Full on GDPR blast?
                    await session.database.delete(
                        index=session.database.dbs.db_mbox, id=email["mid"], refresh='wait_for',
                    )
                    await session.database.delete(
                        index=session.database.dbs.db_source, id=email["dbid"], refresh='wait_for',
                    )
                else:  # Standard behavior: hide the email from everyone.
                    email["deleted"] = True
                    await session.database.update(
                        index=session.database.dbs.db_mbox, body={"doc": email}, id=email["mid"], refresh='wait_for',
                    )
                lid = email.get("list_raw", "??")
                await plugins.auditlog.add_entry(session, action="delete", target=doc, lid=lid, log=f"Removed email {doc} from {lid} archives")
                delcount += 1
        return aiohttp.web.Response(headers={}, status=200, text=f"Removed {delcount} emails from archives.")
    # Hiding one or more emails?
    elif action == "hide":
        hidecount = 0
        for doc in docs:
            assert isinstance(doc, str), "Document ID must be a string"
            email = await plugins.messages.get_email(session, permalink=doc)
            if email:
                if "id" in email: # id is not a valid property for mbox
                    del email["id"]
                email["deleted"] = True
                await session.database.update(
                    index=session.database.dbs.db_mbox, body={"doc": email}, id=email["mid"], refresh='wait_for',
                )
                lid = email.get("list_raw", "??")
                await plugins.auditlog.add_entry(session, action="hide", target=doc, lid=lid, log=f"Hid email {doc} from {lid} archives")
                hidecount += 1
        return aiohttp.web.Response(headers={}, status=200, text=f"Hid {hidecount} emails from archives.")
    # Exposing (unhiding) one or more emails?
    elif action == "unhide":
        hidecount = 0
        for doc in docs:
            assert isinstance(doc, str), "Document ID must be a string"
            email = await plugins.messages.get_email(session, permalink=doc)
            if email:
                if "id" in email: # id is not a valid property for mbox
                    del email["id"]
                email["deleted"] = False
                await session.database.update(
                    index=session.database.dbs.db_mbox, body={"doc": email}, id=email["mid"], refresh='wait_for',
                )
                lid = email.get("list_raw", "??")
                await plugins.auditlog.add_entry(session, action="unhide", target=doc, lid=lid, log=f"Unhid email {doc} from {lid} archives")
                hidecount += 1
        return aiohttp.web.Response(headers={}, status=200, text=f"Unhid {hidecount} emails from archives.")
    # Removing an attachment
    elif action == "delatt":
        delcount = 0
        for doc in docs:
            assert isinstance(doc, str), "Attachment ID must be a string"
            attachment = None
            try:
                assert session.database, "Database not connected!"
                attachment = await session.database.get(
                    index=session.database.dbs.db_attachment, id=doc
                )
            except plugins.database.DBError:
                pass  # attachment not found

            if attachment and isinstance(attachment, dict):
                await session.database.delete(
                    index=session.database.dbs.db_attachment, id=attachment["_id"], refresh='wait_for',
                )
                lid = "<system>"
                await plugins.auditlog.add_entry(session, action="delatt", target=doc, lid=lid, log=f"Removed attachment {doc} from the archives")
                delcount += 1
        return aiohttp.web.Response(headers={}, status=200, text=f"Removed {delcount} attachments from archives.")
    # Editing an email in place
    elif action == "edit":
        new_from = indata.get("from")
        new_subject = indata.get("subject")
        new_list = indata.get("list")
        new_body = indata.get("body")
        attach_edit = indata.get("attachments", None)

        # Check for consistency so we don't pollute the database
        if not isinstance(doc, str):
            return user_error("Document ID is missing or invalid")
        # Allow for omitted values
        if new_from and not isinstance(new_from, str):
            return user_error("Author field must be a text string!")
        if new_subject and not isinstance(new_subject, str):
            return user_error("Subject field must be a text string!")
        if new_list and not isinstance(new_list, str):
            return user_error("List ID field must be a text string!")
        if new_list and not re.match(LISTID_RE, new_list):
            return user_error("List ID field must match listname[@.]domain !")
        if new_body and not isinstance(new_body, str):
            return user_error("Email body must be a text string!")

        # extra list validation
        if new_list:
            new_forum = new_list.strip("<>").replace("@", ".").replace(".", "@", 1)
            if new_forum not in server.data.lists:
                return user_error(f"New list id: '{new_forum}' is not an existing list")

        email = await plugins.messages.get_email(session, permalink=doc)
        if email:

            changes = [] # what changes have been seen?
            new_private = indata.get("private", True) # This allows it to be omitted; assume private
             # the property could also be a string, in which case look for explicit public value
            if not isinstance(new_private, bool):
                new_private = (new_private != 'no') # True unless value is 'no', i.e. public
            old_private = email.get("private")
            # if property is absent, we want to set it, so don't default it
            changed_private = (old_private != new_private)
            if changed_private:
                changes.append(f"Privacy: {old_private} => {new_private}")
                email["private"] = new_private # this does not require the source to be hidden

            hide_source = False # we hide the source if any of its derived fields are changed

            # have any derived fields changed?
            if new_from and not email["from"] == new_from:
                email["from_raw"] = new_from
                email["from"] = new_from
                changes.append("Author")
                hide_source = True

            if new_subject and not email["subject"] == new_subject:
                email["subject"] = new_subject
                changes.append("Subject")
                hide_source = True
    
            origin_lid = email["list_raw"]
            new_lid = origin_lid # needed for audit log
            if new_list:
                # Convert List-ID after verification
                new_lid = "<" + new_list.strip("<>").replace("@", ".") + ">"  # foo@bar.baz -> <foo.bar.baz>
                if not new_lid == origin_lid:
                    email["list"] = new_lid
                    email["list_raw"] = new_lid
                    email["forum"] = new_forum
                    changes.append(f"Listid {origin_lid} => {new_lid}")

            if new_body and not email["body"] == new_body:
                email["body"] = new_body
                email["body_short"] = new_body[:plugins.messages.SHORT_BODY_MAX_LEN+1]
                changes.append("Body")
                hide_source = True

            if attach_edit is not None:  # Only set if truly editing attachments...
                email["attachments"] = attach_edit
                changes.append("Attachments")
                hide_source = True

            # Save edited email
            if changes: # something changed
                if "id" in email: # id is not a valid property for mbox
                    del email["id"]
                await session.database.update(
                    index=session.database.dbs.db_mbox, body={"doc": email}, id=email["mid"], refresh='wait_for',
                )

                # Fetch source, mark as deleted (modified) and save IF anything but just privacy changed
                # We do this, as we can't edit the source easily, so we mark it as off-limits instead.
                if hide_source:
                    source = await plugins.messages.get_source(session, permalink=email["dbid"], raw=True)
                    if source:
                        docid = source["_id"]
                        source = source["_source"]
                        source["deleted"] = True
                        await session.database.update(
                            index=session.database.dbs.db_source, body={"doc": source}, id=docid, refresh='wait_for',
                        )

                # TODO this should perhaps show the actual changes?
                await plugins.auditlog.add_entry(session, action="edit", target=doc, lid=new_lid,
                                             log= f"Edited email {doc} from {origin_lid} archives. Changes: {', '.join(changes)}")

                return aiohttp.web.Response(headers={}, status=200, text="Email successfully saved")
            else:
                return user_error("No changes made!")

        return aiohttp.web.Response(headers={}, status=404, text="Email not found!")

    return aiohttp.web.Response(headers={}, status=404, text="Unknown mgmt command requested")


def register(_server: plugins.server.BaseServer):
    return plugins.server.Endpoint(process)
