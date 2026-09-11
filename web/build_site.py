"""Static generator for the INI Austin site.

Fourteen routes share one header, one footer and one nav. Hand-copying that
into fourteen files guarantees they drift, and drift is exactly the defect the
competitive audit found on the sibling chapter's site: a nav item pointing at
the wrong page, seven orphan pages, four project cards linking to the wrong
destination. Generating from a single template makes those failures structural
rather than a matter of vigilance.

Content lives in PAGES below. Anything not yet confirmed is wrapped in
pending() so it renders as a visible marker instead of quietly reading as fact.

    python3 build_site.py
"""
from __future__ import annotations

import html
import pathlib
import re

SITE = "INI Austin"
ORG = "Institute of Neuro Innovation Austin"
OUT = pathlib.Path(__file__).parent
BASE_URL = "https://iniaustin.org"
BUILD_DATE = "2026-08-22"

def route(slug: str) -> str:
    """The URL a page is linked and indexed under.

    GitHub Pages serves /about from about.html on its own, so the extension is
    a detail of how the file is stored rather than part of the address. Note
    there is no trailing slash: /about/ is a 404 there, and without one every
    relative path in the page still resolves against the site root.
    """
    return "/" if slug == "index" else f"/{slug}"


# Nav is deliberately short and fully visible at every width. Everything else
# is reachable from the footer or from a parent page; nothing is orphaned.
NAV = [
    (route("about"), "About"),
    (route("research"), "Research"),
    (route("people"), "People"),
    (route("publications"), "Publications"),
    (route("events"), "Events"),
    (route("contact"), "Contact"),
]

# The Apply button goes straight to the interest form rather than to a page
# about applying. Both the header button and the home splash button read this.
APPLY_URL = "https://forms.gle/ZNLXi8C9ecE9Mq2SA"

FOOTER_COLS = [
    ("Chapter", [
        (route("about"), "About"),
        (route("people"), "People"),
        (route("research"), "Research"),
        (APPLY_URL, "Apply"),
    ]),
    ("Programs", [
        (route("education"), "Education"),
        (route("outreach"), "Outreach"),
        (route("events"), "Events"),
    ]),
    ("More", [
        (route("publications"), "Publications"),
        (route("contact"), "Contact"),
        (route("privacy"), "Privacy"),
    ]),
]

EXTERNAL = [
    ("https://inifoundation.org/", "National foundation"),
    ("https://www.iniucla.com/", "UCLA chapter"),
]


def pending(text: str) -> str:
    """A fact we expect to be true but have not confirmed. Renders in amber."""
    return f'<span class="pending" title="Not yet confirmed">{html.escape(text)}</span>'


def proposed(text: str) -> str:
    """A proposal nobody has adopted yet.

    Distinct from pending(): pending is a blank waiting to be filled, proposed
    is a suggestion the chapter may well reject. Conflating the two is how a
    draft turns into policy without anyone deciding.
    """
    return (f'<span class="proposed" title="Proposed, not adopted">'
            f'{html.escape(text)}</span>')


def src(url: str, label: str) -> str:
    """Inline citation. A claim that links to its source is checkable."""
    return (f'<a class="src" href="{url}" target="_blank" rel="noreferrer">'
            f'{html.escape(label)}</a>')


def banner(kind: str, title: str, body: str) -> str:
    """Page-level statement about how much of the page below is settled."""
    return (f'<div class="banner banner--{kind}"><strong>{esc(title)}</strong>'
            f'<span>{body}</span></div>')


def esc(t: str) -> str:
    return html.escape(t, quote=False)


# ---------------------------------------------------------------- components

def hero(eyebrow, title_html, lede, actions=(), stage=False):
    acts = "".join(
        f'<a class="btn{"" if i == 0 else " btn-ghost"}" href="{h}">{esc(t)}</a>'
        for i, (h, t) in enumerate(actions))
    stage_html = (
        '<div class="hero-stage">'
        '<canvas id="fibers" aria-label="White-matter tractography reconstructed '
        'from a chapter member\'s own diffusion MRI. Drag to rotate."></canvas>'
        '</div>') if stage else ""
    return f"""
    <section class="hero{'' if stage else ' hero--plain'}">
      <div class="hero-copy">
        {f'<p class="eyebrow">{esc(eyebrow)}</p>' if eyebrow else ''}
        <h1>{title_html}</h1>
        {f'<p class="lede">{esc(lede)}</p>' if lede else ''}
        <div class="hero-actions">{acts}</div>
      </div>
      {stage_html}
    </section>"""


def section(title, lede="", body="", ident=""):
    i = f' id="{ident}"' if ident else ""
    lede_html = f'<p class="section-lede">{lede}</p>' if lede else ""
    t = f"<h2>{esc(title)}</h2>" if title else ""
    return f'<section{i}>{t}{lede_html}{body}</section>'


