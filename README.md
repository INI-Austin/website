# iniaustin.org

Source for the website of INI Austin, the University of Texas at Austin
chapter of the Institute of Neuro Innovation. The live site is
<https://iniaustin.org>.

The site is static and generated. `web/build_site.py` holds every page's copy
and the one template they all share, and writes the HTML next to itself. The
HTML files in `web/` are build output: editing one by hand works until the
next build overwrites it.

## Layout

    web/              the site. build_site.py generates it, everything else is served as is
    web/js/           calendar, contact form, and the WebGL backdrop
    web/viewer/ulm/   Aleph Neuro's microbubble track viewer, vendored under its MIT licence
    render/           the imagery pipeline that baked web/data/. Not needed to build the site
    brand/            logo masters and the vector traces derived from them
    .github/workflows deploy to GitHub Pages

## Build

Python 3.12, no dependencies.

    cd web
    python3 build_site.py

The build refuses to write if an internal link points at a page that does not
exist, and it reports any page that nothing links to. Both checks run in CI,
so a broken link fails the deploy rather than reaching the site.

## Preview

    cd web
    python3 serve.py          # http://localhost:8000

`python -m http.server` is not enough here. It will not serve `/about`, which
makes every link on the site look broken locally while being correct in
production, and it caches aggressively enough that a rebuild does not show up
on reload. `serve.py` does the extensionless fallback GitHub Pages does and
sends no-store.

Two things cannot be exercised locally: the contact form and the events
calendar. Both are restricted to the production origin. `CONTACT-FORM.md` and
`CALENDAR.md` explain why and how to test each one.

## Deploy

Every push to `main` runs `.github/workflows/deploy.yml`, which rebuilds the
site from source and publishes `web/` to GitHub Pages. `web/CNAME` points the
Pages deployment at iniaustin.org.

## Adding an event

Nothing in this repository changes. Add the event to the chapter's Google
Calendar and it is on `/events` at the next page load. `CALENDAR.md` has the
details, including the two settings that have to be right on the Google side.

## Editing copy

All of it is in `web/build_site.py`, in the `PAGES` dictionary. Facts that are
expected but not yet confirmed are wrapped in `pending()` so they render as a
visible marker rather than quietly reading as settled. Grep for `pending(` to
see what is still open.
