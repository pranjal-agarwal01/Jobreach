"""Who to write to: candidates from the post and the company's own site, each with where it was
published, chosen by publication context (docs/plan-global-pool.md, 0.4). No network."""
from app.pipeline import contacts as ct
from app.pipeline.schemas import ApplyRoute, Extracted, Stipend

POST = """Hiring a Backend Intern at Acme Labs (acmelabs.io). Send your CV to our CTO Priya Rao at
priya.rao@acmelabs.io, or to hr@acmelabs.io. For press, write to press@acmelabs.io."""


def ex(routes, **kw):
    base = dict(title="Backend Intern", company_name="Acme Labs", company_domain="acmelabs.io",
                poster_name="Dev Shah", poster_type="employee", stipend=Stipend(stated="unstated"),
                discipline="backend", apply_routes=routes)
    base.update(kw)
    return Extracted(**base)


def email(addr, name=None, role=None):
    return ApplyRoute(type="email", value=addr, person_name=name, person_role=role)


def test_post_order_named_hiring_person_then_hr_then_mailbox():
    e = ex([email("hr@acmelabs.io"), email("priya.rao@acmelabs.io", "Priya Rao", "CTO"),
            email("careers@acmelabs.io")])
    cands, notes = ct.from_post(e, POST + " careers@acmelabs.io", "acmelabs.io")
    assert [c.email for c in sorted(cands, key=ct.Candidate.sort_key)] == [
        "priya.rao@acmelabs.io", "hr@acmelabs.io", "careers@acmelabs.io"]
    best = ct.choose(cands, has_portal=False)
    assert best.person_name == "Priya Rao" and best.context == "post_apply" and best.domain_matches
    assert "Priya Rao" in best.evidence and "priya.rao@acmelabs.io" in best.evidence
    assert not notes


def test_an_address_for_another_purpose_is_never_used():
    cands, notes = ct.from_post(ex([email("press@acmelabs.io")]), POST, "acmelabs.io")
    assert cands == [] and "another purpose" in notes[0]


def test_the_posters_own_address_is_attributed_to_them_never_guessed():
    e = ex([email("dev@acmelabs.io")], poster_name="Dev Shah", poster_role="Founder", poster_type="founder")
    cands, _ = ct.from_post(e, "Email me at dev@acmelabs.io", "acmelabs.io")
    assert cands[0].person_name == "Dev Shah" and cands[0].tier == ct.TIER_LEADER


def test_personal_mailbox_kept_for_a_named_founder_and_dropped_otherwise():
    cands, notes = ct.from_post(ex([email("dev.founder@gmail.com")], poster_type="founder"), "", "acmelabs.io")
    assert cands and cands[0].personal_mailbox and "personal mailbox" in notes[0]
    cands, notes = ct.from_post(ex([email("x123@gmail.com")], poster_type="unknown", company_name=None), "", None)
    assert cands == [] and "no named company" in notes[0]


def test_domain_mismatch_is_flagged_and_ranks_below_a_matching_address():
    cands, notes = ct.from_post(ex([email("jobs@otherco.in"), email("jobs@acmelabs.io")]), "", "acmelabs.io")
    assert any("differs" in n for n in notes)
    assert ct.choose(cands, False).email == "jobs@acmelabs.io"


CAREERS_HTML = """<html><body><h1>Careers at Acme</h1>
<p>Open roles below. Not listed? Write to <a href="mailto:careers@acmelabs.io">our hiring team</a>.</p>
<p>Press enquiries: press@acmelabs.io. Our founder Priya writes at priya@acmelabs.io.</p>
<footer>hello@acmelabs.io · recruiting@agency.com</footer></body></html>"""

HOME_HTML = """<html><body><a href="/careers">We're hiring</a> <a href="https://linkedin.com/company/acme/jobs">Jobs on LinkedIn</a>
<a href="/blog">Blog</a><p>Say hi: hello@acmelabs.io</p></body></html>"""


def test_site_keeps_only_role_addresses_on_the_companys_own_domain():
    got = {c.email: c for c in ct.page_candidates("https://acmelabs.io/careers", CAREERS_HTML, "acmelabs.io")}
    assert set(got) == {"careers@acmelabs.io", "hello@acmelabs.io"}       # no press, no person, no agency
    assert got["careers@acmelabs.io"].context == "careers_page"
    assert "hiring team" in got["careers@acmelabs.io"].evidence
    assert got["hello@acmelabs.io"].context == "site_generic"


def test_harvest_follows_only_the_companys_own_careers_links():
    fetched = []

    def fetch(url):
        fetched.append(url)
        pages = {"https://acmelabs.io": HOME_HTML, "https://acmelabs.io/careers": CAREERS_HTML}
        return (url, pages[url]) if url in pages else None

    found = ct.harvest_site("acmelabs.io", fetch=fetch)
    assert fetched == ["https://acmelabs.io", "https://acmelabs.io/careers"]   # never LinkedIn
    assert [c.email for c in found] == ["careers@acmelabs.io", "hello@acmelabs.io"]


def test_choose_puts_the_portal_above_a_general_inbox_only():
    generic = ct.Candidate(email="hello@acmelabs.io", context="site_generic", tier=ct.TIER_GENERIC_BOX)
    careers = ct.Candidate(email="careers@acmelabs.io", context="careers_page", tier=ct.TIER_HIRING_BOX)
    post = ct.Candidate(email="hr@acmelabs.io", context="post_apply", tier=ct.TIER_HIRING_BOX)
    assert ct.choose([generic], has_portal=True) is None                     # apply on the portal
    assert ct.choose([generic], has_portal=False) is generic
    assert "general inbox" in ct.flag_for(generic)
    assert ct.choose([generic, careers], has_portal=True) is careers
    assert ct.choose([careers, post, generic], has_portal=True) is post
    assert ct.flag_for(post) is None
