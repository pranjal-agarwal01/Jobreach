"""Respect a site's robots.txt before reading its pages automatically. No robots.txt (or one we
cannot read) means the site sets no rule. Answers are cached per host for a few hours."""
from __future__ import annotations

import time
from typing import Callable, Optional
from urllib import robotparser
from urllib.parse import urlparse

from . import USER_AGENT

TTL = 6 * 3600
_CACHE: dict[str, tuple[float, Optional[robotparser.RobotFileParser]]] = {}


def _fetch_text(url: str):
    from ..pipeline.verify import fetch_html
    return fetch_html(url, accept=("text/plain",))


def allowed(url: str, fetch_text: Optional[Callable] = None) -> bool:
    p = urlparse(url)
    host = "{}://{}".format(p.scheme, p.netloc)
    hit = _CACHE.get(host)
    if hit is None or time.time() - hit[0] > TTL:
        rp = None
        got = (fetch_text or _fetch_text)(host + "/robots.txt")
        if got:
            rp = robotparser.RobotFileParser()
            rp.parse(got[1].splitlines())
        _CACHE[host] = hit = (time.time(), rp)
    return hit[1] is None or hit[1].can_fetch(USER_AGENT, url)
