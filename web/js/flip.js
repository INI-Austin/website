/* Two-sided people cards. The flip itself is CSS; this only toggles the state
   and keeps aria-pressed honest for screen readers. Clicking the back while it
   is scrolled is a flip back, which is what people expect from a card. */
(function () {
  "use strict";

  var cards = document.querySelectorAll(".person-flip");

  Array.prototype.forEach.call(cards, function (card) {
    card.addEventListener("click", function () {
      var open = card.classList.toggle("is-flipped");
      card.setAttribute("aria-pressed", open ? "true" : "false");
      var name = card.getAttribute("aria-label") || "";
      card.setAttribute(
        "aria-label",
        name.replace(
          open ? ": show biography" : ": hide biography",
          open ? ": hide biography" : ": show biography"));
      if (!open) {
        var scroller = card.querySelector(".person-back-scroll");
        if (scroller) scroller.scrollTop = 0;
      }
    });
  });
})();
