"""Tracks, leads, opportunities (matches), applications, resumes, outcomes and the Today view."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from .. import onboarding
from ..auth import User, current_user
from ..config import settings
from ..db import audit, system_tx, user_tx
from ..pipeline import resume as resume_mod
from ..pipeline import match as match_mod
from ..pipeline import run as run_mod
from ..pipeline.contacts import CONTEXT_LABEL
from ..pipeline.draft import gmail_compose_url
from ..worker import enqueue

router = APIRouter()
PDF = "application/pdf"


# ------------------------------------------------------------------ tracks

@router.get("/tracks")
def tracks(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        rows = conn.execute("select * from tracks order by sort").fetchall()
        base = {r["track_key"]: r for r in conn.execute(
            "select id, track_key, scale, ats_score, created_at from resumes where is_baseline").fetchall()}
    return [{**t, "baseline": base.get(t["key"])} for t in rows]


class TrackIn(BaseModel):
    label: Optional[str] = None
    title_line: Optional[str] = None
    summary: Optional[str] = None
    left_sections: Optional[list[dict]] = None
    skills: Optional[list[dict]] = None


@router.put("/tracks/{key}")
def put_track(key: str, body: TrackIn, user: User = Depends(current_user)):
    """An edit to a baseline is the user's own wording; the baseline is re-rendered to one page
    in the background."""
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"ok": True}
    sets = ", ".join("{} = %s".format(k) for k in fields)
    vals = [Jsonb(v) if k in ("left_sections", "skills") else v for k, v in fields.items()]
    with user_tx(user.id) as conn:
        r = conn.execute("update tracks set {}, scale = null where key = %s returning id".format(sets),
                         vals + [key]).fetchone()
        if r is None:
            raise HTTPException(404, "not found")
        conn.execute("""update profiles set build = build || jsonb_build_object('status', 'queued', 'step', 'rendering',
                                                                                'error', null)""")
        task = enqueue(conn, user.id, "calibrate_tracks", {"track_keys": [key]})
    return {"ok": True, "task_id": task}


@router.delete("/tracks/{key}")
def delete_track(key: str, user: User = Depends(current_user)):
    """A baseline is a target role family: deleting it stops targeting that family."""
    try:
        onboarding.remove_family(user.id, key)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    with user_tx(user.id) as conn:      # tracks from before role families
        conn.execute("delete from resume_files where id in (select file_id from resumes where track_key = %s and is_baseline)", (key,))
        conn.execute("delete from tracks where key = %s", (key,))
    run_mod.queue_rematch(user.id)
    return {"ok": True}


@router.get("/tasks/{task_id}")
def task_status(task_id: int, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        conn.execute("reset role")
        r = conn.execute("select id, kind, status, attempts, last_error, updated_at from task_queue "
                         "where id = %s and user_id = %s", (task_id, user.id)).fetchone()
    if r is None:
        raise HTTPException(404, "not found")
    return r


# ------------------------------------------------------------------ leads

class LeadIn(BaseModel):
    text: str
    source_ref: Optional[str] = None
    found_by: Optional[str] = None


def _hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()


@router.post("/leads")
def add_lead(body: LeadIn, user: User = Depends(current_user)):
    text = body.text.strip()
    if len(text) < 40:
        raise HTTPException(400, "Paste the whole post or job description")
    if len(text) > 40000:
        raise HTTPException(400, "That is too long for one post")
    with user_tx(user.id) as conn:
        job = conn.execute(
            """insert into jobs (visibility, owner_user_id, source, source_ref, found_by, raw_text, content_hash)
               values ('private', %s, 'paste', %s, %s, %s, %s)
               on conflict (owner_user_id, content_hash) do nothing returning id::text""",
            (user.id, body.source_ref, body.found_by, text, _hash(text))).fetchone()
        if job is None:
            existing = conn.execute("select id::text from jobs where content_hash = %s and owner_user_id = %s",
                                    (_hash(text), user.id)).fetchone()
            return {"job_id": existing["id"], "duplicate": True}
        enqueue(conn, user.id, "process_lead", {"job_id": job["id"]})
    audit(user.id, "lead_added", {"job": job["id"]})
    return {"job_id": job["id"], "duplicate": False}


LEAD_SELECT = """
  select j.id, j.status, j.error, j.source, j.source_ref, j.found_by, j.first_seen_at, j.posted_age_hours,
         coalesce(j.title, j.extracted->>'title') as title, j.extracted->>'company_name' as company_name,
         j.extracted->>'location_text' as location, j.extracted->'stipend' as stipend,
         m.id as match_id, m.decision, m.reasons, m.screen->'flags' as flags, m.overridden, m.rank, m.track_key,
         m.score, m.bucket, m.prepare_status, m.prepare_error,
         c.verification, c.business_summary, a.id as application_id, a.status as application_status
  from jobs j
  left join matches m on m.job_id = j.id
  left join companies c on c.id = j.company_id
  left join applications a on a.job_id = j.id
