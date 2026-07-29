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
