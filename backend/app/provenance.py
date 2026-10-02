"""
Is a line backed by what the user gave us? (docs/plan-global-pool.md, point 1)

Onboarding no longer asks the user to approve each line. Instead every line the model
extracts is checked here against the user's own documents (CVs, notes, GitHub) before it may
reach a resume:

- every number in the line appears in the documents;
- every tool or technology the line names appears in the documents;
- most of its words appear together in one passage (a window, not anywhere in the corpus:
  two-column PDFs interleave lines, so the window is wider than the line).

A line that fails is kept but marked unusable, with the reason, and the review screen lists it
under "Left out". Nothing is ever asked about it.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from .taxonomy import _SKILL_ALIASES, canonical_skill, skill_key

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#]*(?:[.\-][a-z0-9+#]+)*")
STOP = set("""a an the and or of to in for on with by at from as is are was were be been being this that
these those it its into over under via using used use my our their his her we i you he she they me
so than then also while which who whom what when where how per across about after before during up
out more most less least very just only each every all any both other such own same few s""".split())

# Ordinary words that are also tool names: not treated as tool claims inside sentences.
_AMBIGUOUS = {"go", "express", "rest", "spark", "swift", "excel", "next", "node", "react", "ts", "js",
              "py", "tf", "torch", "dl", "ml", "git", "html", "css", "sql", "flask", "java"}
_TECH_KEYS = sorted((k for k in _SKILL_ALIASES if k not in _AMBIGUOUS), key=len, reverse=True)
_TECH_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in _TECH_KEYS) + r")(?![a-z0-9])")

COVERAGE = 0.75          # share of a line's content words that one passage must contain


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = t.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                                   "−": "-", "•": " ", "·": " ", "|": " ", " ": " "}))
    return re.sub(r"\s+", " ", t).strip()


def numbers(text: str) -> set[str]:
    """Numbers as written, without thousands separators or a trailing '.0'."""
    out = set()
    for n in NUMBER_RE.findall(normalize(text)):
        n = n.replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def content_words(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize(text)) if w not in STOP and not w.isdigit()]


def tech_terms(text: str) -> set[str]:
    """The tools a line names, as canonical skill keys."""
    return {skill_key(canonical_skill(m)) for m in _TECH_RE.findall(normalize(text))}


@dataclass
class Check:
    ok: bool
    reason: Optional[str] = None
    doc: Optional[str] = None
    snippet: Optional[str] = None
    coverage: float = 0.0

    def as_json(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "doc": self.doc, "snippet": self.snippet,
                "coverage": round(self.coverage, 2)}


@dataclass
class Corpus:
    """Everything the user gave us, searchable. docs: (label, text) pairs."""
    docs: list[tuple[str, str]]
    text: str = ""
    tokens: list[str] = field(default_factory=list)
    token_doc: list[int] = field(default_factory=list)
    nums: set[str] = field(default_factory=set)
    tech: set[str] = field(default_factory=set)

    def __post_init__(self):
        parts = []
        for i, (_, body) in enumerate(self.docs):
            norm = normalize(body)
            parts.append(norm)
            words = WORD_RE.findall(norm)
            self.tokens.extend(words)
            self.token_doc.extend([i] * len(words))
        self.text = " \n ".join(parts)
        self.nums = numbers(self.text)
        self.tech = tech_terms(self.text)
        self.vocab = set(self.tokens)
        self.where: dict[str, list[int]] = {}
        for i, w in enumerate(self.tokens):
            self.where.setdefault(w, []).append(i)

    def has_phrase(self, phrase: str) -> bool:
        p = normalize(phrase)
        return bool(p) and p in self.text

    def has_tech(self, name: str) -> bool:
        key = skill_key(canonical_skill(name))
        return key in self.tech or self.has_phrase(name) or self.has_phrase(canonical_skill(name))

    def best_window(self, words: list[str]) -> tuple[float, Optional[int], Optional[int]]:
        """The passage containing most of `words`: (coverage, doc index, token start). Only
        windows around places where the line's words occur are tried."""
        want = set(words)
        if not want or not self.tokens:
            return 0.0, None, None
        if len(want & self.vocab) / len(want) < 0.5:
            return len(want & self.vocab) / len(want), None, None
        size = max(2 * len(words) + 12, 30)
        starts = sorted({max(0, p - size // 2) for w in want for p in self.where.get(w, ())[:200]})
        best, at = 0.0, 0
        for start in starts:
            got = len(want.intersection(self.tokens[start:start + size])) / len(want)
            if got > best:
                best, at = got, start
                if best == 1.0:
                    break
        return best, self.token_doc[at], at

    def snippet(self, start: Optional[int], length: int) -> Optional[str]:
        if start is None:
            return None
        return " ".join(self.tokens[start:start + max(length, 8)])[:240]


def check_line(text: str, corpus: Corpus, *, coverage: float = COVERAGE) -> Check:
    """One sentence-like line (a bullet, an award, a summary sentence)."""
    if not (text or "").strip():
        return Check(False, "Empty line")
    missing = sorted(numbers(text) - corpus.nums, key=len, reverse=True)
    if missing:
        return Check(False, "The number {} is not in anything you gave us".format(missing[0]))
    tools = [t for t in tech_terms(text) if t not in corpus.tech and not corpus.has_phrase(t)]
    if tools:
        return Check(False, "{} is not mentioned in anything you gave us".format(canonical_skill(tools[0])))
    words = content_words(text)
    if not words:
        return Check(True, coverage=1.0)
    got, doc, start = corpus.best_window(words)
    need = 1.0 if len(set(words)) <= 3 else coverage
    if got + 1e-9 < need:
        return Check(False, "We couldn't find this in anything you gave us", coverage=got)
    label = corpus.docs[doc][0] if doc is not None else None
    return Check(True, doc=label, snippet=corpus.snippet(start, 2 * len(words)), coverage=got)


def check_name(name: str, corpus: Corpus) -> Check:
    """A proper name (project, employer, institution): every word must be there, together."""
    return check_line(name, corpus, coverage=1.0)


def keep_known_tools(stack: Optional[str], corpus: Corpus) -> tuple[Optional[str], list[str]]:
    """A comma-separated stack trimmed to the tools the documents mention. Returns
    (kept stack, dropped tools)."""
    if not stack:
        return stack, []
    parts = [p.strip() for p in re.split(r"[,;/|]", stack) if p.strip()]
    kept = [p for p in parts if corpus.has_tech(p)]
    dropped = [p for p in parts if p not in kept]
    return (", ".join(kept) or None), dropped


def keep_if_numbers_known(text: Optional[str], corpus: Corpus) -> Optional[str]:
    """A period or a grade survives only if its numbers are all in the documents."""
    if not text:
        return text
    return text if numbers(text) <= corpus.nums else None


def url_key(url: str) -> str:
    u = normalize(url)
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


def has_url(url: str, corpus: Corpus) -> bool:
    k = url_key(url)
    return bool(k) and k in corpus.text


def has_contact(value: Optional[str], corpus: Corpus) -> bool:
    """Emails must appear verbatim; phone numbers by their digits."""
    if not value:
        return False
    if "@" in value:
        return normalize(value) in corpus.text
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 7 and digits[-10:] in re.sub(r"\D", "", corpus.text)


def drop_unbacked_sentences(text: str, corpus: Corpus, extra_numbers: set[str] = frozenset()) -> tuple[str, list[str]]:
    """For text the model writes (a summary): remove each sentence carrying a number or a tool
    that is not in the documents. Returns (kept text, removed sentences)."""
    sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    kept, removed = [], []
    for s in sentences:
        if not s:
            continue
        bad_num = numbers(s) - corpus.nums - set(extra_numbers)
        bad_tool = [t for t in tech_terms(s) if t not in corpus.tech]
        (removed if bad_num or bad_tool else kept).append(s)
    return " ".join(kept), removed
