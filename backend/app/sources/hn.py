"""
Hacker News "Ask HN: Who is hiring?", read through its public Algolia API. Each top-level reply
is one company's posting; by convention its first line is "Company | Role | Location | Remote".
A thread runs for a month, so a reply is treated like a board listing (valid for the month),
not like a social post that ages in hours.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Optional

import httpx

from . import USER_AGENT, Posting, html_to_text

SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
ITEM = "https://hn.algolia.com/api/v1/items/{}"


def _get(url: str, params: Optional[dict] = None):
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as c:
        r = c.get(url, params=params)
    r.raise_for_status()
    return r.json()


def latest_thread(get: Callable = _get) -> Optional[str]:
    hits = get(SEARCH, {"tags": "story,author_whoishiring", "hitsPerPage": 6}).get("hits") or []
    for h in hits:
        if "who is hiring" in (h.get("title") or "").lower():
            return str(h["objectID"])
    return None


def postings(thread_id: str, get: Callable = _get) -> list[Posting]:
    item = get(ITEM.format(thread_id), None)
    out = []
    for k in item.get("children") or []:
        if not k.get("text") or k.get("type") != "comment":
            continue
        text = html_to_text(k["text"])
        header = text.splitlines()[0].strip() if text else ""
        company = re.split(r"\s*[|(–—-]\s*", header, maxsplit=1)[0].strip() or None
        out.append(Posting(
            source="hn", source_job_id=str(k["id"]), title=header[:200], text=text, company_name=company,
            location=header, posted_at=datetime.fromisoformat(k["created_at"].replace("Z", "+00:00")),
            url="https://news.ycombinator.com/item?id={}".format(k["id"])))
    return out
