import json
import os
import shutil
from pathlib import Path

import pytest

from resume_engine.legacy import from_v2
from resume_engine.schema import ResumeData

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "tests" / "fixtures"
PROFILES = sorted((FIXTURES / "profiles").glob("*.json"))


def _reference_dir():
    env = os.environ.get("REFERENCE_DIR")
    path = Path(env) if env else BACKEND.parent / "reference"
    return path if (path / "profile" / "resume_data.json").exists() else None


def _has_soffice():
    try:
        from resume_engine.pages import soffice_path
        soffice_path()
        return True
    except Exception:
        return False


requires_reference = pytest.mark.skipif(
    _reference_dir() is None,
    reason="reference/ not present (personal data; local only, never in CI)")
requires_renderer = pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")


@pytest.fixture(scope="session")
def reference_dir():
    ref = _reference_dir()
    if ref is None:
        pytest.skip("reference/ not present")
    return ref


@pytest.fixture(scope="session")
def v2_data(reference_dir):
    with open(reference_dir / "profile" / "resume_data.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def reference_resume(v2_data) -> ResumeData:
    return from_v2(v2_data)


def load_profile(path) -> ResumeData:
    with open(path, encoding="utf-8") as f:
        return ResumeData.model_validate(json.load(f))
