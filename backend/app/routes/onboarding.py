"""One-form onboarding: send the form, follow the background build, review, finish."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi import Form as FormField
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ValidationError

from .. import onboarding as onb
from ..auth import User, current_user
from ..config import settings
from ..db import audit, user_tx
from ..worker import enqueue
from .me import ensure_user

router = APIRouter(prefix="/onboarding")
MAX_UPLOAD = 5 * 1024 * 1024
MAX_FILES = 6


class StartForm(BaseModel):
    stage: Literal["student", "graduate", "experienced"]
    families: list[str] = []
    titles: list[str] = []
    github: str = ""
    portfolio: str = ""
    linkedin: str = ""
    other_links: str = ""
    notes: str = ""
    open_to: list[Literal["internship", "full_time"]] = []
    remote_ok: bool = True
    hybrid_ok: bool = True
    onsite_ok: bool = True
    locations: list[str] = []
    stipend_floor: Optional[int] = None
    salary_floor: Optional[int] = None
    notice_period: Optional[str] = None
    start_date: Optional[str] = None
    excluded_companies: list[str] = []
    skip_big_tech: Optional[bool] = None
    consent_version: Optional[str] = None


@router.post("/start")
async def start(files: list[UploadFile] = File(default=[]), form: str = FormField(...),
                user: User = Depends(current_user)):
    """The one form: CVs, links, notes, the roles wanted and the usual preferences. Starts the
    build and returns at once; the building screen follows /onboarding/status."""
    ensure_user(user)
    try:
        f = StartForm.model_validate_json(form)
    except ValidationError as e:
        raise HTTPException(400, "The form is incomplete: " + e.errors()[0]["msg"]) from e
    families = onb.families_for(f.families, f.titles)
    if not families:
        raise HTTPException(400, "Pick at least one kind of role")
    if len(files) > MAX_FILES:
        raise HTTPException(400, "Up to {} files".format(MAX_FILES))
    uploads = []
    for up in files:
        data = await up.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "{} is larger than 5 MB".format(up.filename))
        try:
            text = onb.text_from_upload(up.filename or "", data)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        if text.strip():
            uploads.append((up.filename or "CV", text))
    if f.github.strip() and onb.github_username(f.github) is None:
        raise HTTPException(400, "That GitHub link doesn't look like github.com/<username>")
    if not uploads and len(f.notes.strip()) < 80 and not f.github.strip():
        raise HTTPException(400, "Upload your CV, or write a few lines about your work, so there is something to build from")

    with user_tx(user.id) as conn:
        consented = conn.execute("select consent_version from profiles").fetchone()["consent_version"]
        if consented != settings.consent_version:
            if f.consent_version != settings.consent_version:
                raise HTTPException(400, "Please read and agree to how your data is used")
            conn.execute("update profiles set consent_version = %s, consented_at = now()", (f.consent_version,))
        onb.apply_form(conn, user.id, onb.Form(**f.model_dump(exclude={"consent_version"})), uploads)
        enqueue(conn, user.id, "build_profile", {})
    audit(user.id, "onboarding_started", {"files": len(uploads), "families": families})
    return {"ok": True, "families": families}


@router.get("/status")
def status(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        return conn.execute("select onboarding_step as step, build from profiles").fetchone()


LEFT_OUT = """
  select 'item' as kind, i.id::text, i.name as text, null as context, i.provenance->>'reason' as reason, i.sort
    from items i where not i.confirmed
  union all
  select 'bullet', b.id::text, b.text, i.name, b.provenance->>'reason', i.sort * 100 + b.sort
    from bullets b join items i on i.id = b.item_id where not b.confirmed and i.confirmed
  union all
  select 'entry', e.id::text, concat_ws(' ', e.lead, e.text), null, e.provenance->>'reason', 10000 + e.sort
    from entries e where not e.confirmed
  union all
  select 'education', ed.id::text, ed.institution, null, ed.provenance->>'reason', 20000 + ed.sort
    from education ed where not ed.confirmed
  union all
  select 'skill', f.id::text, f.text, null, f.provenance->>'reason', 30000
    from facts f where f.kind = 'skill' and f.confirmed_at is null
  order by 6
