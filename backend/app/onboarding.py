"""
Onboarding (spec 4.1): upload, extract a draft fact bank, interview for what is missing,
check evidence behind every skill, propose tracks. Everything extracted or proposed is
stored unconfirmed; nothing reaches a resume until the user confirms it.
"""
from __future__ import annotations

import io
import os
import re
from typing import Optional, get_args

import httpx
from docx import Document
from psycopg.types.json import Jsonb
from pypdf import PdfReader

from . import llm
from .db import system_tx, user_tx
from .pipeline import prompts
from .pipeline.schemas import (
    BulletProposals, Discipline, Extraction, InterviewTurn, RoleAudit, TrackProposals,
)
from .taxonomy import FAMILIES

FIELDS = set(get_args(Discipline)) - {"other"}
# Posts name the same work differently ("SDE Intern" vs "Backend Intern"), so choosing a role
# keeps leads from its neighbours too. S5 still picks the closest track per lead.
FIELD_NEIGHBOURS = {k: set(f.neighbours) for k, f in FAMILIES.items() if f.neighbours}
FIT_RANK = {"strong": 0, "good": 1, "stretch": 2}
GITHUB_URL_RE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})/?(?:[?#].*)?$", re.I)
GITHUB_NAME_RE = re.compile(r"^@?([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))$")

MAX_QUESTIONS = 8
SECTION_DEFAULTS = {"awards": ("Awards & Certifications", "list", 0),
                    "roles": ("Other Roles & Responsibilities", "detail", 1)}
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def text_from_upload(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        # Two-column PDFs interleave columns; the model still recovers the facts, and the
        # user confirms every line.
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    parts.extend(p.text for p in cell.paragraphs)
        return "\n".join(p for p in parts if p.strip())
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", "replace")
    raise ValueError("Upload a PDF, DOCX or TXT file")


def github_username(s: str) -> Optional[str]:
    s = (s or "").strip()
    m = GITHUB_URL_RE.match(s) or GITHUB_NAME_RE.match(s)
    return m.group(1) if m else None


def github_summary(username: str, timeout: float = 10.0) -> Optional[str]:
    """The student's own public repositories, as a document for the audit to read: name,
    description, language, topics, live link, last push. Forks and archived repos are left
    out. Public API, no key (set GITHUB_TOKEN for a higher rate limit). Facts drawn from it
    stay unconfirmed until the student confirms them, like everything else uploaded."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "jobreach"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        r = httpx.get("https://api.github.com/users/{}/repos".format(username), headers=headers,
                      params={"per_page": 100, "sort": "pushed", "type": "owner"}, timeout=timeout)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    repos = [x for x in r.json() if not x.get("fork") and not x.get("archived")][:30]
    lines = ["GitHub profile https://github.com/{}: {} public repositories of their own, most "
             "recently pushed first.".format(username, len(repos))]
    for x in repos:
        parts = [x["name"]]
        if x.get("description"):
            parts.append(x["description"])
        if x.get("language"):
            parts.append("language: " + x["language"])
        if x.get("topics"):
            parts.append("topics: " + ", ".join(x["topics"]))
        if x.get("homepage"):
            parts.append("live: " + x["homepage"])
        if x.get("stargazers_count"):
            parts.append("stars: {}".format(x["stargazers_count"]))
        parts.append("repo: " + x["html_url"])
        parts.append("last push: " + (x.get("pushed_at") or "")[:10])
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "item"


def _has_number(text: str) -> bool:
    return bool(NUMBER_RE.search(text))


def _section_id(conn, user_id: str, key: str) -> str:
    heading, style, sort = SECTION_DEFAULTS[key]
    row = conn.execute(
        """insert into resume_sections (user_id, key, heading, style, sort) values (%s, %s, %s, %s, %s)
           on conflict (user_id, key) do update set key = excluded.key returning id::text""",
        (user_id, key, heading, style, sort)).fetchone()
    return row["id"]


def run_extraction(user_id: str) -> dict:
    """O2: draft fact bank from the uploaded documents. Replaces any earlier unconfirmed
    extraction, keeps everything the user already confirmed."""
    with user_tx(user_id) as conn:
        docs = conn.execute("select kind, filename, text from source_documents order by created_at").fetchall()
    if not docs:
        raise ValueError("Upload a resume or write an 'about me' first")
    volatile = "\n\n".join("<document kind=\"{}\" name=\"{}\">\n{}\n</document>".format(
        d["kind"], d["filename"] or "", d["text"][:30000]) for d in docs)
    ex = llm.structured("onb_extract", Extraction, stable=[prompts.ONBOARD_EXTRACT], volatile=volatile,
                        effort="medium", max_tokens=16000, ctx=llm.CallContext(user_id=user_id))

    counts = {"items": 0, "bullets": 0, "entries": 0, "education": 0, "skills": 0}
    with user_tx(user_id) as conn:
        conn.execute("delete from items where not confirmed")
        conn.execute("delete from entries where not confirmed")
        conn.execute("delete from education where not confirmed")
        conn.execute("delete from facts where confirmed_at is null and source = 'upload'")
        taken = {r["key"] for r in conn.execute("select key from items").fetchall()}

        p = ex.profile
        conn.execute(
            """update profiles set name = coalesce(name, %s), headline = coalesce(headline, %s),
                   location = coalesce(location, %s), phone = coalesce(phone, %s), email = coalesce(email, %s),
                   links = case when links = '[]'::jsonb then %s else links end,
                   grad_date = coalesce(grad_date, %s), batch_year = coalesce(batch_year, %s),
                   cgpa = coalesce(cgpa, %s), updated_at = now()
               where user_id = %s""",
            (p.name, p.headline, p.location, p.phone, p.email,
             Jsonb([lk.model_dump() for lk in p.links]), p.grad_date, p.batch_year, p.cgpa, user_id))

        for i, it in enumerate(ex.items):
            key = _slug(it.key or it.name)
            while key in taken:
                key += "_2"
            taken.add(key)
            item = conn.execute(
                """insert into items (user_id, key, kind, name, tagline, period, stack, links, sort)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id""",
                (user_id, key, it.kind, it.name, it.tagline, it.period, it.stack,
                 Jsonb([lk.model_dump() for lk in it.links]), 100 + i)).fetchone()
            counts["items"] += 1
            for j, text in enumerate(it.bullets):
                f = conn.execute(
                    "insert into facts (user_id, kind, text, source) values (%s, %s, %s, 'upload') returning id",
                    (user_id, "role" if it.kind == "experience" else "project", text)).fetchone()
                conn.execute(
                    """insert into bullets (user_id, item_id, text, fact_ids, has_metric, sort)
                       values (%s, %s, %s, %s, %s, %s)""",
                    (user_id, item["id"], text, [f["id"]], _has_number(text), j))
                counts["bullets"] += 1

        for i, e in enumerate(ex.entries):
            sid = _section_id(conn, user_id, e.section)
            f = conn.execute(
                "insert into facts (user_id, kind, text, source) values (%s, %s, %s, 'upload') returning id",
                (user_id, "award" if e.section == "awards" else "role", (e.lead or "") + " " + e.text)).fetchone()
            conn.execute(
                "insert into entries (user_id, section_id, lead, text, fact_ids, sort) values (%s, %s, %s, %s, %s, %s)",
                (user_id, sid, e.lead, e.text if not e.lead or e.text.startswith((" ", "—", "-")) else " — " + e.text,
                 [f["id"]], 100 + i))
            counts["entries"] += 1

        for i, ed in enumerate(ex.education):
            conn.execute(
                """insert into education (user_id, institution, degree, meta, result, lines, sort)
                   values (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, ed.institution, ed.degree, ed.meta, ed.result, ed.lines, 100 + i))
            counts["education"] += 1

        existing = {r["text"].lower() for r in conn.execute("select text from facts where kind = 'skill'").fetchall()}
        for s in ex.skills:
            if s.strip() and s.lower() not in existing:
                conn.execute("insert into facts (user_id, kind, text, source) values (%s, 'skill', %s, 'upload')",
                             (user_id, s.strip()))
                existing.add(s.lower())
                counts["skills"] += 1
        for t in ex.other_facts:
            conn.execute("insert into facts (user_id, kind, text, source) values (%s, 'other', %s, 'upload')",
                         (user_id, t))
        conn.execute("update profiles set onboarding_step = 'confirm' where user_id = %s", (user_id,))
    return counts


def _fact_bank_summary(conn) -> str:
    items = conn.execute("select id, key, kind, name, tagline, period, stack from items order by sort").fetchall()
    bullets = conn.execute("select item_id, text from bullets order by sort").fetchall()
    facts = conn.execute("select kind, text from facts where kind not in ('project', 'role') order by created_at").fetchall()
    by_item: dict = {}
    for b in bullets:
        by_item.setdefault(b["item_id"], []).append(b["text"])
    return llm.dumps({
        "items": [{"key": i["key"], "kind": i["kind"], "name": i["name"], "tagline": i["tagline"],
                   "period": i["period"], "stack": i["stack"], "bullets": by_item.get(i["id"], [])} for i in items],
        "other_facts": [{"kind": f["kind"], "text": f["text"]} for f in facts],
    })


def interview(user_id: str, answer: Optional[str]) -> dict:
    """O3: record the user's answer (if any), then ask the next question."""
    with user_tx(user_id) as conn:
        if answer and answer.strip():
            conn.execute("insert into onboarding_messages (user_id, role, content) values (%s, 'user', %s)",
                         (user_id, answer.strip()))
        history = conn.execute("select role, content from onboarding_messages order by created_at").fetchall()
        bank = _fact_bank_summary(conn)
    asked = sum(1 for h in history if h["role"] == "assistant")
    transcript = "\n".join("{}: {}".format("Interviewer" if h["role"] == "assistant" else "Student", h["content"])
                           for h in history) or "(no questions asked yet)"
    volatile = "Questions asked so far: {} of at most {}.\n\nConversation:\n{}".format(asked, MAX_QUESTIONS, transcript)
    turn = llm.structured("onb_interview", InterviewTurn,
                          stable=[prompts.INTERVIEW, "Current fact bank:\n" + bank],
                          volatile=volatile, effort="medium", max_tokens=4000,
                          ctx=llm.CallContext(user_id=user_id))
    done = turn.done or asked >= MAX_QUESTIONS
    added = 0
    with user_tx(user_id) as conn:
        keys = {r["key"]: r["id"] for r in conn.execute("select id, key from items").fetchall()}
        for n in turn.new_items:
            key = _slug(n.key or n.name)
            if key not in keys:
                row = conn.execute(
                    """insert into items (user_id, key, kind, name, tagline, period, sort)
                       values (%s, %s, %s, %s, %s, %s, 200) returning id""",
                    (user_id, key, n.kind, n.name, n.tagline, n.period)).fetchone()
                keys[key] = row["id"]
        for f in turn.new_facts:
            note = "item:" + f.item_key if f.item_key else None
            conn.execute("insert into facts (user_id, kind, text, source, evidence_note) values (%s, %s, %s, 'interview', %s)",
                         (user_id, f.kind, f.text, note))
            added += 1
        if not done and turn.next_question:
            conn.execute("insert into onboarding_messages (user_id, role, content) values (%s, 'assistant', %s)",
                         (user_id, turn.next_question))
    return {"question": None if done else turn.next_question, "done": done, "facts_added": added}


def propose_bullets(user_id: str) -> dict:
    """Write bullets for confirmed interview facts that no bullet uses yet. Proposed bullets
    are unconfirmed and cite the facts they use."""
    with user_tx(user_id) as conn:
        facts = conn.execute(
            """select f.id::text, f.kind, f.text, f.evidence_note from facts f
               where f.confirmed_at is not null and f.source = 'interview' and f.kind <> 'skill'
                 and not exists (select 1 from bullets b where f.id = any(b.fact_ids))""").fetchall()
        items = conn.execute("select key, kind, name, tagline from items order by sort").fetchall()
    if not facts:
        return {"proposed": 0}
    by_item: dict = {}
    for f in facts:
        k = (f["evidence_note"] or "").removeprefix("item:") or None
        by_item.setdefault(k, []).append({"id": f["id"], "kind": f["kind"], "text": f["text"]})
    volatile = "Items:\n{}\n\nItems needing bullets, with their confirmed facts:\n{}".format(
        llm.dumps([dict(i) for i in items]), llm.dumps(by_item))
    out = llm.structured("onb_bullets", BulletProposals, stable=[prompts.BULLETS], volatile=volatile,
                         effort="medium", max_tokens=6000, ctx=llm.CallContext(user_id=user_id))
    valid = {f["id"]: f["text"] for f in facts}
    n = 0
    with user_tx(user_id) as conn:
        item_ids = {r["key"]: r["id"] for r in conn.execute("select id, key from items").fetchall()}
        for b in out.bullets:
            cited = [fid for fid in b.fact_ids if fid in valid]
            if b.item_key not in item_ids or not cited:
                continue
            # A proposed bullet may not carry a number its cited facts do not contain.
            fact_nums = set(NUMBER_RE.findall(" ".join(valid[f] for f in cited)))
            if not set(NUMBER_RE.findall(b.text)) <= fact_nums:
                continue
            conn.execute(
                "insert into bullets (user_id, item_id, text, fact_ids, has_metric, sort) values (%s, %s, %s, %s::uuid[], %s, 50)",
                (user_id, item_ids[b.item_key], b.text, cited, _has_number(b.text)))
            n += 1
    return {"proposed": n}


def evidence_check(user_id: str) -> list[dict]:
    """O4, in code: a skill is backed when a confirmed item's stack or bullets, or a
    confirmed entry, mentions it. Unbacked skills are flagged, not silently kept."""
    with user_tx(user_id) as conn:
        skills = conn.execute("select id::text, text from facts where kind = 'skill' order by text").fetchall()
        items = conn.execute("select id, key, name, coalesce(stack, '') as stack from items where confirmed").fetchall()
        bullets = conn.execute("select item_id, text from bullets where confirmed").fetchall()
        entries = conn.execute("select id::text, coalesce(lead, '') || text as text from entries where confirmed").fetchall()
        text_by_item: dict = {i["id"]: i["name"] + " " + i["stack"] for i in items}
        for b in bullets:
            text_by_item[b["item_id"]] = text_by_item.get(b["item_id"], "") + " " + b["text"]
        out = []
        for s in skills:
            rx = re.compile(r"(?<![\w]){}(?![\w])".format(re.escape(s["text"].lower())))
            backed = [i["key"] for i in items if rx.search(text_by_item.get(i["id"], "").lower())]
            backed += ["entry:" + e["id"] for e in entries if rx.search(e["text"].lower())]
            conn.execute("update facts set evidence_items = %s where id = %s", (backed, s["id"]))
            out.append({"fact_id": s["id"], "skill": s["text"], "backed_by": backed, "backed": bool(backed)})
    return out


def propose_tracks(user_id: str) -> dict:
    """O6: propose 1-4 tracks from confirmed evidence. Stored unapproved; the user edits and
    approves each. Skills outside the confirmed list are removed before storing."""
    with user_tx(user_id) as conn:
        profile = conn.execute("select name, headline, grad_date, batch_year from profiles").fetchone() or {}
        prefs = conn.execute("select role_types, target_roles, open_to from preferences").fetchone() or {}
        items = conn.execute("select id, key, kind, name, tagline, stack from items where confirmed order by sort").fetchall()
        bullets = conn.execute("select item_id, text from bullets where confirmed order by sort").fetchall()
        facts = conn.execute("select kind, text from facts where confirmed_at is not null and kind <> 'skill'").fetchall()
        skills = [r["text"] for r in conn.execute(
            "select text from facts where kind = 'skill' and confirmed_at is not null").fetchall()]
        edu = conn.execute("select institution, degree, meta from education where confirmed order by sort").fetchall()
    by_item: dict = {}
    for b in bullets:
        by_item.setdefault(b["item_id"], []).append(b["text"])
    volatile = llm.dumps({
        "profile": dict(profile), "preferences": dict(prefs), "education": [dict(e) for e in edu],
        "items": [{"key": i["key"], "kind": i["kind"], "name": i["name"], "tagline": i["tagline"],
                   "stack": i["stack"], "bullets": by_item.get(i["id"], [])} for i in items],
        "confirmed_facts": [dict(f) for f in facts], "confirmed_skills": skills,
    })
    out = llm.structured("onb_tracks", TrackProposals, stable=[prompts.TRACKS], volatile=volatile,
                         effort="medium", max_tokens=8000, ctx=llm.CallContext(user_id=user_id))
    known_items = {i["key"] for i in items}
    known_skills = {s.lower() for s in skills}
    corpus = " ".join([f["text"] for f in facts] + [b["text"] for b in bullets]
                      + [" ".join(str(v or "") for v in dict(e).values()) for e in edu]
                      + [str(v or "") for v in dict(profile).values()])
    known_numbers = {n.replace(",", "") for n in NUMBER_RE.findall(corpus)}
    warnings: dict = {}
    stored = []
    with user_tx(user_id) as conn:
        for i, t in enumerate(out.tracks[:4]):
            key = _slug(t.key or t.label)
            left = [{"heading": s.heading, "item_keys": [k for k in s.item_keys if k in known_items]}
                    for s in t.left_sections]
            left = [s for s in left if s["item_keys"]]
            groups = []
            for g in t.skills:
                kept = [s.strip() for s in g.items.split(",") if s.strip().lower() in known_skills]
                if kept:
                    groups.append({"label": g.label, "items": ", ".join(kept)})
            conn.execute(
                """insert into tracks (user_id, key, label, title_line, summary, left_sections, skills, sort, approved)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, false)
                   on conflict (user_id, key) do update set label = excluded.label, title_line = excluded.title_line,
                       summary = excluded.summary, left_sections = excluded.left_sections,
                       skills = excluded.skills, approved = false, scale = null""",
                (user_id, key, t.label, t.title_line, t.summary, Jsonb(left), Jsonb(groups), i))
            stored.append(key)
            unknown = sorted({n.replace(",", "") for n in NUMBER_RE.findall(t.summary + " " + t.title_line)}
                             - known_numbers)
            if unknown:
                warnings[key] = "Summary contains numbers not in your confirmed facts: {}. Edit before approving.".format(
                    ", ".join(unknown))
        conn.execute("update profiles set onboarding_step = 'tracks' where user_id = %s", (user_id,))
    return {"tracks": stored, "rationale": out.rationale, "warnings": warnings}


# ------------------------------------------------------------------ roles: audit and choice

def role_norm(role: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", role.lower()).strip()


def audit_roles(user_id: str) -> dict:
    """After the fact bank is confirmed: which roles and fields the student's record supports,
    including every one they asked for, with an honest fit. Fit is checked in code against
    the confirmed items it cites: strong needs two, good needs one."""
    with user_tx(user_id) as conn:
        profile = conn.execute("select headline, about, grad_date, batch_year, cgpa from profiles").fetchone() or {}
        prefs = conn.execute("select role_types, desired_roles, open_to from preferences").fetchone() or {}
        items = conn.execute("select id, key, kind, name, tagline, stack from items where confirmed order by sort").fetchall()
        bullets = conn.execute("select item_id, text from bullets where confirmed order by sort").fetchall()
        facts = conn.execute("select kind, text from facts where confirmed_at is not null and kind <> 'skill'").fetchall()
        skills = [r["text"] for r in conn.execute(
            "select text from facts where kind = 'skill' and confirmed_at is not null").fetchall()]
        edu = conn.execute("select institution, degree, meta from education where confirmed order by sort").fetchall()
        before = {(r["field"], role_norm(r["role"])) for r in conn.execute(
            "select field, role from role_options where selected").fetchall()}
    if not items and not skills:
        raise ValueError("Confirm at least one project, job or skill first")
    by_item: dict = {}
    for b in bullets:
        by_item.setdefault(b["item_id"], []).append(b["text"])
    volatile = llm.dumps({
        "asked_for": {"fields": prefs.get("role_types") or [], "roles": prefs.get("desired_roles") or [],
                      "open_to": prefs.get("open_to") or []},
        "profile": dict(profile), "education": [dict(e) for e in edu],
        "items": [{"key": i["key"], "kind": i["kind"], "name": i["name"], "tagline": i["tagline"],
                   "stack": i["stack"], "bullets": by_item.get(i["id"], [])} for i in items],
        "confirmed_facts": [dict(f) for f in facts], "confirmed_skills": skills,
    })
    out = llm.structured("onb_roles", RoleAudit, stable=[prompts.ROLES], volatile=volatile,
                         effort="medium", max_tokens=6000, ctx=llm.CallContext(user_id=user_id))
    options = check_role_options(out.options, {i["key"] for i in items})
    with user_tx(user_id) as conn:
        conn.execute("delete from role_options")
        for i, o in enumerate(options):
            conn.execute(
                """insert into role_options (user_id, field, role, fit, why, evidence_item_keys, gaps,
                       desired, selected, sort) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, o.field, o.role, o.fit, o.why, o.evidence_item_keys, o.gaps, o.desired,
                 (o.field, role_norm(o.role)) in before, i))
        conn.execute("update profiles set onboarding_step = 'roles' where user_id = %s", (user_id,))
    return {"summary": out.summary, "options": list_roles(user_id)}


def check_role_options(options: list, known_items: set[str]) -> list:
    """Drop duplicates and unknown fields, keep only cited items that are confirmed, and cap
    each fit at what those items support. Strongest first, the student's own asks first."""
    seen, kept = set(), []
    for o in options:
        role = " ".join(o.role.split())[:80]
        k = (o.field, role_norm(role))
        if not role or o.field not in FIELDS or k in seen:
            continue
        seen.add(k)
        ev = [x for x in dict.fromkeys(o.evidence_item_keys) if x in known_items]
        cap = "strong" if len(ev) >= 2 else "good" if ev else "stretch"
        fit = o.fit if FIT_RANK[o.fit] >= FIT_RANK[cap] else cap
        kept.append(o.model_copy(update={"role": role, "evidence_item_keys": ev, "fit": fit}))
    kept.sort(key=lambda o: (FIT_RANK[o.fit], not o.desired))
    return kept


def list_roles(user_id: str) -> list[dict]:
    """The audit's options, each with what the job pool holds for it: fresh public jobs in
    that field over the last 7 days, and whether the daily collector watches the role."""
    with user_tx(user_id) as conn:
        rows = conn.execute("select * from role_options order by sort").fetchall()
        pool = {r["field"]: r["n"] for r in conn.execute(
            """select extracted->>'discipline' as field, count(*) as n from jobs
               where visibility = 'public' and first_seen_at > now() - interval '7 days'
               group by 1""").fetchall()}
        watched = {(r["field"], r["role_norm"]) for r in conn.execute(
            "select field, role_norm from pool_watches where status = 'active'").fetchall()}
    return [{**r, "pool_jobs": pool.get(r["field"], 0),
             "watched": (r["field"], role_norm(r["role"])) in watched} for r in rows]


def select_roles(user_id: str, mode: str, option_ids: list[str]) -> list[dict]:
    """The student's choice: specific roles, or the mix (every strong and good fit). Sets the
    S3 discipline filter and the chosen titles, and registers each role with the job pool so
    the daily collector starts fetching for any role it does not cover yet."""
    with user_tx(user_id) as conn:
        opts = conn.execute("select id::text, field, role, fit from role_options order by sort").fetchall()
        if mode == "mix":
            chosen = [o for o in opts if o["fit"] in ("strong", "good")]
        else:
            wanted = set(option_ids)
            chosen = [o for o in opts if o["id"] in wanted]
        if not chosen:
            raise ValueError("Pick at least one role" if mode == "specific" else
                             "No strong or good fits yet: pick roles yourself, or add evidence and re-run the audit")
        ids = [o["id"] for o in chosen]
        fields = sorted({f for o in chosen for f in {o["field"]} | FIELD_NEIGHBOURS.get(o["field"], set())})
        conn.execute("update role_options set selected = (id = any(%s::uuid[]))", (ids,))
        conn.execute("""update preferences set role_types = %s, target_roles = %s, pool_mode = %s, updated_at = now()
                        where user_id = %s""", (fields, [o["role"] for o in chosen], mode, user_id))
        conn.execute("update profiles set onboarding_step = 'preferences' where user_id = %s", (user_id,))
    with system_tx() as conn:
        watch_ids = []
        for o in chosen:
            w = conn.execute(
                """insert into pool_watches (field, role, role_norm) values (%s, %s, %s)
                   on conflict (field, role_norm) do update set status = 'active' returning id""",
                (o["field"], o["role"], role_norm(o["role"]))).fetchone()
            watch_ids.append(w["id"])
            conn.execute("insert into pool_watch_users (watch_id, user_id) values (%s, %s) on conflict do nothing",
                         (w["id"], user_id))
        conn.execute("delete from pool_watch_users where user_id = %s and not (watch_id = any(%s))",
                     (user_id, watch_ids))
    return list_roles(user_id)
