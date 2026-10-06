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

import os
import time
import pytest
import random
import requests

# Run as: python3 -m pytest [-s] test/itest_integration.py
# also need to run: python3 main.py --testendpoints

API_BASE='http://localhost:8080/api'
TEST_DOMAIN = 'ponymail.apache.org'
TEST_LIST = 'users'
TEST_LIST2 = 'dev'
DOCUMENT_HIDE_TEST = "c396ps3p5pb05srb4269dzcg9j7sof42"
DOCUMENT_EDIT_TEST = "ffc3s2wzpn4n4pfonk9rffs4mnbk3l65" # dev list
DOCUMENT_EDIT_SOURCE = "a05f5a472b5e7e6d0ea10162fa9d2b499861258c142dbb7f402454ad23b4af46"

DOMAIN_COUNT = 4 # ponymail, kafka, portals, activemq

# Emulate how test auth is used by GUI
def get_cookies(user='user'):
    state=random.randint(
        1000000000000000000,
        2000000000000000000) # roughly equivalent to code in oauth.js
    # Get the oauth settings (returned under 'oauth' key)
    jzon_oauth = requests.get(f"{API_BASE}/preferences?oauth=1").json()
    assert 'oauth' in jzon_oauth
    testprovider='testprovider'
    # get the url for the provider
    oauth_portal = jzon_oauth['oauth'][testprovider]['oauth_portal']
    assert oauth_portal
    res = requests.get(f"{oauth_portal}?state={state}&redirect_uri=x&state={state}&key={testprovider}",allow_redirects=False)
    code = res.headers['Location'][1:]
    assert code.startswith('&code=')
    res = requests.get(f"{API_BASE}/oauth.lua?key=testprovider&state={state}&user={user}{code}")
    cookies = res.cookies
    jzon = requests.get(f"{API_BASE}/preferences", cookies=cookies).json()
    assert 'credentials' in jzon['login']
    return cookies

def get_email_by_mid(mid, cookies=None, status_code=200):
    res = requests.get(
        f"{API_BASE}/email.lua",
        params={"id": mid},
        cookies=cookies
    )
    assert res.status_code == status_code, mid
    return res

def get_email_by_msgid(msgid, listid, cookies=None, status_code=200):
    res = requests.get(
        f"{API_BASE}/email.lua",
        params={"id": msgid, "listid": listid},
        cookies=cookies
    )
    assert res.status_code == status_code, msgid
    return res

def check_email(email, cookies):
    # check email accessibility
    mid = email['mid']
    private = email['private']

    # access by Permalink
    res = requests.get(
        f"{API_BASE}/email.lua",
        params={"id": mid},
        cookies=cookies
    )
    assert res.status_code == 200, mid
    jzon = res.json()
    assert mid == jzon['mid']
    assert mid in jzon['permalinks']

    # check email access by message-id
    msgid = jzon['message-id']
    listid = jzon['list_raw']
    res = requests.get(
        f"{API_BASE}/email.lua",
        params={"id": msgid, "listid": listid},
        cookies=cookies
    )
    assert res.status_code == 200, msgid
    if private:
        # should not be visible without cookies
        res = requests.get(
            f"{API_BASE}/email.lua",
            params={"id": mid}
        )
        assert res.status_code == 404, mid
        res = requests.get(
            f"{API_BASE}/email.lua",
            params={"id": msgid, "listid": listid}
        )
        assert res.status_code == 404, msgid
    return mid, msgid, listid, private

def check_source(mid, msgid, listid, private, cookies):
    res = requests.get(
        f"{API_BASE}/source.lua",
        params={"id": mid},
        cookies=cookies
    )
    assert res.status_code == 200, mid
    res = requests.get(
        f"{API_BASE}/source.lua",
        params={"id": msgid, "listid": listid},
        cookies=cookies
    )
    assert res.status_code == 200, mid
    if private:
        # should not be visible without cookies
        res = requests.get(
            f"{API_BASE}/source.lua",
            params={"id": mid}
        )
        assert res.status_code == 404, mid
        res = requests.get(
            f"{API_BASE}/source.lua",
            params={"id": msgid, "listid": listid}
        )
        assert res.status_code == 404, mid

