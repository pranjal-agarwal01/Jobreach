"""
Prepare one application: the per-user model half of the pipeline (docs/plan-global-pool.md, A).
Runs when the person opens a match, or straight away for a post they pasted. S5 tailors the
baseline the match chose, S6 builds and page-checks the one-page resume, S7 drafts the letter
to the chosen contact and S8 lints it. Nothing is ever sent: the person presses Send.
"""
from __future__ import annotations

from typing import Optional

from psycopg.types.json import Jsonb

from .. import gmail, llm
from ..db import user_tx
from ..provenance import Corpus
from . import draft as draftmod
from . import resume as resume_mod
from . import screen as screen_mod
from . import select as select_mod
from .contacts import Candidate
from .match import age_now
from .schemas import Extracted


class PrepareError(RuntimeError):
    pass


def record_corpus(docs: list[tuple[str, str]], data) -> Corpus:
    """What a tailored summary may draw on: the person's documents (label, text) and their usable
    record (which includes lines they wrote or restored themselves)."""
    lines = []
    for it in data.items.values():
        lines += [it.name, it.tagline or "", it.stack or "", it.period or ""] + [b.text for b in it.bullets]
    lines += [(e.lead or "") + e.text for s in data.sections for e in s.entries]
    lines += [f.text for f in data.facts]
    lines += [" ".join(x for x in (e.institution, e.degree, e.meta, e.result) if x) for e in data.education]
    return Corpus(docs + [("record", "\n".join(x for x in lines if x))])


def years_numbers(profile: dict) -> set[str]:
    y = profile.get("experience_years")
    return {str(int(float(y))), "{:g}".format(float(y))} if y is not None else set()


def _set(user_id: str, match_id: str, status: str, error: Optional[str] = None) -> None:
    with user_tx(user_id) as conn:
        conn.execute("update matches set prepare_status = %s, prepare_error = %s where id = %s",
                     (status, error[:500] if error else None, match_id))


def fail(user_id: str, match_id: str, message: str) -> None:
    _set(user_id, match_id, "failed", message)


def prepare(user_id: str, match_id: str, override: bool = False) -> dict:
    with user_tx(user_id) as conn:
        m = conn.execute("select * from matches where id = %s", (match_id,)).fetchone()
        if m is None:
            raise PrepareError("match not found")
        existing = conn.execute("select id::text from applications where job_id = %s", (m["job_id"],)).fetchone()
        if existing:
            conn.execute("update matches set prepare_status = 'done', prepare_error = null where id = %s", (match_id,))
            return {"application_id": existing["id"], "existing": True}
        job = conn.execute("select * from jobs where id = %s", (m["job_id"],)).fetchone()
        contact_row = conn.execute("select * from opportunity_contacts where id = %s",
                                   (m["contact_id"],)).fetchone() if m["contact_id"] else None
        prefs = dict(conn.execute("select * from preferences").fetchone() or {})
        profile = dict(conn.execute("select * from profiles").fetchone() or {})
        data = resume_mod.load_resume_data(conn, user_id)
        facts = conn.execute("select id, kind, text from facts where confirmed_at is not null").fetchall()
        education = conn.execute("select institution, degree, meta, result, lines from education where confirmed").fetchall()
        corpus = record_corpus([(d["kind"], d["text"]) for d in conn.execute(
            "select kind, text from source_documents").fetchall()], data)
        conn.execute("update matches set prepare_status = 'running', prepare_error = null where id = %s", (match_id,))

    if m["decision"] == "drop" and not (override or m["overridden"]):
        raise PrepareError("This opening was ruled out for you: " + "; ".join(m["reasons"] or []))
    screen = m["screen"] or {}
    route = screen.get("route")
    if route is None:
        raise PrepareError("There is no way to apply: no published address and no portal")
    if not data.tracks or not any(it.bullets for it in data.items.values()):
        raise PrepareError("Finish setting up your profile (a baseline resume and your projects) first")

    ex = Extracted.model_validate(job["extracted"])
    contact = Candidate.from_row(contact_row) if contact_row else None
    key = screen_mod.company_key(ex) or "job-" + str(job["id"])
    ctx = llm.CallContext(user_id=user_id, job_id=str(job["id"]))
    chosen = select_mod.tailor(data, m["track_key"] or next(iter(data.tracks)), ex, job["raw_text"], ctx,
                               corpus=corpus, band=profile.get("experience_band"),
                               extra_numbers=years_numbers(profile))
    sel = chosen.selection

    with user_tx(user_id) as conn:
        app = conn.execute(
            """insert into applications (user_id, job_id, match_id, contact_id, company_id, company_key, role_title,
                   track_key, route, apply_to, status, found_by, age_at_capture_hours, age_at_draft_hours,
                   judgment_calls)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'needs_review', %s, %s, %s, %s)
               on conflict (user_id, company_key) do nothing returning id::text""",
            (user_id, job["id"], match_id, m["contact_id"], job["company_id"], key, sel.role_title,
             chosen.opts.track, route, screen.get("apply_to"), job["found_by"] or job["source"],
             job["posted_age_hours"], age_now(job["posted_at"], job["posted_age_hours"]),
             Jsonb(list(screen.get("flags") or []) + chosen.notes))).fetchone()
    if app is None:
        raise PrepareError("You already have a letter for this company (one role per company)")
    app_id = app["id"]
    ctx = llm.CallContext(user_id=user_id, job_id=str(job["id"]), application_id=app_id)

    built = build_resume(data, chosen, job["raw_text"])
    with user_tx(user_id) as conn:
        resume_id = resume_mod.store(conn, user_id, built, chosen.opts.track, application_id=app_id)

    result = {"application_id": app_id, "resume_id": resume_id, "route": route}
    status = "drafted"
    draft_id = None
    if route == "email":
        d = write_letter(data=data, chosen=chosen, built=built, raw_text=job["raw_text"], ex=ex, screen=screen,
                         contact=contact, profile=profile, prefs=prefs, facts=[dict(f) for f in facts],
                         education=[dict(e) for e in education], ctx=ctx)
        with user_tx(user_id) as conn:
            n = conn.execute("select count(*) as n from drafts where application_id = %s", (app_id,)).fetchone()["n"]
            draft_id = conn.execute(
                """insert into drafts (user_id, application_id, to_addrs, subject, html, facts_used, lint,
                       lint_ok, version, idempotency_key)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id::text""",
                (user_id, app_id, [screen.get("apply_to")], d.subject, d.html, Jsonb(d.facts_used),
                 Jsonb([c.as_json() for c in d.checks]), d.ok, n + 1, "{}:{}:v{}".format(user_id, key, n + 1))).fetchone()["id"]
        status = "drafted" if d.ok else "needs_review"
        result.update({"lint_ok": d.ok, "draft_attempts": d.attempts})

    # A letter that passed every check goes straight to the person's Gmail drafts when connected.
    to_gmail = draft_id is not None and status == "drafted" and gmail.configured() \
        and (gmail.connection(user_id) or {}).get("status") == "active"
    with user_tx(user_id) as conn:
        conn.execute("update applications set status = %s where id = %s", (status, app_id))
        conn.execute("update matches set prepare_status = 'done', prepare_error = null where id = %s", (match_id,))
        if to_gmail:
            gmail.queue_draft(conn, user_id, draft_id)     # last: it leaves the person's role
    result["status"] = status
    result["gmail"] = to_gmail
    return result