"""


@router.get("/leads")
def leads(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        return conn.execute(LEAD_SELECT + " where j.owner_user_id = %s order by j.first_seen_at desc limit 200",
                            (user.id,)).fetchall()


@router.get("/leads/{job_id}")
def lead(job_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        r = conn.execute(LEAD_SELECT + " where j.id = %s", (job_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "not found")
        raw = conn.execute("select raw_text, extracted from jobs where id = %s", (job_id,)).fetchone()
    return {**r, **raw}


@router.post("/leads/{job_id}/override")
def override(job_id: str, user: User = Depends(current_user)):
    """The user can override any drop: the lead is prepared anyway, from the same reading."""
    with user_tx(user.id) as conn:
        r = conn.execute("""select j.id, j.extracted is not null as read, m.id as match_id from jobs j
                            left join matches m on m.job_id = j.id where j.id = %s""", (job_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "not found")
        if not r["read"] or r["match_id"] is None:
            conn.execute("update jobs set status = 'queued' where id = %s", (job_id,))
            enqueue(conn, user.id, "process_lead", {"job_id": job_id, "override": True})
    if r["read"] and r["match_id"] is not None:
        match_id, _ = match_mod.match_one(user.id, job_id, override=True)
        run_mod.queue_prepare(user.id, match_id, override=True)
    audit(user.id, "lead_override", {"job": job_id})
    return {"ok": True}


@router.delete("/leads/{job_id}")
def delete_lead(job_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        conn.execute("delete from jobs where id = %s", (job_id,))
    return {"ok": True}


# ------------------------------------------------------------------ opportunities (matches)

OPP_SELECT = """
  select m.id, m.job_id, m.score, m.bucket, m.why, m.gaps, m.decision, m.reasons, m.overridden, m.track_key,
         m.prepare_status, m.prepare_error, m.seen_at, m.dismissed_at, m.computed_at,
         m.screen->>'route' as route, m.screen->>'apply_to' as apply_to, m.screen->'flags' as flags,
         coalesce(j.title, j.extracted->>'title') as title, j.extracted->>'company_name' as company_name,
         j.role_family, j.employment_type, j.work_mode, j.city, j.exp_min, j.exp_max,
         j.pay_min, j.pay_max, j.pay_currency, j.pay_period, j.skills_must, j.skills_nice,
         j.source, j.source_ref, j.visibility, j.first_seen_at,
         case when j.posted_at is null then null
              else extract(epoch from (now() - j.posted_at)) / 3600 end as age_hours,
         c.domain, c.verification,
         oc.email as contact_email, oc.person_name as contact_name, oc.person_role as contact_role,
         oc.context as contact_context,
         a.id as application_id, a.status as application_status
  from matches m
  join jobs j on j.id = m.job_id
  left join companies c on c.id = j.company_id
  left join opportunity_contacts oc on oc.id = m.contact_id
  left join applications a on a.job_id = m.job_id