def check_access(email, cookies):
        mid, msgid, listid, private = check_email(email, cookies)
        check_source(mid, msgid, listid, private, cookies)

def check_auditlog_count(count, admin_cookies, action_filter=None):
    if isinstance(action_filter, str):
        action_filter = (action_filter,)  # the query expects a tuple/list of terms, not a single string.
    jzon = mgmt_get_json({"action": 'log', "filter": action_filter}, admin_cookies)
    assert len(jzon['entries']) == count
    return jzon['entries']

ARCHIVE_TESTS = [
    # Mid, listid, msgid
    pytest.param(
        'dx5349o3p57hj6zgs8jhd3z8zwr5j89x', '<jetspeed-user.portals.apache.org>', 
        '<AB767F0FA88E184295B9FA55AA4617C102BAC3972F@BLR-HCLT-EVS06.HCLT.	CORP.HCL.IN-1AAF5DAB-5B0B-7BC1-7E16-7904B17DF4C8>',
        id="line-wrap"
    ),
    pytest.param(
        'jovkcx55v2xz31rsvq56mflwdfr0fgdm', '<users.kafka.apache.org>', '<2021111716102807678710@emrubik.com>+942C722077850D4E',
        id="trailing chars",
    ),
    pytest.param(
        'klc68q4cgcx2jfd8k05tf5l8byzmosyd', '<dev.activemq.apache.org>', '<git-pr-262-activemq-artemis@git.apache.org>',
        id="dupe msgid 51149"
    ),
    pytest.param(
        'xt4lgkhv63pb8r9nf4g12wc1fbksp98p', '<dev.activemq.apache.org>', '<git-pr-262-activemq-artemis@git.apache.org>',
        id="dupe msgid 52937",
        marks=pytest.mark.xfail # fails because does not distiguish duplicates in different months
    ),
]

@pytest.mark.parametrize("mid,listid,msgid", ARCHIVE_TESTS, ids=range(1,len(ARCHIVE_TESTS) + 1))
def test_msgid(mid, listid, msgid):
        res = get_email_by_mid(mid)
        assert res.json()['message-id'] == msgid, f"wrong msgid in {mid}" 
        res = get_email_by_msgid(msgid, listid)
        assert res.json()['mid'] == mid, f"wrong mid when searching for: {msgid}" 

def test_setup():
    # ensure test conditions are correct at the start
    try:
        admin_cookies = get_cookies('admin')
    except Exception as e:
        pytest.exit(f'Problem accessing server: {e}',1)
    mgmt_get_text({"action": 'unhide', "document": DOCUMENT_HIDE_TEST}, admin_cookies)

    try:
        mgmt_get_text(
        {
            "action": 'edit', "document": DOCUMENT_EDIT_TEST,
            "list": 'dev.ponymail.apache.org',
            "private": False, # default is True
        },
        admin_cookies
        )
    except Exception: # TODO: narrow exception
        pass

    import yaml
    yaml = yaml.safe_load(open("server/ponymail.yaml"))
    dburl = yaml['database']['dburl']
    from requests.compat import urljoin
    path = urljoin(dburl, "ponymail-auditlog/_delete_by_query?refresh=true")
    res = requests.post(
        path,
        json={ "query": { "match_all": {} }},
        headers={"Content-Type": 'application/json'}
        )
    assert res.status_code == 200
    path = urljoin(dburl, f"ponymail-source/_update/{DOCUMENT_EDIT_SOURCE}")
    res = requests.post(
        path,
        json={ "doc": {"deleted": False} },
        headers={"Content-Type": 'application/json'}
        )
    assert res.status_code == 200

    check_auditlog_count(0, admin_cookies) # double-check that the log is empty

def test_lists():
    jzon = requests.get(f"{API_BASE}/preferences").json()
    # print(jzon)
    lists = jzon['lists']
    assert TEST_DOMAIN in lists
    assert TEST_LIST in lists[TEST_DOMAIN]
    assert len(lists) == DOMAIN_COUNT

