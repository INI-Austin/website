# Contact form

The form on `contact.html` posts a message and the chapter mailbox receives an
email. It is not a `mailto:` link: a visitor on a machine with no mail client
configured could not send anything through one of those, and a message that
merely opens someone's mail app has not been sent.

Target mailbox: `ini.at.austin@gmail.com`.

## What is wired

`web/js/contact.js` posts JSON to FormSubmit:

    https://formsubmit.co/ajax/ini.at.austin@gmail.com

FormSubmit needs no account. The address in the URL is the destination, and
anyone posting to it gets nothing until the address itself confirms once. The
underscored keys in the request body are theirs: `_subject` sets the subject
line, `_replyto` makes Reply in the chapter mailbox go to the visitor rather
than to the relay, `_template` picks the table layout, and `_captcha` is off
because a challenge cannot be shown from a `fetch`.

## The one step left

An activation email has already been sent to `ini.at.austin@gmail.com`. It is
from FormSubmit and it contains an **Activate Form** button.

1. Open that mailbox and click **Activate Form**. Check spam if it is not in
   the inbox.
2. The page it opens shows a random string, something like
   `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. That is the form's token.
3. Optional but worth doing: put the token in `web/js/contact.js` in place of
   the address, so the mailbox is not sitting in the page source for scrapers
   to read.

       var ENDPOINT = "https://formsubmit.co/ajax/<token>";

   Nothing else changes. Rebuild with `python3 build_site.py` from `web/`.

Until step 1 is done the form answers "Something went wrong sending that" and
names the address, which is correct: nothing was delivered.

## Checking it

Fill the form in and press Send. On success the page says so in place and does
not navigate anywhere. The message arrives at the chapter mailbox with the
visitor's address in Reply-To.

The hidden `company` field is a honeypot. A real visitor never sees it, so
anything in it is a bot; the form reports success and discards the message,
because telling a bot it failed invites a retry.
