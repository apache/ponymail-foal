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
// THIS IS AN AUTOMATICALLY COMBINED FILE. PLEASE EDIT THE source/ FILES!

const PONYMAIL_REVISION = '5e59be9';


/******************************************
 Fetched from source/aavariables.js
******************************************/

 /* jshint -W097 */
'use strict';

const PONYMAIL_VERSION = "1.0.1"; // Current version of Pony Mail Foal

let G_apiURL = ''; // external API URL. Usually left blank.

// Stuff regarding what we're doing right now
let G_current_json = {};
let G_current_state = {};
let G_current_list = '';
let G_current_domain = '';
let G_current_year = 0;
let G_current_month = 0;
let G_current_open_email = null;
let G_select_primed = false;
let G_ponymail_preferences = {};
let G_ponymail_search_list = 'this';

let G_current_listmode = 'threaded';
let G_current_listmode_compact = false;
const PONYMAIL_MAX_NESTING = 10; // max nesting level before unthreading to save space

// thread state
let G_current_email_idx;
let G_chatty_layout = true;

// emails (composer, key-commands, render-email)
let G_full_emails = {};

// listview-*.js, key-commands
let G_current_index_pos = 0;
let G_current_per_page = 0;

// sidebar calendar
const MONTHS_SHORTENED = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const CALENDAR_YEARS_SHOWN = 4; // TODO: should this be configurable?
let G_show_stats_sidebar = true; // Whether to show author stats or not

// datepicker
const DAYS_SHORTENED = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// render_email_chatty
const PONYMAIL_DATE_FORMAT = {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
};
const PONYMAIL_TIME_FORMAT = { timeStyle: 'long'}; // ensure TZ is shown

let G_collated_json = {};

if (pm_config.apiURL) {
    G_apiURL = pm_config.apiURL;
}

// check local storage for settings
let G_can_store = false;
if (window.localStorage && window.localStorage.setItem) {
    try {
        window.localStorage.setItem("ponymail_test", "foo");
        G_can_store = true;
    } catch (e) {
    }
}


/******************************************
 Fetched from source/base-http-extensions.js
******************************************/

// URL calls currently 'in escrow'. This controls the spinny wheel animation
let async_escrow = {}
const ASYNC_MAXWAIT = 250; // ms to wait before displaying spinner
let async_status = 'clear';
let async_cache = {}

// Escrow spinner check
async function escrow_check() {
    let now = new Date();
    let show_spinner = false;
    for (let k in async_escrow) {
        if ((now - async_escrow[k]) > ASYNC_MAXWAIT) {
            show_spinner = true;
            break;
        }
    }
    // Fetch or create the spinner
    let spinner = document.getElementById('spinner');
    if (!spinner) {
        spinner = new HTML('div', {
            id: 'spinner',
            class: 'spinner'
        });
        let spinwheel = new HTML('div', {
            id: 'spinwheel',
            class: 'spinwheel'
        });
        spinner.inject(spinwheel);
        spinner.inject(new HTML('h2', {}, "Loading, please wait.."));
        document.body.appendChild(spinner);
    }
    // Show or don't show spinner?
    if (show_spinner) {
        spinner.style.display = 'block';
        if (async_status === 'clear') {
            async_status = 'waiting';
        }
    } else {
        spinner.style.display = 'none';
        if (async_status === 'waiting') {
            async_status = 'clear';
        }
    }
}

async function async_snap(error) {
    let msg = await error.text();
    msg = msg.replace(/<.*?>/g, ""); // strip HTML tags
    if (error.status === 404) {
        msg += "\n\nYou may need to be logged in with additional permissions in order to view this resource.";
        if (pm_config.perm_error_postface) {
            msg += pm_config.perm_error_postface;
        }
    }
    modal("An error occured", "An error code %u occured while trying to fetch %s:\n%s".format(error.status, error.url, msg), "error");
}


// Asynchronous GET call
async function GET(url, callback, state) {
    let pkey = "GET-%s-%s".format(callback, url);
    let res;
    let res_json;
    state = state || {};
    state.url = url;
    if (state && state.cached === true && async_cache[url]) {
        res_json = async_cache[url];
    } else {
        try {
            async_escrow[pkey] = new Date(); // Log start of request in escrow dict
            const rv = await fetch(url, {
                credentials: 'same-origin'
            }); // Wait for resource...

            // Since this is an async request, the request may have been canceled
            // by the time we get a response. Only do callback if not.
            if (async_escrow[pkey] !== undefined) {
                res = rv;
            }
        } catch (e) {
            delete async_escrow[pkey]; // move out of escrow if failed
            modal("An error occured", "An error occured while trying to fetch %s:\n%s".format(url, e), "error");
        }
    }
    if (res !== undefined || res_json !== undefined) {
        // We expect a 2xx return code (usually 200 or 201), snap otherwise
        if ((res_json) || (res.status >= 200 && res.status < 300)) {
            let js;
            if (res_json) {
                js = res_json;
            } else {
                js = await res.json();
                delete async_escrow[pkey]; // move out of escrow when fetched
                async_cache[url] = js;
            }
            if (callback) {
                callback(state, js);
            }
        } else {
            delete async_escrow[pkey]; // move out of escrow when fetched
            async_snap(res);
        }
    }
}


/******************************************
 Fetched from source/base-js-extensions.js
******************************************/

/**
 * String formatting prototype
 * A'la printf
 */

String.prototype.format = function() {
    let args = arguments;
    let n = 0;
    let t = this;
    let rtn = this.replace(/(?!%)?%([-+]*)([0-9.]*)([a-zA-Z])/g, function(m, pm, len, fmt) {
        len = parseInt(len || '1');
        // We need the correct number of args, balk otherwise, using ourselves to format the error!
        if (args.length <= n) {
            let err = "Error interpolating string '%s': Expected at least %u argments, only got %u!".format(t, n + 1, args.length);
            console.log(err);
            throw err;
        }
        let varg = args[n];
        n++;
        switch (fmt) {
            case 's':
                if (typeof(varg) == 'function') {
                    varg = '(function)';
                }
                return varg;
                // For now, let u, d and i do the same thing
            case 'd':
            case 'i':
            case 'u':
                varg = parseInt(varg).pad(len); // truncate to Integer, pad if needed
                return varg;
        }
    });
    return rtn;
};


/**
 * Number prettification prototype:
 * Converts 1234567 into 1,234,567 etc
 */

Number.prototype.pretty = function(fix) {
    if (fix) {
        return String(this.toFixed(fix)).replace(/(\d)(?=(\d{3})+\.)/g, '$1,');
    }
    return String(this.toFixed(0)).replace(/(\d)(?=(\d{3})+$)/g, '$1,');
};


/**
 * Number padding
 * usage: 123.pad(6) -> 000123
 */

Number.prototype.pad = function(n) {
    let str = String(this);

    /* Do we need to pad? if so, do it using String.repeat */
    if (str.length < n) {
        str = "0".repeat(n - str.length) + str;
    }
    return str;
};

/* Func for converting TZ offset from minutes to +/-HHMM */

Date.prototype.TZ_HHMM = function() {
    let off_mins = this.getTimezoneOffset();
    let off_hh =   Math.floor(Math.abs(off_mins/60));
    let off_mm =   Math.abs(off_mins%60);
    let sgn = off_mins > 0 ? '-' : '+';
    return sgn + off_hh.pad(2) + ':' + off_mm.pad(2);
};



/* Func for converting a date to YYYY-MM-DD HH:MM TZ */

Date.prototype.ISOBare = function() {
    let M, O, d, h, m, y;
    if (prefs.UTC === true) {
        y = this.getUTCFullYear();
        m = (this.getUTCMonth() + 1).pad(2);
        d = this.getUTCDate().pad(2);
        h = this.getUTCHours().pad(2);
        M = this.getUTCMinutes().pad(2);
        O = 'UTC';
    } else {
        y = this.getFullYear();
        m = (this.getMonth() + 1).pad(2);
        d = this.getDate().pad(2);
        h = this.getHours().pad(2);
        M = this.getMinutes().pad(2);
        O = this.TZ_HHMM();
    }
    return y + "-" + m + "-" + d + " " + h + ":" + M + " " + O;
};


/* isArray: function to detect if an object is an array */

function isArray(value) {
    return value && typeof value === 'object' && value instanceof Array && typeof value.length === 'number' && typeof value.splice === 'function' && !(value.propertyIsEnumerable('length'));
}


/* isHash: function to detect if an object is a hash */

function isHash(value) {
    return value && typeof value === 'object' && !isArray(value);
}


/* Remove an array element by value */

Array.prototype.remove = function(val) {
    let i, item, j, len;
    for (i = j = 0, len = this.length; j < len; i = ++j) {
        item = this[i];
        if (item === val) {
            this.splice(i, 1);
            return this;
        }
    }
    return this;
};


/* Check if array has value */
Array.prototype.has = function(val) {
    for (let item of this) {
        if (item === val) {
            return true;
        }
    }
    return false;
};

function isEmpty(obj) {
    return (
        obj &&
        Object.keys(obj).length === 0 &&
        Object.getPrototypeOf(obj) === Object.prototype
    );
}


/******************************************
 Fetched from source/body-fixups.js
******************************************/

const PONYMAIL_URL_RE = new RegExp("(" + "(?:(?:[a-z]+)://)" + "(?:\\S+(?::\\S*)?@)?" + "(?:" + "([01][0-9][0-9]|2[0-4][0-9]|25[0-5])" + "|" + "(?:(?:[a-z\\u00a1-\\uffff0-9]-*)*[a-z\\u00a1-\\uffff0-9]+)" + "(?:\\.(?:[a-z\\u00a1-\\uffff0-9]-*)*[a-z\\u00a1-\\uffff0-9]+)*" + "(?:\\.(?:[a-z\\u00a1-\\uffff]{2,}))" + "\\.?" + ")" + "(?::\\d{2,5})?" + "\\/?" + "(?:[/?#]?([^,<>()\\[\\] \\t\\r\\n]|(<[^:\\s]*?>|\\([^:\\s]*?\\)|\\[[^:\\s]*?\\]))*)?" + ")\\.?" + "\\b", "mi");

// Regex for things to potentially put inside quote objects:
// - quotes
// - forwarded emails
// - inline quoting
// - top posting with original email following
const PONYMAIL_QUOTE_RE = new RegExp("(" +
    // Typical encapsulation of context by ticketing systems and/or bug trackers
    "(---\\r?\\n([^\\r\\n]*?\\r?\\n)*?---$)|" +
    "(" +
    "(?:\\r?\\n|^)" + // start of line or after a colon
    // Classic method; a signal line and the quote with '>' starting each line quoted
    "(" +
    "(" + // Initial line signalling a quote
    "((\\d+-\\d+-\\d+)\\s+.+<\\S+@\\S+>:[ \t\r\n]+)|" + // "01-02-1982 Foo Bar <foo@bar.baz>:" OR
    "(on\\s+(.+|.+\\n.+)\\s+wrote:[\r?\n]+)|" + // "On $somedate, $someone wrote:", OR...
    "(le\\s+(.+|.+\\n.+)\\s+écrit:[\r?\n]+)|" + // French version of the above, OR...
    "(.?am .+? schrieb\\s+.+:[\r?\n]+)|" + // German version of the above, OR...
    "(envoy[ée] de mon .+|sent from my .+|von meinem .+ gesendet)[ \t\r\n]+" + // "sent from my iphone/ipad/android phone/whatever", usually means the next part is a quote.
    ")" + // End initial signal line
    "(^$)*" + // Accept blank newlines following it...
    "(((^(?!>)[\\s\\S]+$)*)|(^\\s*>[\\s\\S]+$)*)" + // Either text that follows immediately after with no '>' first, OR text with '>' first, but NOT both...
    ")|" +
    "(" +
    // Lines after the signal line; comes in one shape, generally speaking...
    "(^\\s*>+[ \\t]*[^\r\n]*\r*\n+)+" + // Lines beginning with one or more '>' after the initial signal line
    ")" +
    ")+|" + //OR...
    "(" +
    "^(-{5,10}) .+? \\1[\r\n]+" + // ----- Forwarded Message -----
    "(^\\w+:\\s+.+[\r\n]+){3,10}[\r\n]+" + // Between three and ten header fields (we ask for at least 3, so as to not quote PGP blocks)
    "[\\S\\s]+" + // Whatever comes next...
    ")+" +
    ")", "mi");

// Somewhat simplified method for catching email footers/trailers that we don't need
const PONYMAIL_TRAILER_RE = new RegExp("^--[\r\n]+.*", "mi"); //(--\r?\n([^\r\n]*?\r?\n){1,6}$)|[\r\n.]+^((--+ \r?\n|--+\r?\n|__+\r?\n|--+\\s*[^\r\n]+\\s*--+\r?\n)(.*\r?\n)+)+$", "m");

// This is a regex for capturing code diff blocks in an email
const PONYMAIL_DIFF_RE = new RegExp(
    "(" +
    "^-{3} .+?[\r\n]+" + // Starts with a "--- /foo/bar/baz"
    "^\\+{3} .+?[\r\n]+" + // Then a "+++ /foo/bar/baz"
    "(" + // Then one or more of...
    "^@@@? .+[\r\n]+" + // positioning
    "(^ .*[\r\n]*$){0,3}" + // diff header
    "(^[-+ ].*[\r\n]*)+" + // actual diff
    "(^ .*[\r\n]*$){0,3}" + // diff trailer
    ")+" +
    ")", "mi");

// Function for turning URLs into <a> tags
function fixup_urls(splicer) {

    if (typeof splicer == 'object') {
        return splicer;
        //splicer = splicer.innerText;
    }
    /* Array holding text and links */
    let i, m, t, textbits, url, urls;
    textbits = [];

    /* Find the first link, if any */
    i = splicer.search(PONYMAIL_URL_RE);
    urls = 0;

    /* While we have more links, ... */
    while (i !== -1) {
        urls++;

        /* Only parse the first 250 URLs... srsly */
        if (urls > 250) {
            break;
        }

        /* Text preceding the link? add it to textbits frst */
        if (i > 0) {
            t = splicer.substring(0, i);
            textbits.push(t);
            splicer = splicer.substring(i);
        }

        /* Find the URL and cut it out as a link */
        m = splicer.match(PONYMAIL_URL_RE);
        if (m) {
            url = m[1];
            i = url.length;
            t = splicer.substring(0, i);
            textbits.push(new HTML('a', {
                href: url
            }, url));
            splicer = splicer.substring(i);
        }

        /* Find the next link */
        i = splicer.search(PONYMAIL_URL_RE);
    }

    /* push the remaining text into textbits */
    textbits.push(splicer);
    return textbits;
}


// Simple check to (attempt to) assess whether a trailer should
// remain or get cut out.
function legit_trailer(a) {
    let lines = a.split(/\s*\r?\n/);
    let first_line = lines.shift();
    while (first_line.length == 0 && lines.length) first_line = lines.shift(); // get first meaningful line
    if (!lines.length || first_line == '--') return ''; // likely a simple trailer
    let last_line = lines.pop();
    while (last_line.length == 0 && lines.length) last_line = lines.pop(); // get last meaningful line

    // Check if first and last line are similar, which is usually indictive of a ticket system
    if (last_line == first_line) {
        return a;
    }
    // Otherwise, check if first line has two or more dashes, and it occurs again later (also tix)
    if (first_line.match(/^---+/) && lines.has(first_line)) {
        return "|||" + a + "|||";
    }

    // Lastly, if there is "sufficient" length to the dashes, allow (JIRA etc)
    if (first_line.match(/^-{6,72}$/)) return a;
    return '';
}

// Function for cutting away trailers
function cut_trailer(splicer) {
    if (!G_chatty_layout) return splicer; // only invoke in social rendering mode
    if (typeof splicer == 'object') {
        splicer.innerText = splicer.innerText.replace(PONYMAIL_TRAILER_RE, legit_trailer, 3);
    } else {
        splicer = splicer.replace(PONYMAIL_TRAILER_RE, legit_trailer);

    }
    return splicer;
}

function color_diff_lines(diff) {
    let lines = diff.split(/[\r\n]+/);
    let ret = [];
    for (let z = 0; z < lines.length; z++) {
        let line = lines[z];
        let color = 'grey';
        if (line[0] == '@') color = 'blue';
        if (line[0] == '-') color = 'red';
        if (line[0] == '+') color = 'green';
        if (line[0] == ' ') color = 'black';
        let el = new HTML('span', {
            style: {
                color: color
            }
        }, line);
        ret.push(el);
        ret.push(new HTML('br'));
    }
    return ret;
}

// Function for coloring diffs
function fixup_diffs(splicer) {
    if (!G_chatty_layout) return splicer; // only invoke in social rendering mode
    if (typeof splicer == 'object') {
        splicer = splicer.innerText;
    }
    /* Array holding text and links */
    let i, m, t, diff, diffs;
    let textbits = [];

    /* Find the first link, if any */
    i = splicer.search(PONYMAIL_DIFF_RE);
    diffs = 0;

    /* While we have more links, ... */
    while (i !== -1) {
        diffs++;

        /* Only parse the first 20 diffs... srsly */
        if (diffs > 25) {
            break;
        }
        /* Text preceding the diff? add it to textbits frst */
        if (i > 0) {
            t = splicer.substring(0, i);
            textbits.push(t);
            splicer = splicer.substring(i);
        }

        /* Find the URL and cut it out as a link */
        m = splicer.match(PONYMAIL_DIFF_RE);
        if (m) {
            diff = m[1];
            i = diff.length;
            t = splicer.substring(0, i);
            textbits.push(new HTML('pre', {
                class: 'diff'
            }, color_diff_lines(diff)));
            splicer = splicer.substring(i);
        }

        /* Find the next link */
        i = splicer.search(PONYMAIL_DIFF_RE);
    }

    /* push the remaining text into textbits */
    textbits.push(splicer);
    return textbits;
}

