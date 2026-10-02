"""
S2 global screen and S3 user match, in code (spec 5.2, 5.3). Deterministic rules on the
extracted fields: cheap, explainable, and the user can override any drop.

A drop carries its reasons; a flag is a judgment call surfaced to the user without
blocking the lead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .extract import PERSONAL_DOMAINS, email_domain
from .schemas import Extracted

INDIA = {"india", "in", "bharat"}


@dataclass
class Screen:
    decision: str = "keep"                       # keep | drop
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    route: Optional[str] = None                  # email | portal
    apply_to: Optional[str] = None
    stipend_rule: str = "none"                   # ask | state_floor | none

    def drop(self, reason: str) -> None:
        self.decision = "drop"
        self.reasons.append(reason)

    def as_json(self) -> dict:
        return {"decision": self.decision, "reasons": self.reasons, "flags": self.flags,
                "route": self.route, "apply_to": self.apply_to, "stipend_rule": self.stipend_rule}


def slug(text: str) -> str:
    text = re.sub(r"\b(pvt|private|ltd|limited|llp|inc|technologies|technology|labs|solutions)\b\.?",
                  " ", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def company_domain(ex: Extracted) -> Optional[str]:
    if ex.company_domain:
        d = re.sub(r"^https?://", "", ex.company_domain.strip().lower()).split("/")[0]
        return d[4:] if d.startswith("www.") else d
    for r in ex.apply_routes:
        if r.type == "email" and r.value and email_domain(r.value) not in PERSONAL_DOMAINS:
            return email_domain(r.value)
    return None


def company_key(ex: Extracted) -> Optional[str]:
    """One application per company: the domain when known, else the company's name."""
    d = company_domain(ex)
    if d:
        return d
    return slug(ex.company_name) if ex.company_name else None


def monthly(ex: Extracted) -> Optional[float]:
    s = ex.stipend
    amount = s.max if s.max is not None else s.min
    if amount is None:
        return None
    if s.period == "year":
        return amount / 12
    if s.period == "total":
        return None
    return amount


def portal(ex: Extracted) -> Optional[str]:
    """The post's own application form or portal link, if it gives one."""
    for r in ex.apply_routes:
        if r.type in ("form", "ats", "linkedin_apply"):
            return r.value or r.type
    return None


def global_screen(ex: Extracted) -> Screen:
    """What rules an opening out for everyone. Who to write to is decided later, from the
    contact candidates (contacts.py)."""
    sc = Screen()
    if ex.asks_candidate_for_money:
        sc.drop("Asks the candidate for money")
    if ex.mill_signals:
        sc.drop("Internship mill signals: " + "; ".join(ex.mill_signals[:3]))
    if ex.poster_type in ("recruiter", "aggregator"):
        pointer = " Use {} as a pointer: find and paste the company's own post.".format(
            ex.company_name) if ex.company_name else ""
        sc.drop("Posted by a {}, not the company. No intermediary post has ever converted.{}"
                .format(ex.poster_type, pointer))
    if ex.company_type_hint in ("staffing", "training"):
        sc.drop("Company looks like a {} business".format(ex.company_type_hint))

    country = (ex.country or "").strip().lower()
    if country and country not in INDIA and ex.remote is not True:
        sc.drop("Outside supported geography ({}) and not remote".format(ex.country))
    elif country and country not in INDIA:
        sc.flags.append("Remote role at a company based in {}".format(ex.country))

    if ex.shared_by_third_party:
        sc.flags.append("Shared by a third party, not posted by the company")
    return sc