def test_public_stats():
    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()
    assert jzon['firstYear'] == 2022
    assert jzon['firstMonth'] == 1
    assert jzon['lastYear'] == 2022
    assert jzon['lastMonth'] == 1
    assert jzon['hits'] == 6
    for email in jzon['emails']:
        assert email['list_raw'] == '<users.ponymail.apache.org>'
        assert email['list'] == email['list_raw']
        assert email['id'] == email['mid']
        assert not email['private']
        check_access(email, None)
    # Check we cannot see the private emails
    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": '2019-09'}
        ).json()
    assert jzon['hits'] == 0

def test_private_stats():
    cookies = get_cookies('user')
    # only fetch the private mail stats
    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": '2019-09'},
        cookies=cookies
    ).json()
    # The earlier mails are private
    assert jzon['firstYear'] == 2019
    assert jzon['firstMonth'] == 9
    assert jzon['lastYear'] == 2022
    assert jzon['lastMonth'] == 1
    assert jzon['hits'] == 4
    for email in jzon['emails']:
        assert email['list_raw'] == '<users.ponymail.apache.org>'
        assert email['list'] == email['list_raw']
        assert email['id'] == email['mid']
        assert email['private']
        check_access(email, cookies)

def mgmt_get_text(params, cookies, expected=200):
    res = requests.post(f"{API_BASE}/mgmt.json", json=params, cookies=cookies)
    assert res.status_code == expected, res.text
    return res.text

def mgmt_get_json(params, cookies, expected=200):
    res = requests.post(f"{API_BASE}/mgmt.json", json=params, cookies=cookies)
    assert res.status_code == expected, res.text
    return res.json()

def test_mgmt_validation():
    admin_cookies = get_cookies('admin')
    user_cookies = get_cookies('user')
    mgmt_get_text({"action": 'log'}, user_cookies, 403)
    mgmt_get_text({"action": 'any'}, admin_cookies, 404)

    text = mgmt_get_text({"action": 'delete'}, admin_cookies)
    assert text == "Removed 0 emails from archives."

    text = mgmt_get_text({"action": 'hide'}, admin_cookies)
    assert text == "Hid 0 emails from archives."

    text = mgmt_get_text({"action": 'unhide'}, admin_cookies)
    assert text == "Unhid 0 emails from archives."

    text = mgmt_get_text({"action": 'delatt'}, admin_cookies)
    assert text == "Removed 0 attachments from archives."

    text = mgmt_get_text({"action": 'edit'}, admin_cookies, 400)
    assert "Document ID is missing or invalid" in text

    text = mgmt_get_text({"action": 'edit', "document": None}, admin_cookies, 400)
    assert "Document ID is missing or invalid" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "from": 1234}, admin_cookies, 400)
    assert "Author field" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "subject": 1234}, admin_cookies, 400)
    assert "Subject field" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "list": True}, admin_cookies, 400)
    assert "List ID field" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "list": "True"}, admin_cookies, 400)
    assert "List ID field must match" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "list": "a.b.c.d"}, admin_cookies, 400)
    assert "is not an existing list" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd', "list": "dev.ponymail.apache.org"}, admin_cookies, 404)
    assert "Email not found!" in text

    text = mgmt_get_text(
        {"action": 'edit', "document": 'abcd', "body": 1234}, admin_cookies, 400)
    assert "Email body" in text

    text = mgmt_get_text({"action": 'edit', "document": 'abcd'}, admin_cookies, 404)
    assert "Email not found!" in text

def test_mgmt_log_before():
    admin_cookies = get_cookies('admin')
    check_auditlog_count(0, admin_cookies)

def test_mgmt_hiding():
    admin_cookies = get_cookies('admin')

    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()

    assert jzon['hits'] == 6

    check_access({"mid": DOCUMENT_HIDE_TEST, "private": False}, admin_cookies)

    text = mgmt_get_text({"action": 'hide', "document": DOCUMENT_HIDE_TEST}, admin_cookies)
    assert text == "Hid 1 emails from archives."

    check_auditlog_count(1, admin_cookies)

    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()
    assert jzon['hits'] == 5



    text = mgmt_get_text({"action": 'unhide', "document": DOCUMENT_HIDE_TEST}, admin_cookies)
    assert text == "Unhid 1 emails from archives."

    check_auditlog_count(2, admin_cookies)

    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()
    assert jzon['hits'] == 6

    check_access({"mid": DOCUMENT_HIDE_TEST, "private": False}, None)

