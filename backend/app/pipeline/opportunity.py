"""
The global half of the pipeline (docs/plan-global-pool.md, A): one opening, read once for
everyone it may suit. S1 extract, normalise into the columns the pool filters on, the screen
that applies to everyone (S2), the company check (S4) and the contact candidates. Nothing here
reads a person's data: a pasted post goes through the same steps and stays private to the
person who pasted it.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from psycopg.types.json import Jsonb

from .. import llm
from .. import taxonomy as tx
from ..db import system_tx
from . import contacts as contacts_mod
from . import extract as ex_mod
from . import screen as screen_mod
from . import verify as verify_mod
from .schemas import Extracted

# Posts age fast (founders hire within days); a job-board listing stays valid while listed.
SOCIAL_SOURCES = {"paste", "hn"}
MAX_SKILLS = 20


class OpportunityError(RuntimeError):
    pass


def work_mode(ex: Extracted) -> str:
    if ex.remote is True:
        return "remote"
    if ex.hybrid:
        return "hybrid"
    if ex.remote is False:
        return "onsite"
    return "unknown"


def family_of(ex: Extracted) -> str:
    """The title decides when it names a kind of work. A generic title ("Software Engineer")
    takes the model's narrower reading of the whole post when that is a neighbour."""
    title = ex.title or (ex.role_titles[0] if ex.role_titles else None)
    fam = tx.title_family(title)
    if fam == "other" or (fam == "sde" and ex.discipline in tx.FAMILIES["sde"].neighbours):
        return ex.discipline
    return fam


def _skills(names: list[str], skip: set[str] = frozenset()) -> list[str]:
    """Canonical names, once each. "fastapi or django" (either will do) stays one requirement."""
    out, seen = [], set(skip)
    for n in names:
        name = " or ".join(tx.canonical_skill(p) for p in re.split(r"\s+or\s+", n.strip(), flags=re.I) if p.strip())
        k = tx.skill_key(name)
        if k and k not in seen and len(name) <= 40:
            seen.add(k)
            out.append(name)
    return out[:MAX_SKILLS]


def _currency(c: Optional[str]) -> Optional[str]:
    if not c:
        return None
    c = c.strip().upper().replace("₹", "INR").replace("RS.", "INR").replace("RS", "INR")
    return "INR" if c.startswith("INR") else c[:8]


def normalise(ex: Extracted) -> dict:
    """The jobs columns for one extracted opening."""
    title = ex.title or (ex.role_titles[0] if ex.role_titles else None)
    family = family_of(ex)
    emp = ex.employment_type
    if emp == "unknown" and tx.is_internship(title):
        emp = "internship"
    lo, hi = ex.exp_min, ex.exp_max
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    must = _skills(ex.skills_must)
    nice = _skills(ex.skills_nice, {tx.skill_key(s) for s in must})
    pay = ex.stipend if ex.stipend.stated == "figure" else None
    link = screen_mod.portal(ex)
    return {
        "title": title, "role_family": family, "role_families": sorted(tx.family_with_neighbours(family)),
        "employment_type": emp, "exp_min": lo, "exp_max": hi,
        "experience_bands": tx.bands_for_range(lo, hi, emp),
        "country": ex.country, "city": ex.onsite_city, "work_mode": work_mode(ex),
        "pay_min": pay.min if pay else None, "pay_max": pay.max if pay else None,
        "pay_currency": _currency(pay.currency) if pay else None, "pay_period": pay.period if pay else None,
        "skills_must": must, "skills_nice": nice,
        "batch_years": sorted(set(ex.batch_years)), "cgpa_min": ex.cgpa_min,
        "apply_url": link if link and link.startswith("http") else None,
    }


def dedupe_key(ex: Extracted, cols: dict) -> Optional[str]:
    """The same opening found twice (two boards, a board and a careers page): the company,
    the title without levels or punctuation, and the city."""
    who = screen_mod.company_key(ex)
    if not who or not cols.get("title"):
        return None
    title = re.sub(r"[^a-z0-9]+", " ", cols["title"].lower()).strip()
    city = re.sub(r"[^a-z]+", "", (cols.get("city") or cols.get("work_mode") or "").lower())
    return hashlib.sha1("{}|{}|{}".format(who, title, city).encode()).hexdigest()[:24]