def coming_soon(page_name):
    """A page with nothing to show yet: one large statement over a full screen
    of the cortex backdrop, so the footer stays below the fold. The page name is
    spoken to screen readers but not drawn, since the nav already marks it."""
    return ('<section class="coming-soon">'
            f'<h1><span class="vh">{esc(page_name)}: </span>Coming Soon...</h1>'
            '</section>')


def cards(items, cols="three"):
    out = []
    for it in items:
        tag = f'<span class="tag">{esc(it["tag"])}</span>' if it.get("tag") else ""
        link = (f'<p class="card-link"><a href="{it["href"]}">{esc(it["link"])}</a></p>'
                if it.get("href") else "")
        out.append(f'<article class="card glass">{tag}'
                   f'<h3>{esc(it["title"])}</h3><p>{it["body"]}</p>{link}</article>')
    return f'<div class="cards {cols}">{"".join(out)}</div>'


def stats(items):
    out = "".join(f'<div class="stat glass"><span class="n">{it[0]}</span>'
                  f'<span class="l">{esc(it[1])}</span></div>' for it in items)
    return f'<div class="stat-row">{out}</div>'


def table(headers, rows, cls=""):
    h = "".join(f"<th>{esc(x)}</th>" for x in headers)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return (f'<div class="table-wrap"><table class="{cls}">'
            f"<thead><tr>{h}</tr></thead><tbody>{r}</tbody></table></div>")


def steps(items):
    out = "".join(f"<li><h4>{esc(a)}</h4><p>{b}</p></li>" for a, b in items)
    return f'<div class="ladder glass"><ol>{out}</ol></div>'


def deflist(items):
    out = "".join(f"<div class='def'><dt>{esc(a)}</dt><dd>{b}</dd></div>" for a, b in items)
    return f'<dl class="deflist glass">{out}</dl>'


def note(text):
    return f'<p class="note">{text}</p>'


def footnote(text: str) -> str:
    """A date or an aside at the foot of a page.

    Deliberately not note(): a panel round one short line reads as though the
    line matters more than the page it is under.
    """
    return f'<p class="footnote"><em>{esc(text)}</em></p>'


def plainlist(items) -> str:
    """Term and explanation as running text, with no panel around it."""
    out = "".join(f"<dt>{esc(a)}</dt><dd>{b}</dd>" for a, b in items)
    return f'<dl class="plainlist">{out}</dl>'


def figure(path: str, alt: str, caption: str = "", cls: str = "",
           href: str = "") -> str:
    """An image and what it actually is.

    `caption` is HTML so it can carry the credit link a licence requires. Alt
    text is for someone who cannot see the image, the caption is for everyone,
    so they say different things rather than repeating each other. Given an
    `href` the image becomes the link, since a screenshot of a site the reader
    can open is a thing they will try to click.
    """
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    img = (f'<img src="{esc(path)}" alt="{esc(alt)}" loading="lazy" '
           f'decoding="async">')
    if href:
        cls = f"{cls} fig--link".strip()
        img = (f'<a href="{esc(href)}" target="_blank" rel="noreferrer">'
               f"{img}</a>")
    return (f'<figure class="fig{f" {cls}" if cls else ""}">'
            f"{img}{cap}</figure>")


def viewer(caption: str, label: str, src: str, height: str = "") -> str:
    """A figure you can turn, rather than a photograph of one.

    Both of these are Aleph Neuro's own viewers in an iframe, one served from
    their site and one vendored under web/viewer, so the page never redraws
    their physics itself. `height` is a CSS length the figure is pinned to.
    """
    style = f' style="--viewer-h: {height}"' if height else ""
    return (f'<figure class="fig fig--wide">'
            f'<div class="viewer"{style}>'
            f'<iframe src="{esc(src)}" title="{esc(label)}" loading="lazy"'
            ' allowfullscreen referrerpolicy="no-referrer"></iframe>'
            f'</div><figcaption>{caption}</figcaption></figure>')