def test_mgmt_edit():
    """This test causes the source for an entry to be hidden"""
    admin_cookies = get_cookies('admin')

    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST2, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()

    assert jzon['hits'] == 1

    email = jzon['emails'][0]
    check_access(email, None) # should be fully accessible

    res = requests.get(
        f"{API_BASE}/mbox.lua",
        params={"list": TEST_LIST2, "domain": TEST_DOMAIN, "d": '2020-10'}
    )
    assert res.status_code == 200
    assert res.text.startswith('From dev-return-')

    text = mgmt_get_text(
        {
            "action": 'edit', "document": DOCUMENT_EDIT_TEST,
            "list": 'users.ponymail.apache.org',
            "private": False, # default is True
        },
        admin_cookies
        )
    assert text == "Email successfully saved"

    check_auditlog_count(3, admin_cookies)
    check_access(email, None) # should not change access rights

    text = mgmt_get_text(
        {
            "action": 'edit', "document": DOCUMENT_EDIT_TEST,
            "list": 'dev.ponymail.apache.org',
            "private": False, # default is True
        },
        admin_cookies
        )
    assert text == "Email successfully saved"

    check_auditlog_count(4, admin_cookies)
    check_access(email, None) # should not change access rights

    # N.B. use variable body so it is always changed, even after a reset
    text = mgmt_get_text(
        {
            "action": 'edit', "document": DOCUMENT_EDIT_TEST,
            "body": str(time.time()),
            "from": str(time.time()),
            "subject": str(time.time()),
            "private": False, # default is True
        },
        admin_cookies
        )
    assert text == "Email successfully saved"

    check_auditlog_count(5, admin_cookies)

    log = check_auditlog_count(3, admin_cookies, 'edit')[0]['log']
    assert 'Changes: Author, Subject, Body' in log # This is a fragile test..

    jzon = requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST2, "domain": TEST_DOMAIN, "emailsOnly": True, "d": 'gte=0d'}
    ).json()

    assert jzon['hits'] == 1 # mbox entry still accessible

    check_email(email, None)
    check_access(email, admin_cookies) # but the source needs admin

    # check that cannot see mbox
    res = requests.get(
        f"{API_BASE}/mbox.lua",
        params={"list": TEST_LIST2, "domain": TEST_DOMAIN, "d": '2020-10'}
    )
    assert res.status_code == 200
    assert len(res.text) <= 1 # probably just LF

    res = requests.get(
        f"{API_BASE}/mbox.lua",
        params={"list": TEST_LIST2, "domain": TEST_DOMAIN, "d": '2020-10'},
        cookies=admin_cookies
    )
    assert res.status_code == 200
    assert res.text.startswith('From dev-return-')

def test_mgmt_log_after():
    admin_cookies = get_cookies('admin')
    check_auditlog_count(5, admin_cookies)

# Short-term session tokens. The CI job runs this file with `tokens.enabled` both on and off,
# and passes the mode in PONYMAIL_TOKENS so the tests know which behaviour to expect.

TOKENS_ENABLED = os.environ.get("PONYMAIL_TOKENS", "true") == "true"
needs_tokens = pytest.mark.skipif(not TOKENS_ENABLED, reason="tokens.enabled is off")
needs_tokens_off = pytest.mark.skipif(TOKENS_ENABLED, reason="tokens.enabled is on")

def private_hits(**kwargs):
    return requests.get(
        f"{API_BASE}/stats.lua",
        params={"list": TEST_LIST, "domain": TEST_DOMAIN, "emailsOnly": True, "d": '2019-09'},
        **kwargs
    ).json()['hits']

def mint_token(cookies, **extra):
    res = requests.post(f"{API_BASE}/token.json", json={"client": "itest", **extra}, cookies=cookies)
    assert res.status_code == 200, res.text
    jzon = res.json()
    assert jzon['okay']
    assert jzon['token'].startswith('pmt_')
    return jzon

