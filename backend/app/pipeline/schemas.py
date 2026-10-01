"""Structured-output schemas for every model step. Field names follow spec section 5."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field


def _no_defaults(schema: dict) -> None:
    for prop in (schema.get("properties") or {}).values():
        prop.pop("default", None)


class BaseModel(_PydanticBase):
    """Defaults exist for Python callers only. The JSON schema sent to the model carries
    none: OpenAI strict structured outputs reject the `default` keyword, and the model must
    fill every field itself either way."""
    model_config = ConfigDict(json_schema_extra=_no_defaults)

# ------------------------------------------------------------------ S1 extract

Discipline = Literal["sde", "backend", "fullstack", "frontend", "ai_ml", "cv", "data", "qa",
                     "mobile", "devops", "embedded", "design", "product", "business", "marketing",
                     "operations", "other"]


class Stipend(BaseModel):
    stated: Literal["figure", "unpaid", "unstated", "performance_based"]
    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[Literal["month", "year", "total"]] = None
    unpaid_period_months: Optional[float] = None


class ApplyRoute(BaseModel):
    type: Literal["email", "form", "ats", "linkedin_apply", "dm_only", "whatsapp", "comment"]
    value: Optional[str] = None


class Extracted(BaseModel):
    title: Optional[str] = None
    role_titles: list[str] = Field(default_factory=list)
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    poster_name: Optional[str] = None
    poster_role: Optional[str] = None
    poster_type: Literal["founder", "employee", "company_page", "recruiter", "aggregator", "unknown"]
    location_text: Optional[str] = None
    country: Optional[str] = None
    remote: Optional[bool] = None
    onsite_city: Optional[str] = None
    hybrid: Optional[bool] = None
    employment_type: Literal["internship", "full_time", "both", "unknown"] = "unknown"
    stipend: Stipend
    batch_years: list[int] = Field(default_factory=list)
    cgpa_min: Optional[float] = None
    duration_text: Optional[str] = None
    start_text: Optional[str] = None
    discipline: Discipline
    stack: list[str] = Field(default_factory=list)
    apply_routes: list[ApplyRoute] = Field(default_factory=list)
    posted_age_label: Optional[str] = None
    mill_signals: list[str] = Field(default_factory=list)
    asks_candidate_for_money: bool = False
    company_type_hint: Literal["startup", "sme", "big_tech", "large_enterprise", "it_services_major",
                               "staffing", "training", "unknown"] = "unknown"
    shared_by_third_party: bool = False


# ------------------------------------------------------------------ S4 company summary

class CompanySummary(BaseModel):
    business_type: Literal["product", "service", "agency", "staffing", "msp", "training",
                           "placement", "unknown"]
    summary: str
    matches_post: bool
    is_intermediary: bool
    size_hint: Optional[str] = None


# ------------------------------------------------------------------ S5 selection

class SectionSel(BaseModel):
    heading: str
    item_keys: list[str]


class Selection(BaseModel):
    role_title: str
    track_key: str
    left_sections: list[SectionSel]
    bullet_ids: list[str]
    drop_entry_ids: list[str] = Field(default_factory=list)
    fit_score: int
    fit_reasons: list[str]
    gaps: list[str] = Field(default_factory=list)
    lead_with: str


# ------------------------------------------------------------------ S7 draft

class EmailDraft(BaseModel):
    recipient_type: Literal["recruiter", "hiring_manager", "founder", "referral"]
    subject: str
    paragraphs: list[str]
    work_bullets: list[str] = Field(default_factory=list)
    facts_used: list[str]
    roles_mentioned: list[str]


# ------------------------------------------------------------------ onboarding

class ExLink(BaseModel):
    text: str
    url: str


class ExItem(BaseModel):
    key: str
    kind: Literal["project", "experience"]
    name: str
    tagline: Optional[str] = None
    period: Optional[str] = None
    stack: Optional[str] = None
    links: list[ExLink] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class ExEducation(BaseModel):
    institution: str
    degree: Optional[str] = None
    meta: Optional[str] = None
    result: Optional[str] = None
    lines: list[str] = Field(default_factory=list)


class ExEntry(BaseModel):
    section: Literal["awards", "roles"]
    lead: Optional[str] = None
    text: str


class ExProfile(BaseModel):
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    links: list[ExLink] = Field(default_factory=list)
    grad_date: Optional[str] = None
    batch_year: Optional[int] = None
    cgpa: Optional[float] = None


class Extraction(BaseModel):
    profile: ExProfile
    items: list[ExItem]
    education: list[ExEducation]
    entries: list[ExEntry]
    skills: list[str]
    other_facts: list[str] = Field(default_factory=list)


class NewItem(BaseModel):
    key: str
    kind: Literal["project", "experience"]
    name: str
    tagline: Optional[str] = None
    period: Optional[str] = None


class NewFact(BaseModel):
    kind: Literal["project", "role", "award", "skill", "metric", "other"]
    text: str
    item_key: Optional[str] = None


class InterviewTurn(BaseModel):
    new_items: list[NewItem] = Field(default_factory=list)
    new_facts: list[NewFact] = Field(default_factory=list)
    next_question: Optional[str] = None
    done: bool


class ProposedBullet(BaseModel):
    item_key: str
    text: str
    fact_ids: list[str]


class BulletProposals(BaseModel):
    bullets: list[ProposedBullet]


class SkillGroupP(BaseModel):
    label: str
    items: str


class ProposedTrack(BaseModel):
    key: str
    label: str
    title_line: str
    summary: str
    left_sections: list[SectionSel]
    skills: list[SkillGroupP]


class TrackProposals(BaseModel):
    tracks: list[ProposedTrack]
    rationale: str


class RoleOptionP(BaseModel):
    field: Discipline
    role: str
    fit: Literal["strong", "good", "stretch"]
    why: str
    evidence_item_keys: list[str]
    gaps: list[str]
    desired: bool


class RoleAudit(BaseModel):
    options: list[RoleOptionP]
    summary: str
