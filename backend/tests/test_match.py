"""Per-user matching in code: eligibility, score, bucket, reasons and gaps
(docs/plan-global-pool.md, 0.5). Made-up people; no database or model calls."""
from app.pipeline import contacts as ct
from app.pipeline import match as mt
from app.pipeline import screen
from app.pipeline.opportunity import normalise
from app.pipeline.schemas import ApplyRoute, Extracted, Stipend

POST = """Acme Labs (acmelabs.io) is hiring a Backend Engineer, Bengaluru, onsite. Interns and
full-time both welcome. Must: Python, FastAPI, PostgreSQL, Docker. Nice to have: Kubernetes, React.
Send your CV to hr@acmelabs.io"""

STUDENT = dict(
    profile={"career_stage": "student", "experience_years": 0, "experience_band": "intern", "batch_year": 2027,
             "cgpa": 8.1},
    prefs={"open_to": ["internship"], "locations": ["Bengaluru", "Remote"], "remote_ok": True, "onsite_ok": True,
           "hybrid_ok": True, "stipend_floor": 15000, "excluded_company_types": ["big_tech"],
           "excluded_companies": [], "freshness_ceiling_hours": 72,
           "target_families": ["fullstack", "frontend", "backend"]},
    tracks=[{"key": "fullstack", "label": "Full stack", "role_family": "fullstack", "fit": "strong"},
            {"key": "frontend", "label": "Frontend", "role_family": "frontend", "fit": "good"},
            {"key": "backend", "label": "Backend", "role_family": "backend", "fit": "good"}],
    skills=["React", "Next.js", "TypeScript", "Node.js", "PostgreSQL", "Docker", "Python"],
    items=[{"kind": "project", "name": "PixelForge", "tagline": "A shared pixel-art editor",
            "stack": "Next.js, TypeScript, PostgreSQL",
            "bullets": ["Built a collaborative editor in React with live cursors for 40 users"]},
           {"kind": "project", "name": "Ledgerly", "tagline": "Expense splitter", "stack": "Node.js, Express",
            "bullets": ["Wrote the settle-up API and its tests"]}],
)

ENGINEER = dict(
    profile={"career_stage": "experienced", "experience_years": 3.2, "experience_band": "mid"},
    prefs={"open_to": ["full_time"], "locations": ["Bengaluru"], "remote_ok": True, "onsite_ok": True,
           "hybrid_ok": True, "salary_floor": 1800000, "excluded_company_types": [], "excluded_companies": [],
           "freshness_ceiling_hours": 72, "target_families": ["sde", "ai_ml"]},
    tracks=[{"key": "sde", "label": "Software engineering", "role_family": "sde", "fit": "strong"},
            {"key": "ai_ml", "label": "AI and ML", "role_family": "ai_ml", "fit": "good"}],
    skills=["Python", "FastAPI", "PostgreSQL", "Kafka", "Docker", "AWS", "PyTorch", "Go"],
    items=[{"kind": "experience", "name": "Software Engineer", "tagline": "Ledgerline",
            "stack": "Python, FastAPI, PostgreSQL, Kafka",
            "bullets": ["Built payment reconciliation APIs in FastAPI serving 2M requests a day",
                        "Helped the team go to market with a new payouts product"]},
           {"kind": "project", "name": "Fraudscope", "tagline": "Fraud model", "stack": "PyTorch, Python",
            "bullets": ["Trained a transaction fraud classifier"]}],
)


def seeker(base, **over):
    kw = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in over.items():
        if k in ("profile", "prefs"):
            kw[k].update(v)
        else:
            kw[k] = v
    return mt.make_seeker(**kw)


def ex(**kw):
    base = dict(title="Backend Engineer", company_name="Acme Labs", company_domain="acmelabs.io",
                poster_type="company_page", country="India", remote=False, onsite_city="Bengaluru",
                employment_type="both", stipend=Stipend(stated="unstated"), discipline="backend",
                skills_must=["Python", "FastAPI", "PostgreSQL", "Docker"], skills_nice=["Kubernetes", "React"],
                apply_routes=[ApplyRoute(type="email", value="hr@acmelabs.io")], posted_age_label="3h")
    base.update(kw)
    return Extracted(**base)


def opening(e=None, raw=POST, age=3.0, source="paste", job_id="job-1"):
    e = e or ex()
    cands, _ = ct.from_post(e, raw, screen.company_domain(e))
    return mt.Opening(id=job_id, ex=e, cols=normalise(e), screen=screen.global_screen(e).as_json(),
                      contacts=cands, source=source, age_hours=age)


def test_two_people_get_different_scores_and_reasons_for_the_same_opening():
    o = opening()
    student = mt.evaluate(seeker(STUDENT), o)
    engineer = mt.evaluate(seeker(ENGINEER), o)
    assert student.decision == engineer.decision == "keep", (student.reasons, engineer.reasons)
    assert engineer.score > student.score
    assert engineer.why[0] == "Python, FastAPI and PostgreSQL: used in your work at Ledgerline"
    assert "PostgreSQL and React: used in PixelForge" in student.why
    assert student.bucket == "good" and student.parts["skills"] < mt.STRONG_SKILLS     # misses FastAPI
    assert "Asks for FastAPI" in student.gaps and "Asks for FastAPI" not in engineer.gaps
    assert any("Python yet" in g for g in student.gaps)           # listed, but no project shows it
    assert student.track_key == "backend" and "Backend is one of your targets" in student.why[1]
    assert engineer.track_key == "sde" and "Close to your Software engineering target" in engineer.why
    # The same unstated pay: a student is asked about it; a salaried job is never asked about.
    assert student.stipend_rule == "ask" and engineer.stipend_rule == "none"
    assert student.route == engineer.route == "email" and student.apply_to == "hr@acmelabs.io"


