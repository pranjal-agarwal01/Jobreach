"""The worker keeps running when Supabase's pooler drops a connection."""
import psycopg
import pytest

from app import worker


def test_a_dropped_connection_is_tried_again_on_a_fresh_one(monkeypatch):
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    calls = []

    def claim():
        calls.append(1)
        if len(calls) == 1:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return {"id": 7}
    assert worker._db_retry(claim) == {"id": 7} and len(calls) == 2


def test_a_database_that_stays_down_is_reported_not_retried_forever(monkeypatch):
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)

    def down():
        raise psycopg.OperationalError("connection refused")
    with pytest.raises(psycopg.OperationalError):
        worker._db_retry(down)


def test_the_loop_waits_out_an_unreachable_database_instead_of_exiting(monkeypatch):
    waits = []

    class Stop(Exception):
        pass

    def sleep(s):
        waits.append(s)
        if len(waits) >= 4:
            raise Stop

    def down():
        raise psycopg.OperationalError("server closed the connection unexpectedly")
    monkeypatch.setattr(worker.time, "sleep", sleep)
    monkeypatch.setattr(worker, "claim", down)
    monkeypatch.setattr(worker, "schedule_pool", lambda: None)
    with pytest.raises(Stop):
        worker.run_forever()
    assert worker.DB_DOWN_WAIT_SECONDS in waits                       # it waited, then went round again
