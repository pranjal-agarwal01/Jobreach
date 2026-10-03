"""Curated posts for everyone's pool: one post is one opening however it arrives, a pool key is
only for curators, and only the best few matches get a letter prepared. No database or model."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import curated
from app.main import app
from app.routes import intake

ACTIVITY = "7381234567890123456"


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/posts/riya-sharma_hiring-backend-activity-{}-AbCd?utm_source=share".format(ACTIVITY),
    "https://www.linkedin.com/feed/update/urn:li:activity:{}/".format(ACTIVITY),
    "https://linkedin.com/feed/update/urn%3Ali%3Aactivity%3A{}".format(ACTIVITY),
])
def test_one_linkedin_post_has_one_key_whatever_its_link_looks_like(url):
    assert curated.post_key(url, "any text") == "li:" + ACTIVITY


def test_without_a_linkedin_number_the_link_then_the_text_decides():
    a = curated.post_key("https://example.com/jobs/1?ref=x", "text")
    assert a == curated.post_key("https://www.example.com/jobs/1/", "other text") and a.startswith("url:")
    post = "We're hiring a Backend Intern!\nSend your CV to riya@kitebird.in #hiring #backend"
    copy = "we're   hiring a backend intern!  send your CV to riya@kitebird.in …see more #jobs"
    assert curated.post_key(None, post) == curated.post_key(None, copy)
    assert curated.post_key(None, post) != curated.post_key(None, post.replace("Backend", "Frontend"))


def match(score, bucket, decision="keep"):
    return SimpleNamespace(score=score, bucket=bucket, decision=decision)


def test_letters_go_to_the_best_few_strong_or_good_matches(monkeypatch):
    people = {"u1": match(91, "strong"), "u2": match(70, "good"), "u3": match(88, "strong"),
              "u4": match(95, "gaps"), "u5": match(80, "good", "drop"), "u6": match(60, "good")}
    saved, prepared = [], []
    monkeypatch.setattr(curated, "candidates", lambda family: list(people))

    @contextmanager
    def tx(uid):
        yield SimpleNamespace(uid=uid)
    monkeypatch.setattr(curated, "user_tx", tx)
    monkeypatch.setattr(curated.match_mod, "load_seeker", lambda conn: conn.uid)
    monkeypatch.setattr(curated.match_mod, "load_openings", lambda conn, ids: ["opening"])
    monkeypatch.setattr(curated.match_mod, "evaluate", lambda seeker, o: people[seeker])
    monkeypatch.setattr(curated.match_mod, "save", lambda conn, uid, job, m, ov: saved.append(uid) or "m-" + uid)
    import app.pipeline.run as run_mod
    monkeypatch.setattr(run_mod, "queue_prepare", lambda uid, mid, override=False: prepared.append(uid))

    out = curated.fan_out("j1", "backend", limit=3)
    assert prepared == ["u1", "u3", "u2"]              # best first; a "gaps" match never gets one
    assert "u5" not in saved                            # a match that doesn't suit isn't stored
    assert out == {"matched": 5, "letters": 3}         # everyone else still sees the opening


def test_only_curators_can_make_a_pool_key(monkeypatch):
    from app.auth import User, current_user
    client = TestClient(app)
    app.dependency_overrides[current_user] = lambda: User(id="u1", email="someone@gmail.com")
    try:
        r = client.post("/intake/keys", json={"name": "LinkedIn agent", "scope": "pool"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
    monkeypatch.setattr(intake, "settings", SimpleNamespace(curator_emails=frozenset({"founder@gmail.com"})))
    assert intake.is_curator("Founder@gmail.com") and not intake.is_curator("someone@gmail.com")


def test_a_pool_key_sends_posts_to_everyone_and_repeats_are_duplicates(monkeypatch):
    rows, queued = {}, []

    class Conn:
        def execute(self, sql, params=None):
            flat = " ".join(sql.split())
            if flat.startswith("select count(*) as n from jobs where source = 'curated'"):
                return SimpleNamespace(fetchone=lambda: {"n": 0})
            if flat.startswith("select id::text from jobs where visibility = 'public'"):
                hit = next((jid for jid, r in rows.items() if r["post_key"] == params[0] or r["hash"] == params[1]), None)
                return SimpleNamespace(fetchone=lambda: {"id": hit} if hit else None)
            if flat.startswith("insert into jobs"):
                jid = "j{}".format(len(rows) + 1)
                rows[jid] = {"post_key": params[4], "hash": params[3], "found_by": params[1]}
                return SimpleNamespace(fetchone=lambda: {"id": jid})
            return SimpleNamespace(fetchone=lambda: None)

    @contextmanager
    def tx():
        yield Conn()
    monkeypatch.setattr(intake, "system_tx", tx)
    monkeypatch.setattr(intake, "enqueue", lambda conn, uid, kind, payload: queued.append((uid, kind, payload["job_id"])))
    monkeypatch.setattr(intake, "audit", lambda *a, **k: None)

    link = "https://www.linkedin.com/posts/riya_hiring-activity-{}-x".format(ACTIVITY)
    text = "We're hiring a Backend Intern in Pune. Send your CV to riya@kitebird.in with your projects."
    batch = intake.AgentBatch(leads=[
        {"text": text, "url": link, "age_label": "3h", "combo": "student / backend"},
        {"text": text + " Apply soon!", "url": link + "?utm_source=share"},       # same post, other copy
        {"text": "  " + text.upper() + "  "},                                      # same text, no link
    ])
    out = intake.pool_posts(batch, "founder")
    assert [r["status"] for r in out["results"]] == ["queued", "duplicate", "duplicate"]
    assert queued == [(None, "process_curated", "j1")] and rows["j1"]["found_by"] == "curated: student / backend"