// Function for turning quotes into quote segments
function fixup_quotes(splicer) {
    if (splicer[splicer.length - 1] !== "\n") splicer += "\n"; //tweak to make quotes match the last line if no newline on it.
    let hideQuotes, i, m, qdiv, quote, quotes, t, textbits;
    hideQuotes = true;
    if (prefs.compactQuotes === false && !G_chatty_layout) {
        hideQuotes = false;
    }
    if (!hideQuotes) return splicer; // We'll bail here for now. Dunno why not.

    /* Array holding text and quotes */
    textbits = [];

    /* Find the first quote, if any */
    i = splicer.search(PONYMAIL_QUOTE_RE);
    quotes = 0;

    /* While we have more quotes, ... */
    while (i !== -1) {
        quotes++;

        /* Only parse the first 50 quotes... srsly */
        if (quotes > 50) {
            break;
        }

        /* Text preceding the quote? add it to textbits first */
        if (i > 0) {
            t = splicer.substring(0, i);
            let diffed = fixup_diffs(cut_trailer(t));
            if (isArray(diffed)) {
                for (let z = 0; z < diffed.length; z++) textbits.push(fixup_urls(diffed[z]));
            } else textbits.push(fixup_urls(diffed));
            splicer = splicer.substring(i);
        }

        /* Find the quote and cut it out as a div */
        m = splicer.match(PONYMAIL_QUOTE_RE);
        if (m) {
            quote = m[0];
            i = quote.length;
            t = splicer.substring(0, i);
            quote = quote.replace(/\n>[>\s]*$/g, "\n");
            qdiv = new HTML('div', {
                "class": "email_quote_parent"
            }, [
                new HTML('button', {
                    title: "Toggle quote",
                    onclick: "toggle_quote(this)"
                }, new HTML('span', {
                    class: 'glyphicon glyphicon-comment'
                }, " ")), new HTML('br'), new HTML('blockquote', {
                    "class": "email_quote",
                    style: {
                        display: hideQuotes ? 'none' : 'block'
                    }
                }, fixup_urls(quote))
            ]);
            textbits.push(qdiv);
            splicer = splicer.substring(i);
        }

        /* Find the next quotes */
        i = splicer.search(PONYMAIL_QUOTE_RE);
    }

    /* push the remaining text into textbits */
    let diffed = fixup_diffs(cut_trailer(splicer));
    if (isArray(diffed)) {
        for (let z = 0; z < diffed.length; z++) diffed[z] = fixup_urls(diffed[z]);
    } else diffed = fixup_urls(diffed);
    textbits.push(new HTML('span', {}, diffed));

    return textbits;
}

function toggle_quote(el) {
    let quote = el.parentNode.childNodes[2];
    if (quote.style.display != 'block') {
        quote.style.display = 'block';
    } else {
        quote.style.display = 'none';
    }
}


/******************************************
 Fetched from source/composer.js
******************************************/

let mua_headers = {}; // communication between compose_email and compose_send

function compose_send() {
    let send_button = document.getElementById('composer_send_btn');
    if (send_button) {
        send_button.disabled = true;
        send_button.style.opacity = '0.5';
        send_button.innerText = 'Sending...';
    }
    let content = [];
    for (let k in mua_headers) {
        content.push(k + "=" + encodeURIComponent(mua_headers[k]));
    }
    // Push the subject, (b)cc and email body into the form data
    content.push("subject=" + encodeURIComponent(document.getElementById('composer_subject').value));
    content.push("cc=" + encodeURIComponent(document.getElementById('composer_cc').value));
    content.push("bcc=" + encodeURIComponent(document.getElementById('composer_bcc').value));
    content.push("body=" + encodeURIComponent(document.getElementById('composer_body').value));
    if (G_ponymail_preferences.login && G_ponymail_preferences.login.alternates && document.getElementById('composer_alt')) {
        content.push("alt=" + encodeURIComponent(document.getElementById('composer_alt').options[document.getElementById('composer_alt').selectedIndex].value));
    }

    let request = new XMLHttpRequest();
    request.open("POST", "%sapi/compose.lua".format(G_apiURL));
    request.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    request.send(content.join("&")); // send email as a POST string

    request.onreadystatechange = function(state) {
        if (request.readyState == 4) {
            document.getElementById('composer_modal').style.display = 'none';
            let response = JSON.parse(request.responseText)
            if (response.error) {
                modal("Message dispatch failed!", response.error, "error");
                if (send_button) {
                    send_button.disabled = false;
                    send_button.style.opacity = '1';
                    send_button.innerText = 'Send reply';
                }
            } else {
                modal("Message dispatched!", "Your email has been sent. Depending on moderation rules, it may take a while before it shows up in the archives.", "help");
            }
        }
    }

}

function compose_email(replyto, list) {
    let email = null;
    let mua_trigger = null;
    let loggedIn = (G_ponymail_preferences.login && G_ponymail_preferences.login.credentials) ? true : false;
    if (replyto) email = G_full_emails[replyto || ''];
    let listname = list;
    mua_headers = {};
    if (email) {
        listname = email.list_raw.replace(/[<>]/g, '').replace('.', '@', 1);
        mua_trigger = mua_link(email);
        if (email['message-id'] && email['message-id'].length > 0) mua_headers['in-reply-to'] = email['message-id'];
        if (email['message-id'] && email['message-id'].length > 0) mua_headers.references = email['message-id'];
        mua_headers.eid = email.mid;
    } else {
        mua_trigger = mua_link(null, listname);
    }
    mua_headers.to = listname;

    // Not logged in? MUA it is, then!
    if (!loggedIn) {
        if (email) {
            let a = new HTML('a', {
                href: mua_trigger
            }, "Reply via your own email client");
            let p = new HTML('p', {}, [
                "In order to reply to emails using the web interface, you need to be ",
                new HTML('a', {
                    href: '/oauth.html'
                }, "logged in first"),
                ". You can however still reply to this email using your own email client: ",
                a
            ]);
            composer("Reply to thread:", p);
            return;
        } else {
            modal("Please log in", "You need to be logged in before you can start a new thread.", "warning");
            return
        }
    }

    // Replying to an email and logged in?
    let eml_subject = "";
    let eml_body = "";
    let eml_title = `Start a new thread on ${listname}:`;
    if (email) {
        eml_subject = email.subject;
        if (!eml_subject.match(/^Re:\s+/i)) {  // Add "Re: " if needed only.
            eml_subject = "Re: " + eml_subject;
        }
        eml_body = composer_re(email);
        eml_title = `Reply to email on ${listname}:`;
    }
    let form = [];
    form.push(new HTML('b', {}, "Sending as:"));
    let s = new HTML('select', {
        id: 'composer_alt'
    });
    s.inject(new HTML('option', {}, G_ponymail_preferences.login.credentials.email));
    if (G_ponymail_preferences.login && G_ponymail_preferences.login.alternates) {
        for (let alternate of G_ponymail_preferences.login.alternates) {
            s.inject(new HTML('option', {}, alternate));
        }
    }
    form.push(new HTML('br'));
    form.push(s);
    form.push(new HTML('br'));
    form.push(new HTML('b', {}, "Subject:"));
    form.push(new HTML('br'));
    form.push(new HTML('input', {
        style: {
            width: '90%'
        },
        id: 'composer_subject',
        type: 'text',
        value: eml_subject
    }));
    form.push(new HTML('br'));
    form.push(new HTML('b', {}, "Cc:"));
    form.push(new HTML('br'));
    form.push(new HTML('input', {
        style: {
            width: '90%'
        },
        id: 'composer_cc',
        type: 'text',
    }));
    form.push(new HTML('br'));
    form.push(new HTML('b', {}, "Bcc:"));
    form.push(new HTML('br'));
    form.push(new HTML('input', {
        style: {
            width: '90%'
        },
        id: 'composer_bcc',
        type: 'text',
    }));
    form.push(new HTML('br'));
    form.push(new HTML('b', {}, "Reply:"));
    form.push(new HTML('br'));
    let body = new HTML('textarea', {
        style: {
            width: '90%',
            minHeight: '400px'
        },
        id: 'composer_body'
    }, eml_body);
    form.push(body);

    let btn = new HTML('button', {
        onclick: 'compose_send();',
        id: 'composer_send_btn'
    }, "Send reply");
    form.push(btn);
    form.push("   ");
    form.push(new HTML('a', {
        href: mua_trigger,
        style: {
            marginLeft: '10px'
        }
    }, "Or compose via your own email client"));

    composer(eml_title, form);
    if (email) document.getElementById('composer_body').focus();

}



// Generic modal function
function composer(title, contents) {
    let composer_modal = document.getElementById('composer_modal');
    if (composer_modal == undefined) {
        composer_modal = new HTML('div', {
            id: 'composer_modal'
        }, [
            new HTML('div', {
                id: 'composer_modal_content'
            }, [
                new HTML('span', {
                    id: 'composer_modal_close',
                    onclick: 'document.getElementById("composer_modal").style.display = "none";'
                }, 'X'),
                new HTML('h2', {
                    id: 'composer_modal_title'
                }, title),
                new HTML('div', {
                    id: 'composer_modal_contents'
                }, contents)
            ])
        ]);
        document.body.appendChild(composer_modal);

    } else {
        document.getElementById('composer_modal_title').innerText = title;
        document.getElementById('composer_modal_contents').innerHTML = '';
        document.getElementById('composer_modal_contents').inject(contents || '');
    }
    composer_modal.style.display = 'block';
}

// Constructor for email body in replies...
function composer_re(email) {
    let lines = email.body.split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
        lines[i] = '> ' + lines[i];
    }
    let re = `\n\nOn ${email.date} ${email.from.replace(/\s*<.+?>/, '')} wrote:\n`;
    re += lines.join("\n");
    return re;
}

// MUA mailto: link generator
function mua_link(email, xlist) {
    if (!email && xlist) {
        return `mailto:${xlist}?subject=Subject+goes+here`;
    }
    let eml_raw_short = composer_re(email);
    let subject = "RE: " + email.subject || '';
    let N = 16000; // Anything above 16K can cause namespace issues with links.
    if (eml_raw_short.length > N) {
        eml_raw_short = eml_raw_short.substring(0, N) + "\n[message truncated...]";
    }
    let listname = email.list_raw.replace(/[<>]/g, '').replace('.', '@', 1);
    let xlink = 'mailto:' + listname + "?subject=" + encodeURIComponent(subject) + "&amp;In-Reply-To=" + encodeURIComponent(email['message-id']) + "&body=" + encodeURIComponent(eml_raw_short);
    return xlink;
}


/******************************************
 Fetched from source/construct-thread.js
******************************************/

function expand_email_threaded(idx, flat) {
    let placeholder = document.getElementById('email_%u'.format(idx));
    if (placeholder) {
        // Check if email is already visible - if so, hide it!
        if (placeholder.style.display == 'block') {
            placeholder.style.display = 'none';
            G_current_email_idx = undefined;
            return false;
        }
        G_current_email_idx = idx;
        placeholder.style.display = 'block';

        // Check if we've not already filled out the structure here
        if (placeholder.getAttribute('data-filled') != 'yes') {
            // Construct the base scaffolding for all emails
            let eml = flat ? G_current_json.emails[idx] : G_current_json.thread_struct[idx];
            if (eml) {
                G_current_open_email = eml.tid || eml.mid;
            }
            let thread = construct_thread(eml);
            placeholder.inject(thread);
            placeholder.setAttribute("data-filled", 'yes');
        }
    }
    return false;
}

function construct_thread(thread, cid, nestlevel, included) {
    // First call on a thread/email, this is indef.
    // Use this to plop a scroll call when loaded
    // to prevent weird cache-scrolling
    let doScroll = false;
    if (cid === undefined) {
        doScroll = true;
    }
    included = included || [];
    cid = (cid || 0) + 1;
    nestlevel = (nestlevel || 0) + 1;
    let mw = calc_email_width();
    let max_nesting = PONYMAIL_MAX_NESTING;
    if (mw < 700) {
        max_nesting = Math.floor(mw / 250);
    }
    cid %= 5;
    let color = ['286090', 'ccab0a', 'c04331', '169e4e', '6d4ca5'][cid];
    let email;
    if (nestlevel < max_nesting) {
        email = new HTML('div', {
            class: 'email_wrapper',
            id: 'email_%s'.format(thread.tid || thread.id)
        });
        if (G_chatty_layout) {
            email.style.border = "none !important";
        } else {
            email.style.borderLeft = '3px solid #%s'.format(color);
        }
    } else {
        email = new HTML('div', {
            class: 'email_wrapper_nonest',
            id: 'email_%s'.format(thread.tid || thread.id)
        });
    }
    let wrapper = new HTML('div', {
        class: 'email_inner_wrapper',
        id: 'email_contents_%s'.format(thread.tid || thread.id)
    });
    email.inject(wrapper);
    if (isArray(thread.children)) {
        thread.children.sort((a, b) => a.epoch - b.epoch);
        for (let child of thread.children) {
            let reply = construct_thread(child, cid, nestlevel, included);
            cid++;
            if (reply) {
                email.inject(reply);
            }
        }
    }
    let tid = thread.tid || thread.id;
    if (!included.includes(tid)) {
        included.push(tid);
        GET("%sapi/email.lua?id=%s".format(G_apiURL, encodeURIComponent(tid)), render_email, {
            cached: true,
            scroll: doScroll,
            id: tid,
            div: wrapper
        });
    }
    return email;
}

// Singular thread construction via permalinks
function construct_single_thread(state, json) {
    G_current_json = json;
    if (json) {
        // Old schema has json.error filled on error, simplified schema has json.message filled and json.okay set to false
        let error_message = json.okay === false ? json.message : json.error;
        if (error_message) {
            modal("An error occured", "Sorry, we hit a snag while trying to load the email(s): \n\n%s".format(error_message), "error");
            return;
        }
    }
    let div = document.getElementById('emails');
    div.innerHTML = "";

    // Fix URLs if they point to an deprecated permalink
    if (json.thread) {
        let url_to_push = location.href.replace(/[^/]+$/, "") + json.thread.id;
        if (location.href != url_to_push) {
            window.history.pushState({}, json.thread.subject, url_to_push)
        }
    }

    // Not top level thread?
    let looked_for_parent = location.query == 'find_parent=true';
    if (!looked_for_parent && json.thread['in-reply-to'] && json.thread['in-reply-to'].length > 0) {
        let isign = new HTML('span', {class: 'glyphicon glyphicon-eye-close'}, " ");
        let btitle = new HTML("b", {}, "This may not be the start of the conversation...");
        let a = new HTML("a", {href: "javascript:void(location.href += '?find_parent=true');"}, "Find parent email");
        let notice = new HTML("div", {class: "infobox"}, [
            isign,
            btitle,
            new HTML("br"),
            "This email appears to be a reply to another email, as it contains an in-reply-to reference.",
            new HTML("br"),
            "If you wish to attempt finding the root thread, click here: ",
            a
        ]);
        div.inject(notice);
        notice.inject(a);
    }

    if (G_chatty_layout) {
        let listname = json.thread.list_raw.replace(/[<>]/g, '').replace('.', '@', 1);
        div.setAttribute("class", "email_placeholder_chatty");
        div.inject(new HTML('h4', {
            class: 'chatty_title'
        }, json.emails[0].subject));
        div.inject(new HTML('a', {
            href: 'list.html?%s'.format(listname),
            class: 'chatty_title'
        }, 'Posted to %s'.format(listname)));
    } else {
        div.setAttribute("class", "email_placeholder");
    }
    document.title = json.emails[0].subject + "-" + prefs.title
    div.style.display = "block";
    let thread = json.thread;
    let email = construct_thread(thread);
    div.inject(email);
}


/******************************************
 Fetched from source/datepicker.js
******************************************/

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
let datepicker_spawner = null
let calendarpicker_spawner = null
const DATE_UNITS = {
    w: 'week',
    d: 'day',
    M: 'month',
    y: 'year'
}

function fixupPicker(obj) {
    obj.addEventListener("focus", function(event) {
        $('html').on('hide.bs.dropdown', function(e) {
            return false;
        });
    });
    obj.addEventListener("blur", function(event) {
        $('html').unbind('hide.bs.dropdown')
    });
}
// makeSelect: Creates a <select> object with options
function makeSelect(options, id, selval) {
    let sel = document.createElement('select')
    sel.addEventListener("focus", function(event) {
        $('html').on('hide.bs.dropdown', function(e) {
            return false;
        });
    });
    sel.addEventListener("blur", function(event) {
        $('html').unbind('hide.bs.dropdown')
    });
    sel.setAttribute("name", id)
    sel.setAttribute("id", id)
    // For each options element, create it in the DOM
    for (let key in options) {
        let opt = document.createElement('option')
        // Hash or array?
        if (typeof key == "string") {
            opt.setAttribute("value", key)
            // Option is selected by default?
            if (key == selval) {
                opt.setAttribute("selected", "selected")
            }
        } else {
            // Option is selected by default?
            if (options[key] == selval) {
                opt.setAttribute("selected", "selected")
            }
        }
        opt.text = options[key]
        sel.appendChild(opt)
    }
    return sel
}

// splitDiv: Makes a split div with 2 elements,
// and puts div2 into the right column,
// and 'name' as text in the left one.
function splitDiv(id, name, div2) {
    let div = document.createElement('div')
    let subdiv = document.createElement('div')
    let radio = document.createElement('input')
    radio.setAttribute("type", "radio")
    radio.setAttribute("name", "datepicker_radio")
    radio.setAttribute("value", name)
    radio.setAttribute("id", "datepicker_radio_" + id)
    radio.setAttribute("onclick", "calcTimespan('" + id + "')")
    let label = document.createElement('label')
    label.innerHTML = "&nbsp; " + name + ": "
    label.setAttribute("for", "datepicker_radio_" + id)


    subdiv.appendChild(radio)
    subdiv.appendChild(label)


    subdiv.style.float = "left"
    div2.style.float = "left"

    subdiv.style.width = "120px"
    subdiv.style.height = "48px"
    div2.style.height = "48px"
    div2.style.width = "250px"

    div.appendChild(subdiv)
    div.appendChild(div2)
    return div
}

