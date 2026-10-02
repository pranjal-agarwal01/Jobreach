"""The parts of the one-form build that run in code (app/onboarding.py): families from the
form, stage defaults, checking an extraction, years of experience, and holding the model's
baseline plan to the record. All data is made up."""
from datetime import date

from app import onboarding as onb
from app.pipeline.schemas import (
    BaselineSet, ExEducation, ExEntry, ExItem, ExLink, ExProfile, Extraction, FamilySuggestion,
    ProposedBaseline, SectionSel, SkillGroupP,
)
from app.provenance import Corpus

CV = """Ishaan Verma · ishaan.verma@example.com · Bengaluru, India · github.com/ishaan-verma-example
EXPERIENCE
Software Engineer — Ledgerline Payments | Jul 2023 – Present (full-time)
• Built the refunds API in Python and FastAPI, serving 2,000 requests per minute at peak.
• Moved settlement jobs to Celery workers, cutting the nightly batch from 3 hours to 40 minutes.
Backend Engineering Intern — Tidepool Labs | Jan 2023 – Jun 2023
• Wrote PostgreSQL migrations for the onboarding service.
PROJECTS
DocChat — question answering over PDFs with RAG, LangChain and FastAPI
• Indexed 300 course PDFs and answered questions with cited pages.
EDUCATION
National Institute of Technology, Surat — B.Tech Computer Engineering, 2019 – 2023 — CGPA 8.4
SKILLS Python, FastAPI, Celery, PostgreSQL, Redis, Docker, LangChain, RAG
AWARDS Finalist, Smart India Hackathon 2022
"""
CORPUS = Corpus([("CV: ishaan.pdf", CV)])
TODAY = date(2026, 10, 1)


def extraction(**overrides) -> Extraction:
    data = dict(
        profile=ExProfile(name="Ishaan Verma", email="ishaan.verma@example.com", phone="+91 99999 11111",
                          location="Bengaluru, India", batch_year=2023, cgpa=8.4,
                          links=[ExLink(text="github", url="https://github.com/ishaan-verma-example"),
                                 ExLink(text="site", url="https://ishaan.dev")]),
        items=[
            ExItem(key="ledgerline", kind="experience", name="Software Engineer", tagline="Ledgerline Payments",
                   period="Jul 2023 – Present", stack="Python, FastAPI, Celery, Kubernetes", employment="full_time",
                   bullets=["Built the refunds API in Python and FastAPI, serving 2,000 requests per minute at peak.",
                            "Moved settlement jobs to Celery workers, cutting the nightly batch from 3 hours to 40 minutes.",
                            "Moved settlement jobs to Celery workers, cutting the nightly batch from 3 hours to 40 minutes.",
                            "Mentored four junior engineers on code review."]),
            ExItem(key="tidepool", kind="experience", name="Backend Engineering Intern", tagline="Tidepool Labs",
                   period="Jan 2023 – Jun 2023", employment="internship",
                   bullets=["Wrote PostgreSQL migrations for the onboarding service."]),
            ExItem(key="docchat", kind="project", name="DocChat", tagline="question answering over PDFs",
                   stack="RAG, LangChain, FastAPI", bullets=["Indexed 300 course PDFs and answered questions with cited pages."]),
            ExItem(key="ghost", kind="project", name="Ghostwriter", tagline="an AI blog writer",
                   bullets=["Served 10,000 readers a month."]),
        ],
        education=[ExEducation(institution="National Institute of Technology, Surat", degree="B.Tech Computer Engineering",
                               meta="2019 – 2023", result="CGPA 8.4")],
        entries=[ExEntry(section="awards", text="Finalist, Smart India Hackathon 2022"),
                 ExEntry(section="awards", text="Winner, Google Code Jam 2021")],
        skills=["Python", "FastAPI", "fastapi", "PostgreSQL", "Kubernetes", "RAG"],
    )
    data.update(overrides)
    return Extraction(**data)


