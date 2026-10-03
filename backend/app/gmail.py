"""
Letters drafted in the person's own Gmail. They connect Gmail once, on Google's own consent
screen; from then on every prepared letter is created as a draft in their mailbox, To and Subject
filled and the page-checked resume PDF attached. They open Gmail and press Send.

Jobreach never sends. Gmail has no drafts-only permission: the smallest one that allows drafts
(gmail.compose) also allows sending, so the rule is held here, in code: the only Gmail call this
module can make is drafts.create (ALLOWED), and any other is refused before it leaves.

The refresh token is encrypted with a key only the backend holds (TOKEN_ENCRYPTION_KEY) and
stored where no signed-in user can read it. Disconnecting revokes it at Google and deletes it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from email.message import EmailMessage
from typing import Optional
from urllib.parse import quote, urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .config import settings
from .db import system_tx, user_tx
from .pipeline.draft import html_to_plain

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DRAFTS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
SCOPES = ["openid", "email", "https://www.googleapis.com/auth/gmail.compose"]
ALLOWED = {("POST", DRAFTS_URL)}         # the only Gmail call Jobreach makes: create a draft
STATE_TTL = 15 * 60
TIMEOUT = 20.0


class GmailError(RuntimeError):
    pass


class NotConnected(GmailError):
    pass


class Expired(GmailError):
    """Google no longer accepts the stored access (revoked, or a test app's 7-day limit)."""


class NotGranted(GmailError):
    """The person allowed sign-in but left the drafts box unticked on Google's page."""


def configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.token_encryption_key)


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise GmailError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(settings.token_encryption_key.encode())


