"""
Discovery: new companies for the pool, found without anyone searching for them.

  - Y Combinator's public company directory (the open daily copy at yc-oss.github.io): companies
    marked as hiring that are in India or fully remote.
  - Startup funding news (Inc42, YourStory, The Economic Times, TechCrunch): a company that has
    just raised money is about to hire. The cheap model lists the startups each funding article
    reports; the investors and other names in it are left out.

A company found this way needs a website. The directory gives one; an article sometimes links
one; otherwise a few likely addresses are tried (name.com, name.in, ...). Whichever it is, the
same check as a pasted post's company decides (S4: DNS, mail, the homepage and what the business
is), and a site is kept only when its homepage is that company's own. A kept company joins the
companies the pool scans (pool.scan_company): its careers page, the job board it uses and its
hiring address.

Only public feeds and pages, only where robots.txt allows, nothing republished: an article is
read for company names and kept only as a link.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from . import llm
from .db import system_tx
from .pipeline import prompts
from .pipeline import verify
from .pipeline.schemas import FundingNews
from .sources import robots

log = logging.getLogger("discover")

YC_URL = "https://yc-oss.github.io/api/companies/hiring.json"
YC_REGIONS = {"India", "South Asia", "Fully Remote"}
FEEDS = {
    "inc42": "https://inc42.com/buzz/feed/",
    "yourstory": "https://yourstory.com/feed",
    "et_funding": "https://economictimes.indiatimes.com/tech/funding/rssfeeds/78570540.cms",
    "techcrunch": "https://techcrunch.com/category/fundraising/feed/",
}
FEED_LABEL = {"inc42": "Inc42", "yourstory": "YourStory", "et_funding": "The Economic Times",
              "techcrunch": "TechCrunch"}
# Headlines worth reading: a round, an amount, a raise.
FUNDING_TITLE = re.compile(r"\b(?:rais(?:e|es|ed|ing)|fund(?:ing|raise)|secur(?:es|ed)|bags|nets|series\s+[a-f]\b|"
                           r"seed|pre-seed|pre-series|round|crore|cr\b|mn\b|million|billion)", re.I)
YC_PER_TASK = 50            # directory companies queued per task (each then checked in its own task)
ARTICLES_PER_TASK = 6       # funding articles read per task
GUESS_SUFFIXES = (".com", ".in", ".ai", ".io", ".co", ".co.in", ".app", ".tech")
NAME_DROP = re.compile(r"\b(?:pvt|private|ltd|limited|llp|inc|technologies|technology|tech|labs?|"
                       r"solutions|india|software|ai|hq)\b\.?", re.I)
NOT_COMPANY_HOSTS = ("linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com",
                     "crunchbase.com", "tracxn.com", "google.com", "apple.com", "wikipedia.org", "t.co",
                     "bit.ly", "whatsapp.com", "telegram.me", "t.me")


@dataclass
class Found:
    name: str
    about: str                       # what it does, from the source
    note: str                        # why now: "Raised a Series A of $5 Mn (Inc42)"
    url: Optional[str]               # the article or directory page
    via: str                         # 'yc' | 'funding_news'
    key: str                         # the item key in discovery_items
    website: Optional[str] = None


@dataclass
class Item:
    title: str
    link: str


# ------------------------------------------------------------------ reading the sources

def _get(url: str, timeout: float = 30.0) -> Optional[httpx.Response]:
    if not robots.allowed(url):
        return None
    try:
        r = httpx.get(url, headers={"User-Agent": verify.USER_AGENT}, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as e:
        log.warning("discover: %s: %s", url, e)
        return None
    return r if r.status_code == 200 else None


def yc_candidates(data: list[dict]) -> list[Found]:
    """Directory companies marked as hiring, still active, in India or fully remote, with a site."""
    out = []
    for c in data:
        regions = set(c.get("regions") or [])
        where = c.get("all_locations") or ""
        if not c.get("isHiring") or (c.get("status") or "Active") != "Active" or not c.get("website"):
            continue
        if not (regions & YC_REGIONS or "India" in where):
            continue
        place = where or ", ".join(sorted(regions & YC_REGIONS))
        out.append(Found(name=c["name"], about=c.get("one_liner") or c.get("industry") or "",
                         note="Y Combinator {}, hiring{}".format(c.get("batch") or "company",
                                                                 " ({})".format(place) if place else ""),
                         url=c.get("url"), via="yc", key=c.get("slug") or c["name"], website=c["website"]))
    return out


def feed_items(xml_text: str) -> list[Item]:
    """The items of an RSS feed. A feed that is not well-formed XML is read with a looser pattern."""
    items: list[Item] = []
    try:
        root = ET.fromstring(xml_text)
        for it in root.iter("item"):
            title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
            if title and link:
                items.append(Item(title=title, link=link))
        return items
    except ET.ParseError:
        pass
    for block in re.findall(r"<item\b.*?</item>", xml_text, re.S | re.I):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        lk = re.search(r"<link>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</link>", block, re.S)
        if t and lk:
            items.append(Item(title=BeautifulSoup(t.group(1), "html.parser").get_text().strip(), link=lk.group(1)))
    return items


def article_text_and_links(page_url: str, html: str) -> tuple[str, list[tuple[str, str]]]:
    """The article's words, and its links to other sites (text, href): a startup's own site is
    often among them."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    body = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", body.get_text(" ", strip=True))[:12000]
    own = (urlparse(page_url).hostname or "").removeprefix("www.")
    links, seen = [], set()
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        host = (urlparse(href).hostname or "").lower().removeprefix("www.")
        if not href.startswith("http") or not host or host.endswith(own) or own.endswith(host):
            continue
        if any(host == h or host.endswith("." + h) for h in NOT_COMPANY_HOSTS) or href in seen:
            continue
        seen.add(href)
        links.append((a.get_text(" ", strip=True)[:80], href))
    return text, links[:80]