def people_grid(rows, cols="three"):
    """Name, role and bio are HTML, so pending() may be used in any of them.

    Each card is two-sided: the photo, name and role face up, and the bio is on
    the back. It is a <button> rather than a hover-only effect so it works on
    touch and from the keyboard; the flip is CSS, the toggle is one line of JS
    in js/flip.js.

    Pass a `photo` path for a real headshot. Without one, the front falls back
    to the name's initial so the layout is already photo-ready.
    """
    out = []
    for p in rows:
        meta = " &middot; ".join(x for x in [p.get("major", ""), p.get("year", "")] if x)
        initial = p.get("initial") or re.sub(r"<[^>]+>", "", p["name"])[:1].upper()
        photo = p.get("photo")
        frame = (f'<img src="{esc(photo)}" alt="" loading="lazy">' if photo
                 else f'<span aria-hidden="true">{esc(initial)}</span>')
        plain = re.sub(r"<[^>]+>", "", p["name"])
        out.append(
            f'<button type="button" class="person-flip" aria-pressed="false"'
            f' aria-label="{esc(plain)}: show biography">'
            f'<span class="person-inner">'
            f'<span class="person-face person-front glass">'
            f'<span class="person-photo">{frame}</span>'
            f'<span class="person-body"><span class="person-name">{p["name"]}</span>'
            f'<span class="role">{p["role"]}</span>'
            f'{f"<span class=meta>{esc(meta)}</span>" if meta else ""}'
            f'</span></span>'
            f'<span class="person-face person-back glass">'
            f'<span class="person-back-scroll">'
            f'<span class="person-name">{p["name"]}</span>'
            f'<span class="person-bio">{p.get("bio","")}</span>'
            f'</span></span>'
            f'</span></button>')
    return f'<div class="people-grid {cols}-up">{"".join(out)}</div>'


def timeline(items):
    """`when` is HTML so a date that is not fixed yet can render as pending()."""
    out = "".join(
        f'<li class="{"is-past" if past else ""}"><span class="when">{when}</span>'
        f'<span class="what"><strong>{esc(what)}</strong>{f" {detail}" if detail else ""}</span></li>'
        for when, what, detail, past in items)
    return f'<ul class="timeline glass">{out}</ul>'


# ------------------------------------------------------------------- content

PAGES = {}

# ---- home -------------------------------------------------------------------
# The home page is a title card, not a pitch deck: the name, two ways in, and
# the tractography. Everything else has its own page in the nav.
PAGES["index"] = dict(
    title=SITE,
    desc="INI Austin is the University of Texas at Austin chapter of the "
         "Institute of Neuro Innovation.",
    body=f"""
    <section class="splash">
      <div class="splash-copy">
        <h1 class="splash-title">INI Austin</h1>
        <p class="splash-sub">We are currently recruiting top talent for our
          2026-2027 research cohort.</p>
        <div class="hero-actions">
          <a class="btn" href="{APPLY_URL}">Apply</a>
          <a class="btn btn-ghost" href="/contact">Contact us</a>
        </div>
      </div>
      <div class="hero-stage"><canvas id="fibers" aria-label="White-matter
        tractography reconstructed from a chapter member's own diffusion MRI.
        Drag to rotate."></canvas></div>
    </section>""",
)

# ---- about ------------------------------------------------------------------
PAGES["about"] = dict(
    title=f"About | {SITE}",
    desc="What INI Austin is and how it relates to the national foundation.",
    body=section(
        "About Us", "",
        "<p>INI Austin brings together UT students who are curious about the "
        "brain and want to turn that curiosity into meaningful impact. As the "
        "Austin chapter of the national nonprofit Institute of Neuro "
        "Innovation, we explore neuroscience through research, innovation, "
        "education, and philanthropy. Students from every major are welcome to "
        "participate in our free educational and community programs, while our "
        "selective research team conducts original work aimed toward "
        "publication and real-world clinical or commercial applications. "
        "Whether you are an experienced researcher or simply fascinated by the "
        "nervous system, INI Austin offers a community where you can learn, "
        "collaborate, and help improve lives.</p>")
    + section(
        "Institute of Neuro Innovation",
        "",
        "<p>The Institute of Neuro Innovation is a national nonprofit founded by "
        "neurosurgeon Dr. Amir Vokshoor, headquartered at 2901 Wilshire Blvd "
        "#105 in Santa Monica, California. It develops and implements "
        "pioneering methods in applied neuroscience to alleviate suffering and "
        "enhance lives, capturing the synergies between traditional and "
        "nontraditional approaches within and beyond the boundaries of "
        "healthcare. "
        + src("https://inifoundation.org/", "inifoundation.org") + "</p>"
        "<p>The foundation works across four commitments. Research funds and "
        "conducts studies in applied neuroscience, from spine and "
        "motion-preserving technologies to regenerative neuroscience. "
        "Innovation moves that work toward real "
        "devices and clinical practice. Education runs public programming and "
        "trains students through its university chapters. Philanthropy "
        "supports patients and families living with neurological "
        "conditions.</p>"
        "<p>The foundation extends its work through university chapters that "
        "carry the same four commitments onto their own campuses. INI Austin "
        "is the second, after the founding chapter at UCLA.</p>"),
)