def build_resume(data, chosen: select_mod.Chosen, raw_text: str) -> resume_mod.Built:
    """S6: the tailored baseline, built and page-checked to one page."""
    return resume_mod.build_one_page(chosen.resume_data(resume_mod.order_bullets(data, chosen.bullet_order)),
                                     chosen.opts, jd_text=raw_text)


def write_letter(*, data, chosen: select_mod.Chosen, built: resume_mod.Built, raw_text: str, ex: Extracted,
                 screen: dict, contact: Optional[Candidate], profile: dict, prefs: dict, facts: list[dict],
                 education: list[dict], ctx: llm.CallContext) -> draftmod.DraftOut:
    """S7 + S8: the letter to the chosen contact, linted, with up to two rewrites."""
    bullet_text = {b.id: b.text for it in data.items.values() for b in it.bullets}
    selected = [bullet_text[b] for b in built.result.bullet_ids if b in bullet_text]
    allowed_extra = [str(prefs.get("stipend_floor") or ""), str(prefs.get("salary_floor") or ""),
                     prefs.get("duration_flex") or "", prefs.get("start_date") or "",
                     prefs.get("notice_period") or "", str(profile.get("batch_year") or ""),
                     str(profile.get("cgpa") or ""), profile.get("grad_date") or "",
                     " ".join(years_numbers(profile)), chosen.track.title_line, chosen.track.summary]
    allowed_extra += [" ".join(str(e.get(k) or "") for k in ("institution", "degree", "meta", "result"))
                      + " " + " ".join(e.get("lines") or []) for e in education]
    allowed_extra += [t.title_line for t in data.tracks.values()]
    published_in = [raw_text] + ([contact.evidence or ""] if contact and contact.context != "post_apply" else [])
    return draftmod.write(ex=ex, raw_text=raw_text, sel=chosen.selection, selected_bullets=selected, facts=facts,
                          profile=profile, prefs=prefs, stipend_rule=screen.get("stipend_rule") or "none",
                          to_addr=screen.get("apply_to"), allowed_extra=allowed_extra, ctx=ctx, recipient=contact,
                          published_in=published_in)
