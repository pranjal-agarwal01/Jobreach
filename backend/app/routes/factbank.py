"""
The fact bank: view, edit, delete. `confirmed` means usable: onboarding sets it on every line
its documents back, and anything the user writes or edits is their own statement and usable
at once. Only usable lines reach a resume or an email.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..auth import User, current_user
from ..db import user_tx
from ..onboarding import NUMBER_RE, _section_id, _slug

router = APIRouter()


@router.get("/factbank")
def factbank(user: User = Depends(current_user)):
    with user_tx(user.id) as conn:
        items = conn.execute("select * from items order by sort, created_at").fetchall()
        bullets = conn.execute("select * from bullets order by sort, created_at").fetchall()
        sections = conn.execute("select * from resume_sections order by sort").fetchall()
        entries = conn.execute("select * from entries order by sort, created_at").fetchall()
        education = conn.execute("select * from education order by sort").fetchall()
        facts = conn.execute(
            """select f.* from facts f where not exists
                 (select 1 from bullets b where f.id = any(b.fact_ids))
               and not exists (select 1 from entries e where f.id = any(e.fact_ids))
               order by kind, created_at""").fetchall()
    by_item: dict = {}
    for b in bullets:
        by_item.setdefault(b["item_id"], []).append(b)
    by_sec: dict = {}
    for e in entries:
        by_sec.setdefault(e["section_id"], []).append(e)
    return {
        "items": [{**i, "bullets": by_item.get(i["id"], [])} for i in items],
        "sections": [{**s, "entries": by_sec.get(s["id"], [])} for s in sections],
        "education": education,
        "facts": facts,   # skills and other facts not on a bullet or entry
    }


def _patch(table: str, id_: str, fields: dict, user: User, json_fields=()):
    if not fields:
        return
    sets = ", ".join("{} = %s".format(k) for k in fields)
    vals = [Jsonb(v) if k in json_fields else v for k, v in fields.items()]
    with user_tx(user.id) as conn:
        r = conn.execute("update {} set {} where id = %s returning id".format(table, sets), vals + [id_]).fetchone()
    if r is None:
        raise HTTPException(404, "not found")


def _delete(table: str, id_: str, user: User):
    with user_tx(user.id) as conn:
        r = conn.execute("delete from {} where id = %s returning id".format(table), (id_,)).fetchone()
    if r is None:
        raise HTTPException(404, "not found")
    return {"ok": True}


# ------------------------------------------------------------------ items

class ItemIn(BaseModel):
    kind: Optional[Literal["project", "experience"]] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    period: Optional[str] = None
    stack: Optional[str] = None
    stack_label: Optional[str] = None
    links: Optional[list[dict]] = None
    sort: Optional[int] = None
    confirmed: Optional[bool] = None


@router.post("/items")
def create_item(body: ItemIn, user: User = Depends(current_user)):
    if not body.name:
        raise HTTPException(400, "name is required")
    with user_tx(user.id) as conn:
        taken = {r["key"] for r in conn.execute("select key from items").fetchall()}
        key = _slug(body.name)
        while key in taken:
            key += "_2"
        r = conn.execute(
            """insert into items (user_id, key, kind, name, tagline, period, stack, stack_label, links, confirmed, sort)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (user.id, key, body.kind or "project", body.name, body.tagline, body.period, body.stack,
             body.stack_label or "Stack", Jsonb(body.links or []), body.confirmed is not False, body.sort or 300)).fetchone()
    return r


@router.patch("/items/{item_id}")
def patch_item(item_id: str, body: ItemIn, user: User = Depends(current_user)):
    _patch("items", item_id, body.model_dump(exclude_unset=True), user, json_fields=("links",))
    return {"ok": True}


@router.delete("/items/{item_id}")
def delete_item(item_id: str, user: User = Depends(current_user)):
    return _delete("items", item_id, user)


# ------------------------------------------------------------------ bullets

class BulletIn(BaseModel):
    item_id: Optional[str] = None
    text: Optional[str] = None
    sort: Optional[int] = None
    confirmed: Optional[bool] = None