def article_companies(item: Item, text: str, links: list[tuple[str, str]],
                      feed: str) -> list[Found]:
    """The startups a funding article reports, by the cheap model; a website only when it is one
    of the article's own links."""
    volatile = "Headline: {}\n\nLinks in the article:\n{}\n\n<article>\n{}\n</article>".format(
        item.title, "\n".join("- {} -> {}".format(t or "(no text)", h) for t, h in links) or "(none)", text)
    news = llm.structured("discover_news", FundingNews, stable=[prompts.DISCOVER_NEWS], volatile=volatile,
                          effort="low", max_tokens=2500, ctx=llm.CallContext())
    hrefs = {h for _, h in links}
    out = []
    for c in news.companies:
        if not c.name.strip():
            continue
        raised = " of ".join(x for x in (c.round, c.amount) if x)
        note = "Raised {} ({})".format(raised or "funding", FEED_LABEL.get(feed, feed))
        out.append(Found(name=c.name.strip(), about=c.what_it_does, note=note, url=item.link, via="funding_news",
                         key=item.link, website=c.website if c.website in hrefs else None))
    return out


# ------------------------------------------------------------------ finding the company's site

def domain_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    host = (urlparse(url if "//" in url else "https://" + url).hostname or "").lower().removeprefix("www.")
    return host if verify.HOST_RE.match(host) else None


def name_key(name: str) -> str:
    """"Seeds Fincap Pvt Ltd" -> "seedsfincap": how a company's name is usually written in its address."""
    return re.sub(r"[^a-z0-9]", "", NAME_DROP.sub(" ", name.lower())) or re.sub(r"[^a-z0-9]", "", name.lower())


def guesses(name: str) -> list[str]:
    key = name_key(name)
    return [key + s for s in GUESS_SUFFIXES] if len(key) >= 3 else []


def names_company(homepage_text: str, name: str) -> bool:
    """Does the homepage carry the company's name? A cheap first test before the model looks."""
    squashed = re.sub(r"[^a-z0-9]", "", homepage_text.lower())
    full = re.sub(r"[^a-z0-9]", "", name.lower())
    return bool(full) and (full in squashed or (len(name_key(name)) >= 4 and name_key(name) in squashed))


def register(f: Found, check: Optional[Callable] = None, fetch_home: Optional[Callable] = None,
             has_address: Optional[Callable] = None) -> Optional[str]:
    """Find the company's own site and keep the company, marked as discovered. Returns its id, or
    None when no site could be confirmed."""
    check = check or verify.check_discovered
    fetch_home = fetch_home or verify.fetch_homepage
    has_address = has_address or (lambda d: bool(verify.public_ips(d)))
    given = domain_of(f.website)
    candidates = [given] if given else guesses(f.name)
    for d in candidates:
        with system_tx() as conn:
            known = conn.execute("select id::text from companies where domain = %s", (d,)).fetchone()
        if known:
            _mark(known["id"], f)
            return known["id"]
        if not given and not has_address(d):
            continue
        home = fetch_home(d)
        if not home or (not given and not names_company(home, f.name)):
            continue
        res = check(f.name, d, f.about, homepage=home)
        if res:
            _mark(res["id"], f)
            return res["id"]
    return None


