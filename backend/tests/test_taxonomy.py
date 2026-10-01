"""Role families, experience bands, years from work periods, skill names (app/taxonomy.py).
Titles are made up in the shape real posts use; none come from the reference data."""
from datetime import date
from typing import get_args

import pytest

from app import taxonomy as t
from app.pipeline.schemas import Discipline

TITLES = [
    # software engineering, generic
    ("Software Engineer", "sde"), ("Software Developer", "sde"), ("SDE II", "sde"), ("SDE-1", "sde"),
    ("Software Development Engineer", "sde"), ("Associate Software Engineer", "sde"),
    ("Member of Technical Staff", "sde"), ("Graduate Engineer Trainee", "sde"), ("SWE Intern", "sde"),
    ("Senior Software Engineer (Python)", "sde"), ("Programmer Analyst Trainee", "sde"),
    ("Salesforce Developer", "sde"), ("Game Developer", "sde"), ("Blockchain Developer", "sde"),
    # backend
    ("Backend Software Engineer", "backend"), ("Backend Developer Intern", "backend"),
    ("Back-End Engineer", "backend"), ("Python Backend Engineer", "backend"), ("Node.js Developer", "backend"),
    ("Java Developer", "backend"), ("Golang Engineer", "backend"), ("Django Developer", "backend"),
    ("API Developer", "backend"), ("Software Engineer, Backend", "backend"), ("PHP Developer", "backend"),
    ("Server-side Engineer", "backend"), (".NET Developer", "backend"),
    # frontend
    ("Frontend Engineer", "frontend"), ("Front-End Developer", "frontend"), ("React Developer", "frontend"),
    ("ReactJS Developer Intern", "frontend"), ("UI Developer", "frontend"), ("Angular Developer", "frontend"),
    ("Vue.js Engineer", "frontend"), ("JavaScript Developer", "frontend"), ("Next.js Developer", "frontend"),
    # full stack
    ("Full Stack Developer", "fullstack"), ("Full-Stack Engineer", "fullstack"), ("Fullstack Intern", "fullstack"),
    ("MERN Stack Developer", "fullstack"), ("MEAN Stack Developer", "fullstack"), ("Web Developer", "fullstack"),
    ("Full Stack Engineer (React/Node)", "fullstack"),
    # mobile
    ("Android Developer", "mobile"), ("iOS Engineer", "mobile"), ("Flutter Developer Intern", "mobile"),
    ("React Native Developer", "mobile"), ("Mobile App Developer", "mobile"),
    # AI and ML
    ("Machine Learning Engineer", "ai_ml"), ("ML Engineer", "ai_ml"), ("AI Engineer", "ai_ml"),
    ("AI/ML Intern", "ai_ml"), ("Data Scientist", "ai_ml"), ("NLP Engineer", "ai_ml"),
    ("LLM Engineer", "ai_ml"), ("GenAI Engineer", "ai_ml"), ("Applied Scientist", "ai_ml"),
    ("Deep Learning Engineer", "ai_ml"), ("Software Engineer, Machine Learning", "ai_ml"),
    ("Generative AI Developer", "ai_ml"),
    # computer vision
    ("Computer Vision Engineer", "cv"), ("Perception Engineer", "cv"), ("Image Processing Intern", "cv"),
    # data
    ("Data Analyst", "data_analytics"), ("Data Analyst Intern", "data_analytics"),
    ("Business Intelligence Analyst", "data_analytics"), ("BI Developer", "data_analytics"),
    ("Product Analyst", "data_analytics"), ("Power BI Developer", "data_analytics"),
    ("Data Engineer", "data_engineering"), ("Big Data Engineer", "data_engineering"),
    ("ETL Developer", "data_engineering"), ("Analytics Engineer", "data_engineering"),
    # devops
    ("DevOps Engineer", "devops"), ("Site Reliability Engineer", "devops"), ("SRE", "devops"),
    ("Cloud Engineer", "devops"), ("Platform Engineer", "devops"), ("MLOps Engineer", "devops"),
    ("Infrastructure Engineer", "devops"), ("DevSecOps Engineer", "devops"),
    # QA
    ("QA Engineer", "qa"), ("SDET", "qa"), ("Automation Test Engineer", "qa"), ("Software Tester", "qa"),
    ("Quality Assurance Analyst", "qa"), ("QA Automation Intern", "qa"),
    # embedded
    ("Embedded Software Engineer", "embedded"), ("Firmware Engineer", "embedded"), ("IoT Engineer", "embedded"),
    ("VLSI Design Engineer", "embedded"), ("Hardware Engineer", "embedded"),
    # security
    ("Security Engineer", "security"), ("Cybersecurity Analyst", "security"), ("SOC Analyst", "security"),
    ("Penetration Tester", "security"), ("Application Security Engineer", "security"),
    # design, product, business, marketing, operations
    ("UI/UX Designer", "design"), ("Product Designer", "design"), ("UX Designer Intern", "design"),
    ("Graphic Designer", "design"),
    ("Product Manager", "product"), ("Associate Product Manager", "product"), ("Product Owner", "product"),
    ("Business Analyst", "business"), ("Business Development Executive", "business"), ("Sales Engineer", "business"),
    ("BDE Intern", "business"), ("Financial Analyst", "business"),
    ("Marketing Intern", "marketing"), ("Growth Associate", "marketing"), ("Content Writer", "marketing"),
    ("SEO Executive", "marketing"),
    ("Operations Executive", "operations"), ("HR Intern", "operations"), ("Technical Recruiter", "operations"),
    ("Customer Success Associate", "operations"),
    # nothing to go on
    ("", "other"), (None, "other"), ("Chief of Staff", "other"),
]