# ---- research overview ------------------------------------------------------
# Full width copy with the figure centred beneath it, rather than copy squeezed
# into half a column beside a small image. Both viewers are live and both are
# Aleph Neuro's: the transcranial wave is embedded from their site, the ULM
# volume is their MIT licensed viewer vendored under web/viewer/ulm and fed the
# track binary they published.
PAGES["research"] = dict(
    title=f"Research | {SITE}",
    desc="Four neuromodulation tracks, an open index of neurotechnology, and "
         "an imaging direction.",
    body=hero("", "Four pathways in neuromodulation", "")
    + section(
        "", "",
        "<p>Four research proposals came out of the chapter's first cohort. "
        "Read together, three of them independently identified the same "
        "central technical problem: recovering a neural signal in real time "
        "while a stimulus is actively contaminating the recording, then "
        "adjusting that stimulus based on what is sensed.</p>"
        "<p>Rather than run four separate teams, the chapter is organized as "
        "one shared platform with four application tracks. A core team builds "
        "the real time sensing, artifact rejection, and control loop "
        "framework. Each track applies it to a different condition and a "
        "different stimulation modality. Solving the shared problem once "
        "unblocks all four.</p>")
    + section(
        "Track A: Gamma sensory entrainment for early Alzheimer's disease", "",
        "<p>Synchronized 40 Hz light and sound stimulation reduces amyloid and "
        "tau pathology in animal models and has carried a fixed frequency "
        "device to a pivotal human trial. Every deployed system is open loop: "
        "it delivers a fixed frequency on a fixed schedule with no readout of "
        "whether the brain is actually entraining, and individual response is "
        "highly variable. This track builds the closed loop version, tracking "
        "each participant's gamma response during a session and adapting "
        "stimulation to it.</p>"
        + steps([
            ("Platform and sensing",
             "Build the synchronized light and sound stimulator, the EEG "
             "chain, and the controller between them, then recover the gamma "
             "response while the stimulus is still running."),
            ("Control policy",
             "Develop and benchmark the policy that moves frequency and "
             "intensity within a session, against a fixed frequency "
             "baseline."),
            ("Feasibility pilot",
             "Compare adaptive stimulation against fixed 40 Hz and sham in "
             "healthy adult volunteers, measured on gamma target engagement "
             "rather than on a cognitive endpoint."),
        ]))
    + section(
        "Track B: Closed-loop temporal interference stimulation for "
        "Parkinson's disease", "",
        "<p>Transcranial temporal interference stimulation reaches deep brain "
        "structures without surgery by crossing two kilohertz range fields "
        "through scalp electrodes. Adaptive deep brain stimulation, which "
        "titrates stimulation to the patient's own beta oscillations, received "
        "its first FDA approval in 2025, but requires an implant. Every human "
        "temporal interference study to date has run open loop. This track "
        "combines them into the first noninvasive adaptive deep brain "
        "neuromodulation system.</p>"
        + steps([
            ("Platform and sensing",
             "Build the steerable multi channel stimulator and a high density "
             "EEG front end that can recover the beta biomarker during "
             "kilohertz stimulation. Validate focus and steering in "
             "individualized head models and in a head phantom."),
            ("Target and policy",
             "Determine which noninvasive signal tracks motor state best under "
             "stimulation, then benchmark control policies in a subject "
             "specific model in the loop testbed before running any of them on "
             "people."),
            ("Crossover pilot",
             "Randomized, double blind, sham controlled crossover in "
             "Parkinson's disease comparing closed loop, open loop and sham, "
             "on motor score and on suppression of the biomarker."),
        ]))
    + section(
        "Track C: Pre-ictal detection and focused ultrasound for "
        "drug-resistant epilepsy", "",
        "<p>Roughly a third of people with epilepsy do not achieve seizure "
        "freedom on medication, and fewer than one percent of those patients "
        "are ever referred for surgery. This track develops seizure prediction "
        "and focus localization from scalp EEG and heart rate variability, "
        "then uses that prediction to target low intensity focused ultrasound, "
        "with adenosine mediated inhibition as the candidate mechanism.</p>"
        + steps([
            ("Detection and localization",
             "Train a model on scalp EEG and heart rate variability to detect "
             "pre-ictal onset and localize the focus, using intracranial "
             "recordings as ground truth where they exist."),
            ("Parameter selection",
             "A second model takes that detection and localization and selects "
             "ultrasound parameters within fixed safety limits."),
            ("Mechanism",
             "Test whether the selected parameters release enough adenosine to "
             "suppress seizure activity, and whether the suppression "
             "disappears under A1 receptor blockade."),
            ("Closed loop",
             "Integrate detection and stimulation into one controller and "
             "validate it on real time physiological input with the hardware "
             "in the loop."),
        ])
        + viewer(
            "Ultrasound crossing the skull from a transducer on the temple. "
            "Red and blue are opposite phases of the pressure field, and the "
            "skull scatters and delays all of it. Drag to turn the head. "
            "Viewer by "
            '<a href="https://alephneuro.com/blog/ultrasound-brain" '
            'target="_blank" rel="noreferrer">Aleph Neuro</a>.',
            "Simulated ultrasound propagating through a human head.",
            src="https://alephneuro.com/wave/rdbu.html?embed=1",
            height="min(74vh, 680px)"))
    + section(
        "Track D: Hyperflow, driving and measuring glymphatic clearance", "",
        "<p>The glymphatic system is the brain's sleep dependent waste "
        "clearance pathway, carrying amyloid beta, tau, and alpha synuclein "
        "out of neural tissue. Low intensity focused ultrasound enhances that "
        "clearance in animal models through the TRPV4-AQP4 pathway with no "
        "evidence of tissue damage, while the diffusion MRI index most of the "
        "field reports has been shown to be confounded by fibre geometry "
        "rather than reflecting perivascular flow. No completed human "
        "clearance trial exists yet. This track treats measurement and "
        "intervention as one loop: drive clearance, measure whether it "
        "actually moved, and tune the next session on that readout.</p>"
        + steps([
            ("Measurement stack",
             "Anchor on a contrast or physics based glymphatic MRI readout "
             "paired with plasma p-tau217, and demote the diffusion index to "
             "an exploratory secondary rather than an endpoint."),
            ("Subject specific modelling",
             "Turn an individual scan into a simulation of that person's CSF "
             "and glymphatic flow, so a session reports how much fluid moved "
             "instead of a proxy for it."),
            ("Sleep gated drive",
             "Deliver closed loop focused ultrasound in the slow wave window "
             "where clearance naturally peaks, and find the parameters that "
             "raise flow without heating tissue."),
            ("First population",
             "Run the pilot in idiopathic intracranial hypertension, where "
             "the clearance failure is clearest in the smallest study, before "
             "carrying a positive readout into early Alzheimer's disease."),
        ]))
    + section(
        "Beyond the four tracks", "",
        "<p>Two pieces of work sit outside the platform. Neither is a "
        "neuromodulation track: one is a tool the chapter already uses, and "
        "one is an imaging direction.</p>")
    + section(
        "NeuroBase, an open index of neurotechnology", "",
        "<p>NeuroBase is an automatically updated, open index of the "
        "neurotechnology field. It carries research ranked by field normalized "
        "citation impact, trials pulled from ClinicalTrials.gov with phase and "
        "enrollment, device decisions from the openFDA database, private "
        "financing parsed out of SEC Form D filings, and daily news. It was "
        "built by a chapter member and is live at "
        '<a href="https://neurobase-live.vercel.app/" target="_blank" '
        'rel="noreferrer">neurobase-live.vercel.app</a>.</p>'
        "<p>What it does not do yet is the interesting part. Search is keyword "
        "matching, so it returns what matches rather than what matters. "
        "Nothing in it models significance, so the index cannot tell a result "
        "that moves the field from one that repeats it. There is no per reader "
        "view, so everyone sees the same page. And what it holds on any "
        "individual company is thin. Those four gaps are the work.</p>"
        + figure("assets/research/neurobase-home.webp",
                 "NeuroBase front page: a lead story on a thought-to-text "
                 "brain-computer interface beside a column of the day's other "
                 "neurotechnology headlines.",
                 "NeuroBase, September 2026. Opens the live index.",
                 cls="fig--framed fig--wide",
                 href="https://neurobase-live.vercel.app/"))
    + section(
        "Transcranial ultrasound localization microscopy in the operating "
        "room", "",
        "<p>Ultrasound localization microscopy infuses microbubbles, gas cores "
        "in lipid shells already approved as a clinical contrast agent, into "
        "the bloodstream and tracks them one at a time as they pass through "
        "the vasculature. Ultrasound normally cannot separate two things "
        "closer together than about a wavelength. A single bubble blurs to "
        "that width, but its centre can be fitted far more precisely, so "
        "accumulating millions of positions builds a vascular map finer than "
        "the wavelength that made it.</p>"
        "<p>In June 2026 Aleph Neuro published the first three dimensional ULM "
        "image of a living human brain acquired through an intact skull, and "
        "released the reconstruction pipeline and the dataset under an MIT "
        "licence.</p>"
        "<p>The skull is the hard part of that result, and an operating room "
        "is the one place it is already open. Intraoperative ultrasound is "
        "routine in neurosurgery: it shows anatomy, it checks how much tumour "
        "is left, and it corrects the drift that makes preoperative MRI "
        "unreliable once the brain has shifted under an open skull. What it "
        "does not give the surgeon is the microvasculature. The question is "
        "whether the open pipeline can be adapted to that setting, where there "
        "is no skull left to correct for.</p>"
        + viewer(
            "The vasculature of a living human brain, imaged through an "
            "intact skull. Every dot is a microbubble, located to a fraction "
            "of the ultrasound wavelength and moving along the vessel it was "
            "recorded travelling down, coloured by how fast it was going, "
            "from 0 to 38 mm/s. The vessels are the paths the bubbles trace "
            "out. Drag to turn it, or use the buttons to zoom. Viewer and "
            "track data by "
            '<a href="https://github.com/alephneuro/microbubbles" '
            'target="_blank" rel="noreferrer">Aleph Neuro</a>.',
            "Ultrasound localization microscopy of a living human brain: "
            "thousands of vessel segments traced in blue through red against "
            "black, colour running from slow to fast flow.",
            src="viewer/ulm/index.html",
            height="min(78vh, 760px)")),
)

