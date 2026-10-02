"""
S5: tailor one baseline to one opening (spec 5.5; docs/plan-global-pool.md, A). Code chooses
the baseline from the match (the person's resume for that kind of role). The model selects and
orders the person's own record and writes a short summary; code then

  - discards any id that is not one of the person's usable bullets, items or entries,
  - keeps at least two bullets on every item,
  - moves the skills the opening asks for to the front, without adding any,
  - holds the summary to the person's documents (a sentence carrying a number or tool they
    lack is removed; nothing left means the baseline's summary),
  - builds the title line from the post's role, never with a seniority the record lacks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from resume_engine.schema import BuildOptions, LeftSection, ResumeData, SkillGroup, Track

from .. import llm
from ..provenance import Corpus, drop_unbacked_sentences
from ..taxonomy import canonical_skill, skill_key
from . import prompts
from .schemas import Extracted, Selection

MIN_BULLETS_PER_ITEM = 2
TITLE_SEP = re.compile(r"\s+[·|•–—-]\s+")
LEVEL_WORDS = re.compile(r"\b(intern(ship)?s?|trainee|apprentice(ship)?|fresher|freshers|i{1,3}|iv|[1-4]|l[1-4])\b",
                         re.I)
SENIORITY = re.compile(r"\b(senior|sr|lead|staff|principal|head|chief|director|manager|vp)\b", re.I)


@dataclass
class Chosen:
    selection: Selection
    opts: BuildOptions
    bullet_order: list[str]
    track: Track                          # the tailored copy of the baseline
    notes: list[str] = field(default_factory=list)

    def resume_data(self, data: ResumeData) -> ResumeData:
        """The person's record with this tailored baseline in place of the original."""
        return data.model_copy(update={"tracks": {**data.tracks, self.track.key: self.track}})


def candidate_context(data: ResumeData) -> str:
    """Per-person, stable across openings: forms the cached part of the S5 prompt."""
    return llm.dumps({
        "items": [{"key": it.id, "kind": it.kind, "name": it.name, "tagline": it.tagline, "period": it.period,
                   "stack": it.stack, "bullets": [{"id": b.id, "text": b.text} for b in it.bullets]}
                  for it in data.items.values()],
        "entries": [{"id": e.id, "section": s.heading, "text": (e.lead or "") + e.text}
                    for s in data.sections for e in s.entries],
        "skills": [f.text for f in data.facts if f.kind == "skill"],
        "education": [{"institution": e.institution, "degree": e.degree, "meta": e.meta} for e in data.education],
    })


def baseline_view(t: Track) -> str:
    return llm.dumps({"key": t.key, "title_line": t.title_line, "summary": t.summary,
                      "left_sections": [{"heading": s.heading, "item_keys": s.item_ids} for s in t.left_sections],
                      "skills": [{"label": g.label, "items": g.items} for g in t.skills]})


def tailor(data: ResumeData, track_key: str, ex: Extracted, raw_text: str, ctx: llm.CallContext, *,
           corpus: Optional[Corpus] = None, band: Optional[str] = None,
           extra_numbers: set[str] = frozenset()) -> Chosen:
    track_key = track_key if track_key in data.tracks else next(iter(data.tracks))
    volatile = "Baseline to tailor:\n{}\n\nOpening (extracted):\n{}\n\n<post>\n{}\n</post>".format(
        baseline_view(data.tracks[track_key]), llm.dumps(ex.model_dump()), raw_text[:12000])
    sel = llm.structured("s5_select", Selection,
                         stable=[prompts.SELECT, "Person:\n" + candidate_context(data)],
                         volatile=volatile, effort="medium", max_tokens=4000, ctx=ctx)
    return validate(data, track_key, sel, corpus=corpus, band=band, extra_numbers=extra_numbers)