def bearer(token):
    return {"Authorization": f"Bearer {token}"}

def test_token_info():
    jzon = requests.get(f"{API_BASE}/token.lua", params={"action": "info"}).json()
    assert jzon['enabled'] is TOKENS_ENABLED  # Fails if the server's mode doesn't match PONYMAIL_TOKENS
    assert jzon['ttl'] <= jzon['max_ttl']

@needs_tokens
def test_token_requires_login():
    res = requests.post(f"{API_BASE}/token.json", json={"client": "itest"})
    assert res.status_code == 403
    assert res.json()['error'] == 'login_required'

@needs_tokens
def test_token_requires_post():
    res = requests.get(f"{API_BASE}/token.lua", cookies=get_cookies('user'))
    assert res.status_code == 405

@needs_tokens
def test_token_rejects_cross_origin():
    res = requests.post(
        f"{API_BASE}/token.json", json={"client": "itest"}, cookies=get_cookies('user'),
        headers={"Origin": "https://evil.example.org"}
    )
    assert res.status_code == 403
    assert res.json()['error'] == 'cross_origin'

@needs_tokens
def test_token_redirect_uri_must_be_loopback():
    cookies = get_cookies('user')
    for bad in ("https://evil.example.org:8000/cb", "http://127.0.0.1/cb", "http://user@127.0.0.1:9/cb",
                "http://localhost:9/cb"):
        res = requests.post(f"{API_BASE}/token.json", json={"redirect_uri": bad}, cookies=cookies)
        assert res.status_code == 400, bad
    jzon = mint_token(cookies, redirect_uri="http://127.0.0.1:39818/callback")
    assert jzon['redirect_uri'] == "http://127.0.0.1:39818/callback"

@needs_tokens
def test_token_grants_session_read_access():
    assert private_hits() == 0
    jzon = mint_token(get_cookies('user'))
    assert private_hits(headers=bearer(jzon['token'])) == 4
    prefs = requests.get(f"{API_BASE}/preferences.lua", headers=bearer(jzon['token'])).json()
    assert prefs['login']['token']['client'] == 'itest'
    assert prefs['login']['token']['expires'] == jzon['expires']

@needs_tokens
def test_token_invalid_is_anonymous():
    token = mint_token(get_cookies('user'))['token']
    assert private_hits(headers=bearer(token)) == 4  # Control: the real token works
    tampered = token[:-1] + ('A' if token[-1] != 'A' else 'B')  # Well-formed, but never issued
    for bad in (tampered, "pmt_notarealtoken"):
        assert private_hits(headers=bearer(bad)) == 0, bad
        prefs = requests.get(f"{API_BASE}/preferences.lua", headers=bearer(bad)).json()
        assert 'credentials' not in prefs['login'], bad  # The server sees no logged-in user

@needs_tokens
def test_token_ignores_cookie_when_bearer_given():
    # A bad token must not fall back to the cookie sent alongside it
    cookies = get_cookies('user')
    assert private_hits(cookies=cookies) == 4  # Control: the cookie alone grants access
    assert private_hits(headers=bearer("pmt_notarealtoken"), cookies=cookies) == 0

@needs_tokens
def test_token_is_read_only():
    token = mint_token(get_cookies('admin'))['token']
    res = requests.post(f"{API_BASE}/token.json", json={"client": "chained"}, headers=bearer(token))
    assert res.status_code == 403
    assert res.json()['error'] == 'token_not_allowed'
    res = requests.post(f"{API_BASE}/mgmt.json", json={"action": "log"}, headers=bearer(token))
    assert res.status_code == 403
    res = requests.post(f"{API_BASE}/compose.json", json={"to": "x@apache.org", "subject": "s", "body": "b"},
                        headers=bearer(token))
    assert res.status_code == 403