@pytest.mark.parametrize("title,family", TITLES)
def test_title_family(title, family):
    assert t.title_family(title) == family


def test_families_match_the_extraction_schema():
    assert set(t.FAMILIES) == set(get_args(t.RoleFamily)) == set(get_args(Discipline))
    for key, fam in t.FAMILIES.items():
        assert fam.neighbours <= set(t.FAMILIES) - {key}, key
        assert key == "other" or fam.aliases, key


def test_family_rules_name_real_families():
    assert {fam for fam, _ in t._RULES} <= set(t.FAMILIES)


def test_neighbours_include_self():
    assert t.family_with_neighbours("backend") == {"backend", "sde", "fullstack"}
    assert t.family_with_neighbours("security") == {"security"}
    assert t.family_with_neighbours("nonsense") == {"nonsense"}


@pytest.mark.parametrize("title,hint", [
    ("Backend Developer Intern", "intern"), ("Graduate Engineer Trainee", "intern"),
    ("Senior Software Engineer", "senior"), ("Sr. Data Engineer", "senior"), ("Tech Lead", "senior"),
    ("Junior Frontend Developer", "junior"), ("Associate Software Engineer", "junior"),
    ("Software Engineer", None), ("SDE II", None),
])
def test_seniority_hint(title, hint):
    assert t.seniority_hint(title) == hint


@pytest.mark.parametrize("years,stage,band", [
    (0, None, "entry"), (0.9, None, "entry"), (1, None, "junior"), (2.99, None, "junior"), (3, None, "mid"),
    (4.9, None, "mid"), (5, None, "senior"), (7.9, None, "senior"), (8, None, "lead"), (15, None, "lead"),
    (None, None, "entry"), (2, "student", "intern"), (0, "student", "intern"), (3.2, "experienced", "mid"),
])
def test_band_for_years(years, stage, band):
    assert t.band_for_years(years, stage) == band