@dataclass
class Read:
    ex: Extracted
    screen: screen_mod.Screen
    verification: Optional[verify_mod.Verification]
    contacts: list[contacts_mod.Candidate] = field(default_factory=list)
    portal: Optional[str] = None
    age_hours: Optional[float] = None


def read(raw_text: str, source_ref: Optional[str], ctx: llm.CallContext, *,
         verify: Callable = verify_mod.verify, site: Callable = contacts_mod.site_candidates) -> Read:
    """S1, S2, S4 and contact candidates for one opening. Model calls and network, but no
    database writes beyond the shared company cache."""
    ex = ex_mod.extract(raw_text, source_ref, ctx)
    sc = screen_mod.global_screen(ex)
    domain = screen_mod.company_domain(ex)

    v: Optional[verify_mod.Verification] = None
    if sc.decision == "keep":
        v = verify(ex, domain, ctx)
        if v.verification == "fail":
            for r in v.reasons:
                sc.drop(r)
        sc.flags.extend(v.flags)
        if v.linkedin_check_url:
            sc.flags.append("Check the company page yourself: " + v.linkedin_check_url)

    cands, notes = contacts_mod.from_post(ex, raw_text, domain)
    sc.flags.extend(notes)
    link = screen_mod.portal(ex)
    if sc.decision == "keep" and not cands and domain and v is not None and v.verification != "fail":
        cands = site(domain)
    if not cands and not link:
        sc.drop("No apply route: the post gives no email, form or ATS link, and the company's site "
                "publishes no hiring address")
    flag = contacts_mod.flag_for(contacts_mod.choose(cands, bool(link)))
    if flag:
        sc.flags.append(flag)
    return Read(ex=ex, screen=sc, verification=v, contacts=cands, portal=link,
                age_hours=ex_mod.parse_age_hours(ex.posted_age_label))


def store(job_id: str, r: Read, public: bool = False) -> None:
    cols = normalise(r.ex)
    if public:
        cols["dedupe_key"] = dedupe_key(r.ex, cols)
    names = list(cols)
    with system_tx() as conn:
        conn.execute(
            """update jobs set extracted = %s, posted_age_hours = %s,
                   posted_at = case when %s::numeric is null then null
                                    else first_seen_at - make_interval(secs => %s::numeric * 3600) end,
                   company_id = %s, screen = %s, last_seen_at = now(), {}
               where id = %s""".format(", ".join("{} = %s".format(n) for n in names)),
            [Jsonb(r.ex.model_dump()), r.age_hours, r.age_hours, r.age_hours,
             r.verification.company_id if r.verification else None, Jsonb(r.screen.as_json())]
            + [cols[n] for n in names] + [job_id])
        conn.execute("delete from opportunity_contacts where job_id = %s", (job_id,))
        for c in r.contacts:
            row = conn.execute(
                """insert into opportunity_contacts (job_id, email, person_name, person_role, context, source_url,
                       is_generic, domain_matches, confidence, evidence)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (job_id, email) do nothing returning id::text""", c.as_row(job_id)).fetchone()
            if row:
                c.id = row["id"]


def process(job_id: str, user_id: Optional[str] = None) -> Read:
    """Read and store one opening. user_id: whose model budget a pasted post is billed to."""
    with system_tx() as conn:
        job = conn.execute("select id, raw_text, source_ref, visibility from jobs where id = %s", (job_id,)).fetchone()
        if job is None:
            raise OpportunityError("opening not found")
        conn.execute("update jobs set status = 'processing', error = null where id = %s", (job_id,))
    r = read(job["raw_text"], job["source_ref"], llm.CallContext(user_id=user_id, job_id=job_id))
    store(job_id, r, public=job["visibility"] == "public")
    return r
