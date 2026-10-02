"""The line check that replaced per-line approval (app/provenance.py). The CV is made up in
the shape real ones take, including a two-column layout read line by line across both columns."""
from app.provenance import (
    Corpus, check_line, check_name, drop_unbacked_sentences, has_contact, has_url, keep_if_numbers_known,
    keep_known_tools, numbers, tech_terms,
)

CV = """ROHAN DAS                                            CONTACT
Backend Developer · B.Tech Computer Science, 2027      Kolkata, West Bengal, India
PROJECTS                                               rohan.das@example.com · +91 90000 00005
PixelForge — Image Processing API | Jan 2026 – Apr 2026   github.com/rohan-das-example
Stack: Python, FastAPI, Celery, Redis, Pillow, MinIO, Docker   TECHNICAL SKILLS
• Moved processing to a Celery worker pool, handling about   Languages: Python, TypeScript, SQL
60 images per second on a four-core machine without          Backend: FastAPI, Node.js, Express
blocking requests.                                            EDUCATION
• Cached results by content hash in S3-compatible storage,    Hooghly Institute of Technology
so repeated requests for the same transform skip processing.  CGPA: 8.30 / 10
TutorLink — Tutoring Marketplace | Aug 2025 – Dec 2025        AWARDS
• Reached a Lighthouse mobile performance score of 96 after   Winner, college web development hackathon, 2025
optimising images and splitting the bundle by route.
• Grew to 1,200 weekly users across three colleges.
"""
NOTES = "I also built Splitsy, an expense splitter for hostel roommates, in React and Node.js."
CORPUS = Corpus([("CV: rohan.pdf", CV), ("your notes", NOTES)])


def test_verbatim_bullet_passes_across_interleaved_columns():
    c = check_line("Moved processing to a Celery worker pool, handling about 60 images per second on a "
                   "four-core machine without blocking requests.", CORPUS)
    assert c.ok, c.reason
    assert c.doc == "CV: rohan.pdf" and c.coverage >= 0.9


def test_light_rewording_passes():
    assert check_line("Cached transform results by content hash in S3-compatible storage so repeated requests "
                      "skip processing", CORPUS).ok


def test_a_changed_number_fails_with_the_number_named():
    c = check_line("Moved processing to a Celery worker pool, handling about 600 images per second.", CORPUS)
    assert not c.ok and "600" in c.reason


def test_thousands_separators_and_trailing_zeros_compare_equal():
    assert check_line("Grew to 1200 weekly users across three colleges.", CORPUS).ok
    assert numbers("CGPA 8.30") == {"8.3"}
    assert "8.3" in CORPUS.nums


def test_an_added_tool_fails():
    c = check_line("Moved processing to a Celery worker pool on Kubernetes without blocking requests.", CORPUS)
    assert not c.ok and "Kubernetes" in c.reason


def test_an_invented_line_fails():
    c = check_line("Led a team of eight engineers to migrate the billing platform to microservices.", CORPUS)
    assert not c.ok and c.reason == "We couldn't find this in anything you gave us"


def test_notes_count_as_sources():
    assert check_line("Built Splitsy, an expense splitter for hostel roommates, in React and Node.js.", CORPUS).ok


def test_short_lines_need_every_word():
    assert check_name("PixelForge", CORPUS).ok
    assert check_name("TutorLink", CORPUS).ok
    assert not check_name("PixelSmith", CORPUS).ok
    assert check_line("Winner, college web development hackathon, 2025", CORPUS).ok
    assert not check_line("Winner, national hackathon, 2025", CORPUS).ok


def test_stack_keeps_only_tools_the_documents_name():
    kept, dropped = keep_known_tools("Python, FastAPI, Kubernetes, Redis", CORPUS)
    assert kept == "Python, FastAPI, Redis" and dropped == ["Kubernetes"]
    assert keep_known_tools(None, CORPUS) == (None, [])


def test_periods_and_grades_need_known_numbers():
    assert keep_if_numbers_known("Jan 2026 – Apr 2026", CORPUS) == "Jan 2026 – Apr 2026"
    assert keep_if_numbers_known("Jan 2024 – Apr 2026", CORPUS) is None
    assert keep_if_numbers_known("CGPA: 8.3 / 10", CORPUS) == "CGPA: 8.3 / 10"


def test_contacts_and_links_must_appear():
    assert has_contact("rohan.das@example.com", CORPUS)
    assert not has_contact("rohan@example.com", CORPUS)
    assert has_contact("+91-90000-00005", CORPUS)
    assert has_url("https://github.com/rohan-das-example/", CORPUS)
    assert not has_url("https://github.com/someone-else", CORPUS)


def test_tech_terms_skip_ordinary_words():
    assert tech_terms("Used Redis and PostgreSQL to go faster and express intent") == {"redis", "postgresql"}


def test_summaries_lose_only_the_unbacked_sentences():
    kept, removed = drop_unbacked_sentences(
        "Builds backends that hold up under load. PixelForge handles about 60 images a second. "
        "Served 50,000 users on Kubernetes.", CORPUS)
    assert kept == "Builds backends that hold up under load. PixelForge handles about 60 images a second."
    assert removed == ["Served 50,000 users on Kubernetes."]
    kept, _ = drop_unbacked_sentences("Three years building payment APIs.", CORPUS, extra_numbers={"3"})
    assert kept


def test_empty_corpus_backs_nothing():
    empty = Corpus([])
    assert not check_line("Built an API.", empty).ok
    assert not check_line("", CORPUS).ok
