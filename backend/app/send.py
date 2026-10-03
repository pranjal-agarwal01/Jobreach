"""
Send for me: an opt-in. Off by default; without it Jobreach only creates drafts and the person
presses Send in Gmail.

When the person turns it on (Profile > Gmail), each letter that passed every check and is in their
Gmail drafts is sent from their Gmail:

  - at a random moment inside the window they chose (2 to 5 PM by default, in their time zone),
    at least MIN_GAP_MINUTES from their other letters, so the sending looks like a person's;
  - never sooner than their waiting period (two hours by default) after the letter reached their
    Gmail drafts: until then they can edit it there (the edited version is what goes) or cancel
    it in Jobreach;
  - at most their daily number (10 by default, 20 at most);
  - only while the post is fresh: a letter that can't go within MAX_LETTER_AGE_HOURS of the
    opening being found waits for the person instead.

It pauses itself after BOUNCES_TO_PAUSE bounces in a week, or when Gmail's own sending limit is
reached, and says why. A letter that needs a look is never sent; nor is one the person already
sent or deleted in Gmail, marked sent, or closed.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import gmail
from .db import audit, user_tx

log = logging.getLogger("send")

MIN_GAP_MINUTES = 7
MAX_LETTER_AGE_HOURS = 72
LATE_MINUTES = 20            # a send that comes due later than this (the worker was down) moves to the next window
BOUNCES_TO_PAUSE = 2
SEARCH_DAYS = 7


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def zone(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Kolkata")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Asia/Kolkata")


@dataclass
class Plan:
    start: time
    end: time
    tz: ZoneInfo
    cap: int
    grace: timedelta

    @classmethod
    def of(cls, prefs: dict) -> "Plan":
        return cls(start=prefs["auto_send_window_start"], end=prefs["auto_send_window_end"],
                   tz=zone(prefs.get("auto_send_timezone")), cap=int(prefs["auto_send_daily_cap"]),
                   grace=timedelta(minutes=int(prefs["auto_send_grace_minutes"])))

    def windows(self, after: datetime, days: int = SEARCH_DAYS) -> list[tuple[datetime, datetime]]:
        """The sending windows that end after `after`, as (start, end). A window that runs past
        midnight (10 PM to 1 AM) belongs to the day it starts."""
        first = after.astimezone(self.tz).date()
        out = []
        for i in range(-1, days):
            d: date = first + timedelta(days=i)
            s = datetime.combine(d, self.start, self.tz)
            e = datetime.combine(d, self.end, self.tz)
            if e <= s:
                e += timedelta(days=1)
            if e > after:
                out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
        return out

    def window_now(self, at: datetime) -> Optional[tuple[datetime, datetime]]:
        return next(((s, e) for s, e in self.windows(at - timedelta(days=1), 3) if s <= at < e), None)


def pick_time(plan: Plan, earliest: datetime, taken: list[datetime], rng=random) -> Optional[datetime]:
    """A random moment in the first window from `earliest` on that still has room: fewer than the
    daily number of letters in it, and at least MIN_GAP_MINUTES from each of the others."""
    gap = timedelta(minutes=MIN_GAP_MINUTES)
    for s, e in plan.windows(earliest):
        lo = max(s, earliest)
        if lo >= e or sum(1 for t in taken if s <= t < e) >= plan.cap:
            continue
        for _ in range(60):
            t = (lo + (e - lo) * rng.random()).replace(microsecond=0)
            if all(abs(t - x) >= gap for x in taken):
                return t
    return None


def _letter(conn, draft_id: str) -> Optional[dict]:
    return conn.execute(
        """select d.id::text, d.application_id::text, d.lint_ok, d.gmail_draft_id, d.send_at, d.send_cancelled_at,
                  d.gmail_sent_at, coalesce(d.gmail_drafted_at, d.created_at) as in_gmail_at,
                  a.status, a.created_at as found_at,
                  d.version = (select max(version) from drafts x where x.application_id = d.application_id) as latest
           from drafts d join applications a on a.id = d.application_id where d.id = %s""", (draft_id,)).fetchone()


def _taken(conn) -> list[datetime]:
    return [r["t"] for r in conn.execute(
        """select coalesce(gmail_sent_at, send_at) as t from drafts
           where (gmail_sent_at is not null or (send_at is not null and send_cancelled_at is null))
             and coalesce(gmail_sent_at, send_at) > now() - interval '2 days'""").fetchall()]


def why_not(d: Optional[dict]) -> Optional[str]:
    """Why a letter can't be sent for the person, or None."""
    if d is None:
        return "letter not found"
    if not d["latest"]:
        return "a newer version of this letter exists"
    if d["status"] == "needs_review":
        return "it needs a look first"
    if d["status"] != "drafted":
        return "it is marked {}".format(d["status"])
    if not d["lint_ok"]:
        return "it didn't pass every check"
    if not d["gmail_draft_id"]:
        return "it isn't in your Gmail drafts"
    if d["gmail_sent_at"]:
        return "already sent"
    if d["send_cancelled_at"]:
        return "you said not to send it"
    return None


