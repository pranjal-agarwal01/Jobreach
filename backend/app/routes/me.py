from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..auth import User, current_user
from ..config import settings
from ..db import audit, system_tx, user_tx

router = APIRouter()


def ensure_user(user: User) -> None:
    """Create the profile and preferences rows on first sight of a new user."""
    with user_tx(user.id) as conn:
        conn.execute("insert into profiles (user_id, email) values (%s, %s) on conflict do nothing",
                     (user.id, user.email))
        conn.execute("insert into preferences (user_id) values (%s) on conflict do nothing", (user.id,))


@router.get("/me")
def me(user: User = Depends(current_user)):
    ensure_user(user)
    with user_tx(user.id) as conn:
        profile = conn.execute("select * from profiles").fetchone()
        prefs = conn.execute("select * from preferences").fetchone()
        counts = conn.execute(
            """select (select count(*) from items where confirmed) as items,
                      (select count(*) from bullets where confirmed) as bullets,
                      (select count(*) from tracks where approved) as tracks,
                      (select count(*) from applications) as applications""").fetchone()
    return {"user": {"id": user.id, "email": user.email}, "profile": profile, "preferences": prefs,
            "counts": counts, "consent_version": settings.consent_version,
            "needs_consent": profile["consent_version"] != settings.consent_version}


class Consent(BaseModel):
    version: str


@router.post("/consent")
def consent(body: Consent, user: User = Depends(current_user)):
    ensure_user(user)
    with user_tx(user.id) as conn:
        conn.execute("update profiles set consent_version = %s, consented_at = now()", (body.version,))
    audit(user.id, "consent", {"version": body.version})
    return {"ok": True}


class ProfileIn(BaseModel):
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    links: Optional[list[dict]] = None
    about: Optional[str] = None
    grad_date: Optional[str] = None
    batch_year: Optional[int] = None
    cgpa: Optional[float] = None
    onboarding_step: Optional[str] = None


@router.put("/profile")
def put_profile(body: ProfileIn, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"ok": True}
    sets = ", ".join("{} = %s".format(k) for k in fields)
    vals = [Jsonb(v) if k == "links" else v for k, v in fields.items()]
    with user_tx(user.id) as conn:
        conn.execute("update profiles set {}, updated_at = now()".format(sets), vals)
    return {"ok": True}


class PrefsIn(BaseModel):
    role_types: Optional[list[str]] = None
    open_to: Optional[list[str]] = None
    locations: Optional[list[str]] = None
    remote_ok: Optional[bool] = None
    onsite_ok: Optional[bool] = None
    hybrid_ok: Optional[bool] = None
    stipend_floor: Optional[int] = None
    currency: Optional[str] = None
    unpaid_remote_policy: Optional[str] = None
    unpaid_onsite_policy: Optional[str] = None
    excluded_company_types: Optional[list[str]] = None
    excluded_companies: Optional[list[str]] = None
    freshness_ceiling_hours: Optional[int] = None
    duration_flex: Optional[str] = None
    start_date: Optional[str] = None
    signature_html: Optional[str] = None
    format_settings: Optional[dict] = None


@router.put("/preferences")
def put_prefs(body: PrefsIn, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"ok": True}
    sets = ", ".join("{} = %s".format(k) for k in fields)
    vals = [Jsonb(v) if k == "format_settings" else v for k, v in fields.items()]
    with user_tx(user.id) as conn:
        conn.execute("update preferences set {}, updated_at = now()".format(sets), vals)
    return {"ok": True}


@router.get("/usage")
def usage(user: User = Depends(current_user)):
    """Measured token use and cost per pipeline step (spec 10.2: measure, do not assume)."""
    with user_tx(user.id) as conn:
        steps = conn.execute(
            """select step, count(*) as calls, sum(input_tokens) as input_tokens,
                      sum(output_tokens) as output_tokens, sum(cache_read_tokens) as cache_read_tokens,
                      sum(cache_write_tokens) as cache_write_tokens, round(sum(cost_usd), 4) as cost_usd,
                      round(avg(latency_ms)) as avg_latency_ms
               from llm_calls group by step order by step""").fetchall()
        per_draft = conn.execute(
            """select round(avg(c), 4) as avg_cost_per_application, count(*) as applications from (
                 select application_id, sum(cost_usd) as c from llm_calls
                 where application_id is not null group by application_id) t""").fetchone()
        per_lead = conn.execute(
            """select round(avg(c), 4) as avg_cost_per_lead, count(*) as leads from (
                 select job_id, sum(cost_usd) as c from llm_calls where job_id is not null group by job_id) t""").fetchone()
        total = conn.execute("select round(coalesce(sum(cost_usd), 0), 4) as cost_usd from llm_calls").fetchone()
    return {"steps": steps, "per_application": per_draft, "per_lead": per_lead, "total": total}


@router.delete("/account")
def delete_account(user: User = Depends(current_user)):
    """Real deletion (DPDP): removing the auth user cascades to every row the user owns,
    including stored resume files. Shared company rows hold no personal data."""
    with system_tx() as conn:
        conn.execute("delete from auth.users where id = %s", (user.id,))
    audit(None, "account_deleted", {"user": user.id})
    return {"ok": True}