// calcTimespan: Calculates the value and representational text
// for the datepicker choice and puts it in the datepicker's
// spawning input/select element.
function calcTimespan(what) {
    let wat = ""
    let tval = ""

    // Less than N units ago?
    if (what == 'lt') {
        // Get unit and how many units
        let N = document.getElementById('datepicker_lti').value
        let unit = document.getElementById('datepicker_lts').value
        let unitt = DATE_UNITS[unit]
        if (parseInt(N) != 1) {
            unitt += "s"
        }

        // If this makes sense, construct a humanly readable and a computer version
        // of the timespan
        if (N.length > 0) {
            wat = "Less than " + N + " " + unitt + " ago"
            tval = "lte=" + N + unit
        }
    }

    // More than N units ago?
    if (what == 'mt') {
        // As above, get unit and no of units.
        let N = document.getElementById('datepicker_mti').value
        let unit = document.getElementById('datepicker_mts').value
        let unitt = DATE_UNITS[unit]
        if (parseInt(N) != 1) {
            unitt += "s"
        }

        // construct timespan val + description
        if (N.length > 0) {
            wat = "More than " + N + " " + unitt + " ago"
            tval = "gte=" + N + unit
        }
    }

    // Date range?
    if (what == 'cd') {
        // Get From and To values
        let f = document.getElementById('datepicker_cfrom').value
        let t = document.getElementById('datepicker_cto').value
        // construct timespan val + description if both from and to are valid
        if (f.length > 0 && t.length > 0) {
            wat = "From " + f + " to " + t
            tval = "dfr=" + f + "|dto=" + t
        }
    }

    // If we calc'ed a value and spawner exists, update its key/val
    if (datepicker_spawner && what && wat.length > 0) {
        document.getElementById('datepicker_radio_' + what).checked = true
        if (datepicker_spawner.options) {
            datepicker_spawner.options[0].value = tval
            datepicker_spawner.options[0].text = wat
        } else if (datepicker_spawner.value) {
            datepicker_spawner.value = wat
            datepicker_spawner.setAttribute("data", tval)
        }

    }
}

// datePicker: spawns a date picker with letious
// timespan options right next to the parent caller.
function datePicker(parent, seedPeriod) {
    datepicker_spawner = parent
    let div = document.getElementById('datepicker_popup')

    // If the datepicker object doesn't exist, spawn it
    if (!div) {
        div = document.createElement('div')
        div.setAttribute("id", "datepicker_popup")
        div.setAttribute("class", "datepicker")
    }

    // Reset the contents of the datepicker object
    div.innerHTML = ""
    div.style.display = "block"

    // Position the datepicker next to whatever called it
    let bb = parent.getBoundingClientRect()
    div.style.top = (bb.bottom + 8) + "px"
    div.style.left = (bb.left + 32) + "px"


    // -- Less than N $units ago
    let ltdiv = document.createElement('div')
    let lti = document.createElement('input')
    lti.setAttribute("id", "datepicker_lti")
    lti.style.width = "48px"
    lti.setAttribute("onkeyup", "calcTimespan('lt')")
    lti.setAttribute("onblur", "calcTimespan('lt')")
    ltdiv.appendChild(lti)

    let lts = makeSelect({
        'd': "Day(s)",
        'w': 'Week(s)',
        'M': "Month(s)",
        'y': "Year(s)"
    }, 'datepicker_lts', 'm')
    lts.setAttribute("onchange", "calcTimespan('lt')")
    ltdiv.appendChild(lts)
    ltdiv.appendChild(document.createTextNode(' ago'))

    div.appendChild(splitDiv('lt', 'Less than', ltdiv))


    // -- More than N $units ago
    let mtdiv = document.createElement('div')

    let mti = document.createElement('input')
    mti.style.width = "48px"
    mti.setAttribute("id", "datepicker_mti")
    mti.setAttribute("onkeyup", "calcTimespan('mt')")
    mti.setAttribute("onblur", "calcTimespan('mt')")
    mtdiv.appendChild(mti)


    let mts = makeSelect({
        'd': "Day(s)",
        'w': 'Week(s)',
        'M': "Month(s)",
        'y': "Year(s)"
    }, 'datepicker_mts', 'm')
    mtdiv.appendChild(mts)
    mts.setAttribute("onchange", "calcTimespan('mt')")
    mtdiv.appendChild(document.createTextNode(' ago'))
    div.appendChild(splitDiv('mt', 'More than', mtdiv))



    // -- Calendar timespan
    // This is just two text fields, the calendarPicker sub-plugin populates them
    let cdiv = document.createElement('div')

    let cfrom = document.createElement('input')
    cfrom.style.width = "90px"
    cfrom.setAttribute("id", "datepicker_cfrom")
    cfrom.setAttribute("onfocus", "showCalendarPicker(this)")
    cfrom.setAttribute("onchange", "calcTimespan('cd')")
    cdiv.appendChild(document.createTextNode('From: '))
    cdiv.appendChild(cfrom)

    let cto = document.createElement('input')
    cto.style.width = "90px"
    cto.setAttribute("id", "datepicker_cto")
    cto.setAttribute("onfocus", "showCalendarPicker(this)")
    cto.setAttribute("onchange", "calcTimespan('cd')")
    cdiv.appendChild(document.createTextNode('To: '))
    cdiv.appendChild(cto)

    div.appendChild(splitDiv('cd', 'Date range', cdiv))



    // -- Magic button that sends the timespan back to the caller
    let okay = document.createElement('input')
    okay.setAttribute("type", "button")
    okay.setAttribute("value", "Okay")
    okay.setAttribute("onclick", "setDatepickerDate()")
    div.appendChild(okay)
    parent.parentNode.appendChild(div)
    document.body.setAttribute("onclick", "")
    window.setTimeout(function() {
        document.body.setAttribute("onclick", "blurDatePicker(event)")
    }, 200)
    lti.focus()

    // This is for recalcing the set options if spawned from a
    // select/input box with an existing value derived from an
    // earlier call to datePicker
    let ptype = ""
    let pvalue = parent.hasAttribute("data") ? parent.getAttribute("data") : parent.value
    if (pvalue.search(/=|-/) != -1) {

        // Less than N units ago?
        if (pvalue.match(/lte/)) {
            let m = pvalue.match(/lte=(\d+)([dMyw])/)
            ptype = 'lt'
            if (m) {
                document.getElementById('datepicker_lti').value = m[1]
                let sel = document.getElementById('datepicker_lts')
                for (let i in sel.options) {
                    if (parseInt(i) >= 0) {
                        if (sel.options[i].value == m[2]) {
                            sel.options[i].selected = "selected"
                        } else {
                            sel.options[i].selected = null
                        }
                    }
                }
            }

        }

        // More than N units ago?
        if (pvalue.match(/gte/)) {
            ptype = 'mt'
            let m = pvalue.match(/gte=(\d+)([dMyw])/)
            if (m) {
                document.getElementById('datepicker_mti').value = m[1]
                let sel = document.getElementById('datepicker_mts')
                // Go through the unit values, select the one we use
                for (let i in sel.options) {
                    if (parseInt(i) >= 0) {
                        if (sel.options[i].value == m[2]) {
                            sel.options[i].selected = "selected"
                        } else {
                            sel.options[i].selected = null
                        }
                    }
                }
            }
        }

        // Date range?
        if (pvalue.match(/dfr/)) {
            ptype = 'cd'
            // Make sure we have both a dfr and a dto here, catch them
            let mf = pvalue.match(/dfr=(\d+-\d+-\d+)/)
            let mt = pvalue.match(/dto=(\d+-\d+-\d+)/)
            if (mf && mt) {
                // easy peasy, just set two text fields!
                document.getElementById('datepicker_cfrom').value = mf[1]
                document.getElementById('datepicker_cto').value = mt[1]
            }
        }
        // Month??
        if (pvalue.match(/(\d{4})-(\d+)/)) {
            ptype = 'cd'
            // Make sure we have both a dfr and a dto here, catch them
            let m = pvalue.match(/(\d{4})-(\d+)/)
            if (m.length == 3) {
                // easy peasy, just set two text fields!
                let dfrom = new Date(parseInt(m[1]), parseInt(m[2]) - 1, 1, 0, 0, 0)
                let dto = new Date(parseInt(m[1]), parseInt(m[2]), 0, 23, 59, 59)
                document.getElementById('datepicker_cfrom').value = m[0] + "-" + dfrom.getDate()
                document.getElementById('datepicker_cto').value = m[0] + "-" + dto.getDate()
            }
        }
        calcTimespan(ptype)
    }
}


function datePickerValue(seedPeriod) {
    // This is for recalcing the set options if spawned from a
    // select/input box with an existing value derived from an
    // earlier call to datePicker
    let rv = seedPeriod
    if (seedPeriod && seedPeriod.search && seedPeriod.search(/=|-/) != -1) {

        // Less than N units ago?
        if (seedPeriod.match(/lte/)) {
            let m = seedPeriod.match(/lte=(\d+)([dMyw])/)
            let unitt = DATE_UNITS[m[2]]
            if (parseInt(m[1]) != 1) {
                unitt += "s"
            }
            rv = "Less than " + m[1] + " " + unitt + " ago"
        }

        // More than N units ago?
        if (seedPeriod.match(/gte/)) {
            let m = seedPeriod.match(/gte=(\d+)([dMyw])/)
            let unitt = DATE_UNITS[m[2]]
            if (parseInt(m[1]) != 1) {
                unitt += "s"
            }
            rv = "More than " + m[1] + " " + unitt + " ago"
        }

        // Date range?
        if (seedPeriod.match(/dfr/)) {
            let mf = seedPeriod.match(/dfr=(\d+-\d+-\d+)/)
            let mt = seedPeriod.match(/dto=(\d+-\d+-\d+)/)
            if (mf && mt) {
                rv = "From " + mf[1] + " to " + mt[1]
            }
        }

        // Month??
        if (seedPeriod.match(/^(\d+)-(\d+)$/)) {
            let mr = seedPeriod.match(/(\d+)-(\d+)/)
            if (mr) {
                let dfrom = new Date(parseInt(mr[1]), parseInt(mr[2]) - 1, 1, 0, 0, 0)
                rv = MONTHS[dfrom.getMonth()] + ', ' + mr[1]
            }
        }

    }
    return rv
}

function datePickerDouble(seedPeriod) {
    // This basically takes a date-arg and doubles it backwards
    // so >=3M becomes =>6M etc. Also returns the cutoff for
    // the original date and the span in days of the original
    let dbl = seedPeriod
    let tspan = 1
    let dfrom = new Date()
    let dto = new Date()

    // datepicker range?
    if (seedPeriod && seedPeriod.search && seedPeriod.search(/=/) != -1) {

        // Less than N units ago?
        if (seedPeriod.match(/lte/)) {
            let m = seedPeriod.match(/lte=(\d+)([dMyw])/)
            dbl = "lte=" + (parseInt(m[1]) * 2) + m[2]

            // N months ago
            if (m[2] == "M") {
                dfrom.setMonth(dfrom.getMonth() - parseInt(m[1]), dfrom.getDate())
            }

            // N days ago
            if (m[2] == "d") {
                dfrom.setDate(dfrom.getDate() - parseInt(m[1]))
            }

            // N years ago
            if (m[2] == "y") {
                dfrom.setYear(dfrom.getFullYear() - parseInt(m[1]))
            }

            // N weeks ago
            if (m[2] == "w") {
                dfrom.setDate(dfrom.getDate() - (parseInt(m[1]) * 7))
            }

            // Calc total duration in days for this time span
            tspan = parseInt((dto.getTime() - dfrom.getTime() + 5000) / (1000 * 86400))
        }

        // More than N units ago?
        if (seedPeriod.match(/gte/)) {
            let m = seedPeriod.match(/gte=(\d+)([dMyw])/)
            dbl = "gte=" + (parseInt(m[1]) * 2) + m[2]
            // Can't really figure out a timespan for this, so...null!
            // This also sort of invalidates use on the trend page, but meh..
            tspan = null
            dfrom = null

            // Months
            if (m[2] == "M") {
                dto.setMonth(dto.getMonth() - parseInt(m[1]), dto.getDate())
            }

            // Days
            if (m[2] == "d") {
                dto.setDate(dto.getDate() - parseInt(m[1]))
            }

            // Years
            if (m[2] == "y") {
                dto.setYear(dto.getFullYear() - parseInt(m[1]))
            }

            // Weeks
            if (m[2] == "w") {
                dto.setDate(dto.getDate() - (parseInt(m[1]) * 7))
            }
        }

        // Date range?
        if (seedPeriod.match(/dfr/)) {
            // Find from and to
            let mf = seedPeriod.match(/dfr=(\d+)-(\d+)-(\d+)/)
            let mt = seedPeriod.match(/dto=(\d+)-(\d+)-(\d+)/)
            if (mf && mt) {
                // Starts at 00:00:00 on from date
                dfrom = new Date(parseInt(mf[1]), parseInt(mf[2]) - 1, parseInt(mf[3]), 0, 0, 0)

                // Ends at 23:59:59 on to date
                dto = new Date(parseInt(mt[1]), parseInt(mt[2]) - 1, parseInt(mt[3]), 23, 59, 59)

                // Get duration in days, add 5 seconds to we can floor the value and get an integer
                tspan = parseInt((dto.getTime() - dfrom.getTime() + 5000) / (1000 * 86400))

                // double the distance
                let dpast = new Date(dfrom)
                dpast.setDate(dpast.getDate() - tspan)
                dbl = seedPeriod.replace(/dfr=[^|]+/, "dfr=" + (dpast.getFullYear()) + '-' + (dpast.getMonth() + 1) + '-' + dpast.getDate())
            } else {
                tspan = 0
            }
        }
    }

    // just N days?
    else if (parseInt(seedPeriod).toString() == seedPeriod.toString()) {
        tspan = parseInt(seedPeriod)
        dfrom.setDate(dfrom.getDate() - tspan)
        dbl = "lte=" + (tspan * 2) + "d"
    }

    // Specific month?
    else if (seedPeriod.match(/^(\d+)-(\d+)$/)) {
        // just a made up thing...(month range)
        let mr = seedPeriod.match(/(\d+)-(\d+)/)
        if (mr) {
            // Same as before, start at 00:00:00
            dfrom = new Date(parseInt(mr[1]), parseInt(mr[2]) - 1, 1, 0, 0, 0)
            // end at 23:59:59
            dto = new Date(parseInt(mr[1]), parseInt(mr[2]), 0, 23, 59, 59)

            // B-A, add 5 seconds so we can floor the no. of days into an integer neatly
            tspan = parseInt((dto.getTime() - dfrom.getTime() + 5000) / (1000 * 86400))

            // Double timespan
            let dpast = new Date(dfrom)
            dpast.setDate(dpast.getDate() - tspan)
            dbl = "dfr=" + (dpast.getFullYear()) + '-' + (dpast.getMonth() + 1) + '-' + dpast.getDate() + "|dto=" + (dto.getFullYear()) + '-' + (dto.getMonth() + 1) + '-' + dto.getDate()
        } else {
            tspan = 0
        }
    }

    return [dbl, dfrom, dto, tspan]
}

// set date in caller and hide datepicker again.
function setDatepickerDate() {
    calcTimespan()
    blurDatePicker()
}

// findParent: traverse DOM and see if we can find a parent to 'el'
// called 'name'. This is used for figuring out whether 'el' has
// lost focus or not.
function findParent(el, name) {
    if (el.getAttribute && el.getAttribute("id") == name) {
        return true
    }
    if (el.parentNode && el.parentNode.getAttribute) {
        if (el.parentNode.getAttribute("id") != name) {
            return findParent(el.parentNode, name)
        } else {
            return true
        }
    } else {
        return false;
    }
}

// function for hiding the date picker
function blurDatePicker(evt) {
    let es = evt ? (evt.target || evt.srcElement) : null;
    if ((!es || !es.parentNode || (!findParent(es, "datepicker_popup") && !findParent(es, "calendarpicker_popup"))) && !(es ? es : "null").toString().match(/javascript:void/)) {
        document.getElementById('datepicker_popup').style.display = "none"
        $('html').trigger('hide.bs.dropdown')
    }
}

// draws the actual calendar inside a calendarPicker object
function drawCalendarPicker(obj, date) {


    obj.focus()

    // Default to NOW for calendar.
    let now = new Date()

    // if called with an existing date (YYYY-MM-DD),
    // convert it to a JS date object and use that for
    // rendering the calendar
    if (date) {
        let ar = date.split(/-/)
        now = new Date(ar[0], parseInt(ar[1]) - 1, ar[2])
    }
    let mat = now

    // Go to first day of the month
    mat.setDate(1)

    obj.innerHTML = "<h3>" + MONTHS[mat.getMonth()] + ", " + mat.getFullYear() + ":</h3>"
    let tm = mat.getMonth()

    // -- Nav buttons --

    // back-a-year button
    let a = document.createElement('a')
    fixupPicker(a)
    a.setAttribute("onclick", "drawCalendarPicker(this.parentNode, '" + (mat.getFullYear() - 1) + '-' + (mat.getMonth() + 1) + '-' + mat.getDate() + "');")
    a.setAttribute("href", "javascript:void(0);")
    a.setAttribute("class", "glyphicon glyphicon-fast-backward");
    obj.appendChild(a)

    // back-a-month button
    a = document.createElement('a')
    fixupPicker(a)
    a.setAttribute("onclick", "drawCalendarPicker(this.parentNode, '" + mat.getFullYear() + '-' + (mat.getMonth()) + '-' + mat.getDate() + "');")
    a.setAttribute("href", "javascript:void(0);")
    a.setAttribute("class", "glyphicon glyphicon-step-backward");
    obj.appendChild(a)

    // forward-a-month button
    a = document.createElement('a')
    fixupPicker(a)
    a.setAttribute("onclick", "drawCalendarPicker(this.parentNode, '" + mat.getFullYear() + '-' + (mat.getMonth() + 2) + '-' + mat.getDate() + "');")
    a.setAttribute("href", "javascript:void(0);")
    a.setAttribute("class", "glyphicon glyphicon-step-forward");
    obj.appendChild(a)

    // forward-a-year button
    a = document.createElement('a')
    fixupPicker(a)
    a.setAttribute("onclick", "drawCalendarPicker(this.parentNode, '" + (mat.getFullYear() + 1) + '-' + (mat.getMonth() + 1) + '-' + mat.getDate() + "');")
    a.setAttribute("href", "javascript:void(0);")
    a.setAttribute("class", "glyphicon glyphicon-fast-forward");
    obj.appendChild(a)
    obj.appendChild(document.createElement('br'))


    // Table containing the dates of the selected month
    let table = document.createElement('table')

    table.setAttribute("border", "1")
    table.style.margin = "0 auto"

    // Add header day names
    let tr = document.createElement('tr');
    for (let m = 0; m < 7; m++) {
        let td = document.createElement('th')
        td.innerHTML = DAYS_SHORTENED[m]
        tr.appendChild(td)
    }
    table.appendChild(tr)

    // Until we hit the first day in a month, add blank days
    tr = document.createElement('tr');
    let weekday = mat.getDay()
    if (weekday == 0) {
        weekday = 7
    }
    weekday--;
    for (let i = 0; i < weekday; i++) {
        let td = document.createElement('td')
        tr.appendChild(td)
    }

    // While still in this month, add day then increment date by 1 day.
    while (mat.getMonth() == tm) {
        weekday = mat.getDay()
        if (weekday == 0) {
            weekday = 7
        }
        weekday--;
        if (weekday == 0) {
            table.appendChild(tr)
            tr = document.createElement('tr');
        }
        let td = document.createElement('td')
        // onclick for setting the calendarPicker's parent to this val.
        td.setAttribute("onclick", "setCalendarDate('" + mat.getFullYear() + '-' + (mat.getMonth() + 1) + '-' + mat.getDate() + "');")
        td.innerHTML = mat.getDate()
        mat.setDate(mat.getDate() + 1)
        tr.appendChild(td)
    }

    table.appendChild(tr)
    obj.appendChild(table)
}

