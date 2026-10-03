"""The intake for a person's own agent: keys, the post format, and what happens to a post it
sends. No database or model calls."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.pipeline import run as run_mod
from app.routes import intake


def test_keys_are_random_shown_once_and_stored_as_a_fingerprint():
    key, prefix, digest = intake.new_key()
    assert key.startswith("jri_") and len(key) > 40 and key.startswith(prefix)
    assert digest == intake.key_hash(key) and key not in digest
    assert intake.new_key()[0] != key


@pytest.mark.parametrize("url,canon", [
    ("https://www.LinkedIn.com/posts/priya_hiring-activity-123/?utm_source=share&rcm=x", "https://www.linkedin.com/posts/priya_hiring-activity-123"),
    ("https://www.linkedin.com/feed/update/urn:li:activity:123/", "https://www.linkedin.com/feed/update/urn:li:activity:123"),
    ("javascript:alert(1)", None),
    (None, None),
])
def test_links_lose_tracking_so_the_same_post_is_one_lead(url, canon):
    assert intake.canonical_url(url) == canon


def test_post_age_is_counted_back_from_when_the_agent_saw_it():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    seen = now - timedelta(hours=2)
    posted, age = intake.posted_at_for("3h", seen, now)
    assert posted == now - timedelta(hours=5) and age == pytest.approx(5)
    assert intake.posted_at_for(None, seen, now) == (None, None)
    assert intake.posted_at_for("2d", None, now)[1] == pytest.approx(48)


def test_the_format_is_checked():
    ok = {"text": "We are hiring a backend intern in Pune. Mail hr@acme.example with your resume."}
    intake.AgentBatch(leads=[ok])
    with pytest.raises(ValidationError):
        intake.AgentBatch(leads=[{"text": "too short"}])
    with pytest.raises(ValidationError):
        intake.AgentBatch(leads=[ok] * (intake.MAX_PER_CALL + 1))
    with pytest.raises(ValidationError):
        intake.AgentBatch(leads=[])


def test_only_a_live_intake_key_gets_in(monkeypatch):
    client = TestClient(app)
    body = {"leads": [{"text": "We are hiring a backend intern in Pune. Mail hr@acme.example with your resume."}]}
    assert client.post("/intake/leads", json=body).status_code == 401
    assert client.post("/intake/leads", json=body, headers={"Authorization": "Bearer not-a-key"}).status_code == 401

    @contextmanager
    def tx():
        yield SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: None))   # no such key
    monkeypatch.setattr(intake, "system_tx", tx)
    r = client.post("/intake/leads", json=body, headers={"Authorization": "Bearer jri_revoked"})
    assert r.status_code == 401 and "turned-off" in r.json()["detail"]


@pytest.mark.parametrize("prepare,bucket,prepared", [
    ("always", "gaps", True),      # a pasted post: always
    ("suits", "strong", True),     # the agent's: only when it suits the person
    ("suits", "good", True),
    ("suits", "gaps", False),
])
def test_an_agents_post_is_prepared_only_when_it_suits(monkeypatch, prepare, bucket, prepared):
    calls = []

    @contextmanager
    def tx(user_id):
        yield SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: {"id": "j1", "extracted": None}))
    monkeypatch.setattr(run_mod, "user_tx", tx)
    monkeypatch.setattr(run_mod.opportunity, "process", lambda job_id, user_id: None)
    monkeypatch.setattr(run_mod.match_mod, "match_one",
                        lambda u, j, o: ("m1", SimpleNamespace(decision="keep", bucket=bucket, score=60, reasons=[])))
    monkeypatch.setattr(run_mod, "queue_prepare", lambda u, m, o=False: calls.append(m))
    monkeypatch.setattr(run_mod, "_finish", lambda u, j, note=None: None)
    run_mod.process_lead("u1", "j1", prepare=prepare)
    assert (calls == ["m1"]) is prepared