def user_match(ex: Extracted, sc: Screen, prefs: dict, profile: dict, applied: set[str],
               age_hours: Optional[float], key: Optional[str], social: bool = True) -> Screen:
    """One person's rules. The kind of role and years of experience are matched in match.py.
    social: a post (freshness ceiling applies); job-board listings stay valid while listed."""
    # Work mode and place.
    locs = [l.lower() for l in (prefs.get("locations") or [])]
    anywhere = not locs or any("anywhere" in l for l in locs)
    if ex.remote is True:
        if not prefs.get("remote_ok", True):
            sc.drop("Remote role; remote is switched off in preferences")
    elif ex.remote is False or ex.hybrid:
        mode_ok = prefs.get("hybrid_ok", True) if ex.hybrid else prefs.get("onsite_ok", True)
        if not mode_ok:
            sc.drop("{} role; that work mode is switched off in preferences".format(
                "Hybrid" if ex.hybrid else "Onsite"))
        city = (ex.onsite_city or ex.location_text or "").lower()
        if not anywhere and city and not any(l in city or city in l for l in locs if l != "remote"):
            sc.drop("Location {} is not in preferred locations".format(ex.onsite_city or ex.location_text))
    else:
        sc.flags.append("Work mode (remote or onsite) not stated")

    open_to = prefs.get("open_to") or ["internship"]
    if ex.employment_type in ("internship", "full_time") and ex.employment_type not in open_to:
        sc.drop("{} role; preferences are {}".format(ex.employment_type.replace("_", "-"),
                                                       ", ".join(open_to)))

    by = profile.get("batch_year")
    if ex.batch_years and by and int(by) not in ex.batch_years:
        sc.drop("Batch-year gate ({}) excludes {}".format(", ".join(map(str, ex.batch_years)), by))
    cg = profile.get("cgpa")
    if ex.cgpa_min and cg and float(cg) < ex.cgpa_min:
        sc.drop("CGPA gate {} is above {}".format(ex.cgpa_min, cg))

    if ex.company_type_hint in (prefs.get("excluded_company_types") or []):
        sc.drop("Excluded company type ({})".format(ex.company_type_hint.replace("_", " ")))
    excluded = {slug(c) for c in (prefs.get("excluded_companies") or [])}
    if ex.company_name and slug(ex.company_name) in excluded:
        sc.drop("Company is on the excluded list")

    if key and key in applied:
        sc.drop("Already applied to this company (one role per company)")
    if not key:
        sc.flags.append("Company not identifiable from the post")

    ceiling = prefs.get("freshness_ceiling_hours") or 72
    if social and age_hours is None:
        sc.flags.append("Post age unknown")
    elif social and age_hours > ceiling:
        sc.drop("Post is {:.0f}h old, past the {}h freshness ceiling".format(age_hours, ceiling))

    if is_job(ex, profile):
        _salary(ex, sc, prefs)
    else:
        _stipend(ex, sc, prefs)
    return sc


def is_job(ex: Extracted, profile: dict) -> bool:
    """Full-time pay rules (a yearly salary floor, never asked about in a first email) or an
    internship's (a monthly stipend floor, asked about when unstated)."""
    if ex.employment_type == "full_time":
        return True
    if ex.employment_type == "internship":
        return False
    return (profile.get("career_stage") or "student") != "student"


def yearly(ex: Extracted) -> Optional[float]:
    s = ex.stipend
    amount = s.max if s.max is not None else s.min
    if amount is None or s.period == "total":
        return None
    return amount * 12 if s.period == "month" else amount


def _salary(ex: Extracted, sc: Screen, prefs: dict) -> None:
    floor = prefs.get("salary_floor")
    s = ex.stipend
    if s.stated == "figure":
        y = yearly(ex)
        cur = (s.currency or "").upper().replace("RS", "INR").replace("₹", "INR")
        if floor and y is not None and (not cur or cur.startswith("INR")) and y < floor:
            sc.drop("Stated pay ({:,.0f} a year) is below your floor ({:,})".format(y, floor))
        elif y is None or (cur and not cur.startswith("INR")):
            sc.flags.append("Pay stated in a form that cannot be compared with your floor")
    elif s.stated == "unpaid":
        sc.drop("Unpaid full-time role")
    elif s.stated == "performance_based":
        sc.flags.append("Pay is performance-based only")


def _stipend(ex: Extracted, sc: Screen, prefs: dict) -> None:
    floor = prefs.get("stipend_floor")
    s = ex.stipend
    if s.stated == "figure":
        m = monthly(ex)
        cur = (s.currency or "").upper().replace("RS", "INR").replace("₹", "INR")
        if floor and m is not None and (not cur or cur.startswith("INR")) and m < floor:
            sc.drop("Stated pay ({:,.0f}/month) is below the floor ({:,})".format(m, floor))
        elif m is None or (cur and not cur.startswith("INR")):
            sc.flags.append("Pay stated in a form that cannot be compared with the floor")
        return
    if s.stated in ("unstated", "performance_based"):
        sc.stipend_rule = "ask"
        if s.stated == "performance_based":
            sc.flags.append("Pay is performance-based only")
        return
    # Unpaid, including "paid after an unpaid period".
    onsite = ex.remote is False or bool(ex.hybrid)
    policy = prefs.get("unpaid_onsite_policy" if onsite else "unpaid_remote_policy") or (
        "drop" if onsite else "draft_with_floor")
    if ex.remote is None:
        sc.flags.append("Unpaid, and work mode not stated")
    if policy == "drop":
        sc.drop("Unpaid{} ({} policy: drop)".format(
            " after an evaluation period" if s.unpaid_period_months else "",
            "onsite/hybrid" if onsite else "remote"))
    elif floor:
        sc.stipend_rule = "state_floor"
        sc.flags.append("Unpaid: the email states your floor")
    else:
        sc.flags.append("Unpaid, and no stipend floor is set")
