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
    if (error.status === 404) {
        let text = document.getElementById('modal_text');
        text.inject(new HTML('br'));
        text.inject(new HTML('a', {
            href: 'oauth.html'
        }, "Log in"));
    }
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
