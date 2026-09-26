"""Pipeline rules that run in code: S1 guards, S2/S3 screening, S5 validation, S7 render,
S8 lint and the S4 fetch guard. No database or model calls."""
import pytest

from app.pipeline import draft as draftmod
from app.pipeline import lint as lintmod
from app.pipeline import screen
from app.pipeline import select as selmod
from app.pipeline.extract import email_is_published, enforce_text, parse_age_hours, published_emails
from app.pipeline.schemas import ApplyRoute, EmailDraft, Extracted, Selection, SectionSel, Stipend
from app.pipeline.verify import _safe_url

from .conftest import PROFILES, load_profile

POST = """We're hiring a Backend Intern at Acme Labs (acmelabs.io), Bengaluru, onsite.
Stack: Python, FastAPI, Postgres. Duration 3-6 months. Mail your resume to hr@acmelabs.io
Stipend: Rs 15,000/month."""


def ex(**kw) -> Extracted:
    base = dict(title="Backend Intern", company_name="Acme Labs", company_domain="acmelabs.io",
                poster_name="Priya", poster_type="employee", country="India", remote=False,
                onsite_city="Bengaluru", employment_type="internship",
                stipend=Stipend(stated="figure", min=15000, max=15000, currency="INR", period="month"),
                discipline="backend", apply_routes=[ApplyRoute(type="email", value="hr@acmelabs.io")],
                posted_age_label="3h")
    base.update(kw)
    return Extracted(**base)


PREFS = {"role_types": ["sde", "backend", "fullstack"], "open_to": ["internship"], "locations": ["Bengaluru", "Remote"],
         "remote_ok": True, "onsite_ok": True, "hybrid_ok": True, "stipend_floor": 10000,
         "unpaid_remote_policy": "draft_with_floor", "unpaid_onsite_policy": "drop",
         "excluded_company_types": ["big_tech"], "excluded_companies": [], "freshness_ceiling_hours": 72}
PROFILE = {"batch_year": 2027, "cgpa": 7.9}


def run(e, prefs=PREFS, applied=frozenset()):
    sc = screen.global_screen(e)
    return screen.user_match(e, sc, prefs, PROFILE, set(applied), parse_age_hours(e.posted_age_label),
                             screen.company_key(e))


# ------------------------------------------------------------------ S1 guards

def test_age_labels():
    assert parse_age_hours("45m") == 0.75
    assert parse_age_hours("3h") == 3
    assert parse_age_hours("2d") == 48
    assert parse_age_hours("1w") == 168
    assert parse_age_hours("5 hours ago") == 5
    assert parse_age_hours(None) is None and parse_age_hours("yesterday-ish") is None


def test_only_published_addresses_survive():
    assert email_is_published("HR@acmelabs.io", POST)
    assert not email_is_published("careers@acmelabs.io", POST)   # pattern-inferred: never
    assert "jobs@x.in" in published_emails("write to jobs [at] x [dot] in")
    e = ex(apply_routes=[ApplyRoute(type="email", value="careers@acmelabs.io"),
                         ApplyRoute(type="email", value="hr@acmelabs.io")])
    assert [r.value for r in enforce_text(e, POST).apply_routes] == ["hr@acmelabs.io"]


# ------------------------------------------------------------------ S2 / S3

def test_good_lead_is_kept():
    sc = run(ex())
    assert sc.decision == "keep", sc.reasons
    assert sc.route == "email" and sc.apply_to == "hr@acmelabs.io"
    assert sc.stipend_rule == "none"