def test_a_skill_the_work_shows_counts_more_than_one_only_listed():
    s = seeker(ENGINEER)
    assert mt.skill_evidence(s, "fastapi") == (mt.SHOWN, ["your work at Ledgerline"])
    assert mt.skill_evidence(s, "Docker") == (mt.LISTED, [])
    assert mt.skill_evidence(s, "Kubernetes") == (0.0, [])
    assert mt.skill_evidence(seeker(STUDENT), "ReactJS")[0] == mt.SHOWN     # "React" in a bullet


def test_ordinary_words_are_not_read_as_tools():
    s = seeker(ENGINEER)                                          # "go to market" in a bullet
    assert mt.skill_evidence(s, "Go") == (mt.LISTED, [])
    s = seeker(ENGINEER, items=ENGINEER["items"] + [{"kind": "project", "name": "Tiny", "stack": "Go", "bullets": []}])
    assert mt.skill_evidence(s, "Golang") == (mt.SHOWN, ["Tiny"])


def test_a_kind_of_role_nobody_targets_is_ruled_out_with_the_targets_named():
    m = mt.evaluate(seeker(STUDENT), opening(ex(title="Product Designer", discipline="design")))
    assert m.decision == "drop" and m.bucket is None
    assert "Not a kind of role you're targeting (Design). Your targets: Full stack, Frontend, Backend" in m.reasons


def test_experience_one_year_short_is_a_gap_more_is_ruled_out():
    eng = seeker(ENGINEER)
    m = mt.evaluate(eng, opening(ex(employment_type="full_time", exp_min=4, exp_max=6, title="Software Engineer",
                                    discipline="sde")))
    assert m.decision == "keep" and "Asks for 4+ years; you have 3.2" in m.gaps and m.bucket != "strong"
    m = mt.evaluate(eng, opening(ex(employment_type="full_time", exp_min=5, title="Software Engineer", discipline="sde")))
    assert m.decision == "drop" and "Asks for 5+ years; you have 3.2" in m.reasons


def test_a_senior_title_with_no_years_is_a_stretch_for_a_junior():
    jr = seeker(ENGINEER, profile={"experience_years": 1.5, "experience_band": "junior"})
    m = mt.evaluate(jr, opening(ex(employment_type="full_time", title="Senior Software Engineer", discipline="sde")))
    assert any("senior title" in g.lower() for g in m.gaps) and m.bucket != "strong"


def test_strong_match_and_its_reasons():
    e = ex(employment_type="full_time", title="Software Engineer", discipline="sde", exp_min=2, exp_max=4,
           skills_must=["Python", "FastAPI", "PostgreSQL"], skills_nice=["Kafka"],
           apply_routes=[ApplyRoute(type="email", value="priya@acmelabs.io", person_name="Priya Rao",
                                    person_role="Engineering Manager")])
    m = mt.evaluate(seeker(ENGINEER), opening(e, raw="Write to Priya Rao at priya@acmelabs.io"))
    assert m.bucket == "strong" and m.score >= mt.STRONG_AT, (m.score, m.parts)
    assert "Asks for 2 to 4 years; you have 3.2" in m.why
    assert "Posted 3 hours ago" in m.why
    assert m.why[-1] == "Email to Priya Rao (Engineering Manager), given in the post for applying"
    assert m.gaps == []


def test_board_listings_rank_by_age_without_a_ceiling():
    old = mt.evaluate(seeker(ENGINEER), opening(age=20 * 24, source="greenhouse"))
    assert old.decision == "keep" and 0.3 < old.parts["freshness"] < 1
    assert mt.evaluate(seeker(ENGINEER), opening(age=20 * 24)).decision == "drop"     # a post past 72h


def test_one_role_per_company_except_the_opening_already_applied_to():
    applied = {"acmelabs.io": "another-job"}
    m = mt.evaluate(seeker(ENGINEER, applied=applied), opening())
    assert any("one role per company" in r for r in m.reasons)
    m = mt.evaluate(seeker(ENGINEER, applied={"acmelabs.io": "job-1"}), opening())
    assert m.decision == "keep"


def test_override_keeps_a_dropped_opening_and_still_scores_it():
    m = mt.evaluate(seeker(STUDENT), opening(ex(title="Product Designer", discipline="design")), override=True)
    assert m.decision == "keep" and m.bucket is not None and m.reasons


def test_portal_only_and_general_inbox_routes():
    portal = ex(apply_routes=[ApplyRoute(type="ats", value="https://jobs.acmelabs.io/1")])
    m = mt.evaluate(seeker(ENGINEER), opening(portal))
    assert m.route == "portal" and m.apply_to == "https://jobs.acmelabs.io/1" and m.contact is None
    o = opening(ex(apply_routes=[]))
    o.contacts = [ct.Candidate(email="hello@acmelabs.io", context="site_generic", tier=ct.TIER_GENERIC_BOX)]
    m = mt.evaluate(seeker(ENGINEER), o)
    assert m.route == "email" and m.parts["contact"] < mt.contact_credit(None, "https://x")
    assert not any("Email to" in w for w in m.why)                # a general inbox is not a reason


def test_either_of_two_skills_is_one_requirement():
    student = seeker(STUDENT)                       # PixelForge shows PostgreSQL; nothing shows Django
    assert mt.skill_evidence(student, "Django or PostgreSQL") == (mt.SHOWN, ["PixelForge"])
    m = mt.evaluate(student, opening(ex(skills_must=["Django or PostgreSQL"], skills_nice=[])))
    assert not any("Django" in g for g in m.gaps) and m.parts["skills"] == 1.0
