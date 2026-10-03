"""The shared pool's rules in code: which postings are worth reading before any model sees one,
and how a source's postings are brought in. The database and the model are replaced by fakes."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app import llm, pool
from app.sources import Posting

NOW = datetime.now(timezone.utc)


def post(i, title="Backend Engineer", location="Bengaluru, India", **kw):
    return Posting(source="greenhouse", source_job_id=str(i), title=title, text="...", location=location,
                   company_name="Kitebird", company_domain="kitebird.example",
                   posted_at=NOW - timedelta(hours=i), **kw)


WANT = pool.watched_from([("backend", "intern"), ("ai_ml", "mid")])


def test_watched_includes_neighbours_with_their_bands():
    assert WANT["backend"] == {"intern"} and WANT["sde"] == {"intern"} and WANT["fullstack"] == {"intern"}
    assert WANT["ai_ml"] == {"mid"} and WANT["cv"] == {"mid"}
    assert "design" not in WANT


@pytest.mark.parametrize("p,reason", [
    (post(1, "Product Designer"), "kind of role nobody targets"),
    (post(1, "Chief of Staff"), "kind of role nobody targets"),
    (post(1, "Backend Engineer", "London, UK"), "not in India"),
    (post(1, "Backend Engineer", "Remote - US"), "not in India"),
    (post(1, "Senior Backend Engineer"), "senior role"),
    (post(1, "Machine Learning Intern"), "internship"),
    (post(1, "Backend Engineering Intern"), None),
    (post(1, "Software Engineer", "Remote"), None),                  # sde: a neighbour of backend
    (post(1, "Senior ML Engineer", "Remote (APAC)"), None),          # someone mid-level wants AI/ML
    (post(1, "Lead ML Engineer", "Remote (APAC)"), "senior role"),   # lead roles need senior demand
    (post(1, "Director, AI Platform"), "senior role"),
])
def test_skip_reason(p, reason):
    got = pool.skip_reason(p, WANT)
    assert (got is None) if reason is None else (got is not None and reason in got), got


@pytest.fixture
def fake_db(monkeypatch):
    state = {"known": set(), "inserted": [], "done": [], "failed": [], "dupes": set()}

    @contextmanager
    def tx():
        yield None
    monkeypatch.setattr(pool, "system_tx", tx)
    monkeypatch.setattr(pool, "watched", lambda conn: WANT)
    monkeypatch.setattr(pool, "_mark_seen", lambda source, ids: {i for i in ids if i in state["known"]})

    def insert(p, found_by, board_id, company_id):
        if p.source_job_id in state["dupes"]:
            return None
        state["inserted"].append(p.source_job_id)
        return "job-" + p.source_job_id
    monkeypatch.setattr(pool, "_insert", insert)
    monkeypatch.setattr(pool, "_done", lambda job_id: state["done"].append(job_id))
    monkeypatch.setattr(pool, "_failed", lambda job_id, e: state["failed"].append((job_id, type(e).__name__)))
    return state


def reading(family_title="Backend Engineer", decision="keep"):
    from app.pipeline.schemas import Extracted, Stipend
    ex = Extracted(title=family_title, poster_type="company_page", stipend=Stipend(stated="unstated"), discipline="backend")
    return SimpleNamespace(ex=ex, screen=SimpleNamespace(decision=decision))


def test_postings_nobody_wants_are_never_read(fake_db):
    read = []
    posts = [post(1, "Product Designer"), post(2, "Backend Engineer", "London"), post(3, "Backend Intern"),
             post(4, "Senior Backend Engineer")]
    stats = pool.ingest(posts, found_by="greenhouse:kite", process=lambda job_id: read.append(job_id) or reading())
    assert read == ["job-3"]                                          # only the wanted one reached the model
    assert stats["read"] == 1 and sum(stats["skipped"].values()) == 3 and stats["families"] == ["backend"]


def test_known_postings_are_touched_not_reread_and_reading_is_capped(fake_db):
    fake_db["known"] = {"1"}
    posts = [post(i, "Backend Engineering Intern") for i in range(1, 15)]
    stats = pool.ingest(posts, found_by="greenhouse:kite", limit=5, process=lambda job_id: reading())
    assert stats["known"] == 1 and stats["read"] == 5 and stats["more"] is True
    assert fake_db["inserted"] == ["2", "3", "4", "5", "6"]          # newest first


def test_a_family_restricted_read_only_reads_that_family(fake_db):
    posts = [post(1, "Backend Intern"), post(2, "ML Engineer")]
    stats = pool.ingest(posts, found_by="x", families=["ai_ml"], process=lambda job_id: reading("ML Engineer"))
    assert fake_db["inserted"] == ["2"] and stats["skipped"]["kind of role nobody targets"] == 1


def test_duplicates_and_failures_never_stop_the_rest(fake_db):
    fake_db["dupes"] = {"1"}

    def process(job_id):
        if job_id == "job-2":
            raise httpx.ConnectError("down")
        if job_id == "job-3":
            raise llm.LLMRefusal("refused")
        return reading(decision="drop")
    posts = [post(i, "Backend Intern") for i in (1, 2, 3, 4)]
    stats = pool.ingest(posts, found_by="x", process=process)
    assert stats["duplicates"] == 1 and stats["failed"] == 2 and stats["read"] == 1
    assert fake_db["failed"] == [("job-2", "ConnectError"), ("job-3", "LLMRefusal")]
    assert stats["families"] == []                                    # dropped for everyone: nobody to re-match


def test_a_board_that_is_gone_stops_being_polled(monkeypatch):
    calls = []

    @contextmanager
    def tx():
        class Conn:
            def execute(self, sql, params=None):
                calls.append(sql.split()[0:3])
                return SimpleNamespace(fetchone=lambda: {"id": "b1", "status": "active", "source": "lever",
                                                         "board_token": "gone", "company": "X", "domain": "x.example",
                                                         "company_id": None})
        yield Conn()
    monkeypatch.setattr(pool, "system_tx", tx)

    def fetch(*a):
        raise pool.boards_src.BoardGone("404")
    assert pool.poll_board("b1", fetch=fetch) == {"gone": True}
    assert ["update", "source_boards", "set"] in calls
