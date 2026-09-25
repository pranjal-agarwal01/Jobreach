import pytest
from pydantic import ValidationError

from resume_engine.schema import Fact, ResumeData, validate_fact_refs

from .conftest import PROFILES, load_profile


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_profile_valid_and_every_line_traces_to_a_confirmed_fact(path):
    data = load_profile(path)
    assert validate_fact_refs(data) == []


def test_at_least_five_synthetic_profiles():
    assert len(PROFILES) >= 5


def test_fact_check_catches_unknown_unconfirmed_and_uncited():
    data = load_profile(PROFILES[0])
    item = next(iter(data.items.values()))
    item.bullets[0].fact_ids = ["nope"]
    item.bullets[1].fact_ids = []
    data.facts.append(Fact(id="f_unconfirmed", kind="metric", text="x", confirmed=False))
    item.bullets[2].fact_ids = ["f_unconfirmed"]
    problems = validate_fact_refs(data)
    assert any("unknown fact 'nope'" in p for p in problems)
    assert any("cites no fact" in p for p in problems)
    assert any("not confirmed" in p for p in problems)


def test_track_referencing_missing_item_is_rejected():
    raw = load_profile(PROFILES[0]).model_dump()
    raw["tracks"]["sde"]["left_sections"][0]["item_ids"].append("ghost")
    with pytest.raises(ValidationError, match="unknown item"):
        ResumeData.model_validate(raw)