// callback for datePicker; sets the cd value to what date was picked
function setCalendarDate(what) {
    $('html').on('hide.bs.dropdown', function(e) {
        return false;
    });
    setTimeout(function() {
        $('html').unbind('hide.bs.dropdown');
    }, 250);


    calendarpicker_spawner.value = what
    let div = document.getElementById('calendarpicker_popup')
    div.parentNode.focus()
    div.style.display = "none"
    calcTimespan('cd')
}

// caller for when someone clicks on a calendarPicker enabled field
function showCalendarPicker(parent, seedDate) {
    calendarpicker_spawner = parent

    // If supplied with a YYYY-MM-DD date, use this to seed the calendar
    if (!seedDate) {
        let m = parent.value.match(/(\d+-\d+(-\d+)?)/)
        if (m) {
            seedDate = m[1]
        }
    }

    // Show or create the calendar object
    let div = document.getElementById('calendarpicker_popup')
    if (!div) {
        div = document.createElement('div')
        div.setAttribute("id", "calendarpicker_popup")
        div.setAttribute("class", "calendarpicker")
        document.getElementById('datepicker_popup').appendChild(div)
        div.innerHTML = "Calendar goes here..."
    }
    div.style.display = "block"
    let bb = parent.getBoundingClientRect()

    // Align with the calling object, slightly below
    div.style.top = (bb.bottom + 8) + "px"
    div.style.left = (bb.right - 32) + "px"

    drawCalendarPicker(div, seedDate)
}


/******************************************
 Fetched from source/init.js
******************************************/

console.log("/******* Apache Pony Mail (Foal v/%s) Initializing ********/".format(PONYMAIL_VERSION))

// Adjust titles:
document.title = prefs.title;
for (let title of document.getElementsByClassName("title")) {
    title.innerText = prefs.title;
}

window.setInterval(escrow_check, 250);

window.addEventListener('keyup', keyCommands);

window.addEventListener('load', function() {
    let powered_by = "Powered by Apache Pony Mail (Foal v/%s ~%s)".format(PONYMAIL_VERSION, PONYMAIL_REVISION);
    let pb = document.getElementById("powered_by");
    if (pb) {
        pb.innerHTML = powered_by
    }
    document.body.appendChild(new HTML('footer', {
        class: 'footer hidden-xs'
    }, [
        new HTML('div', {
            class: 'container'
        }, [
            new HTML('p', {
                class: 'muted'
            }, powered_by)
        ])
    ]));
});
window.onpopstate = function(event) {
    return parseURL({
        cached: true
    });
};


/******************************************
 Fetched from source/key-commands.js
******************************************/

// Generic modal function
function modal(title, msg, type, isHTML) {
    let modalId = document.getElementById('modal');
    let text = document.getElementById('modal_text');
    if (modalId == undefined) {
        text = new HTML('p', {
            id: 'modal_text'
        }, "");
        modalId = new HTML('div', {
            id: 'modal'
        }, [
            new HTML('div', {
                id: 'modal_content'
            }, [
                new HTML('span', {
                    id: 'modal_close',
                    onclick: 'document.getElementById("modal").style.display = "none";'
                }, 'X'),
                new HTML('h2', {
                    id: 'modal_title'
                }, title),
                new HTML('div', {}, text)
            ])
        ]);
        document.body.appendChild(modalId);

    }
    if (type) {
        modalId.setAttribute("class", "modal_" + type);
    } else {
        modalId.setAttribute("class", undefined);
    }
    modalId.style.display = 'block';
    document.getElementById('modal_title').innerText = title;
    // If we trust HTML, use it. Otherwise only show as textNode.
    if (isHTML) {
        text.innerHTML = msg;
    } else {
        msg = msg.replace(/<.*?>/g, ""); // strip HTML tags
        text.innerText = msg;
    }
}

// Helper for determining if an email is open or not...
function anyOpen() {
    let open = (G_current_email_idx !== undefined) ? true : false;
    return open;
}

// Helper function for hiding windows and open tabs
// Hide previous action on first escape, hide everything on second escape
function hideWindows(force_all) {

    // First, check if we want to hide a modal
    let modalId = document.getElementById('modal');
    if (modalId && modalId.style.display == 'block') {
        modalId.style.display = 'none';
        if (force_all !== true) return;
    }

    // RThen, check if we want to hide a composer modal
    let cmodal = document.getElementById('composer_modal');
    if (cmodal && cmodal.style.display == 'block') {
        cmodal.style.display = 'none';
        if (force_all !== true) return;
    }

    // Check Advanced Search
    let as = document.getElementById('advanced_search');
    if (as && as.style.display == 'block') {
        as.style.display = 'none';
        if (force_all !== true) return;
    }

    // Check for individually opened email
    if (G_current_email_idx !== undefined) {
        let placeholder = document.getElementById('email_%u'.format(G_current_email_idx));
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        G_current_email_idx = undefined; // undef this even if we can't find the email
        if (force_all !== true) return;
    }

    // if viewing a single thread, disregard the collapses below - the won't make sense!
    if (location.href.match(/thread(?:\.html)?/)) return;

    // Finally, check for other opened emails, close 'em all
    let placeholders = document.getElementsByClassName('email_placeholder');
    for (let placeholder of placeholders) {
        if (placeholder.style.display == 'block') {
            placeholder.style.display = 'none';
            // Reset scroll cache
            try {
                window.scrollTo(0, 0);
            } catch (e) {}
        }
    }

    placeholders = document.getElementsByClassName('email_placeholder_chatty');
    for (let placeholder of placeholders) {
        if (placeholder.style.display == 'block') {
            placeholder.style.display = 'none';
            // Reset scroll cache
            try {
                window.scrollTo(0, 0);
            } catch (e) {}
        }
    }

}

// Show keyboard commands
function showHelp() {
    modal("Keyboard shortcuts:", "<pre><kbd>H</kbd>: Show this help window.\n<kbd>C</kbd>: Compose a new email to this list.\n<kbd>R</kbd>: Reply to the currently active thread.\n<kbd>S</kbd>: Go to the search bar.\n<kbd>Escape</kbd>: Hide modals or collapse threads.\n<kbd>RightArrow</kbd>: Go to next bunch of emails in list view.\n<kbd>LeftArrow</kbd>: Go to previous bunch of emails in list view.</pre>", "help", true);
}

// Function for capturing and evaluating key strokes
// If it matches a known shortcut, execute that then..
function keyCommands(e) {
    if (!e.ctrlKey) {
        // Get calling element and its type
        let target = e.target || e.srcElement;
        let type = target.tagName;
        // We won't jump out of an input field!
        if (['INPUT', 'TEXTAREA', 'SELECT'].has(type)) {
            return;
        }
        switch (e.key) {
            case 's':
                document.getElementById('q').focus();
                return;
            case 'h':
                showHelp();
                return;
            case 'c':
                compose_email(null, `${G_current_list}@${G_current_domain}`);
                return;
            case 'r':
                if (G_current_open_email && G_full_emails[G_current_open_email]) {
                    compose_email(G_current_open_email);
                }
                return;
            case 'Escape':
                hideWindows();
                return;
            case 'ArrowRight': // quick-next
                if (G_current_json) { // IF list view...
                    let blobs = G_current_json.emails;
                    if (G_current_listmode == 'threaded') blobs = G_current_json.thread_struct;
                    let no_emails = blobs.length;
                    if (G_current_email_idx == undefined && G_current_json && (G_current_index_pos + G_current_per_page) < no_emails) {
                        listview_header({
                            pos: G_current_index_pos + G_current_per_page
                        }, G_current_json);
                    }
                }
                return;
            case 'ArrowLeft': // quick previous
                if (G_current_json) { // IF list view...
                    if (G_current_email_idx == undefined && G_current_json && (G_current_index_pos - G_current_per_page) >= 0) {
                        listview_header({
                            pos: G_current_index_pos - G_current_per_page
                        }, G_current_json);
                    }
                }
                return;
        }

    }
}

// swipe left/right for next/previous page on mobile
function ponymail_swipe(event) {
    // Only accept "big" swipes
    let len = Math.abs(event.detail.swipestart.coords[0] - event.detail.swipestop.coords[0]);
    let direction = event.detail.swipestart.coords[0] > event.detail.swipestop.coords[0] ? 'left' : 'right';
    if (len < 20) return false;
    if (direction == 'right') {
        if (G_current_json) { // IF list view...
            if (G_current_email_idx == undefined && G_current_json && (G_current_index_pos - G_current_per_page) >= 0) {
                listview_header({
                    pos: G_current_index_pos - G_current_per_page
                }, G_current_json);
            }
        }
    } else if (direction == 'left') {
        if (G_current_json) { // IF list view...
            let blobs = G_current_json.emails;
            if (G_current_listmode == 'threaded') blobs = G_current_json.thread_struct;
            let no_emails = blobs.length;
            if (G_current_email_idx == undefined && G_current_json && (G_current_index_pos + G_current_per_page) < no_emails) {
                listview_header({
                    pos: G_current_index_pos + G_current_per_page
                }, G_current_json);
            }
        }
    }
    return false;
}


/******************************************
 Fetched from source/list-index.js
******************************************/

let list_json = {}

function list_index(state, json) {
    if (json) {
        list_json = json;
    }
    let letter = 'a';
    let lists = document.getElementById('list_picker_ul');
    if (state && state.letter) {
        letter = state.letter;
        for (let xtab of lists.childNodes) {
            if (xtab.innerText == state.letter) {
                xtab.setAttribute("class", 'active');
            } else if (xtab.setAttribute) {
                xtab.setAttribute("class", "");
            }
        }
    } else {
        let letters = 'abcdefghijklmnopqrstuvwxyz#';
        for (let char of letters) {
            let xletter = char.toUpperCase();
            let li = new HTML('li', {
                onclick: 'list_index({letter: "%s"});'.format(xletter),
                class: (xletter == 'A') ? 'active' : null
            }, xletter);
            lists.inject(li);
        }
    }

    let list_ul = document.getElementById('list_index_wide_lists');
    list_ul.textContent = "";
    let domains = Object.keys(list_json.lists);
    domains.sort();
    for (let domain_name of domains) {
        if (is_letter(domain_name, letter)) {
            let li = new HTML('li', {});
            let a = new HTML('a', {
                href: 'list.html?%s'.format(domain_name)
            }, domain_name);
            li.inject(a);
            list_ul.inject(li);
        }
    }
}


function is_letter(domain, letter) {
    if (letter == '#' && domain.match(/^([^a-zA-Z]+)/)) return true
    else return domain.toLowerCase().startsWith(letter.toLowerCase());
}

function list_index_onepage(state, json) {
    let obj = document.getElementById('list_index_child');
    obj.style.padding = '8px';
    let domains = Object.keys(json.lists);
    domains.sort();
    let letter = '';
    for (let domain of domains) {
        let l = domain[0];
        if (l != letter) {
            letter = l;
            let lhtml = new HTML('h2', {}, l.toUpperCase());
            obj.inject(lhtml);
        }
        let a = new HTML('a', {
            href: 'list.html?%s'.format(domain)
        }, domain);
        obj.inject(['- ', a]);
        obj.inject(new HTML('br'));
    }
    if (domains.length > pm_config.LOTS_OF_LISTS) {
        list_index(state, json);
    } else {
        let wide_obj = document.getElementById('list_index_child_wide');
        let new_obj = obj.cloneNode(true);
        new_obj.setAttribute("id", "list_index_child_wide");
        wide_obj.replaceWith(new_obj);
    }
}

// onload function for index.html
function prime_list_index() {
    GET('%sapi/preferences.lua'.format(G_apiURL), list_index_onepage, {});
}


/******************************************
 Fetched from source/listview-flat.js
******************************************/

let compact_email_height = 24;  // a normal email element is 24 pixels high
let preview_email_height = 40;

let narrow_width = 600;  // <= 600 pixels and we're in narrow view

function calc_per_page() {
    // Figure out how many emails per page
    let body = document.body;
    let html = document.documentElement;
    let height = Math.max(body.scrollHeight,
        html.clientHeight, html.scrollHeight);
    let width = Math.max(body.scrollWidth,
        html.clientWidth, html.scrollWidth);
    let email_h = G_current_listmode_compact ? compact_email_height : preview_email_height;
    if (width < narrow_width) {
        email_h = G_current_listmode_compact ? compact_email_height * 1.5 : preview_email_height * 2;
    }
    height -= document.getElementById("emails").getBoundingClientRect().y + 16; // top area height plus footer
    email_h += 2;
    let per_page = Math.max(5, Math.floor(height / email_h));
    per_page -= per_page % 5;
    return per_page;
}

function listview_flat(json, start) {
    let list = document.getElementById('emails');
    list.innerHTML = "";

    let s = start || 0;
    let n;
    if (json.emails && json.emails.length) {
        for (n = s; n < (s + G_current_per_page); n++) {
            let z = json.emails.length - n - 1; // reverse order by default
            if (json.emails[z]) {
                let item = listview_flat_element(json.emails[z], z);
                list.inject(item);

                // Hidden placeholder for expanding email(s)
                let placeholder = new HTML('div', {
                    class: G_chatty_layout ? 'email_placeholder_chatty' : 'email_placeholder',
                    id: 'email_%u'.format(z)
                });
                list.inject(placeholder);
            }
        }
    } else {
        list.inject(txt("No emails found..."));
    }
}

function listview_flat_element(eml, idx) {

    let link_wrapper = new HTML('a', {
        href: 'thread/%s'.format(eml.id),
        onclick: 'return(expand_email_threaded(%u, true));'.format(idx)
    });

    let element = new HTML('div', {
        class: G_current_listmode_compact ? "listview_email_compact" : "listview_email_flat"
    }, " ");

    // Add gravatar
    let gravatar = new HTML('img', {
        class: "gravatar",
        src: GRAVATAR_URL.format(eml.gravatar)
    });
    element.inject(gravatar);


    // Add author
    let authorName = eml.from.replace(/\s*<.+>/, "").replace(/"/g, '');
    let authorEmail = eml.from.match(/\s*<(.+@.+)>\s*/);
    if (authorName.length == 0) authorName = authorEmail ? authorEmail[1] : "(No author?)";
    let author = new HTML('span', {
        class: "listview_email_author"
    }, authorName);
    element.inject(author);

    // reasons to show the list name
    let showList = G_current_domain == 'inbox' || G_current_list == '*' || G_current_domain == '*';

    // If space and needed, inject ML name
    if (!G_current_listmode_compact && showList) {
        author.style.lineHeight = '16px';
        author.inject(new HTML('br'));
        author.inject(new HTML('span', {
            class: "label label-primary",
            style: "font-style: italic; font-size: 1rem;"
        }, eml.list_raw.replace(/[<>]/g, '').replace('.', '@', 1)));
    }

    // Combined space for subject + body teaser
    let as = new HTML('div', {
        class: 'listview_email_as'
    });

    let suba = new HTML('a', {}, eml.subject === '' ? '(No subject)' : eml.subject);
    if (G_current_listmode_compact && showList) {
        let kbd = new HTML('kbd', {
            class: 'listview_kbd'
        }, eml.list_raw.replace(/[<>]/g, '').replace('.', '@', 1))
        suba = [kbd, suba];
    }
    let subject = new HTML('div', {
        class: 'listview_email_subject email_unread'
    }, suba);
    as.inject(subject);
    if (!G_current_listmode_compact) { // No body in compact mode
        let body = new HTML('div', {
            class: 'listview_email_body'
        }, eml.body);
        as.inject(body);
    }

    element.inject(as);

    // Labels
    let labels = new HTML('div', {
        class: 'listview_email_labels'
    });

    let date = new Date(eml.epoch * 1000.0);
    let now = new Date();

    let dl = new HTML('span', {
        class: 'label label-default'
    }, date.ISOBare());
    if (now - date < 86400000) {
        dl.setAttribute("class", "label label-primary");
    }
    labels.inject(dl);

    element.inject(labels);
    link_wrapper.inject(element);

    return link_wrapper;
}


/******************************************
 Fetched from source/listview-header.js
******************************************/

let prev_listview_json = {};
let prev_listview_state = {};

function listview_header(state, json) {
    if (isEmpty(json)) { // Bad search request?
        modal("Bad search request", "Your request could not be parsed.", "warning");
        return;
    }
    let list_title = json.list;
    prev_listview_json = json;
    prev_listview_state = state;
    if (G_current_list == 'virtual' && G_current_domain == 'inbox') {
        list_title = "Virtual inbox, past 30 days";
    }
    let blobs = json.emails ? json.emails : [];
    if (G_current_listmode == 'threaded' || G_current_listmode == 'treeview') blobs = json.thread_struct;

    if (G_current_year && G_current_month) {
        list_title += ", %s %u".format(MONTHS[G_current_month - 1], G_current_year);
    } else {
        list_title += ", past month";
    }

    if (json.searchParams && (
            json.searchParams.q &&
            json.searchParams.q.length ||
            (json.searchParams.d || "").match(/=/))
    ){
        list_title = "Custom search";
    }
    document.title = list_title + " - " + prefs.title;
    document.getElementById('listview_title').innerText = list_title + ":";
    let download = new HTML('button', {
        title: 'Download as mbox archive',
        download: 'true'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-save'
    }, " "));
    document.getElementById('listview_title').inject(download);
    download.addEventListener('click', () => {
        let sep = '?';
        let dl_url = G_apiURL + 'api/mbox.lua';
        for (let key in json.searchParams || {}) {
            dl_url += sep + key + "=" + encodeURIComponent(json.searchParams[key]);
            sep = '&';
        }
        location.href = dl_url;
    });

    let chevrons = document.getElementById('listview_chevrons');
    G_current_per_page = calc_per_page();
    G_current_index_pos = state.pos || 0;
    let first = 1;
    if (state && state.pos) {
        first = 1 + state.pos;
    }
    if (!blobs || blobs.length == 0) {
        chevrons.innerHTML = "No topics to show";
        blobs = [];
    } else {
        chevrons.innerHTML = "Showing <b>%u through %u</b> of <b>%u</b> topics&nbsp;".format(first, Math.min(first + G_current_per_page - 1, blobs.length), blobs.length || 0);
    }

    let pprev = Math.max(0, first - G_current_per_page - 1);
    let cback = new HTML('button', {
        onclick: 'listview_header({pos: %u}, G_current_json);'.format(pprev),
        disabled: (first == 1) ? 'true' : null
    }, new HTML('span', {
        class: 'glyphicon glyphicon-chevron-left'
    }, " "));
    chevrons.inject(cback);

    let pnext = first + G_current_per_page - 1;
    let cforward = new HTML('button', {
        onclick: 'listview_header({pos: %u}, G_current_json);'.format(pnext),
        disabled: (first + G_current_per_page - 1 >= blobs.length) ? 'true' : null
    }, new HTML('span', {
        class: 'glyphicon glyphicon-chevron-right'
    }, " "));
    chevrons.inject(cforward);

    let crefresh = new HTML('button', {
        onclick: 'parseURL({noprefs: true});',
        title: 'Refresh results',
        style: {
            marginLeft: '8px'
        }
    }, new HTML('span', {
        class: 'glyphicon glyphicon-refresh'
    }, " "));
    chevrons.inject(crefresh);
    if (state && state.pos != undefined) {
        if (G_current_listmode == 'threaded') {
            listview_threaded(json, state.pos);
        } else if (G_current_listmode == 'flat') {
            listview_flat(json, state.pos);
        } else {
            listview_treeview(json, state.pos);
        }
    }

}

