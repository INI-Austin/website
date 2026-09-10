/* Contact form.

   The form posts to a relay that emails the chapter mailbox. It is not a
   mailto: link. A visitor on a machine with no mail client configured, which
   is most shared and school machines, could not send anything through the old
   version, and a message that opens someone's mail app has not been sent yet.

   ENDPOINT is FormSubmit, which needs no account. The random string in it is
   the token that address was issued once it confirmed it wanted the mail, and
   it is there in place of the address itself so a bot scraping form endpoints
   does not walk away with the mailbox. The token is not a credential: it only
   ever delivers to the one address that activated it.

   TO is still spelled out below, but only inside the message shown when a
   send fails. A visitor whose submission did not go through is better off
   being handed somewhere to write than being told to try again. */
(function () {
  "use strict";

  var ENDPOINT = "https://formsubmit.co/ajax/91562740cc391369d10e1d33edaf16f4";
  var TO = "ini.at.austin@gmail.com";

  var form = document.getElementById("contact-form");
  if (!form) return;

  var button = document.getElementById("cf-send");
  var confirm = document.getElementById("cf-confirm");

  function value(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }

  function say(text, isError) {
    if (!confirm) return;
    confirm.textContent = text;
    confirm.classList.toggle("is-error", !!isError);
    confirm.hidden = false;
  }

  function busy(state) {
    if (!button) return;
    button.disabled = state;
    button.textContent = state ? "Sending..." : "Send";
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    var fields = {
      name: value("cf-name"),
      email: value("cf-email"),
      subject: value("cf-subject"),
      message: value("cf-message")
    };

    if (!fields.name || !fields.email || !fields.subject || !fields.message) {
      say("Please fill in every field before sending.", true);
      return;
    }

    /* A real visitor never sees this field, so anything in it is a bot. Report
       success rather than an error: telling a bot it failed invites a retry. */
    if (value("cf-company")) {
      say("Thanks. Your message has been sent.", false);
      form.reset();
      return;
    }

    busy(true);
    fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({
        name: fields.name,
        email: fields.email,
        message: fields.message,
        /* Underscored keys are the relay's own. _replyto makes Reply in the
           chapter mailbox go to the visitor rather than to the relay, and
           _captcha is off because a challenge cannot be shown from a fetch. */
        _subject: "INI Austin site: " + fields.subject,
        _replyto: fields.email,
        _template: "table",
        _captcha: "false"
      })
    }).then(function (res) {
      return res.json().catch(function () { return {}; });
    }).then(function (data) {
      busy(false);
      if (String(data.success) !== "true") throw new Error(data.message || "failed");
      form.reset();
      say("Thanks. Your message has been sent, and we will reply by email.",
        false);
    }).catch(function () {
      busy(false);
      say("Something went wrong sending that. Please email " + TO +
        " directly and we will pick it up there.", true);
    });
  });
})();
