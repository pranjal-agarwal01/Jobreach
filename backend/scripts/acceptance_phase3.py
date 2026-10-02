"""
Phase 3 acceptance (docs/plan-global-pool.md): the split pipeline on made-up people and made-up
posts, with the real model and the real renderer, without touching any account.

  1. A pasted post becomes a match card, then a prepared letter, in under 2 minutes: S1 extract,
     S2 screen, contact candidates, the match, S5 tailoring, S6 one-page resume, S7 letter and
     S8 lint. The companies are made up, so the S4 company check (DNS, homepage) is replaced by
     a pass; S4 itself is unchanged since Phase 1.
  2. The same opening scores differently for two people, with different reasons and gaps: Rohan
     (a fresher, synthetic profile 05) and Ishaan (3 years, tests/fixtures/cvs/06).
  3. The contact chosen follows the publication-context order, on three posts: a named CTO
     beside a careers mailbox and a press address; no address in the post (the company's site
     is a recorded page); a portal and nothing better.

    python scripts/acceptance_phase3.py [--out out/acceptance_phase3]

Model calls are logged to llm_calls without a user, so the cost is measured.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm  # noqa: E402
from app.pipeline import contacts as ct  # noqa: E402
from app.pipeline import match as mt  # noqa: E402
from app.pipeline import opportunity as opp  # noqa: E402
from app.pipeline import prepare as prep  # noqa: E402
from app.pipeline import select as select_mod  # noqa: E402
from app.pipeline.verify import Verification  # noqa: E402
from resume_engine.ats_score import docx_text  # noqa: E402
from resume_engine.builder import build  # noqa: E402
from resume_engine.schema import BuildOptions, Fact, ResumeData  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

MAIN_POST = """Kitebird Labs is hiring!

Role: Backend Engineer (0-2 years), Bengaluru, hybrid. Open to full-time hires and to final-year
students as interns.

We're a 20-person team building dispatch software for small manufacturers. You'll own the APIs
our drivers' app runs on.

You should know:
- Python, with FastAPI or Django
- PostgreSQL
- Docker
Nice to have: Redis, AWS

Pay as per experience.

Send your resume to our CTO, Meera Iyer: meera@kitebirdlabs.example
Hiring questions: careers@kitebirdlabs.example. Press: press@kitebirdlabs.example

