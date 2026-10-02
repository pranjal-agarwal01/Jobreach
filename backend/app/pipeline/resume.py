"""
S6: build a one-page resume from the user's confirmed data, verify the page count with the
renderer, and store it. Also calibrates each track's baseline scale during onboarding.

One page, always (spec 6.5): if a build spills, step the scale down one grid step, then
drop the lowest-priority line, then rebuild. Never ship two pages.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from psycopg import Connection

from resume_engine import calibrate as cal
from resume_engine.ats_score import docx_text, score as ats_score
from resume_engine.builder import BuildResult, build
from resume_engine.jd_match import match_text
from resume_engine.pages import render, renderer_version
from resume_engine.schema import (
    Bullet, BuildOptions, Contact, Education, Entry, Fact, Item, LeftSection, Link, ResumeData,
    Section, SkillGroup, Track,
)

MAX_FIT_STEPS = 14


class ResumeTooLong(RuntimeError):
    pass


@dataclass
class Built:
    content: bytes
    filename: str
    result: BuildResult
    pages: int
    scale: float
    dropped: list[str] = field(default_factory=list)
    ats: Optional[float] = None
    jd_match: Optional[float] = None
    pdf: Optional[bytes] = None      # the page-checked render; what the student sends

    @property
    def pdf_filename(self) -> str:
        return self.filename.rsplit(".", 1)[0] + ".pdf"


def load_resume_data(conn: Connection, user_id: str) -> ResumeData:
    """Everything confirmed, nothing else. Call inside user_tx(user_id)."""
    p = conn.execute("select * from profiles where user_id = %s", (user_id,)).fetchone() or {}
    items = conn.execute("select * from items where confirmed order by sort, created_at").fetchall()
    bullets = conn.execute("select * from bullets where confirmed order by sort, created_at").fetchall()
    sections = conn.execute("select * from resume_sections order by sort").fetchall()
    entries = conn.execute("select * from entries where confirmed order by sort, created_at").fetchall()
    education = conn.execute("select * from education where confirmed order by sort").fetchall()
    tracks = conn.execute("select * from tracks order by sort").fetchall()
    facts = conn.execute("select * from facts where confirmed_at is not null").fetchall()

    by_item: dict = {}
    for b in bullets:
        by_item.setdefault(b["item_id"], []).append(
            Bullet(id=str(b["id"]), text=b["text"], fact_ids=[str(f) for f in b["fact_ids"]]))
    item_map = {}
    for it in items:
        item_map[it["key"]] = Item(
            id=it["key"], kind=it["kind"], name=it["name"], tagline=it["tagline"], period=it["period"],
            stack=it["stack"], stack_label=it["stack_label"],
            links=[Link(**lk) for lk in (it["links"] or [])], bullets=by_item.get(it["id"], []))

    by_section: dict = {}
    for e in entries:
        by_section.setdefault(e["section_id"], []).append(
            Entry(id=str(e["id"]), text=e["text"], lead=e["lead"], tracks=e["tracks"],
                  fact_ids=[str(f) for f in e["fact_ids"]]))
    secs = [Section(id=s["key"], heading=s["heading"], style=s["style"], entries=by_section.get(s["id"], []))
            for s in sections]

    track_map = {}
    for t in tracks:
        left = [LeftSection(heading=s["heading"], item_ids=[k for k in s.get("item_keys", []) if k in item_map])
                for s in (t["left_sections"] or [])]
        track_map[t["key"]] = Track(
            key=t["key"], label=t["label"], title_line=t["title_line"], summary=t["summary"],
            left_sections=left, skills=[SkillGroup(**g) for g in (t["skills"] or [])],
            scale=float(t["scale"]) if t["scale"] is not None else None)

    contact = Contact(name=p.get("name") or "Your Name", location=p.get("location"),
                      phone=p.get("phone"), email=p.get("email"),
                      social=[Link(**lk) for lk in (p.get("links") or [])])
    return ResumeData(
        contact=contact, items=item_map, sections=secs,
        education=[Education(institution=e["institution"], degree=e["degree"], meta=e["meta"],
                             result=e["result"], lines=e["lines"] or []) for e in education],
        tracks=track_map,
        facts=[Fact(id=str(f["id"]), kind=f["kind"], text=f["text"], confirmed=True) for f in facts])


def resume_filename(name: str) -> str:
    parts = [re.sub(r"[^A-Za-z]", "", w).capitalize() for w in (name or "").split()]
    parts = [w for w in parts if w]
    return "resume_{}.docx".format("_".join(parts[:3]) or "Resume")


def order_bullets(data: ResumeData, bullet_order: list[str]) -> ResumeData:
    """Apply the selection's bullet order within each item (selection only, no new text)."""
    rank = {bid: i for i, bid in enumerate(bullet_order)}
    items = {}
    for key, it in data.items.items():
        bl = sorted(it.bullets, key=lambda b: rank.get(b.id, len(rank)))
        items[key] = it.model_copy(update={"bullets": bl})
    return data.model_copy(update={"items": items})


def _lowest_priority(data: ResumeData, opts: BuildOptions, res: BuildResult) -> Optional[str]:
    """The line to drop next: from whichever column the estimate says is longer. Left:
    the last bullet of the last item still carrying more than two. Right: the last entry
    of the last non-empty section."""
    def left():
        for key in reversed(res.item_ids):
            used = [b for b in data.items[key].bullets if b.id in res.bullet_ids]
            if len(used) > 2:
                return used[-1].id
        return None

    def right():
        return res.entry_ids[-1] if res.entry_ids else None

    first, second = (left, right) if res.est_left >= res.est_right else (right, left)
    return first() or second()


