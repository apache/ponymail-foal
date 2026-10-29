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

# User Guide

## Browsing the Archive

### Front Page

The front page shows all available mailing list domains and their lists
with message counts. Click a domain to expand, then click a list name
to view its archive.

### List View

Once you select a list, you see the current month's emails. The sidebar
shows:

- **Calendar** — click any month to browse historical archives
- **Participants** — top contributors for the selected period
- **Word Cloud** — common terms (if enabled by the administrator)

### Display Modes

Three display modes are available (toggle in the header):

| Mode | Description |
|------|-------------|
| **Threaded** | Groups emails by conversation thread. Click a thread to expand. |
| **Flat** | Shows all emails in chronological order. |
| **Tree** | Hierarchical indented view showing reply relationships. |

### Reading an Email

Click any email subject to open it. The view shows:

- Full message body (with quoted text collapsed by default)
- Sender, date, and list information
- Attachments (downloadable)
- Navigation: "Find parent email" link, permalink

---

## Searching

Use the search box at the top of any page. Supports:

- Free text: `budget meeting`
- Required terms: `+budget`
- Excluded terms: `-spam`
- Exact phrases: `"quarterly review"`

For full search syntax including date ranges and header filters, see
[search.md](search.md).

---

## Authentication

### Logging In

Click the profile icon (top right) to log in via OAuth. Available
providers depend on the deployment (commonly Google, GitHub, or a
custom provider like ASF OAuth).

### What Login Enables

| Feature | Anonymous | Logged In (authoritative) | Admin |
|---------|-----------|--------------------------|-------|
| Browse public lists | ✓ | ✓ | ✓ |
| Browse private lists | ✗ | ✓ | ✓ |
| Compose replies | ✗ | ✓ | ✓ |
| Management console | ✗ | ✗ | ✓ |

"Authoritative" means the OAuth provider is listed in the server's
`authoritative_domains` configuration.

### Logging Out

Click the profile icon again and select "Log out". Your session cookie
is invalidated, along with any session tokens created from that session.

### Session Tokens

If the server enables them, the user menu has a **Session tokens** entry.
There you can create a short-lived, read-only token for a script or tool,
see all your active tokens, and revoke them, including tokens created from
a browser you have since closed. See [Session Tokens](session_tokens.md).

---

## Composing Replies

When logged in via an authoritative OAuth provider:

1. Open an email you want to reply to
2. Click the **Reply** button below the message
3. Compose your reply in the text box
4. Click **Send**

Restrictions:

- You can only reply to lists whose domain matches the server's
  `sender_domains` configuration
- The email is sent from your OAuth-verified email address
- The `In-Reply-To` and `References` headers are set automatically

---

## Permalinks

Every email has a stable permalink URL of the form:

```
https://your-instance/thread/{permalink_id}
```

Use the "Permalink" link in the email view to copy it. These URLs are
stable and suitable for sharing.

**Note:** If an email requires authentication (private list), visitors
who are not logged in will see an error. They must log in first via the
profile icon.

---

## Mbox Download

You can download a month's archive in mbox format by clicking the
download icon in the list view header. This produces a standard mbox
file suitable for import into other mail clients or tools.
