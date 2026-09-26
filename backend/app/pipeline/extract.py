"""S1: extract a pasted post into structured fields, then hold the model to the text."""
from __future__ import annotations

import re
from typing import Optional

from .. import llm
from . import prompts
from .schemas import Extracted

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PERSONAL_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com",
                    "hotmail.com", "live.com", "rediffmail.com", "icloud.com", "proton.me",
                    "protonmail.com", "zoho.com", "aol.com"}

_OBFUSCATIONS = [
    (re.compile(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", re.I), "@"),
    (re.compile(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", re.I), "."),
]


def deobfuscate(text: str) -> str:
    """'hr [at] acme [dot] com' -> 'hr@acme.com'. Rewriting a published address's
    punctuation is not guessing; completing or correcting one would be."""
    for rx, rep in _OBFUSCATIONS:
        text = rx.sub(rep, text)
    return text


def published_emails(raw_text: str) -> set[str]:
    return {m.group(0).lower().rstrip(".") for m in EMAIL_RE.finditer(deobfuscate(raw_text))}


def email_is_published(address: str, *sources: str) -> bool:
    """Principle 4: an address must appear verbatim in the post, the JD or the company's
    own site. Never pattern-inferred."""
    a = address.strip().lower()
    return any(a in published_emails(s or "") for s in sources)


def email_domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower()


def parse_age_hours(label: Optional[str]) -> Optional[float]:
    """'45m' 0.75, '3h' 3, '2d' 48, '1w' 168, '1mo' 720; also '3 hours ago', 'just now'."""
    if not label:
        return None
    s = label.strip().lower()
    if s in ("just now", "now", "moments ago"):
        return 0.0
    m = re.match(r"(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wk|weeks?|mo|months?|y|yr|years?)\b", s)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2)
    if unit.startswith("mo"):
        return n * 720
    if unit.startswith("m"):
        return n / 60
    if unit.startswith("h"):
        return n
    if unit.startswith("d"):
        return n * 24
    if unit.startswith("w"):
        return n * 168
    return n * 8760


def extract(raw_text: str, source_ref: Optional[str], ctx: llm.CallContext, log: bool = True) -> Extracted:
    volatile = "Source: {}\n\n<post>\n{}\n</post>".format(source_ref or "pasted by the user", raw_text)
    ex = llm.structured("s1_extract", Extracted, stable=[prompts.EXTRACT], volatile=volatile,
                        effort="low", max_tokens=4000, ctx=ctx, log=log)
    return enforce_text(ex, raw_text)


def enforce_text(ex: Extracted, raw_text: str) -> Extracted:
    """Drop any email route whose address is not written in the post itself. An address
    the model left out is not added back: not every address in a post is an apply route."""
    routes = []
    for r in ex.apply_routes:
        if r.type == "email":
            if not r.value or not email_is_published(r.value, raw_text):
                continue
            r = r.model_copy(update={"value": r.value.strip().lower()})
        routes.append(r)
    return ex.model_copy(update={"apply_routes": routes})
