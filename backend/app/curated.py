"""
Curated posts: hiring posts the founder, or the founder's own agent, collects for everyone
(docs/agent-intake.md, "Shared pool"). Unlike a paste or a person's own agent, they enter the
shared pool as public openings.

Each post is read once (opportunity.process: S1, S2, S4, contacts), then matched for every
person who targets that kind of role, code only. Letters are prepared for at most
LETTERS_PER_POST people, the best matches first (strong or good, and not already writing to that
company), so one poster never receives a pile of near-identical letters. Everyone else who suits
the post still sees it among their openings and can choose to prepare it.

The same post never enters the pool twice: post_key is its LinkedIn activity number when the link
has one, else its link without tracking, else a fingerprint of its text.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from . import taxonomy as tx
from .db import system_tx, user_tx
from .pipeline import match as match_mod
from .pipeline import opportunity

log = logging.getLogger("curated")

LETTERS_PER_POST = 3
# urn:li:activity:7381..., /posts/name_slug-activity-7381...-AbCd, urn:li:ugcPost:7381..., share:7381...
LI_POST_ID = re.compile(r"(?:activity|ugcPost|share)(?::|-|%3A)(\d{15,22})", re.I)


def canonical_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    p = urlsplit(url.strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return urlunsplit((p.scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", ""))


def text_fingerprint(text: str) -> str:
    """The same post copied twice: case, spacing, links, "...see more" and hashtags aside."""
    t = text.lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"(…|\.\.\.)\s*(see more|more)\b", " ", t)
    t = re.sub(r"#\w+", " ", t)
    t = re.sub(r"[^\w@.]+", " ", t)
    return hashlib.sha256(re.sub(r"\s+", " ", t).strip().encode()).hexdigest()


def post_key(url: Optional[str], text: str) -> str:
    if url:
        m = LI_POST_ID.search(url)
        if m:
            return "li:" + m.group(1)
        c = canonical_url(url)
        if c:
            return "url:" + hashlib.sha256(c.encode()).hexdigest()[:32]
    return "text:" + text_fingerprint(text)[:32]


def candidates(family: str) -> list[str]:
    """Everyone done with sign-up who targets this kind of role or a neighbour of it."""
    with system_tx() as conn:
        rows = conn.execute("""select p.user_id::text, p.target_families from preferences p join profiles pr using (user_id)
                               where pr.onboarding_step = 'done'""").fetchall()
    return [r["user_id"] for r in rows
            if any(family in tx.family_with_neighbours(t) for t in (r["target_families"] or []))]


def fan_out(job_id: str, family: str, limit: int = LETTERS_PER_POST) -> dict:
    """Match the post for everyone it may suit and prepare letters for the best few."""
    from .pipeline.run import queue_prepare
    scored = []
    for uid in candidates(family):
        with user_tx(uid) as conn:
            seeker = match_mod.load_seeker(conn)
            found = match_mod.load_openings(conn, [job_id])
            if not found:
                continue
            m = match_mod.evaluate(seeker, found[0])
            if m.decision != "keep":
                continue
            match_id = match_mod.save(conn, uid, job_id, m, False)
        scored.append((m.score or 0, m.bucket, uid, match_id))
    scored.sort(reverse=True)
    picked = [(uid, mid) for score, bucket, uid, mid in scored if bucket in ("strong", "good")][:limit]
    for uid, mid in picked:
        queue_prepare(uid, mid)
    return {"matched": len(scored), "letters": len(picked)}


def process(job_id: str) -> dict:
    """Read the post once, then fan it out."""
    r = opportunity.process(job_id)
    with system_tx() as conn:
        conn.execute("update jobs set status = 'done', error = null where id = %s", (job_id,))
    if r.screen.decision != "keep":
        return {"decision": "drop", "reasons": r.screen.reasons}
    out = fan_out(job_id, opportunity.family_of(r.ex))
    log.info("curated %s: %s", job_id, out)
    return {"decision": "keep", **out}


def fail(job_id: str, message: str) -> None:
    with system_tx() as conn:
        conn.execute("update jobs set status = 'failed', error = %s where id = %s", (message[:500], job_id))
