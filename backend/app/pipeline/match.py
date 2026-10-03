"""
The per-user half of the pipeline (docs/plan-global-pool.md, 0.5): does one opening suit one
person, how well, and why. Code only, so every eligible (person, opening) pair can be scored
at no model cost; the model runs later, only when the person prepares a letter.

Eligibility first: the person's own rules (place, work mode, employment type, batch, CGPA,
excluded companies, one role per company, freshness, pay; screen.user_match), then the kind of
role and the years of experience. Then a score out of 100:

  skills      40  the skills the opening asks for; one the person's work shows counts more
                  than one only listed
  family      25  one of their target kinds of role (and how strong that baseline is), or a
                  neighbour of one
  experience  15  their years against the opening's range, one year of tolerance as a gap
  freshness   10  posts age in hours; board listings in weeks
  contact     10  who there is to write to, by where the address was published

The same opening scores differently for different people, with the reasons and gaps in plain
words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

from psycopg.types.json import Jsonb

from .. import taxonomy as tx
from ..db import user_tx
from ..provenance import normalize
from . import contacts as contacts_mod
from . import screen as screen_mod
from .schemas import Extracted

WEIGHTS = {"skills": 40, "family": 25, "experience": 15, "freshness": 10, "contact": 10}
FIT_CREDIT = {"strong": 1.0, "good": 0.8, "stretch": 0.55}
NEIGHBOUR = 0.6                  # a neighbouring family, times that baseline's fit
SHOWN, LISTED = 1.0, 0.6         # a required skill the person's work shows, or only lists
NO_SKILLS_STATED = 0.6
EXPERIENCE_CREDIT = {"fits": 1.0, "unstated": 0.85, "stretch": 0.5}
STRONG_AT, GOOD_AT = 70, 50
STRONG_SKILLS = 0.7              # a strong match also needs most of the asked-for skills
POOL_WINDOW_DAYS = 60            # pool openings posted longer ago than this are not matched
# A pasted post ages in hours (founders hire within days). Board listings, careers pages and the
# month-long Hacker News thread stay valid while listed, ranked by age.
SOCIAL_SOURCES = {"paste"}
# Words that are tool names but also ordinary English: only a stack field counts for them.
ORDINARY_WORDS = {"go", "rest", "express", "spark", "swift", "excel", "next", "c", "r"}


class MatchError(RuntimeError):
    pass


# ------------------------------------------------------------------ the person and the opening

@dataclass
class TrackFit:
    key: str
    family: str
    label: str
    fit: Optional[str] = None


@dataclass
class Seeker:
    stage: str
    years: float
    band: Optional[str]
    profile: dict
    prefs: dict
    tracks: list[TrackFit]
    listed: dict[str, str]                       # skill key -> as the person lists it
    stacks: dict[str, list[str]]                 # skill key -> items whose stack names it
    item_text: list[tuple[str, str]]             # (item name, normalised text)
    applied: dict[str, str] = field(default_factory=dict)   # company key -> job id applied to

    @property
    def families(self) -> list[str]:
        return [t.family for t in self.tracks] or list(self.prefs.get("target_families") or [])


def track_family(t: dict) -> str:
    if t.get("role_family"):
        return t["role_family"]
    return t["key"] if t["key"] in tx.FAMILIES else tx.title_family(t.get("label") or t.get("title_line"))


def make_seeker(*, profile: dict, prefs: dict, tracks: list[dict], skills: list[str], items: list[dict],
                applied: Optional[dict[str, str]] = None) -> Seeker:
    """items: {kind, name, tagline, stack, bullets: [text]} for each usable project or job."""
    stage = profile.get("career_stage") or "student"
    years = float(profile.get("experience_years") or 0)
    stacks: dict[str, list[str]] = {}
    item_text = []
    for it in items:
        shown_as = "your work at " + it["tagline"] if it.get("kind") == "experience" and it.get("tagline") else it["name"]
        for s in re.split(r"[,;|/]", it.get("stack") or ""):
            if s.strip():
                stacks.setdefault(tx.skill_key(tx.canonical_skill(s)), []).append(shown_as)
        text = " ".join([it["name"], it.get("tagline") or "", it.get("stack") or "", *(it.get("bullets") or [])])
        item_text.append((shown_as, normalize(text)))
    return Seeker(
        stage=stage, years=years, band=profile.get("experience_band") or tx.band_for_years(years, stage),
        profile=profile, prefs=prefs,
        tracks=[TrackFit(key=t["key"], family=track_family(t), label=t.get("label") or t["key"], fit=t.get("fit"))
                for t in tracks],
        listed={tx.skill_key(tx.canonical_skill(s)): s.strip() for s in skills if s.strip()},
        stacks=stacks, item_text=item_text, applied=dict(applied or {}))


@dataclass
class Opening:
    """One opening as matching sees it: the extraction, its normalised columns, the global
    screen and its contact candidates."""
    id: Optional[str]
    ex: Extracted
    cols: dict
    screen: dict
    contacts: list[contacts_mod.Candidate]
    source: str = "paste"
    age_hours: Optional[float] = None

    @property
    def social(self) -> bool:
        return self.source in SOCIAL_SOURCES

    @property
    def company_key(self) -> Optional[str]:
        return screen_mod.company_key(self.ex)

    @property
    def portal(self) -> Optional[str]:
        return screen_mod.portal(self.ex)


def age_now(posted_at: Optional[datetime], fallback: Optional[float] = None) -> Optional[float]:
    if posted_at is None:
        return fallback
    return max(0.0, (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600)


def opening_from_row(job: dict, contact_rows: list[dict]) -> Opening:
    cols = {k: job.get(k) for k in ("title", "role_family", "employment_type", "exp_min", "exp_max",
                                    "skills_must", "skills_nice", "work_mode", "city", "visibility")}
    for k in ("exp_min", "exp_max"):
        cols[k] = float(cols[k]) if cols[k] is not None else None
    return Opening(id=str(job["id"]), ex=Extracted.model_validate(job["extracted"]), cols=cols,
                   screen=job.get("screen") or {"decision": "keep", "reasons": [], "flags": []},
                   contacts=[contacts_mod.Candidate.from_row(r) for r in contact_rows],
                   source=job.get("source") or "paste", age_hours=age_now(job.get("posted_at")))


# ------------------------------------------------------------------ the parts of the score

@lru_cache(maxsize=2048)
def _mention_re(skill: str) -> Optional[re.Pattern]:
    words = sorted({normalize(s) for s in tx.skill_spellings(skill)} - ORDINARY_WORDS, key=len, reverse=True)
    words = [w for w in words if len(w) >= 2]
    if not words:
        return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z0-9])")


def skill_evidence(s: Seeker, skill: str) -> tuple[float, list[str]]:
    """(credit, items that show it). Shown in a project or job: full credit. Only on the
    skills list: partial. Neither: none. "FastAPI or Django": the best of the two."""
    alternatives = [p for p in re.split(r"\s+or\s+", skill.strip(), flags=re.I) if p.strip()]
    if len(alternatives) > 1:
        return max((skill_evidence(s, a) for a in alternatives), key=lambda e: (e[0], len(e[1])))
    key = tx.skill_key(tx.canonical_skill(skill))
    names = list(s.stacks.get(key, []))
    rx = _mention_re(skill)
    if rx is not None:
        names += [n for n, t in s.item_text if rx.search(t) and n not in names]
    if names:
        return SHOWN, names
    if key in s.listed:
        return LISTED, []
    return 0.0, []


def family_fit(s: Seeker, family: str) -> tuple[str, Optional[TrackFit]]:
    """('target' | 'neighbour' | 'none', the baseline to tailor)."""
    def best(ts: list[TrackFit]) -> Optional[TrackFit]:
        return max(ts, key=lambda t: FIT_CREDIT.get(t.fit or "", 0.8)) if ts else None
    exact = [t for t in s.tracks if t.family == family]
    if exact:
        return "target", best(exact)
    near = [t for t in s.tracks if family in tx.family_with_neighbours(t.family)]
    if near:
        return "neighbour", best(near)
    if family in (s.prefs.get("target_families") or []):
        return "target", best(s.tracks)
    return "none", best(s.tracks)


def experience(s: Seeker, o: Opening) -> tuple[str, Optional[str]]:
    """('fits' | 'unstated' | 'stretch' | 'under' | 'over', a note for the person)."""
    if o.cols.get("employment_type") == "internship":
        return "fits", None
    lo, hi = o.cols.get("exp_min"), o.cols.get("exp_max")
    if lo is None and hi is None:
        if tx.seniority_hint(o.cols.get("title")) == "senior" and s.band in ("intern", "entry", "junior"):
            return "stretch", "A senior title with no years stated; you have {:g} years".format(round(s.years, 1))
        return "unstated", None
    return tx.experience_fit(s.years, lo, hi)


def freshness(age_hours: Optional[float], social: bool, ceiling: float) -> float:
    if age_hours is None:
        return 0.5
    if social:
        return max(0.0, 1 - age_hours / ceiling)
    days = age_hours / 24
    return 1.0 if days <= 7 else max(0.3, 1 - 0.7 * (days - 7) / 23)


def contact_credit(c: Optional[contacts_mod.Candidate], portal: Optional[str]) -> float:
    if c is None:
        return 0.45 if portal else 0.0
    if c.context == "post_apply":
        return (1.0, 0.95, 0.95, 0.9, 0.85)[min(c.tier, 4)] - (0.1 if c.domain_matches is False else 0)
    return 0.8 if c.context == "careers_page" else 0.35


def _years(lo: Optional[float], hi: Optional[float]) -> str:
    if lo is not None and hi is not None:
        return "{:g} years".format(lo) if lo == hi else "{:g} to {:g} years".format(lo, hi)
    return "{:g}+ years".format(lo) if lo is not None else "up to {:g} years".format(hi)


def _and(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _hours(h: float) -> str:
    if h < 1:
        return "under an hour ago"
    return "{:.0f} hour{} ago".format(h, "" if round(h) == 1 else "s")


# ------------------------------------------------------------------ one person, one opening

@dataclass
class MatchResult:
    decision: str
    reasons: list[str]
    flags: list[str]
    score: Optional[float]
    bucket: Optional[str]
    why: list[str]
    gaps: list[str]
    track_key: Optional[str]
    contact: Optional[contacts_mod.Candidate]
    route: Optional[str]
    apply_to: Optional[str]
    stipend_rule: str
    parts: dict

    def screen_json(self) -> dict:
        return {"decision": self.decision, "reasons": self.reasons, "flags": self.flags, "route": self.route,
                "apply_to": self.apply_to, "stipend_rule": self.stipend_rule,
                "parts": {k: round(v, 2) for k, v in self.parts.items()}}


def evaluate(s: Seeker, o: Opening, override: bool = False) -> MatchResult:
    g = o.screen or {}
    sc = screen_mod.Screen(decision=g.get("decision", "keep"), reasons=list(g.get("reasons") or []),
                           flags=list(g.get("flags") or []))
    applied = {k for k, job in s.applied.items() if job != o.id}
    screen_mod.user_match(o.ex, sc, s.prefs, s.profile, applied, o.age_hours, o.company_key, social=o.social)

    family = o.cols.get("role_family") or "other"
    kind, track = family_fit(s, family)
    if kind == "none":
        targets = [tx.FAMILIES[f].label for f in s.families if f in tx.FAMILIES]
        sc.drop("Not a kind of role you're targeting ({}){}".format(
            tx.FAMILIES.get(family, tx.FAMILIES["other"]).label,
            ". Your targets: " + ", ".join(targets) if targets else ""))
    exp_status, exp_note = experience(s, o)
    if exp_status in ("under", "over"):
        sc.drop(exp_note)

    # Skills.
    must, nice = list(o.cols.get("skills_must") or []), list(o.cols.get("skills_nice") or [])
    shown: dict[str, list[str]] = {}          # item -> skills it shows
    listed_only, missing = [], []
    got = total = 0.0
    for weight, names in ((1.0, must), (0.5, nice)):
        for sk in names:
            credit, items = skill_evidence(s, sk)
            got += weight * credit
            total += weight
            if items:
                shown.setdefault(items[0], []).append(sk)
            elif credit and weight == 1.0:
                listed_only.append(sk)
            elif not credit and weight == 1.0:
                missing.append(sk)
    skills_part = got / total if total else NO_SKILLS_STATED

    fit_credit = FIT_CREDIT.get(track.fit or "", 0.8) if track else 0.8
    family_part = {"target": fit_credit, "neighbour": NEIGHBOUR * fit_credit, "none": 0.0}[kind]
    ceiling = float(s.prefs.get("freshness_ceiling_hours") or 72)
    contact = contacts_mod.choose(o.contacts, bool(o.portal))
    parts = {"skills": skills_part, "family": family_part,
             "experience": EXPERIENCE_CREDIT.get(exp_status, 0.0),
             "freshness": freshness(o.age_hours, o.social, ceiling),
             "contact": contact_credit(contact, o.portal)}
    score = round(sum(WEIGHTS[k] * v for k, v in parts.items()), 1)

    # Why, in the person's terms.
    why = []
    for item, sks in sorted(shown.items(), key=lambda kv: -len(kv[1]))[:2]:
        why.append("{}: used in {}".format(_and(sks[:4]), item))
    if listed_only and not shown:
        why.append("On your skills list: {}".format(_and(listed_only[:3])))
    if track and kind == "target":
        label = tx.FAMILIES.get(family, tx.FAMILIES["other"]).label
        why.append("{} is one of your targets{}".format(
            label, "; your {} resume is a {} fit".format(track.label, track.fit) if track.fit in ("strong", "good") else ""))
    elif track and kind == "neighbour":
        why.append("Close to your {} target".format(track.label))
    lo, hi = o.cols.get("exp_min"), o.cols.get("exp_max")
    if exp_status == "fits" and (lo is not None or hi is not None) and (hi is None or s.years <= hi):
        why.append("Asks for {}; you have {:g}".format(_years(lo, hi), round(s.years, 1)))
    elif exp_status == "fits" and o.cols.get("employment_type") == "internship" and s.stage == "student":
        why.append("An internship, and you're a student")
    if o.social and o.age_hours is not None and o.age_hours < 24:
        why.append("Posted " + _hours(o.age_hours))
    if contact is not None and contact.context != "site_generic":
        why.append("Email to {}, {}".format(contact.who(), contacts_mod.CONTEXT_LABEL[contact.context]))

    gaps = ["Asks for " + sk for sk in missing[:4]]
    gaps += ["No project shows {} yet; it's only on your skills list".format(sk) for sk in listed_only[:2]]
    if exp_status == "stretch" and exp_note:
        gaps.append(exp_note)
    if track and track.fit == "stretch":
        gaps.append("Your {} resume is a stretch fit".format(track.label))

    if sc.decision == "drop" and not override:
        bucket = None
    elif (score >= STRONG_AT and skills_part >= STRONG_SKILLS and len(missing) <= 1
          and exp_status in ("fits", "unstated") and kind == "target"):
        bucket = "strong"
    elif score >= GOOD_AT and len(missing) <= 2:
        bucket = "good"
    else:
        bucket = "gaps"

    route = "email" if contact else ("portal" if o.portal else None)
    return MatchResult(
        decision="keep" if override else sc.decision, reasons=sc.reasons, flags=sc.flags, score=score,
        bucket=bucket, why=why, gaps=gaps, track_key=track.key if track else None, contact=contact, route=route,
        apply_to=contact.email if contact else o.portal, stipend_rule=sc.stipend_rule, parts=parts)


# ------------------------------------------------------------------ database

def load_seeker(conn) -> Seeker:
    """Inside user_tx: row-level security scopes every query to the person."""
    profile = conn.execute("select * from profiles").fetchone() or {}
    prefs = conn.execute("select * from preferences").fetchone() or {}
    tracks = conn.execute("select key, label, title_line, role_family, fit from tracks order by sort").fetchall()
    skills = [r["text"] for r in conn.execute(
        "select text from facts where kind = 'skill' and confirmed_at is not null").fetchall()]
    items = conn.execute("select id, kind, name, tagline, stack from items where confirmed order by sort").fetchall()
    bullets: dict = {}
    for b in conn.execute("select item_id, text from bullets where confirmed").fetchall():
        bullets.setdefault(b["item_id"], []).append(b["text"])
    applied = {r["company_key"]: str(r["job_id"]) for r in conn.execute(
        "select company_key, job_id from applications").fetchall()}
    return make_seeker(profile=dict(profile), prefs=dict(prefs), tracks=[dict(t) for t in tracks], skills=skills,
                       items=[{**dict(i), "bullets": bullets.get(i["id"], [])} for i in items], applied=applied)


def load_openings(conn, job_ids: list[str]) -> list[Opening]:
    if not job_ids:
        return []
    jobs = conn.execute("select * from jobs where id = any(%s::uuid[]) and extracted is not null",
                        (job_ids,)).fetchall()
    by_job: dict = {}
    for c in conn.execute("select * from opportunity_contacts where job_id = any(%s::uuid[])", (job_ids,)).fetchall():
        by_job.setdefault(c["job_id"], []).append(c)
    return [opening_from_row(j, by_job.get(j["id"], [])) for j in jobs]


def save(conn, user_id: str, job_id: str, m: MatchResult, override: bool) -> str:
    row = conn.execute(
        """insert into matches (user_id, job_id, decision, reasons, screen, overridden, score, bucket, why, gaps,
               contact_id, track_key, rank, computed_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
           on conflict (user_id, job_id) do update set decision = excluded.decision, reasons = excluded.reasons,
               screen = excluded.screen, overridden = matches.overridden or excluded.overridden,
               score = excluded.score, bucket = excluded.bucket, why = excluded.why, gaps = excluded.gaps,
               contact_id = excluded.contact_id, track_key = excluded.track_key, rank = excluded.rank,
               computed_at = now()
           returning id::text""",
        (user_id, job_id, m.decision, Jsonb(m.reasons), Jsonb(m.screen_json()), override, m.score, m.bucket,
         Jsonb(m.why), Jsonb(m.gaps), m.contact.id if m.contact else None, m.track_key, m.score)).fetchone()
    return row["id"]


def match_one(user_id: str, job_id: str, override: bool = False) -> tuple[str, MatchResult]:
    with user_tx(user_id) as conn:
        s = load_seeker(conn)
        found = load_openings(conn, [job_id])
        if not found:
            raise MatchError("opening not found or not read yet")
        prev = conn.execute("select overridden from matches where job_id = %s", (job_id,)).fetchone()
        override = override or bool(prev and prev["overridden"])
        m = evaluate(s, found[0], override)
        return save(conn, user_id, job_id, m, override), m


def match_user(user_id: str) -> int:
    """Re-score every opening this person can see: the posts they pasted, and active pool
    openings in their kinds of role (and neighbours) that passed the shared screen. Code only.
    A pool opening that does not suit them is not stored, unless a match row already exists
    (their pasted posts are, so they can see why one was dropped)."""
    with user_tx(user_id) as conn:
        s = load_seeker(conn)
        fams = sorted(set().union(*(tx.family_with_neighbours(f) for f in s.families))) if s.families else []
        ids = [str(r["id"]) for r in conn.execute(
            """select id from jobs where extracted is not null and (
                   owner_user_id = %s
                   or (visibility = 'public' and state = 'active' and status = 'done' and role_family = any(%s)
                       and coalesce(screen->>'decision', 'keep') = 'keep'
                       and coalesce(posted_at, first_seen_at) > now() - make_interval(days => %s)))""",
            (user_id, fams, POOL_WINDOW_DAYS)).fetchall()]
        existing = {str(r["job_id"]): r["overridden"] for r in conn.execute(
            "select job_id, overridden from matches").fetchall()}
        n = 0
        for o in load_openings(conn, ids):
            ov = bool(existing.get(o.id))
            m = evaluate(s, o, ov)
            if m.decision == "drop" and o.id not in existing and o.cols.get("visibility") == "public":
                continue
            save(conn, user_id, o.id, m, ov)
            n += 1
    return n
