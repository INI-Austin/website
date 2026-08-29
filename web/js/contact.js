/* Contact form. There is no backend yet and no chapter mailbox, so the form
   hands the message to the visitor's own mail client. When an address and an
   endpoint exist, replace the mailto branch with a fetch() POST and nothing
   else on the page has to change. */
(function () {
  "use strict";

  var TO = "ini.at.utaustin@inifoundation.org";

  var form = document.getElementById("contact-form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    var get = function (id) {
      var el = document.getElementById(id);
      return el ? el.value.trim() : "";
    };

    var name = get("cf-name");
    var email = get("cf-email");
    var subject = get("cf-subject");
    var message = get("cf-message");

    var body = "From: " + name + " <" + email + ">\n\n" + message;
    window.location.href = "mailto:" + TO +
      "?subject=" + encodeURIComponent(subject) +
      "&body=" + encodeURIComponent(body);

    var confirm = document.getElementById("cf-confirm");
    if (confirm) {
      confirm.textContent =
        "Your mail app should now be open with this message ready to send.";
      confirm.hidden = false;
    }
  });
})();
