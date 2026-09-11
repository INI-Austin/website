/* Swaps a still figure for the interactive viewer, but only where it will
   actually run.

   Aleph's wave viewer decodes the pressure field out of an MP4 through
   WebCodecs. Two browsers cannot finish that. One has no WebCodecs at all and
   dead-ends: their loader falls back to a raw .bin that is not on their server,
   so the figure sits on "loading..." forever. The other is WebKit, which
   exposes VideoDecoder but never completes the decode, so an iPhone draws a
   head you can turn around a wave that never moves. Every iOS browser is
   WebKit, Chrome and Brave included, so this is one engine rather than three.

   Neither case can be detected from here after the fact: the iframe is
   cross-origin, so the page cannot look inside it to see whether anything
   drew. The still is therefore what ships in the HTML, and the viewer is the
   upgrade. Anything that fails this check keeps the image, which is the figure
   the caption describes either way. */
(function () {
  "use strict";

  var boxes = document.querySelectorAll(".viewer[data-viewer]");
  if (!boxes.length) return;

  // MacIntel with touch points is an iPad, which reports itself as a desktop.
  var webkit = /iP(hone|od|ad)/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (webkit || typeof VideoDecoder === "undefined") return;

  for (var i = 0; i < boxes.length; i++) {
    var box = boxes[i];
    var frame = document.createElement("iframe");
    frame.src = box.getAttribute("data-viewer");
    frame.title = box.getAttribute("data-label") || "";
    frame.loading = "lazy";
    frame.allowFullscreen = true;
    frame.referrerPolicy = "no-referrer";
    box.textContent = "";
    box.appendChild(frame);

    // The instruction to drag is only true now that there is something to drag.
    var cap = box.parentNode.querySelector(".live-only");
    if (cap) cap.hidden = false;
  }
})();
