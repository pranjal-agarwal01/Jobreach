"""
Phase 2 acceptance (docs/plan-global-pool.md): the one-form build, end to end, on made-up
people, with the real model and the real renderer, without touching any account.

  - a fresher targeting full stack, frontend and backend gets three one-page baselines;
  - a 3-year engineer targeting SDE and AI/ML gets two;
  - no question is asked, and no line on any baseline is missing from the person's documents.

    python scripts/acceptance_onboarding.py [--out out/acceptance]

The fresher is synthetic profile 05 (Rohan Das): his CV is rendered by the resume engine and
read back as text, the way an upload is. The engineer is tests/fixtures/cvs/06_ishaan_sde_3yrs.txt.
Model calls are logged to llm_calls without a user, so the cost of a build is measured.
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
from app import onboarding as onb  # noqa: E402
from app.pipeline import prompts  # noqa: E402
from app.pipeline import resume as resume_mod  # noqa: E402
from app.pipeline.schemas import BaselineSet  # noqa: E402
from app.provenance import Corpus, check_line  # noqa: E402
from app.taxonomy import band_for_years  # noqa: E402
from resume_engine import calibrate as cal  # noqa: E402
from resume_engine.ats_score import docx_text  # noqa: E402
from resume_engine.builder import build  # noqa: E402
from resume_engine.schema import (  # noqa: E402
    BuildOptions, Bullet, Contact, Education, Entry, Item, LeftSection, Link, ResumeData, Section,
    SkillGroup, Track,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def rohan_cv_text() -> str:
    data = ResumeData.model_validate(json.loads((FIXTURES / "profiles" / "05_rohan_fullstack_multitrack.json")
                                                .read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "cv.docx")
        build(data, BuildOptions(track="fullstack", scale=1.0), path)
        return docx_text(path)


PEOPLE = [
    {"name": "Rohan (fresher)", "stage": "student", "families": ["fullstack", "frontend", "backend"],
     "docs": lambda: [("CV: Rohan_Das_CV.docx", rohan_cv_text())], "expect": 3},
    {"name": "Ishaan (3 years)", "stage": "experienced", "families": ["sde", "ai_ml"],
     "docs": lambda: [("CV: Ishaan_Verma_CV.txt", (FIXTURES / "cvs" / "06_ishaan_sde_3yrs.txt").read_text(encoding="utf-8"))],
     "expect": 2},
]


def resume_data(checked: onb.CheckedProfile, tracks: list[dict]) -> ResumeData:
    """The checked profile as the engine's input: usable lines only, as load_resume_data would."""
    p = checked.profile
    items = {}
    for ci in checked.items:
        if not ci.usable:
            continue
        it = ci.item
        items[it.key] = Item(id=it.key, kind=it.kind, name=it.name, tagline=it.tagline, period=it.period,
                             stack=it.stack, links=[Link(text=lk.text, url=lk.url) for lk in it.links],
                             bullets=[Bullet(id="{}.{}".format(it.key, i), text=b.text)
                                      for i, b in enumerate(ci.bullets) if b.check.ok])
    sections = []
    for key, (heading, style, _) in onb.SECTION_DEFAULTS.items():
        entries = [Entry(id="{}{}".format(key, i), lead=e.lead, text=e.text if not e.lead else " - " + e.text)
                   for i, (e, c) in enumerate(checked.entries) if c.ok and e.section == key]
        if entries:
            sections.append(Section(id=key, heading=heading, style=style, entries=entries))
    return ResumeData(
        contact=Contact(name=p.name or "Name", location=p.location, phone=p.phone, email=p.email,
                        social=[Link(text=lk.text, url=lk.url) for lk in p.links]),
        items=items, sections=sections,
        education=[Education(institution=e.institution, degree=e.degree, meta=e.meta, result=e.result, lines=e.lines)
                   for e, c in checked.education if c.ok],
        tracks={t["key"]: Track(key=t["key"], label=t["label"], title_line=t["title_line"], summary=t["summary"],
                                left_sections=[LeftSection(heading=s["heading"], item_ids=s["item_keys"])
                                               for s in t["left_sections"]],
                                skills=[SkillGroup(**g) for g in t["skills"]]) for t in tracks})


