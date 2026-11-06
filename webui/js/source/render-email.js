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

// Build a permalink button with a dropdown for "open" and "copy link"
function make_permalink_dropdown(mid) {
    let permalink = new URL('thread/%s'.format(mid), window.location.href).href;

    let wrapper = new HTML('div', {
        class: 'permalink_dropdown'
    });

    let button = new HTML('button', {
        title: "Permanent link to this email",
        class: 'btn toolbar_btn toolbar_button_link',
        onclick: 'permalink_toggle(this);'
    }, new HTML('span', {
        class: 'glyphicon glyphicon-link'
    }, ' '));
    wrapper.inject(button);

    let menu = new HTML('div', {
        class: 'permalink_menu'
    });
    let open_link = new HTML('a', {
        href: permalink,
        target: '_blank',
        class: 'permalink_menu_item'
    }, 'Open in new tab');
    let copy_link = new HTML('a', {
        href: 'javascript:void(0);',
        class: 'permalink_menu_item',
        onclick: "permalink_copy(this, '%s');".format(permalink.replace(/'/g, "\\'"))
    }, 'Copy link');
    menu.inject([open_link, copy_link]);
    wrapper.inject(menu);

    return wrapper;
}

function permalink_toggle(btn) {
    let menu = btn.parentNode.querySelector('.permalink_menu');
    // Close any other open permalink menus first
    document.querySelectorAll('.permalink_menu.show').forEach(m => {
        if (m !== menu) m.classList.remove('show');
    });
    menu.classList.toggle('show');
    // If we just opened it, add a one-time click-outside listener to close
    if (menu.classList.contains('show')) {
        setTimeout(() => {
            document.addEventListener('click', function _dismiss(e) {
                if (!menu.contains(e.target) && e.target !== btn) {
                    menu.classList.remove('show');
                    document.removeEventListener('click', _dismiss);
                }
            });
        }, 0);
    }
}

function permalink_copy(el, url) {
    navigator.clipboard.writeText(url).then(() => {
        el.textContent = 'Copied!';
        setTimeout(() => { el.textContent = 'Copy link'; }, 1500);
    });
    el.closest('.permalink_menu').classList.remove('show');
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
    let linkbutton = make_permalink_dropdown(json.mid);
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
    let linkbutton = make_permalink_dropdown(json.mid);
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
