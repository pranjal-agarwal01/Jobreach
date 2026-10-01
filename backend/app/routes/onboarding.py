from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .. import onboarding as onb
from ..auth import User, current_user
from ..db import user_tx
from .me import ensure_user

router = APIRouter(prefix="/onboarding")
MAX_UPLOAD = 5 * 1024 * 1024


def _split(s: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in s.replace("\n", ",").split(",") if x.strip()))


@router.post("/upload")
async def upload(files: list[UploadFile] = File(default=[]), about: str = Form(default=""),
                 links: str = Form(default=""), projects: str = Form(default=""),
                 github: str = Form(default=""), fields: str = Form(default=""),
                 roles: str = Form(default=""), user: User = Depends(current_user)):
    """The one-time sign-up form: every CV, a description, projects, GitHub, other links, and
    the fields and roles the student wants. Everything is read by the audit (extraction); the
    student confirms what it finds."""
    ensure_user(user)
    docs = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "{} is larger than 5 MB".format(f.filename))
        try:
            text = onb.text_from_upload(f.filename or "", data)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        if text.strip():
            docs.append(("resume", f.filename, text))
    if about.strip():
        docs.append(("about", "about me", about.strip()))
    if projects.strip():
        docs.append(("other", "projects", projects.strip()))
    if links.strip():
        docs.append(("links", "links", links.strip()))

    gh = {"username": None, "read": False}
    if github.strip():
        name = onb.github_username(github)
        if name is None:
            raise HTTPException(400, "That GitHub link doesn't look like github.com/<username>")
        gh["username"] = name
        summary = await run_in_threadpool(onb.github_summary, name)
        gh["read"] = summary is not None
        docs.append(("links", "github", summary or "GitHub profile https://github.com/" + name))
    if not docs:
        raise HTTPException(400, "Nothing to read: upload a resume or write something about yourself")

    wanted_fields = [f for f in _split(fields) if f in onb.FIELDS]
    wanted_roles = [r[:80] for r in _split(roles)][:12]
    with user_tx(user.id) as conn:
        for kind, name, text in docs:
            conn.execute("insert into source_documents (user_id, kind, filename, text) values (%s, %s, %s, %s)",
                         (user.id, kind, name, text))
        conn.execute("""update profiles set about = coalesce(nullif(%s, ''), about),
                            github_url = coalesce(%s, github_url), onboarding_step = 'extract'""",
                     (about.strip(), "https://github.com/" + gh["username"] if gh["username"] else None))
        if wanted_fields or wanted_roles:
            conn.execute("update preferences set role_types = %s, desired_roles = %s, updated_at = now()",
                         (wanted_fields, wanted_roles))
    return {"documents": len(docs), "github": gh}


@router.post("/extract")
def extract(user: User = Depends(current_user)):
    try:
        return onb.run_extraction(user.id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class Answer(BaseModel):
    answer: Optional[str] = None


@router.post("/interview")
def interview(body: Answer, user: User = Depends(current_user)):
    return onb.interview(user.id, body.answer)


@router.get("/interview")
def interview_history(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        return conn.execute("select role, content, created_at from onboarding_messages order by created_at").fetchall()


@router.post("/bullets")
def bullets(user: User = Depends(current_user)):
    return onb.propose_bullets(user.id)


@router.get("/evidence")
def evidence(user: User = Depends(current_user)):
    return onb.evidence_check(user.id)


@router.get("/roles")
def roles(user: User = Depends(current_user)):
    return onb.list_roles(user.id)


@router.post("/roles")
def audit_roles(user: User = Depends(current_user)):
    try:
        return onb.audit_roles(user.id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class RoleChoice(BaseModel):
    mode: Literal["specific", "mix"]
    option_ids: list[str] = []


@router.post("/roles/select")
def select_roles(body: RoleChoice, user: User = Depends(current_user)):
    try:
        return onb.select_roles(user.id, body.mode, body.option_ids)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/tracks")
def tracks(user: User = Depends(current_user)):
    return onb.propose_tracks(user.id)
