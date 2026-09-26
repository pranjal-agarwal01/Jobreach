"""
S7 draft + S8 lint, with up to two rewrites that feed the failed checks back to the model.

The model returns plain paragraphs; code renders the HTML (so it is always well formed and
escaped) and appends the user's signature verbatim, so neither can be mangled by the model.
"""
from __future__ import annotations

import html as htmlmod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from .. import llm
from . import lint as lintmod
from . import prompts
from .schemas import EmailDraft, Extracted, Selection

MAX_REWRITES = 2


@dataclass
class DraftOut:
    draft: EmailDraft
    subject: str
    html: str
    plain: str
    checks: list[lintmod.Check]
    attempts: int
    facts_used: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return lintmod.passed(self.checks)


def stipend_instruction(rule: str, floor: Optional[int], currency: str) -> str:
    if rule == "ask":
        return "The post does not state a stipend. Ask directly, in one sentence ending with a question mark, what the stipend is."
    if rule == "state_floor":
        return ("The role is unpaid. State plainly that the student needs a stipend of at least "
                "{} {:,} per month to take it on.".format("Rs" if currency == "INR" else currency, floor))
    return "Do not mention stipend or salary."


def render(d: EmailDraft, signature: Optional[str]) -> tuple[str, str, str]:
    """Return (html, plain_full, body_plain_without_signature)."""
    paras = [p.strip() for p in d.paragraphs if p.strip()]
    html_parts = ["<p>{}</p>".format(htmlmod.escape(p)) for p in paras]
    plain_parts = list(paras)
    if d.work_bullets:
        at = min(2, len(html_parts))
        ul = "<ul>{}</ul>".format("".join("<li>{}</li>".format(htmlmod.escape(b)) for b in d.work_bullets))
        html_parts.insert(at, ul)
        plain_parts.insert(at, "\n".join("- " + b for b in d.work_bullets))
    body_plain = "\n\n".join(plain_parts)
    html = "\n".join(html_parts)
    plain = body_plain
    if signature:
        sig_html = "<br>".join(htmlmod.escape(line) for line in signature.strip().splitlines())
        html += "\n<p>{}</p>".format(sig_html)
        plain += "\n\n" + signature.strip()
    return html, plain, body_plain


def facts_context(facts: list[dict], profile: dict, prefs: dict) -> str:
    """Per-user and stable across leads: the cached part of the S7 prompt."""
    return llm.dumps({
        "student": {"name": profile.get("name"), "headline": profile.get("headline"),
                    "graduation": profile.get("grad_date"), "batch_year": profile.get("batch_year")},
        "availability": {"start": prefs.get("start_date"), "duration": prefs.get("duration_flex")},
        "facts": [{"id": str(f["id"]), "kind": f["kind"], "text": f["text"]} for f in facts],
    })


def write(*, ex: Extracted, raw_text: str, sel: Selection, selected_bullets: list[str],
          facts: list[dict], profile: dict, prefs: dict, stipend_rule: str, to_addr: Optional[str],
          allowed_extra: list[str], ctx: llm.CallContext) -> DraftOut:
    signature = prefs.get("signature_html")
    floor = prefs.get("stipend_floor")
    stable = [prompts.DRAFT, "Student:\n" + facts_context(facts, profile, prefs)]
    base = "\n".join([
        "Role to apply for: {}".format(sel.role_title),
        "Company: {}".format(ex.company_name or "unknown"),
        "Poster: {} ({}, {})".format(ex.poster_name or "not named", ex.poster_role or "role unknown", ex.poster_type),
        "Lead with: {}".format(sel.lead_with),
        "Gaps to name honestly: {}".format("; ".join(sel.gaps) or "none"),
        "Stipend instruction: {}".format(stipend_instruction(stipend_rule, floor, prefs.get("currency") or "INR")),
        "Resume bullets on the attached resume (for reference; quote numbers exactly):",
        *["- " + b for b in selected_bullets],
        "",
        "<post>\n{}\n</post>".format(raw_text[:12000]),
    ])
    fact_texts = [f["text"] for f in facts]
    feedback = ""
    out: Optional[DraftOut] = None
    for attempt in range(1, MAX_REWRITES + 2):
        volatile = base + (("\n\nYour previous draft failed these checks; fix every one:\n" + feedback)
                           if feedback else "")
        d = llm.structured("s7_draft", EmailDraft, stable=stable, volatile=volatile,
                           effort="medium", max_tokens=4000, ctx=ctx)
        html, plain, body = render(d, signature)
        checks = lintmod.lint(
            subject=d.subject, body_text=body, html=html, to_addr=to_addr, raw_post=raw_text,
            fact_texts=fact_texts, allowed_extra=allowed_extra, recipient_type=d.recipient_type,
            roles_mentioned=d.roles_mentioned, stipend_rule=stipend_rule, floor=floor,
            duration_flex=prefs.get("duration_flex") or "", post_start_text=ex.start_text,
            user_start=prefs.get("start_date") or "", signature_text=signature, plain_full=plain)
        valid_ids = {str(f["id"]) for f in facts}
        out = DraftOut(draft=d, subject=d.subject, html=html, plain=plain, checks=checks,
                       attempts=attempt, facts_used=[f for f in d.facts_used if f in valid_ids])
        if out.ok:
            return out
        feedback = "\n".join("- {}: {}".format(c.name, c.detail or "failed") for c in checks if not c.ok)
    return out


def gmail_compose_url(to_addr: str, subject: str, plain: str) -> str:
    """Phase 1 delivery: a prefilled Gmail compose window (plain text, no attachment; the
    user attaches the resume). The body travels in the URL, so it lands in browser history."""
    return "https://mail.google.com/mail/?view=cm&fs=1&to={}&su={}&body={}".format(
        quote(to_addr), quote(subject), quote(plain))
