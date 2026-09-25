"""
Per-application keyword coverage: does this resume use the JD's own words?

ats_score.py is JD-independent. This is the other half: literal term overlap, which
is what keyword-matching ATS rank on. Advice for the user, never a reason to add a
term the fact bank does not back.

Fix over the reference version: it read only body-level paragraphs, which in the
two-column layout is empty (every line lives inside the layout table), so it
reported near-zero coverage for every schema-v2 resume. This reads the table cells.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Iterable

from .ats_score import docx_text

STOP = set("""a an the and or but if then than that this these those of in on at to for with by from
as is are was were be been being it its into over under about above below not no yes you your our we
us they them their he she his her i me my will would can could should may might must have has had do
does did done make made get got go goes going new more most other some any all both each few many minimum requirements preferred qualifications responsibilities through knowledge ability
abilities demonstrating capacity unfamiliar independent related field strong foundational master
masters phd bachelor bachelors degree side coursework prior multi-person receive seeking
incorporating efficiently questioning status equivalent specialized balanced general navigate
across including include such well also within e.g i.e per plus
who whom which what when where why how work working works experience role team intern
internship job apply application candidate candidates you'll we're etc via using use used""".split())

TOP_TERMS = 45


@dataclass
class MatchResult:
    covered: list[tuple[str, int]]
    missing: list[tuple[str, int]]

    @property
    def coverage(self) -> float:
        total = len(self.covered) + len(self.missing)
        return len(self.covered) / total if total else 0.0


def _words(text: str, stop: set[str]) -> list[str]:
    # Dots stay inside a term ("node.js") but not at its edge: the reference version
    # kept sentence-final periods, so "Kubernetes." never matched "Kubernetes".
    words = (w.strip(".-/") for w in re.findall(r"[a-z0-9\+#\.\-/]{2,}", text.lower()))
    return [w for w in words if len(w) >= 2 and w not in stop]


def match_text(resume_text: str, jd_text: str, extra_stop: Iterable[str] = ()) -> MatchResult:
    """`extra_stop`: words to ignore, e.g. the company's own name."""
    stop = STOP | {w.lower() for w in extra_stop}
    resume = resume_text.lower()
    freq: dict[str, int] = {}
    for w in _words(jd_text, stop):
        freq[w] = freq.get(w, 0) + 1
    terms = sorted(freq.items(), key=lambda kv: -kv[1])[:TOP_TERMS]
    covered, missing = [], []
    for w, c in terms:
        stem = w.rstrip("s")
        (covered if (w in resume or stem in resume) else missing).append((w, c))
    return MatchResult(covered, missing)


def match_docx(resume_path, jd_text: str, extra_stop: Iterable[str] = ()) -> MatchResult:
    return match_text(docx_text(resume_path), jd_text, extra_stop)


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python -m resume_engine.jd_match <resume.docx> <jd.txt>")
    with open(sys.argv[2], encoding="utf-8") as f:
        r = match_docx(sys.argv[1], f.read())
    n = len(r.covered) + len(r.missing)
    print("JD terms covered: {}/{}  ({:.0f}%)".format(len(r.covered), n, 100.0 * r.coverage))
    print("\nCOVERED  :", ", ".join(w for w, _ in r.covered))
    print("\nMISSING  (JD says it, resume doesn't):")
    for w, c in r.missing:
        print("   {:<22} x{}".format(w, c))


if __name__ == "__main__":
    main()
