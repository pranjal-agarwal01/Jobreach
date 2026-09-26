"""
One lead end to end: S1 extract, S2 screen, S3 match, S4 verify, then for every lead that
passes (the founder's call: draft automatically) S5 select, S6 resume, S7 draft, S8 lint,
S10 record. Nothing is ever sent: the user presses Send.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from psycopg.types.json import Jsonb

from .. import llm
from ..db import user_tx
from . import draft as draftmod
from . import extract as ex_mod
from . import resume as resume_mod
from . import screen as screen_mod
from . import select as select_mod
from . import verify as verify_mod
from .schemas import Extracted


class LeadError(RuntimeError):
    pass


def _hours_since(ts: datetime) -> float:
    return (datetime.now(timezone.utc) - ts).total_seconds() / 3600


def process_lead(user_id: str, job_id: str, override: bool = False) -> dict:
    ctx = llm.CallContext(user_id=user_id, job_id=job_id)
    with user_tx(user_id) as conn:
        job = conn.execute("select * from jobs where id = %s", (job_id,)).fetchone()
        if job is None:
            raise LeadError("lead not found")
        conn.execute("update jobs set status = 'processing', error = null where id = %s", (job_id,))
        prefs = conn.execute("select * from preferences where user_id = %s", (user_id,)).fetchone() or {}
        profile = conn.execute("select * from profiles where user_id = %s", (user_id,)).fetchone() or {}
        applied = {r["company_key"] for r in conn.execute("select company_key from applications").fetchall()}

    # S1 (reused on an override, so the user's decision runs on the same reading)
    if job["extracted"] and override:
        ex = Extracted.model_validate(job["extracted"])
    else:
        ex = ex_mod.extract(job["raw_text"], job["source_ref"], ctx)
    age = ex_mod.parse_age_hours(ex.posted_age_label)
    key = screen_mod.company_key(ex)

    # S2 + S3 (code)
    sc = screen_mod.global_screen(ex)
    sc = screen_mod.user_match(ex, sc, dict(prefs), dict(profile), applied, age, key)

    # S4 only for survivors: it costs a fetch and a model call.
    v: Optional[verify_mod.Verification] = None
    if sc.decision == "keep" or override:
        v = verify_mod.verify(ex, screen_mod.company_domain(ex), ctx)
        if v.verification == "fail":
            for r in v.reasons:
                sc.drop(r)
        sc.flags.extend(v.flags)
        if v.linkedin_check_url:
            sc.flags.append("Check the company page yourself: " + v.linkedin_check_url)

    decision = "keep" if override else sc.decision
    with user_tx(user_id) as conn:
        conn.execute(
            """update jobs set extracted = %s, posted_age_hours = %s,
                   posted_at = case when %s::numeric is null then null
                                    else first_seen_at - make_interval(secs => %s::numeric * 3600) end,
                   company_id = %s
               where id = %s""",
            (Jsonb(ex.model_dump()), age, age, age, v.company_id if v else None, job_id))
        conn.execute(
            """insert into matches (user_id, job_id, decision, reasons, screen, overridden)
               values (%s, %s, %s, %s, %s, %s)
               on conflict (user_id, job_id) do update set decision = excluded.decision,
                   reasons = excluded.reasons, screen = excluded.screen, overridden = excluded.overridden""",
            (user_id, job_id, decision, Jsonb(sc.reasons), Jsonb(sc.as_json()), override))

    if decision == "drop":
        _finish(user_id, job_id)
        return {"decision": "drop", "reasons": sc.reasons}
    if sc.route is None:
        _finish(user_id, job_id, "Kept, but the post has no apply route to write to")
        return {"decision": "keep", "drafted": False}
    return _draft_application(user_id, job, ex, sc, v, key or "job-" + job_id, age, dict(prefs),
                              dict(profile), ctx)


def _draft_application(user_id, job, ex: Extracted, sc, v, key: str, age: Optional[float],
                       prefs: dict, profile: dict, ctx: llm.CallContext) -> dict:
    job_id = str(job["id"])
    with user_tx(user_id) as conn:
        data = resume_mod.load_resume_data(conn, user_id)
        facts = conn.execute("select id, kind, text from facts where confirmed_at is not null").fetchall()
        education = conn.execute("select institution, degree, meta, result, lines from education where confirmed").fetchall()
    if not data.tracks or not any(it.bullets for it in data.items.values()):
        _finish(user_id, job_id, "Finish onboarding (confirmed items and an approved track) before drafting")
        return {"decision": "keep", "drafted": False}

    chosen = select_mod.select(data, ex, job["raw_text"], ctx)
    sel = chosen.selection

    # Dedupe immediately before creating anything (one role per company, idempotent).
    age_at_draft = (age + _hours_since(job["first_seen_at"])) if age is not None else None
    with user_tx(user_id) as conn:
        app = conn.execute(
            """insert into applications (user_id, job_id, company_id, company_key, role_title, track_key,
                   route, apply_to, status, found_by, age_at_capture_hours, age_at_draft_hours, judgment_calls)
               values (%s, %s, %s, %s, %s, %s, %s, %s, 'needs_review', %s, %s, %s, %s)
               on conflict (user_id, company_key) do nothing returning id::text""",
            (user_id, job_id, v.company_id if v else None, key, sel.role_title, sel.track_key, sc.route,
             sc.apply_to, job["found_by"] or job["source"], age, age_at_draft,
             Jsonb(sc.flags + chosen.notes))).fetchone()
        conn.execute("update matches set track_key = %s, rank = %s where job_id = %s",
                     (sel.track_key, sel.fit_score, job_id))
    if app is None:
        _finish(user_id, job_id, "Already applied to this company (one role per company)")
        return {"decision": "keep", "drafted": False, "duplicate": True}
    app_id = app["id"]
    ctx = llm.CallContext(user_id=user_id, job_id=job_id, application_id=app_id)

    # S6
    ordered = resume_mod.order_bullets(data, chosen.bullet_order)
    built = resume_mod.build_one_page(ordered, chosen.opts, jd_text=job["raw_text"])
    with user_tx(user_id) as conn:
        resume_id = resume_mod.store(conn, user_id, built, sel.track_key, application_id=app_id)

    result = {"decision": "keep", "application_id": app_id, "resume_id": resume_id, "route": sc.route}
    status = "drafted"
    if sc.route == "email":
        bullet_text = {b.id: b.text for it in data.items.values() for b in it.bullets}
        selected = [bullet_text[b] for b in built.result.bullet_ids if b in bullet_text]
        allowed_extra = [str(prefs.get("stipend_floor") or ""), prefs.get("duration_flex") or "",
                         prefs.get("start_date") or "", str(profile.get("batch_year") or ""),
                         str(profile.get("cgpa") or ""), profile.get("grad_date") or ""]
        allowed_extra += [" ".join(str(e[k] or "") for k in ("institution", "degree", "meta", "result"))
                          + " " + " ".join(e["lines"] or []) for e in education]
        allowed_extra += [t.title_line for t in data.tracks.values()]
        d = draftmod.write(ex=ex, raw_text=job["raw_text"], sel=sel, selected_bullets=selected,
                           facts=[dict(f) for f in facts], profile=profile, prefs=prefs,
                           stipend_rule=sc.stipend_rule, to_addr=sc.apply_to,
                           allowed_extra=allowed_extra, ctx=ctx)
        with user_tx(user_id) as conn:
            n = conn.execute("select count(*) as n from drafts where application_id = %s", (app_id,)).fetchone()["n"]
            conn.execute(
                """insert into drafts (user_id, application_id, to_addrs, subject, html, facts_used, lint,
                       lint_ok, version, idempotency_key)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, app_id, [sc.apply_to], d.subject, d.html, Jsonb(d.facts_used),
                 Jsonb([c.as_json() for c in d.checks]), d.ok, n + 1,
                 "{}:{}:v{}".format(user_id, key, n + 1)))
        status = "drafted" if d.ok else "needs_review"
        result.update({"lint_ok": d.ok, "draft_attempts": d.attempts})

    with user_tx(user_id) as conn:
        conn.execute("update applications set status = %s where id = %s", (status, app_id))
    _finish(user_id, job_id)
    result["status"] = status
    return result


def _finish(user_id: str, job_id: str, note: Optional[str] = None) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update jobs set status = 'done', error = %s where id = %s", (note, job_id))


def fail(user_id: str, job_id: str, message: str) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update jobs set status = 'failed', error = %s where id = %s", (message[:500], job_id))
