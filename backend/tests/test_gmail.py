"""Gmail drafts: connecting, the stored access, the message, and the rule that Jobreach only ever
creates drafts. Google is replaced by a fake transport; no database."""
import email
import json
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet

from app import gmail


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setattr(gmail, "settings", SimpleNamespace(
        google_client_id="cid.apps.googleusercontent.com", google_client_secret="secret",
        token_encryption_key=Fernet.generate_key().decode(), gmail_redirect_uri="http://localhost:8000/gmail/callback"))


class FakeDB:
    """Answers the few queries gmail.py makes, and records every statement."""
    def __init__(self, rows=None):
        self.rows, self.calls = rows or {}, []

    @contextmanager
    def tx(self, *a):
        yield self

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        key = next((k for k in self.rows if k in sql), None)
        return SimpleNamespace(fetchone=lambda: self.rows.get(key), fetchall=lambda: self.rows.get(key) or [])


def google(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def id_token(email_addr):
    body = gmail._b64(json.dumps({"email": email_addr, "email_verified": True}).encode())
    return "header." + body + ".sig"


def test_stored_access_is_encrypted_and_readable_only_with_the_key():
    blob = gmail.encrypt("1//refresh-token")
    assert "refresh" not in blob and gmail.decrypt(blob) == "1//refresh-token"


def test_the_connection_request_cannot_be_forged_reused_late_or_sent_elsewhere():
    s = gmail.sign_state("user-1", "/today", now=1000)
    assert gmail.read_state(s, now=1001) == ("user-1", "/today")
    body, sig = s.split(".")
    other = gmail.sign_state("user-2", "/today", now=1000).split(".")[0]
    with pytest.raises(gmail.GmailError):
        gmail.read_state(other + "." + sig, now=1001)                     # someone else's request, our signature
    with pytest.raises(gmail.GmailError):
        gmail.read_state(s, now=1000 + gmail.STATE_TTL + 1)               # too late
    with pytest.raises(gmail.GmailError):
        gmail.read_state("garbage", now=1001)
    for evil in ("https://evil.example", "//evil.example", "/\\evil.example", None):
        assert gmail.safe_return(evil) == "/today"
    assert gmail.safe_return("/jobs/abc") == "/jobs/abc"


def test_consent_screen_asks_for_lasting_access_to_drafts_only_what_is_needed():
    url = gmail.auth_url("user-1", "/today", "a@gmail.com")
    q = dict(httpx.URL(url).params)
    assert url.startswith(gmail.AUTH_URL)
    assert q["access_type"] == "offline" and q["prompt"] == "consent" and q["login_hint"] == "a@gmail.com"
    assert q["scope"].split() == ["openid", "email", "https://www.googleapis.com/auth/gmail.compose"]
    assert q["redirect_uri"] == "http://localhost:8000/gmail/callback"
    assert gmail.read_state(q["state"])[0] == "user-1"


def test_connecting_stores_the_encrypted_token_and_the_address(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(gmail, "system_tx", db.tx)
    client = google(lambda req: httpx.Response(200, json={
        "access_token": "ya29", "refresh_token": "1//r", "id_token": id_token("rohan@gmail.com"),
        "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/gmail.compose"}))
    user, addr, back = gmail.finish_connect("code", gmail.sign_state("user-1", "/leads"), client)
    assert (user, addr, back) == ("user-1", "rohan@gmail.com", "/leads")
    sql, params = db.calls[-1]
    assert sql.startswith("insert into gmail_connections") and "1//r" not in params
    assert gmail.decrypt(params[2]) == "1//r"


@pytest.mark.parametrize("tokens,why", [
    ({"access_token": "a", "refresh_token": "r", "scope": "openid email"}, "drafts was not given"),
    ({"access_token": "a", "scope": "https://www.googleapis.com/auth/gmail.compose"}, "lasting access"),
])
def test_connecting_without_draft_permission_or_lasting_access_fails(monkeypatch, tokens, why):
    monkeypatch.setattr(gmail, "system_tx", FakeDB().tx)
    with pytest.raises(gmail.GmailError, match=why):
        gmail.finish_connect("code", gmail.sign_state("u", "/"), google(lambda req: httpx.Response(200, json=tokens)))


def test_access_google_no_longer_accepts_is_marked_expired(monkeypatch):
    db = FakeDB({"from gmail_connections": {"email": "a@gmail.com", "refresh_token_enc": gmail.encrypt("r"),
                                             "status": "active"}})
    monkeypatch.setattr(gmail, "system_tx", db.tx)
    with pytest.raises(gmail.Expired):
        gmail.access_token("u", google(lambda req: httpx.Response(400, json={"error": "invalid_grant"})))
    assert any("set status = 'expired'" in sql for sql, _ in db.calls)


def test_the_message_is_the_letter_with_the_resume_attached_and_nothing_else():
    raw = gmail.mime("priya@acme.example", "Backend Intern: Rohan Das, résumé attached",
                     "<p>Hi Priya,</p><p>My resume is attached.</p>", b"%PDF-1.7 fake", "resume_Rohan_Das.pdf")
    m = email.message_from_bytes(raw, policy=email.policy.default)
    assert m["To"] == "priya@acme.example" and m["Subject"] == "Backend Intern: Rohan Das, résumé attached"
    assert m["From"] is None and m["Bcc"] is None
    kinds = [p.get_content_type() for p in m.walk()]
    assert "text/plain" in kinds and "text/html" in kinds and "application/pdf" in kinds
    pdf = next(p for p in m.walk() if p.get_content_type() == "application/pdf")
    assert pdf.get_filename() == "resume_Rohan_Das.pdf" and pdf.get_content() == b"%PDF-1.7 fake"
    assert "Hi Priya," in m.get_body(("plain",)).get_content()


@pytest.mark.parametrize("method,url", [
    ("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"),
    ("POST", "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send"),
    ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/messages"),
])
def test_jobreach_can_only_create_drafts_never_send_or_read(method, url):
    sent = []
    with pytest.raises(gmail.GmailError, match="only creates drafts"):
        gmail._gmail(method, url, "tok", {}, google(lambda req: sent.append(req) or httpx.Response(200, json={})))
    assert sent == []                                                    # nothing left the building


def test_a_letter_lands_in_gmail_once_with_its_resume(monkeypatch):
    user_db = FakeDB({"from drafts": {"id": "d1", "application_id": "a1", "to_addrs": ["priya@acme.example"],
                                      "subject": "Backend Intern", "html": "<p>Hi Priya,</p>", "gmail_draft_id": None,
                                      "gmail_message_id": None},
                      "from resumes": {"pdf": b"%PDF", "name": "resume.pdf"}})
    sys_db = FakeDB({"from gmail_connections": {"email": "rohan@gmail.com", "refresh_token_enc": gmail.encrypt("r"),
                                                "status": "active"}})
    monkeypatch.setattr(gmail, "user_tx", user_db.tx)
    monkeypatch.setattr(gmail, "system_tx", sys_db.tx)
    seen = []

    def handler(req):
        seen.append((req.method, str(req.url)))
        if str(req.url) == gmail.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "ya29"})
        body = json.loads(req.content)
        msg = email.message_from_bytes(gmail._unb64(body["message"]["raw"]), policy=email.policy.default)
        assert msg["To"] == "priya@acme.example" and req.headers["Authorization"] == "Bearer ya29"
        return httpx.Response(200, json={"id": "r-123", "message": {"id": "18f0abc"}})

    out = gmail.create_draft("u", "d1", google(handler))
    assert seen == [("POST", gmail.TOKEN_URL), ("POST", gmail.DRAFTS_URL)]
    assert out["link"] == "https://mail.google.com/mail/u/rohan%40gmail.com/#drafts?compose=18f0abc"
    assert any("set gmail_draft_id" in sql and params[0] == "r-123" for sql, params in user_db.calls)

    user_db.rows["from drafts"] = {**user_db.rows["from drafts"], "gmail_draft_id": "r-123", "gmail_message_id": "18f0abc"}
    seen.clear()
    assert gmail.create_draft("u", "d1", google(handler))["existing"] is True and seen == []   # never twice