"""


@router.get("/review")
def review(user: User = Depends(current_user)):
    """Everything the review screen shows: who we think you are, a baseline per role family,
    what the record also supports, and what was left out and why."""
    with user_tx(user.id) as conn:
        profile = conn.execute("""select name, career_stage, experience_years, experience_band, build,
                                         onboarding_step, grad_date, batch_year from profiles""").fetchone()
        prefs = conn.execute("select target_families, desired_roles from preferences").fetchone()
        tracks = conn.execute("select * from tracks order by sort").fetchall()
        base = {r["track_key"]: r for r in conn.execute(
            """select id, track_key, scale, ats_score, dropped_ids, created_at from resumes where is_baseline""").fetchall()}
        names = {r["key"]: r["name"] for r in conn.execute("select key, name from items").fetchall()}
        left_out = conn.execute(LEFT_OUT).fetchall()
        counts = conn.execute(
            """select (select count(*) from items where confirmed) as items,
                      (select count(*) from bullets where confirmed) as bullets,
                      (select count(*) from facts where kind = 'skill' and confirmed_at is not null) as skills""").fetchone()
    return {"profile": profile, "preferences": prefs, "item_names": names, "counts": counts,
            "tracks": [{**t, "baseline": base.get(t["key"])} for t in tracks],
            "left_out": [{k: v for k, v in r.items() if k != "sort"} for r in left_out],
            "suggestions": (profile["build"] or {}).get("suggestions", [])}


class UseIn(BaseModel):
    kind: Literal["item", "bullet", "entry", "education", "skill"]
    id: str


@router.post("/use")
def use_line(body: UseIn, user: User = Depends(current_user)):
    """Put a left-out line back: the user's word that it is true. It reaches the resumes after
    the next re-render."""
    by_user = Jsonb({"ok": True, "reason": None, "restored_by_user": True})
    with user_tx(user.id) as conn:
        if body.kind == "item":
            conn.execute("update items set confirmed = true, provenance = %s where id = %s", (by_user, body.id))
            ids = [r["id"] for r in conn.execute("select id from bullets where item_id = %s", (body.id,)).fetchall()]
            conn.execute("update bullets set confirmed = true where id = any(%s)", (ids,))
            conn.execute("""update facts set confirmed_at = now() where id = any(
                              select unnest(fact_ids) from bullets where item_id = %s)""", (body.id,))
        elif body.kind in ("bullet", "entry"):
            table = "bullets" if body.kind == "bullet" else "entries"
            r = conn.execute("update {} set confirmed = true, provenance = %s where id = %s returning fact_ids".format(table),
                             (by_user, body.id)).fetchone()
            if r:
                conn.execute("update facts set confirmed_at = now() where id = any(%s)", (r["fact_ids"],))
        elif body.kind == "education":
            conn.execute("update education set confirmed = true, provenance = %s where id = %s", (by_user, body.id))
        else:
            conn.execute("update facts set confirmed_at = now(), provenance = %s where id = %s", (by_user, body.id))
    return {"ok": True}


class FamilyIn(BaseModel):
    family: str


@router.post("/families")
def add_family(body: FamilyIn, user: User = Depends(current_user)):
    """Add a resume for another kind of role. Written and rendered in the background."""
    with user_tx(user.id) as conn:
        families = conn.execute("select target_families from preferences").fetchone()["target_families"] or []
        if body.family not in onb.FAMILIES or body.family == "other":
            raise HTTPException(400, "Unknown kind of role")
        if body.family not in families and len(families) >= onb.MAX_FAMILIES:
            raise HTTPException(400, "Up to {} kinds of role: remove one first".format(onb.MAX_FAMILIES))
        conn.execute("""update profiles set build = build || jsonb_build_object('status', 'queued', 'step', 'writing',
                                                                                'error', null)""")
        enqueue(conn, user.id, "add_family", {"family": body.family})
    return {"ok": True}


@router.delete("/families/{family}")
def remove_family(family: str, user: User = Depends(current_user)):
    try:
        families = onb.remove_family(user.id, family)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"families": families}


@router.post("/rerender")
def rerender(user: User = Depends(current_user)):
    """Re-render every baseline after edits to the profile."""
    with user_tx(user.id) as conn:
        conn.execute("""update profiles set build = build || jsonb_build_object('status', 'queued', 'step', 'rendering',
                                                                                'error', null)""")
        enqueue(conn, user.id, "calibrate_tracks", {"track_keys": None})
    return {"ok": True}


@router.post("/finish")
def finish(user: User = Depends(current_user)):
    onb.finish(user.id)
    audit(user.id, "onboarding_finished", {})
    return {"ok": True}
