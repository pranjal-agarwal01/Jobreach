"""The global half of the pipeline: normalising an opening into the columns the pool filters on,
and reading one (S1, S2, S4 and contacts) with the model and the network replaced by fakes."""
import pytest

from app.pipeline import contacts as ct
from app.pipeline import opportunity as opp
from app.pipeline.schemas import ApplyRoute, Extracted, Stipend
from app.pipeline.verify import Verification


def ex(**kw):
    base = dict(title="Backend Engineer", company_name="Acme Labs", company_domain="acmelabs.io",
                poster_type="company_page", country="India", remote=False, onsite_city="Bengaluru",
                employment_type="full_time", stipend=Stipend(stated="unstated"), discipline="backend",
                apply_routes=[ApplyRoute(type="email", value="hr@acmelabs.io")], posted_age_label="5h")
    base.update(kw)
    return Extracted(**base)


@pytest.mark.parametrize("title,discipline,family", [
    ("Software Engineer", "backend", "backend"),          # a generic title takes the narrower reading
    ("Software Engineer", "marketing", "sde"),            # ... but only a neighbour's
    ("Senior Data Engineer", "backend", "data_engineering"),
    ("Backend Engineer Intern", "sde", "backend"),
    ("Chief Happiness Wizard", "operations", "operations"),
    ("Software Engineer II", "security", "security"),     # the post's own reading of a generic title
    ("SIEM & SecOps Engineer II", "sde", "security"),
    ("Cloud Network Engineer II", "sde", "devops"),
])
def test_family_from_title_then_reading(title, discipline, family):
    assert opp.family_of(ex(title=title, discipline=discipline)) == family


def test_normalise_columns():
    c = opp.normalise(ex(title="Backend Developer Intern", employment_type="unknown", exp_min=None, exp_max=None,
                         skills_must=["ReactJS", "postgres", "Python"], skills_nice=["React", "k8s"],
                         stipend=Stipend(stated="figure", min=20000, max=30000, currency="Rs", period="month"),
                         apply_routes=[ApplyRoute(type="form", value="https://forms.gle/x"),
                                       ApplyRoute(type="dm_only")]))
    assert c["role_family"] == "backend" and "sde" in c["role_families"] and "fullstack" in c["role_families"]
    assert c["employment_type"] == "internship" and c["experience_bands"] == ["intern"]
    assert c["skills_must"] == ["React", "PostgreSQL", "Python"] and c["skills_nice"] == ["Kubernetes"]
    assert (c["pay_min"], c["pay_max"], c["pay_currency"], c["pay_period"]) == (20000, 30000, "INR", "month")
    assert c["work_mode"] == "onsite" and c["city"] == "Bengaluru"
    assert c["apply_url"] == "https://forms.gle/x"

    c = opp.normalise(ex(exp_min=4, exp_max=2, remote=True, onsite_city=None))   # swapped range
    assert (c["exp_min"], c["exp_max"]) == (2, 4) and c["experience_bands"] == ["junior", "mid"]
    assert c["work_mode"] == "remote" and c["pay_min"] is None


def test_dedupe_key_ignores_case_and_punctuation_but_not_place():
    a = opp.dedupe_key("acmelabs.io", "Backend Engineer (Payments)", "Bengaluru")
    assert a == opp.dedupe_key("AcmeLabs.io", "backend engineer - payments", "bengaluru")
    assert a != opp.dedupe_key("acmelabs.io", "Backend Engineer (Payments)", "Pune")
    assert opp.dedupe_key(None, "Backend Engineer", "Pune") is None


@pytest.fixture
def fakes(monkeypatch):
    calls = {"verify": 0, "site": 0}
    state = {"ex": ex(), "verification": "pass", "site": []}
    monkeypatch.setattr(opp.ex_mod, "extract", lambda raw, ref, ctx: state["ex"])

    def verify(e, domain, ctx):
        calls["verify"] += 1
        return Verification("company-1", state["verification"],
                            reasons=["Business is staffing"] if state["verification"] == "fail" else [])

    def site(domain):
        calls["site"] += 1
        return list(state["site"])
    return state, calls, dict(verify=verify, site=site)


def test_a_post_with_an_address_never_fetches_the_site(fakes):
    state, calls, kw = fakes
    r = opp.read("Send CVs to hr@acmelabs.io", None, None, **kw)
    assert r.screen.decision == "keep" and calls == {"verify": 1, "site": 0}
    assert [c.email for c in r.contacts] == ["hr@acmelabs.io"] and r.age_hours == 5


def test_no_address_in_the_post_looks_on_the_companys_site(fakes):
    state, calls, kw = fakes
    state["ex"] = ex(apply_routes=[ApplyRoute(type="dm_only")])
    state["site"] = [ct.Candidate(email="hello@acmelabs.io", context="site_generic", tier=ct.TIER_GENERIC_BOX)]
    r = opp.read("DM me", None, None, **kw)
    assert calls["site"] == 1 and r.screen.decision == "keep"
    assert any("general inbox" in f for f in r.screen.flags)


def test_no_route_anywhere_is_ruled_out(fakes):
    state, calls, kw = fakes
    state["ex"] = ex(apply_routes=[ApplyRoute(type="comment")])
    r = opp.read("Comment interested", None, None, **kw)
    assert r.screen.decision == "drop" and any("No apply route" in x for x in r.screen.reasons)


def test_ruled_out_for_everyone_skips_the_company_check(fakes):
    state, calls, kw = fakes
    state["ex"] = ex(poster_type="aggregator")
    r = opp.read("Top 10 jobs this week", None, None, **kw)
    assert r.screen.decision == "drop" and calls == {"verify": 0, "site": 0}


def test_a_failed_company_check_rules_the_opening_out(fakes):
    state, calls, kw = fakes
    state["verification"] = "fail"
    state["ex"] = ex(apply_routes=[ApplyRoute(type="dm_only")])
    r = opp.read("DM me", None, None, **kw)
    assert r.screen.decision == "drop" and "Business is staffing" in r.screen.reasons
    assert calls["site"] == 0                             # no harvesting for a company that failed


def test_alternatives_stay_one_requirement_with_canonical_names():
    c = opp.normalise(ex(skills_must=["python", "fastapi or django", "CI/CD"]))
    assert c["skills_must"] == ["Python", "FastAPI or Django", "CI/CD"]


def test_a_company_board_is_the_company_whatever_the_model_reads(fakes):
    state, calls, kw = fakes
    state["ex"] = ex(poster_type="aggregator", shared_by_third_party=True)
    assert opp.read("...", None, None, source="paste", **kw).screen.decision == "drop"
    r = opp.read("...", None, None, source="lever", **kw)
    assert r.screen.decision == "keep" and r.ex.poster_type == "company_page"
