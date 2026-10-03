"""
The shared vocabulary of the opportunity pool and every profile (docs/plan-global-pool.md):
role families, experience bands and skill names.

Posts name the same work many ways ("SDE II", "Backend Software Engineer", "Python Backend
Developer"); collection and matching need one key per kind of work, while the original title
is kept for display. Experience is stored as numbers and mapped to bands, so pools can be
counted per band while eligibility still compares years.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

RoleFamily = Literal["sde", "backend", "frontend", "fullstack", "mobile", "ai_ml", "cv",
                     "data_analytics", "data_engineering", "devops", "qa", "embedded", "security",
                     "design", "product", "business", "marketing", "operations", "other"]


@dataclass(frozen=True)
class Family:
    label: str
    aliases: tuple[str, ...]                     # search queries collectors run for this family
    neighbours: frozenset[str] = field(default_factory=frozenset)


FAMILIES: dict[str, Family] = {
    "sde": Family("Software engineering", ("Software Engineer", "Software Developer", "SDE",
                  "Software Development Engineer", "Graduate Engineer Trainee"),
                  frozenset({"backend", "fullstack", "frontend"})),
    "backend": Family("Backend", ("Backend Engineer", "Backend Developer", "Backend Software Engineer",
                      "Python Backend Engineer", "Node.js Developer", "Java Developer", "Golang Developer"),
                      frozenset({"sde", "fullstack"})),
    "frontend": Family("Frontend", ("Frontend Engineer", "Frontend Developer", "React Developer",
                       "UI Developer"), frozenset({"sde", "fullstack"})),
    "fullstack": Family("Full stack", ("Full Stack Developer", "Full Stack Engineer", "MERN Stack Developer",
                        "Web Developer"), frozenset({"sde", "backend", "frontend"})),
    "mobile": Family("Mobile", ("Android Developer", "iOS Developer", "Flutter Developer",
                     "React Native Developer"), frozenset({"frontend"})),
    "ai_ml": Family("AI and ML", ("Machine Learning Engineer", "AI Engineer", "Data Scientist",
                    "LLM Engineer", "NLP Engineer", "GenAI Engineer"), frozenset({"cv"})),
    "cv": Family("Computer vision", ("Computer Vision Engineer", "Perception Engineer"), frozenset({"ai_ml"})),
    "data_analytics": Family("Data analytics", ("Data Analyst", "Business Intelligence Analyst",
                             "Product Analyst"), frozenset({"data_engineering"})),
    "data_engineering": Family("Data engineering", ("Data Engineer", "Big Data Engineer", "Analytics Engineer",
                               "ETL Developer"), frozenset({"data_analytics", "backend"})),
    "devops": Family("DevOps and cloud", ("DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer",
                     "Platform Engineer", "MLOps Engineer"), frozenset({"backend"})),
    "qa": Family("QA and testing", ("QA Engineer", "SDET", "Automation Test Engineer")),
    "embedded": Family("Embedded", ("Embedded Software Engineer", "Firmware Engineer", "IoT Engineer")),
    "security": Family("Security", ("Security Engineer", "Cybersecurity Analyst", "SOC Analyst",
                       "Penetration Tester")),
    "design": Family("Design", ("Product Designer", "UI/UX Designer", "UX Designer")),
    "product": Family("Product", ("Product Manager", "Associate Product Manager")),
    "business": Family("Business", ("Business Analyst", "Business Development")),
    "marketing": Family("Marketing", ("Marketing", "Growth", "Content")),
    "operations": Family("Operations", ("Operations", "Human Resources")),
    "other": Family("Other", ()),
}

# First match wins, so the specific comes before the generic ("Software Engineer, Backend" is
# backend; "Sales Engineer" is business; a bare "Engineer" is software engineering).
_RULES: list[tuple[str, str]] = [
    ("design", r"\bdesigner\b|\bui\s*/\s*ux\b|\bux\b"),
    ("security", r"\bsecurity\b|\bcyber\s*security\b|\bsoc\s+analyst\b|\bpenetration\b|\bpen\s*test|\bappsec\b|\binfosec\b|\bvapt\b|\bsec\s*ops\b|\bsiem\b|\bthreat\b"),
    ("qa", r"\bqa\b|\bquality\s+(assurance|analyst|engineer)\b|\bsdet\b|\btest(ing)?\s+(engineer|analyst|automation)\b|\bautomation\s+test|\btester\b|\bsoftware\s+test"),
    ("devops", r"\bdev\s*-?\s*ops\b|\bdevsecops\b|\bmlops\b|\bsre\b|\bsite\s+reliability\b|\bcloud\s+(\w+\s+)?(engineer|architect|ops|developer)\b|\bnetwork\s+(engineer|administrator)\b|\bplatform\s+engineer\b|\binfrastructure\b|\binfra\s+engineer\b|\bkubernetes\b|\bsys\s*admin|\bsystems?\s+administrator\b"),
    ("data_engineering", r"\bdata\s+engineer|\bbig\s+data\b|\betl\b|\banalytics\s+engineer|\bdata\s+platform\b|\bdata\s+warehouse"),
    ("cv", r"\bcomputer\s+vision\b|\bcv\s+engineer|\bperception\b|\bimage\s+processing\b"),
    ("ai_ml", r"\bmachine\s+learning\b|\bml\b|\bai\b|\bartificial\s+intelligence\b|\bdeep\s+learning\b|\bnlp\b|\bllms?\b|\bgen\s*ai\b|\bgenerative\b|\bdata\s+scien|\bapplied\s+scientist\b|\bresearch\s+scientist\b"),
    ("data_analytics", r"\b(data|bi|business\s+intelligence|product|reporting|marketing)\s+analyst\b|\bbi\s+(developer|engineer)\b|\banalytics\b|\bpower\s*bi\b|\btableau\b"),
    ("mobile", r"\bandroid\b|\bios\b|\bmobile\b|\bflutter\b|\breact\s+native\b|\bkotlin\b|\bswift\b"),
    ("embedded", r"\bembedded\b|\bfirmware\b|\biot\b|\bvlsi\b|\bfpga\b|\basic\b|\brtl\b|\bhardware\b|\bpcb\b|\bmicrocontroller|\brobotics\b"),
    ("fullstack", r"\bfull\s*-?\s*stack\b|\bmern\b|\bmean\s+stack\b|\bmevn\b|\bweb\s+(developer|engineer)\b"),
    ("frontend", r"\bfront\s*-?\s*end\b|\bui\s+(developer|engineer)\b|\breact(\.?js)?\s+(developer|engineer)\b|\bangular\b|\bvue(\.?js)?\b|\bnext\.?js\b|\bjavascript\s+(developer|engineer)\b"),
    ("backend", r"\bback\s*-?\s*end\b|\bserver\s*-?\s*side\b|\b(python|java|golang|go|node(\.?js)?|django|flask|fastapi|spring|ruby|rails|php|laravel|c#|api|scala|rust|elixir)\s+(developer|engineer)\b|(?<![\w.])\.net\s+(developer|engineer)\b"),
    ("product", r"\bproduct\s+(manager|owner|management)\b|\bapm\b|\bprogram\s+manager\b"),
    ("marketing", r"\bmarketing\b|\bgrowth\b|\bseo\b|\bsem\b|\bcontent\b|\bsocial\s+media\b|\bbrand\b|\bcopywriter\b"),
    ("sde", r"\bprogrammer\s+analyst\b|\bsystems?\s+engineer\b"),   # IT-services titles, not business
    ("business", r"\bbusiness\s+(analyst|development)\b|\bsales\b|\baccount\s+(executive|manager)\b|\bbd[ea]\b|\bconsultant\b|\bstrategy\b|\bfinance\b|\banalyst\b"),
    ("operations", r"\boperations\b|\bhr\b|\bhuman\s+resources\b|\brecruit(er|ment|ing)\b|\btalent\b|\bcustomer\s+(success|support)\b|\bsupport\b|\badmin\b"),
    ("sde", r"\bsoftware\b|\bsde\b|\bswe\b|\bdeveloper\b|\bprogrammer\b|\bengineer\b|\bmember\s+of\s+technical\s+staff\b|\bmts\b|\bcoder\b"),
]
_COMPILED = [(fam, re.compile(rx, re.I)) for fam, rx in _RULES]


def title_family(title: Optional[str]) -> str:
    """The role family a job title belongs to. The title itself is kept elsewhere for display."""
    t = " ".join((title or "").replace("_", " ").split())
    for fam, rx in _COMPILED:
        if rx.search(t):
            return fam
    return "other"


def family_with_neighbours(family: str) -> set[str]:
    f = FAMILIES.get(family)
    return {family} | set(f.neighbours if f else ())


_INTERN_RE = re.compile(r"\b(intern(ship)?|trainee|apprentice)\b", re.I)
_SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|head|architect|manager)\b", re.I)
_JUNIOR_RE = re.compile(r"\b(junior|jr\.?|associate|entry[\s-]*level|fresher|graduate|new\s+grad)\b", re.I)


def is_internship(text: Optional[str]) -> bool:
    return bool(_INTERN_RE.search(text or ""))


def seniority_hint(title: Optional[str]) -> Optional[str]:
    """What a title says about level when the post gives no years: intern, junior or senior."""
    t = title or ""
    if _INTERN_RE.search(t):
        return "intern"
    if _SENIOR_RE.search(t):
        return "senior"
    if _JUNIOR_RE.search(t):
        return "junior"
    return None


# ------------------------------------------------------------------ experience bands

Band = Literal["intern", "entry", "junior", "mid", "senior", "lead"]

# Half-open intervals in years: entry is [0, 1), junior [1, 3), and so on. No gaps.
BANDS: list[tuple[str, float, Optional[float]]] = [
    ("entry", 0, 1), ("junior", 1, 3), ("mid", 3, 5), ("senior", 5, 8), ("lead", 8, None),
]
BAND_LABEL = {"intern": "Student, internships", "entry": "0 to 1 year", "junior": "1 to 3 years",
              "mid": "3 to 5 years", "senior": "5 to 8 years", "lead": "8 years and more"}
OPEN_ENDED_SPAN = 2.0      # "3+ years" is read as 3 to 5 for banding


def band_for_years(years: Optional[float], stage: Optional[str] = None) -> str:
    """A person's band: students looking for internships are 'intern' whatever their years."""
    if stage == "student":
        return "intern"
    y = max(0.0, float(years or 0))
    for name, lo, hi in BANDS:
        if y >= lo and (hi is None or y < hi):
            return name
    return "lead"


