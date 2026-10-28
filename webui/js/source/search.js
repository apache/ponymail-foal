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
     * See https://github.com/apache/ponymail-foal/issues/266
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
