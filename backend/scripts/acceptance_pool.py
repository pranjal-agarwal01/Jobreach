"""
Phase 4 acceptance (docs/plan-global-pool.md), live: real public job boards, the real database,
the real extraction model. No user account is touched.

  1. A kind of role someone starts needing triggers a read of every board, for that kind.
  2. Postings outside the kinds of role anyone needs are never read by the model.
  3. A posting that leaves its board expires (and comes back if it is listed again).
  4. A new person whose segments already exist sees matches with no fetching at all.

    python scripts/acceptance_pool.py [--boards zeta cred atlan groww]

It seeds the starting boards, adds temporary demand for a few kinds of role, runs a tick, works
through the queued reads for the chosen boards and the Hacker News thread, then removes the
temporary demand and any reads left queued. The openings it read are real public listings and
stay in the pool.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app import pool, worker  # noqa: E402
from app.db import system_tx  # noqa: E402
from app.pipeline import match as mt  # noqa: E402
from app.sources import boards as boards_src  # noqa: E402
from seed_boards import STARTING, add  # noqa: E402

SEGMENTS = [("sde", "junior"), ("backend", "junior"), ("data_analytics", "entry"), ("ai_ml", "mid"), ("devops", "mid")]


def run_queued(board_ids: set[str], since_id: int, budget: int) -> list[dict]:
    """Work through this run's queued pool reads for the chosen boards (and Hacker News)."""
    done = []
    while len(done) < budget:
        with system_tx() as conn:
            t = conn.execute(
                """update task_queue set status = 'running', locked_at = now(), locked_by = 'acceptance',
                       attempts = attempts + 1 where id = (
                       select id from task_queue where status = 'queued' and id > %s
                         and (kind = 'poll_hn' or (kind = 'poll_board' and payload->>'board_id' = any(%s)))
                       order by id limit 1 for update skip locked) returning *""",
                (since_id, sorted(board_ids))).fetchone()
        if t is None:
            break
        t0 = time.monotonic()
        worker.handle(t)
        worker._done(t["id"])
        done.append({"kind": t["kind"], "board": t["payload"].get("board_id"), "seconds": round(time.monotonic() - t0)})
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", nargs="+", default=["zeta", "cred", "atlan", "groww"])
    a = ap.parse_args()
    checks = {}
    print("seeded {} new board(s)".format(add(STARTING)))

    with system_tx() as conn:
        since = conn.execute("select coalesce(max(id), 0) as n from task_queue").fetchone()["n"]
        s1_before = conn.execute("select count(*) as n from llm_calls where step = 's1_extract'").fetchone()["n"]
        made = []
        for fam, band in SEGMENTS:
            r = conn.execute("""insert into pool_segments (role_family, experience_band) values (%s, %s)
                                on conflict (role_family, experience_band) do nothing returning id::text""", (fam, band)).fetchone()
            if r:
                made.append(r["id"])
        boards = {r["board_token"]: r["id"] for r in conn.execute(
            "select board_token, id::text from source_boards where board_token = any(%s)", (a.boards,)).fetchall()}

    try:
        # 1. New segments: the tick queues a family-restricted read of every board.
        out = pool.tick()
        with system_tx() as conn:
            queued = conn.execute("""select count(*) filter (where payload ? 'families') as fam_reads,
                                            count(distinct payload->>'board_id') as boards
                                     from task_queue where id > %s and kind = 'poll_board'""", (since,)).fetchone()
            all_boards = conn.execute("select count(*) as n from source_boards where status = 'active'").fetchone()["n"]
        print("\n1. tick:", out)
        print("   queued {} family reads across {} of {} boards".format(queued["fam_reads"], queued["boards"], all_boards))
        checks["new segment triggers a read of every board"] = queued["boards"] == all_boards and queued["fam_reads"] >= all_boards

        # 2. Read the chosen boards (and Hacker News), through the worker's own task handler.
        t0 = time.monotonic()
        ran = run_queued(set(boards.values()), since, budget=40)
        with system_tx() as conn:
            stats = conn.execute(
                """select count(*) as stored, count(*) filter (where status = 'done') as read_ok,
                          count(*) filter (where screen->>'decision' = 'keep') as kept,
                          count(*) filter (where status = 'failed') as failed
                   from jobs where visibility = 'public' and first_seen_at > now() - interval '2 hours'""").fetchone()
            s1_calls = conn.execute("select count(*) as n from llm_calls where step = 's1_extract'").fetchone()["n"] - s1_before
            fams = conn.execute("""select role_family, count(*) as n from jobs where visibility = 'public' and state = 'active'
                                   and first_seen_at > now() - interval '2 hours' group by role_family order by n desc""").fetchall()
        print("\n2. ran {} read task(s) in {:.0f}s".format(len(ran), time.monotonic() - t0))
        listed = 0
        for token in a.boards:
            src = next(s for s, t, _, _ in STARTING if t == token)
            listed += len(boards_src.fetch(src, token))
        print("   {} postings listed on the chosen boards; {} read by the model ({} kept for matching, {} failed)".format(
            listed, stats["stored"], stats["kept"], stats["failed"]))
        print("   model extraction calls: {}; by kind of role: {}".format(
            s1_calls, ", ".join("{} {}".format(r["n"], r["role_family"]) for r in fams)))
        checks["postings nobody wants are never read"] = s1_calls == stats["stored"] and stats["stored"] < listed

        # 3. A posting that leaves its board expires, and returns when listed again.
        token = next(t for t in a.boards if t in boards)
        src = next(s for s, t, _, _ in STARTING if t == token)
        real = boards_src.fetch(src, token)
        with system_tx() as conn:
            row = conn.execute("""select id::text, source_job_id from jobs where board_id = %s and state = 'active'
                                  order by first_seen_at limit 1""", (boards[token],)).fetchone()
        if row:
            pool.poll_board(boards[token], fetch=lambda *x: [p for p in real if p.source_job_id != row["source_job_id"]])
            with system_tx() as conn:
                gone = conn.execute("select state from jobs where id = %s", (row["id"],)).fetchone()["state"]
            pool.poll_board(boards[token], fetch=lambda *x: real)
            with system_tx() as conn:
                back = conn.execute("select state from jobs where id = %s", (row["id"],)).fetchone()["state"]
            print("\n3. {}: a listing removed from the board -> {}; listed again -> {}".format(token, gone, back))
            checks["a posting that leaves its board expires"] = gone == "expired" and back == "active"

        # 4. A new person whose segments exist: matches straight from the pool, no fetching.
        def no_network(*a, **k):
            raise AssertionError("fetched during matching")
        real_send = httpx.Client.send
        httpx.Client.send = no_network
        try:
            seeker = mt.make_seeker(
                profile={"career_stage": "experienced", "experience_years": 2.5, "experience_band": "junior"},
                prefs={"open_to": ["full_time"], "locations": ["Bengaluru", "Remote"], "remote_ok": True, "onsite_ok": True,
                       "hybrid_ok": True, "salary_floor": None, "excluded_company_types": [], "excluded_companies": [],
                       "target_families": ["sde", "backend"]},
                tracks=[{"key": "backend", "label": "Backend", "role_family": "backend", "fit": "strong"},
                        {"key": "sde", "label": "Software engineering", "role_family": "sde", "fit": "good"}],
                skills=["Java", "Spring Boot", "Python", "PostgreSQL", "Kafka", "Docker", "AWS", "Microservices"],
                items=[{"kind": "experience", "name": "Software Engineer", "tagline": "a payments startup",
                        "stack": "Java, Spring Boot, PostgreSQL, Kafka, Docker",
                        "bullets": ["Built the ledger service in Java and Spring Boot on PostgreSQL",
                                    "Moved settlement events to Kafka"]}])
            with system_tx() as conn:
                ids = [r["id"] for r in conn.execute(
                    """select id::text from jobs where visibility = 'public' and state = 'active' and status = 'done'
                       and coalesce(screen->>'decision', 'keep') = 'keep' and role_family = any(%s)""",
                    (sorted({"sde", "backend", "fullstack", "frontend"}),)).fetchall()]
                openings = mt.load_openings(conn, ids)
            results = sorted(((mt.evaluate(seeker, o), o) for o in openings), key=lambda x: -(x[0].score or 0))
            kept = [(m, o) for m, o in results if m.decision == "keep"]
            print("\n4. a new 2.5-year backend engineer, no fetching: {} opening(s) scored, {} kept".format(len(results), len(kept)))
            for m, o in kept[:5]:
                print("   {:>5}  {:<6} {} at {}".format(m.score, m.bucket, o.cols.get("title"), o.ex.company_name))
                for w in m.why[:2]:
                    print("            + " + w)
                for g in m.gaps[:2]:
                    print("            - " + g)
            checks["a new person sees matches without fetching"] = len(results) > 0
        finally:
            httpx.Client.send = real_send
    finally:
        with system_tx() as conn:
            conn.execute("delete from pool_segments where id = any(%s::uuid[])", (made,))
            left = conn.execute("""delete from task_queue where id > %s and status = 'queued'
                                   and kind in ('poll_board', 'poll_hn', 'scan_company', 'pool_tick') returning id""",
                                (since,)).fetchall()
        print("\nremoved {} temporary segment(s) and {} queued read(s)".format(len(made), len(left)))

    print()
    for k, v in checks.items():
        print("  {:<46} {}".format(k, "PASS" if v else "FAIL"))
    ok = len(checks) == 4 and all(checks.values())
    print("\nPhase 4 acceptance: {}".format("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