@pytest.mark.parametrize("change,reason", [
    (dict(asks_candidate_for_money=True), "money"),
    (dict(mill_signals=["3 certificates on completion"]), "mill"),
    (dict(poster_type="aggregator"), "not the company"),
    (dict(country="Pakistan", remote=False), "geography"),
    (dict(apply_routes=[ApplyRoute(type="dm_only")]), "No apply route"),
    (dict(batch_years=[2025, 2026]), "Batch-year"),
    (dict(cgpa_min=8.5), "CGPA"),
    (dict(company_type_hint="big_tech"), "Excluded company type"),
    (dict(posted_age_label="5d"), "freshness"),
    (dict(discipline="marketing"), "Wrong discipline"),
    (dict(stipend=Stipend(stated="figure", min=5000, max=5000, currency="INR", period="month")), "below the floor"),
    (dict(stipend=Stipend(stated="unpaid")), "Unpaid"),                  # unpaid + onsite
    (dict(onsite_city="Mumbai", location_text="Mumbai"), "not in preferred"),
    (dict(employment_type="full_time"), "full-time"),
])
def test_drops(change, reason):
    sc = run(ex(**change))
    assert sc.decision == "drop"
    assert any(reason.lower() in r.lower() for r in sc.reasons), sc.reasons


def test_already_applied_is_one_role_per_company():
    sc = run(ex(), applied={"acmelabs.io"})
    assert any("one role per company" in r for r in sc.reasons)


def test_unpaid_remote_drafts_with_floor_and_unstated_asks():
    sc = run(ex(remote=True, onsite_city=None, stipend=Stipend(stated="unpaid")))
    assert sc.decision == "keep" and sc.stipend_rule == "state_floor"
    sc = run(ex(stipend=Stipend(stated="unstated")))
    assert sc.decision == "keep" and sc.stipend_rule == "ask"


def test_personal_mailbox_flagged_for_named_employee_dropped_otherwise():
    route = [ApplyRoute(type="email", value="priya.founder@gmail.com")]
    sc = run(ex(apply_routes=route, poster_type="founder"))
    assert sc.decision == "keep" and any("personal mailbox" in f for f in sc.flags)
    sc = run(ex(apply_routes=route, poster_type="unknown", company_name=None, company_domain=None))
    assert sc.decision == "drop"


def test_domain_mismatch_is_a_flag_not_a_drop():
    sc = run(ex(apply_routes=[ApplyRoute(type="email", value="jobs@otherco.in")]))
    assert sc.decision == "keep" and any("differs" in f for f in sc.flags)


def test_annual_salary_normalised_to_monthly():
    e = ex(employment_type="full_time", stipend=Stipend(stated="figure", min=600000, max=800000, period="year"))
    assert screen.monthly(e) == pytest.approx(800000 / 12)


# ------------------------------------------------------------------ S5 validation

def test_selection_discards_unknown_ids_and_keeps_two_bullets_per_item():
    data = load_profile(next(p for p in PROFILES if "rohan" in p.stem))
    sel = Selection(role_title="Backend Intern", track_key="nope",
                    left_sections=[SectionSel(heading="Projects", item_keys=["pixelforge", "ghost"])],
                    bullet_ids=["pf.b2", "made-up-id"], drop_entry_ids=["aw1", "fake"], fit_score=80,
                    fit_reasons=["x"], lead_with="PixelForge")
    ch = selmod.validate(data, sel)
    assert ch.opts.track == "fullstack"                           # fell back to a real track
    assert [s.item_ids for s in ch.opts.left_sections] == [["pixelforge"]]
    assert "made-up-id" not in ch.bullet_order
    kept = [b for b in ch.bullet_order if b.startswith("pf.")]
    assert len(kept) >= 2                                         # never fewer than two
    assert "aw1" in ch.opts.drop and "fake" not in ch.opts.drop


# ------------------------------------------------------------------ S7 render + S8 lint

SIG = "--\nBest Regards,\nAarav Mehta\nMobile No. +91 90000 00001"


def lint_for(d: EmailDraft, **kw):
    html, plain, body = draftmod.render(d, kw.pop("signature", SIG))
    args = dict(subject=d.subject, body_text=body, html=html, to_addr="hr@acmelabs.io", raw_post=POST,
                fact_texts=["QueueKit sustained 300 jobs per second with four workers"],
                allowed_extra=["2027"], recipient_type=d.recipient_type, roles_mentioned=d.roles_mentioned,
                stipend_rule="none", floor=10000, duration_flex="Flexible on duration", post_start_text=None,
                user_start="Immediately", signature_text=SIG, plain_full=plain)
    args.update(kw)
    return {c.name: c for c in lintmod.lint(**args)}


