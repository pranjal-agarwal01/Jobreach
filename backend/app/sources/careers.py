"""
A company's own site: its homepage and the careers pages it links to. Read for three things,
in one pass:

  - the job board it uses (a link to Greenhouse, Lever or Ashby), which the pool then polls;
  - openings listed on the page in the standard JobPosting format (schema.org, the markup
    search engines read), each one a posting;
  - hiring addresses (careers@, jobs@), for the contact step.

Only the company's own pages, only public ones, and only where its robots.txt allows.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from bs4 import BeautifulSoup

from ..pipeline import contacts as ct
from . import Posting, html_to_text, robots

BOARD_LINKS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)", re.I)),
]
NOT_TOKENS = {"embed", "api", "v0", "v1", "jobs", "job_board", "static", "assets", "js", "css"}


@dataclass
class SiteScan:
    boards: list[tuple[str, str]] = field(default_factory=list)          # (source, token)
    postings: list[Posting] = field(default_factory=list)
    contacts: list[ct.Candidate] = field(default_factory=list)
    pages: int = 0


def board_links(html: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for source, rx in BOARD_LINKS:
        for m in rx.finditer(html):
            token = m.group(1).strip(".").lower()
            if token and token not in NOT_TOKENS and (source, token) not in out:
                out.append((source, token))
    return out


def _nodes(data):
    """Every dict in a JSON-LD blob (lists and @graph included)."""
    if isinstance(data, list):
        for x in data:
            yield from _nodes(x)
    elif isinstance(data, dict):
        yield data
        for k in ("@graph", "itemListElement", "item"):
            if k in data:
                yield from _nodes(data[k])


def _text(v) -> str:
    if isinstance(v, dict):
        return " ".join(_text(x) for x in v.values() if isinstance(x, (str, dict, list)))
    if isinstance(v, list):
        return "; ".join(_text(x) for x in v)
    return str(v or "")


def job_postings(url: str, html: str, company: Optional[str], domain: Optional[str]) -> list[Posting]:
    """Openings marked up as schema.org JobPosting on one page."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "null")
        except (ValueError, TypeError):
            continue
        for n in _nodes(data):
            types = n.get("@type")
            if "JobPosting" not in (types if isinstance(types, list) else [types]):
                continue
            until = n.get("validThrough")
            if until:
                try:
                    if datetime.fromisoformat(str(until).replace("Z", "+00:00")).timestamp() < time.time():
                        continue
                except ValueError:
                    pass
            ident = n.get("identifier")
            ident = ident.get("value") if isinstance(ident, dict) else ident
            link = n.get("url") or url
            title = (n.get("title") or "").strip()
            if not title:
                continue
            posted = None
            try:
                posted = datetime.fromisoformat(str(n.get("datePosted")).replace("Z", "+00:00")) if n.get("datePosted") else None
            except ValueError:
                pass
            remote = str(n.get("jobLocationType") or "").upper() == "TELECOMMUTE"
            org = n.get("hiringOrganization")
            out.append(Posting(
                source="careers", source_job_id=str(ident or "{}#{}".format(link, title))[:300], title=title,
                text=html_to_text(n.get("description")), company_name=(org.get("name") if isinstance(org, dict) else None) or company,
                company_domain=domain, location=_text(n.get("jobLocation"))[:300], remote=remote or None,
                employment=_text(n.get("employmentType")) or None, posted_at=posted, url=link, apply_url=link))
    return out


def scan(domain: str, company: Optional[str], fetch: Optional[Callable] = None,
         fetch_text: Optional[Callable] = None) -> SiteScan:
    """Read the homepage and the careers pages it links to (at most two), where robots.txt
    allows. fetch(url) -> (final_url, html) | None; fetch_text reads robots.txt."""
    from ..pipeline import verify
    fetch = fetch or verify.fetch_html
    out = SiteScan()
    home = None
    for start in ("https://" + domain, "https://www." + domain):
        if robots.allowed(start, fetch_text):
            home = fetch(start)
        if home:
            break
    if not home:
        return out
    pages = [home] + [pg for link in ct.careers_links(home[0], home[1], domain)
                      if robots.allowed(link, fetch_text) and (pg := fetch(link))]
    seen_contacts: dict[str, ct.Candidate] = {}
    for page_url, html in pages:
        out.pages += 1
        for b in board_links(html):
            if b not in out.boards:
                out.boards.append(b)
        out.postings += job_postings(page_url, html, company, domain)
        for c in ct.page_candidates(page_url, html, domain):
            if c.email not in seen_contacts or c.sort_key() < seen_contacts[c.email].sort_key():
                seen_contacts[c.email] = c
    out.contacts = sorted(seen_contacts.values(), key=ct.Candidate.sort_key)
    return out