# ---- people -----------------------------------------------------------------
PAGES["people"] = dict(
    title=f"People | {SITE}",
    desc="Executive board and advisors.",
    body=hero("", "Our team", "")
    + section(
        "Executive Board", "",
        people_grid([
            dict(name="Shree Rao",
                 photo="assets/people/shree-rao.jpg",
                 role="President of Operations",
                 bio="B.S. Neuroscience, class of 2029. Jefferson Scholar in "
                     "the Program of Core Texts and Ideas. Studies cognitive "
                     "control and reading development in late childhood at the "
                     "Developmental Cognitive Neuroscience Lab."),
            dict(name="Donovan Santine",
                 photo="assets/people/donovan-santine.jpg",
                 role="President of Research",
                 bio="B.S. Biomedical Engineering Honors, class of 2028. "
                     "Designs ear-EEG electrodes and event-related potential "
                     "paradigms in Dr. José del R. Millán's Clinical "
                     "Neuroprosthetics and Brain Interaction Lab. Co-founder "
                     "and CTO of MoltGrid, an open-source AI agent "
                     "infrastructure platform."),
        ], cols="compact"))
    + section(
        "Advisors", "",
        people_grid([
            dict(name="Dr. Jordan Amadio",
                 photo="assets/people/jordan-amadio.jpg",
                 role="Faculty Advisor for Research",
                 bio='Affiliate faculty in the Department of Neurosurgery at '
                     '<a href="https://dellmed.utexas.edu/directory/jordan-amadio">'
                     'Dell Medical School</a>. Board-certified neurosurgeon, '
                     "NIH-funded investigator in Texas Robotics, and "
                     "co-founder of the NeuroLaunch incubator. Director of "
                     "neurosurgery at Neuralink and chief of spinal "
                     "neurosurgery at the Olympia Neurological Institute. MD "
                     "from Harvard Medical School, MBA from Harvard Business "
                     "School."),
            dict(name="Sidney Harris",
                 photo="assets/people/sidney-harris.jpg",
                 role="Faculty Advisor for Operations",
                 bio="B.S. in Neuroscience from UT Austin, class of 2026. "
                     "Former president of UT Synapse. Currently a teaching "
                     "assistant at the university."),
        ], cols="compact"),
        ident="advisors"),
)