def build_one_page(data: ResumeData, opts: BuildOptions, jd_text: Optional[str] = None) -> Built:
    track = data.tracks[opts.track]
    scale = opts.scale or track.scale
    if scale is None:
        c = cal.calibrate(data, tracks=[opts.track])[opts.track]
        if c.scale is None:
            raise ResumeTooLong("Track {} does not fit on one page at any scale".format(opts.track))
        scale = c.scale
    drop = set(opts.drop)
    dropped: list[str] = []
    stepped = False
    with tempfile.TemporaryDirectory(prefix="build-") as tmp:
        for step in range(MAX_FIT_STEPS):
            path = os.path.join(tmp, "r{}.docx".format(step))
            o = opts.model_copy(update={"drop": drop, "scale": scale})
            res = build(data, o, path)
            pages, pdf = render([path], keep_pdf=True)[path]
            if pages == 1:
                with open(path, "rb") as f:
                    content = f.read()
                b = Built(content=content, filename=resume_filename(data.contact.name), result=res,
                          pages=pages, scale=scale, dropped=dropped, pdf=pdf)
                b.ats = round(ats_score(path)[0], 1)
                if jd_text:
                    b.jd_match = round(100 * match_text(docx_text(path), jd_text).coverage, 1)
                return b
            if not stepped and round(scale - cal.FINE_STEP, 3) >= cal.MIN_SCALE:
                scale, stepped = round(scale - cal.FINE_STEP, 3), True
                continue
            victim = _lowest_priority(data, o, res)
            if victim is None:
                break
            drop.add(victim)
            dropped.append(victim)
    raise ResumeTooLong("Could not fit {} on one page".format(opts.track))


def store(conn: Connection, user_id: str, built: Built, track_key: str,
          application_id: Optional[str] = None, is_baseline: bool = False) -> str:
    """Insert the file and its resume row. Call inside user_tx(user_id)."""
    f = conn.execute(
        "insert into resume_files (user_id, filename, content, pdf, pdf_filename) values (%s, %s, %s, %s, %s) returning id",
        (user_id, built.filename, built.content, built.pdf, built.pdf_filename if built.pdf else None)).fetchone()
    r = built.result
    bullet_ids = [b for b in r.bullet_ids]
    row = conn.execute(
        """insert into resumes (user_id, application_id, track_key, is_baseline, file_id, item_keys,
               bullet_ids, entry_ids, dropped_ids, scale, pages_verified, renderer, ats_score, jd_match)
           values (%s, %s, %s, %s, %s, %s, %s::uuid[], %s::uuid[], %s, %s, %s, %s, %s, %s) returning id::text""",
        (user_id, application_id, track_key, is_baseline, f["id"], r.item_ids, bullet_ids, r.entry_ids,
         built.dropped, built.scale, built.pages, _renderer(), built.ats, built.jd_match)).fetchone()
    return row["id"]


def pdf_from_docx(content: bytes) -> bytes:
    """Render a stored .docx that has no PDF yet (files made before PDFs were kept)."""
    with tempfile.TemporaryDirectory(prefix="pdf-") as tmp:
        path = os.path.join(tmp, "r.docx")
        with open(path, "wb") as f:
            f.write(content)
        return render([path], keep_pdf=True)[path][1]


_RENDERER: Optional[str] = None


def _renderer() -> str:
    global _RENDERER
    if _RENDERER is None:
        try:
            _RENDERER = renderer_version()
        except Exception:
            _RENDERER = "libreoffice"
    return _RENDERER


def calibrate_baselines(user_id: str, track_keys: Optional[list[str]] = None) -> dict:
    """Find each baseline's one-page scale and store a verified baseline. A record too long for
    one page even at the smallest type is built at that size, dropping its lowest-priority lines
    (the dropped ids are kept on the resume row). Rendering takes seconds per track, so it runs
    outside any database transaction; one track failing does not stop the others."""
    from ..db import user_tx

    with user_tx(user_id) as conn:
        data = load_resume_data(conn, user_id)
    keys = [k for k in (track_keys or list(data.tracks)) if k in data.tracks]
    out, built_by_key = {}, {}
    for key in keys:
        if not any(s.item_ids for s in data.tracks[key].left_sections):
            out[key] = {"ok": False, "error": "This resume has no projects or jobs on it yet."}
            continue
        try:
            c = cal.calibrate(data, tracks=[key])[key]
            data.tracks[key].scale = c.scale if c.scale is not None else cal.MIN_SCALE
            built_by_key[key] = (c, build_one_page(data, BuildOptions(track=key)))
        except ResumeTooLong as e:
            out[key] = {"ok": False, "error": str(e)}

    with user_tx(user_id) as conn:
        for key, (c, built) in built_by_key.items():
            conn.execute("update tracks set scale = %s, calibrated_at = now() where key = %s", (built.scale, key))
            old = conn.execute("select file_id from resumes where track_key = %s and is_baseline", (key,)).fetchall()
            for o in old:
                conn.execute("delete from resume_files where id = %s", (o["file_id"],))
            rid = store(conn, user_id, built, key, is_baseline=True)
            out[key] = {"ok": True, "scale": built.scale, "capped": c.capped, "resume_id": rid, "ats": built.ats,
                        "dropped": built.dropped}
    return out
