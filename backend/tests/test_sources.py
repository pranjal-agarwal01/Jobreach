"""The pool's sources: public job-board feeds, the Hacker News thread and careers pages, parsed
from made-up data in each feed's real shape. No network."""
from datetime import datetime, timezone

import pytest

from app.sources import Posting, boards, careers, hn, html_to_text, india_or_open

GREENHOUSE = {"jobs": [{
    "id": 101, "title": "Backend Engineer", "company_name": "Kitebird", "absolute_url": "https://job-boards.greenhouse.io/kitebird/jobs/101",
    "location": {"name": "Bengaluru, India"}, "first_published": "2026-09-30T10:00:00-04:00", "updated_at": "2026-10-01T10:00:00-04:00",
    "content": "&lt;p&gt;Build our &lt;strong&gt;Python&lt;/strong&gt; APIs.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;FastAPI&lt;/li&gt;&lt;li&gt;PostgreSQL&lt;/li&gt;&lt;/ul&gt;"}]}
LEVER = [{
    "id": "lv-1", "text": "Frontend Developer Intern", "categories": {"commitment": "Intern", "location": "Pune", "allLocations": ["Pune"]},
    "createdAt": 1759300000000, "workplaceType": "hybrid", "country": "IN", "hostedUrl": "https://jobs.lever.co/kite/lv-1",
    "applyUrl": "https://jobs.lever.co/kite/lv-1/apply", "openingPlain": "Join us.", "descriptionPlain": "Work on React.",
    "lists": [{"text": "You have", "content": "<li>React</li><li>TypeScript</li>"}], "additionalPlain": "Stipend Rs 20,000"}]
ASHBY = {"jobs": [
    {"id": "as-1", "title": "Data Analyst", "isListed": True, "isRemote": True, "workplaceType": "Remote", "location": "India",
     "secondaryLocations": [], "employmentType": "FullTime", "publishedAt": "2026-09-29T08:00:00+00:00",
     "jobUrl": "https://jobs.ashbyhq.com/kite/as-1", "applyUrl": "https://jobs.ashbyhq.com/kite/as-1/application",
     "descriptionPlain": "SQL and dashboards.", "address": {"postalAddress": {"addressCountry": "India"}}},
    {"id": "as-2", "title": "Hidden role", "isListed": False}]}


def test_greenhouse_lever_and_ashby_feeds_become_postings():
    gh = boards.fetch("greenhouse", "kitebird", "Kitebird", "kitebird.example", get=lambda url: GREENHOUSE)
    assert gh[0].source_job_id == "101" and gh[0].company_domain == "kitebird.example"
    assert "Build our Python APIs." in gh[0].text and "- FastAPI" in gh[0].text
    assert gh[0].posted_at == datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)

    lv = boards.fetch("lever", "kite", "Kite", "kite.example", get=lambda url: LEVER)
    assert lv[0].country == "IN" and lv[0].remote is False and lv[0].employment == "Intern"
    assert "You have" in lv[0].text and "- TypeScript" in lv[0].text and "Rs 20,000" in lv[0].text

    ab = boards.fetch("ashby", "kite", "Kite", None, get=lambda url: ASHBY)
    assert [p.source_job_id for p in ab] == ["as-1"]                 # unlisted roles are not read
    assert ab[0].remote is True and ab[0].country == "India"

    raw = gh[0].raw_text()
    assert raw.startswith("Backend Engineer\nKitebird (kitebird.example)\nLocation: Bengaluru, India")
    assert "Apply: https://job-boards.greenhouse.io/kitebird/jobs/101" in raw


def test_probe_lists_only_live_boards():
    def get(url):
        if "lever" in url:
            return LEVER
        raise boards.BoardGone(url)
    assert boards.probe("kite", get=get) == [("lever", 1)]


@pytest.mark.parametrize("location,remote,country,ok", [
    ("Bengaluru-VTP, India", None, None, True),
    ("Bangalore; San Francisco", None, None, True),
    ("Pune", None, "IN", True),
    ("Remote", True, None, True),
    ("Remote - Worldwide", None, None, True),
    ("Remote (APAC)", None, None, True),
    ("Remote - US", None, None, False),
    ("Remote, Canada", True, None, False),
    ("London, UK", None, None, False),
    ("Acme | Senior Engineer | Remote (US only)", None, None, False),
    ("Acme | Backend Engineer | REMOTE | Full-time", None, None, True),
])
def test_india_or_open_to_india(location, remote, country, ok):
    assert india_or_open(location, remote, country) is ok


