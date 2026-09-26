/*
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
*/

// Approval page for short-term session tokens (see server/plugins/tokens.py).
//
// An external client (CLI, MCP server, script) opens
//   token.html?client=<name>&redirect_uri=http://127.0.0.1:<port>/<path>&state=<nonce>
// The logged-in user is asked to confirm. On approval a token is minted for the
// current browser session and handed back to the client with a form POST to the
// loopback redirect_uri (fields: token, state, expires). On denial the client gets
// error=access_denied instead. Without a redirect_uri the token is shown on the
// page for the user to copy.

'use strict';

const G_token_apiURL = (pm_config.URLBase || '') + (pm_config.apiURL || '/');

function tokenApi(endpoint, method, body) {
    const opts = { method: method, credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    return fetch((G_token_apiURL + 'api/' + endpoint).replace(/\/+/g, '/'), opts)
        .then((r) => r.json());
}

function tokenEl(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        if (k.startsWith('on')) el.addEventListener(k.substring(2), v);
        else el.setAttribute(k, v);
    }
    for (const c of children) {
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
}

function tokenShow(...children) {
    const card = document.getElementById('token_card');
    card.textContent = '';
    for (const c of children) card.appendChild(c);
}

function tokenDuration(seconds) {
    if (seconds % 3600 === 0) return (seconds / 3600) + (seconds === 3600 ? ' hour' : ' hours');
    return Math.round(seconds / 60) + ' minutes';
}

// Mirror of the server-side check: loopback IP literal, explicit port, no credentials.
function tokenLoopbackTarget(uri) {
    try {
        const u = new URL(uri);
        const loopback = ['127.0.0.1', '[::1]'].includes(u.hostname);
        if ((u.protocol === 'http:' || u.protocol === 'https:') && loopback && u.port && !u.username && !u.hash) {
            return u;
        }
    } catch (e) {
        // fall through
    }
    return null;
}

// Hand the result to the waiting client. A form POST keeps the token out of
// the browser history and out of any server logs of the query string.
function tokenHandOff(redirect_uri, fields) {
    const form = tokenEl('form', { method: 'POST', action: redirect_uri });
    for (const [k, v] of Object.entries(fields)) {
        form.appendChild(tokenEl('input', { type: 'hidden', name: k, value: String(v) }));
    }
    document.body.appendChild(form);
    form.submit();
}

function tokenApprove(req) {
    tokenShow(tokenEl('p', {}, 'Creating token...'));
    const body = { action: 'create', client: req.client };
    if (req.redirect_uri) body.redirect_uri = req.redirect_uri;
    if (req.ttl) body.ttl = req.ttl;
    tokenApi('token.json', 'POST', body).then((json) => {
        if (!json.okay) {
            tokenShow(tokenEl('p', {}, 'Could not create a token: ' + (json.message || json.error)));
            return;
        }
        if (json.redirect_uri) {
            tokenShow(tokenEl('p', {}, 'Token created, handing it back to ' + json.client + '...'));
            tokenHandOff(json.redirect_uri, { token: json.token, state: req.state, expires: json.expires });
            return;
        }
        const value = tokenEl('p', { id: 'token_value' }, json.token);
        tokenShow(
            tokenEl('p', {}, 'Your token (valid for ' + tokenDuration(json.ttl) + '):'),
            value,
            tokenEl('div', { class: 'warn' },
                'Copy it now - it will not be shown again. Send it as an ',
                tokenEl('code', {}, 'Authorization: Bearer <token>'),
                ' header. Anyone holding it can read the archives as you until it expires.'),
            tokenEl('div', { class: 'buttons' },
                tokenEl('button', { class: 'btn btn-primary', onclick: () => navigator.clipboard.writeText(json.token) },
                    'Copy to clipboard'))
        );
    }).catch((e) => tokenShow(tokenEl('p', {}, 'Could not create a token: ' + e)));
}

function tokenDeny(req) {
    if (req.redirect_uri) {
        tokenShow(tokenEl('p', {}, 'Request denied, letting ' + req.client + ' know...'));
        tokenHandOff(req.redirect_uri, { error: 'access_denied', state: req.state });
    } else {
        tokenShow(tokenEl('p', {}, 'Request denied. You can close this tab.'));
    }
}

function tokenAsk(req, info, creds) {
    const ttl = Math.min(req.ttl || info.ttl, info.max_ttl);
    const target = req.redirect_uri
        ? tokenEl('p', {}, 'The token will be sent to a program on this computer listening on ',
            tokenEl('code', {}, req.target.host), '.')
        : tokenEl('p', {}, 'The token will be shown on this page for you to copy.');
    tokenShow(
        tokenEl('p', {}, tokenEl('span', { class: 'who' }, req.client),
            ' is asking for a session token that lets it read the mailing list archives as ',
            tokenEl('span', { class: 'who' }, creds.fullname + ' (' + creds.email + ')'),
            ' for up to ' + tokenDuration(ttl) + '.'),
        target,
        tokenEl('div', { class: 'warn' },
            'Only approve this if you started the request yourself just now, from a tool you trust. ',
            'The token can read everything you can read here, including private lists. ',
            'It cannot send email, and it stops working when it expires or when you log out.'),
        tokenEl('div', { class: 'buttons' },
            tokenEl('button', { class: 'btn btn-success', onclick: () => tokenApprove(req) }, 'Approve'),
            tokenEl('button', { class: 'btn btn-default', onclick: () => tokenDeny(req) }, 'Deny'))
    );
}

function tokenInit() {
    // Never let another site frame this page and trick the user into clicking Approve
    if (window.top !== window.self) {
        tokenShow(tokenEl('p', {}, 'This page cannot be displayed inside a frame.'));
        return;
    }
    const q = new URLSearchParams(window.location.search);
    const req = {
        client: (q.get('client') || 'unknown client').substring(0, 64),
        redirect_uri: q.get('redirect_uri') || '',
        state: q.get('state') || '',
        ttl: parseInt(q.get('ttl') || '0', 10) || 0,
        target: null,
    };
    if (req.redirect_uri) {
        req.target = tokenLoopbackTarget(req.redirect_uri);
        if (!req.target) {
            tokenShow(tokenEl('p', {}, 'This request is not valid: tokens can only be handed to a program on this ' +
                'computer (a loopback address with a port).'));
            return;
        }
        if (!req.state) {
            tokenShow(tokenEl('p', {}, 'This request is not valid: it is missing the state parameter.'));
            return;
        }
    }
    Promise.all([tokenApi('token.lua?action=info', 'GET'), tokenApi('preferences.lua', 'GET')])
        .then(([info, prefs]) => {
            if (!info.enabled) {
                tokenShow(tokenEl('p', {}, 'Session tokens are not enabled on this server.'));
                return;
            }
            const creds = prefs.login && prefs.login.credentials;
            if (!creds) {
                // oauth.html sends the user back to the referring page after login
                tokenShow(
                    tokenEl('p', {}, 'You need to be logged in to approve this request.'),
                    tokenEl('div', { class: 'buttons' },
                        tokenEl('a', { class: 'btn btn-primary', href: 'oauth.html', referrerpolicy: 'same-origin' },
                            'Log in')));
                return;
            }
            tokenAsk(req, info, creds);
        })
        .catch((e) => tokenShow(tokenEl('p', {}, 'Could not contact the server: ' + e)));
}

document.addEventListener('DOMContentLoaded', tokenInit);
