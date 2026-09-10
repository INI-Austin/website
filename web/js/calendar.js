/* Events calendar: a Monday-to-Sunday strip for the current week, and a month
   grid below it with arrows.

   Events come from the chapter's Google Calendar, live, so nothing has to be
   copied into this file when a meeting is scheduled. Two constants below turn
   that on; see CALENDAR.md at the repo root. With them blank the page still
   renders, it just renders empty, which is also what happens if Google is
   unreachable. A visitor never sees an error about it: an events page with no
   events is a legible page, an events page with a stack trace is not. */
(function () {
  "use strict";

  var CALENDAR_ID = "ini.at.austin@gmail.com";
  var API_KEY = "";

  // How much of the calendar to pull. The month arrows move through whatever
  // is in this window without going back to the network.
  var MONTHS_BACK = 3;
  var MONTHS_FORWARD = 15;

  var EVENTS = [];

  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];

  function ymd(d) {
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function eventsOn(key) {
    return EVENTS.filter(function (e) { return e.date === key; });
  }

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  /* ---- the chapter's calendar ---- */

  function clockTime(iso) {
    var d = new Date(iso);
    var h = d.getHours();
    var m = d.getMinutes();
    return (h % 12 || 12) + (m ? ":" + String(m).padStart(2, "0") : "") +
      (h < 12 ? "am" : "pm");
  }

  /* Google gives an all-day event a plain date and an exclusive end date, and
     a timed one an RFC 3339 stamp. Both are spread across every day they
     cover, so a three-day event appears on all three rather than only on the
     day it started. */
  function expand(item) {
    var out = [];
    var allDay = !item.start.dateTime;
    var startsAt = item.start.dateTime || item.start.date;
    var first = allDay
      ? new Date(startsAt + "T00:00:00")
      : new Date(startsAt);
    var endsAt = (item.end && (item.end.dateTime || item.end.date)) || startsAt;
    var last = allDay
      ? new Date(new Date(endsAt + "T00:00:00").getTime() - 86400000)
      : new Date(endsAt);

    var day = new Date(first.getFullYear(), first.getMonth(), first.getDate());
    var stop = new Date(last.getFullYear(), last.getMonth(), last.getDate());
    // A run that never terminates would hang the page, so bound it.
    for (var i = 0; day <= stop && i < 60; i++) {
      out.push({
        date: ymd(day),
        title: item.summary || "Untitled event",
        time: allDay || i > 0 ? "" : clockTime(startsAt),
        url: item.htmlLink || ""
      });
      day.setDate(day.getDate() + 1);
    }
    return out;
  }

  function load() {
    if (!API_KEY) return Promise.resolve();

    var from = new Date(today.getFullYear(), today.getMonth() - MONTHS_BACK, 1);
    var to = new Date(today.getFullYear(), today.getMonth() + MONTHS_FORWARD, 1);
    var url = "https://www.googleapis.com/calendar/v3/calendars/" +
      encodeURIComponent(CALENDAR_ID) + "/events" +
      "?key=" + encodeURIComponent(API_KEY) +
      "&timeMin=" + encodeURIComponent(from.toISOString()) +
      "&timeMax=" + encodeURIComponent(to.toISOString()) +
      // Recurring events arrive as one rule unless they are expanded here.
      "&singleEvents=true&orderBy=startTime&maxResults=250";

    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).then(function (data) {
      EVENTS = (data.items || []).filter(function (item) {
        return item.status !== "cancelled" && item.start;
      }).reduce(function (all, item) {
        return all.concat(expand(item));
      }, []);
    }).catch(function (err) {
      console.error("Calendar unavailable:", err);
    });
  }

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
                  return '<span class="week-event">' +
                    (e.time ? '<b>' + esc(e.time) + "</b> " : "") +
                    esc(e.title) + "</span>";
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
            return '<span class="cal-event" title="' + esc(e.title) + '">' +
              esc(e.title) + "</span>";
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
     They come back as soon as the calendar has a single entry. */
  function renderEmptyState() {
    var notice = document.getElementById("events-empty");
    var isEmpty = EVENTS.length === 0;
    if (notice) notice.hidden = !isEmpty;
    if (prev) prev.hidden = isEmpty;
    if (next) next.hidden = isEmpty;
  }

  function draw() {
    renderWeek();
    renderMonth();
    renderEmptyState();
  }

  // Draw once from nothing so the grid is on screen while the network is
  // still out, then again with whatever came back.
  draw();
  load().then(draw);
})();
