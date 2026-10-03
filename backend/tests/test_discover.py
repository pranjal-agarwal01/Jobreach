"""Discovery: which directory companies and news items are worth a look, and when a company's
site is kept. The network, the model and the database are replaced by fakes."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import discover


def yc(name, regions, hiring=True, status="Active", website="https://example.com", where=""):
    return {"name": name, "slug": name.lower(), "regions": regions, "all_locations": where, "isHiring": hiring,
            "status": status, "website": website, "batch": "Winter 2024", "one_liner": "Payments for shops",
            "url": "https://www.ycombinator.com/companies/" + name.lower()}


def test_directory_companies_in_india_or_fully_remote_and_hiring():
    data = [yc("Razorpay", ["India", "South Asia"], where="Bengaluru, KA, India"),
            yc("Remotely", ["Fully Remote"]),
            yc("Valley", ["America / Canada", "Partly Remote"]),
            yc("Quiet", ["India"], hiring=False),
            yc("Gone", ["India"], status="Inactive"),
            yc("NoSite", ["India"], website=None)]
    got = discover.yc_candidates(data)
    assert [f.name for f in got] == ["Razorpay", "Remotely"]
    assert got[0].note == "Y Combinator Winter 2024, hiring (Bengaluru, KA, India)" and got[0].via == "yc"


FEED = """<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[Seeds Fincap secures Rs 100 Cr in Series B]]></title><link>https://news.example/seeds</link></item>
<item><title>Why founders burn out</title><link>https://news.example/opinion</link></item>
</channel></rss>"""


def test_feed_items_well_formed_and_loose():
    assert [(i.title, i.link) for i in discover.feed_items(FEED)][0] == (
        "Seeds Fincap secures Rs 100 Cr in Series B", "https://news.example/seeds")
    broken = FEED.replace("Why founders", "Why &nbsp; founders")          # an HTML entity XML doesn't know
    assert len(discover.feed_items(broken)) == 2


@pytest.mark.parametrize("title,funding", [
    ("Seeds Fincap secures over Rs 100 Cr in Series B", True),
    ("From Simple Energy To Arivihan: Indian Startups Raised Over $233 Mn This Week", True),
    ("Kiwi bags $3 Mn in seed round", True),
    ("Caller ID app hits 500 million monthly users", True),      # read, and the model finds no round
    ("Why founders burn out", False),
])
def test_only_funding_headlines_are_read(title, funding):
    assert bool(discover.FUNDING_TITLE.search(title)) is funding


def test_article_links_leave_out_the_news_site_and_social_media():
    html = """<html><body><nav><a href="https://other.example/nav">nav</a></nav><article>
      <p>Kiwi raised $3 Mn. <a href="https://www.kiwi.example/">Kiwi</a> builds credit cards.
      <a href="https://news.example/more">more news</a> <a href="https://www.linkedin.com/company/kiwi">LinkedIn</a></p>
      </article></body></html>"""
    text, links = discover.article_text_and_links("https://news.example/kiwi", html)
    assert "Kiwi raised $3 Mn" in text and links == [("Kiwi", "https://www.kiwi.example/")]


def test_a_website_the_model_invents_is_not_used(monkeypatch):
    news = SimpleNamespace(companies=[
        SimpleNamespace(name="Kiwi", website="https://www.kiwi.example/", what_it_does="credit cards",
                        round="seed", amount="$3 Mn", city="Bengaluru"),
        SimpleNamespace(name="Made Up", website="https://madeup.example", what_it_does="x", round=None,
                        amount=None, city=None)])
    monkeypatch.setattr(discover.llm, "structured", lambda *a, **k: news)
    item = discover.Item("Kiwi bags $3 Mn", "https://news.example/kiwi")
    got = discover.article_companies(item, "text", [("Kiwi", "https://www.kiwi.example/")], "inc42")
    assert got[0].website == "https://www.kiwi.example/" and got[0].note == "Raised seed of $3 Mn (Inc42)"
    assert got[1].website is None and got[1].note == "Raised funding (Inc42)"


@pytest.mark.parametrize("name,key", [("Seeds Fincap Pvt Ltd", "seedsfincap"), ("Kiwi", "kiwi"),
                                      ("Simple Energy", "simpleenergy"), ("Atlan Technologies", "atlan")])
def test_name_key(name, key):
    assert discover.name_key(name) == key


@pytest.fixture
def db(monkeypatch):
    state = {"known": {}, "marked": []}

    class Conn:
        def execute(self, sql, params=None):
            if "from companies where domain" in sql:
                hit = state["known"].get(params[0])
                return SimpleNamespace(fetchone=lambda: {"id": hit} if hit else None)
            if sql.lstrip().startswith("update companies"):
                state["marked"].append(params[-1])
            return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    @contextmanager
    def tx():
        yield Conn()
    monkeypatch.setattr(discover, "system_tx", tx)
    return state


def found(website=None):
    return discover.Found(name="Kiwi", about="credit cards", note="Raised seed (Inc42)", url="https://news.example/k",
                          via="funding_news", key="https://news.example/k", website=website)


def test_a_guessed_site_is_kept_only_when_it_carries_the_name_and_the_check_agrees(db):
    homes = {"kiwi.com": "Title: Domain for sale", "kiwi.in": "Title: Kiwi | Credit cards on UPI"}
    checked = []

    def check(name, d, about, homepage):
        checked.append(d)
        return {"id": "c-" + d, "verification": "pass"}
    cid = discover.register(found(), check=check, fetch_home=homes.get, has_address=lambda d: d in homes)
    assert cid == "c-kiwi.in" and checked == ["kiwi.in"] and db["marked"] == ["c-kiwi.in"]


def test_a_site_the_check_rejects_is_not_kept(db):
    cid = discover.register(found("https://kiwi.example"), check=lambda *a, **k: None,
                            fetch_home=lambda d: "Title: Kiwi", has_address=lambda d: True)
    assert cid is None and db["marked"] == []


def test_a_company_already_known_is_only_marked(db):
    db["known"]["kiwi.example"] = "c-old"
    cid = discover.register(found("https://www.kiwi.example/"), check=lambda *a, **k: pytest.fail("checked again"),
                            fetch_home=lambda d: pytest.fail("fetched again"))
    assert cid == "c-old" and db["marked"] == ["c-old"]


def test_news_reads_each_funding_article_once(db, monkeypatch):
    seen, remembered = set(), []
    monkeypatch.setattr(discover, "_seen", lambda feed: seen)
    monkeypatch.setattr(discover, "_remember", lambda feed, key, title, n: (remembered.append((feed, key, n)), seen.add(key)))
    queued = []
    monkeypatch.setattr(discover, "_queue_companies", lambda found: queued.extend(found))
    monkeypatch.setattr(discover, "FEEDS", {"inc42": "https://inc42.example/feed"})
    extract = lambda item, text, links, feed: [found()]                       # noqa: E731
    out = discover.discover_news(fetch_feed=lambda u: FEED, fetch_article=lambda u: (u, "<article>x</article>"),
                                 extract=extract)
    assert out == {"articles": 1, "companies_queued": 1, "more": False} and [f.name for f in queued] == ["Kiwi"]
    assert remembered == [("inc42", "https://news.example/seeds", 1)]
    again = discover.discover_news(fetch_feed=lambda u: FEED, fetch_article=lambda u: pytest.fail("read twice"),
                                   extract=extract)
    assert again["articles"] == 0


def test_directory_companies_are_queued_once_each(monkeypatch):
    seen, queued = set(), []
    monkeypatch.setattr(discover, "_seen", lambda feed: set(seen))
    monkeypatch.setattr(discover, "_remember", lambda feed, key, title, n: seen.add(key))
    monkeypatch.setattr(discover, "_queue_companies", lambda found: queued.extend(f.name for f in found))
    monkeypatch.setattr(discover, "_continue", lambda kind: None)
    data = [yc("Razorpay", ["India"]), yc("Remotely", ["Fully Remote"])]
    assert discover.discover_yc(data)["queued"] == 2 and discover.discover_yc(data)["queued"] == 0
    assert queued == ["Razorpay", "Remotely"]


def test_a_queued_company_is_checked_from_its_task(monkeypatch):
    got = []
    monkeypatch.setattr(discover, "register", lambda f: got.append(f) or "c1")
    from dataclasses import asdict
    assert discover.discover_company(asdict(found("https://kiwi.example"))) == "c1" and got[0].website == "https://kiwi.example"