"""
BUCKETS = ("strong", "good", "gaps")


@router.get("/opportunities")
def opportunities(user: User = Depends(current_user)):
    """Openings that suit this person, best first, in three groups."""
    with user_tx(user.id) as conn:
        rows = conn.execute(OPP_SELECT + """ where m.decision = 'keep' and m.dismissed_at is null and j.state = 'active'
                            order by m.score desc nulls last, m.computed_at desc limit 300""").fetchall()
    return {b: [r for r in rows if r["bucket"] == b] for b in BUCKETS}


@router.get("/opportunities/{match_id}")
def opportunity(match_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        r = conn.execute(OPP_SELECT + " where m.id = %s", (match_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "not found")
        job = conn.execute("select raw_text, extracted from jobs where id = %s", (r["job_id"],)).fetchone()
        company = conn.execute("""select c.name, c.domain, c.verification, c.business_summary, c.flags from jobs j
                                  join companies c on c.id = j.company_id where j.id = %s""",
                               (r["job_id"],)).fetchone()
        contacts = conn.execute("""select id, email, person_name, person_role, context, source_url, evidence,
                                          is_generic, domain_matches, confidence
                                   from opportunity_contacts where job_id = %s order by confidence desc""",
                                (r["job_id"],)).fetchall()
        conn.execute("update matches set seen_at = coalesce(seen_at, now()) where id = %s", (match_id,))
    return {**r, "job": job, "company": company,
            "contacts": [{**c, "chosen": c["email"] == r["contact_email"], "where": CONTEXT_LABEL[c["context"]]}
                         for c in contacts]}


class PrepareIn(BaseModel):
    override: bool = False


@router.post("/opportunities/{match_id}/prepare")
def prepare_opportunity(match_id: str, body: Optional[PrepareIn] = None, user: User = Depends(current_user)):
    """Write the letter and the tailored resume for this opening (about a minute)."""
    override = bool(body and body.override)
    with user_tx(user.id) as conn:
        m = conn.execute("""select m.id, m.decision, m.overridden, m.prepare_status, a.id::text as application_id
                            from matches m left join applications a on a.job_id = m.job_id where m.id = %s""",
                         (match_id,)).fetchone()
        if m is None:
            raise HTTPException(404, "not found")
        if m["application_id"]:
            return {"application_id": m["application_id"]}
        if m["decision"] == "drop" and not (override or m["overridden"]):
            raise HTTPException(400, "This opening was ruled out for you. Prepare it anyway to override.")
        if override:
            conn.execute("update matches set overridden = true where id = %s", (match_id,))
        if m["prepare_status"] in ("queued", "running"):
            return {"queued": True}
    run_mod.queue_prepare(user.id, match_id, override=override or m["overridden"])
    audit(user.id, "opportunity_prepare", {"match": match_id})
    return {"queued": True}


class DismissIn(BaseModel):
    dismissed: bool = True


@router.post("/opportunities/{match_id}/dismiss")
def dismiss(match_id: str, body: Optional[DismissIn] = None, user: User = Depends(current_user)):
    dismissed = body.dismissed if body else True
    with user_tx(user.id) as conn:
        conn.execute("update matches set dismissed_at = case when %s then now() else null end where id = %s",
                     (dismissed, match_id))
    return {"ok": True}


# ------------------------------------------------------------------ applications

APP_SELECT = """
  select a.*, j.extracted->>'company_name' as company_name, j.extracted->>'poster_name' as poster_name,
         j.source_ref, j.source, c.domain, c.verification, c.business_summary,
         (select d.lint_ok from drafts d where d.application_id = a.id order by d.version desc limit 1) as lint_ok,
         rs.resume_id, rs.resume_filename
  from applications a
  join jobs j on j.id = a.job_id
  left join companies c on c.id = a.company_id
  left join lateral (
    select r.id as resume_id,
           coalesce(f.pdf_filename, regexp_replace(f.filename, '\\.docx$', '.pdf')) as resume_filename
    from resumes r join resume_files f on f.id = r.file_id
    where r.application_id = a.id order by r.created_at desc limit 1) rs on true
