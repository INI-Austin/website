# Contact form

The form on `contact.html` posts a message and the chapter mailbox receives an
email. It is not a `mailto:` link: a visitor on a machine with no mail client
configured could not send anything through one of those, and a message that
merely opens someone's mail app has not been sent.

## What is wired

`web/js/contact.js` posts JSON to FormSubmit:

    https://formsubmit.co/ajax/91562740cc391369d10e1d33edaf16f4

FormSubmit needs no account. That string is the token the chapter mailbox was
issued when it confirmed the form, and it only ever delivers to that one
address, so it is not a credential and belongs in the page source. The
underscored keys in the request body are theirs: `_subject` sets the subject
line, `_replyto` makes Reply in the chapter mailbox go to the visitor rather
than to the relay, `_template` picks the table layout, and `_captcha` is off
because a challenge cannot be shown from a `fetch`.

## Status

Live. The address confirmed the form, and the endpoint now carries the token it
was issued rather than the address itself, so a bot scraping form endpoints
does not walk away with the mailbox.

## It only works from iniaustin.org

FormSubmit treats every origin as its own form. The token is activated for
`https://iniaustin.org`, so a submission from there is delivered and a
submission from `http://localhost:8000` comes back "This form needs
Activation" and triggers a fresh confirmation email to the chapter mailbox.

That is the right behaviour, and it means the contact form is the one thing on
this site that cannot be tested end to end in local preview. Locally it will
say the send failed, which is true: it did. Test it on the deployed site
instead, or ignore the mail if you submit locally by accident.

## Checking it

Fill the form in and press Send. On success the page says so in place and does
not navigate anywhere. The message arrives at the chapter mailbox with the
visitor's address in Reply-To.

The hidden `company` field is a honeypot. A real visitor never sees it, so
anything in it is a bot; the form reports success and discards the message,
because telling a bot it failed invites a retry.

