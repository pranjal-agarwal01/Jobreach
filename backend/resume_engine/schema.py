"""
Resume data schema v3: the generalised form of the reference pipeline's schema v2.

v2 was one person's CV: exactly four tracks, a single "Projects" section on the left,
and awards / other roles hard-wired on the right. v3 keeps the same rendered format
but allows any number of tracks, items, bullets and right-column sections, and every
bullet or entry names the fact-bank ids it was built from.

Rule carried over from v2: resume lines are *selected* from confirmed facts, never
invented. `validate_fact_refs` is the check that enforces it.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 3


class Link(BaseModel):
    text: str
    url: str


class Contact(BaseModel):
    name: str
    location: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    social: list[Link] = Field(default_factory=list)


class Fact(BaseModel):
    """One true, user-confirmed statement. Only confirmed facts may reach a resume."""
    id: str
    kind: Literal["project", "role", "award", "education", "skill", "metric", "other"]
    text: str
    confirmed: bool = False
    source: str = "upload"


class Bullet(BaseModel):
    id: str
    text: str
    fact_ids: list[str] = Field(default_factory=list)


class Item(BaseModel):
    """A left-column block: a project, an internship, a job. Rendered identically."""
    id: str
    kind: Literal["project", "experience"] = "project"
    name: str
    tagline: Optional[str] = None
    links: list[Link] = Field(default_factory=list)
    period: Optional[str] = None
    stack: Optional[str] = None
    stack_label: str = "Stack"
    bullets: list[Bullet] = Field(default_factory=list)


class Entry(BaseModel):
    """A right-column bullet line. `lead` renders bold ahead of `text`."""
    id: str
    text: str
    lead: Optional[str] = None
    tracks: Optional[list[str]] = None  # None = every track
    fact_ids: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """A right-column bullet section after Education, e.g. awards or other roles.

    style "list" is for one-line entries (awards, certifications) and spaces them a
    little tighter; "detail" is for entries with a bold lead (roles).
    """
    id: str
    heading: str
    style: Literal["list", "detail"] = "detail"
    entries: list[Entry] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: Optional[str] = None
    meta: Optional[str] = None
    result: Optional[str] = None
    lines: list[str] = Field(default_factory=list)


class SkillGroup(BaseModel):
    label: str
    items: str


class LeftSection(BaseModel):
    heading: str
    item_ids: list[str]


class Track(BaseModel):
    key: str
    label: str
    title_line: str
    summary: str = ""
    left_sections: list[LeftSection]
    skills: list[SkillGroup] = Field(default_factory=list)
    scale: Optional[float] = None  # calibrated largest one-page scale; None = not yet calibrated


class ResumeData(BaseModel):
    schema_version: int = SCHEMA_VERSION
    contact: Contact
    items: dict[str, Item]
    education: list[Education] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    tracks: dict[str, Track]
    facts: list[Fact] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "ResumeData":
        for key, track in self.tracks.items():
            if track.key != key:
                raise ValueError(f"track key mismatch: {key!r} holds track {track.key!r}")
            for sec in track.left_sections:
                missing = [i for i in sec.item_ids if i not in self.items]
                if missing:
                    raise ValueError(f"track {key}: unknown item id(s) {missing}")
        for item_id, item in self.items.items():
            if item.id != item_id:
                raise ValueError(f"item key mismatch: {item_id!r} holds item {item.id!r}")
        return self


class BuildOptions(BaseModel):
    """Per-build tailoring. Everything here selects or orders; nothing adds content."""
    track: str
    left_sections: Optional[list[LeftSection]] = None  # override the track's item order
    drop: set[str] = Field(default_factory=set)        # ids of items, bullets or entries to omit
    scale: Optional[float] = None                      # override the track's calibrated scale


def validate_fact_refs(data: ResumeData, require_refs: bool = True) -> list[str]:
    """Return problems with fact references. Empty list means every line traces to a
    confirmed fact. With require_refs, a bullet or entry that cites no fact is a problem."""
    facts = {f.id: f for f in data.facts}
    problems: list[str] = []

    def check(where: str, fact_ids: list[str]) -> None:
        if not fact_ids and require_refs:
            problems.append(f"{where}: cites no fact")
        for fid in fact_ids:
            fact = facts.get(fid)
            if fact is None:
                problems.append(f"{where}: unknown fact {fid!r}")
            elif not fact.confirmed:
                problems.append(f"{where}: fact {fid!r} is not confirmed")

    for item in data.items.values():
        for b in item.bullets:
            check(f"bullet {b.id}", b.fact_ids)
    for sec in data.sections:
        for e in sec.entries:
            check(f"entry {e.id}", e.fact_ids)
    return problems
