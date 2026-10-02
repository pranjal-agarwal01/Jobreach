"""Sign-up and delivery rules that run in code: GitHub links, and the one-page build keeping
the PDF it measured."""
import io

import pytest
from pypdf import PdfReader

from app import onboarding as onb
from app.pipeline import resume as resume_mod
from resume_engine.schema import BuildOptions

from .conftest import PROFILES, load_profile, requires_renderer


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