def reorder_skills(groups: list[SkillGroup], first: list[str]) -> list[SkillGroup]:
    """The asked-for skills first, inside their groups and across groups. Order only."""
    rank: dict[str, int] = {}
    for i, s in enumerate(first):
        rank.setdefault(skill_key(canonical_skill(s)), i)
    big = len(rank) + 1000
    out = []
    for gi, g in enumerate(groups):
        items = [x.strip() for x in g.items.split(",") if x.strip()]
        order = sorted(range(len(items)), key=lambda j: (rank.get(skill_key(canonical_skill(items[j])), big), j))
        best = min((rank.get(skill_key(canonical_skill(x)), big) for x in items), default=big)
        out.append((best, gi, g.model_copy(update={"items": ", ".join(items[j] for j in order)})))
    return [g for _, _, g in sorted(out, key=lambda t: (t[0], t[1]))]


def tailored_title(base: str, role: str, band: Optional[str]) -> str:
    """'Backend Developer · B.Tech CSE, 2027' for a 'Backend Engineer Intern (Remote)' post
    becomes 'Backend Engineer · B.Tech CSE, 2027'. The context after the separator is the
    baseline's own. Any doubt keeps the baseline's title."""
    parts = TITLE_SEP.split(base, maxsplit=1)
    if len(parts) < 2 or not role:
        return base
    r = re.sub(r"\(.*?\)|\[.*?\]", " ", role)
    r = re.split(r"\s+[-–—|@:]\s+|,|\s+at\s+", r)[0]
    if SENIORITY.search(r) and band not in ("senior", "lead"):
        return base
    r = " ".join(LEVEL_WORDS.sub(" ", r).split()).strip(" -–—,/")
    if not r or len(r.split()) > 5 or re.search(r"\d", r):
        return base
    sep = base[len(parts[0]):len(base) - len(parts[1])]
    return r + sep + parts[1]


def validate(data: ResumeData, track_key: str, sel: Selection, *, corpus: Optional[Corpus] = None,
             band: Optional[str] = None, extra_numbers: set[str] = frozenset()) -> Chosen:
    notes = []
    if track_key not in data.tracks:
        notes.append("Baseline {!r} not found; used {!r}".format(track_key, next(iter(data.tracks))))
        track_key = next(iter(data.tracks))
    track = data.tracks[track_key]

    sections = []
    for s in sel.left_sections:
        keys = [k for k in dict.fromkeys(s.item_keys) if k in data.items]
        if keys:
            sections.append(LeftSection(heading=s.heading, item_ids=keys))
    if not sections:
        sections = track.left_sections
        notes.append("Model chose no valid items; used the baseline's order")

    chosen_items = [k for s in sections for k in s.item_ids]
    valid_bullets = {b.id for k in chosen_items for b in data.items[k].bullets}
    keep = [b for b in dict.fromkeys(sel.bullet_ids) if b in valid_bullets]
    dropped_unknown = [b for b in sel.bullet_ids if b not in valid_bullets]
    if dropped_unknown:
        notes.append("Ignored {} bullet id(s) that are not usable bullets".format(len(dropped_unknown)))

    # Never leave an item with fewer than two bullets: restore its first ones.
    for k in chosen_items:
        ids = [b.id for b in data.items[k].bullets]
        kept = [b for b in ids if b in keep]
        if len(kept) < min(MIN_BULLETS_PER_ITEM, len(ids)):
            for b in ids:
                if b not in keep and len(kept) < MIN_BULLETS_PER_ITEM:
                    keep.append(b)
                    kept.append(b)

    summary = track.summary
    if corpus is not None and sel.summary.strip():
        kept_text, removed = drop_unbacked_sentences(sel.summary, corpus, extra_numbers)
        if removed:
            notes.append("Removed {} summary sentence(s) your documents do not back".format(len(removed)))
        summary = kept_text or track.summary

    tailored = track.model_copy(update={
        "title_line": tailored_title(track.title_line, sel.role_title, band),
        "summary": summary, "left_sections": sections,
        "skills": reorder_skills(track.skills, sel.skills_first)})

    all_entries = {e.id for s in data.sections for e in s.entries}
    drop = {b for k in chosen_items for b in (x.id for x in data.items[k].bullets) if b not in keep}
    drop |= {e for e in sel.drop_entry_ids if e in all_entries}
    opts = BuildOptions(track=track_key, left_sections=sections, drop=drop)
    return Chosen(selection=sel, opts=opts, bullet_order=keep, track=tailored, notes=notes)