function listview_list_lists(state, json) {
    let lists = document.getElementById('list_picker_ul');
    let searching = (state && state.search === true) ? true : false;
    if (state && state.to) {
        let tab;
        let tabs = lists.childNodes;
        for (let xtab of tabs) {
            if ((state.to == 'search' && xtab.getAttribute('id') == 'tab_search') || (xtab.innerText == state.to || xtab.getAttribute('data-list') == state.to)) {
                tab = xtab;
                tab.setAttribute("class", state.to == 'search' ? 'search' : 'active');
            } else if (xtab.getAttribute("class") != 'list_all_narrow' && xtab.getAttribute("class") != 'others') {
                xtab.setAttribute("class", "");
            }

        }
        return;
    }
    if (!json) {
        json = G_ponymail_preferences;
    }
    if (lists) {
        lists.innerHTML = "";

        if (isHash(json.lists) && json.lists[G_current_domain]) {
            let lists_sorted = [];
            for (let list in json.lists[G_current_domain]) {
                lists_sorted.push([list, json.lists[G_current_domain][list]]);
            }
            lists_sorted.sort((a, b) => b[1] - a[1]);
            let alists = [];
            for (let list of lists_sorted) alists.push(list[0]);
            if (G_current_list != '*' && G_current_domain != '*') {
                alists.remove(G_current_list);
                alists.unshift(G_current_list);
            }
            let maxlists = (searching && 3 || 4);
            if (alists.length == maxlists + 1) maxlists++; // skip drop-down if only one additional list (#54)
            for (let i = 0; i < alists.length; i++) {
                if (i >= maxlists) break;
                let listname = alists[i];
                let listnametxt = listname;
                if (pm_config.long_tabs) {
                    listnametxt = '%s@%s'.format(listname, G_current_domain);
                }
                let li = new HTML('li', {
                    onclick: 'switch_list(this, "tab");',
                    class: (listname == G_current_list && !searching) ? 'active' : null
                }, listnametxt);
                li.setAttribute("data-list", '%s@%s'.format(listname, G_current_domain));
                lists.inject(li);
            }

            if (alists.length > maxlists) {
                let other_lists_sorted = [];
                for (let i = maxlists; i < alists.length; i++) {
                    other_lists_sorted.push(alists[i]);
                }
                other_lists_sorted.sort();
                let li = new HTML('li', {
                    class: 'others'
                });
                let otherlists = new HTML('select', {
                    class: 'listview_others',
                    onchange: 'switch_list(this.value);'
                });
                otherlists.inject(new HTML('option', {
                    disabled: 'disabled',
                    selected: 'selected'
                }, 'Other lists (%u):'.format(other_lists_sorted.length)));
                li.inject(otherlists);
                for (let listname of other_lists_sorted) {
                    let opt = new HTML('option', {
                        value: "%s@%s".format(listname, G_current_domain)
                    }, listname);
                    otherlists.inject(opt);
                }
                lists.inject(li);
            }
            // All lists, for narrow UI
            let all_lists_narrow = [];
            for (let alist of alists) {
                all_lists_narrow.push(alist);
            }
            all_lists_narrow.sort();
            let li = new HTML('li', {
                class: 'list_all_narrow'
            });
            let otherlists = new HTML('select', {
                class: 'listview_others',
                onchange: 'switch_list(this.value);'
            });
            otherlists.inject(new HTML('option', {
                disabled: 'disabled',
                selected: 'selected'
            }, "%s@%s".format(G_current_list, G_current_domain)));
            li.inject(otherlists);
            for (let listname of all_lists_narrow) {
                let opt = new HTML('option', {
                    value: "%s@%s".format(listname, G_current_domain)
                }, listname);
                otherlists.inject(opt);
            }
            lists.inject(li);
        }
    }
    if (searching) {
        let li = new HTML('li', {
            onclick: 'switch_list(this, "tab");',
            id: 'tab_search',
            class: 'search'
        }, "Search: %s".format(state.query));
        li.setAttribute("data-url", state.url);
        li.setAttribute("data-href", location.href);
        li.setAttribute("data-list", '%s@%s'.format(state.list, state.domain));
        lists.inject(li);
    }

    // Populate the project selector
    if (isHash(json.lists)) {
        let no_projects = 0;
        let select = document.getElementById('project_select');
        if (!select || G_select_primed) return;
        let opts = {}
        let doms = [];
        for (let domain in json.lists) {
            let option = new HTML('option', {
                value: domain
            }, domain);
            opts[domain] = option;
            doms.push(domain);
            no_projects++;
        }
        if (no_projects > 1 || G_current_domain == '*') {
            select.innerHTML = "";
            let title = new HTML('option', {
                disabled: 'disabled',
                selected: 'true',
                value: ''
            }, "Available projects (%u):".format(no_projects));
            select.inject(title);
            doms.sort();
            for (let dom of doms) {
                select.inject(opts[dom]);
            }
            select.style.display = "inline-block";
            G_select_primed = true; // mark it primed so we don't generate it again later
        }
    }
}


function switch_project(domain) {
    // TODO: improve this
    if (G_ponymail_preferences && G_ponymail_preferences.lists[domain]) {
        // Switch to the most populous, but not commits/cvs
        let lists_sorted = [];
        for (let list in G_ponymail_preferences.lists[domain]) {
            lists_sorted.push([list, G_ponymail_preferences.lists[domain][list]]);
        }
        lists_sorted.sort((a, b) => b[1] - a[1]);
        let lists = [];
        for (let list of lists_sorted) lists.push(list[0]);
        let listname = lists[0];
        let n = 1;
        if (lists.length > n) {
            while (pm_config.boring_lists.has(listname) && lists.length > n) {
                listname = lists[n];
                n++;
            }
            if (lists.has(pm_config.favorite_list)) {
                listname = pm_config.favorite_list;
            }
        }
        switch_list('%s@%s'.format(listname, domain));
    } else {
        switch_list('%s@%s'.format(pm_config.favorite_list, domain));
    }
}

function switch_list(list, from) {
    let listid = list;
    if (typeof list == 'object') {
        listid = list.getAttribute("data-list") || list.innerText;
        let dataURL = list.getAttribute('data-url');
        if (dataURL) {
            let bits = listid.split("@");
            G_current_list = bits[0];
            G_current_domain = bits[1];
            GET(dataURL, renderListView, {
                search: true,
                cached: true
            });
            let newhref = list.getAttribute('data-href');
            if (location.href !== newhref) {
                window.history.pushState({}, null, newhref);
            }
            listview_list_lists({
                to: 'search'
            });
            return;
        }
    }
    let bits = listid.split("@");
    G_current_list = bits[0];
    G_current_domain = bits[1];
    G_current_year = 0;
    G_current_month = 0;

    let newhref = "list.html?%s".format(listid);
    if (location.href !== newhref) {
        window.history.pushState({}, null, newhref);
    }

    listview_list_lists({
        to: from ? listid : undefined
    });
    post_prime({
        cached: true,
        from: from
    });
}

window.addEventListener('orientationchange', function() {
    window.setTimeout(function() {
        if (anyOpen() == false && location.href.match(/\/list(\.html)?/) && location.search.length) {
            listview_header(prev_listview_state, prev_listview_json);
        }
    }, 100);
}, false);


/******************************************
 Fetched from source/listview-threaded.js
******************************************/

function calc_email_width() {
    // Get email width; used for calculating reply nesting offsets
    let body = document.body;
    let html = document.documentElement;
    return Math.max(body.scrollWidth, body.offsetWidth,
        html.clientWidth, html.scrollWidth, html.offsetWidth);
}

function listview_threaded(json, start) {
    let list = document.getElementById('emails');
    list.innerHTML = "";

    let s = start || 0;
    if (json.thread_struct && json.thread_struct.length) {
        for (let n = s; n < (s + G_current_per_page); n++) {
            let z = json.thread_struct.length - n - 1; // reverse order by default
            if (json.thread_struct[z]) {
                let item = listview_threaded_element(json.thread_struct[z], z);
                list.inject(item);
                // Hidden placeholder for expanding email(s)
                let placeholder = new HTML('div', {
                    class: G_chatty_layout ? 'email_placeholder_chatty' : 'email_placeholder',
                    id: 'email_%u'.format(z)
                });
                list.inject(placeholder);
            }
        }
    } else {
        list.inject(txt("No emails found..."));
    }
}

function find_email(id) {
    if (!G_current_json.emails) return null;
    for (let email of G_current_json.emails) {
        if (email.id == id) return email;
    }
    return null;
}

function count_replies(thread) {
    let reps = 0;
    if (isArray(thread.children)) {
        for (let child of thread.children) {
            if (child.tid == thread.tid) reps--;
            reps++;
            reps += count_replies(child);
        }
    }
    return reps;
}

function count_people(thread, hash) {
    let ppl = hash || {};
    let eml = find_email(thread.tid);
    if (eml) ppl[eml.from] = true;
    if (isArray(thread.children)) {
        for (let child of thread.children) {
            count_people(child, ppl);
        }
    }
    let n = 0;
    for (let _ in ppl) n++;
    return n;
}


function last_email(thread) {
    let newest = thread.epoch;
    if (isArray(thread.children)) {
        for (let child of thread.children) {
            newest = Math.max(newest, last_email(child));
        }
    }
    return newest;
}



