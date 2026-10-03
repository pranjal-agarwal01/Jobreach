"""
Background worker: claims tasks from the Postgres queue (FOR UPDATE SKIP LOCKED, so any
number of workers can run) and executes them.

    python -m app.worker
"""
from __future__ import annotations

import logging
import os
import socket
import time
import traceback

from psycopg.types.json import Jsonb

from . import llm
from . import onboarding
from .config import settings
from .db import system_tx
from .pipeline import match as match_mod
from .pipeline import opportunity as opp_mod
from .pipeline import prepare as prepare_mod
from .pipeline import resume as resume_mod
from .pipeline import run as run_mod

log = logging.getLogger("worker")
WORKER_ID = "{}:{}".format(socket.gethostname(), os.getpid())
STALE_MINUTES = 15
# The shared pool's tasks (pool.POOL_KINDS) run below anything a person is waiting for.
POOL_KINDS = {"pool_tick", "poll_board", "poll_hn", "scan_company"}
PRIORITY_PERSON, PRIORITY_POOL = 10, 0
SCHEDULE_CHECK_SECONDS = 60


def enqueue(conn, user_id, kind: str, payload: dict) -> int:
    """Enqueue inside the caller's transaction. The queue is not visible to users, so this
    runs with the connection's own role. user_id is None for the pool's own tasks."""
    conn.execute("reset role")
    row = conn.execute(
        "insert into task_queue (user_id, kind, payload, priority) values (%s, %s, %s, %s) returning id",
        (user_id, kind, Jsonb(payload), PRIORITY_POOL if kind in POOL_KINDS else PRIORITY_PERSON)).fetchone()
    return row["id"]


def claim():
    with system_tx() as conn:
        # Requeue tasks whose worker died mid-run.
        conn.execute("""update task_queue set status = 'queued', locked_at = null, locked_by = null
                        where status = 'running' and locked_at < now() - make_interval(mins => %s)""",
                     (STALE_MINUTES,))
        return conn.execute(
            """update task_queue set status = 'running', locked_at = now(), locked_by = %s,
                   attempts = attempts + 1, updated_at = now()
               where id = (select id from task_queue where status = 'queued' and run_after <= now()
                           order by priority desc, id for update skip locked limit 1)
               returning *""", (WORKER_ID,)).fetchone()


def _done(task_id: int) -> None:
    with system_tx() as conn:
        conn.execute("update task_queue set status = 'done', updated_at = now() where id = %s", (task_id,))


def _failed(task, err: str, retry: bool) -> None:
    final = not retry or task["attempts"] >= task["max_attempts"]
    with system_tx() as conn:
        conn.execute(
            """update task_queue set status = %s, last_error = %s, locked_at = null, locked_by = null,
                   run_after = now() + make_interval(secs => %s), updated_at = now() where id = %s""",
            ("failed" if final else "queued", err[:2000], 30 * 2 ** task["attempts"], task["id"]))
    if final and task["kind"] == "process_lead":
        run_mod.fail(str(task["user_id"]), task["payload"]["job_id"], err)
    elif final and task["kind"] == "prepare_application":
        prepare_mod.fail(str(task["user_id"]), task["payload"]["match_id"], err)
    elif final and task["kind"] in ("build_profile", "calibrate_tracks", "add_family"):
        onboarding.fail_build(str(task["user_id"]), err)


def handle(task) -> None:
    user_id, p = (str(task["user_id"]) if task["user_id"] else None), task["payload"]
    if task["kind"] in POOL_KINDS:
        from . import pool
        if task["kind"] == "pool_tick":
            log.info("pool tick: %s", pool.tick())
        elif task["kind"] == "poll_board":
            log.info("board %s: %s", p["board_id"], pool.poll_board(p["board_id"], families=p.get("families")))
        elif task["kind"] == "poll_hn":
            log.info("hacker news: %s", pool.poll_hn())
        else:
            log.info("company %s: %s", p["company_id"], pool.scan_company(p["company_id"]))
    elif task["kind"] == "process_lead":
        run_mod.process_lead(user_id, p["job_id"], override=p.get("override", False))
    elif task["kind"] == "prepare_application":
        prepare_mod.prepare(user_id, p["match_id"], override=p.get("override", False))
    elif task["kind"] == "match_user":
        match_mod.match_user(user_id)
    elif task["kind"] == "build_profile":
        onboarding.build_profile(user_id)
    elif task["kind"] == "calibrate_tracks":
        onboarding.render_baselines(user_id, p.get("track_keys"))
        run_mod.queue_rematch(user_id)
    elif task["kind"] == "add_family":
        onboarding.add_family(user_id, p["family"])
        run_mod.queue_rematch(user_id)
    else:
        raise ValueError("unknown task kind " + task["kind"])


def schedule_pool() -> None:
    """Queue a pool tick when none is waiting and the last one is older than the interval. Any
    number of workers may call this; the check and the insert share one transaction."""
    if not settings.pool_enabled:
        return
    with system_tx() as conn:
        conn.execute("select pg_advisory_xact_lock(hashtext('jobreach_pool_tick'))")
        recent = conn.execute(
            """select 1 from task_queue where kind = 'pool_tick'
               and (status in ('queued', 'running') or created_at > now() - make_interval(mins => %s)) limit 1""",
            (settings.pool_tick_minutes,)).fetchone()
        if recent is None:
            enqueue(conn, None, "pool_tick", {})


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("worker %s started", WORKER_ID)
    last_check = 0.0
    while True:
        if time.monotonic() - last_check > SCHEDULE_CHECK_SECONDS:
            last_check = time.monotonic()
            try:
                schedule_pool()
            except Exception as e:  # the pool must never stop people's own tasks
                log.error("pool schedule: %s", e)
        task = claim()
        if task is None:
            time.sleep(settings.worker_poll_seconds)
            continue
        t0 = time.monotonic()
        try:
            handle(task)
            _done(task["id"])
            log.info("task %s %s done in %.1fs", task["id"], task["kind"], time.monotonic() - t0)
        except (llm.LLMRefusal, resume_mod.ResumeTooLong, run_mod.LeadError, prepare_mod.PrepareError,
                match_mod.MatchError, opp_mod.OpportunityError, ValueError) as e:
            _failed(task, str(e), retry=False)
            log.warning("task %s %s failed: %s", task["id"], task["kind"], e)
        except Exception as e:  # transient: API, network, renderer
            _failed(task, "{}: {}".format(type(e).__name__, e), retry=True)
            log.error("task %s %s error: %s\n%s", task["id"], task["kind"], e, traceback.format_exc())


if __name__ == "__main__":
    run_forever()
