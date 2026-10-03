"""Connecting Gmail, and drafting a letter there by hand (app/gmail.py does the work)."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .. import gmail, send
from ..auth import User, current_user
from ..config import settings
from ..db import audit, user_tx

router = APIRouter()


@router.get("/gmail")
def status(user: User = Depends(current_user)):
    c = gmail.connection(user.id) if gmail.configured() else None
    return {"available": gmail.configured(), "connected": bool(c and c["status"] == "active"),
            "expired": bool(c and c["status"] == "expired"), "email": c["email"] if c else None,
            "connected_at": c["connected_at"] if c else None, "unverified": not settings.google_app_verified,
            "send": send.status(user.id) if gmail.configured() else None}


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
    send.unschedule_all(user.id)
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


HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class SendSettings(BaseModel):
    enabled: bool
    window_start: str = "14:00"
    window_end: str = "17:00"
    timezone: str = "Asia/Kolkata"
    daily_cap: int = Field(10, ge=1, le=20)
    grace_minutes: int = Field(120, ge=30, le=1440)


@router.put("/gmail/send-for-me")
def send_for_me(body: SendSettings, user: User = Depends(current_user)):
    """Turn Send for me on or off, or change its window. Turning it on is the person's consent for
    Jobreach to send their letters from their Gmail; it is recorded (audit and enabled_at)."""
    if not (HHMM.match(body.window_start) and HHMM.match(body.window_end)) or body.window_start == body.window_end:
        raise HTTPException(422, "Choose a window with a start and an end, like 14:00 to 17:00")
    if send.zone(body.timezone).key != body.timezone:
        raise HTTPException(422, "Unknown time zone")
    c = gmail.connection(user.id) if gmail.configured() else None
    if body.enabled and not (c and c["status"] == "active"):
        raise HTTPException(400, "Connect Gmail first")
    with user_tx(user.id) as conn:
        was = conn.execute("select auto_send from preferences").fetchone()
        conn.execute(
            """update preferences set auto_send = %s, auto_send_window_start = %s, auto_send_window_end = %s,
                   auto_send_timezone = %s, auto_send_daily_cap = %s, auto_send_grace_minutes = %s,
                   auto_send_paused_reason = null,
                   auto_send_enabled_at = case when %s and not auto_send then now() else auto_send_enabled_at end,
                   updated_at = now()""",
            (body.enabled, body.window_start, body.window_end, body.timezone, body.daily_cap, body.grace_minutes,
             body.enabled))
    send.unschedule_all(user.id)                       # the old moments may not fit the new window
    lined_up = send.schedule_ready(user.id) if body.enabled else 0
    action = ("send_for_me_on" if body.enabled and not (was and was["auto_send"]) else
              "send_for_me_off" if not body.enabled else "send_for_me_changed")
    audit(user.id, action, {"window": [body.window_start, body.window_end], "tz": body.timezone,
                            "cap": body.daily_cap, "grace": body.grace_minutes, "lined_up": lined_up})
    return send.status(user.id)


@router.post("/applications/{app_id}/send-cancel")
def cancel_send(app_id: str, user: User = Depends(current_user)):
    """"Don't send this one": the letter stays in Gmail drafts for the person to send, or not."""
    if not send.cancel(user.id, app_id):
        raise HTTPException(409, "This letter isn't lined up to be sent")
    audit(user.id, "send_for_me_cancelled", {"application_id": app_id})
    return {"ok": True}