def bands_for_range(exp_min: Optional[float], exp_max: Optional[float],
                    employment_type: Optional[str] = None) -> list[str]:
    """Every band a post's requirement overlaps. Internships are the intern band only; a post
    that states no years is entry and junior (most posts that omit years are early-career)."""
    if employment_type == "internship":
        return ["intern"]
    if exp_min is None and exp_max is None:
        return ["entry", "junior"]
    lo = float(exp_min if exp_min is not None else 0)
    hi = float(exp_max) if exp_max is not None else lo + OPEN_ENDED_SPAN
    hi = max(hi, lo)
    return [name for name, a, b in BANDS if a <= hi and (b is None or lo < b)]


def experience_fit(years: Optional[float], exp_min: Optional[float], exp_max: Optional[float],
                   tolerance: float = 1.0) -> tuple[str, Optional[str]]:
    """How a person's years sit against a post's range: fits, stretch (up to `tolerance` short),
    under (more than that short) or over (well past the top). With a note for the user."""
    y = float(years or 0)
    if exp_min is not None and y < exp_min:
        short = exp_min - y
        note = "Asks for {:g}+ years; you have {:g}".format(exp_min, round(y, 1))
        return ("stretch" if short <= tolerance else "under"), note
    if exp_max is not None and y > exp_max + 2 * tolerance:
        return "over", "Asks for up to {:g} years; you have {:g}".format(exp_max, round(y, 1))
    return "fits", None


