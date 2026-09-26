from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import onboarding as onb
from ..auth import User, current_user
from ..db import user_tx
from .me import ensure_user

router = APIRouter(prefix="/onboarding")
MAX_UPLOAD = 5 * 1024 * 1024


@router.post("/upload")
async def upload(files: list[UploadFile] = File(default=[]), about: str = Form(default=""),
                 links: str = Form(default=""), user: User = Depends(current_user)):
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
    if links.strip():
        docs.append(("links", "links", links.strip()))
    if not docs:
        raise HTTPException(400, "Nothing to read: upload a resume or write something about yourself")
    with user_tx(user.id) as conn:
        for kind, name, text in docs:
            conn.execute("insert into source_documents (user_id, kind, filename, text) values (%s, %s, %s, %s)",
                         (user.id, kind, name, text))
        conn.execute("update profiles set about = coalesce(nullif(%s, ''), about), onboarding_step = 'extract'",
                     (about.strip(),))
    return {"documents": len(docs)}


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


@router.post("/tracks")
def tracks(user: User = Depends(current_user)):
    return onb.propose_tracks(user.id)
