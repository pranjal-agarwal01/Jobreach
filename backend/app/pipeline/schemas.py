"""Structured-output schemas for every model step. Field names follow spec section 5."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from ..taxonomy import RoleFamily


def _no_defaults(schema: dict) -> None:
    for prop in (schema.get("properties") or {}).values():
        prop.pop("default", None)


class BaseModel(_PydanticBase):
    """Defaults exist for Python callers only. The JSON schema sent to the model carries
    none: OpenAI strict structured outputs reject the `default` keyword, and the model must
    fill every field itself either way."""
    model_config = ConfigDict(json_schema_extra=_no_defaults)

# ------------------------------------------------------------------ S1 extract

# The kind of work a post is for: one of the shared role families (app/taxonomy.py).
Discipline = RoleFamily


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
    # Who reads this address, only when the post says so ("send your CV to Priya, our CTO, at ...").
    person_name: Optional[str] = None
    person_role: Optional[str] = None


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
    exp_min: Optional[float] = None
    exp_max: Optional[float] = None
    skills_must: list[str] = Field(default_factory=list)
    skills_nice: list[str] = Field(default_factory=list)
    apply_routes: list[ApplyRoute] = Field(default_factory=list)
    posted_age_label: Optional[str] = None
    mill_signals: list[str] = Field(default_factory=list)
    asks_candidate_for_money: bool = False
    company_type_hint: Literal["startup", "sme", "big_tech", "large_enterprise", "it_services_major",
                               "staffing", "training", "unknown"] = "unknown"
    shared_by_third_party: bool = False


# ------------------------------------------------------------------ discovery (app/discover.py)

class FundedCompany(BaseModel):
    name: str
    website: Optional[str] = None          # only a link the article itself gives
    what_it_does: str
    round: Optional[str] = None            # "Series A", "seed"
    amount: Optional[str] = None           # as written: "$5 Mn", "Rs 100 Cr"
    city: Optional[str] = None


class FundingNews(BaseModel):
    companies: list[FundedCompany] = Field(default_factory=list)


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
    """S5 tailors one baseline (chosen in code) to one opening: ids and order only, plus a
    summary that code holds to the person's own record."""
    role_title: str
    summary: str
    left_sections: list[SectionSel]
    bullet_ids: list[str]
    drop_entry_ids: list[str] = Field(default_factory=list)
    skills_first: list[str] = Field(default_factory=list)
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
    # For experience: counts toward years of experience only when full_time (or unknown and
    # not called an internship).
    employment: Literal["full_time", "internship", "part_time", "freelance", "unknown"] = "unknown"


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


class SkillGroupP(BaseModel):
    label: str
    items: str


class ProposedBaseline(BaseModel):
    family: Discipline
    title_line: str
    summary: str
    left_sections: list[SectionSel]
    skills: list[SkillGroupP]
    evidence_item_keys: list[str]
    fit: Literal["strong", "good", "stretch"]
    fit_why: str
    gaps: list[str]


class FamilySuggestion(BaseModel):
    family: Discipline
    why: str
    evidence_item_keys: list[str]


class BaselineSet(BaseModel):
    baselines: list[ProposedBaseline]
    suggestions: list[FamilySuggestion]