@router.post("/bullets")
def create_bullet(body: BulletIn, user: User = Depends(current_user)):
    """A bullet the user writes is their own statement: it becomes a fact of its own."""
    if not body.item_id or not body.text:
        raise HTTPException(400, "item_id and text are required")
    c = body.confirmed is not False
    with user_tx(user.id) as conn:
        f = conn.execute(
            """insert into facts (user_id, kind, text, source, confirmed_at)
               values (%s, 'project', %s, 'edit', case when %s then now() end) returning id""",
            (user.id, body.text, c)).fetchone()
        return conn.execute(
            """insert into bullets (user_id, item_id, text, fact_ids, has_metric, confirmed, sort)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            (user.id, body.item_id, body.text, [f["id"]], bool(NUMBER_RE.search(body.text)), c,
             body.sort or 100)).fetchone()


@router.patch("/bullets/{bullet_id}")
def patch_bullet(bullet_id: str, body: BulletIn, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True, exclude={"item_id"})
    with user_tx(user.id) as conn:
        b = conn.execute("select * from bullets where id = %s", (bullet_id,)).fetchone()
        if b is None:
            raise HTTPException(404, "not found")
        if "text" in fields and fields["text"] != b["text"]:
            # Editing the words edits the claim: the bullet now states a new fact of the user's own,
            # usable at once (unless the same request says otherwise).
            usable = fields.get("confirmed", True)
            f = conn.execute(
                """insert into facts (user_id, kind, text, source, confirmed_at)
                   values (%s, 'project', %s, 'edit', case when %s then now() end) returning id""",
                (user.id, fields["text"], usable)).fetchone()
            conn.execute("""update bullets set text = %s, fact_ids = %s, has_metric = %s, confirmed = %s,
                                provenance = '{"ok": true, "edited_by_user": true}' where id = %s""",
                         (fields["text"], [f["id"]], bool(NUMBER_RE.search(fields["text"])), usable, bullet_id))
            conn.execute("""delete from facts where id = any(%s) and source = 'upload'
                            and not exists (select 1 from bullets x where facts.id = any(x.fact_ids))""",
                         (b["fact_ids"],))
        for k in ("sort", "confirmed"):
            if k in fields:
                conn.execute("update bullets set {} = %s where id = %s".format(k), (fields[k], bullet_id))
        if "confirmed" in fields:
            conn.execute("update facts set confirmed_at = case when %s then now() else null end where id = any("
                         "(select fact_ids from bullets where id = %s))", (fields["confirmed"], bullet_id))
    return {"ok": True}


@router.delete("/bullets/{bullet_id}")
def delete_bullet(bullet_id: str, user: User = Depends(current_user)):
    return _delete("bullets", bullet_id, user)


# ------------------------------------------------------------------ entries

class EntryIn(BaseModel):
    section: Optional[Literal["awards", "roles"]] = None
    lead: Optional[str] = None
    text: Optional[str] = None
    tracks: Optional[list[str]] = None
    sort: Optional[int] = None
    confirmed: Optional[bool] = None


@router.post("/entries")
def create_entry(body: EntryIn, user: User = Depends(current_user)):
    if not body.section or not body.text:
        raise HTTPException(400, "section and text are required")
    c = body.confirmed is not False
    with user_tx(user.id) as conn:
        sid = _section_id(conn, user.id, body.section)
        f = conn.execute(
            """insert into facts (user_id, kind, text, source, confirmed_at)
               values (%s, %s, %s, 'edit', case when %s then now() end) returning id""",
            (user.id, "award" if body.section == "awards" else "role", (body.lead or "") + body.text, c)).fetchone()
        return conn.execute(
            """insert into entries (user_id, section_id, lead, text, tracks, fact_ids, confirmed, sort)
               values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (user.id, sid, body.lead, body.text, body.tracks, [f["id"]], c, body.sort or 100)).fetchone()


@router.patch("/entries/{entry_id}")
def patch_entry(entry_id: str, body: EntryIn, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True, exclude={"section"})
    _patch("entries", entry_id, fields, user)
    if "confirmed" in fields or "text" in fields or "lead" in fields:
        with user_tx(user.id) as conn:
            e = conn.execute("select * from entries where id = %s", (entry_id,)).fetchone()
            conn.execute("""update facts set text = %s, confirmed_at = case when %s then now() else null end
                            where id = any(%s)""",
                         ((e["lead"] or "") + e["text"], e["confirmed"], e["fact_ids"]))
    return {"ok": True}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str, user: User = Depends(current_user)):
    return _delete("entries", entry_id, user)


# ------------------------------------------------------------------ education

class EducationIn(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    meta: Optional[str] = None
    result: Optional[str] = None
    lines: Optional[list[str]] = None
    sort: Optional[int] = None
    confirmed: Optional[bool] = None


@router.post("/education")
def create_education(body: EducationIn, user: User = Depends(current_user)):
    if not body.institution:
        raise HTTPException(400, "institution is required")
    with user_tx(user.id) as conn:
        return conn.execute(
            """insert into education (user_id, institution, degree, meta, result, lines, confirmed, sort)
               values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (user.id, body.institution, body.degree, body.meta, body.result, body.lines or [],
             body.confirmed is not False, body.sort or 100)).fetchone()


@router.patch("/education/{edu_id}")
def patch_education(edu_id: str, body: EducationIn, user: User = Depends(current_user)):
    _patch("education", edu_id, body.model_dump(exclude_unset=True), user)
    return {"ok": True}


@router.delete("/education/{edu_id}")
def delete_education(edu_id: str, user: User = Depends(current_user)):
    return _delete("education", edu_id, user)


# ------------------------------------------------------------------ loose facts (skills, other)

class FactIn(BaseModel):
    kind: Optional[Literal["project", "role", "award", "skill", "metric", "other"]] = None
    text: Optional[str] = None
    confirmed: Optional[bool] = None


@router.post("/facts")
def create_fact(body: FactIn, user: User = Depends(current_user)):
    if not body.kind or not body.text:
        raise HTTPException(400, "kind and text are required")
    with user_tx(user.id) as conn:
        return conn.execute(
            """insert into facts (user_id, kind, text, source, confirmed_at)
               values (%s, %s, %s, 'edit', case when %s then now() end) returning *""",
            (user.id, body.kind, body.text, body.confirmed is not False)).fetchone()


@router.patch("/facts/{fact_id}")
def patch_fact(fact_id: str, body: FactIn, user: User = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    with user_tx(user.id) as conn:
        if "text" in fields or "kind" in fields:
            sets = {k: v for k, v in fields.items() if k in ("text", "kind")}
            conn.execute("update facts set {}, source = 'edit' where id = %s".format(
                ", ".join("{} = %s".format(k) for k in sets)), list(sets.values()) + [fact_id])
        if "confirmed" in fields:
            conn.execute("update facts set confirmed_at = case when %s then now() else null end where id = %s",
                         (fields["confirmed"], fact_id))
    return {"ok": True}


@router.delete("/facts/{fact_id}")
def delete_fact(fact_id: str, user: User = Depends(current_user)):
    return _delete("facts", fact_id, user)