@needs_tokens
def test_token_refused_unless_endpoint_allows_it():
    # oauth does not opt in to tokens, so it must refuse one by default
    token = mint_token(get_cookies('user'))['token']
    res = requests.get(f"{API_BASE}/oauth.lua", headers=bearer(token))
    assert res.status_code == 403
    assert res.text == "Session tokens cannot be used with this endpoint."

@needs_tokens
def test_token_revoke_self():
    token = mint_token(get_cookies('user'))['token']
    assert private_hits(headers=bearer(token)) == 4  # Before: the token works
    res = requests.post(f"{API_BASE}/token.json", json={"action": "revoke"}, headers=bearer(token))
    assert res.json()['revoked'] == 1
    assert private_hits(headers=bearer(token)) == 0  # After: it doesn't

@needs_tokens
def test_token_logout_via_token_keeps_browser_session():
    cookies = get_cookies('user')
    token = mint_token(cookies)['token']
    assert private_hits(headers=bearer(token)) == 4  # Before: both work
    assert private_hits(cookies=cookies) == 4
    requests.get(f"{API_BASE}/preferences.lua", params={"logout": "true"}, headers=bearer(token))
    assert private_hits(headers=bearer(token)) == 0  # After: the token is gone...
    assert private_hits(cookies=cookies) == 4  # ...and the browser session is unchanged

@needs_tokens
def test_token_dies_with_browser_session():
    cookies = get_cookies('user')
    token = mint_token(cookies)['token']
    assert private_hits(headers=bearer(token)) == 4  # Before: both work
    assert private_hits(cookies=cookies) == 4
    requests.get(f"{API_BASE}/preferences.lua", params={"logout": "true"}, cookies=cookies)
    assert private_hits(headers=bearer(token)) == 0  # After: the browser session and its token are gone
    assert private_hits(cookies=cookies) == 0

@needs_tokens
def test_token_list_and_revoke_by_id():
    cookies = get_cookies('user')
    first = mint_token(cookies)
    second = mint_token(cookies)
    listed = requests.post(f"{API_BASE}/token.json", json={"action": "list"}, cookies=cookies).json()['tokens']
    assert {t['id'] for t in listed} == {first['id'], second['id']}
    assert all('token' not in t for t in listed)
    assert private_hits(headers=bearer(first['token'])) == 4
    assert private_hits(headers=bearer(second['token'])) == 4
    res = requests.post(f"{API_BASE}/token.json", json={"action": "revoke", "id": first['id']}, cookies=cookies)
    assert res.json()['revoked'] == 1
    assert private_hits(headers=bearer(first['token'])) == 0
    assert private_hits(headers=bearer(second['token'])) == 4

@needs_tokens
def test_token_revoke_requires_id():
    res = requests.post(f"{API_BASE}/token.json", json={"action": "revoke"}, cookies=get_cookies('user'))
    assert res.status_code == 400
    assert res.json()['error'] == 'missing_id'

@needs_tokens
def test_token_revoke_all():
    cookies = get_cookies('user')
    first = mint_token(cookies)['token']
    second = mint_token(cookies)['token']
    assert private_hits(headers=bearer(first)) == 4
    assert private_hits(headers=bearer(second)) == 4
    res = requests.post(f"{API_BASE}/token.json", json={"action": "revoke", "id": "*"}, cookies=cookies)
    assert res.json()['revoked'] == 2
    assert private_hits(headers=bearer(first)) == 0
    assert private_hits(headers=bearer(second)) == 0
    assert private_hits(cookies=cookies) == 4  # The browser session itself is untouched

@needs_tokens_off
def test_tokens_disabled_refuses_token_actions():
    cookies = get_cookies('user')
    for action in ("create", "list", "revoke"):
        res = requests.post(f"{API_BASE}/token.json", json={"action": action}, cookies=cookies)
        assert res.status_code == 403, action
        assert res.json()['error'] == 'tokens_disabled', action

@needs_tokens_off
def test_tokens_disabled_ignores_bearer_header():
    # With tokens off the Authorization header is not looked at; the cookie session applies as usual
    cookies = get_cookies('user')
    assert private_hits(headers=bearer("pmt_notarealtoken")) == 0
    assert private_hits(headers=bearer("pmt_notarealtoken"), cookies=cookies) == 4