def test_html_to_text_keeps_lists_and_paragraphs():
    assert html_to_text("<p>One</p><ul><li>A</li><li>B</li></ul>") == "One\n- A\n- B"


CAREERS_PAGE = """<html><head>
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
  {"@type": "Organization", "name": "Tallyhoo"},
  {"@type": "JobPosting", "title": "Frontend Intern", "datePosted": "2026-09-28", "identifier": {"value": "fe-7"},
   "description": "<p>React and TypeScript.</p>", "employmentType": "INTERN", "jobLocationType": "TELECOMMUTE",
   "hiringOrganization": {"name": "Tallyhoo"}, "url": "https://tallyhoo.example/careers/fe-7"},
  {"@type": "JobPosting", "title": "Old role", "validThrough": "2020-01-01", "description": "gone"}]}</script>
</head><body>
<a href="https://boards.greenhouse.io/tallyhoo">All openings</a>
<a href="https://jobs.lever.co/tallyhoo-eng/abc">One role</a>
<script src="https://boards.greenhouse.io/embed/job_board/js?for=tallyhoo"></script>
<a href="mailto:jobs@tallyhoo.example">Write to us</a>
</body></html>"""


def test_careers_page_gives_its_boards_and_its_listed_openings():
    assert careers.board_links(CAREERS_PAGE) == [("greenhouse", "tallyhoo"), ("lever", "tallyhoo-eng")]
    got = careers.job_postings("https://tallyhoo.example/careers", CAREERS_PAGE, "Tallyhoo", "tallyhoo.example")
    assert [p.title for p in got] == ["Frontend Intern"]              # the expired one is left out
    p = got[0]
    assert p.source == "careers" and p.source_job_id == "fe-7" and p.remote is True
    assert p.text == "React and TypeScript." and p.company_domain == "tallyhoo.example"


def test_site_scan_reads_home_and_careers_pages_where_robots_allow():
    home = '<a href="/careers">Careers</a> <a href="/team">Team</a>'
    pages = {"https://tallyhoo.example": home, "https://tallyhoo.example/careers": CAREERS_PAGE}
    fetched = []

    def fetch(url):
        fetched.append(url)
        return (url, pages[url]) if url in pages else None

    robots = "User-agent: *\nDisallow: /private\n"
    s = careers.scan("tallyhoo.example", "Tallyhoo", fetch=fetch, fetch_text=lambda u: (u, robots))
    assert fetched == ["https://tallyhoo.example", "https://tallyhoo.example/careers"]
    assert s.pages == 2 and ("greenhouse", "tallyhoo") in s.boards and len(s.postings) == 1
    assert [c.email for c in s.contacts] == ["jobs@tallyhoo.example"]

    careers.robots._CACHE.clear()
    blocked = careers.scan("tallyhoo.example", "Tallyhoo", fetch=fetch,
                           fetch_text=lambda u: (u, "User-agent: *\nDisallow: /\n"))
    assert blocked.pages == 0
    careers.robots._CACHE.clear()


HN_THREAD = {"children": [
    {"id": 1, "type": "comment", "created_at": "2026-10-01T15:05:00.000Z",
     "text": "Kitebird | Backend Engineer | Bengaluru, India | ONSITE<p>Python, FastAPI. Email jobs@kitebird.example</p>"},
    {"id": 2, "type": "comment", "created_at": "2026-10-01T15:06:00.000Z", "text": None},
]}


def test_hacker_news_replies_become_postings():
    ps = hn.postings("49922569", get=lambda url, params=None: HN_THREAD)
    assert len(ps) == 1
    p: Posting = ps[0]
    assert p.company_name == "Kitebird" and p.title.startswith("Kitebird | Backend Engineer")
    assert p.url == "https://news.ycombinator.com/item?id=1" and india_or_open(p.location)
    assert hn.latest_thread(get=lambda url, params=None: {"hits": [
        {"objectID": "2", "title": "Ask HN: Who wants to be hired? (October 2026)"},
        {"objectID": "3", "title": "Ask HN: Who is hiring? (October 2026)"}]}) == "3"
