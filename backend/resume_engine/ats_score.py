"""
JD-independent ATS score out of 100: parseability, contact completeness, recognised
section headings, date hygiene, content quality, skills coverage, and length.

Ported from the reference pipeline. It is ADVICE shown to the user, never a reason to
invent content. About 9 points of the two-column format's gap to a single-column
resume are structural and permanent.

Known bias, carried over: HARD_SKILLS and the contact checks were written for an
Indian software-engineering CV. Scores for other fields will read low on skills
coverage until those lists are generalised.
"""
from __future__ import annotations

import re
import sys
import zipfile
from dataclasses import dataclass

from docx import Document

ACTION_VERBS = {
    "built", "created", "designed", "developed", "engineered", "delivered", "shipped",
    "automated", "implemented", "indexed", "combined", "added", "owned", "ran", "chose",
    "fine-tuned", "tuned", "reduced", "improved", "led", "migrated", "deployed", "scaled",
    "optimized", "optimised", "architected", "wrote", "integrated", "launched", "cut",
    "self-hosted", "tackled", "benchmarked", "instrumented", "refactored", "profiled",
    "achieved", "generated", "produced", "handled", "maintained", "packaged", "drove",
    "suppressed", "evaluated", "measured", "removed",
    "eliminated", "stabilized", "stabilised", "sustained", "replaced", "split",
    "converted", "hardened", "abstracted", "tracked", "validated", "prevented",
    "isolated", "lifted", "selected", "normalized", "normalised", "scripted",
    "held", "made", "fused", "masked", "restructured", "consolidated", "unified",
    "fit", "fitted", "prepared", "fixed", "solved", "detected", "trained",
}
WEAK_OPENERS = {
    "responsible", "worked", "helped", "assisted", "participated", "involved",
    "tasked", "duties", "various", "successfully",
}
PRONOUNS = re.compile(r"\b(i|me|my|we|our|us)\b", re.I)
STD_HEADINGS = {
    "skills": ("skills", "technical skills"),
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "projects": ("projects", "personal projects"),
    "education": ("education",),
    "certificates": ("certificates", "certifications"),
    "achievements": ("achievements", "awards", "honors", "accomplishments"),
    "summary": ("summary", "professional summary", "profile"),
}
HEADING_WEIGHTS = {"skills": 3, "experience": 3.5, "education": 3.5, "projects": 2.5,
                   "certificates": 1, "achievements": 1, "summary": 0.5}

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
DASH = r"[-–—]"
DATE_RANGE = re.compile(
    r"{m}\s+\d{{4}}\s*{d}\s*(?:{m}\s+\d{{4}}|Present|Expected\s+{m}\s+\d{{4}})".format(m=MONTH, d=DASH),
    re.I)

# Tokens that contain digits but quantify nothing.
NOT_A_METRIC = re.compile(
    r"\b(?:yolov?\d+|yolo\d+|crc\d+|utf-?\d+|sha\d+|md5|base64|oauth\s?\d|"
    r"kitti|nanoid|jwt|bcrypt|gpt-?\d|claude\s?\d|llama\s?\d|s3|ec2|http/?\d)\b", re.I)
METRIC = re.compile(
    r"(?:~|\+|<|>)?\d[\d,\.]*\s*[-–]?\s*(?:%|x\b|k\b|hrs?\b|hours?\b|days?\b|weeks?\b|"
    r"months?\b|years?\b|pages?\b|clients?\b|users?\b|trials?\b|sites?\b|teams?\b|rps\b|qps\b|"
    r"fps\b|ms\b|seconds?\b|lpa\b|orders?\b|images?\b|classes?\b|digests?\b|links?\b|files?\b|"
    r"queries\b|query\b|questions?\b|requests?\b|records?\b|rows?\b|problems?\b|epochs?\b|"
    r"checks?\b|items?\b|calls?\b|frames?\b|feeds?\b|sources?\b|models?\b|stages?\b)"
    r"|\b(?:rank|top)\s+\d+\b|\b\d+\s*(?:of|/)\s*\d+\b|\bmap\s*\d*\s*[:=]?\s*[\d\.]+"
    # "from 0.61 to 0.84": a before/after improvement carries no unit.
    r"|\bfrom\s+\d[\d\.]*\s+to\s+\d[\d\.]*\b",
    re.I)