# ---- join -------------------------------------------------------------------
# ---- education --------------------------------------------------------------
# Education and outreach are placeholders until the officers who own them
# settle what actually runs. The prose that used to be here (a journal club
# pattern, an eight-week methods outline, three planned programs) was written
# for this site rather than agreed by the chapter, so it is in git history at
# b8f7983 rather than on the page.
PAGES["education"] = dict(
    title=f"Education | {SITE}",
    desc="Chapter education programs.",
    body=coming_soon("Education"),
)

# ---- outreach ---------------------------------------------------------------
PAGES["outreach"] = dict(
    title=f"Outreach | {SITE}",
    desc="Chapter outreach programs.",
    body=coming_soon("Outreach"),
)

# ---- events -----------------------------------------------------------------
PAGES["events"] = dict(
    title=f"Events | {SITE}",
    desc="Chapter events calendar.",
    body=section(
        "Events", "",
        # Visible by default and hidden by JS once EVENTS has entries, so the
        # page still reads correctly with no script.
        '<p class="empty" id="events-empty">Events for the fall term are being '
        'scheduled.</p>'
        '<div class="week-strip" id="week-strip" aria-label="This week"></div>')
    + section(
        "", "",
        """<div class="cal" id="cal">
      <div class="cal-head">
        <button type="button" class="cal-nav" id="cal-prev"
                aria-label="Previous month">&#8592;</button>
        <h3 class="cal-title" id="cal-title" aria-live="polite"></h3>
        <button type="button" class="cal-nav" id="cal-next"
                aria-label="Next month">&#8594;</button>
      </div>
      <div class="cal-grid" id="cal-grid" role="grid"></div>
    </div>"""),
)

# ---- publications -----------------------------------------------------------
PAGES["publications"] = dict(
    title=f"Publications | {SITE}",
    desc="Chapter publications.",
    body=coming_soon("Publications"),
)