def good_draft(**kw):
    words = ("I build backend services that hold up under load, and QueueKit is the clearest example of that "
             "work. It is a Postgres job queue that sustained 300 jobs per second with four workers in a load "
             "test, and it stopped a college fest app from losing registration emails during peak signups. "
             "I would like to bring that care to the Backend Intern role at Acme Labs, where the stack is "
             "Python and FastAPI. I also wrote the retry logic and the dead-letter table myself, so I know "
             "how these systems fail. My resume is attached. I can start immediately and I am flexible on duration.")
    d = dict(recipient_type="hiring_manager", subject="Backend Intern application: Aarav Mehta",
             paragraphs=["Hi Priya,", words], facts_used=["f1"], roles_mentioned=["Backend Intern"])
    d.update(kw)
    return EmailDraft(**d)


def test_clean_draft_passes_every_check():
    checks = lint_for(good_draft())
    assert all(c.ok for c in checks.values()), {k: c.detail for k, c in checks.items() if not c.ok}


@pytest.mark.parametrize("mutate,check", [
    (lambda p: p.replace("QueueKit is", "QueueKit — my queue — is"), "no_em_dash"),
    (lambda p: p + " See github.com/aarav", "no_bare_urls"),
    (lambda p: p.replace("300 jobs", "900 jobs"), "numbers_backed"),
    (lambda p: p.replace("My resume is attached.", "My CV is enclosed."), "resume_attached"),
    (lambda p: p.replace("flexible on duration", "available for 3-6 months"), "availability_not_narrowed"),
    (lambda p: p + " [Company]", "no_placeholders"),
])
def test_each_lint_rule_blocks(mutate, check):
    d = good_draft()
    d = d.model_copy(update={"paragraphs": [d.paragraphs[0], mutate(d.paragraphs[1])]})
    assert not lint_for(d)[check].ok


def test_lint_recipient_stipend_role_length_signature():
    assert not lint_for(good_draft(), to_addr="careers@acmelabs.io")["recipient_published"].ok
    assert not lint_for(good_draft(), stipend_rule="ask")["stipend_rule"].ok
    assert not lint_for(good_draft(), stipend_rule="state_floor")["stipend_rule"].ok
    assert not lint_for(good_draft(roles_mentioned=["Backend Intern", "ML Intern"]))["one_role"].ok
    assert not lint_for(good_draft(paragraphs=["Hi Priya,", "My resume is attached."]))["length"].ok
    assert not lint_for(good_draft(), plain_full="tampered")["signature_verbatim"].ok


def test_model_html_is_escaped_and_caught():
    d = good_draft(paragraphs=["Hi Priya,", good_draft().paragraphs[1] + " <p>bonus</p>"])
    html, _, _ = draftmod.render(d, SIG)
    assert "<p>bonus</p>" not in html
    assert not lint_for(d)["html_well_formed"].ok


def test_signature_is_appended_verbatim_and_gmail_link_built():
    html, plain, body = draftmod.render(good_draft(), SIG)
    assert plain.endswith(SIG) and SIG not in body
    url = draftmod.gmail_compose_url("hr@acmelabs.io", "Subj", plain)
    assert url.startswith("https://mail.google.com/mail/?view=cm") and "hr%40acmelabs.io" in url


# ------------------------------------------------------------------ S4 fetch guard

@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost", "http://10.0.0.5",
                                 "file:///etc/passwd", "http://example.com:8080", "ftp://example.com",
                                 "http://169.254.169.254/latest/meta-data"])
def test_fetch_guard_refuses_internal_and_odd_urls(url):
    assert not _safe_url(url)