# ------------------------------------------------------------------ years from work periods

_MONTHS = {m: i for i, ms in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
     ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
     ("oct", "october"), ("nov", "november"), ("dec", "december")], start=1) for m in ms}
_NOW_RE = re.compile(r"\b(present|current|now|till\s+date|to\s+date|ongoing|today)\b", re.I)
_SEPARATORS = [re.compile(r"\s*[–—]\s*"), re.compile(r"\s+-\s+"), re.compile(r"\s+(?:to|till|until)\s+", re.I)]


def _point(text: str, today: date) -> Optional[int]:
    """A month as a single integer (year * 12 + month - 1), or None."""
    s = text.strip().lower().rstrip(".")
    if _NOW_RE.search(s):
        return today.year * 12 + today.month - 1
    m = re.search(r"\b([a-z]{3,9})\.?\s*'?(\d{2}|\d{4})\b", s)
    if m and m.group(1) in _MONTHS:
        y = int(m.group(2))
        y = y + 2000 if y < 100 else y
        return y * 12 + _MONTHS[m.group(1)] - 1
    m = re.search(r"\b(\d{1,2})\s*[/.]\s*(\d{4})\b", s) or None
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)) * 12 + int(m.group(1)) - 1
    m = re.search(r"\b(\d{4})\s*[-/.]\s*(\d{1,2})\b", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)) * 12 + int(m.group(2)) - 1
    m = re.search(r"\b(19|20)(\d{2})\b", s)
    if m:
        return int(m.group(0)) * 12 + 5          # a bare year: count from mid-year, no more
    return None


def _split_period(s: str, today: date) -> list[str]:
    """Split a period at its separator. A bare hyphen is also part of dates ('2022-01'), so it
    only counts as one when both sides read as dates ('2021-2023', 'Jan 2022-Present')."""
    for rx in _SEPARATORS:
        parts = rx.split(s, maxsplit=1)
        if len(parts) == 2 and all(p.strip() for p in parts):
            return parts
    for i, ch in enumerate(s):
        if ch == "-" and _point(s[:i], today) is not None and _point(s[i + 1:], today) is not None \
                and not re.fullmatch(r"\s*\d{1,2}\s*", s[i + 1:]):
            return [s[:i], s[i + 1:]]
    return [s]


