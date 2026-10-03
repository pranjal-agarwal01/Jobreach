"""
Who to write to for one opening, with where each address was published
(docs/plan-global-pool.md, 0.4).

Which address to use depends on where it was published, not on how senior the person is. A
founder's address on a press page is not an invitation to apply, and writing there hurts the
person applying. In order:

  1. an address the post itself gives for applying: a named hiring manager or founder, then HR,
     then a hiring mailbox, then any other address the post gives;
  2. a hiring address (careers@, jobs@ ...) on the company's own site;
  3. the post's own portal or form, when it has one;
  4. the company's general inbox (hello@, contact@), only with a visible flag.

Never used: an address published for another purpose (press, support, sales, investors), a
named person's address found on a web page with no stated purpose, anything not written
verbatim, anything pattern-guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from ..db import system_tx
from .extract import EMAIL_RE, PERSONAL_DOMAINS, deobfuscate, email_domain
from .schemas import Extracted

SITE_CACHE_DAYS = 30
MAX_CAREERS_PAGES = 2

HIRING_LOCAL = re.compile(r"^(careers?|jobs?|hiring|hire|hr|recruit\w*|talent\w*|people|join\w*|apply|"
                          r"applications?|internships?|interns?|work\w*|cv|resumes?)$")
GENERIC_LOCAL = re.compile(r"^(hello|hi|hey|contact\w*|info|team|office|connect|mail|enquir(y|ies)|"
                           r"inquir(y|ies)|general|founders?)$")
OTHER_PURPOSE = re.compile(r"^(press|media|pr|news|support|help\w*|care|customer\w*|service|billing|accounts?|"
                           r"finance|invoices?|payments?|sales|partners?|partnerships?|investors?|ir|privacy|"
                           r"legal|dpo|grievances?|compliance|abuse|security|noreply|no-reply|donotreply|"
                           r"do-not-reply|webmaster|admin|postmaster|marketing|feedback|orders?)$")
CAREERS_LINK = re.compile(r"career|jobs?\b|join|hiring|work[\s_-]*with[\s_-]*us|open[\s_-]*(positions|roles)|"
                          r"openings|vacanc", re.I)
LEADER_ROLE = re.compile(r"found|ceo|cto|coo|cpo|chief|director|head|vp|vice\s+president|manager|lead|"
                         r"engineering|owner|partner", re.I)
HR_ROLE = re.compile(r"\bhr\b|human\s+resources|recruit|talent|people|hiring", re.I)

# Within a context, lower is better.
TIER_LEADER, TIER_HR, TIER_NAMED, TIER_HIRING_BOX, TIER_GENERIC_BOX = 0, 1, 2, 3, 4
CONTEXT_RANK = {"post_apply": 0, "careers_page": 1, "site_generic": 3}
PORTAL_RANK = 2
CONTEXT_LABEL = {"post_apply": "given in the post for applying",
                 "careers_page": "published on the company's own site as a hiring address",
                 "site_generic": "the company's general inbox; no hiring address is published"}


@dataclass
class Candidate:
    email: str
    context: str                        # post_apply | careers_page | site_generic
    tier: int = TIER_NAMED
    person_name: Optional[str] = None
    person_role: Optional[str] = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    is_generic: bool = False
    domain_matches: Optional[bool] = None
    personal_mailbox: bool = False
    id: Optional[str] = None

    @property
    def confidence(self) -> float:
        base = {"post_apply": 0.95, "careers_page": 0.8, "site_generic": 0.5}[self.context]
        base -= 0.05 * min(self.tier, 4) if self.context == "post_apply" else 0
        if self.domain_matches is False:
            base -= 0.2
        return round(max(base, 0.1), 2)

    def sort_key(self) -> tuple:
        return (CONTEXT_RANK[self.context], self.tier, self.domain_matches is False, self.personal_mailbox)

    def who(self) -> str:
        """'Priya Sharma (CTO)', or 'the hiring team (careers@acme.com)'."""
        if self.person_name:
            return "{} ({})".format(self.person_name, self.person_role) if self.person_role else self.person_name
        return "{} ({})".format("the hiring team" if self.context != "site_generic" else "the company's general inbox",
                                self.email)

    def as_row(self, job_id: str) -> tuple:
        return (job_id, self.email, self.person_name, self.person_role, self.context, self.source_url,
                self.is_generic, self.domain_matches, self.confidence, self.evidence)

    @classmethod
    def from_row(cls, r: dict) -> "Candidate":
        local, dom = r["email"].split("@", 1)
        c = cls(email=r["email"], context=r["context"], person_name=r.get("person_name"),
                person_role=r.get("person_role"), source_url=r.get("source_url"), evidence=r.get("evidence"),
                is_generic=bool(r.get("is_generic")), domain_matches=r.get("domain_matches"),
                personal_mailbox=dom.lower() in PERSONAL_DOMAINS, id=str(r["id"]) if r.get("id") else None)
        c.tier = _tier(local, c.person_name, c.person_role)
        return c


def _tier(local: str, name: Optional[str], role: Optional[str]) -> int:
    local = local.lower()
    if name or role:
        if role and HR_ROLE.search(role):
            return TIER_HR
        if role and LEADER_ROLE.search(role):
            return TIER_LEADER
        return TIER_NAMED
    if HIRING_LOCAL.match(local):
        return TIER_HIRING_BOX
    if GENERIC_LOCAL.match(local):
        return TIER_GENERIC_BOX
    return TIER_NAMED                       # a personal-looking address the post gives for applying


def _matches_domain(dom: str, company: Optional[str]) -> Optional[bool]:
    if not company:
        return None
    return dom == company or dom.endswith("." + company)


_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n\s*\n")


def _sentence_with(text: str, address: str) -> Optional[str]:
    """The sentence the address was written in, for the person to see. Posts wrap lines
    mid-sentence, so a single line break does not end one; a long run falls back to the line."""
    flat = deobfuscate(text)
    i = flat.lower().find(address.lower())
    if i < 0:
        return None
    ends = [m.end() for m in _SENTENCE_END.finditer(flat)]
    start = max([e for e in ends if e <= i], default=0)
    end = min([e for e in ends if e > i + len(address)], default=len(flat))
    out = " ".join(flat[start:end].split())
    if len(out) > 300:
        a, b = flat.rfind("\n", 0, i) + 1, flat.find("\n", i)
        out = " ".join(flat[a:b if b >= 0 else len(flat)].split())
    return out[:300] or None


def from_post(ex: Extracted, raw_text: str, company_domain: Optional[str]) -> tuple[list[Candidate], list[str]]:
    """Addresses the post gives for applying (S1 already dropped any not written in the post).
    Returns (candidates, notes for the user)."""
    out: list[Candidate] = []
    notes: list[str] = []
    seen = set()
    poster_first = (ex.poster_name or "").split()[0].lower() if ex.poster_name else ""
    for r in ex.apply_routes:
        if r.type != "email" or not r.value:
            continue
        email = r.value.strip().lower()
        if email in seen or "@" not in email:
            continue
        seen.add(email)
        local, dom = email.split("@", 1)
        if OTHER_PURPOSE.match(local):
            notes.append("{} is published for another purpose, not hiring; not used".format(email))
            continue
        name, role = r.person_name, r.person_role
        if not name and len(poster_first) >= 3 and poster_first in local and ex.poster_type in ("founder", "employee"):
            name, role = ex.poster_name, ex.poster_role or ex.poster_type
        personal = dom in PERSONAL_DOMAINS
        if personal:
            if ex.poster_type in ("founder", "employee") and ex.company_name:
                notes.append("Contact is a personal mailbox ({}) from a named {} of {}".format(
                    dom, ex.poster_type, ex.company_name))
            else:
                notes.append("{} is a personal mailbox with no named company behind it; not used".format(email))
                continue
        matches = None if personal else _matches_domain(dom, company_domain)
        if matches is False:
            notes.append("Contact domain ({}) differs from the website domain ({})".format(dom, company_domain))
        out.append(Candidate(email=email, context="post_apply", tier=_tier(local, name, role), person_name=name,
                             person_role=role, evidence=_sentence_with(raw_text, email),
                             is_generic=not name and bool(HIRING_LOCAL.match(local) or GENERIC_LOCAL.match(local)),
                             domain_matches=matches, personal_mailbox=personal))
    return out, notes


# ------------------------------------------------------------------ the company's own site

def page_candidates(url: str, html: str, domain: str) -> list[Candidate]:
    """Role addresses on the company's own domain published on one of its pages. A hiring
    address (careers@, jobs@) counts wherever it appears on the site; a general inbox is only
    a last resort."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if EMAIL_RE.fullmatch(addr):
                ctx = a.find_parent(["p", "li", "div", "section", "footer"]) or a
                found.setdefault(addr, " ".join(ctx.get_text(" ", strip=True).split())[:300])
    text = " ".join(soup.get_text(" ", strip=True).split())
    for m in EMAIL_RE.finditer(deobfuscate(text)):
        addr = m.group(0).lower().rstrip(".")
        found.setdefault(addr, text[max(0, m.start() - 120):m.end() + 120].strip())

    out = []
    for addr, evidence in found.items():
        local, dom = addr.split("@", 1)
        if not _matches_domain(dom, domain) or OTHER_PURPOSE.match(local):
            continue
        if HIRING_LOCAL.match(local):
            context, tier = "careers_page", TIER_HIRING_BOX
        elif GENERIC_LOCAL.match(local):
            context, tier = "site_generic", TIER_GENERIC_BOX
        else:
            continue                        # a person's address with no stated purpose
        if addr not in evidence.lower():         # a mailto link: its words, then the address
            evidence = "{} ({})".format(evidence, addr) if evidence else "{} (linked on {})".format(addr, url)
        out.append(Candidate(email=addr, context=context, tier=tier, source_url=url, evidence=evidence,
                             is_generic=True, domain_matches=True))
    return out


