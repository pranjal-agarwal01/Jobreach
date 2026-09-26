"""
S5: choose the track, the item order and the bullets for one lead (spec 5.5). Selection
and ordering only: the model returns ids, and code discards any id that is not one of the
user's confirmed bullets, items or entries.

This call also returns the fit score used to rank leads (spec 5.3's model ranking), so a
pasted lead costs one model call here rather than two.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from resume_engine.schema import BuildOptions, LeftSection, ResumeData

from .. import llm
from . import prompts
from .schemas import Extracted, Selection

MIN_BULLETS_PER_ITEM = 2


@dataclass
class Chosen:
    selection: Selection
    opts: BuildOptions
    bullet_order: list[str]
    notes: list[str] = field(default_factory=list)


def candidate_context(data: ResumeData) -> str:
    """Per-user, stable across leads: forms the cached part of the S5 prompt."""
    return llm.dumps({
        "tracks": [{"key": t.key, "label": t.label, "title_line": t.title_line,
                    "left_sections": [{"heading": s.heading, "item_keys": s.item_ids} for s in t.left_sections]}
                   for t in data.tracks.values()],
        "items": [{"key": it.id, "kind": it.kind, "name": it.name, "tagline": it.tagline,
                   "stack": it.stack, "bullets": [{"id": b.id, "text": b.text} for b in it.bullets]}
                  for it in data.items.values()],
        "entries": [{"id": e.id, "section": s.heading, "text": (e.lead or "") + e.text}
                    for s in data.sections for e in s.entries],
    })


def select(data: ResumeData, ex: Extracted, raw_text: str, ctx: llm.CallContext) -> Chosen:
    volatile = "Lead (extracted):\n{}\n\n<post>\n{}\n</post>".format(
        llm.dumps(ex.model_dump()), raw_text[:12000])
    sel = llm.structured("s5_select", Selection,
                         stable=[prompts.SELECT, "Candidate:\n" + candidate_context(data)],
                         volatile=volatile, effort="medium", max_tokens=4000, ctx=ctx)
    return validate(data, sel)


def validate(data: ResumeData, sel: Selection) -> Chosen:
    notes = []
    if sel.track_key not in data.tracks:
        notes.append("Model chose unknown track {!r}; used {!r}".format(sel.track_key, next(iter(data.tracks))))
        sel = sel.model_copy(update={"track_key": next(iter(data.tracks))})
    track = data.tracks[sel.track_key]

    sections = []
    for s in sel.left_sections:
        keys = [k for k in s.item_keys if k in data.items]
        if keys:
            sections.append(LeftSection(heading=s.heading, item_ids=keys))
    if not sections:
        sections = track.left_sections
        notes.append("Model chose no valid items; used the track's default order")

    chosen_items = [k for s in sections for k in s.item_ids]
    valid_bullets = {b.id for k in chosen_items for b in data.items[k].bullets}
    keep = [b for b in sel.bullet_ids if b in valid_bullets]
    dropped_unknown = [b for b in sel.bullet_ids if b not in valid_bullets]
    if dropped_unknown:
        notes.append("Ignored {} bullet id(s) that are not confirmed bullets".format(len(dropped_unknown)))

    # Never leave an item with fewer than two bullets: restore its first ones.
    for k in chosen_items:
        ids = [b.id for b in data.items[k].bullets]
        kept = [b for b in ids if b in keep]
        if len(kept) < min(MIN_BULLETS_PER_ITEM, len(ids)):
            for b in ids:
                if b not in keep and len(kept) < MIN_BULLETS_PER_ITEM:
                    keep.append(b)
                    kept.append(b)

    all_entries = {e.id for s in data.sections for e in s.entries}
    drop = {b for k in chosen_items for b in (x.id for x in data.items[k].bullets) if b not in keep}
    drop |= {e for e in sel.drop_entry_ids if e in all_entries}
    opts = BuildOptions(track=sel.track_key, left_sections=sections, drop=drop)
    return Chosen(selection=sel, opts=opts, bullet_order=keep, notes=notes)
