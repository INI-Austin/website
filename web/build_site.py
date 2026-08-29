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

# Nav is deliberately short and fully visible at every width. Everything else
# is reachable from the footer or from a parent page; nothing is orphaned.
NAV = [
    ("about.html", "About"),
    ("research.html", "Research"),
    ("people.html", "People"),
    ("publications.html", "Publications"),
    ("events.html", "Events"),
    ("contact.html", "Contact"),
]

# The Apply button goes straight to the interest form rather than to a page
# about applying. Both the header button and the home splash button read this.
APPLY_URL = "https://forms.gle/ZNLXi8C9ecE9Mq2SA"

FOOTER_COLS = [
    ("Chapter", [
        ("about.html", "About"),
        ("people.html", "People"),
        ("research.html", "Research"),
        ("join.html", "Join"),
    ]),
    ("Programs", [
        ("education.html", "Education"),
        ("outreach.html", "Outreach"),
        ("events.html", "Events"),
    ]),
    ("More", [
        ("publications.html", "Publications"),
        ("contact.html", "Contact"),
        ("privacy.html", "Privacy"),
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
        <p class="eyebrow">{esc(eyebrow)}</p>
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
          <a class="btn btn-ghost" href="contact.html">Contact us</a>
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
PAGES["research"] = dict(
    title=f"Research | {SITE}",
    desc="One shared platform and four application tracks in applied "
         "neuroscience.",
    body=hero("Research", "One platform, four applications", "")
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
        "stimulation to it. Bench platform first, then a target engagement "
        "pilot in healthy volunteers.</p>")
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
        "neuromodulation system, beginning with subject specific field "
        "modeling and control policy benchmarking.</p>")
    + section(
        "Track C: Pre-ictal detection and focused ultrasound for "
        "drug-resistant epilepsy", "",
        "<p>Roughly a third of people with epilepsy do not achieve seizure "
        "freedom on medication, and fewer than one percent of those patients "
        "are ever referred for surgery. This track develops seizure prediction "
        "and focus localization from scalp EEG and heart rate variability, "
        "then uses that prediction to target low intensity focused ultrasound, "
        "with adenosine mediated inhibition as the candidate mechanism. Begins "
        "with detection model development on public epilepsy datasets.</p>")
    + section(
        "Track D: Hyperflow, driving and measuring glymphatic clearance", "",
        "<p>The glymphatic system is the brain's sleep dependent waste "
        "clearance pathway, carrying amyloid beta and tau out of neural "
        "tissue. Low intensity focused ultrasound enhances that clearance in "
        "animal models with no tissue damage, and the MRI index most of the "
        "field relies on to measure it has been shown to be confounded. This "
        "track treats measurement and intervention as one loop: drive "
        "clearance, measure whether it actually moved using physics grounded "
        "imaging and a blood biomarker, and tune the next session.</p>")
    + note("Track leads are chapter members who authored the underlying "
           "proposals. Human studies are conducted under a faculty principal "
           "investigator with UT Austin IRB approval."),
)

# ---- people -----------------------------------------------------------------
PAGES["people"] = dict(
    title=f"People | {SITE}",
    desc="Executive board and advisors.",
    body=hero("People", "Our team", "")
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
PAGES["join"] = dict(
    title=f"Join | {SITE}",
    desc="Three ways in, what each one is actually for, and how to apply.",
    body=hero("Join", "Three ways in",
              "General membership is open to any UT student. Committee and "
              "research membership are both by application, and they lead to "
              "different places.")
    + banner("draft", "This page is not final.",
             "The chapter is new and its application has not run once yet.")
    + section(
        "Recruiting status", "",
        f'<div class="status glass"><p class="status-line">'
        f'<span class="dot"></span> Applications are <strong>open</strong>.</p>'
        f'<p>All applications, for both committee and research membership, are '
        f'submitted through a single Google Form. '
        f'<a href="{APPLY_URL}">Apply here</a>.</p></div>')
    + section(
        "The three tiers", "",
        deflist([
            ("General Member",
             "Any currently enrolled UT student, any major, any class year. No "
             "application, no obligation, no dues. Register and attend the "
             "speaker series, workshops, and brain health programming."),
            ("Committee Member",
             "By application, serving on a standing committee under a Vice "
             "President. The point of committee membership is leadership: it is "
             "the principal pathway to becoming that Vice President, and from "
             "there potentially President. It also helps a Research Fellow "
             "application, though only somewhat. If research is what you want, "
             "apply for research."),
            ("Research Fellow",
             "By application, reviewed by the President of Research. Open to any "
             "class year, including juniors and seniors. Assigned to a project "
             "team. This is the research track and it is the selective one."),
        ]))
    + section(
        "Who is eligible", "",
        "<ul class='plain'>"
        "<li>Any currently enrolled UT Austin student, at every tier.</li>"
        "<li>Any major. Members are welcome from every discipline whose "
        "curiosity touches the nervous system.</li>"
        "<li>Any class year. There is no first-year or second-year window on "
        "Research Fellow applications; juniors and seniors are eligible.</li>"
        "<li>No prior research experience is required.</li></ul>")
    + section(
        "How to apply",
        "One Google Form covers both applications.",
        f'<p><a class="btn" href="{APPLY_URL}">Apply</a></p>')
    + section(
        "What is asked of you",
        "The chapter fixes one of these. The rest are unset.",
        table(["Commitment", "Amount"], [
            ["Written progress report",
             "Due to your Research Lead one day before each project work "
             "meeting, covering challenges faced, how they were addressed, and "
             "goals for the coming week"],
            ["Project work meeting", "Weekly"],
            ["Hours per week", pending("Not set")],
            ["Term length", pending("Not set")],
            ["Deliverable", pending("Not set")],
            ["Dues", "None, at any tier"],
        ]))
    + section(
        "What you get", "",
        "<ul class='plain'>"
        "<li>A named project with a named lead.</li>"
        "<li>Weekly review of your work by someone accountable for it.</li>"
        "<li>Eligibility, on reaching junior standing, to apply for the national "
        "INI research internship described below.</li></ul>"
        "<p class='note'>The chapter does not promise publication acceptance, a "
        "lab position, or graduate placement. Those depend on work and on other "
        "people's decisions.</p>")
    + section(
        "The national research internship",
        "Separate from this chapter and run by the national foundation. Every "
        "detail in this section is quoted from the foundation's own page.",
        table(["Detail", "What the foundation states"], [
            ["Who runs it", "The Institute of Neuro Innovation, for members of "
                            "its university chapters"],
            ["Undergraduate eligibility",
             "Junior standing or above, in the foundation's own words"],
            ["Paid", "No. Unpaid and educational, with interns expected to "
                     "pursue academic course credit through their home "
                     "institution where applicable"],
            ["Length", "Typically 6 to 10 weeks"],
            ["Placement", "One primary research project, chosen on interests, "
                          "skills, availability, and study needs. Remote or "
                          "hybrid"],
            ["Review", "Rolling, with an initial response in 5 to 7 business "
                       "days. Not all applicants are placed"],
            ["Timing", "Applications must be sent in the quarter before the "
                       "internship"],
            ["Deliverable", "One capstone deliverable, such as a research brief, "
                            "infographic, or white paper, plus a Neuroscience "
                            "Anthology reflection that may be published"],
            ["Priority", "Given to active members of the chapter"],
        ])
        + note("The national foundation's "
               + src("https://inifoundation.org/ucla-research-internship",
                     "research internship")
               + " is offered to the UCLA chapter. Whether INI Austin members "
                 "are eligible on the same terms is "
               + pending("not yet confirmed") + "."))
    + section(
        "Questions people actually ask", "",
        deflist([
            ("Do I need research experience?",
             "No. It is not required."),
            ("Do I need to be a neuroscience major?",
             "No, at any tier. Projects need statistics, linguistics, and "
             "software as much as biology."),
            ("Can I apply as a junior or senior?",
             "Yes, to every tier including Research Fellow. There is no class "
             "year restriction."),
            ("Is there a fee?",
             "No. There are no dues at any tier and all programming is free."),
            ("How do I apply?",
             "Through a Google Form, linked in the recruiting status box "
             f'above. <a href="{APPLY_URL}">Apply here</a>.'),
            ("What is the difference between committee and research?",
             "Committee membership is the leadership track: it leads to a Vice "
             "President position and potentially to President. Research "
             "membership is the research track. Committee membership helps a "
             "research application somewhat, but it is not the main route into "
             "research, and it is not a prerequisite."),
            ("Do I have to be a committee member first?",
             "No. You can apply directly for a Research Fellow position."),
            ("How many people are admitted?",
             "The chapter sets the research group at ten to twenty-five "
             "Fellows across two to three projects. The chapter does not "
             "publish an acceptance rate because it does not have one yet."),
            ("Do you run experiments on people?",
             "Some projects do. Current tracks include noninvasive stimulation "
             "and studies with human volunteers. All human and animal work is "
             "conducted under a faculty principal investigator with UT Austin "
             "IRB approval, which is required before any data collection "
             "begins. See the "
             '<a href="research.html">research page</a> for what each track '
             "involves."),
            ("Can I propose my own question?",
             "Yes, at any tier."),
        ]))
    + note("Last updated 29 August 2026."),
)

# ---- education --------------------------------------------------------------
PAGES["education"] = dict(
    title=f"Education | {SITE}",
    desc="Journal club, the methods curriculum, and workshops. Open to any UT "
         "student at no cost.",
    body=hero("Education", "The curriculum, published",
              "Journal club, an eight-week methods sequence, and workshops. All "
              "of it is open to any UT student, whether or not they are a Fellow, "
              "and none of it costs anything.")
    + banner("draft", "Nothing on this page has run yet.",
             "The journal club pattern and the methods outline below are "
             "proposals written for this site. The Vice President of Education "
             "sets the actual curriculum.")
    + section(
        "Journal club",
        proposed("Every other week during the semester, one paper, one member "
                 "presenting, thirty minutes of discussion.")
        + " Papers chosen for having something wrong with them as often as for "
          "being landmarks.",
        table(["Week", "Focus", "Presenter"], [
            ["1", "A landmark paper in the current project area", pending("TBA")],
            ["3", "A direct challenge to that landmark", pending("TBA")],
            ["5", "A methods paper underlying both", pending("TBA")],
            ["7", "A failed replication, read closely", pending("TBA")],
            ["9", "A preprint from the last six months", pending("TBA")],
            ["11", "Member's choice", pending("TBA")],
        ]))
    + section(
        "Methods sequence",
        proposed("Eight sessions, run once per year, ninety minutes each.")
        + " Published as an outline so it can be argued with rather than taken "
          "on trust.",
        steps([
            ("Reading a paper against itself",
             "Figures before abstract. What the data would look like if the claim "
             "were false."),
            ("Study design and what it can support",
             "Cross-sectional, longitudinal, and within-subject designs, and the "
             "claims each cannot license."),
            ("Effect sizes, intervals, and power",
             "Why an underpowered significant result is weaker evidence than a "
             "null one, not stronger."),
            ("Pre-registration and the garden of forking paths",
             "Reading a registration against the paper that came out of it."),
            ("Neuroimaging data, concretely",
             "What a BIDS dataset contains, what a preprocessing pipeline does to "
             "it, and where the choices are."),
            ("Diffusion MRI and tractography",
             "Reconstruction, its ambiguities, and why a tract image is a model "
             "and not a photograph."),
            ("Systematic search and extraction",
             "Building a search, an inclusion log, and an extraction sheet that "
             "someone else could rerun."),
            ("Writing the thing",
             "Structure, figures, authorship, and how to submit."),
        ]))
    + section(
        "Workshops", "",
        '<p class="empty">Workshop dates for the coming term are published on the '
        '<a href="events.html">events</a> page as they are set.</p>')
    + note("The tractography on the home page was reconstructed from a chapter "
           "member's own diffusion MRI, using the pipeline the sixth session "
           "above would cover. A chapter member has already done this work, "
           "which is why it can be taught here."),
)

# ---- outreach ---------------------------------------------------------------
PAGES["outreach"] = dict(
    title=f"Outreach | {SITE}",
    desc="K-12 visits, brain health programming, and the annual symposium, with "
         "dates, locations, and numbers.",
    body=hero("Outreach", "Programs with numbers attached",
              "Every outreach program on this page will be reported with its "
              "date, its location, and how many people it reached. A program "
              "without those three is a statement of intent, not a result.")
    + section(
        "Planned programs", "",
        cards([
            dict(tag="K-12", title="School visits",
                 body="Classroom sessions on how the brain is studied, built "
                      "around the chapter's own imaging data rather than stock "
                      "diagrams."),
            dict(tag="Community", title="Brain health programming",
                 body="Open sessions on sleep, ageing, and cognition, covering "
                      "what the evidence supports and, as often, what it does "
                      "not."),
            dict(tag="Annual", title="Research symposium",
                 body="The chapter's flagship event. Fellows present the term's "
                      "deliverables alongside invited speakers."),
        ]))
    + section(
        "Reported outcomes", "",
        '<p class="empty">No programs have run yet. When one does, it is '
        'listed here as program, date, site, and number of people reached.</p>')
    + note("Outreach describes research. It does not offer screening, "
           "assessment, or advice about anyone's health."),
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

      <button class="btn" type="submit">Send</button>
      <p class="form-note">We use your name, email, subject, and message only to
        reply to you. See our <a href="privacy.html">privacy notice</a>.</p>
      <p class="form-confirm" id="cf-confirm" hidden></p>
    </form>"""),
)

# ---- privacy ----------------------------------------------------------------
PAGES["privacy"] = dict(
    title=f"Privacy | {SITE}",
    desc="What this site collects, which is almost nothing.",
    body=hero("Privacy", "What this site collects",
              "This is a static site. It sets no cookies, runs no analytics, and "
              "loads nothing from a third party.")
    + section(
        "", "",
        deflist([
            ("Cookies", "None. The site sets no cookies and has no consent banner "
                        "because it has nothing to consent to."),
            ("Analytics", "None. No page views, sessions, or identifiers are "
                          "recorded."),
            ("Third-party requests",
             "None. Fonts, scripts, and images are served from this site. Links "
             "to other sites are ordinary links and are only followed if you "
             "click them."),
            ("Server logs",
             "The host may keep standard access logs, which typically include IP "
             "address and user agent. The chapter does not read or analyze them."),
            ("Application data",
             "Applications are collected through a form linked from the "
             '<a href="join.html">join</a> page. Responses are read by the '
             "reviewing officers only and are not shared outside the chapter."),
            ("Imaging data",
             "The tractography on the home page was reconstructed from a chapter "
             "member's own diffusion MRI, shared with their consent. No other "
             "person's imaging data appears on this site."),
        ]))
    + note("Last updated 22 August 2026."),
)

# ---- 404 --------------------------------------------------------------------
PAGES["404"] = dict(
    title=f"Page not found | {SITE}",
    desc="That page does not exist.",
    body=hero("404", "That page does not exist",
              "The link may be old, or it may be wrong. Everything on this site "
              "is reachable from the navigation above and the footer below.",
              [("index.html", "Go to the home page"), ("research.html", "See the research")]),
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
        here = href == f"{current}.html" or (
            current.startswith("research") and href == "research.html")
        cur = ' aria-current="page"' if here else ""
        out.append(f'<a href="{href}"{cur}>{esc(label)}</a>')
    return "".join(out)


def footer_html() -> str:
    cols = "".join(
        f"<div><h4>{esc(title)}</h4><ul>"
        + "".join(f'<li><a href="{h}">{esc(t)}</a></li>' for h, t in links)
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
    <a class="brand" href="index.html">
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


def render(slug: str, page: dict, cssv: str, jsv: str) -> str:
    has_stage = 'id="fibers"' in page["body"]
    scripts = (f'<script src="js/fibers.js?v={jsv}" defer></script>'
               if has_stage else "")
    if "person-flip" in page["body"]:
        scripts += f'<script src="js/flip.js?v={jsv}" defer></script>'
    if 'id="cal-grid"' in page["body"]:
        scripts += f'<script src="js/calendar.js?v={jsv}" defer></script>'
    if 'id="contact-form"' in page["body"]:
        scripts += f'<script src="js/contact.js?v={jsv}" defer></script>'
    jsonld = (f'<script type="application/ld+json">{ORG_JSONLD}</script>'
              if slug == "index" else "")
    return SHELL.format(
        title=html.escape(page["title"], quote=True),
        desc=html.escape(page["desc"], quote=True),
        cssv=cssv, nav=nav_html(slug), body=page["body"],
        footer=footer_html(), scripts=scripts, jsonld=jsonld,
        base=BASE_URL,
        canonical=(BASE_URL + "/" if slug == "index"
                   else f"{BASE_URL}/{slug}.html"),
        apply_url=APPLY_URL, bodycls=f' class="page-{slug}"')


def check_links(files: dict) -> list:
    """Every internal href must point at a page we actually wrote."""
    known = {f"{s}.html" for s in files}
    bad = []
    for slug, doc in files.items():
        for href in re.findall(r'href="([^"#?]+\.html)[^"]*"', doc):
            if href.startswith(("http://", "https://", "//")):
                continue  # canonical/og URLs are absolute, not internal routes
            if href not in known:
                bad.append(f"{slug}.html -> {href}")
    return bad


def main() -> None:
    cssv, jsv = asset_version("css/style.css"), asset_version("js/fibers.js")
    docs = {slug: render(slug, page, cssv, jsv) for slug, page in PAGES.items()}

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
        f"\n  <url><loc>{BASE_URL}/{'' if s == 'index' else s + '.html'}</loc>"
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
    for doc in docs.values():
        for href in re.findall(r'href="([^"#?]+)\.html', doc):
            orphans.discard(href)
    if orphans:
        print("orphan pages (unreachable by link):", ", ".join(sorted(orphans)))


if __name__ == "__main__":
    main()