def careers_links(base_url: str, html: str, domain: str) -> list[str]:
    """Links from a page to the company's own careers or jobs pages (never another site)."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        label = "{} {}".format(a.get_text(" ", strip=True), a["href"])
        if not CAREERS_LINK.search(label):
            continue
        url = urljoin(base_url, a["href"].strip())
        host = (urlparse(url).hostname or "").lower()
        if urlparse(url).scheme in ("http", "https") and _matches_domain(host.removeprefix("www."), domain) \
                and url.split("#")[0] not in out:
            out.append(url.split("#")[0])
    return out[:MAX_CAREERS_PAGES]


def harvest_site(domain: str, fetch=None) -> list[Candidate]:
    """Hiring and general addresses on the company's homepage and the careers pages it links
    to. `fetch(url) -> (final_url, html) | None` defaults to the SSRF-safe fetcher, where the
    site's robots.txt allows."""
    if fetch is None:
        from ..sources.robots import allowed
        from .verify import fetch_html

        def fetch(url):
            return fetch_html(url) if allowed(url) else None
    home = None
    for start in ("https://" + domain, "https://www." + domain):
        home = fetch(start)
        if home:
            break
    if not home:
        return []
    by_email: dict[str, Candidate] = {}

    def add(cands: list[Candidate]) -> None:
        for c in cands:
            old = by_email.get(c.email)
            if old is None or c.sort_key() < old.sort_key():
                by_email[c.email] = c

    add(page_candidates(home[0], home[1], domain))
    for link in careers_links(home[0], home[1], domain):
        page = fetch(link)
        if page:
            add(page_candidates(page[0], page[1], domain))
    return sorted(by_email.values(), key=Candidate.sort_key)


