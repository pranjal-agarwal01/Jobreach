"""Send for me: when a letter may go, and the checks made again at the moment it goes. Gmail and
the database are replaced by fakes."""
import random
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest

from app import gmail, send

IST = ZoneInfo("Asia/Kolkata")
PREFS = {"auto_send": True, "auto_send_window_start": time(14, 0), "auto_send_window_end": time(17, 0),
         "auto_send_timezone": "Asia/Kolkata", "auto_send_daily_cap": 3, "auto_send_grace_minutes": 120,
         "auto_send_paused_reason": None}


def ist(h, m=0, day=5):
    return datetime(2026, 10, day, h, m, tzinfo=IST).astimezone(timezone.utc)


def test_a_letter_goes_inside_the_window_after_the_waiting_period():
    plan = send.Plan.of(PREFS)
    rng = random.Random(1)
    for written in (ist(9), ist(13, 30), ist(14, 30), ist(15), ist(23)):
        t = send.pick_time(plan, written + plan.grace, [], rng)
        local = t.astimezone(IST)
        assert time(14) <= local.time() < time(17) and t >= written + plan.grace
    assert send.pick_time(plan, ist(14, 30) + plan.grace, [], rng).astimezone(IST).day == 5   # 4:30 to 5 PM is left
    assert send.pick_time(plan, ist(15) + plan.grace, [], rng).astimezone(IST).day == 6       # nothing left: tomorrow


def test_the_daily_number_and_the_gap_between_letters_are_kept():
    plan = send.Plan.of(PREFS)
    rng = random.Random(7)
    taken = []
    for _ in range(7):
        taken.append(send.pick_time(plan, ist(9), taken, rng))
    days = [t.astimezone(IST).day for t in taken]
    assert days.count(5) == 3 and days.count(6) == 3 and days.count(7) == 1
    gaps = [abs(a - b) for i, a in enumerate(taken) for b in taken[i + 1:]]
    assert min(gaps) >= timedelta(minutes=send.MIN_GAP_MINUTES)


def test_a_window_past_midnight_belongs_to_the_day_it_starts():
    plan = send.Plan.of({**PREFS, "auto_send_window_start": time(22), "auto_send_window_end": time(1)})
    t = send.pick_time(plan, ist(23, 30), [], random.Random(3))
    local = t.astimezone(IST)
    assert local >= datetime(2026, 10, 5, 23, 30, tzinfo=IST) and local < datetime(2026, 10, 6, 1, tzinfo=IST)
    assert plan.window_now(ist(0, 30, day=6)) is not None and plan.window_now(ist(12)) is None


def letter(**kw):
    d = {"id": "d1", "application_id": "a1", "lint_ok": True, "gmail_draft_id": "r-1", "send_at": None,
         "send_cancelled_at": None, "gmail_sent_at": None, "in_gmail_at": ist(10), "status": "drafted",
         "found_at": ist(9), "latest": True}
    d.update(kw)
    return d


@pytest.mark.parametrize("kw,reason", [
    ({}, None),
    ({"status": "needs_review"}, "needs a look"),
    ({"status": "sent"}, "marked sent"),
    ({"lint_ok": False}, "didn't pass every check"),
    ({"gmail_draft_id": None}, "isn't in your Gmail drafts"),
    ({"send_cancelled_at": ist(11)}, "said not to send"),
    ({"latest": False}, "newer version"),
])
def test_which_letters_may_be_sent(kw, reason):
    got = send.why_not(letter(**kw))
    assert (got is None) if reason is None else reason in got


class FakeConn:
    def __init__(self, state):
        self.s = state

    def execute(self, sql, params=None):
        s = self.s
        flat = " ".join(sql.split())
        s["sql"].append((flat, params))
        one = None
        if flat.startswith("select * from preferences"):
            one = s["prefs"]
        elif "from drafts d join applications a" in flat and "where d.id" in flat:
            one = s["letter"]
        elif "type = 'bounce'" in flat:
            one = {"n": s["bounces"]}
        elif "count(*) as n from drafts where gmail_sent_at >=" in flat:
            one = {"n": s["sent_in_window"]}
        elif flat.startswith("select coalesce(gmail_sent_at, send_at)"):
            return SimpleNamespace(fetchall=lambda: [{"t": t} for t in s["taken"]], fetchone=lambda: None, rowcount=0)
        elif flat.startswith("update drafts set send_at = %s"):
            s["letter"] = {**s["letter"], "send_at": params[0]}
        elif flat.startswith("update drafts set send_at = null where id"):
            s["letter"] = {**s["letter"], "send_at": None}
        return SimpleNamespace(fetchone=lambda: one, fetchall=lambda: [], rowcount=1)


@pytest.fixture
def db(monkeypatch):
    state = {"prefs": dict(PREFS), "letter": letter(), "bounces": 0, "sent_in_window": 0, "taken": [], "sql": [],
             "queued": [], "audit": []}

    @contextmanager
    def tx(user_id):
        yield FakeConn(state)
    monkeypatch.setattr(send, "user_tx", tx)
    monkeypatch.setattr(send, "audit", lambda u, a, d=None: state["audit"].append(a))
    import app.worker as worker
    monkeypatch.setattr(worker, "enqueue", lambda conn, u, kind, payload, run_after=None:
                        state["queued"].append((kind, run_after)))
    return state