def test_families_from_choices_and_titles():
    assert onb.families_for(["backend", "ai_ml"], []) == ["backend", "ai_ml"]
    assert onb.families_for(["backend"], ["Senior Backend Engineer", "ML Engineer", "Chief of Staff"]) == ["backend", "ai_ml"]
    assert onb.families_for(["nonsense", "other"], ["SDE II"]) == ["sde"]
    assert len(onb.families_for(["sde", "backend", "frontend", "fullstack", "ai_ml"], [])) == onb.MAX_FAMILIES


def test_role_types_cover_neighbours():
    assert onb.role_types(["backend"]) == ["backend", "fullstack", "sde"]


def test_stage_defaults():
    assert onb.stage_defaults("student") == {"open_to": ["internship"], "excluded_company_types": ["big_tech"]}
    assert onb.stage_defaults("experienced") == {"open_to": ["full_time"], "excluded_company_types": []}


def test_header_links_from_the_form():
    f = onb.Form(stage="graduate", families=["backend"], github="github.com/ishaan-verma-example",
                 linkedin="linkedin.com/in/ishaan", portfolio="")
    assert onb.header_links(f) == [
        {"text": "github.com/ishaan-verma-example", "url": "https://github.com/ishaan-verma-example"},
        {"text": "linkedin.com/in/ishaan", "url": "https://linkedin.com/in/ishaan"}]


def test_check_extraction_keeps_backed_lines_and_trims_headers():
    c = onb.check_extraction(extraction(), CORPUS)
    led = next(ci for ci in c.items if ci.item.key == "ledgerline")
    assert led.usable and led.item.stack == "Python, FastAPI, Celery"
    assert "'Kubernetes' from the stack" in led.trimmed
    assert [b.check.ok for b in led.bullets] == [True, True, False]           # duplicate dropped, invented one fails
    ghost = next(ci for ci in c.items if ci.item.key == "ghost")
    assert not ghost.usable and not any(b.check.ok for b in ghost.bullets)
    assert [s.text for s in c.skills] == ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "RAG"]
    assert [s.check.ok for s in c.skills] == [True, True, True, False, True]
    assert [chk.ok for _, chk in c.entries] == [True, False]
    assert c.profile.phone is None and c.profile.email == "ishaan.verma@example.com"
    assert [lk.url for lk in c.profile.links] == ["https://github.com/ishaan-verma-example"]
    assert c.education[0][1].ok and c.education[0][0].result == "CGPA 8.4"
    counts = c.counts()
    assert counts["left_out"] >= 5 and counts["kept"] >= 10


def test_years_count_full_time_work_only():
    c = onb.check_extraction(extraction(), CORPUS)
    assert onb.counted_experience(c.items, TODAY) == 3.3           # Jul 2023 to Oct 2026, 40 months; not the internship


def test_untyped_jobs_count_unless_called_internships():
    ex = extraction()
    ex.items[0] = ex.items[0].model_copy(update={"employment": "unknown"})
    ex.items[1] = ex.items[1].model_copy(update={"employment": "unknown"})
    c = onb.check_extraction(ex, CORPUS)
    assert onb.counted_experience(c.items, TODAY) == 3.3


ITEMS = [{"key": "ledgerline", "kind": "experience"}, {"key": "tidepool", "kind": "experience"},
         {"key": "docchat", "kind": "project"}]
SKILLS = ["Python", "FastAPI", "Celery", "PostgreSQL", "RAG", "LangChain"]


def baseline(family="backend", **kw):
    data = dict(family=family, title_line="Senior Backend Engineer · 3 years building payment APIs",
                summary="Builds payment APIs that hold up at peak. Served 2,000 requests per minute. Scaled to 1M users on Kubernetes.",
                left_sections=[SectionSel(heading="Experience", item_keys=["ledgerline", "made_up", "ledgerline"]),
                               SectionSel(heading="Projects", item_keys=["docchat"])],
                skills=[SkillGroupP(label="Backend", items="FastAPI, Celery, Kubernetes"), SkillGroupP(label="Data", items="Postgres")],
                evidence_item_keys=["ledgerline", "made_up"], fit="strong", fit_why="Two years of payment APIs.",
                gaps=["no Kubernetes", " ", "no Go"])
    data.update(kw)
    return ProposedBaseline(**data)


