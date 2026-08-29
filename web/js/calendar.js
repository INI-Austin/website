/* Events calendar: a Monday-to-Sunday strip for the current week, and a month
   grid below it with arrows. EVENTS is empty until the chapter has dates; add
   entries as {date: "2026-09-14", title: "General meeting"} and both views
   pick them up. */
(function () {
  "use strict";

  var EVENTS = [];

  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];

  function ymd(d) {
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }

  function eventsOn(key) {
    return EVENTS.filter(function (e) { return e.date === key; });
  }

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  /* ---- this week, Monday first ---- */

  function renderWeek() {
    var strip = document.getElementById("week-strip");
    if (!strip) return;

    // getDay() is Sunday-first; shift so Monday starts the week.
    var offset = (today.getDay() + 6) % 7;
    var monday = new Date(today);
    monday.setDate(today.getDate() - offset);

    var html = "";
    for (var i = 0; i < 7; i++) {
      var d = new Date(monday);
      d.setDate(monday.getDate() + i);
      var key = ymd(d);
      var evs = eventsOn(key);
      var isToday = key === ymd(today);
      html +=
        '<div class="week-day' + (isToday ? " is-today" : "") + '">' +
          '<span class="week-dow">' + DAYS[i] + "</span>" +
          '<span class="week-num">' + d.getDate() + "</span>" +
          '<span class="week-events">' +
            (evs.length
              ? evs.map(function (e) {
                  return '<span class="week-event">' + e.title + "</span>";
                }).join("")
              : '<span class="week-none">&mdash;</span>') +
          "</span>" +
        "</div>";
    }
    strip.innerHTML = html;
  }

  /* ---- month grid ---- */

  var cursor = new Date(today.getFullYear(), today.getMonth(), 1);

  function renderMonth() {
    var grid = document.getElementById("cal-grid");
    var title = document.getElementById("cal-title");
    if (!grid || !title) return;

    title.textContent = MONTHS[cursor.getMonth()] + " " + cursor.getFullYear();

    var html = "";
    for (var i = 0; i < 7; i++) {
      html += '<div class="cal-dow">' + DAYS[i] + "</div>";
    }

    var first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    var lead = (first.getDay() + 6) % 7;
    var days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();

    for (var b = 0; b < lead; b++) {
      html += '<div class="cal-cell is-empty"></div>';
    }
    for (var n = 1; n <= days; n++) {
      var d = new Date(cursor.getFullYear(), cursor.getMonth(), n);
      var key = ymd(d);
      var evs = eventsOn(key);
      html +=
        '<div class="cal-cell' + (key === ymd(today) ? " is-today" : "") + '"' +
          ' role="gridcell">' +
          '<span class="cal-num">' + n + "</span>" +
          evs.map(function (e) {
            return '<span class="cal-event">' + e.title + "</span>";
          }).join("") +
        "</div>";
    }
    grid.innerHTML = html;
  }

  function step(months) {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + months, 1);
    renderMonth();
  }

  var prev = document.getElementById("cal-prev");
  var next = document.getElementById("cal-next");
  if (prev) prev.addEventListener("click", function () { step(-1); });
  if (next) next.addEventListener("click", function () { step(1); });

  /* With nothing scheduled anywhere, month arrows are controls that lead to
     more of the same emptiness, so hide them and leave the notice standing.
     They come back as soon as EVENTS has a single entry. */
  function renderEmptyState() {
    var notice = document.getElementById("events-empty");
    var isEmpty = EVENTS.length === 0;
    if (notice) notice.hidden = !isEmpty;
    if (prev) prev.hidden = isEmpty;
    if (next) next.hidden = isEmpty;
  }

  renderWeek();
  renderMonth();
  renderEmptyState();
})();
