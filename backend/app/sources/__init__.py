"""
Where the shared pool's openings come from (docs/plan-global-pool.md, Phase 4). Every source is
public and needs no login: company job boards on Greenhouse, Lever and Ashby (APIs published
for exactly this), the Hacker News "Who is hiring" thread, and the job listings a company puts
on its own careers page. LinkedIn is never read (spec 11.1).

Each source turns its feed into Postings. Code decides which postings are worth reading
(pool.py: a watched kind of role, India or open to India) before any model sees one.
"""
from __future__ import annotations

import html as htmlmod
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

USER_AGENT = "Jobreach/0.1 (company check and public job listings)"   # as verify.USER_AGENT
MAX_TEXT = 8000

INDIA_PLACES = re.compile(
    r"\b(india|indian|bharat|bengaluru|bangalore|mumbai|bombay|pune|hyderabad|chennai|madras|delhi|new delhi|ncr|"
    r"gurgaon|gurugram|noida|kolkata|calcutta|ahmedabad|jaipur|kochi|cochin|coimbatore|indore|chandigarh|"
    r"thiruvananthapuram|trivandrum|mysuru|mysore|bhubaneswar|nagpur|surat|vadodara|lucknow|goa|visakhapatnam|"
    r"vizag|mangaluru|mangalore|nashik|bhopal|kanpur|ranchi|guwahati)\b", re.I)
OPEN_WORLD = re.compile(r"\b(anywhere|worldwide|world-wide|global(ly)?|international|apac|asia|any\s+time\s*zone|"
                        r"all\s+locations|work\s+from\s+anywhere)\b", re.I)
REMOTE_WORD = re.compile(r"\b(remote|wfh|work\s+from\s+home|distributed|telecommute)\b", re.I)
FILLER = re.compile(r"\b(remote|wfh|work\s+from\s+home|distributed|telecommute|first|friendly|only|ok|"
                    r"possible|available|hybrid|onsite|on-site|in|office|or|and|the|role|position)\b", re.I)


@dataclass
class Posting:
    source: str                      # greenhouse | lever | ashby | hn | careers
    source_job_id: str
    title: str
    text: str                        # the description, as plain text
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    location: str = ""
    country: Optional[str] = None    # when the feed gives one ("IN", "India")
    remote: Optional[bool] = None
    employment: Optional[str] = None  # as the feed says it ("Intern", "Full Time Employee")
    posted_at: Optional[datetime] = None
    url: Optional[str] = None        # the posting's own page
    apply_url: Optional[str] = None

    def raw_text(self) -> str:
        """What S1 reads: the feed's structured facts as a short header, then the description,
        so a board posting reads like a pasted one."""
        who = self.company_name or ""
        if self.company_domain:
            who = "{} ({})".format(who, self.company_domain) if who else self.company_domain
        head = [self.title, who,
                "Location: {}{}{}".format(self.location or "not stated",
                                          " ({})".format(self.country) if self.country else "",
                                          ", remote" if self.remote else ""),
                "Employment: {}".format(self.employment) if self.employment else "",
                "Apply: {}".format(self.apply_url or self.url) if (self.apply_url or self.url) else ""]
        return "\n".join(x for x in head if x) + "\n\n" + self.text[:MAX_TEXT]


def html_to_text(fragment: Optional[str]) -> str:
    """Plain text from a feed's HTML (Greenhouse escapes its HTML once more)."""
    if not fragment:
        return ""
    s = fragment
    if "&lt;" in s and "<" not in s:
        s = htmlmod.unescape(s)
    soup = BeautifulSoup(s, "html.parser")
    for br in soup.find_all(["br"]):
        br.replace_with("\n")
    for block in soup.find_all(["p", "li", "div", "h1", "h2", "h3", "h4", "tr"]):
        block.insert_after("\n")
    for li in soup.find_all("li"):
        li.insert_before("- ")
    text = soup.get_text("")
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", "\n".join(line.strip() for line in text.splitlines())).strip()


def india_or_open(location: str, remote: Optional[bool] = None, country: Optional[str] = None) -> bool:
    """Is this posting in India, or remote with no region that shuts India out? Code only, before
    any model call. 'Bengaluru; San Francisco' is in; 'Remote - US' and 'London' are out."""
    loc = (location or "").strip()
    if (country or "").upper() in ("IN", "IND", "INDIA") or INDIA_PLACES.search(loc):
        return True
    if not (remote or REMOTE_WORD.search(loc)):
        return False
    if OPEN_WORLD.search(loc):
        return True
    # Only the parts that speak of remote work can restrict it ("Acme | Engineer | Remote (US)").
    parts = [x for x in re.split(r"[|;\n]", loc) if REMOTE_WORD.search(x)] or [loc]
    rest = [re.sub(r"[^a-z]+", " ", FILLER.sub(" ", x.lower())).strip() for x in parts]
    return all(r == "" for r in rest)    # remote, with no region named