function listview_threaded_element(thread, idx) {
    let eml = find_email(thread.tid);
    if (!eml) {
        return;
    }

    let link_wrapper = new HTML('a', {
        href: 'thread/%s'.format(eml.id),
        onclick: 'return(expand_email_threaded(%u));'.format(idx)
    });

    let element = new HTML('div', {
        class: G_current_listmode_compact ? "listview_email_compact" : "listview_email_flat"
    }, " ");
    let date = new Date(eml.epoch * 1000.0);
    let now = new Date();

    // Add gravatar
    let gravatar = new HTML('img', {
        class: "gravatar",
        src: GRAVATAR_URL.format(eml.gravatar)
    });
    element.inject(gravatar);


    // Add author
    let authorName = eml.from.replace(/\s*<.+>/, "").replace(/"/g, '');
    let authorEmail = eml.from.match(/\s*<(.+@.+)>\s*/);
    if (authorName.length == 0) authorName = authorEmail ? authorEmail[1] : "(No author?)";
    let author = new HTML('span', {
        class: "listview_email_author"
    }, authorName);
    element.inject(author);

    // reasons to show the list name
    let showList = G_current_domain == 'inbox' || G_current_list == '*' || G_current_domain == '*';

    // If space and needed, inject ML name
    if (!G_current_listmode_compact && showList) {
        author.style.lineHeight = '16px';
        author.inject(new HTML('br'));
        author.inject(new HTML('span', {
            class: "label label-primary",
            style: "font-style: italic; font-size: 1rem;"
        }, eml.list_raw.replace(/[<>]/g, '').replace('.', '@', 1)));
    }



    // Combined space for subject + body teaser
    let as = new HTML('div', {
        class: 'listview_email_as'
    });

    let suba = new HTML('a', {}, eml.subject === '' ? '(No subject)' : eml.subject);
    if (G_current_listmode_compact && showList) {
        let kbd = new HTML('kbd', {
            class: 'listview_kbd'
        }, eml.list_raw.replace(/[<>]/g, '').replace('.', '@', 1))
        suba = [kbd, suba];
    }
    let subject = new HTML('div', {
        class: 'listview_email_subject email_unread'
    }, suba);
    as.inject(subject);

    if (!G_current_listmode_compact) { // No body teaser in compact mode
        let body = new HTML('div', {
            class: 'listview_email_body'
        }, eml.body);
        as.inject(body);
    }

    element.inject(as);

    // Labels
    let labels = new HTML('div', {
        class: 'listview_email_labels'
    });


    // Participants
    let ppl = count_people(thread);
    let ptitle = (ppl == 1) ? "one participant" : "%u participants".format(ppl);
    let people = new HTML('span', {
        class: 'label label-default',
        title: ptitle
    }, [
        new HTML('span', {
            class: 'glyphicon glyphicon-user'
        }, ' '),
        " %u".format(ppl)
    ]);
    labels.inject(people);

    // Replies
    let reps = count_replies(thread);
    let rtitle = (reps == 1) ? "one reply" : "%u replies".format(reps);
    let repl = new HTML('span', {
        class: 'label label-default',
        title: rtitle
    }, [
        new HTML('span', {
            class: 'glyphicon glyphicon-envelope'
        }, ' '),
        " %u".format(reps)
    ]);
    labels.inject(repl);

    // Date
    date = new Date(last_email(thread) * 1000.0);
    let dl = new HTML('span', {
        class: 'label label-default'
    }, date.ISOBare());
    if (now - date < 86400000) {
        dl.setAttribute("class", "label label-primary");
    }
    labels.inject(dl);

    element.inject(labels);
    link_wrapper.inject(element);

    return link_wrapper;
}


/******************************************
 Fetched from source/listview-treeview.js
******************************************/

function email_idx(email) {
    // Locates the index position of an email in our current json storage
    for (const [idx, eml] of G_current_json.emails.entries()) {
        if (eml.id === email.id) {
            return idx
        }
    }
    return 0
}

function listview_treeview(json, start) {
    let list = document.getElementById('emails');
    list.innerHTML = "";
    let s = start || 0;
    let email_ordered = [];
    for (let thread of json.thread_struct) {
        let eml = find_email(thread.tid);
        if (eml) email_ordered.push(eml);
        for (let child of thread.children) {
            let eml = find_email(child.tid);
            if (eml) email_ordered.push(eml);
        }
    }
    if (email_ordered.length) {
        for (let n = s; n < (s + G_current_per_page); n++) {
            let z = email_ordered.length - n - 1; // reverse order by default
            if (email_ordered[z]) {
                let item = listview_flat_element(email_ordered[z], email_idx(email_ordered[z]));
                list.inject(item);

                // Hidden placeholder for expanding email(s)
                let placeholder = new HTML('div', {
                    class: G_chatty_layout ? 'email_placeholder_chatty' : 'email_placeholder',
                    id: 'email_%u'.format(z)
                });
                list.inject(placeholder);
            }
        }
    } else {
        list.inject(txt("No emails found..."));
    }
}


/******************************************
 Fetched from source/mgmt.js
******************************************/

let admin_current_email = null;
let admin_email_meta = {};
let audit_page = 0;
let audit_size = 30;
let mgmt_prefs = {}

async function POST(url, formdata, state) {
    const resp = await fetch(url, {
        credentials: "same-origin",
        mode: "same-origin",
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: formdata
    });
    return resp
}

// Removes an attachment from the archives
async function admin_del_attachment(hash) {
    if (!confirm("Are you sure you wish remove this attachment from the archives?")) {
        return
    }
    // rewrite attachments for email
    let new_attach = [];
    for (let el of admin_email_meta.attachments) {
        if (el.hash != hash) {
            new_attach.push(el);
        }
    }
    admin_email_meta.attachments = new_attach;
    let formdata = JSON.stringify({
        action: "delatt",
        document: hash
    });
    // remove attachment
    let rv = await POST('%sapi/mgmt.json'.format(G_apiURL), formdata, {});
    let response = await rv.text();

    // Edit email in place
    admin_save_email(true);

    if (rv.status == 200) {
        modal("Attachment removed", "Server responded with: " + response, "help");
    } else {
        modal("Something went wrong!", "Server responded with: " + response, "error");
    }
}

// Hides an email from the archives
async function admin_hide_email() {
    if (!confirm("Are you sure you wish to hide this email from the archives?")) {
        return
    }
    let formdata = JSON.stringify({
        action: "hide",
        document: admin_current_email
    });
    let rv = await POST('%sapi/mgmt.json'.format(G_apiURL), formdata, {});
    let response = await rv.text();
    if (rv.status == 200) {
        modal("Email hidden", "Server responded with: " + response, "help");
    } else {
        modal("Something went wrong!", "Server responded with: " + response, "error");
    }
}

async function admin_unhide_email() {
    if (!confirm("Are you sure you wish to unhide this email?")) {
        return
    }
    let formdata = JSON.stringify({
        action: "unhide",
        document: admin_current_email
    });
    let rv = await POST('%sapi/mgmt.json'.format(G_apiURL), formdata, {});
    let response = await rv.text();
    if (rv.status == 200) {
        modal("Email unhidden", "Server responded with: " + response, "help");
    } else {
        modal("Something went wrong!", "Server responded with: " + response, "error");
    }
}


// Fully deletes an email from the archives
async function admin_delete_email() {
    if (!confirm("Are you sure you wish to remove this email from the archives?")) {
        return
    }
    let formdata = JSON.stringify({
        action: "delete",
        document: admin_current_email
    });
    let rv = await POST('%sapi/mgmt.json'.format(G_apiURL), formdata, {});
    let response = await rv.text();
    if (rv.status == 200) {
        modal("Email removed", "Server responded with: " + response, "help");
    } else {
        modal("Something went wrong!", "Server responded with: " + response, "error");
    }
}

// Saves an email with edits
async function admin_save_email(edit_attachment = false) {
    let from = document.getElementById('email_from').value;
    let subject = document.getElementById('email_subject').value;
    let listname = document.getElementById('email_listname').value;
    let is_private = document.getElementById('email_private').value;
    let body = document.getElementById('email_body').value;
    let attach = null;
    if (edit_attachment) {
        attach = admin_email_meta.attachments;
    }
    let formdata = JSON.stringify({
        action: "edit",
        document: admin_current_email,
        from: from,
        subject: subject,
        list: listname,
        private: is_private,
        body: body,
        attachments: attach
    })
    let rv = await POST('%sapi/mgmt.json'.format(G_apiURL), formdata, {});
    let response = await rv.text();
    if (edit_attachment && rv.status == 200) return
    if (rv.status == 200) {
        modal("Email changed", "Server responded with: " + response, "help");
    } else {
        modal("Something went wrong!", "Server responded with: " + response, "error");
    }
}

function admin_email_preview(stats, json) {
    admin_current_email = json.mid;
    admin_email_meta = json;
    let cp = document.getElementById("panel");
    let div = new HTML('div', {
        style: {
            margin: '5px'
        }
    });
    cp.inject(div);

    div.inject(new HTML('h1', {}, "Editing email " + json.mid + ":"));

    // Author
    let author_field = new HTML('div', {
        class: 'email_kv_edit'
    });
    let author_key = new HTML('div', {
        class: 'email_key'
    }, "From: ");
    let author_value = new HTML('input', {
        id: 'email_from',
        style: {
            width: "480px"
        },
        value: json.from
    });
    author_field.inject([author_key, author_value]);
    div.inject(author_field);

    // Subject
    let subject_field = new HTML('div', {
        class: 'email_kv_edit'
    });
    let subject_key = new HTML('div', {
        class: 'email_key'
    }, "Subject: ");
    let subject_value = new HTML('input', {
        id: 'email_subject',
        style: {
            width: "480px"
        },
        value: json.subject
    });
    subject_field.inject([subject_key, subject_value]);
    div.inject(subject_field);

    // Date
    let date_field = new HTML('div', {
        class: 'email_kv_edit'
    });
    let date_key = new HTML('div', {
        class: 'email_key'
    }, "Date: ");
    let date_value = new HTML('div', {
        class: 'email_value'
    }, new Date(json.epoch * 1000.0).ISOBare());
    date_field.inject([date_key, date_value]);
    div.inject(date_field);

    // List
    let listname = json.list_raw.replace(".", "@", 1).replace(/[<>]/g, "");
    let list_field = new HTML('div', {
        class: 'email_kv_edit'
    });
    let list_key = new HTML('div', {
        class: 'email_key'
    }, "List: ");
    let list_value = new HTML('input', {
        id: 'email_listname',
        style: {
            width: "480px"
        },
        value: listname
    });
    list_field.inject([list_key, list_value]);
    div.inject(list_field);

    // Private email?
    let priv_field = new HTML('div', {
        class: 'email_kv_edit'
    });
    let priv_key = new HTML('div', {
        class: 'email_key'
    }, "Visibility: ");
    let priv_value = new HTML('select', {
        id: 'email_private'
    });
    priv_value.inject(new HTML('option', {
        value: 'no',
        style: {
            color: 'green'
        },
        selected: json.private ? null : "selected"
    }, "Public"));
    priv_value.inject(new HTML('option', {
        value: 'yes',
        style: {
            color: 'red'
        },
        selected: json.private ? "selected" : null
    }, "Private"));
    priv_field.inject([priv_key, priv_value]);
    div.inject(priv_field);

    // Attachments?
    if (json.attachments && json.attachments.length > 0) {
        let attach_field = new HTML('div', {
            class: 'email_kv'
        });
        let attach_key = new HTML('div', {
            class: 'email_key'
        }, "Attachment(s): ");
        let alinks = [];
        for (let attachment of json.attachments) {
            let link = `${G_apiURL}api/email.lua?attachment=true&id=${encodeURIComponent(json.mid)}&file=${encodeURIComponent(attachment.hash)}`;
            let a = new HTML('a', {
                href: link,
                target: '_blank'
            }, attachment.filename);
            alinks.push(a);
            let fs = ` ${attachment.size} bytes`;
            if (attachment.size >= 1024) fs = ` ${Math.floor(attachment.size/1024)} KB`;
            if (attachment.size >= 1024 * 1024) fs = ` ${Math.floor(attachment.size/(1024*10.24))/100} MB`;
            alinks.push(fs);
            let adel = new HTML('a', {
                onclick: `admin_del_attachment('${attachment.hash}');`,
                href: "javascript:void(0);"
            }, "Delete attachment");
            alinks.push(adel);
            alinks.push(new HTML('br'));
        }
        let attach_value = new HTML('div', {
            class: 'email_value'
        }, alinks);
        attach_field.inject([attach_key, attach_value]);
        div.inject(attach_field);
    }

    let text = new HTML('textarea', {
        id: 'email_body',
        style: {
            width: "100%",
            height: "480px"
        }
    }, json.body);
    div.inject(text);

    let btn_edit = new HTML('button', {
        onclick: "admin_save_email();"
    }, "Save changes to archive");
    let btn_del = new HTML('button', {
        onclick: "admin_delete_email();",
        style: {
            marginLeft: "36px",
            color: 'red'
        }
    }, "Delete email from archives");

    let btn_hide = new HTML('button', {
        onclick: "admin_hide_email();",
        style: {
            marginLeft: "36px",
            color: 'purple'
        }
    }, "Hide email from archives");
    if (admin_email_meta.deleted) {
        btn_hide = new HTML('button', {
            onclick: "admin_unhide_email();",
            style: {
                marginLeft: "36px",
                color: 'purple'
            }
        }, "Unhide email from archives");
    }

    div.inject(new HTML('br'));
    div.inject(btn_edit);
    div.inject(btn_hide);
    div.inject(btn_del);
    div.inject(new HTML('br'));
    div.inject(new HTML('small', {}, "Modifying emails will remove the option to view their sources via the web interface, as the source may contain traces that reveal the edit."))
    div.inject(new HTML('br'));
    if (!mgmt_prefs.login.credentials.fully_delete) {
        div.inject(new HTML('small', {}, "Emails that are deleted may still be recovered by the base system administrator. For complete expungement, please contact the system administrator."))
    } else {
        div.inject(new HTML('small', {style:{color: 'red'}}, "As full delete enforcement is enabled on this server, emails are removed forever from the archive when deleted, and cannot be recovered."))
    }
}

function admin_audit_view(state, json) {
    let headers = ['Date', 'Author', 'Remote', 'Action', 'Target', 'Log'];
    let cp = document.getElementById("panel");
    let div = document.getElementById('auditlog_entries');
    if (!div) {
        div = new HTML('div', {
            id: "auditlog",
            style: {
                margin: '5px'
            }
        });
        cp.inject(div);
        div.inject(new HTML('h1', {}, "Audit log:"));
    }
    let table = document.getElementById('auditlog_entries');
    if (json.entries && json.entries.length > 0 || table) {
        if (!table) {
            table = new HTML('table', {
                border: "1",
                id: "auditlog_entries",
                class: "auditlog_entries"
            });
            let trh = new HTML('tr');
            for (let header of headers) {
                let th = new HTML('th', {}, header + ":");
                trh.inject(th);
            }
            table.inject(trh)
            div.inject(table);
            let btn = new HTML('button', {
                onclick: "admin_audit_next();"
            }, "Load more entries");
            div.inject(btn);
        }
        for (let entry of json.entries) {
            let tr = new HTML('tr', {
                class: "auditlog_entry"
            });
            for (let header of headers) {
                let key = header.toLowerCase();
                let value = entry[key];
                if (key == 'target') {
                    value = new HTML('a', {
                        href: "/admin/" + value
                    }, value);
                }
                if (key == 'action') {
                    let action_colors = {
                        edit: 'blue',
                        delete: 'red',
                        default: 'black'
                    };
                    value = new HTML('spam', {
                        style: {
                            color: action_colors[value] ? action_colors[value] : action_colors['default']
                        }
                    }, value);
                }
                let th = new HTML('td', {}, value);
                tr.inject(th);
            }
            table.inject(tr);
        }
    } else {
        div.inject("Audit log is empty");
    }
}

function admin_audit_next() {
    audit_page++;
    GET('%sapi/mgmt.json?action=log&page=%u&size=%u'.format(G_apiURL, audit_page, audit_size), admin_audit_view, null);
}

// Onload function for admin.html
function admin_init() {
    init_preferences(); // blank call to load defaults like social rendering
    GET('%sapi/preferences.lua'.format(G_apiURL), (state, json) => {
        mgmt_prefs = json
        init_preferences(state, json);
    }, null);
    let mid = decodeURIComponent(location.href.split('/').pop());
    // Specific email/list handling?
    if (mid.length > 0) {
        // List handling?
        if (mid.match(/^<.+>$/)) {

        }
        // Email handling?
        else {
            GET('%sapi/email.json?id=%s'.format(G_apiURL, encodeURIComponent(mid)), admin_email_preview, null);
        }
    } else { // View audit log
        GET('%sapi/mgmt.json?action=log&page=%s&size=%u'.format(G_apiURL, audit_page, audit_size), admin_audit_view, null);
    }
}


/******************************************
 Fetched from source/preferences.js
******************************************/

// logout: log out a user
// call the logout URL, then refresh this page - much simple!
function logout() {
    GET("%sapi/preferences.lua?logout=true".format(G_apiURL), () => location.href = document.location);
}

function init_preferences(state, json) {
    G_ponymail_preferences = json || {};
    // First, load session local settings, if possible
    if (G_can_store) {
        let local_preferences = window.localStorage.getItem('G_ponymail_preferences');
        if (local_preferences) {
            let ljson = JSON.parse(local_preferences);
            if (ljson.G_chatty_layout !== undefined) {
                G_chatty_layout = ljson.G_chatty_layout;
            }
            if (ljson.G_current_listmode !== undefined) {
                G_current_listmode = ljson.G_current_listmode;
            }
            if (ljson.G_current_listmode_compact !== undefined) {
                G_current_listmode_compact = ljson.G_current_listmode_compact;
            }
            if (ljson.G_show_stats_sidebar !== undefined) {
                G_show_stats_sidebar = ljson.G_show_stats_sidebar;
            }
        }
    }

    // Set chatty/plain email rendering mode:
    let cl = document.getElementById('chatty_link'); //  legacy button
    if (cl) {
        cl.setAttribute("class", G_chatty_layout ? "enabled" : "disabled");
    }
    let cle = document.getElementById('email_mode_chatty');
    if (cle) {
        cle.checked = G_chatty_layout;
    }
    let cld = document.getElementById('email_mode_plain');
    if (cld) {
        cld.checked = !G_chatty_layout;
    }
    let cla = document.getElementById('G_show_stats_sidebar');
    if (cla) {
        cla.checked = G_show_stats_sidebar;
    }

    // Set list display mode:
    let dmt = document.getElementById('display_mode_threaded');
    if (dmt) {
        dmt.checked = (G_current_listmode == 'threaded');
    }
    let dmf = document.getElementById('display_mode_flat');
    if (dmf) {
        dmf.checked = (G_current_listmode == 'flat');
    }
    let dmtr = document.getElementById('display_mode_treeview');
    if (dmtr) {
        dmtr.checked = (G_current_listmode == 'treeview');
    }

    // Compact list view
    let dmc = document.getElementById('display_mode_compact');
    if (dmc) {
        dmc.checked = G_current_listmode_compact;
    }



    if (G_ponymail_preferences.login && G_ponymail_preferences.login.credentials) {
        let prefsmenu = document.getElementById('login_dropdown') || document.getElementById('prefs_dropdown');
        let uimg = document.getElementById('uimg');
        uimg.setAttribute("src", "images/user.png");
        uimg.setAttribute("title", "Logged in as %s".format(G_ponymail_preferences.login.credentials.fullname));

        // Generate user menu
        prefsmenu.innerHTML = "";


        let logout = new HTML('a', {
            href: "javascript:void(logout());"
        }, "Log out");
        let li = new HTML('li', {}, logout)
        prefsmenu.inject(li);

    } else {
        let prefsmenu = document.getElementById('login_dropdown') || document.getElementById('prefs_dropdown');
        if (prefsmenu) {
            prefsmenu.innerHTML = "";
            let login = new HTML('a', {
                href: "javascript:location.href='oauth.html';"
            }, "Log In");
            let li = new HTML('li', {}, login)
            prefsmenu.inject(li);
        }
    }

    if (json) {
        listview_list_lists(state, json);
        if (state && state.prime) {
            // If lists is accessible, show it
            if (json.lists[G_current_domain] && (G_current_list == '*' || json.lists[G_current_domain][G_current_list] != undefined)) {
                post_prime(state);
            } else if  (G_current_domain == '*') { // assume a match
                post_prime(state);
            } else { // otherwise, bork
                if (G_current_list.length > 0 && (!json.lists[G_current_domain] || Object.keys(json.lists[G_current_domain]).length > 0)) {
                    let eml = document.getElementById('emails');
                    eml.innerText = "We couldn't find this list. It may not exist or require you to be logged in with specific credentials.";
                    eml.inject(new HTML('br'));
                    eml.inject(new HTML('a', {
                        href: 'oauth.html',
                        onclick: 'location.href="oauth.html";'
                    }, "Click here to log in via OAuth"));
                } else {
                    switch_project(G_current_domain);
                }
            }
        }
    }
}

function save_preferences() {
    if (G_can_store) {
        let ljson = {
            G_chatty_layout: G_chatty_layout,
            G_current_listmode: G_current_listmode,
            G_current_listmode_compact: G_current_listmode_compact,
            G_show_stats_sidebar: G_show_stats_sidebar
        };
        let lstring = JSON.stringify(ljson);
        window.localStorage.setItem('G_ponymail_preferences', lstring);
    }
}


function set_theme(theme, compact_mode) {
    G_current_listmode = theme;
    if (compact_mode !== undefined) {
        G_current_listmode_compact = compact_mode;
    }
    renderListView(G_current_state, G_current_json);
    save_preferences();
}

function set_skin(skin) {
    if (typeof(enable_chatty) === "boolean") {
        G_chatty_layout = enable_chatty;
    } else {
        G_chatty_layout = !G_chatty_layout;
    }
    let cl = document.getElementById('chatty_link');
    if (cl) {
        cl.setAttribute("class", G_chatty_layout ? "enabled" : "disabled");
    }
    hideWindows(true);
    renderListView(G_current_state, G_current_json);
    save_preferences();
}

// set_skin, but for permalinks
function set_skin_permalink(enable_chatty) {
    if (typeof(enable_chatty) === "boolean") {
        G_chatty_layout = enable_chatty;
    } else {
        G_chatty_layout = !G_chatty_layout;
    }
    let cl = document.getElementById('chatty_link');
    if (cl) {
        cl.setAttribute("class", G_chatty_layout ? "enabled" : "disabled");
    }
    hideWindows(true);
    save_preferences();
    parse_permalink();
}

function set_show_stats(display) {
    G_show_stats_sidebar = display;
    if (display === false) {
        document.getElementById('sidebar_stats').style.display = "none";
        document.getElementById('sidebar_wordcloud').style.display = "none";
    } else {
        document.getElementById('sidebar_stats').style.display = "block";
        document.getElementById('sidebar_wordcloud').style.display = "block";
    }
    save_preferences();
    renderCalendar();
}


/******************************************
 Fetched from source/primer.js
******************************************/

/* List View Rendering main func */
function renderListView(state, json) {
    if (json) {
        G_current_json = json;
    }
    G_current_state = state;
    async_escrow['rendering'] = new Date();
    if (!state || state.update_calendar !== false) {
        renderCalendar({
            FY: json.firstYear,
            FM: json.firstMonth,
            LY: json.lastYear,
            LM: json.lastMonth,
            activity: json.active_months
        });
    }
    // sort threads by date
    if (isArray(json.thread_struct)) {
        G_current_json.thread_struct.sort((a, b) => last_email(a) - last_email(b));
    }
    listview_header(state, json);
    if (G_current_listmode == 'threaded') {
        listview_threaded(json, 0);
    } else if (G_current_listmode == 'treeview') {
        listview_treeview(json, 0);
    } else {
        listview_flat(json, 0);
    }

    sidebar_stats(json); // This comes last, takes the longest with WC enabled.
    delete async_escrow['rendering'];

    if (state && state.to) {
        listview_list_lists(state);
    }
}

/* Primer function for List View
 * Fetches the following:
 * - user preferences (api/preferences.lua)
 * When done, we create the scaffolding and list view
 */
function primeListView(state) {
    state = state || {};
    state.prime = true;
    GET('%sapi/preferences.lua'.format(G_apiURL), init_preferences, state);
}

// callback from when prefs have loaded
function post_prime(state) {
    let sURL = '%sapi/stats.lua?list=%s&domain=%s'.format(G_apiURL, encodeURIComponent(G_current_list), encodeURIComponent(G_current_domain));
    if (G_current_year && G_current_month) {
        sURL += "&d=%u-%u".format(G_current_year, G_current_month);
    }
    if (!(state && state.search)) {
        if (state && state.array) {
            G_collated_json = {};
            for (let entry of state.array) {
                let list = entry.split('@');
                sURL = '%sapi/stats.lua?list=%s&domain=%s'.format(G_apiURL, encodeURIComponent(list[0]), encodeURIComponent(list[1]));
                GET(sURL, render_virtual_inbox, state);
            }
        } else {
            GET(sURL, renderListView, state);
        }
    } else {
        search(state.query, state.date);
    }
}

// onload function for list.html
function parseURL(state) {
    let bits = window.location.search.substring(1).split(":", 3);
    let list = bits[0];
    let month = bits[1];
    let query = bits[2];
    state = state || {};
    G_current_month = 0;
    G_current_year = 0;

    // If "month" (year-month) is specified,
    // we should set the current vars
    if (month) {
        try {
            let dbits = month.split("-");
            G_current_year = dbits[0];
            G_current_month = dbits[1];
        } catch (e) {}
    }
    // Is this a valid list?
    if (list !== '') {
        // multi-list??
        if (list.match(/,/)) {
            state.array = list.split(',');
            G_current_domain = 'inbox';
            G_current_list = 'virtual';
        } else {
            let lbits = list.split("@");
            if (lbits.length > 1) {
                G_current_list = lbits[0];
                G_current_domain = lbits[1];
            } else {
                G_current_domain = lbits;
                G_current_list = '';
            }
        }
    }
    // Are we initiating a search?
    if (query || (month && !month.match(/^\d\d\d\d-\d+$/))) { // single-month isn't a search, but any other date marker is
        state.search = true;
        state.query = decodeURIComponent(query||"");
        state.date = month;
    }
    // If hitting the refresh button, don't refresh preferences, just do the search.
    if (state.noprefs) {
        post_prime(state);
    } else {
        primeListView(state);
    }
}



// Parse a permalink and fetch the thread
// URL is expected to be of the form /thread[.html]/<msgid>?<list.id>|find_parent=true
// onload function for thread.html
function parse_permalink() {
    // message id is the bit after the last /
    // TODO: could look for thread[.html]/ instead
    let mid = decodeURIComponent(location.pathname.split('/').pop());
    // List-ID specified?
    // query needs decodeURIComponent with '+' conversion
    const query = decodeURIComponent(location.search.substring(1).replace(/\+/g, ' '));
    let list_id = null;
    let find_parent = false;
    if (query.length) {
        if (query.match(/^<.+>$/)) {
            list_id = query;
        }
        find_parent = query == 'find_parent=true';
    }

    mid = unshortenID(mid);  // In case of old school shortened links
    init_preferences(); // blank call to load defaults like social rendering
    GET('%sapi/preferences.lua'.format(G_apiURL), init_preferences, null);
    // Fetch the thread data and pass to build_single_thread
    if (list_id) {
        GET('%sapi/thread.lua?id=%s&listid=%s'.format(G_apiURL, encodeURIComponent(mid), encodeURIComponent(list_id)), construct_single_thread, {
            cached: true
        });
    }
    else {
        let encoded_mid = encodeURIComponent(mid);
        if (find_parent) {
            GET('%sapi/thread.lua?id=%s&find_parent=true'.format(G_apiURL, encoded_mid), construct_single_thread, {
                cached: true
            });
        } else {
            GET('%sapi/thread.lua?id=%s'.format(G_apiURL, encoded_mid), construct_single_thread, {
                cached: true
            });
        }
    }
}


// Virtual inbox ŕendering
function render_virtual_inbox(state, json) {
    if (json) {
        G_collated_json.emails = G_collated_json.emails || [];
        G_collated_json.thread_struct = G_collated_json.thread_struct || [];
        for (let email of json.emails) {
            G_collated_json.emails.push(email);
        }
        for (let thread_struct of json.thread_struct) {
            G_collated_json.thread_struct.push(thread_struct);
        }
    }

    for (let _ in async_escrow) {
        return;
    }

    if (true) {
        G_current_json = G_collated_json;
        G_current_json.participants = [];

        async_escrow['rendering'] = new Date();
        if (!state || state.update_calendar !== false) {
            renderCalendar({
                FY: json.firstYear,
                FM: json.firstMonth,
                LY: json.lastYear,
                LM: json.lastMonth,
                activity: json.active_months
            });
        }
        // sort threads by date
        if (isArray(json.thread_struct)) {
            G_current_json.thread_struct.sort((a, b) => last_email(a) - last_email(b));
        }
        listview_header(state, G_current_json);
        if (G_current_listmode == 'threaded') {
            listview_threaded(G_current_json, 0);
        } else if (G_current_listmode == 'treeview') {
            listview_treeview(G_current_json, 0);
        } else {
            listview_flat(G_current_json, 0);
        }

        sidebar_stats(G_current_json); // This comes last, takes the longest with WC enabled.
        delete async_escrow['rendering'];
    }
}


// hex <- base 36 conversion, reverses short links
function unshortenID(mid) {
    // all short links begin with 'Z'. If not, it's not a short link
    // so let's just pass it through unaltered if so.
    // Some old shortlinks begin with 'B', so let's be backwards compatible for now.
    // Shortlinks are also 15 chars (including prefix)
    // They should also consist of base 36 chars or '-'
    if ((mid[0] == 'Z' || mid[0] == 'B') && mid.length == 15){
        // remove padding
        let id1 = parseInt(mid.substring(1, 8).replace(/-/g, ""), 36)
        let id2 = parseInt(mid.substring(8, 15).replace(/-/g, ""), 36)
        id1 = id1.toString(16)
        id2 = id2.toString(16)

        // add 0-padding
        while (id1.length < 9) id1 = '0' + id1
        while (id2.length < 9) id2 = '0' + id2
        return id1+id2
    }
    return mid
}


/******************************************
 Fetched from source/render-email.js
******************************************/

// Function for parsing email addresses from a to or cc line
function get_rcpts(addresses) {
    let list_of_emails = []
    if (!addresses) return [] // cc or to may be null
    for (let a of addresses.split(/,\s*/)) {
        let m = a.match(/<(.+)>/);
        if (m) {
            a = m[1];
        }
        if (a && a.length > 5) { // more than a@b.c
            list_of_emails.push(a);
        }
    }
    return list_of_emails;
}

async function render_email(state, json) {
    let div = state.div;
    G_full_emails[json.mid] = json; // Save for composer if replying later...
    if (state.scroll) {
        let rect = div.getBoundingClientRect();
        try {
            window.setTimeout(function() {
                window.scrollTo(0, rect.top - 48);
            }, 200);
        } catch (e) {}
    }
    if (G_chatty_layout) {
        return render_email_chatty(state, json);
    }

    // Author
    let author_field = new HTML('div', {
        class: 'email_kv'
    });
    let author_key = new HTML('div', {
        class: 'email_key'
    }, "From: ");
    let author_value = new HTML('div', {
        class: 'email_value'
    }, json.from);
    author_field.inject([author_key, author_value]);
    div.inject(author_field);

    // Subject
    let subject_field = new HTML('div', {
        class: 'email_kv'
    });
    let subject_key = new HTML('div', {
        class: 'email_key'
    }, "Subject: ");
    let subject_value = new HTML('div', {
        class: 'email_value'
    }, json.subject == '' ? '(No subject)' : json.subject);
    subject_field.inject([subject_key, subject_value]);
    div.inject(subject_field);

    // Date
    let date_field = new HTML('div', {
        class: 'email_kv'
    });
    let date_key = new HTML('div', {
        class: 'email_key'
    }, "Date: ");
    let date_value = new HTML('div', {
        class: 'email_value'
    }, new Date(json.epoch * 1000.0).ISOBare());
    date_field.inject([date_key, date_value]);
    div.inject(date_field);


    // List
    let listname = json.list_raw.replace(".", "@", 1).replace(/[<>]/g, "");
    let list_field = new HTML('div', {
        class: 'email_kv'
    });
    let list_key = new HTML('div', {
        class: 'email_key'
    }, "List: ");
    let list_value = new HTML('div', {
            class: 'email_value'
        },
        new HTML('a', {
            href: 'list?%s'.format(listname)
        }, listname)
    );
    list_field.inject([list_key, list_value]);
    div.inject(list_field);

    // To + CC if need be
    let rcpts = get_rcpts(json.to);
    rcpts.push(...get_rcpts(json.cc));
    rcpts.remove(listname);
    if (rcpts.length) {
        let rcpt_field = new HTML('div', {
            class: 'email_kv'
        });
        let rcpt_key = new HTML('div', {
            class: 'email_key'
        }, "To/Cc: ");
        let rcpt_value = new HTML('div', {
                class: 'email_value'
            },
            new HTML('span', {}, rcpts.join(", "))
    );
        rcpt_field.inject([rcpt_key, rcpt_value]);
        div.inject(rcpt_field);
    }

    // Private email??
    if (json.private === true) {
        let priv_field = new HTML('div', {
            class: 'email_kv'
        });
        let priv_key = new HTML('div', {
            class: 'email_key'
        }, "Private: ");
        let priv_value = new HTML('div', {
            class: 'email_value_emphasis'
        }, "YES");
        priv_field.inject([priv_key, priv_value]);
        div.inject(priv_field);
    }

    // Attachments?
    if (json.attachments && json.attachments.length > 0) {
        let attach_field = new HTML('div', {
            class: 'email_kv'
        });
        let attach_key = new HTML('div', {
            class: 'email_key'
        }, "Attachment(s): ");
        let alinks = [];
        for (let attachment of json.attachments) {
            let link = `${G_apiURL}api/email.lua?attachment=true&id=${json.mid}&file=${attachment.hash}`;
            let a = new HTML('a', {
                href: link,
                target: '_blank'
            }, attachment.filename);
            alinks.push(a);
            let fs = ` ${attachment.size} bytes`;
            if (attachment.size >= 1024) fs = ` ${Math.floor(attachment.size/1024)} KB`;
            if (attachment.size >= 1024 * 1024) fs = ` ${Math.floor(attachment.size/(1024*10.24))/100} MB`;
            alinks.push(fs);
            alinks.push(new HTML('br'));
        }
        let attach_value = new HTML('div', {
            class: 'email_value'
        }, alinks);
        attach_field.inject([attach_key, attach_value]);
        div.inject(attach_field);
    }

    let text = new HTML('pre', {}, fixup_quotes(json.body));
    div.inject(text);

    // Private text?
    if (json.private === true) {
        text.style.backgroundImage = "url(images/private.png)";
    }


    let toolbar = new HTML('div', {
        class: 'toolbar'
    });

    // reply to email button
    let replybutton = new HTML('button', {
        title: "Reply to this email",
        onclick: `compose_email('${json.mid}');`,
        class: 'btn toolbar_btn toolbar_button_reply'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-pencil'
    }, ' '));
    toolbar.inject(replybutton);

    // permalink button
    let linkbutton = new HTML('a', {
        href: 'thread/%s'.format(json.mid),
        target: '_blank',
        title: "Permanent link to this email",
        class: 'btn toolbar_btn toolbar_button_link'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-link'
    }, ' '));
    toolbar.inject(linkbutton);

    // Source-view button
    let sourcebutton = new HTML('a', {
        href: '%sapi/source.lua?id=%s'.format(G_apiURL, encodeURIComponent(json.mid)),
        target: '_blank',
        title: "View raw source",
        class: 'btn toolbar_btn toolbar_button_source'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-file'
    }, ' '));
    toolbar.inject(sourcebutton);

    // Admin button?
    if (G_ponymail_preferences.login && G_ponymail_preferences.login.credentials && G_ponymail_preferences.login.credentials.admin) {
        let adminbutton = new HTML('a', {
            href: 'admin/%s'.format(json.mid),
            target: '_blank',
            title: "Modify email",
            class: 'btn toolbar_btn toolbar_button_admin'
        }, new HTML('span', {
            class: 'glyphicon glyphicon-cog'
        }, ' '));
        toolbar.inject(adminbutton);
    }

    text.inject(toolbar);
}