"""


@router.get("/applications")
def applications(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        return conn.execute(APP_SELECT + " order by a.created_at desc limit 500").fetchall()


def _html_to_plain(html: str) -> str:
    text = re.sub(r"</p>\s*", "\n\n", html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<li>", "- ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    import html as h
    return h.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()


@router.get("/applications/{app_id}")
def application(app_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        a = conn.execute(APP_SELECT + " where a.id = %s", (app_id,)).fetchone()
        if a is None:
            raise HTTPException(404, "not found")
        d = conn.execute("select * from drafts where application_id = %s order by version desc limit 1",
                         (app_id,)).fetchone()
        r = conn.execute("""select r.id, r.track_key, r.scale, r.pages_verified, r.renderer, r.ats_score, r.jd_match,
                                   r.dropped_ids, r.item_keys, r.created_at,
                                   coalesce(f.pdf_filename, regexp_replace(f.filename, '\\.docx$', '.pdf')) as filename
                            from resumes r join resume_files f on f.id = r.file_id where r.application_id = %s
                            order by r.created_at desc limit 1""", (app_id,)).fetchone()
        if r:
            r["link"] = _active_link(conn, r["id"])
        events = conn.execute("select * from events where application_id = %s order by occurred_at desc",
                              (app_id,)).fetchall()
        job = conn.execute("select raw_text, extracted from jobs where id = %s", (a["job_id"],)).fetchone()
        match = conn.execute("select id, score, bucket, why, gaps from matches where job_id = %s",
                             (a["job_id"],)).fetchone()
        contact = None
        if a["contact_id"]:
            contact = conn.execute("""select email, person_name, person_role, context, source_url, evidence
                                      from opportunity_contacts where id = %s""", (a["contact_id"],)).fetchone()
    draft = None
    if d:
        plain = _html_to_plain(d["html"])
        draft = {**d, "plain": plain,
                 "gmail_url": gmail_compose_url(d["to_addrs"][0], d["subject"], plain) if d["to_addrs"] else None}
    if contact:
        contact = {**contact, "where": CONTEXT_LABEL[contact["context"]]}
    return {"application": a, "draft": draft, "resume": r, "events": events, "job": job, "match": match,
            "contact": contact}


class AppPatch(BaseModel):
    status: Optional[Literal["drafted", "needs_review", "sent", "replied", "interview", "assignment",
                             "rejected", "bounced", "closed"]] = None
    notes: Optional[str] = None


@router.patch("/applications/{app_id}")
def patch_application(app_id: str, body: AppPatch, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    with user_tx(user.id) as conn:
        if "notes" in fields:
            conn.execute("update applications set notes = %s where id = %s", (fields["notes"], app_id))
        if "status" in fields:
            conn.execute("""update applications set status = %s,
                                user_marked_sent_at = case when %s = 'sent' then coalesce(user_marked_sent_at, now())
                                                           else user_marked_sent_at end
                            where id = %s""", (fields["status"], fields["status"], app_id))
            if fields["status"] == "sent":
                conn.execute("insert into events (user_id, application_id, type, summary) values (%s, %s, 'sent', %s)",
                             (user.id, app_id, "Marked sent"))
    return {"ok": True}


class EventIn(BaseModel):
    type: Literal["reply", "bounce", "interview", "assignment", "rejection", "auto_ack", "gated_unpaid",
                  "form_request", "other"]
    occurred_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    summary: Optional[str] = None


STATUS_FOR_EVENT = {"reply": "replied", "bounce": "bounced", "interview": "interview", "assignment": "assignment",
                    "rejection": "rejected", "gated_unpaid": "replied", "form_request": "replied", "auto_ack": None,
                    "other": None}


@router.post("/applications/{app_id}/events")
def add_event(app_id: str, body: EventIn, user: User = Depends(current_user)):
    """Phase 1 outcome logging is manual, one click per event (spec 9)."""
    with user_tx(user.id) as conn:
        conn.execute(
            """insert into events (user_id, application_id, type, occurred_at, deadline_at, summary)
               values (%s, %s, %s, coalesce(%s, now()), %s, %s)""",
            (user.id, app_id, body.type, body.occurred_at, body.deadline_at, body.summary))
        st = STATUS_FOR_EVENT.get(body.type)
        if st:
            conn.execute("update applications set status = %s where id = %s", (st, app_id))
    return {"ok": True}


# ------------------------------------------------------------------ resumes: PDF, download, share link

def _resume_pdf(conn, resume_id: str) -> Optional[tuple[bytes, str]]:
    """The PDF the page check measured. Files from before PDFs were kept are rendered once
    and stored."""
    r = conn.execute("""select f.id, f.filename, f.content, f.pdf, f.pdf_filename from resumes r
                        join resume_files f on f.id = r.file_id where r.id = %s""", (resume_id,)).fetchone()
    if r is None:
        return None
    name = r["pdf_filename"] or re.sub(r"\.docx$", "", r["filename"]) + ".pdf"
    if r["pdf"] is None:
        pdf = resume_mod.pdf_from_docx(bytes(r["content"]))
        conn.execute("update resume_files set pdf = %s, pdf_filename = %s where id = %s", (pdf, name, r["id"]))
        return pdf, name
    return bytes(r["pdf"]), name


def _pdf_response(pdf: bytes, name: str, download: bool) -> Response:
    return Response(pdf, media_type=PDF, headers={
        "Content-Disposition": '{}; filename="{}"'.format("attachment" if download else "inline", name),
        "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"})


@router.get("/resumes/{resume_id}/pdf")
def resume_pdf(resume_id: str, download: bool = False, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        got = _resume_pdf(conn, resume_id)
    if got is None:
        raise HTTPException(404, "not found")
    return _pdf_response(*got, download=download)


@router.get("/resumes/{resume_id}/download")
def download(resume_id: str, user: User = Depends(current_user)):
    return resume_pdf(resume_id, download=True, user=user)


def _link_url(token: str) -> str:
    return "{}/r/{}".format(settings.public_base_url.rstrip("/"), token)


def _active_link(conn, resume_id) -> Optional[dict]:
    row = conn.execute("""select token, opens, last_opened_at, created_at from resume_links
                          where resume_id = %s and revoked_at is null order by created_at desc limit 1""",
                       (resume_id,)).fetchone()
    return {**row, "url": _link_url(row["token"])} if row else None


@router.post("/resumes/{resume_id}/link")
def create_link(resume_id: str, user: User = Depends(current_user)):
    """A share link to put in an email instead of attaching the file. Unguessable, revocable,
    and it counts opens (a number only: no addresses or devices are stored)."""
    with user_tx(user.id) as conn:
        if conn.execute("select 1 from resumes where id = %s", (resume_id,)).fetchone() is None:
            raise HTTPException(404, "not found")
        link = _active_link(conn, resume_id)
        if link is None:
            conn.execute("insert into resume_links (token, user_id, resume_id) values (%s, %s, %s)",
                         (secrets.token_urlsafe(12), user.id, resume_id))
            link = _active_link(conn, resume_id)
    audit(user.id, "resume_link_created", {"resume": resume_id})
    return link


@router.delete("/resumes/{resume_id}/link")
def revoke_link(resume_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        conn.execute("update resume_links set revoked_at = now() where resume_id = %s and revoked_at is null",
                     (resume_id,))
    return {"ok": True}


@router.get("/r/{token}", include_in_schema=False)
def shared_resume(token: str):
    """Public: whoever has the link sees the PDF, until the student revokes it."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", token):
        raise HTTPException(404, "not found")
    with system_tx() as conn:
        link = conn.execute("""update resume_links set opens = opens + 1, last_opened_at = now()
                               where token = %s and revoked_at is null returning resume_id""", (token,)).fetchone()
        got = _resume_pdf(conn, link["resume_id"]) if link else None
    if got is None:
        raise HTTPException(404, "This resume link does not exist or was turned off by its owner")
    return _pdf_response(*got, download=False)