# ---- contact ----------------------------------------------------------------
PAGES["contact"] = dict(
    title=f"Contact | {SITE}",
    desc="Get in touch with INI Austin.",
    body=section(
        "Contact Us", "",
        """<form class="contact-form" id="contact-form">
      <label for="cf-name">Name</label>
      <input id="cf-name" name="name" type="text" required />

      <label for="cf-email">Email</label>
      <input id="cf-email" name="email" type="email" required />

      <label for="cf-subject">Subject</label>
      <input id="cf-subject" name="subject" type="text" required />

      <label for="cf-message">Message</label>
      <textarea id="cf-message" name="message" rows="6" required></textarea>

      <p class="hp" aria-hidden="true"><label for="cf-company">Company</label>
        <input id="cf-company" name="company" type="text" tabindex="-1"
               autocomplete="off" /></p>

      <button class="btn" id="cf-send" type="submit">Send</button>
      <p class="form-note">This goes straight to the chapter mailbox. We use
        your name, email, subject, and message only to reply to you. See our
        <a href="/privacy">privacy notice</a>.</p>
      <p class="form-confirm" id="cf-confirm" hidden></p>
    </form>"""),
)

# ---- privacy ----------------------------------------------------------------
PAGES["privacy"] = dict(
    title=f"Privacy | {SITE}",
    desc="What this site collects, which is almost nothing.",
    body=hero("Privacy", "What this site collects",
              "This is a static site. It sets no cookies, runs no analytics, "
              "and loads nothing from a third party while you read it.")
    + section(
        "", "",
        plainlist([
            ("Cookies", "None. The site sets no cookies and has no consent banner "
                        "because it has nothing to consent to."),
            ("Analytics", "None. No page views, sessions, or identifiers are "
                          "recorded."),
            ("Third-party requests",
             "Fonts, scripts, and images are served from this site, and links "
             "to other sites are ordinary links that are only followed if you "
             "click them. Two pages reach further. The events page reads the "
             "chapter's public Google Calendar from Google when it loads, "
             "which sends Google the request the way visiting any page sends "
             "its host a request. The contact form posts your message to "
             "FormSubmit, which relays it to the chapter mailbox, and nothing "
             "is sent there unless you press Send."),
            ("Server logs",
             "The host may keep standard access logs, which typically include IP "
             "address and user agent. The chapter does not read or analyze them."),
            ("Application data",
             "Applications are collected through the Google Form the Apply "
             "button opens. Responses are read by the reviewing officers only "
             "and are not shared outside the chapter."),
            ("Contact form",
             "The name, email, subject, and message you send through the "
             "contact page reach the chapter mailbox by way of FormSubmit, "
             "which passes the message on and does not keep an account for "
             "us. They are used only to reply to you."),
            ("Imaging data",
             "The tractography on the home page was reconstructed from a chapter "
             "member's own diffusion MRI, shared with their consent. No other "
             "person's imaging data appears on this site."),
        ]))
    + footnote("Last updated 10 September 2026."),
)

# ---- 404 --------------------------------------------------------------------
PAGES["404"] = dict(
    title=f"Page not found | {SITE}",
    desc="That page does not exist.",
    body=hero("404", "That page does not exist",
              "The link may be old, or it may be wrong. Everything on this site "
              "is reachable from the navigation above and the footer below.",
              [(route("index"), "Go to the home page"), (route("research"), "See the research")]),
)


# -------------------------------------------------------------------- render

ORG_JSONLD = """{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "INI Austin",
  "alternateName": "Institute of Neuro Innovation Austin",
  "description": "The University of Texas at Austin chapter of the Institute of Neuro Innovation.",
  "foundingDate": "2026",
  "parentOrganization": {
    "@type": "NGO",
    "name": "Institute of Neuro Innovation",
    "url": "https://inifoundation.org/"
  },
  "memberOf": {
    "@type": "CollegeOrUniversity",
    "name": "The University of Texas at Austin",
    "url": "https://www.utexas.edu/"
  }
}"""


def asset_version(rel: str) -> str:
    p = OUT / rel
    return str(int(p.stat().st_mtime)) if p.exists() else "1"


def nav_html(current: str) -> str:
    out = []
    for href, label in NAV:
        here = href == route(current) or (
            current.startswith("research") and href == route("research"))
        cur = ' aria-current="page"' if here else ""
        out.append(f'<a href="{href}"{cur}>{esc(label)}</a>')
    return "".join(out)


def footer_html() -> str:
    def link(href: str, text: str) -> str:
        # Apply is the one entry that leaves the site, and it leaves for the
        # same form the header button opens.
        away = ' target="_blank" rel="noreferrer"' if href.startswith("http") else ""
        return f'<li><a href="{href}"{away}>{esc(text)}</a></li>'

    cols = "".join(
        f"<div><h4>{esc(title)}</h4><ul>"
        + "".join(link(h, t) for h, t in links)
        + "</ul></div>"
        for title, links in FOOTER_COLS)
    ext = "".join(
        f'<li><a href="{h}" target="_blank" rel="noreferrer">{esc(t)}</a></li>'
        for h, t in EXTERNAL)
    return f"""
<footer class="site-footer">
  <div class="shell">
    <div class="footer-cols">
      {cols}
      <div><h4>Other chapters</h4><ul>{ext}</ul></div>
    </div>
    <div class="footer-row">
      <span>&copy; 2026 {esc(ORG)}. Founded 2026.</span>
    </div>
  </div>
</footer>"""


SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{desc}" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{desc}" />
<meta property="og:type" content="website" />
<meta property="og:url" content="{canonical}" />
<meta property="og:site_name" content="INI Austin" />
<meta property="og:image" content="{base}/assets/og-preview.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="Institute of Neuro Innovation" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="{base}/assets/og-preview.png" />
<link rel="canonical" href="{canonical}" />
<link rel="icon" href="assets/ini-symbol-light.svg" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="css/style.css?v={cssv}" />
{jsonld}
</head>
<body{bodycls}>
<a class="skip-link" href="#main">Skip to main content</a>

<header class="site-header">
  <div class="shell nav-wrap">
    <a class="brand" href="/">
      <img class="brand-lockup" src="assets/ini-logo-white.svg"
           alt="Institute of Neuro Innovation Austin" />
    </a>
    <nav class="site-nav" aria-label="Main">{nav}</nav>
    <a class="btn btn-sm" href="{apply_url}">Apply</a>
  </div>
</header>

<main id="main">
  <div class="shell">
{body}
  </div>
</main>
{footer}
{scripts}
</body>
</html>
"""


def script_tag(rel: str) -> str:
    # Versioned by its own file, not by a shared number: editing one script
    # has to change that script's URL or cached browsers keep the old copy.
    return f'<script src="{rel}?v={asset_version(rel)}" defer></script>'


def render(slug: str, page: dict, cssv: str) -> str:
    has_stage = 'id="fibers"' in page["body"]
    scripts = script_tag("js/fibers.js") if has_stage else ""
    if "person-flip" in page["body"]:
        scripts += script_tag("js/flip.js")
    if 'id="cal-grid"' in page["body"]:
        scripts += script_tag("js/calendar.js")
    if 'id="contact-form"' in page["body"]:
        scripts += script_tag("js/contact.js")
    jsonld = (f'<script type="application/ld+json">{ORG_JSONLD}</script>'
              if slug == "index" else "")
    return SHELL.format(
        title=html.escape(page["title"], quote=True),
        desc=html.escape(page["desc"], quote=True),
        cssv=cssv, nav=nav_html(slug), body=page["body"],
        footer=footer_html(), scripts=scripts, jsonld=jsonld,
        base=BASE_URL,
        canonical=BASE_URL + route(slug),
        apply_url=APPLY_URL, bodycls=f' class="page-{slug}"')


def check_links(files: dict) -> list:
    """Every internal href must point at a page we actually wrote."""
    known = {route(s) for s in files} | {f"{s}.html" for s in files}
    bad = []
    for slug, doc in files.items():
        for href in re.findall(r'href="(/[^":?#]*|[^":?#/]+\.html)[^"]*"', doc):
            if href.startswith("//"):
                continue
            if href not in known:
                bad.append(f"{slug}.html -> {href}")
    return bad


def main() -> None:
    cssv = asset_version("css/style.css")
    docs = {slug: render(slug, page, cssv) for slug, page in PAGES.items()}

    broken = check_links(docs)
    if broken:
        raise SystemExit("broken internal links:\n  " + "\n  ".join(broken))

    for slug, doc in docs.items():
        (OUT / f"{slug}.html").write_text(doc, encoding="utf-8")

    # Priority ranks the pages a search engine should surface first. 404 and
    # privacy are excluded from the sitemap rather than merely deprioritised.
    priority = {"index": "1.0", "research": "0.9", "join": "0.9", "about": "0.8",
                "people": "0.8", "publications": "0.7", "events": "0.7"}
    urls = "".join(
        f"\n  <url><loc>{BASE_URL}{route(s)}</loc>"
        f"<lastmod>{BUILD_DATE}</lastmod>"
        f"<priority>{priority.get(s, '0.6')}</priority></url>"
        for s in sorted(docs) if s not in ("404", "privacy"))
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}\n</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n",
        encoding="utf-8")

    print(f"wrote {len(docs)} pages, sitemap.xml, robots.txt, "
          f"0 broken internal links")

    orphans = set(docs) - {"index", "404"}
    by_route = {route(slug): slug for slug in docs}
    for doc in docs.values():
        for href in re.findall(r'href="(/[^":?#]*)"', doc):
            orphans.discard(by_route.get(href, ""))
    if orphans:
        print("orphan pages (unreachable by link):", ", ".join(sorted(orphans)))


if __name__ == "__main__":
    main()
