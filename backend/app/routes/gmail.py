"""Connecting Gmail, and drafting a letter there by hand (app/gmail.py does the work)."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .. import gmail
from ..auth import User, current_user
from ..config import settings
from ..db import audit, user_tx

router = APIRouter()


@router.get("/gmail")
def status(user: User = Depends(current_user)):
    c = gmail.connection(user.id) if gmail.configured() else None
    return {"available": gmail.configured(), "connected": bool(c and c["status"] == "active"),
            "expired": bool(c and c["status"] == "expired"), "email": c["email"] if c else None,
            "connected_at": c["connected_at"] if c else None, "unverified": not settings.google_app_verified}


class ConnectIn(BaseModel):
    return_to: Optional[str] = None


@router.post("/gmail/connect")
def connect(body: Optional[ConnectIn] = None, user: User = Depends(current_user)):
    """The address of Google's consent screen; the browser goes there next."""
    if not gmail.configured():
        raise HTTPException(503, "Gmail drafts are not set up on this server yet")
    return {"url": gmail.auth_url(user.id, body.return_to if body else None, user.email)}


@router.get("/gmail/callback", include_in_schema=False)
def callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Google sends the browser back here. Who it is comes from the state Jobreach signed."""
    def back(path: str, result: str) -> RedirectResponse:
        sep = "&" if "?" in path else "?"
        return RedirectResponse(settings.frontend_url + path + sep + urlencode({"gmail": result}), status_code=303)

    try:
        _, path = gmail.read_state(state or "")
    except gmail.GmailError:
        path = "/today"
    if error or not code or not state:
        return back(path, "denied" if error == "access_denied" else "error")
    try:
        user_id, email, path = gmail.finish_connect(code, state)
    except gmail.NotGranted:
        return back(path, "unticked")
    except gmail.GmailError:
        return back(path, "error")
    queued = gmail.queue_ready(user_id)
    audit(user_id, "gmail_connected", {"drafts_queued": queued})
    return back(path, "connected")


@router.delete("/gmail")
def disconnect(user: User = Depends(current_user)):
    gmail.disconnect(user.id)
    audit(user.id, "gmail_disconnected", {})
    return {"ok": True}


@router.post("/applications/{app_id}/gmail-draft")
def draft_now(app_id: str, user: User = Depends(current_user)):
    """Draft this letter in Gmail now (also for a letter that needs a look first)."""
    if gmail.connection(user.id) is None:
        raise HTTPException(400, "Connect Gmail first")
    with user_tx(user.id) as conn:
        d = conn.execute("""select id::text, gmail_draft_id from drafts where application_id = %s
                            order by version desc limit 1""", (app_id,)).fetchone()
        if d is None:
            raise HTTPException(404, "This job has no letter")
        if d["gmail_draft_id"]:
            return {"queued": False, "existing": True}
        conn.execute("update drafts set gmail_error = null where id = %s", (d["id"],))
        gmail.queue_draft(conn, user.id, d["id"])
    return {"queued": True}