async function render_email_chatty(state, json) {
    let div = state.div;
    div.parentNode.style.border = 'none';

    // Author
    let when = new Date(json.epoch * 1000.0);
    let ldate = when.toISOString();
    try {
        ldate = "%s %s".format(when.toLocaleDateString(undefined, PONYMAIL_DATE_FORMAT), when.toLocaleTimeString(undefined, PONYMAIL_TIME_FORMAT));
    } catch (e) {

    }

    let author_field = new HTML('div', {
        class: 'chatty_author'
    });
    let gravatar = new HTML('img', {
        class: "chatty_gravatar",
        src: GRAVATAR_URL.format(json.gravatar)
    });
    let author_name = json.from.replace(/\s*<.+>/, "").replace(/"/g, '');
    let author_email = json.from.match(/\s*<(.+@.+)>\s*/);
    if (author_name.length == 0) author_name = author_email ? author_email[1] : "(No author?)";
    let author_nametag = new HTML('div', {
        class: 'chatty_author_name'
    }, [
        new HTML('b', {}, author_name),
        " - %s".format(ldate)
    ]);
    author_field.inject([gravatar, author_nametag]);
    div.inject(author_field);
    let chatty_body = fixup_quotes(json.body);
    if (json.mid == G_current_open_email) {
        let header = new HTML('h4', {
            class: 'chatty_title_inline'
        }, json.subject);
        chatty_body.unshift(header);
    }
    let text = new HTML('pre', {
        class: 'chatty_body'
    }, chatty_body);
    div.inject(text);

    // Private text?
    if (json.private === true) {
        text.style.backgroundImage = "url(images/private.png)";
    }

    // Attachments?
    if (json.attachments && json.attachments.length > 0) {
        let attach_field = new HTML('div', {
            class: 'email_kv'
        });
        let attach_key = new HTML('div', {
            class: 'email_key'
        }, "Attachment(s):");
        let alinks = [];
        for (let attachment of json.attachments) {
            let link = `${G_apiURL}api/email.lua?attachment=true&id=${json.mid}&file=${attachment.hash}`;
            let a = new HTML('a', {
                href: link,
                target: '_blank'
            }, attachment.filename);
            alinks.push(a);
            let fs = ` ${attachment.size} bytes`;
            if (attachment.size >= 1024) fs = ` ${Math.floor(attachment.size/1024)} KB`;
            if (attachment.size >= 1024 * 1024) fs = ` ${Math.floor(attachment.size/(1024*10.24))/100} MB`;
            alinks.push(fs);
            alinks.push(new HTML('br'));
        }
        let attach_value = new HTML('div', {
            class: 'email_value'
        }, alinks);
        attach_field.inject([attach_key, attach_value]);
        text.inject(attach_field);
    }

    let toolbar = new HTML('div', {
        class: 'toolbar_chatty'
    });

    // reply to email button
    let replybutton = new HTML('button', {
        title: "Reply to this email",
        onclick: `compose_email('${json.mid}');`,
        class: 'btn toolbar_btn toolbar_button_reply'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-pencil'
    }, ' '));
    toolbar.inject(replybutton);

    // permalink button
    let linkbutton = new HTML('a', {
        href: 'thread/%s'.format(json.mid),
        title: "Permanent link to this email",
        target: '_blank',
        class: 'btn toolbar_btn toolbar_button_link'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-link'
    }, ' '));
    toolbar.inject(linkbutton);

    // Source-view button
    let sourcebutton = new HTML('a', {
        href: '%sapi/source.lua?id=%s'.format(G_apiURL, encodeURIComponent(json.mid)),
        target: '_blank',
        title: "View raw source",
        class: 'btn toolbar_btn toolbar_button_source'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-file'
    }, ' '));
    toolbar.inject(sourcebutton);

    // Admin button?
    if (G_ponymail_preferences.login && G_ponymail_preferences.login.credentials && G_ponymail_preferences.login.credentials.admin) {
        let adminbutton = new HTML('a', {
            href: 'admin/%s'.format(encodeURIComponent(json.mid)),
            target: '_blank',
            title: "Modify email",
            class: 'btn toolbar_btn toolbar_button_admin'
        }, new HTML('span', {
            class: 'glyphicon glyphicon-cog'
        }, ' '));
        toolbar.inject(adminbutton);
    }

    text.inject(toolbar);
}


/******************************************
 Fetched from source/scaffolding-html.js
******************************************/

/**
 * HTML: DOM creator class
 * args:
 * - type: HTML element type (div, table, p etc) to produce
 * - params: hash of element params to add (class, style etc)
 * - children: optional child or children objects to insert into the new element
 * Example:
 * div = new HTML('div', {
 *    class: "footer",
 *    style: {
 *        fontWeight: "bold"
 *    }
#}, "Some text inside a div")
 */

const txt = (msg) => document.createTextNode(msg);

