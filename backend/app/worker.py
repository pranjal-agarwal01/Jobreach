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
from .pipeline import resume as resume_mod
from .pipeline import run as run_mod

log = logging.getLogger("worker")
WORKER_ID = "{}:{}".format(socket.gethostname(), os.getpid())
STALE_MINUTES = 15


def enqueue(conn, user_id: str, kind: str, payload: dict) -> int:
    """Enqueue inside the caller's transaction. The queue is not visible to users, so this
    runs with the connection's own role."""
    conn.execute("reset role")
    row = conn.execute("insert into task_queue (user_id, kind, payload) values (%s, %s, %s) returning id",
                       (user_id, kind, Jsonb(payload))).fetchone()
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
                           order by id for update skip locked limit 1)
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
    elif final and task["kind"] in ("build_profile", "calibrate_tracks", "add_family"):
        onboarding.fail_build(str(task["user_id"]), err)


def handle(task) -> None:
    user_id, p = str(task["user_id"]), task["payload"]
    if task["kind"] == "process_lead":
        run_mod.process_lead(user_id, p["job_id"], override=p.get("override", False))
    elif task["kind"] == "build_profile":
        onboarding.build_profile(user_id)
    elif task["kind"] == "calibrate_tracks":
        onboarding.render_baselines(user_id, p.get("track_keys"))
    elif task["kind"] == "add_family":
        onboarding.add_family(user_id, p["family"])
    else:
        raise ValueError("unknown task kind " + task["kind"])


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("worker %s started", WORKER_ID)
    while True:
        task = claim()
        if task is None:
            time.sleep(settings.worker_poll_seconds)
            continue
        t0 = time.monotonic()
        try:
            handle(task)
            _done(task["id"])
            log.info("task %s %s done in %.1fs", task["id"], task["kind"], time.monotonic() - t0)
        except (llm.LLMRefusal, resume_mod.ResumeTooLong, run_mod.LeadError, ValueError) as e:
            _failed(task, str(e), retry=False)
            log.warning("task %s %s failed: %s", task["id"], task["kind"], e)
        except Exception as e:  # transient: API, network, renderer
            _failed(task, "{}: {}".format(type(e).__name__, e), retry=True)
            log.error("task %s %s error: %s\n%s", task["id"], task["kind"], e, traceback.format_exc())


if __name__ == "__main__":
    run_forever()
