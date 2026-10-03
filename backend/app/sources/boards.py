"""
Public company job boards: Greenhouse, Lever and Ashby each publish a company's open roles as
JSON for anyone to read, which is what their own embeddable job boards use. One request per
board returns every opening the company has.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from . import USER_AGENT, Posting, html_to_text

TIMEOUT = 20.0
GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true"
LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{}?includeCompensation=true"
URLS = {"greenhouse": GREENHOUSE, "lever": LEVER, "ashby": ASHBY}


class BoardGone(RuntimeError):
    """The board no longer exists (404): stop polling it."""


def _get(url: str):
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as c:
        r = c.get(url)
    if r.status_code == 404:
        raise BoardGone(url)
    r.raise_for_status()
    return r.json()


def _when(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):                       # Lever: milliseconds
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def greenhouse(token: str, data: dict, company: Optional[str], domain: Optional[str]) -> list[Posting]:
    out = []
    for j in data.get("jobs") or []:
        loc = (j.get("location") or {}).get("name") or ""
        out.append(Posting(
            source="greenhouse", source_job_id=str(j["id"]), title=(j.get("title") or "").strip(),
            text=html_to_text(j.get("content")), company_name=j.get("company_name") or company, company_domain=domain,
            location=loc, remote=None, employment=None,
            posted_at=_when(j.get("first_published") or j.get("updated_at")),
            url=j.get("absolute_url"), apply_url=j.get("absolute_url")))
    return out


def lever(token: str, data: list, company: Optional[str], domain: Optional[str]) -> list[Posting]:
    out = []
    for j in data or []:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
        parts = [j.get("openingPlain") or "", j.get("descriptionBodyPlain") or j.get("descriptionPlain") or ""]
        for lst in j.get("lists") or []:
            parts.append("{}\n{}".format(lst.get("text") or "", html_to_text(lst.get("content"))))
        parts.append(j.get("additionalPlain") or "")
        wp = (j.get("workplaceType") or "").lower()
        out.append(Posting(
            source="lever", source_job_id=str(j["id"]), title=(j.get("text") or "").strip(),
            text="\n\n".join(p.strip() for p in parts if p and p.strip()), company_name=company, company_domain=domain,
            location="; ".join(locs), country=j.get("country"),
            remote=True if wp == "remote" else (False if wp in ("onsite", "on-site", "hybrid") else None),
            employment=cat.get("commitment"), posted_at=_when(j.get("createdAt")),
            url=j.get("hostedUrl"), apply_url=j.get("applyUrl") or j.get("hostedUrl")))
    return out


def ashby(token: str, data: dict, company: Optional[str], domain: Optional[str]) -> list[Posting]:
    out = []
    for j in data.get("jobs") or []:
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location") or "" for s in j.get("secondaryLocations") or []
                                            if isinstance(s, dict)]
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        out.append(Posting(
            source="ashby", source_job_id=str(j["id"]), title=(j.get("title") or "").strip(),
            text=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")), company_name=company,
            company_domain=domain, location="; ".join(x for x in locs if x), country=country,
            remote=bool(j.get("isRemote")) or (j.get("workplaceType") or "").lower() == "remote",
            employment=j.get("employmentType"), posted_at=_when(j.get("publishedAt")),
            url=j.get("jobUrl"), apply_url=j.get("applyUrl") or j.get("jobUrl")))
    return out


PARSERS: dict[str, Callable] = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def fetch(source: str, token: str, company: Optional[str] = None, domain: Optional[str] = None,
          get: Callable = _get) -> list[Posting]:
    """Every listed opening on one board."""
    return PARSERS[source](token, get(URLS[source].format(token)), company, domain)


def probe(token: str, get: Callable = _get) -> list[tuple[str, int]]:
    """Which providers have a live board under this name: [(source, openings)]."""
    found = []
    for source, url in URLS.items():
        try:
            data = get(url.format(token))
        except (BoardGone, httpx.HTTPError, ValueError):
            continue
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if isinstance(jobs, list):
            found.append((source, len(jobs)))
    return found
