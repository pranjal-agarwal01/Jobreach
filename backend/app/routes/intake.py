"""
Intake for a person's own agent (docs/agent-intake.md). The agent sends the posts it found for
that person; each becomes their private lead and is read, scored and, when it suits them,
prepared, exactly like a post they pasted. It never enters the shared pool (the database
refuses a public 'agent' row).

The agent signs in with a personal intake key (Profile > Your agent), not the person's login:
random, shown once, stored only as a SHA-256, revocable, and limited per day.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ..auth import User, current_user
from ..db import audit, system_tx, user_tx
from ..pipeline.extract import parse_age_hours
from ..worker import enqueue
from .work import _hash as text_hash     # the same fingerprint as a pasted post: the two never double up

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

KEY_PREFIX = "jri_"
MAX_KEYS = 5
MAX_PER_CALL = 25
MAX_PER_DAY = 100          # posts a day per person: keeps a runaway agent from running up model costs


def new_key() -> tuple[str, str, str]:
    """(key, prefix shown in the app, SHA-256 stored)."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[:12], key_hash(key)


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def canonical_url(url: Optional[str]) -> Optional[str]:
    """A post's link without tracking parameters, so the same post found twice is one lead."""
    if not url:
        return None
    p = urlsplit(url.strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))


def posted_at_for(age_label: Optional[str], found_at: Optional[datetime],
                  now: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[float]]:
    """When the post went up: its age label, counted back from when the agent saw it."""
    age = parse_age_hours(age_label)
    if age is None:
        return None, None
    now = now or datetime.now(timezone.utc)
    seen = found_at or now
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    posted = seen - timedelta(hours=age)
    return posted, max(0.0, (now - posted).total_seconds() / 3600)


def intake_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> str:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials.startswith(KEY_PREFIX):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "send your intake key as: Authorization: Bearer jri_...")
    with system_tx() as conn:
        row = conn.execute("""update intake_keys set last_used_at = now()
                              where key_hash = %s and revoked_at is null returning user_id::text""",
                           (key_hash(creds.credentials),)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown or turned-off intake key")
    return row["user_id"]


# ------------------------------------------------------------------ the agent's endpoint

class AgentLead(BaseModel):
    text: str = Field(min_length=40, max_length=40000, description="The whole post, to the end")
    url: Optional[str] = Field(default=None, max_length=2000)
    age_label: Optional[str] = Field(default=None, max_length=40, description='As shown, e.g. "3h"')
    found_by: Optional[str] = Field(default=None, max_length=300, description="The search that found it")
    found_at: Optional[datetime] = None


class AgentBatch(BaseModel):
    leads: list[AgentLead] = Field(min_length=1, max_length=MAX_PER_CALL)


@router.post("/intake/leads")
def intake_leads(body: AgentBatch, user_id: str = Depends(intake_user)):
    """Posts the person's agent found. Each is queued like a pasted post; one that is already a
    lead (same text or same link) is reported as a duplicate."""
    results, queued = [], []
    with user_tx(user_id) as conn:
        today = conn.execute("""select count(*) as n from jobs where source = 'agent'
                                and first_seen_at > now() - interval '1 day'""").fetchone()["n"]
        if today + len(body.leads) > MAX_PER_DAY:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "daily limit of {} posts reached ({} today)".format(MAX_PER_DAY, today))
        for lead in body.leads:
            text, url = lead.text.strip(), canonical_url(lead.url)
            h = text_hash(text)
            dup = conn.execute("""select id::text from jobs where owner_user_id = %s
                                  and (content_hash = %s or (%s::text is not null and source_ref = %s))""",
                               (user_id, h, url, url)).fetchone()
            if dup:
                results.append({"job_id": dup["id"], "status": "duplicate"})
                continue
            posted, age = posted_at_for(lead.age_label, lead.found_at)
            row = conn.execute(
                """insert into jobs (visibility, owner_user_id, source, source_ref, found_by, raw_text, content_hash,
                       posted_at, posted_age_hours)
                   values ('private', %s, 'agent', %s, %s, %s, %s, %s, %s)
                   on conflict (owner_user_id, content_hash) do nothing returning id::text""",
                (user_id, url, "agent: " + (lead.found_by or "not given"), text, h, posted, age)).fetchone()
            if row is None:
                results.append({"job_id": None, "status": "duplicate"})
                continue
            results.append({"job_id": row["id"], "status": "queued"})
            queued.append(row["id"])
        # Queue last: enqueue leaves the person's role for the queue's own.
        for job_id in queued:
            enqueue(conn, user_id, "process_lead", {"job_id": job_id, "prepare": "suits"})
    audit(user_id, "agent_leads", {"queued": len(queued), "duplicates": len(results) - len(queued)})
    return {"received": len(body.leads), "queued": len(queued), "results": results}


# ------------------------------------------------------------------ keys, managed by the person

class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.get("/intake/keys")
def list_keys(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        return conn.execute("""select id, name, prefix, created_at, last_used_at from intake_keys
                               where revoked_at is null order by created_at desc""").fetchall()


@router.post("/intake/keys")
def create_key(body: KeyIn, user: User = Depends(current_user)):
    """A new key, returned once. Only its fingerprint is kept."""
    key, prefix, digest = new_key()
    with user_tx(user.id) as conn:
        n = conn.execute("select count(*) as n from intake_keys where revoked_at is null").fetchone()["n"]
        if n >= MAX_KEYS:
            raise HTTPException(400, "Turn off a key before making another (at most {})".format(MAX_KEYS))
        row = conn.execute("""insert into intake_keys (user_id, name, prefix, key_hash) values (%s, %s, %s, %s)
                              returning id, name, prefix, created_at""",
                           (user.id, body.name.strip(), prefix, digest)).fetchone()
    audit(user.id, "intake_key_created", {"key": str(row["id"])})
    return {**row, "key": key}


@router.delete("/intake/keys/{key_id}")
def revoke_key(key_id: str, user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        conn.execute("update intake_keys set revoked_at = now() where id = %s and revoked_at is null", (key_id,))
    audit(user.id, "intake_key_revoked", {"key": key_id})
    return {"ok": True}