def encrypt(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt(blob: str) -> str:
    try:
        return _fernet().decrypt(blob.encode()).decode()
    except InvalidToken as e:
        raise GmailError("stored Gmail access cannot be read with the current key") from e


# ------------------------------------------------------------------ connecting

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _state_key() -> bytes:
    return hashlib.sha256(b"gmail-state:" + settings.token_encryption_key.encode()).digest()


def safe_return(path: Optional[str]) -> str:
    """Only a path inside the app: never another site (no open redirect)."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/today"
    return path[:200]


def sign_state(user_id: str, return_to: Optional[str], now: Optional[float] = None) -> str:
    body = _b64(json.dumps({"u": user_id, "r": safe_return(return_to), "n": secrets.token_urlsafe(8),
                            "e": int((now or time.time()) + STATE_TTL)}).encode())
    return body + "." + _b64(hmac.new(_state_key(), body.encode(), hashlib.sha256).digest())


def read_state(state: str, now: Optional[float] = None) -> tuple[str, str]:
    """(user_id, return path) from a state Jobreach signed, or GmailError."""
    try:
        body, sig = state.split(".", 1)
        good = hmac.compare_digest(_unb64(sig), hmac.new(_state_key(), body.encode(), hashlib.sha256).digest())
        data = json.loads(_unb64(body))
    except (ValueError, TypeError) as e:
        raise GmailError("the Gmail connection request was not recognised") from e
    if not good:
        raise GmailError("the Gmail connection request was not recognised")
    if data["e"] < (now or time.time()):
        raise GmailError("the Gmail connection request expired; start again")
    return data["u"], safe_return(data.get("r"))


def auth_url(user_id: str, return_to: Optional[str] = None, email_hint: Optional[str] = None) -> str:
    """Google's consent screen. offline + consent: Google returns a refresh token every time."""
    params = {"client_id": settings.google_client_id, "redirect_uri": settings.gmail_redirect_uri,
              "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
              "prompt": "consent", "include_granted_scopes": "true", "state": sign_state(user_id, return_to)}
    if email_hint:
        params["login_hint"] = email_hint
    return AUTH_URL + "?" + urlencode(params)


def _post_form(url: str, data: dict, client: Optional[httpx.Client] = None) -> httpx.Response:
    c = client or httpx.Client(timeout=TIMEOUT)
    try:
        return c.post(url, data=data)
    finally:
        if client is None:
            c.close()


def email_from_id_token(id_token: str) -> Optional[str]:
    """The Google account's address, from the ID token Google's token endpoint returned over TLS
    (direct from Google, so its claims are read without a second check)."""
    try:
        claims = json.loads(_unb64(id_token.split(".")[1]))
    except (ValueError, IndexError):
        return None
    return claims.get("email") if claims.get("email_verified", True) else None


def finish_connect(code: str, state: str, client: Optional[httpx.Client] = None) -> tuple[str, str, str]:
    """Exchange Google's code and store the encrypted refresh token. Returns (user_id, email, return path)."""
    user_id, return_to = read_state(state)
    r = _post_form(TOKEN_URL, {"code": code, "client_id": settings.google_client_id,
                               "client_secret": settings.google_client_secret,
                               "redirect_uri": settings.gmail_redirect_uri, "grant_type": "authorization_code"}, client)
    if r.status_code != 200:
        raise GmailError("Google did not accept the connection ({})".format(r.json().get("error", r.status_code)))
    tok = r.json()
    granted = set((tok.get("scope") or "").split())
    if SCOPES[2] not in granted:
        raise NotGranted("Permission to create drafts was not given")
    if not tok.get("refresh_token"):
        raise GmailError("Google did not return lasting access; disconnect Jobreach in your Google account and try again")
    email = email_from_id_token(tok.get("id_token", "")) or "your Gmail"
    with system_tx() as conn:
        conn.execute(
            """insert into gmail_connections (user_id, email, refresh_token_enc, scope)
               values (%s, %s, %s, %s)
               on conflict (user_id) do update set email = excluded.email, refresh_token_enc = excluded.refresh_token_enc,
                   scope = excluded.scope, connected_at = now(), status = 'active', last_error = null""",
            (user_id, email, encrypt(tok["refresh_token"]), " ".join(sorted(granted))))
    return user_id, email, return_to


def connection(user_id: str) -> Optional[dict]:
    with system_tx() as conn:
        return conn.execute("""select email, status, connected_at, last_used_at, last_error
                               from gmail_connections where user_id = %s""", (user_id,)).fetchone()


def disconnect(user_id: str, client: Optional[httpx.Client] = None) -> bool:
    """Revoke the access at Google (best effort) and forget it."""
    with system_tx() as conn:
        row = conn.execute("delete from gmail_connections where user_id = %s returning refresh_token_enc",
                           (user_id,)).fetchone()
    if row is None:
        return False
    try:
        _post_form(REVOKE_URL, {"token": decrypt(row["refresh_token_enc"])}, client)
    except (httpx.HTTPError, GmailError):
        pass
    return True


def access_token(user_id: str, client: Optional[httpx.Client] = None) -> tuple[str, str]:
    """A fresh access token and the connected address. Expired when Google refuses."""
    with system_tx() as conn:
        row = conn.execute("""select email, refresh_token_enc, status from gmail_connections
                              where user_id = %s""", (user_id,)).fetchone()
    if row is None:
        raise NotConnected("Gmail is not connected")
    if row["status"] != "active":
        raise Expired("Gmail access ended; reconnect Gmail")
    r = _post_form(TOKEN_URL, {"client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
                               "refresh_token": decrypt(row["refresh_token_enc"]), "grant_type": "refresh_token"}, client)
    if r.status_code in (400, 401) and r.json().get("error") in ("invalid_grant", "unauthorized_client"):
        with system_tx() as conn:
            conn.execute("""update gmail_connections set status = 'expired', last_error = %s where user_id = %s""",
                         ("Google no longer accepts this connection; reconnect Gmail", user_id))
        raise Expired("Gmail access ended; reconnect Gmail")
    r.raise_for_status()
    return r.json()["access_token"], row["email"]


# ------------------------------------------------------------------ drafting

def mime(to: str, subject: str, html: str, pdf: Optional[bytes], pdf_name: Optional[str]) -> bytes:
    """The letter as Gmail stores it: plain and HTML versions, and the resume attached. No From
    (Gmail uses the connected account) and nothing that would send it."""
    m = EmailMessage()
    m["To"] = to
    m["Subject"] = subject
    m.set_content(html_to_plain(html))
    m.add_alternative(html, subtype="html")
    if pdf:
        m.add_attachment(pdf, maintype="application", subtype="pdf", filename=pdf_name or "resume.pdf")
    return m.as_bytes()


def _gmail(method: str, url: str, token: str, body: dict, client: Optional[httpx.Client] = None) -> dict:
    if (method, url) not in ALLOWED:
        raise GmailError("Jobreach only creates drafts; {} {} is not allowed".format(method, url))
    c = client or httpx.Client(timeout=TIMEOUT)
    try:
        r = c.request(method, url, json=body, headers={"Authorization": "Bearer " + token})
    finally:
        if client is None:
            c.close()
    if r.status_code in (401, 403):
        raise GmailError("Gmail refused the draft ({})".format(r.status_code))
    r.raise_for_status()
    return r.json()


def draft_link(email: str, message_id: Optional[str]) -> Optional[str]:
    if not message_id:
        return None
    return "https://mail.google.com/mail/u/{}/#drafts?compose={}".format(quote(email), message_id)


def create_draft(user_id: str, draft_id: str, client: Optional[httpx.Client] = None) -> dict:
    """Put one Jobreach letter in the person's Gmail drafts, with its resume attached. Idempotent:
    a letter already in Gmail is not drafted twice."""
    with user_tx(user_id) as conn:
        d = conn.execute("""select id, application_id, to_addrs, subject, html, gmail_draft_id, gmail_message_id
                            from drafts where id = %s""", (draft_id,)).fetchone()
        if d is None:
            raise GmailError("letter not found")
        if d["gmail_draft_id"]:
            return {"draft_id": d["gmail_draft_id"], "message_id": d["gmail_message_id"], "existing": True}
        f = conn.execute("""select f.pdf, coalesce(f.pdf_filename, 'resume.pdf') as name from resumes r
                            join resume_files f on f.id = r.file_id where r.application_id = %s
                            order by r.created_at desc limit 1""", (d["application_id"],)).fetchone()
    if not d["to_addrs"]:
        raise GmailError("this letter has no address to write to")
    try:
        token, email = access_token(user_id, client)
        made = _gmail("POST", DRAFTS_URL, token,
                      {"message": {"raw": _b64(mime(d["to_addrs"][0], d["subject"], d["html"],
                                                    bytes(f["pdf"]) if f and f["pdf"] else None,
                                                    f["name"] if f else None))}}, client)
    except GmailError as e:
        with user_tx(user_id) as conn:
            conn.execute("update drafts set gmail_error = %s where id = %s", (str(e)[:300], draft_id))
        raise
    with user_tx(user_id) as conn:
        conn.execute("""update drafts set gmail_draft_id = %s, gmail_message_id = %s, gmail_drafted_at = now(),
                            gmail_error = null where id = %s""", (made["id"], made["message"]["id"], draft_id))
    with system_tx() as conn:
        conn.execute("update gmail_connections set last_used_at = now() where user_id = %s", (user_id,))
    return {"draft_id": made["id"], "message_id": made["message"]["id"], "link": draft_link(email, made["message"]["id"])}


# ------------------------------------------------------------------ queueing

def queue_draft(conn, user_id: str, draft_id: str) -> None:
    """Inside the caller's transaction (enqueue leaves the person's role: call it last)."""
    from .worker import enqueue
    enqueue(conn, user_id, "gmail_draft", {"draft_id": str(draft_id)})


def queue_ready(user_id: str) -> int:
    """After connecting: every letter ready to send and not yet in Gmail goes there. Letters that
    need a look stay in Jobreach until the person drafts them by hand."""
    if connection(user_id) is None:
        return 0
    with user_tx(user_id) as conn:
        ids = [r["id"] for r in conn.execute(
            """select distinct on (d.application_id) d.id::text as id, d.gmail_draft_id
               from drafts d join applications a on a.id = d.application_id
               where a.status = 'drafted' and d.lint_ok
               order by d.application_id, d.version desc""").fetchall() if not r["gmail_draft_id"]]
        for i in ids:
            queue_draft(conn, user_id, i)
    return len(ids)
