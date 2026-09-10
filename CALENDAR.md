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

## The two steps left

Both are in the chapter's Google account.

**1. Make the calendar public.** In Google Calendar, open Settings for
`ini.at.austin@gmail.com`, go to *Access permissions for events*, and tick
*Make available to public*. Leave it on **See only free/busy** if you do not
want titles readable, but note the page then has nothing to show; to list event
names, choose *See all event details*. Only put on this calendar what the
chapter is happy to publish.

**2. Create a browser API key.**

1. Go to <https://console.cloud.google.com/> and create a project, or open an
   existing one.
2. *APIs & Services* -> *Library* -> search "Google Calendar API" -> **Enable**.
3. *APIs & Services* -> *Credentials* -> *Create credentials* -> **API key**.
4. Edit the key and restrict it, which matters because the key ships in the
   page source:
   - *Application restrictions*: **Websites**, with
     `https://iniaustin.org/*` and `https://*.iniaustin.org/*`. Add
     `http://localhost:8000/*` if you want the calendar to work in local
     preview too.
   - *API restrictions*: **Restrict key**, and select only *Google Calendar
     API*.
5. Paste the key into `web/js/calendar.js`:

       var API_KEY = "AIza...";

6. Rebuild with `python3 build_site.py` from `web/`, then commit and push.

A key restricted this way is meant to be public. It cannot be used from another
site, and it can only read this one API. If it is ever abused, delete it in the
console and make a new one; nothing else has to change.

The privacy page already says the events page reads the calendar from Google.

## Checking it

Add an event to the calendar for tomorrow, load `/events`, and it should appear
in the week strip with its start time. If the grid is empty, open the browser
console: a rejected key logs `Calendar unavailable:` with the reason, which is
almost always the calendar not being public or the referrer restriction not
matching the domain you are testing from.