HARD_SKILLS = [
    "python", "java", "javascript", "sql", "react", "node", "express", "fastapi", "flask",
    "mongodb", "mysql", "docker", "git", "rest", "pytorch", "opencv", "yolo", "numpy",
    "pandas", "langchain", "rag", "pinecone", "n8n", "github actions", "scikit-learn",
    "optuna", "tailwind", "postman", "claude api",
]
STANDARD_FONTS = {"Calibri", "Arial", "Helvetica", "Times New Roman", "Georgia",
                  "Garamond", "Cambria", "Verdana"}


@dataclass
class ScoreRow:
    category: str
    points: float
    max_points: float
    note: str


def is_two_column_layout(doc) -> bool:
    """True for the builder's CV: exactly one table, one row, two cells. That shape is a
    layout frame, not a data table; docx parsers read it cleanly cell by cell."""
    return (len(doc.tables) == 1
            and len(doc.tables[0].rows) == 1
            and len(doc.tables[0].columns) == 2)


def all_paragraphs(doc, left_only: bool = False):
    """Body paragraphs, then table cells column by column: the order a docx-aware ATS
    reads them in. With left_only, only the first cell of each row."""
    paras = list(doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for i, cell in enumerate(row.cells):
                if not left_only or i == 0:
                    paras.extend(cell.paragraphs)
    return paras


def docx_text(path) -> str:
    return "\n".join(p.text for p in all_paragraphs(Document(path)))


def _load(path):
    doc = Document(path)
    paras = all_paragraphs(doc)
    # `main` is the left column only: the project bullets the content-quality test is
    # about. The right column holds awards and roles, a different genre of line.
    main = all_paragraphs(doc, left_only=True)
    texts = [p.text.strip() for p in paras if p.text.strip()]
    main_texts = [p.text.strip() for p in main if p.text.strip()]
    if not is_two_column_layout(doc):
        main_texts = texts
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    return doc, paras, texts, main_texts, z, xml


def _heading_paras(paras):
    """Section headings are the bold ALL-CAPS runs the builder emits."""
    out = []
    for p in paras:
        t = p.text.strip()
        if t and len(t) <= 30 and t.isupper() and any(r.bold for r in p.runs):
            out.append(t.lower())
    return out


def score(path) -> tuple[float, list[ScoreRow]]:
    doc, paras, texts, main_texts, z, xml = _load(path)
    names = z.namelist()
    heads = _heading_paras(paras)
    two_col = is_two_column_layout(doc)
    bl = [t.lstrip("• ").strip() for t in main_texts if t.startswith("•")]
    body = "\n".join(texts)
    low = body.lower()
    rows: list[ScoreRow] = []

    def add(cat, got, mx, note):
        rows.append(ScoreRow(cat, max(0.0, round(got, 1)), mx, note))

    # ---- 1. Parseability (25) ----
    pts, notes = 25.0, []
    if two_col:
        # Clean in .docx; pdftotext on this layout interleaves the columns mid-sentence,
        # so the product delivers .docx, never a PDF of it.
        pts -= 4
        notes.append("2-col layout table - clean in .docx, INTERLEAVES if exported to PDF")
    elif doc.tables:
        pts -= 10
        notes.append("%d table(s) - ATS reads cells out of order" % len(doc.tables))
    if "<w:txbxContent" in xml:
        pts -= 8
        notes.append("text box present - often dropped entirely")
    if any(n.startswith("word/media/") for n in names):
        pts -= 5
        notes.append("embedded image")
    live_hdr = []
    for n in names:
        if re.match(r"word/(header|footer)\d*\.xml$", n):
            if re.search(r"<w:t[ >]", z.read(n).decode("utf-8", "replace")):
                live_hdr.append(n)
    if live_hdr:
        pts -= 6
        notes.append("text in Word header/footer - many parsers skip it")
    if re.search(r'<w:cols[^>]*w:num="[2-9]"', xml):
        pts -= 12
        notes.append("multi-column layout")
    fonts = set(re.findall(r'w:ascii="([^"]+)"', xml))
    odd = fonts - STANDARD_FONTS
    if odd:
        pts -= 3
        notes.append("non-standard font(s): %s" % ", ".join(sorted(odd)))
    add("Parseability", pts, 25,
        "; ".join(notes) or "single column, no tables/boxes/images, contact in body text")

    # ---- 2. Contact completeness (10) ----
    pts, missing = 0.0, []
    checks = [
        ("email", r"[\w\.\-]+@[\w\.\-]+\.\w+", 2.5),
        ("phone", r"(?:\+91[\s\-]?)?\d{10}", 2.5),
        ("location", r"[A-Z][a-z]+,\s*[A-Z][a-z]+", 1.5),
        ("linkedin", r"linkedin\.com/in/", 1.5),
        ("github", r"github\.com/", 1.0),
        ("portfolio/code-profile", r"vercel\.app|leetcode\.com|codolio\.com", 1.0),
    ]
    for name, rx, w in checks:
        if re.search(rx, body, re.I):
            pts += w
        else:
            missing.append(name)
    # In the two-column format the contact block opens the right cell, so it lands
    # mid-document in reading order. Clearly labelled, so a smaller penalty.
    contact_window = 5 if not two_col else 40
    if not re.search(r"[\w\.\-]+@[\w\.\-]+", "\n".join(texts[:contact_window])):
        pts -= 2
        missing.append("contact not in top block")
    elif two_col and not re.search(r"[\w\.\-]+@[\w\.\-]+", "\n".join(texts[:5])):
        pts -= 1
        missing.append("contact in 2nd column, not the top block")
    add("Contact block", pts, 10,
        ("missing: " + ", ".join(missing)) if missing else "all fields present, in body text")

    # ---- 3. Section headings (15) ----
    # Containment, not equality: "AWARDS & CERTIFICATIONS" satisfies both keys.
    pts, found, absent = 0.0, [], []
    for key, aliases in STD_HEADINGS.items():
        if any(any(a in h for a in aliases) for h in heads):
            pts += HEADING_WEIGHTS[key]
            found.append(key)
        else:
            absent.append(key)
    add("Section headings", pts, 15,
        "found: %s%s" % (", ".join(found), ("; absent: " + ", ".join(absent)) if absent else ""))

    # ---- 4. Dates (10) ----
    pts, notes = 0.0, []
    dated = len(DATE_RANGE.findall(body))
    if dated >= 6:
        pts += 5
    elif dated >= 3:
        pts += 3.5
        notes.append("only %d parseable MMM YYYY ranges" % dated)
    else:
        notes.append("too few parseable date ranges (%d)" % dated)
    if re.search(r"Expected\s+(?:%s\s+)?\d{4}" % MONTH, body, re.I):
        pts += 3
    else:
        notes.append("no explicit 'Expected <Month Year>' graduation date")
    stray = sorted(set(re.findall(r"\b\d{1,2}/\d{2,4}\b", body)))
    if stray:
        notes.append("mixed date formats: %s" % ", ".join(stray[:3]))
    else:
        pts += 2
    add("Dates", pts, 10,
        "; ".join(notes) or "%d clean MMM YYYY ranges, explicit graduation date" % dated)

    # ---- 5. Content quality (20) ----
    pts, notes = 0.0, []
    n = len(bl)
    if 10 <= n <= 22:
        pts += 4
    elif n:
        pts += 2
        notes.append("%d bullets (10-22 is the sweet spot)" % n)
    starts = [b.split()[0].lower().strip(",:") for b in bl if b.split()]
    verb_hits = sum(1 for s in starts if s in ACTION_VERBS)
    vr = verb_hits / max(1, n)
    pts += 5 * min(1.0, vr / 0.9)
    if vr < 0.9:
        bad = sorted({s for s in starts if s not in ACTION_VERBS})
        notes.append("%d/%d bullets verb-led (%.0f%%); non-verb openers: %s"
                     % (verb_hits, n, vr * 100, ", ".join(bad[:5])))
    weak = sorted({s for s in starts if s in WEAK_OPENERS})
    if weak:
        pts -= 2
        notes.append("weak openers: %s" % ", ".join(weak))
    quant = [b for b in bl if METRIC.search(NOT_A_METRIC.sub(" ", b))]
    qr = len(quant) / max(1, n)
    pts += 6 * min(1.0, qr / 0.40)          # 40% quantified = full marks (industry benchmark)
    if qr < 0.40:
        notes.append("%d/%d bullets carry a metric (%.0f%%; benchmark is 40%%)"
                     % (len(quant), n, qr * 100))
    lens = [len(b.split()) for b in bl]
    ok_len = sum(1 for L in lens if 8 <= L <= 34)
    pts += 3 * (ok_len / max(1, n))
    if ok_len < n:
        notes.append("%d bullet(s) outside 8-34 words" % (n - ok_len))
    if PRONOUNS.search(" ".join(bl)):
        pts -= 2
        notes.append("first-person pronouns present")
    else:
        pts += 2
    add("Content quality", pts, 20,
        "; ".join(notes) or "verb-led, quantified, well-sized bullets")

    # ---- 6. Skills coverage (15) ----
    pts, notes = 0.0, []
    hits = [s for s in HARD_SKILLS if s in low]
    if len(hits) >= 18:
        pts += 7
    elif len(hits) >= 12:
        pts += 5.5
        notes.append("%d hard skills surfaced" % len(hits))
    else:
        pts += 3
        notes.append("only %d hard skills surfaced" % len(hits))
    if any(h in STD_HEADINGS["skills"] for h in heads):
        pts += 4
    else:
        notes.append("no dedicated skills section")
    bullet_text = " ".join(bl).lower()
    echoed = [s for s in hits if s in bullet_text]
    er = len(echoed) / max(1, len(hits))
    pts += 4 * min(1.0, er / 0.45)
    if er < 0.45:
        notes.append("only %.0f%% of listed skills are evidenced in a bullet" % (er * 100))
    add("Skills coverage", pts, 15,
        "; ".join(notes) or "%d skills listed, %d evidenced in bullets" % (len(hits), len(echoed)))

    # ---- 7. Length (5) ----
    words = len(body.split())
    ceiling = 950 if two_col else 800
    if 380 <= words <= ceiling:
        add("Length", 5.0, 5, "%d words, one page" % words)
    elif words < 380:
        add("Length", 3.0, 5, "%d words - thin for a full page" % words)
    else:
        add("Length", 3.0, 5, "%d words - risks spilling to page 2" % words)

    return sum(r.points for r in rows), rows


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not paths:
        sys.exit(__doc__)
    for path in paths:
        total, rows = score(path)
        band = "STRONG" if total >= 85 else ("OK" if total >= 75 else "NEEDS WORK")
        print("\n%s\n  ATS SCORE: %.1f/100   [%s]" % (path, total, band))
        for r in rows:
            filled = int(round(12 * r.points / r.max_points))
            bar = "#" * filled + "." * (12 - filled)
            print("    %-18s %5.1f/%-3s %s  %s" % (r.category, r.points, r.max_points, bar, r.note))
    print("")


if __name__ == "__main__":
    main()
