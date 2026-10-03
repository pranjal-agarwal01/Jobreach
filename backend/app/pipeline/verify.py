"""
S4: is the company real? DNS (A/AAAA), MX, the homepage, and a model summary of what the
business actually is. Cached per domain for 30 days in the shared companies table.

No LinkedIn access of any kind (spec 11.1): the user gets a search link to check the
company page themselves. No SMTP mailbox probing: it is unreliable and harms sender
reputation, so bounces are recorded as a normal cost instead.

The homepage fetch takes a domain from untrusted pasted text, so it only connects to
public addresses on ports 80/443 and re-checks every redirect hop.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus, urlparse

import dns.exception
import dns.resolver
import httpx
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from .. import llm
from ..db import system_tx
from . import prompts
from .schemas import CompanySummary, Extracted

CACHE_DAYS = 30
FETCH_TIMEOUT = 8.0
MAX_BYTES = 600_000
# One name for every page Jobreach reads, so a site's robots.txt can address it.
USER_AGENT = "Jobreach/0.1 (company check and public job listings)"
HOST_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


@dataclass
class Verification:
    company_id: Optional[str]
    verification: str                 # pass | flag | fail
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    linkedin_check_url: Optional[str] = None


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime = 5.0
    return r


def public_ips(host: str) -> list[str]:
    out = []
    for rtype in ("A", "AAAA"):
        try:
            for rr in _resolver().resolve(host, rtype):
                out.append(rr.to_text())
        except (dns.exception.DNSException, socket.error):
            continue
    return [ip for ip in out if ipaddress.ip_address(ip).is_global]


def has_mx(domain: str) -> bool:
    try:
        return len(_resolver().resolve(domain, "MX")) > 0
    except dns.exception.DNSException:
        return False


def _safe_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    if p.port not in (None, 80, 443):
        return False
    host = p.hostname.lower()
    try:
        ipaddress.ip_address(host)
        return False          # literal IPs are never a company homepage
    except ValueError:
        pass
    return bool(HOST_RE.match(host)) and bool(public_ips(host))


def fetch_homepage(domain: str) -> Optional[str]:
    """Return visible text of the homepage, or None. Manual redirects, each re-checked."""
    for start in ("https://" + domain, "https://www." + domain, "http://" + domain):
        text = fetch_page(start)
        if text is not None:
            return text
    return None


def fetch_page(url: str) -> Optional[str]:
    """Visible text of one public web page, or None."""
    got = fetch_html(url)
    return _visible_text(got[1]) if got else None


def fetch_html(url: str, accept: tuple[str, ...] = ("html",)) -> Optional[tuple[str, str]]:
    """(final url, body) of one public web page, or None. Only public addresses on ports
    80/443; every redirect hop is re-checked. accept: content types to read ("html", or
    "text/plain" for robots.txt)."""
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=False,
                          headers={"User-Agent": USER_AGENT}) as c:
            for _ in range(4):
                if not _safe_url(url):
                    return None
                with c.stream("GET", url) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        url = str(httpx.URL(url).join(r.headers["location"]))
                        continue
                    ctype = r.headers.get("content-type", accept[0])
                    if r.status_code >= 400 or not any(t in ctype for t in accept):
                        return None
                    body = b""
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    return url, body.decode(r.encoding or "utf-8", "replace")
    except httpx.HTTPError:
        return None
    return None


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    desc = desc.get("content", "") if desc else ""
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return "Title: {}\nDescription: {}\n\n{}".format(title, desc, text[:5000])


def linkedin_search_url(name: Optional[str]) -> Optional[str]:
    return ("https://www.linkedin.com/search/results/companies/?keywords=" + quote_plus(name)
            if name else None)


def verify(ex: Extracted, domain: Optional[str], ctx: llm.CallContext) -> Verification:
    name = ex.company_name or domain or "unknown"
    li = linkedin_search_url(ex.company_name)
    if not domain:
        if not ex.company_name:
            return Verification(None, "fail", ["No company domain and no company name in the post"],
                                linkedin_check_url=li)
        cid = _upsert(name, None, {"verification": "flag", "flags": ["No website in the post"]})
        return Verification(cid, "flag", flags=["No website in the post; check the company yourself"],
                            linkedin_check_url=li)

    cached = _cached(domain)
    if cached is None:
        cached = _check(name, domain, ex, ctx)
    v = Verification(cached["id"], cached["verification"], linkedin_check_url=li)
    flags = cached.get("flags") or []
    if v.verification == "fail":
        v.reasons.extend(flags or ["Company check failed"])
    else:
        v.flags.extend(flags)
    return v


def _cached(domain: str) -> Optional[dict]:
    with system_tx() as conn:
        return conn.execute(
            """select id::text, verification, flags from companies
               where domain = %s and checked_at > now() - make_interval(days => %s)""",
            (domain, CACHE_DAYS)).fetchone()


def _check(name: str, domain: str, ex: Extracted, ctx: llm.CallContext) -> dict:
    dns_ok = bool(HOST_RE.match(domain)) and bool(public_ips(domain))
    mx_ok = has_mx(domain) if dns_ok or HOST_RE.match(domain) else False
    text = fetch_homepage(domain) if dns_ok else None
    summary: Optional[CompanySummary] = None
    if text:
        volatile = "Company named in the post: {}\nRole in the post: {}\n\n<homepage>\n{}\n</homepage>".format(
            ex.company_name, ex.title, text)
        summary = llm.structured("s4_company", CompanySummary, stable=[prompts.COMPANY],
                                 volatile=volatile, effort="low", max_tokens=1500,
                                 ctx=llm.CallContext(job_id=ctx.job_id))
    named_poster = ex.poster_type in ("founder", "employee") and bool(ex.poster_name)

    flags: list[str] = []
    if summary and (summary.is_intermediary or summary.business_type in ("staffing", "msp", "training", "placement")):
        result = "fail"
        flags.append("Business is {}: {}".format(summary.business_type, summary.summary))
    elif not dns_ok and not mx_ok:
        result = "fail"
        flags.append("Domain {} does not resolve and accepts no mail".format(domain))
    elif dns_ok and mx_ok and text and summary and summary.matches_post:
        result = "pass"
    elif mx_ok and named_poster:
        result = "flag"
        if not text:
            flags.append("Website {} is down or unreadable, but it accepts mail and the poster is named".format(domain))
        elif summary and not summary.matches_post:
            flags.append("Website does not obviously match the role: {}".format(summary.summary))
    else:
        result = "flag"
        if not mx_ok:
            flags.append("Domain {} has no mail server (MX); an email may bounce".format(domain))
        if not text:
            flags.append("Website {} is down or unreadable".format(domain))
        elif summary and not summary.matches_post:
            flags.append("Website does not obviously match the role: {}".format(summary.summary))

    row = {
        "dns_ok": dns_ok, "mx_ok": mx_ok, "homepage_ok": bool(text),
        "business_summary": summary.summary if summary else None,
        "business_type": summary.business_type if summary else None,
        "is_intermediary": summary.is_intermediary if summary else None,
        "size_band": summary.size_hint if summary else None,
        "verification": result, "flags": flags,
    }
    cid = _upsert(name, domain, row)
    return {"id": cid, "verification": result, "flags": flags}


def _upsert(name: str, domain: Optional[str], row: dict) -> str:
    cols = ["dns_ok", "mx_ok", "homepage_ok", "business_summary", "business_type",
            "is_intermediary", "size_band", "verification", "flags"]
    vals = [Jsonb(row.get(c) or []) if c == "flags" else row.get(c) for c in cols]
    with system_tx() as conn:
        if domain:
            r = conn.execute(
                """insert into companies (name, domain, {cols}, checked_at)
                   values (%s, %s, {ph}, now())
                   on conflict (domain) do update set name = excluded.name, {upd}, checked_at = now()
                   returning id::text""".format(
                    cols=", ".join(cols), ph=", ".join(["%s"] * len(cols)),
                    upd=", ".join("{0} = excluded.{0}".format(c) for c in cols)),
                [name, domain] + vals).fetchone()
        else:
            r = conn.execute(
                """insert into companies (name, {cols}, checked_at) values (%s, {ph}, now())
                   returning id::text""".format(cols=", ".join(cols), ph=", ".join(["%s"] * len(cols))),
                [name] + vals).fetchone()
    return r["id"]