@pytest.mark.parametrize("lo,hi,etype,bands", [
    (None, None, "internship", ["intern"]), (2, 4, "internship", ["intern"]),
    (0, 0, "full_time", ["entry"]), (0, 1, "full_time", ["entry", "junior"]),
    (0, 2, None, ["entry", "junior"]), (2, 4, None, ["junior", "mid"]), (3, 5, None, ["mid", "senior"]),
    (3, None, None, ["mid", "senior"]), (5, None, None, ["senior"]), (8, None, None, ["lead"]),
    (10, 15, None, ["lead"]), (None, None, "full_time", ["entry", "junior"]), (None, 2, None, ["entry", "junior"]),
])
def test_bands_for_range(lo, hi, etype, bands):
    assert t.bands_for_range(lo, hi, etype) == bands


def test_bands_cover_every_year_without_gaps():
    edges = [(lo, hi) for _, lo, hi in t.BANDS]
    assert edges[0][0] == 0 and edges[-1][1] is None
    for (_, a_hi), (b_lo, _) in zip(edges, edges[1:]):
        assert a_hi == b_lo


@pytest.mark.parametrize("years,lo,hi,fit", [
    (3, 3, 5, "fits"), (4, 3, None, "fits"), (2.2, 3, 5, "stretch"), (2, 3, 5, "stretch"),
    (1.5, 3, 5, "under"), (0, None, None, "fits"), (9, 0, 2, "over"), (4, 0, 2, "fits"), (0, 0, 0, "fits"),
])
def test_experience_fit(years, lo, hi, fit):
    assert t.experience_fit(years, lo, hi)[0] == fit


def test_experience_fit_explains_a_shortfall():
    assert t.experience_fit(2, 3, 5) == ("stretch", "Asks for 3+ years; you have 2")


TODAY = date(2026, 10, 1)


@pytest.mark.parametrize("period,months", [
    ("Jan 2022 – Present", 58), ("Aug 2023 - May 2025", 22), ("2021-2023", 25), ("Jan 2022-Present", 58),
    ("2022-01 - 2023-06", 18), ("06/2022 to 08/2023", 15), ("Sept 2024 – Mar 2025", 7),
    ("March 2020 — February 2021", 12), ("Jul '23 - Dec '23", 6), ("2022", 1), ("Oct 2026 - Present", 1),
])
def test_period_span(period, months):
    a, b = t.period_span(period, TODAY)
    assert b - a + 1 == months


@pytest.mark.parametrize("period", ["", None, "Summer", "Present - Jan 2020", "a few months"])
def test_period_span_unreadable(period):
    assert t.period_span(period, TODAY) is None


def test_years_merge_overlaps_and_skip_unreadable():
    assert t.years_of_experience(["Jan 2022 – Dec 2022", "Jul 2022 – Jun 2023", "sometime"], TODAY) == 1.5
    assert t.years_of_experience(["Jan 2020 – Dec 2020", "Jan 2022 – Dec 2022"], TODAY) == 2.0
    assert t.years_of_experience(["Oct 2023 – Present"], TODAY) == 3.1
    assert t.years_of_experience([], TODAY) == 0.0


def test_internship_detection():
    assert t.is_internship("Backend Intern")
    assert t.is_internship("Summer Internship, Acme")
    assert t.is_internship("Graduate Trainee")
    assert not t.is_internship("Internal Tools Engineer")


@pytest.mark.parametrize("raw,canon", [
    ("reactjs", "React"), ("React.js", "React"), (" NodeJS ", "Node.js"), ("postgres", "PostgreSQL"),
    ("K8s", "Kubernetes"), ("golang", "Go"), ("Tailwind", "Tailwind CSS"), ("sklearn", "scikit-learn"),
    ("REST APIs", "REST APIs"), ("Rust", "Rust"), ("Some  Custom   Tool", "Some Custom Tool"),
])
def test_canonical_skill(raw, canon):
    assert t.canonical_skill(raw) == canon


def test_same_skill():
    assert t.same_skill("ReactJS", "react")
    assert t.same_skill("Postgres", "PostgreSQL.")
    assert not t.same_skill("Java", "JavaScript")
