"""Sign-up and delivery rules that run in code: the role audit's fit cap, GitHub links,
and the one-page build keeping the PDF it measured."""
import io

import pytest
from pypdf import PdfReader

from app import onboarding as onb
from app.pipeline import resume as resume_mod
from app.pipeline.schemas import RoleOptionP
from resume_engine.schema import BuildOptions

from .conftest import PROFILES, load_profile, requires_renderer


def opt(role, field="backend", fit="strong", ev=(), desired=False):
    return RoleOptionP(field=field, role=role, fit=fit, why="", evidence_item_keys=list(ev), gaps=[],
                       desired=desired)


def test_fit_is_capped_by_confirmed_items():
    known = {"queuekit", "campusbites"}
    out = onb.check_role_options([
        opt("Backend Developer Intern", ev=["queuekit", "campusbites"]),          # 2 items: strong stays
        opt("ML Engineer Intern", field="ai_ml", ev=["queuekit"]),                  # 1 item: strong -> good
        opt("Data Analyst Intern", field="data_analytics", fit="good", ev=["made_up_key"]),  # unconfirmed: -> stretch
    ], known)
    fits = {o.role: o.fit for o in out}
    assert fits == {"Backend Developer Intern": "strong", "ML Engineer Intern": "good",
                    "Data Analyst Intern": "stretch"}
    assert next(o for o in out if o.role == "Data Analyst Intern").evidence_item_keys == []


def test_fit_is_never_raised_and_order_is_strongest_then_asked():
    out = onb.check_role_options([
        opt("Frontend Intern", field="frontend", fit="stretch", ev=["a", "b"]),
        opt("QA Intern", field="qa", fit="stretch", desired=True),
        opt("Backend Intern", fit="good", ev=["a"]),
    ], {"a", "b"})
    assert [(o.role, o.fit) for o in out] == [("Backend Intern", "good"), ("QA Intern", "stretch"),
                                              ("Frontend Intern", "stretch")]


def test_duplicate_and_unknown_field_options_are_dropped():
    out = onb.check_role_options([
        opt("Backend  Developer Intern"), opt("backend developer intern"),
        opt("Something", field="other"),
    ], set())
    assert [o.role for o in out] == ["Backend Developer Intern"]


@pytest.mark.parametrize("given,user", [
    ("https://github.com/aarav-mehta", "aarav-mehta"), ("github.com/aarav-mehta/", "aarav-mehta"),
    ("www.github.com/Aarav?tab=repositories", "Aarav"), ("@aarav", "aarav"), ("aarav", "aarav"),
    ("https://gitlab.com/aarav", None), ("https://github.com/a/b", None), ("", None),
])
def test_github_username(given, user):
    assert onb.github_username(given) == user


@requires_renderer
def test_one_page_build_keeps_the_pdf_it_measured():
    data = load_profile(PROFILES[0])
    track = next(iter(data.tracks))
    built = resume_mod.build_one_page(data, BuildOptions(track=track, scale=1.0))
    assert built.pdf and len(PdfReader(io.BytesIO(built.pdf)).pages) == 1
    assert built.pdf_filename.endswith(".pdf") and built.pdf_filename.startswith("resume_")