const HTML = (function() {
    function HTML(type, params, children) {

        /* create the raw element, or clone if passed an existing element */
        if (typeof type === 'object') {
            this.element = type.cloneNode();
        } else {
            this.element = document.createElement(type);
        }

        /* If params have been passed, set them */
        if (isHash(params)) {
            for (let key in params) {
                let val = params[key];

                /* Standard string value? */
                if (typeof val === "string" || typeof val === 'number') {
                    this.element.setAttribute(key, val);
                } else if (isArray(val)) {

                    /* Are we passing a list of data to set? concatenate then */
                    this.element.setAttribute(key, val.join(" "));
                } else if (isHash(val)) {

                    /* Are we trying to set multiple sub elements, like a style? */
                    for (let subkey in val) {
                        let subval = val[subkey];
                        if (!this.element[key]) {
                            throw "No such attribute, " + key + "!";
                        }
                        this.element[key][subkey] = subval;
                    }
                }
            }
        }

        /* If any children have been passed, add them to the element */
        if (children) {

            /* If string, convert to textNode using txt() */
            if (typeof children === "string") {
                this.element.inject(txt(children));
            } else {

                /* If children is an array of elems, iterate and add */
                if (isArray(children)) {
                    let child, j, len;
                    for (j = 0, len = children.length; j < len; j++) {
                        child = children[j];

                        /* String? Convert via txt() then */
                        if (typeof child === "string") {
                            this.element.inject(txt(child));
                        } else {

                            /* Plain element, add normally */
                            this.element.inject(child);
                        }
                    }
                } else {

                    /* Just a single element, add it */
                    this.element.inject(children);
                }
            }
        }
        return this.element;
    }

    return HTML;

})();

/**
 * prototype injector for HTML elements:
 * Example: mydiv.inject(otherdiv)
 */

HTMLElement.prototype.inject = function(child) {
    let item, j, len;
    if (isArray(child)) {
        for (j = 0, len = child.length; j < len; j++) {
            item = child[j];
            if (typeof item === 'string') {
                item = txt(item);
            }
            this.appendChild(item);
        }
    } else {
        if (typeof child === 'string') {
            child = txt(child);
        }
        this.appendChild(child);
    }
    return child;
};



/**
 * prototype for emptying an html element
 */

HTMLElement.prototype.empty = function() {
    let ndiv;
    ndiv = this.cloneNode();
    this.parentNode.replaceChild(ndiv, this);
    return ndiv;
};

function toggleView(id) {
    let obj = document.getElementById(id);
    if (obj) {
        obj.style.display = (obj.style.display == 'block') ? 'none' : 'block';
    }
}

/******************************************
 Fetched from source/search.js
******************************************/

function search(query, date) {
    let list = G_current_list;
    let global = false;
    let domain = G_current_domain;
    if (G_ponymail_search_list == 'global') {
        list = '*';
        domain = '*';
        global = true;
    }
    if (G_ponymail_search_list == 'domain') {
        list = '*';
        global = true;
    }

    let listid = '%s@%s'.format(list, domain);
    G_current_list = list;
    G_current_domain = domain;

    let header_from = document.getElementById('header_from');
    let header_subject = document.getElementById('header_subject');
    let header_to = document.getElementById('header_to');
    let header_body = document.getElementById('header_body');
    let header_messageid = document.getElementById('header_messageid');
    /*
     * See https://github.com/apache/incubator-ponymail-foal/issues/266
     *
     * The newhref URL parameter values should have been encoded.
     * However changing this now might invalidate existing URLs.
     * A work-round is to avoid splitting on '&' alone.
     * We know what parameter names to expect, so can look for them.
     * Also, the split() function discards excess parts, so use indexOf instead.
     */
    let qparts = query.split('&header_'); // look for additional query options (all start with header_)
    if (qparts.length > 0) { // i.e. query + header bits
        query = qparts.shift(); // Keep only the query
        // store the values to be picked up below
        for (let part of qparts) {
            let sep = part.indexOf('='); // find separator
            let key = part.substring(0, sep);
            let value = part.substring(sep+1)
            if (key == 'from') {
                header_from.value = value;
            }
            if (key == 'subject') {
                header_subject.value = value;
            }
            if (key == 'to') {
                header_to.value = value;
            }
            if (key == 'body') {
                header_body.value = value;
            }
            if (key == 'messageid') {
                header_messageid.value = value;
            }
            // N.B. other options are currently ignored
        }
    }
    let newhref = "list?%s:%s:%s".format(listid, date, encodeURIComponent(query));
    let sURL = '%sapi/stats.lua?d=%s&list=%s&domain=%s&q=%s'.format(
        G_apiURL, encodeURIComponent(date), encodeURIComponent(list), encodeURIComponent(domain), encodeURIComponent(query)
        );
    // Encode header values for shareable URLs
    if (header_from.value.length > 0) {
        sURL += "&header_from=%s".format(encodeURIComponent(header_from.value));
        newhref += "&header_from=%s".format(encodeURIComponent(header_from.value));
        header_from.value = "";
    }
    if (header_subject.value.length > 0) {
        sURL += "&header_subject=%s".format(encodeURIComponent(header_subject.value));
        newhref += "&header_subject=%s".format(encodeURIComponent(header_subject.value));
        header_subject.value = "";
    }
    if (header_to.value.length > 0) {
        sURL += "&header_to=%s".format(encodeURIComponent(header_to.value));
        newhref += "&header_to=%s".format(encodeURIComponent(header_to.value));
        header_to.value = "";
    }
    if (header_body.value.length > 0) {
        sURL += "&header_body=%s".format(encodeURIComponent(header_body.value));
        newhref += "&header_body=%s".format(encodeURIComponent(header_body.value));
        header_body.value = "";
    }
    if (header_messageid.value.length > 0) {
        sURL += "&header_messageid=%s".format(encodeURIComponent(header_messageid.value));
        newhref += "&header_messageid=%s".format(encodeURIComponent(header_messageid.value));
        header_messageid.value = "";
    }
    GET(sURL, renderListView, {
        search: true,
        global: global
    });
    if (location.href !== newhref) {
        window.history.pushState({}, null, newhref);
    }

    listview_list_lists({
        url: sURL,
        search: true,
        query: query,
        list: list,
        domain: domain
    });
    hideWindows(true);
    document.getElementById('q').value = query;
    return false;
}

// set the list(s) to search, update links
function search_set_list(what) {
    G_ponymail_search_list = what;
    let links = document.getElementsByClassName('searchlistoption');
    let whatxt = "this list"
    for (let el of links) {
        if (el.getAttribute("id").match(what)) {
            el.setAttribute("class", "searchlistoption checked");
            whatxt = el.innerText.toLowerCase();
        } else {
            el.setAttribute("class", "searchlistoption");
        }
    }
    document.getElementById('q').setAttribute("placeholder", "Search %s...".format(whatxt));
}


/******************************************
 Fetched from source/sidebar-calendar.js
******************************************/

let calendar_index = 0;
let current_calendar_size = CALENDAR_YEARS_SHOWN;
let calendar_state = {}


function calendar_max_height() {
    let body = document.body;
    let html = document.documentElement;
    let height = Math.max(body.scrollHeight,
        html.clientHeight, html.scrollHeight);
    let width = Math.max(body.scrollWidth,
        html.clientWidth, html.scrollWidth);
    let year_height = 48; // Height of one calendar year
    height -= document.getElementById("emails").getBoundingClientRect().y + 16; // top area height plus footer
    let number_of_years = Math.max(5, Math.floor(height / year_height));
    return number_of_years;
}

function renderCalendar(state) {
    calendar_state = state ? state : calendar_state;
    calendar_index = 0;
    current_calendar_size = G_show_stats_sidebar ? CALENDAR_YEARS_SHOWN : calendar_max_height();
    // Only render if calendar div is present
    let cal = document.getElementById('sidebar_calendar');
    if (!cal) {
        return;
    }

    let now = new Date();
    let CY = now.getFullYear();
    let CM = now.getMonth() + 1;
    let SY = Math.min(calendar_state.LY, CY); // last year in calendar, considering current date

    // If Last Year is into the future, set Last Month to this one.
    if (calendar_state.LY > CY) {
        calendar_state.LM = CM;
    }

    let cdiv = new HTML('div', {
        class: 'sidebar_calendar'
    })
    let N = 0;

    // Chevron for moving to later years
    let chevron = new HTML('div', {
        class: 'sidebar_calendar_chevron'
    });
    chevron.inject(new HTML('span', {
        onclick: 'calendar_scroll(this, -1);',
        style: {
            display: 'none'
        },
        id: 'sidebar_calendar_up',
        class: 'glyphicon glyphicon-collapse-up',
        title: "Show later years"
    }, " "));
    cdiv.inject(chevron);

    // Create divs for each year, assign all visible
    for (let Y = SY; Y >= calendar_state.FY; Y--) {
        let ydiv = new HTML('div', {
            class: 'sidebar_calendar_year',
            id: 'sidebar_calendar_' + N++
        });
        ydiv.inject(txt(Y));
        ydiv.inject(new HTML('br'));
        for (let i = 0; i < MONTHS_SHORTENED.length; i++) {
            let mon = MONTHS_SHORTENED[i];
            let mdiv = new HTML('div', {
                onclick: 'calendar_click(%u, %u);'.format(Y, i + 1),
                class: 'sidebar_calendar_month'
            }, mon);

            // Mark out-of-bounds segments
            let ym = '%04u-%02u'.format(Y, i+1);
            let c_active = true;
            if (calendar_state.activity && !calendar_state.activity[ym]) {
                c_active = false;
            }
            if ((Y == SY && i >= calendar_state.LM) || (Y == CY && i > CM)) {
                c_active = false;
            }
            if (Y == calendar_state.FY && ((i + 1) < calendar_state.FM)) {
                c_active = false;
            }
            if (!c_active) {
                mdiv.setAttribute("class", "sidebar_calendar_month_nothing");
                mdiv.setAttribute("onclick", "javascript:void(0);");
            } else if (calendar_state.activity && calendar_state.activity[ym]) {
                let count = calendar_state.activity[ym];
                if (count >= 1000) {
                    count = Math.round(count/100.0); // nearest century
                    count = Math.floor(count/10) + "k" + (count % 10); // thousands and remainder
                } else {
                    count = count.toString();
                }
                mdiv.inject(new HTML('span', {title: `${calendar_state.activity[ym].pretty()} emails this month`, class: 'calendar_count'}, count));
            }
            ydiv.inject(mdiv);
        }
        cdiv.inject(ydiv);
    }

    cal.innerHTML = "<p style='text-align: center;'>Archives (%u - %u):</p>".format(calendar_state.FY, SY);
    cal.inject(cdiv);


    chevron = new HTML('div', {
        class: 'sidebar_calendar_chevron'
    });
    chevron.inject(new HTML('span', {
        onclick: 'calendar_scroll(this, 1);',
        style: {
            display: 'none'
        },
        id: 'sidebar_calendar_down',
        class: 'glyphicon glyphicon-collapse-down',
        title: "Show earlier years"
    }, " "));
    cdiv.inject(chevron);

    // If we have > N years, hide the rest
    if (N > current_calendar_size) {
        for (let i = current_calendar_size; i < N; i++) {
            let obj = document.getElementById('sidebar_calendar_' + i);
            if (obj) {
                obj.style.display = "none";
            }
        }
        document.getElementById('sidebar_calendar_down').style.display = 'block';
    }
}

function calendar_scroll(me, direction) {
    let x = direction * current_calendar_size;
    let years = document.getElementsByClassName('sidebar_calendar_year');
    calendar_index = Math.max(Math.min(years.length - x, calendar_index + x), 0);
    if (calendar_index > 0) {
        document.getElementById('sidebar_calendar_up').style.display = 'block';
    } else {
        document.getElementById('sidebar_calendar_up').style.display = 'none';
    }
    if (calendar_index < (years.length - x)) {
        document.getElementById('sidebar_calendar_down').style.display = 'block';
    } else {
        document.getElementById('sidebar_calendar_down').style.display = 'none';
    }


    for (let i = 0; i < years.length; i++) {
        let year = years[i];
        if (typeof(year) == 'object') {
            if (i >= calendar_index && i < (calendar_index + Math.abs(x))) {
                year.style.display = "block";
            } else {
                year.style.display = "none";
            }
        }
    }

}


function calendar_click(year, month) {
    G_current_year = year;
    G_current_month = month;
    let q = ""; // components are not encoded
    let qapi = ""; // components need to be encoded for the api call
    let calendar_current_list = G_current_list;
    let calendar_current_domain = G_current_domain;
    if (G_current_json && G_current_json.searchParams) {
        q = G_current_json.searchParams.q || "";
        qapi = encodeURIComponent(q);
        calendar_current_list = G_current_json.searchParams.list;
        calendar_current_domain = G_current_json.searchParams.domain;
        // Weave in header parameters
        for (let key of Object.keys((G_current_json.searchParams || {}))) {
            if (key.match(/^header_/)) {
                let value = G_current_json.searchParams[key];
                q += `&${key}=${value}`;
                qapi += `&${key}=${encodeURIComponent(value)}`; // only encode the values
            }
        }
    }
    let newhref = "list?%s@%s:%u-%u".format(calendar_current_list, calendar_current_domain, year, month);
    if (q && q.length > 0) newhref += ":" + encodeURIComponent(q);

    if (location.href !== newhref) {
        window.history.pushState({}, null, newhref);
    }
    GET('%sapi/stats.lua?list=%s&domain=%s&d=%u-%u&q=%s'.format(
            G_apiURL, encodeURIComponent(calendar_current_list),
            encodeURIComponent(calendar_current_domain),
            encodeURIComponent(year), encodeURIComponent(month),
            qapi
        ),
        renderListView, {
        to: (q && q.length > 0) ? 'search' : '%s@%s'.format(calendar_current_list, calendar_current_domain),
        update_calendar: false,
        search: (q && q.length > 0)
    });
}


/******************************************
 Fetched from source/sidebar-stats.js
******************************************/

async function sidebar_stats(json) {
    let obj = document.getElementById('sidebar_stats');
    if (!obj) {
        return;
    }

    obj.innerHTML = ""; // clear stats bar

    // Subscribe button
    if (prefs && prefs.subscribeLinks) {
        let sb = document.getElementById('sidebar_subscribe');
        if (sb) sb.textContent = "";
        if (sb && json.list && !json.list.match(/\*/)) {
            sb.textContent = "";
            let sublink = json.list.replace("@", "-subscribe@");
            let subbutton = new HTML("a", {href: `mailto:${sublink}`, id: "subscribe_button"}, "Subscribe to list");
            sb.inject(subbutton);
        }
    }

    let wc = document.getElementById('sidebar_wordcloud');
    if (!json.emails || isHash(json.emails) || json.emails.length == 0) {
        obj.innerText = "No emails found...";
        if (wc) {
            wc.innerHTML = "";
        }
        return;
    }

    // Top 10 participants
    obj.inject("Found %u emails by %u authors, divided into %u topics.".format(json.emails.length, json.numparts, json.no_threads));
    obj.inject(new HTML('h5', {}, "Most active authors: "));
    for (let i = 0; i < json.participants.length; i++) {
        if (i >= 5) {
        break;
        }
        let par = json.participants[i];
        let full_name = par.name;
        if (par.name.length > 24) {
            par.name = par.name.substring(0, 23) + "...";
        }
        if (par.name.length == 0) {
            par.name = par.email;
            full_name = par.email;
        }
        let pdiv = new HTML('div', {
            class: "sidebar_stats_participant"
        });
        let pimg = new HTML('img', {
            class: "gravatar_sm",
            src: GRAVATAR_URL.format(par.gravatar)
        })
        pdiv.inject(pimg);
        let plink = new HTML('a', {
            href: 'javascript:void(0);',
            onclick: "search('&header_from=" + full_name.replace(/'/g, "\\'") + "', '" + (G_current_month ? G_current_year + '-' + G_current_month : G_current_year) + "')"
        }, par.name + ": ");
        pdiv.inject(new HTML('b', {}, plink));
        pdiv.inject(new HTML('br'));
        pdiv.inject("%u emails sent".format(par.count));
        obj.inject(pdiv);
    }

    // Word cloud, if applicable
    if (wc && json.cloud) {
        wc.innerHTML = "";
        wc.inject(new HTML('h5', {}, "Popular topics:"));
        // word cloud is delayed by 50ms to let the rest render first
        // this is a chrome-specific slowdown we're addressing.
        window.setTimeout(function() {
            if (G_current_month) {
                daterange = G_current_year + '-' + G_current_month
            } else {
                daterange = G_current_year
            }
            wordCloud(json.cloud, 220, 100, wc, daterange);
        }, 50);
    }
    if (G_show_stats_sidebar === false) {
        obj.style.display = "none";
        wc.style.display = "none";
    }
}


/******************************************
 Fetched from source/swipe.js
******************************************/

const SWIPE_THRESHOLD = 50; // Need at least this long a swipe before we register it

class SwipeDetector {
    constructor(target = document, threshold = SWIPE_THRESHOLD) {
        this.xDown = null;
        this.yDown = null;
        this.xUp = null;
        this.yUp = null;
        this.threshold = threshold;
        this.target = target;

        target.addEventListener("touchstart", this.touchStart, false);
        target.addEventListener("touchend", this.touchEnd, false);
    }

    setCallback(direction, callback_function ) {
        document.addEventListener(`swipe${direction}`, callback_function);
    }

    touchStart(evt) {
        let firstTouch = (evt.touches || evt.originalEvent.touches)[0];
        this.xDown = firstTouch.clientX;
        this.yDown = firstTouch.clientY;
    }

    touchEnd(evt) {
        if (!this.xDown || !this.yDown) return
        this.xUp = evt.changedTouches[0].clientX;
        this.yUp = evt.changedTouches[0].clientY;

        let xDiff = Math.abs(this.xDown - this.xUp);
        let yDiff = Math.abs(this.yDown - this.yUp);
        let coords = {
            detail: {
                swipestart: {
                    coords: [this.xDown, this.yDown]
                },
                swipestop: {
                    coords: [this.xUp, this.yUp]
                }
            }
        };
        // If the swipe was too short, abort
        if (Math.sqrt(xDiff ** 2 + yDiff ** 2) < this.threshold) return

        // Which direction??
        if (xDiff > yDiff) {
            if (xDiff > 0) {
                document.dispatchEvent(new CustomEvent("swipeleft", coords));
            } else {
                document.dispatchEvent(new CustomEvent("swiperight", coords));
            }
        } else {
            if (yDiff > 0) {
                document.dispatchEvent(new CustomEvent("swipeup", coords));
            } else {
                document.dispatchEvent(new CustomEvent("swipedown", coords));
            }
        }
        this.xDown = null;
        this.yDown = null;
    }

}
