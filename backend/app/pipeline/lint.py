"""
S8: lint a draft in code. Any failure blocks the draft from being marked ready
(spec 5.8). The signature block is the user's own text, so it is exempt from the body
checks and is instead checked for being present verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional

from .extract import published_emails

EM_DASH = "—"
LENGTHS = {"recruiter": (90, 110), "hiring_manager": (100, 130), "founder": (100, 130),
           "referral": (150, 200)}
EMAIL_RE = re.compile(r"[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://\S+|www\.\S+|\b[\w\-]+\.(?:com|in|io|ai|dev|org|net|co|app|me|xyz)(?:/\S*)?\b",
                    re.I)
PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|\[(?:link|company|name|role|your[^\]]*|insert[^\]]*)\]|\bTODO\b|"
                            r"\bPASTE\b|\bXXX\b|lorem ipsum|<[A-Z][a-z]+ ?[A-Z]?[a-z]*>", re.I)
NUM_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(\s?[kK]\b)?")
# A letter that inventories what the seeker lacks reads as a reason not to reply (rule 10).
LACKS_RE = re.compile(r"\bI\s+lack\b|\blacking\b|\b(?:is|are|isn['’]t|aren['’]t|not)\s+documented\b|"
                      r"\bundocumented\b|\bunconfirmed\b|\bnot\s+a\s+graduate\b", re.I)
DURATION_RE = re.compile(r"\b\d+\s*(?:-|to|–)\s*\d+\s*(?:months?|weeks?)\b|\b\d+\s*(?:months?|weeks?)\b", re.I)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def as_json(self):
        return {"check": self.name, "ok": self.ok, "detail": self.detail}


class _Balance(HTMLParser):
    VOID = {"br", "hr", "img", "meta", "link", "input"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected </{}>".format(tag))
        else:
            self.stack.pop()


def _numbers(text: str) -> set[str]:
    out = set()
    for m in NUM_RE.finditer(text):
        n = m.group(1).replace(",", "").rstrip(".")
        if not n:
            continue
        out.add(n)
        if m.group(2):                           # "10k" -> also 10000
            try:
                out.add(str(int(float(n) * 1000)))
            except ValueError:
                pass
    return out


def lint(*, subject: str, body_text: str, html: str, to_addr: Optional[str], raw_post: str,
         fact_texts: list[str], allowed_extra: list[str], recipient_type: str,
         roles_mentioned: list[str], stipend_rule: str, floor: Optional[int],
         duration_flex: str, post_start_text: Optional[str], user_start: str,
         signature_text: Optional[str], plain_full: str,
         published_in: Optional[list[str]] = None) -> list[Check]:
    """body_text: the email without the signature. plain_full: the full plain-text email.
    published_in: the texts the recipient's address may be written in (default: the post)."""
    checks: list[Check] = []
    add = lambda name, ok, detail="": checks.append(Check(name, ok, detail))  # noqa: E731

    dash_hits = (subject + body_text).count(EM_DASH)
    add("no_em_dash", dash_hits == 0, "{} em dash(es)".format(dash_hits) if dash_hits else "")

    no_emails = EMAIL_RE.sub(" ", body_text)
    urls = URL_RE.findall(no_emails)
    add("no_bare_urls", not urls, ", ".join(urls[:3]))

    bal = _Balance()
    bal.feed(html)
    bal.close()
    escaped = "&lt;" in html and re.search(r"&lt;/?(p|br|a|ul|li|div)", html)
    ok_html = not bal.errors and not bal.stack and not escaped
    add("html_well_formed", ok_html, "; ".join(bal.errors + (["unclosed " + ", ".join(bal.stack)] if bal.stack else [])
                                               + (["escaped tags"] if escaped else [])))

    ph = PLACEHOLDER_RE.findall(subject + "\n" + body_text)
    add("no_placeholders", not ph, ", ".join(ph[:3]))

    if to_addr:
        sources = published_in if published_in is not None else [raw_post]
        ok = any(to_addr.lower() in published_emails(t or "") for t in sources)
        add("recipient_published", ok,
            "" if ok else "{} is not written in the post or on the company's site".format(to_addr))

    allowed = set()
    for t in fact_texts + [raw_post] + allowed_extra:
        allowed |= _numbers(t)
    unknown = sorted(n for n in _numbers(subject + " " + body_text) - allowed)
    add("numbers_backed", not unknown, "not in fact bank or post: " + ", ".join(unknown) if unknown else "")

    lo, hi = LENGTHS.get(recipient_type, (90, 130))
    words = len(body_text.split())
    add("length", lo <= words <= hi, "{} words; {} range is {}-{}".format(words, recipient_type, lo, hi))

    add("resume_attached", "resume is attached" in body_text.lower())

    lacks = [m.group(0) for m in LACKS_RE.finditer(body_text)]
    add("strengths_not_lacks", not lacks,
        "lists what the seeker lacks ({}); say what they bring, at most one hard gap".format(", ".join(lacks[:3]))
        if lacks else "")

    add("one_role", len(roles_mentioned) == 1,
        "mentions {}".format(", ".join(roles_mentioned)) if len(roles_mentioned) != 1 else "")

    durations = [d for d in DURATION_RE.findall(body_text) if d.lower() not in duration_flex.lower()]
    narrowed = list(durations)
    if post_start_text and post_start_text.strip() and post_start_text.lower() in body_text.lower() \
            and post_start_text.lower() not in user_start.lower():
        narrowed.append("start: " + post_start_text)
    add("availability_not_narrowed", not narrowed, ", ".join(narrowed))

    low = body_text.lower()
    if stipend_rule == "ask":
        ok = "stipend" in low and "?" in body_text
        add("stipend_rule", ok, "" if ok else "post states no stipend: the email must ask")
    elif stipend_rule == "state_floor":
        ok = floor is not None and str(floor) in _numbers(body_text)
        add("stipend_rule", ok, "" if ok else "unpaid remote post: the email must state the floor")

    if signature_text:
        ok = plain_full.rstrip().endswith(signature_text.strip())
        add("signature_verbatim", ok, "" if ok else "signature missing or altered")
    return checks


def passed(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)
