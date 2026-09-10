# Events calendar

The events page draws its week strip and month grid from the chapter's Google
Calendar, live. Nothing is copied into the repository when a meeting is
scheduled: add it to the calendar and the page shows it on the next load.

Calendar: `ini.at.austin@gmail.com`.

## What is wired

`web/js/calendar.js` reads the Google Calendar API:

    https://www.googleapis.com/calendar/v3/calendars/<calendar>/events

It pulls three months back and fifteen months forward in one request, so the
month arrows move through the year without going back to the network. Recurring
events are expanded to their individual instances, all-day events are spread
across every day they cover, and cancelled events are dropped.

With no key set the page still renders, it just renders empty. So does a
failed request. A visitor never sees an error: an events page with no events is
a legible page, an events page with a stack trace is not.

## Status

Live. The calendar is public with full event details, and the browser key is in
`web/js/calendar.js`, restricted to `https://iniaustin.org/*`. Add an event to
the calendar and it is on the page at the next load.

The key is meant to be public. The referrer restriction is what protects it: it
works from this domain and nowhere else, and it can only read Calendar. If it is
ever abused, delete it in the console and make another; nothing else changes.

## It only works from iniaustin.org

The referrer restriction has no exception for local preview, so `/events` on
localhost draws the week strip and month grid and fills them with nothing. That
is the same thing a visitor sees if Google is down, which is the intended
failure. To see real events locally, either add `http://localhost:8000/*` to the
key's website restrictions in the console, or preview against a saved response.

## Set the calendar to Central time

The calendar was created in `America/New_York`. Google stores an event at the
instant the calendar's zone makes it, so an officer in Austin who types 11am
gets an event at 10am Central, and that is the hour the page shows. Fix it in
Google Calendar under *Settings* for the calendar, *Time zone*, Central Time -
Chicago. Changing the setting does not move events that already exist, so check
anything already on the calendar afterwards.

## Checking it

Add an event to the calendar for tomorrow, load `/events`, and it should appear
in the week strip with its start time. If the grid is empty, open the browser
console: a rejected key logs `Calendar unavailable:` with the reason, which is
almost always the calendar not being public or the referrer restriction not
matching the domain you are testing from.