#hiring #backend #bengaluru
3h"""

NO_ADDRESS_POST = """We're hiring frontend interns at Tallyhoo (tallyhoo.example), remote, Rs 20,000 a month.
React and TypeScript. I'm the founder; DM me if you're interested!
2h"""

PORTAL_POST = """Acme Robotics (acmerobotics.example) is hiring a Full Stack Developer intern in Pune, onsite.
Stipend Rs 25,000/month. React, Node.js, PostgreSQL. Apply here: https://jobs.ats.example/acme/fs-intern
5h"""

SITES = {
    "https://tallyhoo.example": """<a href="/careers">Careers</a> <a href="https://linkedin.com/company/tallyhoo">LinkedIn</a>
        <footer>Say hello: hello@tallyhoo.example</footer>""",
    "https://tallyhoo.example/careers": """<h1>Work at Tallyhoo</h1><p>Don't see your role? Write to
        <a href="mailto:jobs@tallyhoo.example">jobs@tallyhoo.example</a>.</p><p>Our founder blogs at
        priya@tallyhoo.example. Press: press@tallyhoo.example</p>""",
    "https://acmerobotics.example": """<p>Robots for warehouses.</p><footer>hello@acmerobotics.example</footer>""",
}


def fake_fetch(url):
    return (url, SITES[url]) if url in SITES else None


def passing_check(ex, domain, ctx):
    return Verification(None, "pass")


def read(post: str) -> opp.Read:
    return opp.read(post, None, llm.CallContext(), verify=passing_check,
                    site=lambda d: ct.harvest_site(d, fetch=fake_fetch))


def opening(r: opp.Read) -> mt.Opening:
    return mt.Opening(id="job-1", ex=r.ex, cols=opp.normalise(r.ex), screen=r.screen.as_json(),
                      contacts=r.contacts, source="paste", age_hours=r.age_hours)


# ------------------------------------------------------------------ the two people

def rohan() -> tuple[ResumeData, str, mt.Seeker, dict, dict]:
    data = ResumeData.model_validate(json.loads((FIXTURES / "profiles" / "05_rohan_fullstack_multitrack.json")
                                                .read_text(encoding="utf-8")))
    skills = list(dict.fromkeys(x.strip() for t in data.tracks.values() for g in t.skills
                                for x in g.items.split(",") if x.strip()))
    data.facts += [Fact(id="skill{}".format(i), kind="skill", text=s, confirmed=True) for i, s in enumerate(skills)]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "cv.docx")
        build(data, BuildOptions(track="fullstack", scale=1.0), path)
        cv = docx_text(path)
    profile = {"name": "Rohan Das", "career_stage": "student", "experience_years": 0, "experience_band": "intern",
               "batch_year": 2027, "grad_date": "May 2027", "headline": "B.Tech Computer Science, 2027"}
    prefs = {"open_to": ["internship"], "locations": ["Bengaluru", "Remote"], "remote_ok": True, "onsite_ok": True,
             "hybrid_ok": True, "stipend_floor": 15000, "excluded_company_types": ["big_tech"],
             "excluded_companies": [], "freshness_ceiling_hours": 72, "duration_flex": "Flexible on duration",
             "start_date": "Immediately", "target_families": ["fullstack", "frontend", "backend"],
             "signature_html": "--\nRohan Das\n+91 90000 00005"}
    fits = {"fullstack": "strong", "frontend": "good", "backend": "good"}
    seeker = mt.make_seeker(
        profile=profile, prefs=prefs, skills=skills,
        tracks=[{"key": k, "label": t.label, "role_family": k, "fit": fits.get(k)} for k, t in data.tracks.items()],
        items=[{"kind": it.kind, "name": it.name, "tagline": it.tagline, "stack": it.stack,
                "bullets": [b.text for b in it.bullets]} for it in data.items.values()])
    return data, cv, seeker, profile, prefs


def ishaan() -> mt.Seeker:
    """From tests/fixtures/cvs/06_ishaan_sde_3yrs.txt, as the Phase 2 build reads it."""
    return mt.make_seeker(
        profile={"career_stage": "experienced", "experience_years": 3.2, "experience_band": "mid"},
        prefs={"open_to": ["full_time"], "locations": ["Bengaluru"], "remote_ok": True, "onsite_ok": True,
               "hybrid_ok": True, "salary_floor": 1800000, "excluded_company_types": [], "excluded_companies": [],
               "freshness_ceiling_hours": 72, "target_families": ["sde", "ai_ml"]},
        tracks=[{"key": "sde", "label": "Software engineering", "role_family": "sde", "fit": "strong"},
                {"key": "ai_ml", "label": "AI and ML", "role_family": "ai_ml", "fit": "good"}],
        skills=["Python", "SQL", "Go", "FastAPI", "Django", "Celery", "REST APIs", "PostgreSQL", "Redis", "pgvector",
                "LangChain", "RAG", "PyTorch", "Hugging Face Transformers", "Docker", "AWS", "GitHub Actions"],
        items=[{"kind": "experience", "name": "Software Engineer", "tagline": "Ledgerline Payments",
                "stack": "Python, FastAPI, Celery, Redis, PostgreSQL, Docker, AWS",
                "bullets": ["Built the refunds API in Python and FastAPI, serving 2,000 requests per minute at the monthly peak.",
                            "Moved nightly settlement jobs to Celery workers on Redis, cutting the batch from 3 hours to 40 minutes."]},
               {"kind": "experience", "name": "Software Engineering Intern", "tagline": "Brightwell Health",
                "stack": "Python, Django, PostgreSQL, Docker",
                "bullets": ["Built appointment-booking endpoints in Django REST Framework used by 40 partner clinics."]},
               {"kind": "project", "name": "DocChat", "tagline": "question answering over course PDFs",
                "stack": "Python, LangChain, FastAPI, PostgreSQL, pgvector, RAG",
                "bullets": ["Indexed 300 course PDFs with LangChain and a pgvector store, answering questions with cited pages."]},
               {"kind": "project", "name": "Invoice Lens", "tagline": "extracting fields from scanned invoices",
                "stack": "Python, PyTorch, Hugging Face Transformers",
                "bullets": ["Fine-tuned a LayoutLM model on 1,500 labelled invoices to pull totals, dates and GST numbers."]}])


def show(name: str, m: mt.MatchResult) -> None:
    print("  {:<8} {} score {:>5}  bucket {:<6}  baseline {}".format(name, m.decision, m.score, m.bucket or "-",
                                                                     m.track_key))
    for w in m.why:
        print("           + " + w)
    for g in m.gaps:
        print("           - " + g)
    for r in m.reasons:
        print("           x " + r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out" / "acceptance_phase3"))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    data, cv, rohan_seeker, profile, prefs = rohan()
    ishaan_seeker = ishaan()
    checks = {}

    # 1. Paste -> match card -> prepared letter, timed.
    t0 = time.monotonic()
    r = read(MAIN_POST)
    o = opening(r)
    m = mt.evaluate(rohan_seeker, o)
    t_card = time.monotonic() - t0
    ctx = llm.CallContext()
    corpus = prep.record_corpus([("CV", cv)], data)
    chosen = select_mod.tailor(data, m.track_key, r.ex, MAIN_POST, ctx, corpus=corpus, band="intern")
    built = prep.build_resume(data, chosen, MAIN_POST)
    letter = prep.write_letter(data=data, chosen=chosen, built=built, raw_text=MAIN_POST, ex=r.ex,
                               screen=m.screen_json(), contact=m.contact, profile=profile, prefs=prefs,
                               facts=[{"id": f.id, "kind": f.kind, "text": f.text} for f in data.facts],
                               education=[e.model_dump() for e in data.education], ctx=ctx)
    t_letter = time.monotonic() - t0
    (out / "rohan_kitebird.pdf").write_bytes(built.pdf or b"")
    (out / "rohan_kitebird_letter.txt").write_text("To: {}\nSubject: {}\n\n{}".format(
        m.apply_to, letter.subject, letter.plain), encoding="utf-8")
    print("1. Pasted post to letter (Rohan, Kitebird Labs)")
    print("   match card after {:.0f}s; letter after {:.0f}s".format(t_card, t_letter))
    print("   resume: {} page at scale {}, title '{}'".format(built.pages, built.scale, chosen.track.title_line))
    print("   letter to {} ({}), lint {} after {} attempt(s)".format(
        m.apply_to, m.contact.context if m.contact else "-", "passed" if letter.ok else "FAILED", letter.attempts))
    for c in letter.checks:
        if not c.ok:
            print("     failed check:", c.name, c.detail)
    for n in chosen.notes:
        print("   note:", n)
    checks["letter in under 2 minutes"] = t_letter < 120 and built.pages == 1 and letter.ok and m.route == "email"

    # 2. The same opening, two people.
    print("\n2. The same opening for two people")
    mi = mt.evaluate(ishaan_seeker, o)
    show("Rohan", m)
    show("Ishaan", mi)
    checks["different scores and reasons"] = (m.decision == mi.decision == "keep" and m.score != mi.score
                                              and m.why != mi.why and m.gaps != mi.gaps)

    # 3. Who to write to, by where the address was published.
    print("\n3. Contacts, in publication-context order")
    seen = {}
    for name, post in (("named CTO, careers and press", MAIN_POST), ("no address in the post", NO_ADDRESS_POST),
                       ("a portal only", PORTAL_POST)):
        rr = r if post is MAIN_POST else read(post)
        chosen_c = ct.choose(rr.contacts, bool(rr.portal))
        seen[name] = chosen_c
        print("  {}: candidates {}".format(name, ", ".join("{} [{}]".format(c.email, c.context) for c in
                                                         sorted(rr.contacts, key=ct.Candidate.sort_key)) or "none"))
        print("     chosen: {}".format("{} ({})".format(chosen_c.who(), ct.CONTEXT_LABEL[chosen_c.context])
                                       if chosen_c else "the portal: " + str(rr.portal)))
        if rr.screen.flags:
            print("     flags:", "; ".join(rr.screen.flags))
    a, b, c = seen.values()
    checks["contact order"] = (a is not None and a.email == "meera@kitebirdlabs.example" and a.context == "post_apply"
                               and b is not None and b.email == "jobs@tallyhoo.example" and b.context == "careers_page"
                               and c is None)

    print()
    for k, v in checks.items():
        print("  {:<32} {}".format(k, "PASS" if v else "FAIL"))
    ok = all(checks.values())
    print("\nPhase 3 acceptance: {}  (files in {})".format("PASS" if ok else "FAIL", out))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
