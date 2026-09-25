"""
Convert the reference pipeline's schema v2 resume_data.json into schema v3.

Used only for the parity test against the original baselines. v2 files hold real
personal data and must never be used as seed or test data in a deployed environment.
"""
from __future__ import annotations

from .schema import (
    Bullet, Contact, Education, Entry, Fact, Item, LeftSection, Link, ResumeData,
    Section, SkillGroup, Track,
)


def from_v2(v2: dict) -> ResumeData:
    facts: list[Fact] = []

    def fact(fid: str, kind: str, text: str) -> str:
        # v2 bullets were all taken from CVs the user wrote, so they count as confirmed.
        facts.append(Fact(id=fid, kind=kind, text=text, confirmed=True, source="v2-import"))
        return fid

    c = v2["contact"]
    contact = Contact(
        name=c["name"], location=c.get("location"), phone=c.get("phone"),
        email=c.get("email"), social=[Link(**s) for s in c.get("social", [])],
    )

    items: dict[str, Item] = {}
    for pid, p in v2["projects"].items():
        bullets = []
        for i, text in enumerate(p["bullets"], start=1):
            bid = "{}.b{}".format(pid, i)
            bullets.append(Bullet(id=bid, text=text, fact_ids=[fact("f." + bid, "project", text)]))
        items[pid] = Item(
            id=pid, kind="project", name=p["name"], tagline=p.get("tagline"),
            links=[Link(**lk) for lk in p.get("links", [])], period=p.get("period"),
            stack=p.get("stack"), bullets=bullets,
        )

    awards = []
    for i, a in enumerate(v2.get("awards", []), start=1):
        eid = "aw{}".format(i)
        awards.append(Entry(id=eid, text=a["text"], tracks=a.get("tracks"),
                            fact_ids=[fact("f." + eid, "award", a["text"])]))
    roles = []
    for r in v2.get("other_roles", []):
        roles.append(Entry(id=r["id"], lead=r.get("lead"), text=r["text"], tracks=r.get("tracks"),
                           fact_ids=[fact("f." + r["id"], "role", (r.get("lead") or "") + r["text"])]))
    sections = [
        Section(id="awards", heading="Awards & Certifications", style="list", entries=awards),
        Section(id="other_roles", heading="Other Roles & Responsibilities", style="detail",
                entries=roles),
    ]

    labels = v2.get("_tracks", {})
    scales = v2.get("scale", {})
    tracks = {}
    for key, title in v2["titles"].items():
        tracks[key] = Track(
            key=key, label=labels.get(key, key), title_line=title,
            summary=v2["summary"].get(key, ""),
            left_sections=[LeftSection(heading="Projects", item_ids=v2["project_order"][key])],
            skills=[SkillGroup(label=label, items=items_) for label, items_ in v2["skills"][key]],
            scale=scales.get(key),
        )

    education = [Education(**ed) for ed in v2.get("education", [])]
    return ResumeData(contact=contact, items=items, education=education, sections=sections,
                      tracks=tracks, facts=facts)