def period_span(period: Optional[str], today: date) -> Optional[tuple[int, int]]:
    """'Jan 2022 – Present' -> (start, end) months, both inclusive. None if unreadable."""
    if not period:
        return None
    parts = _split_period(period.strip(), today)
    if len(parts) == 1:
        start = _point(parts[0], today)
        return (start, start) if start is not None else None
    start, end = _point(parts[0], today), _point(parts[1], today)
    if start is None or end is None or end < start:
        return None
    return start, end


def years_of_experience(periods: list[Optional[str]], today: Optional[date] = None) -> float:
    """Full-time years from work periods: overlapping jobs count once. The caller leaves out
    internships and projects."""
    today = today or date.today()
    spans = sorted(s for s in (period_span(p, today) for p in periods) if s)
    months, cur = 0, None
    for a, b in spans:
        if cur and a <= cur[1] + 1:
            cur = (cur[0], max(cur[1], b))
            continue
        if cur:
            months += cur[1] - cur[0] + 1
        cur = (a, b)
    if cur:
        months += cur[1] - cur[0] + 1
    return round(months / 12, 1)


# ------------------------------------------------------------------ skills

_SKILL_ALIASES = {
    "react": "React", "reactjs": "React", "react.js": "React", "react js": "React",
    "next": "Next.js", "nextjs": "Next.js", "next.js": "Next.js",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "node js": "Node.js",
    "express": "Express", "expressjs": "Express", "express.js": "Express",
    "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js", "angularjs": "Angular",
    "js": "JavaScript", "javascript": "JavaScript", "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python3": "Python", "golang": "Go", "go": "Go", "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#", ".net": ".NET", "dotnet": ".NET",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "psql": "PostgreSQL",
    "mysql": "MySQL", "mongo": "MongoDB", "mongodb": "MongoDB", "redis": "Redis",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes", "docker": "Docker",
    "aws": "AWS", "amazon web services": "AWS", "gcp": "Google Cloud", "google cloud platform": "Google Cloud",
    "azure": "Azure", "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning", "nlp": "NLP", "llm": "LLMs", "llms": "LLMs", "genai": "Generative AI",
    "gen ai": "Generative AI", "rag": "RAG", "langchain": "LangChain",
    "tensorflow": "TensorFlow", "tf": "TensorFlow", "pytorch": "PyTorch", "torch": "PyTorch",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn", "scikit-learn": "scikit-learn",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "spring boot": "Spring Boot",
    "springboot": "Spring Boot", "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS", "html5": "HTML", "html": "HTML", "css3": "CSS", "css": "CSS",
    "git": "Git", "github": "GitHub", "ci/cd": "CI/CD", "cicd": "CI/CD", "rest": "REST APIs",
    "rest api": "REST APIs", "rest apis": "REST APIs", "restful apis": "REST APIs",
    "graphql": "GraphQL", "sql": "SQL", "power bi": "Power BI", "powerbi": "Power BI",
    "excel": "Excel", "ms excel": "Excel", "tableau": "Tableau", "spark": "Apache Spark",
    "pyspark": "PySpark", "apache spark": "Apache Spark", "kafka": "Kafka", "apache kafka": "Kafka",
    "airflow": "Airflow", "apache airflow": "Airflow", "linux": "Linux", "figma": "Figma",
    "flutter": "Flutter", "react native": "React Native", "kotlin": "Kotlin", "swift": "Swift",
    "java": "Java", "opencv": "OpenCV", "celery": "Celery", "prisma": "Prisma",
}


def skill_key(name: str) -> str:
    """A comparison key: case, spacing and trailing punctuation do not matter."""
    return re.sub(r"\s+", " ", (name or "").strip().lower().rstrip(".,;:"))


# Canonical names are their own aliases ("python" is Python, "pytorch" is PyTorch).
_CANONICAL = {re.sub(r"\s+", " ", v.lower()): v for v in _SKILL_ALIASES.values()}


def canonical_skill(name: str) -> str:
    """The name a skill is stored and shown under. Unknown skills keep the user's own spelling."""
    k = skill_key(name)
    return (_SKILL_ALIASES.get(k) or _SKILL_ALIASES.get(k.replace(" ", "")) or _CANONICAL.get(k)
            or " ".join(name.split()))


def same_skill(a: str, b: str) -> bool:
    return skill_key(canonical_skill(a)) == skill_key(canonical_skill(b))


def skill_spellings(name: str) -> set[str]:
    """Every spelling of a skill the alias table knows: 'ReactJS' -> react, reactjs, react.js,
    react js. A skill outside the table has its own spelling only."""
    canon = canonical_skill(name)
    return {k for k, v in _SKILL_ALIASES.items() if v == canon} | {skill_key(name), skill_key(canon)}
