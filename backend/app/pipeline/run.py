"""
A pasted post, end to end. The post goes through the global half once (opportunity.py: S1
extract, S2 screen, S4 company check, contact candidates), then the per-user half: a match with
a score, reasons and gaps (match.py), and, because pasting a post shows intent, its letter and
tailored resume are prepared straight away (prepare.py, a task of its own so a retry never reads
the post twice). Nothing is ever sent: the person presses Send.
"""
from __future__ import annotations

from typing import Optional

from ..db import user_tx
from . import match as match_mod
from . import opportunity


class LeadError(RuntimeError):
    pass


def process_lead(user_id: str, job_id: str, override: bool = False, prepare: str = "always") -> dict:
    """prepare: "always" for a post the person pasted (pasting shows intent); "suits" for one
    their agent found, prepared only when it is a strong or good match."""
    with user_tx(user_id) as conn:
        job = conn.execute("select id, extracted from jobs where id = %s and owner_user_id = %s",
                           (job_id, user_id)).fetchone()
    if job is None:
        raise LeadError("lead not found")
    if not (override and job["extracted"]):
        opportunity.process(job_id, user_id)
    match_id, m = match_mod.match_one(user_id, job_id, override)

    if m.decision == "drop":
        _finish(user_id, job_id)
        return {"decision": "drop", "reasons": m.reasons, "match_id": match_id}
    if prepare == "always" or override or m.bucket in ("strong", "good"):
        queue_prepare(user_id, match_id, override)
    _finish(user_id, job_id)
    return {"decision": "keep", "match_id": match_id, "bucket": m.bucket, "score": m.score}


def queue_prepare(user_id: str, match_id: str, override: bool = False) -> int:
    from ..worker import enqueue
    with user_tx(user_id) as conn:
        conn.execute("update matches set prepare_status = 'queued', prepare_error = null where id = %s", (match_id,))
        return enqueue(conn, user_id, "prepare_application", {"match_id": match_id, "override": override})


def _finish(user_id: str, job_id: str, note: Optional[str] = None) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update jobs set status = 'done', error = %s where id = %s", (note, job_id))


def fail(user_id: str, job_id: str, message: str) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update jobs set status = 'failed', error = %s where id = %s", (message[:500], job_id))


def queue_rematch(user_id: str) -> None:
    """Re-score this person's openings after their profile, preferences or resumes change. Code
    only and cheap; one waiting re-match is enough. Nothing to do before onboarding is done."""
    from ..worker import enqueue
    with user_tx(user_id) as conn:
        p = conn.execute("select onboarding_step from profiles").fetchone()
        if not p or p["onboarding_step"] != "done":
            return
        conn.execute("reset role")
        if conn.execute("select 1 from task_queue where user_id = %s and kind = 'match_user' and status = 'queued'",
                        (user_id,)).fetchone() is None:
            enqueue(conn, user_id, "match_user", {})