def _mark(company_id: str, f: Found) -> None:
    """Funding news is the newest reason to write, so it replaces an older note; the directory
    only fills an empty one."""
    with system_tx() as conn:
        if f.via == "funding_news":
            conn.execute("""update companies set discovered_via = 'funding_news', discovery_note = %s,
                                discovery_url = %s, discovered_at = coalesce(discovered_at, now()) where id = %s""",
                         (f.note, f.url, company_id))
        else:
            conn.execute("""update companies set discovered_via = coalesce(discovered_via, %s),
                                discovery_note = coalesce(discovery_note, %s), discovery_url = coalesce(discovery_url, %s),
                                discovered_at = coalesce(discovered_at, now()) where id = %s""",
                         (f.via, f.note, f.url, company_id))


def _seen(feed: str) -> set[str]:
    with system_tx() as conn:
        return {r["item_key"] for r in conn.execute("select item_key from discovery_items where feed = %s",
                                                    (feed,)).fetchall()}


def _remember(feed: str, key: str, title: str, added: int) -> None:
    with system_tx() as conn:
        conn.execute("""insert into discovery_items (feed, item_key, title, companies) values (%s, %s, %s, %s)
                        on conflict (feed, item_key) do update set companies = excluded.companies""",
                     (feed, key, title[:300], added))


def _continue(kind: str) -> None:
    from .worker import enqueue
    with system_tx() as conn:
        enqueue(conn, None, kind, {})


# ------------------------------------------------------------------ the tasks
#
# Each company is checked in its own small task (discover_company), so a weekly roundup of
# twenty startups never holds the worker while a person waits for their own letter: people's
# tasks always come first.

def _queue_companies(found: list[Found]) -> None:
    from dataclasses import asdict
    from .worker import enqueue
    with system_tx() as conn:
        for f in found:
            enqueue(conn, None, "discover_company", asdict(f))


def discover_company(payload: dict) -> Optional[str]:
    return register(Found(**payload))


def discover_yc(data: Optional[list[dict]] = None) -> dict:
    """Directory companies not yet looked at, YC_PER_TASK at a time; the rest in a continuation."""
    if data is None:
        r = _get(YC_URL, timeout=60)
        if r is None:
            return {"error": "directory unreachable"}
        data = r.json()
    found = yc_candidates(data)
    seen = _seen("yc")
    todo = [f for f in found if f.key not in seen][:YC_PER_TASK]
    _queue_companies(todo)
    for f in todo:
        _remember("yc", f.key, f.name, 1)
    left = max(0, len([f for f in found if f.key not in seen]) - len(todo))
    if left:
        _continue("discover_yc")
    return {"hiring_in_scope": len(found), "queued": len(todo), "left": left}


def discover_news(fetch_feed: Optional[Callable] = None, fetch_article: Optional[Callable] = None,
                  extract: Optional[Callable] = None) -> dict:
    """Funding headlines not yet read, ARTICLES_PER_TASK at a time across the feeds. Each article's
    startups are queued for checking."""
    fetch_feed = fetch_feed or (lambda url: (r.text if (r := _get(url)) is not None else None))
    fetch_article = fetch_article or (lambda url: verify.fetch_html(url) if robots.allowed(url) else None)
    extract = extract or article_companies
    budget, read, listed, more = ARTICLES_PER_TASK, 0, 0, False
    for feed, url in FEEDS.items():
        xml = fetch_feed(url)
        if not xml:
            continue
        seen = _seen(feed)
        fresh = [i for i in feed_items(xml) if FUNDING_TITLE.search(i.title) and i.link not in seen]
        for item in fresh:
            if budget <= 0:
                more = True
                break
            budget -= 1
            read += 1
            found: list[Found] = []
            got = fetch_article(item.link)
            if got:
                text, links = article_text_and_links(*got)
                try:
                    found = extract(item, text, links, feed)
                except Exception as e:          # one article must not stop the rest
                    log.warning("discover %s %s: %s", feed, item.link, e)
            _queue_companies(found)
            _remember(feed, item.link, item.title, len(found))
            listed += len(found)
    if more:
        _continue("discover_news")
    return {"articles": read, "companies_queued": listed, "more": more}
