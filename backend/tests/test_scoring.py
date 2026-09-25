from resume_engine.ats_score import score
from resume_engine.builder import build
from resume_engine.jd_match import match_docx, match_text
from resume_engine.schema import BuildOptions

from .conftest import PROFILES, load_profile


def test_ats_score_runs_on_a_built_resume(tmp_path):
    data = load_profile(next(p for p in PROFILES if "rohan" in p.stem))
    out = tmp_path / "r.docx"
    build(data, BuildOptions(track="fullstack"), str(out))
    total, rows = score(str(out))
    assert 0 < total <= 100
    assert {r.category for r in rows} == {"Parseability", "Contact block", "Section headings",
                                           "Dates", "Content quality", "Skills coverage", "Length"}


def test_jd_match_reads_text_inside_the_layout_table(tmp_path):
    """The reference jd_match read only body paragraphs, which are empty in this layout."""
    data = load_profile(next(p for p in PROFILES if "rohan" in p.stem))
    out = tmp_path / "r.docx"
    build(data, BuildOptions(track="backend"), str(out))
    jd = "We need FastAPI and Celery experience. FastAPI, Redis, PostgreSQL, Kubernetes."
    r = match_docx(str(out), jd)
    covered = {w for w, _ in r.covered}
    assert {"fastapi", "celery", "redis", "postgresql"} <= covered
    assert "kubernetes" in {w for w, _ in r.missing}


def test_extra_stop_words_ignore_company_name():
    r = match_text("python", "Acme Acme Acme wants python", extra_stop=["Acme"])
    assert all(w != "acme" for w, _ in r.covered + r.missing)