# ------------------------------------------------------------------ today

@router.get("/today")
def today(user: User = Depends(current_user)):
    """Live threads with deadlines first, then letters ready to send, then the openings that
    suit this person in three groups (strong, good, with gaps), then the posts it dropped."""
    with user_tx(user.id) as conn:
        deadlines = conn.execute(
            """select e.*, a.role_title, j.extracted->>'company_name' as company_name from events e
               join applications a on a.id = e.application_id join jobs j on j.id = a.job_id
               where e.type in ('interview', 'assignment', 'form_request', 'gated_unpaid')
                 and (e.deadline_at is null or e.deadline_at > now() - interval '1 day')
                 and a.status not in ('rejected', 'closed')
               order by e.deadline_at nulls last, e.occurred_at desc limit 20""").fetchall()
        ready = conn.execute(
            APP_SELECT + """ where a.status in ('drafted', 'needs_review')
               order by a.age_at_draft_hours nulls last, a.created_at desc limit 30""").fetchall()
        opps = conn.execute(
            OPP_SELECT + """ where m.decision = 'keep' and m.dismissed_at is null and a.id is null
               and j.state = 'active' order by m.score desc nulls last limit 90""").fetchall()
        decisions = conn.execute(
            LEAD_SELECT + """ where j.owner_user_id = %s and m.decision = 'drop' and not m.overridden
               and j.first_seen_at > now() - interval '3 days' order by j.first_seen_at desc limit 20""",
            (user.id,)).fetchall()
        processing = conn.execute(
            """select (select count(*) from jobs where owner_user_id = %s and status in ('queued', 'processing'))
                    + (select count(*) from matches where prepare_status in ('queued', 'running')) as n""",
            (user.id,)).fetchone()
        number_gaps = conn.execute(
            """select b.id, b.text, i.name as item_name from bullets b join items i on i.id = b.item_id
               where b.confirmed and not b.has_metric order by i.sort, b.sort limit 8""").fetchall()
        me = conn.execute("""select p.name, p.career_stage, p.experience_years, p.experience_band, pr.target_families
                             from profiles p left join preferences pr using (user_id)""").fetchone()
        conn.execute("update profiles set last_active_at = now()")    # pre-warm only for people who come back
    return {"deadlines": deadlines, "ready": ready,
            "groups": {b: [o for o in opps if o["bucket"] == b][:30] for b in BUCKETS},
            "decisions": decisions, "number_gaps": number_gaps, "processing": processing["n"], "me": me}