def test_turning_it_on_is_needed_before_anything_is_lined_up(db):
    db["prefs"]["auto_send"] = False
    assert send.schedule("u", "d1", now=ist(10)) is None and db["queued"] == []
    db["prefs"]["auto_send"] = True
    at = send.schedule("u", "d1", now=ist(10), rng=random.Random(2))
    assert at is not None and db["queued"] == [("gmail_send", at)] and at >= ist(12)


def test_a_letter_that_cannot_go_while_the_post_is_fresh_waits_for_the_person(db):
    db["letter"] = letter(found_at=ist(9, day=2), in_gmail_at=ist(10, day=4))   # found 3 days before
    assert send.schedule("u", "d1", now=ist(10, day=5)) is None and db["queued"] == []


def fake_gmail(monkeypatch, result):
    calls = []

    def send_draft(user_id, draft_id, client=None):
        calls.append(draft_id)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(gmail, "send_draft", send_draft)
    return calls


def test_at_its_moment_the_letter_is_sent_and_recorded(db, monkeypatch):
    db["letter"] = letter(send_at=ist(15))
    calls = fake_gmail(monkeypatch, {"id": "msg-1"})
    assert send.send_due("u", "d1", now=ist(15, 1)) == {"sent": "msg-1"} and calls == ["r-1"]
    sql = [q for q, _ in db["sql"]]
    assert any(q.startswith("update drafts set gmail_sent_at") for q in sql)
    assert any(q.startswith("update applications set status = 'sent'") for q in sql)
    assert any("insert into events" in q and "'jobreach'" in q for q in sql)


@pytest.mark.parametrize("change,expect", [
    ({"prefs": {**PREFS, "auto_send": False}}, "skipped"),
    ({"prefs": {**PREFS, "auto_send_paused_reason": "2 bounced"}}, "skipped"),
    ({"letter": letter(send_at=None)}, "skipped"),                         # cancelled or turned off since
    ({"letter": letter(send_at=ist(15), status="sent")}, "skipped"),       # the person marked it sent
])
def test_nothing_goes_when_anything_changed(db, monkeypatch, change, expect):
    db.update(change)
    calls = fake_gmail(monkeypatch, {"id": "x"})
    assert expect in send.send_due("u", "d1", now=ist(15)) and calls == []


def test_late_or_over_the_number_moves_to_the_next_window(db, monkeypatch):
    calls = fake_gmail(monkeypatch, {"id": "x"})
    db["letter"] = letter(send_at=ist(15))
    out = send.send_due("u", "d1", now=ist(18))                          # the worker was down
    assert out["moved"] == "outside the window" and calls == []
    assert out["to"] and datetime.fromisoformat(out["to"]).astimezone(IST).day == 6
    db["letter"], db["sent_in_window"] = letter(send_at=ist(15)), 3
    assert send.send_due("u", "d1", now=ist(15))["moved"] == "today's number reached" and calls == []


def test_bounces_pause_it(db, monkeypatch):
    db["letter"], db["bounces"] = letter(send_at=ist(15)), 2
    calls = fake_gmail(monkeypatch, {"id": "x"})
    assert send.send_due("u", "d1", now=ist(15)) == {"paused": "bounces"} and calls == []
    assert "send_for_me_paused" in db["audit"]


def test_a_draft_already_sent_or_deleted_in_gmail_is_left_alone(db, monkeypatch):
    db["letter"] = letter(send_at=ist(15))
    fake_gmail(monkeypatch, gmail.DraftGone("The letter wasn't in your Gmail drafts any more"))
    assert "wasn't in your Gmail drafts" in send.send_due("u", "d1", now=ist(15))["skipped"]


# ------------------------------------------------------------------ the Gmail call itself

def test_sending_is_refused_unless_it_comes_through_send_for_me():
    hits = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: hits.append(r) or httpx.Response(200, json={})))
    with pytest.raises(gmail.GmailError, match="only through Send for me"):
        gmail._gmail("POST", gmail.DRAFT_SEND_URL, "tok", {"id": "r-1"}, client)
    with pytest.raises(gmail.GmailError):
        gmail._gmail("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", "tok", {}, client,
                     sending=True)                                        # never a new message, only a draft
    assert hits == []
    assert gmail._gmail("POST", gmail.DRAFT_SEND_URL, "tok", {"id": "r-1"}, client, sending=True) == {}


@pytest.mark.parametrize("status,body,error", [
    (404, {"error": {"message": "Requested entity was not found."}}, gmail.DraftGone),
    (429, {"error": {"message": "Too many"}}, gmail.SendLimit),
    (403, {"error": {"errors": [{"reason": "dailyLimitExceeded"}]}}, gmail.SendLimit),
    (400, {"error": {"message": "Invalid To header"}}, gmail.GmailError),
])
def test_gmail_answers_to_a_send(status, body, error):
    with pytest.raises(error):
        gmail._sent(httpx.Response(status, json=body, request=httpx.Request("POST", gmail.DRAFT_SEND_URL)))