def schedule(user_id: str, draft_id: str, now: Optional[datetime] = None, rng=random) -> Optional[datetime]:
    """Give a letter its moment, when the person turned Send for me on and the letter qualifies.
    Returns the moment, or None (the letter then waits for the person, as without Send for me)."""
    from .worker import enqueue
    now = now or now_utc()
    with user_tx(user_id) as conn:
        prefs = conn.execute("select * from preferences").fetchone()
        if not prefs or not prefs["auto_send"] or prefs["auto_send_paused_reason"]:
            return None
        d = _letter(conn, draft_id)
        if why_not(d) or d["send_at"]:
            return d["send_at"] if d and d["send_at"] else None
        plan = Plan.of(prefs)
        at = pick_time(plan, max(now, d["in_gmail_at"] + plan.grace), _taken(conn), rng)
        if at is None or at > d["found_at"] + timedelta(hours=MAX_LETTER_AGE_HOURS):
            return None
        conn.execute("update drafts set send_at = %s, send_error = null where id = %s", (at, draft_id))
        enqueue(conn, user_id, "gmail_send", {"draft_id": draft_id}, run_after=at)     # last: leaves the person's role
    return at


def schedule_ready(user_id: str) -> int:
    """After turning it on, or changing the window: every qualifying letter in Gmail gets a moment,
    oldest first (it goes stale soonest)."""
    with user_tx(user_id) as conn:
        ids = [r["id"] for r in conn.execute(
            """select distinct on (d.application_id) d.id::text as id, a.created_at
               from drafts d join applications a on a.id = d.application_id
               where a.status = 'drafted' and a.created_at > now() - make_interval(hours => %s)
               order by d.application_id, d.version desc""", (MAX_LETTER_AGE_HOURS,)).fetchall()]
    return sum(1 for i in ids if schedule(user_id, i))


def unschedule_all(user_id: str) -> int:
    """Nothing is sent from now on (the queued tasks find no moment and stop)."""
    with user_tx(user_id) as conn:
        return conn.execute("""update drafts set send_at = null where send_at is not null and gmail_sent_at is null
                               and send_cancelled_at is null""").rowcount


def cancel(user_id: str, application_id: str) -> bool:
    with user_tx(user_id) as conn:
        return conn.execute("""update drafts set send_cancelled_at = now(), send_at = null
                               where application_id = %s and send_at is not null and gmail_sent_at is null""",
                            (application_id,)).rowcount > 0


def pause(user_id: str, reason: str) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update preferences set auto_send_paused_reason = %s", (reason,))
    unschedule_all(user_id)
    audit(user_id, "send_for_me_paused", {"reason": reason[:120]})


def _later(user_id: str, draft_id: str, why: str, now: datetime) -> dict:
    with user_tx(user_id) as conn:
        conn.execute("update drafts set send_at = null where id = %s", (draft_id,))
    at = schedule(user_id, draft_id, now=now)
    return {"moved": why, "to": at.isoformat() if at else None}