def run(person: dict, out: Path) -> dict:
    t0 = time.monotonic()
    docs = person["docs"]()
    corpus = Corpus(docs)
    ex = onb.extract_profile(docs, llm.CallContext())
    checked = onb.check_extraction(ex, corpus)
    years = onb.counted_experience(checked.items)
    band = band_for_years(years, person["stage"])

    items = [{"key": ci.item.key, "kind": ci.item.kind, "name": ci.item.name, "tagline": ci.item.tagline,
              "period": ci.item.period, "stack": ci.item.stack, "bullets": [b.text for b in ci.bullets if b.check.ok]}
             for ci in checked.items if ci.usable]
    skills = [s.text for s in checked.skills if s.check.ok]
    entries = [((e.lead or "") + " " + e.text).strip() for e, c in checked.entries if c.ok]
    person_ctx = {"name": checked.profile.name, "career_stage": person["stage"], "experience_years": years,
                  "whole_years": int(years),
                  "experience_band": band, "batch_year": checked.profile.batch_year,
                  "education": [e.model_dump() for e, c in checked.education if c.ok]}
    plan = llm.structured("onb_baselines", BaselineSet, stable=[prompts.BASELINES],
                          volatile=onb.baseline_context(person["families"], person_ctx, items, skills, entries),
                          effort="medium", max_tokens=10000, ctx=llm.CallContext())
    tracks, suggestions = onb.validate_baselines(plan, person["families"], items, skills, corpus, band,
                                                 onb.extra_numbers_for(person_ctx))

    data = resume_data(checked, tracks)
    report = {"person": person["name"], "years": years, "band": band, "families": [t["key"] for t in tracks],
              "suggestions": [s["family"] for s in suggestions], **checked.counts(), "baselines": []}
    for t in tracks:
        c = cal.calibrate(data, tracks=[t["key"]])[t["key"]]
        data.tracks[t["key"]].scale = c.scale if c.scale is not None else cal.MIN_SCALE
        built = resume_mod.build_one_page(data, BuildOptions(track=t["key"]))
        pdf_path = out / "{}_{}.pdf".format(person["name"].split()[0].lower(), t["key"])
        pdf_path.write_bytes(built.pdf or b"")
        # Every line on the page must be backed: re-check what the page actually carries.
        on_page = [b.text for k in built.result.item_ids for b in data.items[k].bullets if b.id in built.result.bullet_ids]
        unbacked = [x for x in on_page if not check_line(x, corpus).ok]
        report["baselines"].append({"family": t["key"], "fit": t["fit"], "pages": built.pages, "scale": built.scale,
                                    "title": t["title_line"], "bullets": len(on_page), "unbacked": unbacked,
                                    "pdf": str(pdf_path)})
    report["seconds"] = round(time.monotonic() - t0, 1)
    report["ok"] = (len(tracks) == person["expect"] and all(b["pages"] == 1 and not b["unbacked"]
                                                           for b in report["baselines"]))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out" / "acceptance"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = [run(p, out) for p in PEOPLE]
    for r in results:
        print("\n{person}: {years} years ({band}), {kept} lines kept, {left_out} left out, {seconds}s".format(**r))
        for b in r["baselines"]:
            print("  {family:<10} fit {fit:<8} {pages} page at {scale}, {bullets} bullets, unbacked: {n}  {title}".format(
                n=len(b["unbacked"]), **b))
        if r["suggestions"]:
            print("  also suggested:", ", ".join(r["suggestions"]))
    ok = all(r["ok"] for r in results)
    print("\nAcceptance (baselines per family, one page each, every line backed): {}".format("PASS" if ok else "FAIL"))
    print("PDFs in", out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