def test_validate_baselines_holds_the_plan_to_the_record():
    out = BaselineSet(baselines=[baseline()], suggestions=[])
    tracks, _ = onb.validate_baselines(out, ["backend"], ITEMS, SKILLS, CORPUS, "mid", {"3", "3.2"})
    t = tracks[0]
    assert t["key"] == t["role_family"] == "backend" and t["label"] == "Backend"
    assert t["title_line"] == "Backend Engineer · 3 years building payment APIs"   # no seniority at mid
    assert t["summary"] == "Builds payment APIs that hold up at peak. Served 2,000 requests per minute."
    assert t["left_sections"] == [{"heading": "Experience", "item_keys": ["ledgerline"]},
                                  {"heading": "Projects", "item_keys": ["docchat"]}]
    assert t["skills"] == [{"label": "Backend", "items": "FastAPI, Celery"}, {"label": "Data", "items": "PostgreSQL"}]
    assert t["fit"] == "good"                                                # one real item behind it
    assert t["gaps"] == ["no Kubernetes", "no Go"]


def test_seniority_survives_for_senior_bands():
    tracks, _ = onb.validate_baselines(BaselineSet(baselines=[baseline()], suggestions=[]), ["backend"], ITEMS,
                                       SKILLS, CORPUS, "senior", {"3"})
    assert tracks[0]["title_line"].startswith("Senior Backend Engineer")


def test_a_title_with_an_unbacked_number_falls_back():
    b = baseline(title_line="Backend Engineer · 7 years")
    tracks, _ = onb.validate_baselines(BaselineSet(baselines=[b], suggestions=[]), ["backend"], ITEMS, SKILLS, CORPUS, "mid", {"3"})
    assert tracks[0]["title_line"] == "Backend Engineer"


def test_a_skipped_family_still_gets_a_plain_baseline():
    out = BaselineSet(baselines=[baseline()], suggestions=[])
    tracks, _ = onb.validate_baselines(out, ["backend", "ai_ml"], ITEMS, SKILLS, CORPUS, "mid", set())
    ai = tracks[1]
    assert ai["key"] == "ai_ml" and ai["fit"] == "stretch" and ai["title_line"] == "Machine Learning Engineer"
    assert ai["left_sections"] == [{"heading": "Experience", "item_keys": ["ledgerline", "tidepool"]},
                                   {"heading": "Projects", "item_keys": ["docchat"]}]
    assert [t["sort"] for t in tracks] == [0, 1]


def test_fit_is_never_raised():
    b = baseline(fit="stretch", evidence_item_keys=["ledgerline", "docchat"])
    tracks, _ = onb.validate_baselines(BaselineSet(baselines=[b], suggestions=[]), ["backend"], ITEMS, SKILLS, CORPUS, "mid", set())
    assert tracks[0]["fit"] == "stretch"
    b = baseline(fit="strong", evidence_item_keys=["ledgerline", "docchat"])
    tracks, _ = onb.validate_baselines(BaselineSet(baselines=[b], suggestions=[]), ["backend"], ITEMS, SKILLS, CORPUS, "mid", set())
    assert tracks[0]["fit"] == "strong"


def test_suggestions_need_two_items_and_a_new_family():
    out = BaselineSet(baselines=[baseline()], suggestions=[
        FamilySuggestion(family="ai_ml", why="DocChat and the refunds API.", evidence_item_keys=["docchat", "ledgerline"]),
        FamilySuggestion(family="backend", why="Already a target.", evidence_item_keys=["docchat", "ledgerline"]),
        FamilySuggestion(family="data_engineering", why="Thin.", evidence_item_keys=["tidepool"]),
    ])
    _, sug = onb.validate_baselines(out, ["backend"], ITEMS, SKILLS, CORPUS, "mid", set())
    assert sug == [{"family": "ai_ml", "label": "AI and ML", "why": "DocChat and the refunds API."}]


def test_extra_numbers_are_the_computed_years():
    assert onb.extra_numbers_for({"experience_years": 3.2}) == {"3", "3.2"}
    assert onb.extra_numbers_for({"experience_years": None}) == set()