def send_due(user_id: str, draft_id: str, now: Optional[datetime] = None, client=None) -> dict:
    """The queued moment has come: check everything again, then send."""
    from .worker import enqueue
    now = now or now_utc()
    with user_tx(user_id) as conn:
        prefs = conn.execute("select * from preferences").fetchone()
        d = _letter(conn, draft_id)
        bounces = conn.execute("""select count(*) as n from events where type = 'bounce'
                                  and occurred_at > now() - interval '7 days'""").fetchone()["n"]
    if not prefs or not prefs["auto_send"] or prefs["auto_send_paused_reason"]:
        return {"skipped": "Send for me is off or paused"}
    if d is None or d["send_at"] is None:
        return {"skipped": "no moment set (cancelled, or Send for me was changed)"}
    reason = why_not(d)
    if reason:
        with user_tx(user_id) as conn:
            conn.execute("update drafts set send_at = null where id = %s", (draft_id,))
        return {"skipped": reason}
    if now < d["send_at"] - timedelta(minutes=1):
        with user_tx(user_id) as conn:
            enqueue(conn, user_id, "gmail_send", {"draft_id": draft_id}, run_after=d["send_at"])
        return {"skipped": "not due yet"}
    plan = Plan.of(prefs)
    window = plan.window_now(now)
    if window is None or now > d["send_at"] + timedelta(minutes=LATE_MINUTES):
        return _later(user_id, draft_id, "outside the window", now)
    with user_tx(user_id) as conn:
        sent_here = conn.execute("select count(*) as n from drafts where gmail_sent_at >= %s and gmail_sent_at < %s",
                                 window).fetchone()["n"]
    if sent_here >= plan.cap:
        return _later(user_id, draft_id, "today's number reached", now)
    if bounces >= BOUNCES_TO_PAUSE:
        pause(user_id, "{} letters bounced in the last 7 days. Check the addresses, then turn Send for me "
                       "back on.".format(bounces))
        return {"paused": "bounces"}
    try:
        msg = gmail.send_draft(user_id, d["gmail_draft_id"], client)
    except gmail.DraftGone as e:
        with user_tx(user_id) as conn:
            conn.execute("update drafts set send_at = null, send_error = %s where id = %s", (str(e), draft_id))
        return {"skipped": str(e)}
    except gmail.SendLimit as e:
        return _later(user_id, draft_id, str(e), now + timedelta(hours=12))
    except gmail.GmailError as e:
        with user_tx(user_id) as conn:
            conn.execute("update drafts set send_at = null, send_error = %s where id = %s", (str(e)[:300], draft_id))
        raise
    with user_tx(user_id) as conn:
        conn.execute("""update drafts set gmail_sent_at = now(), gmail_sent_message_id = %s, send_error = null
                        where id = %s""", (msg.get("id"), draft_id))
        conn.execute("""update applications set status = 'sent', user_marked_sent_at = coalesce(user_marked_sent_at, now())
                        where id = %s and status = 'drafted'""", (d["application_id"],))
        conn.execute("""insert into events (user_id, application_id, type, source, summary)
                        values (%s, %s, 'sent', 'jobreach', 'Sent from your Gmail by Send for me')""",
                     (user_id, d["application_id"]))
    audit(user_id, "send_for_me_sent", {"draft_id": draft_id})
    return {"sent": msg.get("id")}


def status(user_id: str) -> dict:
    """The settings, what is lined up, and what went today: for Profile > Gmail."""
    with user_tx(user_id) as conn:
        p = conn.execute("""select auto_send, auto_send_window_start, auto_send_window_end, auto_send_timezone,
                                   auto_send_daily_cap, auto_send_grace_minutes, auto_send_enabled_at,
                                   auto_send_paused_reason from preferences""").fetchone()
        upcoming = conn.execute(
            """select a.id::text as application_id, j.extracted->>'company_name' as company, a.role_title, d.send_at
               from drafts d join applications a on a.id = d.application_id join jobs j on j.id = a.job_id
               where d.send_at is not null and d.gmail_sent_at is null and d.send_cancelled_at is null
               order by d.send_at limit 10""").fetchall()
        sent = conn.execute("select count(*) as n from drafts where gmail_sent_at > now() - interval '24 hours'").fetchone()["n"]
    if p is None:
        return {"enabled": False}
    return {"enabled": p["auto_send"], "window_start": p["auto_send_window_start"].strftime("%H:%M"),
            "window_end": p["auto_send_window_end"].strftime("%H:%M"), "timezone": p["auto_send_timezone"],
            "daily_cap": p["auto_send_daily_cap"], "grace_minutes": p["auto_send_grace_minutes"],
            "enabled_at": p["auto_send_enabled_at"], "paused_reason": p["auto_send_paused_reason"],
            "upcoming": upcoming, "sent_last_24h": sent}
