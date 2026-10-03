"""
The shared opportunity pool (docs/plan-global-pool.md, Phase 4): openings found once, on the
server, for everyone they may suit. No user ever searches, and nothing logs in anywhere.

  tick, a system task the worker schedules every POOL_TICK_MINUTES:
    - recount how many people need each (kind of role, experience band) segment; a segment
      nobody has needed for 14 days pauses, and wakes with a fresh read when someone needs it
    - queue the job boards that are due (each is read every 6 hours); a kind of role someone
      just started needing gets every board read for it at once
    - queue the Hacker News thread twice a day and companies' own sites once a week (that is
      also how boards are discovered: a careers page that links to its board)
    - expire listings that left their board or went unseen for 30 days; delete the contact
      details of openings 30 days after they were last seen
    - prepare a few strong, fresh matches ahead for people who use the app (Phase 5)

  poll_board / poll_hn / scan_company, system tasks below anything a person is waiting for:
    - code passes on postings nobody could want before any model reads them: a kind of role
      nobody targets, a place that is neither India nor open to India, a senior role nobody
      senior is looking for, an internship nobody studying is looking for
    - the rest go through the global half of the pipeline (opportunity.process), at most
      NEW_PER_TASK per task; a board with more queues its own continuation
    - everyone whose kinds of role were touched is re-matched (code only)
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

import httpx
from psycopg.types.json import Jsonb

from . import llm
from . import taxonomy as tx
from .config import settings
from .db import system_tx, user_tx
from .pipeline import opportunity
from .pipeline import screen as screen_mod
from .sources import INDIA_PLACES, Posting, india_or_open
from .sources import boards as boards_src
from .sources import careers as careers_src
from .sources import hn as hn_src

log = logging.getLogger("pool")

BOARD_POLL_HOURS = 6
BOARD_RETRY_HOURS = 1
HN_POLL_HOURS = 12
HN_VALID_DAYS = 35               # a month's thread, plus a few days
COMPANY_SCAN_DAYS = 7
DISCOVER_YC_HOURS = 24
DISCOVER_NEWS_HOURS = 6
COMPANIES_PER_TICK = 10
NEW_PER_TASK = 5                 # openings read per task (each about 30s), so a person's own task never waits long
UNSEEN_EXPIRE_DAYS = 30
CONTACTS_KEEP_DAYS = 30
SEGMENT_IDLE_DAYS = 14
SEGMENT_REFRESH_HOURS = 6
# "Senior" suits someone with 3+ years stretching up; lead, staff, principal, head, manager and
# director roles suit only senior people.
SENIOR_TITLE = re.compile(r"\b(senior|sr)\b", re.I)
LEAD_TITLE = re.compile(r"\b(lead|staff|principal|head|architect|manager|director|vp|vice\s+president|chief)\b",
                        re.I)


# ------------------------------------------------------------------ what is wanted

def watched_from(segments: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    """{kind of role: bands} someone needs. A family's neighbours count too: matching offers
    openings 'close to your target'."""
    out: dict[str, set[str]] = {}
    for family, band in segments:
        for f in tx.family_with_neighbours(family):
            out.setdefault(f, set()).add(band)
    return out


def watched(conn) -> dict[str, set[str]]:
    rows = conn.execute("select role_family, experience_band from pool_segments where status = 'active'").fetchall()
    return watched_from((r["role_family"], r["experience_band"]) for r in rows)


def skip_reason(p: Posting, want: dict[str, set[str]]) -> Optional[str]:
    """Why code passes on a posting before any model reads it; None to read it."""
    family = tx.title_family(p.title)
    if family == "other" or family not in want:
        return "kind of role nobody targets"
    if not india_or_open(p.location, p.remote, p.country):
        return "not in India or open to India"
    bands = want[family]
    internship = tx.is_internship(p.title) or "intern" in (p.employment or "").lower()
    if internship and "intern" not in bands:
        return "internship, and nobody wanting this kind of role is a student"
    if not internship and LEAD_TITLE.search(p.title) and not bands & {"senior", "lead"}:
        return "senior role, and nobody wanting this kind of role is senior"
    if not internship and SENIOR_TITLE.search(p.title) and not bands & {"mid", "senior", "lead"}:
        return "senior role, and nobody wanting this kind of role is senior"
    return None


def place_of(p: Posting) -> str:
    m = INDIA_PLACES.search(p.location or "")
    if m:
        return m.group(0)
    return "remote" if p.remote else (p.location or "")[:40]


def company_of(p: Posting) -> Optional[str]:
    if p.company_domain:
        return p.company_domain.lower()
    return screen_mod.slug(p.company_name) if p.company_name else None


def _hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()


# ------------------------------------------------------------------ reading postings in

def _mark_seen(source: str, ids: list[str]) -> set[str]:
    """Touch the postings already in the pool (a listing that reappears is active again);
    return their ids."""
    if not ids:
        return set()
    with system_tx() as conn:
        rows = conn.execute(
            """update jobs set last_seen_at = now(), state = case when state = 'expired' then 'active' else state end
               where visibility = 'public' and source = %s and source_job_id = any(%s) returning source_job_id""",
            (source, ids)).fetchall()
    return {r["source_job_id"] for r in rows}


def _insert(p: Posting, found_by: str, board_id: Optional[str], company_id: Optional[str]) -> Optional[str]:
    """A new public opening, or None when the same one is already in the pool (from this or
    another source)."""
    age = None
    if p.posted_at:
        age = max(0.0, (datetime.now(timezone.utc) - p.posted_at).total_seconds() / 3600)
    raw = p.raw_text()
    with system_tx() as conn:
        row = conn.execute(
            """insert into jobs (visibility, source, source_ref, found_by, raw_text, content_hash, source_job_id, board_id,
                   company_id, posted_at, posted_age_hours, apply_url, dedupe_key, title, status)
               values ('public', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'queued')
               on conflict do nothing returning id::text""",
            (p.source, p.url, found_by, raw, _hash(raw), p.source_job_id, board_id, company_id, p.posted_at, age,
             p.apply_url, opportunity.dedupe_key(company_of(p), p.title, place_of(p)), p.title[:300])).fetchone()
    return row["id"] if row else None


def _done(job_id: str) -> None:
    with system_tx() as conn:
        conn.execute("update jobs set status = 'done', error = null where id = %s", (job_id,))


def _failed(job_id: str, err: Exception) -> None:
    """A refusal or a malformed reading stays failed (it would fail again); anything else
    (network, rate limit) is removed, so the next read of the board tries it again."""
    permanent = isinstance(err, (llm.LLMRefusal, ValueError))
    with system_tx() as conn:
        if permanent:
            conn.execute("update jobs set status = 'failed', error = %s where id = %s", (str(err)[:500], job_id))
        else:
            conn.execute("delete from jobs where id = %s", (job_id,))


def ingest(postings: list[Posting], *, found_by: str, board_id: Optional[str] = None,
           company_id: Optional[str] = None, families: Optional[Iterable[str]] = None,
           limit: int = NEW_PER_TASK, process: Optional[Callable] = None) -> dict:
    """Bring a source's postings into the pool. families: read only for these kinds of role
    (a kind someone just started needing)."""
    process = process or opportunity.process
    stats = {"listed": len(postings), "known": 0, "skipped": Counter(), "read": 0, "duplicates": 0,
             "failed": 0, "more": False, "families": []}
    if not postings:
        return stats
    with system_tx() as conn:
        want = watched(conn)
    if families is not None:
        only = set(families)
        want = {f: b for f, b in want.items() if f in only}
    known = _mark_seen(postings[0].source, [p.source_job_id for p in postings])
    stats["known"] = len(known)
    fresh = []
    for p in postings:
        if p.source_job_id in known:
            continue
        why = skip_reason(p, want)
        if why:
            stats["skipped"][why] += 1
        else:
            fresh.append(p)
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    fresh.sort(key=lambda p: p.posted_at or oldest, reverse=True)
    stats["more"] = len(fresh) > limit
    touched: set[str] = set()
    for p in fresh[:limit]:
        job_id = _insert(p, found_by, board_id, company_id)
        if job_id is None:
            stats["duplicates"] += 1
            continue
        try:
            r = process(job_id)
        except Exception as e:  # one posting never stops the rest
            log.warning("pool: %s %s not read: %s", p.source, p.source_job_id, e)
            _failed(job_id, e)
            stats["failed"] += 1
            continue
        _done(job_id)
        stats["read"] += 1
        if r.screen.decision == "keep":
            touched.add(opportunity.family_of(r.ex))
    stats["families"] = sorted(touched)
    return stats


def _continue(kind: str, payload: dict) -> None:
    from .worker import enqueue
    with system_tx() as conn:
        enqueue(conn, None, kind, payload)


# ------------------------------------------------------------------ the sources

def poll_board(board_id: str, families: Optional[list[str]] = None, fetch: Optional[Callable] = None) -> dict:
    fetch = fetch or boards_src.fetch
    with system_tx() as conn:
        b = conn.execute("""select b.*, c.name as company, c.domain from source_boards b
                            left join companies c on c.id = b.company_id where b.id = %s""", (board_id,)).fetchone()
    if b is None or b["status"] != "active":
        return {"inactive": True}
    try:
        posts = fetch(b["source"], b["board_token"], b["company"], b["domain"])
    except boards_src.BoardGone:
        with system_tx() as conn:
            conn.execute("update source_boards set status = 'dead', last_error = 'board not found', "
                         "last_polled_at = now() where id = %s", (board_id,))
        return {"gone": True}
    except (httpx.HTTPError, ValueError) as e:
        with system_tx() as conn:
            conn.execute("""update source_boards set last_error = %s, last_polled_at = now(),
                                next_poll_at = now() + make_interval(hours => %s) where id = %s""",
                         (str(e)[:300], BOARD_RETRY_HOURS, board_id))
        return {"error": str(e)}

    stats = ingest(posts, found_by="{}:{}".format(b["source"], b["board_token"]), board_id=str(b["id"]),
                   company_id=str(b["company_id"]) if b["company_id"] else None, families=families)
    with system_tx() as conn:
        if posts:   # an empty answer may be a glitch: unseen listings expire after 30 days instead
            conn.execute("""update jobs set state = 'expired' where board_id = %s and state = 'active'
                            and not (source_job_id = any(%s))""", (board_id, [p.source_job_id for p in posts]))
        conn.execute(
            """update source_boards set last_polled_at = now(), last_found = %s, last_error = null,
                   next_poll_at = case when %s then next_poll_at else now() + make_interval(hours => %s) end
               where id = %s""", (stats["read"], families is not None, BOARD_POLL_HOURS, board_id))
    if stats["more"] and stats["read"]:
        _continue("poll_board", {"board_id": board_id, "families": families})
    fan_out(stats["families"])
    return stats


def poll_hn(get: Optional[Callable] = None) -> dict:
    kw = {"get": get} if get else {}
    thread = hn_src.latest_thread(**kw)
    if not thread:
        return {"thread": None}
    now = datetime.now(timezone.utc)
    posts = [p for p in hn_src.postings(thread, **kw)
             if p.posted_at is None or (now - p.posted_at).days < HN_VALID_DAYS]
    stats = ingest(posts, found_by="hn:" + thread)
    if stats["more"] and stats["read"]:
        _continue("poll_hn", {})
    fan_out(stats["families"])
    return {"thread": thread, **stats}


def scan_company(company_id: str, scan: Optional[Callable] = None) -> dict:
    """A company's own site: register the job board it links to, read the openings it lists,
    and keep its hiring addresses for the contact step."""
    with system_tx() as conn:
        c = conn.execute("select id::text, name, domain from companies where id = %s", (company_id,)).fetchone()
    if c is None or not c["domain"]:
        return {}
    s = (scan or careers_src.scan)(c["domain"], c["name"])
    keep = ("email", "context", "tier", "source_url", "evidence", "is_generic", "domain_matches")
    with system_tx() as conn:
        for source, token in s.boards:
            conn.execute("""insert into source_boards (source, board_token, company_id) values (%s, %s, %s)
                            on conflict (source, board_token) do update
                            set company_id = coalesce(source_boards.company_id, excluded.company_id)""",
                         (source, token, company_id))
        conn.execute("""update companies set careers_checked_at = now(), site_emails = %s, site_emails_at = now()
                        where id = %s""", (Jsonb([{k: getattr(x, k) for k in keep} for x in s.contacts]), company_id))
    stats = ingest(s.postings, found_by="careers:" + c["domain"], company_id=company_id) if s.postings else {}
    if s.postings:
        with system_tx() as conn:
            conn.execute("""update jobs set state = 'expired' where source = 'careers' and company_id = %s
                            and state = 'active' and not (source_job_id = any(%s))""",
                         (company_id, [p.source_job_id for p in s.postings]))
    fan_out((stats or {}).get("families") or [])
    return {"pages": s.pages, "boards": s.boards, "postings": len(s.postings), **(stats or {})}


# ------------------------------------------------------------------ people

def fan_out(families: Iterable[str]) -> int:
    """Re-match everyone who targets one of these kinds of role, or a neighbour of one."""
    fams = set(families)
    if not fams:
        return 0
    from .pipeline.run import queue_rematch
    with system_tx() as conn:
        rows = conn.execute("""select p.user_id::text, p.target_families from preferences p join profiles pr using (user_id)
                               where pr.onboarding_step = 'done'""").fetchall()
    users = [r["user_id"] for r in rows
             if any(fams & tx.family_with_neighbours(t) for t in (r["target_families"] or []))]
    for u in users:
        queue_rematch(u)
    return len(users)


def prewarm(per_day: Optional[int] = None) -> int:
    """Phase 5: for each person active in the last week, prepare up to `per_day` of their
    strongest fresh matches a day before they open them."""
    from .pipeline.run import queue_prepare
    per_day = settings.prewarm_per_day if per_day is None else per_day
    if per_day <= 0:
        return 0
    with system_tx() as conn:
        users = [r["user_id"] for r in conn.execute(
            """select user_id::text from profiles where onboarding_step = 'done'
               and last_active_at > now() - interval '7 days'""").fetchall()]
    n = 0
    for uid in users:
        with user_tx(uid) as conn:
            room = per_day - conn.execute(
                "select count(*) as n from matches where prewarmed_at > now() - interval '1 day'").fetchone()["n"]
            picks = [] if room <= 0 else [r["id"] for r in conn.execute(
                """select m.id::text from matches m join jobs j on j.id = m.job_id
                   left join applications a on a.job_id = m.job_id
                   where m.decision = 'keep' and m.bucket = 'strong' and m.prepare_status is null
                     and m.dismissed_at is null and a.id is null and j.state = 'active'
                     and coalesce(j.posted_at, j.first_seen_at) > now() - interval '7 days'
                   order by m.score desc limit %s""", (room,)).fetchall()]
            for mid in picks:
                conn.execute("update matches set prewarmed_at = now() where id = %s", (mid,))
        for mid in picks:
            queue_prepare(uid, mid)
            n += 1
    return n


# ------------------------------------------------------------------ the tick

def _recount(conn) -> None:
    conn.execute("""update pool_segments s set demand = (
                        select count(*) from preferences p join profiles pr using (user_id)
                        where s.role_family = any(p.target_families) and pr.experience_band = s.experience_band
                          and pr.onboarding_step = 'done')""")
    conn.execute("update pool_segments set idle_since = now() where demand = 0 and idle_since is null")
    # A paused segment someone needs again wakes with a fresh read (last_run_at null).
    conn.execute("""update pool_segments set idle_since = null, status = 'active',
                        last_run_at = case when status = 'paused' then null else last_run_at end
                    where demand > 0 and (idle_since is not null or status <> 'active')""")
    conn.execute("""update pool_segments set status = 'paused'
                    where demand = 0 and status = 'active' and idle_since < now() - make_interval(days => %s)""",
                 (SEGMENT_IDLE_DAYS,))


def _bookkeep(conn) -> None:
    conn.execute(
        """update pool_segments s set
               last_found = (select count(*) from jobs j where j.visibility = 'public' and j.role_family = s.role_family
                             and s.experience_band = any(j.experience_bands)
                             and j.first_seen_at > coalesce(s.last_run_at, now() - interval '1 day')),
               active_count = (select count(*) from jobs j where j.visibility = 'public' and j.state = 'active'
                               and j.status = 'done' and j.role_family = s.role_family
                               and s.experience_band = any(j.experience_bands)
                               and coalesce(j.screen->>'decision', 'keep') = 'keep'),
               last_run_at = now(), next_run_at = now() + make_interval(hours => %s)
           where s.status = 'active' and (s.next_run_at <= now() or s.last_run_at is null)""",
        (SEGMENT_REFRESH_HOURS,))


def _expire(conn) -> None:
    conn.execute("""update jobs set state = 'expired' where visibility = 'public' and state = 'active'
                    and last_seen_at < now() - make_interval(days => %s)""", (UNSEEN_EXPIRE_DAYS,))
    conn.execute("""update jobs set state = 'expired' where visibility = 'public' and state = 'active' and source = 'hn'
                    and coalesce(posted_at, first_seen_at) < now() - make_interval(days => %s)""", (HN_VALID_DAYS,))
    # Third parties' contact details are kept for the hiring purpose only.
    conn.execute("""delete from opportunity_contacts c using jobs j where c.job_id = j.id and j.visibility = 'public'
                    and j.state = 'expired' and j.last_seen_at < now() - make_interval(days => %s)""",
                 (CONTACTS_KEEP_DAYS,))


def tick() -> dict:
    from .worker import enqueue
    out: dict = {}
    with system_tx() as conn:
        _recount(conn)
        want = watched(conn)
        _expire(conn)
        if not want:
            return {"idle": True}
        queued = {r["b"] for r in conn.execute(
            """select payload->>'board_id' as b from task_queue
               where kind = 'poll_board' and status in ('queued', 'running')""").fetchall()}
        new = [r["role_family"] for r in conn.execute(
            "select distinct role_family from pool_segments where status = 'active' and last_run_at is null").fetchall()]
        if new:
            fams = sorted(set().union(*(tx.family_with_neighbours(f) for f in new)))
            boards = [r["id"] for r in conn.execute("select id::text from source_boards where status = 'active'").fetchall()]
            for b in boards:
                enqueue(conn, None, "poll_board", {"board_id": b, "families": fams})
            out["new_families"] = fams
            queued |= set(boards)       # read for the new kinds this time; the rest at the next tick
        due = [r["id"] for r in conn.execute(
            """select id::text from source_boards where status = 'active' and next_poll_at <= now()
               order by next_poll_at limit 100""").fetchall()]
        for b in due:
            if b not in queued:
                enqueue(conn, None, "poll_board", {"board_id": b})
        out["boards"] = len(due)
        hn_recent = conn.execute(
            "select 1 from task_queue where kind = 'poll_hn' and created_at > now() - make_interval(hours => %s) limit 1",
            (HN_POLL_HOURS,)).fetchone()
        if hn_recent is None:
            enqueue(conn, None, "poll_hn", {})
            out["hn"] = True
        # New companies (discover.py): the directory once a day, funding news every few hours.
        if settings.discovery_enabled:
            for kind, hours in (("discover_yc", DISCOVER_YC_HOURS), ("discover_news", DISCOVER_NEWS_HOURS)):
                if conn.execute("select 1 from task_queue where kind = %s and created_at > now() - make_interval(hours => %s)"
                                " limit 1", (kind, hours)).fetchone() is None:
                    enqueue(conn, None, kind, {})
                    out[kind] = True
        companies = [r["id"] for r in conn.execute(
            """select c.id::text from companies c where c.domain is not null and c.verification in ('pass', 'flag')
                 and (c.careers_checked_at is null or c.careers_checked_at < now() - make_interval(days => %s))
                 and not exists (select 1 from task_queue t where t.kind = 'scan_company'
                                 and t.status in ('queued', 'running') and t.payload->>'company_id' = c.id::text)
               order by c.careers_checked_at nulls first limit %s""", (COMPANY_SCAN_DAYS, COMPANIES_PER_TICK)).fetchall()]
        for c in companies:
            enqueue(conn, None, "scan_company", {"company_id": c})
        out["companies"] = len(companies)
        _bookkeep(conn)
    out["prewarmed"] = prewarm()
    return out