def site_candidates(domain: str) -> list[Candidate]:
    """harvest_site, cached on the shared companies row for a month."""
    with system_tx() as conn:
        row = conn.execute("""select site_emails from companies where domain = %s
                              and site_emails_at > now() - make_interval(days => %s)""",
                           (domain, SITE_CACHE_DAYS)).fetchone()
    if row is not None:
        return [Candidate(**{**c, "id": None}) for c in row["site_emails"]]
    found = harvest_site(domain)
    keep = ("email", "context", "tier", "source_url", "evidence", "is_generic", "domain_matches")
    with system_tx() as conn:
        conn.execute("update companies set site_emails = %s, site_emails_at = now() where domain = %s",
                     (Jsonb([{k: getattr(c, k) for k in keep} for c in found]), domain))
    return found


# ------------------------------------------------------------------ choosing one

def choose(candidates: list[Candidate], has_portal: bool) -> Optional[Candidate]:
    """The address to write to, or None when the post's portal is the better route (or there is
    no route at all). A general inbox is used only when nothing better exists."""
    if not candidates:
        return None
    best = min(candidates, key=Candidate.sort_key)
    if has_portal and CONTEXT_RANK[best.context] > PORTAL_RANK:
        return None
    return best


def flag_for(c: Optional[Candidate]) -> Optional[str]:
    """The visible flag a weaker contact carries."""
    if c is None:
        return None
    if c.context == "site_generic":
        return "Only the company's general inbox ({}) is published; no hiring address".format(c.email)
    return None
