"""
S7 draft + S8 lint, with up to two rewrites that feed the failed checks back to the model.

The model returns plain paragraphs; code renders the HTML (so it is always well formed and
escaped) and appends the user's signature verbatim, so neither can be mangled by the model.
"""
from __future__ import annotations

import html as htmlmod
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from .. import llm
from . import lint as lintmod
from . import prompts
from .contacts import CONTEXT_LABEL
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


LEGAL_SUFFIX_RE = re.compile(r"[\s,]+(?:pvt\.?|private|ltd\.?|limited|llp|inc\.?|llc|corp\.?|"
                             r"corporation|gmbh|plc|co\.)(?=[\s,.]|$)", re.I)


def everyday_name(company: Optional[str]) -> Optional[str]:
    """The name people say: "Koenig Solutions Pvt. Ltd." -> "Koenig Solutions"."""
    if not company:
        return company
    short = company
    while True:
        cut = LEGAL_SUFFIX_RE.sub("", short, count=1).strip(" ,.")
        if cut == short or not cut:
            break
        short = cut
    return short or company


def display_name(name: Optional[str]) -> str:
    """A name as it is written in a letter: "PRASHANT PANWAR" -> "Prashant Panwar"."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    return name.title() if name and (name.isupper() or name.islower()) else name


def recipient_line(c, company: Optional[str]) -> str:
    """Who the letter goes to, from the chosen contact (contacts.Candidate)."""
    company = everyday_name(company)
    team = "the hiring team at {}".format(company) if company else "the hiring team"
    if c is None:
        return "Recipient: {}.".format(team)
    if c.person_name:
        return "Recipient: {}{}, address {}. Greet them by first name.".format(
            c.person_name, ", " + c.person_role if c.person_role else "", CONTEXT_LABEL[c.context])
    if c.context == "site_generic":
        return ("Recipient: the company's general inbox ({}); no hiring address is published. Greet the team "
                "and name the role in your first sentence.".format(c.email))
    return "Recipient: {} ({}, {}). Greet the team.".format(team, c.email, CONTEXT_LABEL[c.context])


SIGN_OFF = "Best regards,"


def _bare(url: str) -> str:
    """A link as people write it in a signature: no scheme, no www, no trailing slash."""
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", url.strip()).rstrip("/")


def default_signature(profile: dict) -> str:
    """How a letter ends when the person hasn't written their own sign-off. Gmail adds nothing to
    a draft created through its API, so without this a letter would stop mid-air. The web app's
    Preferences shows the same text (frontend/components/PreferencesForm.tsx, standardSignature)."""
    links = [_bare(u) for u in (profile.get("linkedin_url"), profile.get("github_url"), profile.get("portfolio_url"))
             if u and u.strip()]
    lines = [SIGN_OFF, display_name(profile.get("name")), (profile.get("phone") or "").strip(),
             " | ".join(dict.fromkeys(links))]
    return "\n".join(x for x in lines if x)


def signature_for(prefs: dict, profile: dict) -> str:
    return (prefs.get("signature_html") or "").strip() or default_signature(profile)


def _paragraphs(paragraphs: list[str]) -> list[str]:
    """One string per paragraph. The model sometimes puts the greeting and the first paragraph in
    one string with a line break between them; in HTML that break would vanish and the greeting
    would run into the text, so every line becomes its own paragraph."""
    return [q.strip() for p in paragraphs for q in re.split(r"\s*\n\s*", p) if q.strip()]


def render(d: EmailDraft, signature: Optional[str]) -> tuple[str, str, str]:
    """Return (html, plain_full, body_plain_without_signature)."""
    paras = _paragraphs(d.paragraphs)
    esc = lambda t: htmlmod.escape(t, quote=False)  # noqa: E731  (text, not attributes)
    html_parts = ["<p>{}</p>".format(esc(p)) for p in paras]
    plain_parts = list(paras)
    if d.work_bullets:
        at = min(2, len(html_parts))
        ul = "<ul>{}</ul>".format("".join("<li>{}</li>".format(esc(b)) for b in d.work_bullets))
        html_parts.insert(at, ul)
        plain_parts.insert(at, "\n".join("- " + b for b in d.work_bullets))
    body_plain = "\n\n".join(plain_parts)
    html = "\n".join(html_parts)
    plain = body_plain
    if signature:
        sig_html = "<br>".join(esc(line) for line in signature.strip().splitlines())
        html += "\n<p>{}</p>".format(sig_html)
        plain += "\n\n" + signature.strip()
    return html, plain, body_plain


def facts_context(facts: list[dict], profile: dict, prefs: dict) -> str:
    """Per-person and stable across openings: the cached part of the S7 prompt."""
    stage = profile.get("career_stage") or "student"
    seeker = {"name": display_name(profile.get("name")), "headline": profile.get("headline"), "stage": stage,
              "graduation": profile.get("grad_date"), "batch_year": profile.get("batch_year")}
    if stage != "student" and profile.get("experience_years") is not None:
        seeker["years_of_experience"] = int(float(profile["experience_years"]))
    availability = {"start": prefs.get("start_date")}
    if stage == "student":
        availability["duration"] = prefs.get("duration_flex")
    elif prefs.get("notice_period"):
        availability["notice_period"] = prefs.get("notice_period")
    return llm.dumps({
        "seeker": seeker, "availability": availability,
        "facts": [{"id": str(f["id"]), "kind": f["kind"], "text": f["text"]} for f in facts],
    })


def write(*, ex: Extracted, raw_text: str, sel: Selection, selected_bullets: list[str],
          facts: list[dict], profile: dict, prefs: dict, stipend_rule: str, to_addr: Optional[str],
          allowed_extra: list[str], ctx: llm.CallContext, recipient=None,
          published_in: Optional[list[str]] = None) -> DraftOut:
    """recipient: the chosen contacts.Candidate. published_in: where its address is written
    (the post, or the company's page it was found on); the lint checks it is there."""
    signature = signature_for(prefs, profile)
    floor = prefs.get("stipend_floor")
    stable = [prompts.DRAFT, "Seeker:\n" + facts_context(facts, profile, prefs)]
    base = "\n".join([
        "Role to apply for: {}".format(sel.role_title),
        "Company: {}".format(ex.company_name or "unknown"),
        recipient_line(recipient, ex.company_name),
        "Posted by: {} ({}, {})".format(ex.poster_name or "not named", ex.poster_role or "role unknown",
                                        ex.poster_type),
        "Lead with: {}".format(sel.lead_with),
        "What the post asks for that the seeker's record doesn't show (mention at most one, and only "
        "a hard requirement; see rule 10): {}".format("; ".join(sel.gaps[:3]) or "none"),
        "Pay instruction: {}".format(stipend_instruction(stipend_rule, floor, prefs.get("currency") or "INR")),
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
            published_in=published_in,
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


def html_to_plain(html: str) -> str:
    """A stored letter's HTML as plain text: paragraphs, line breaks and list items kept."""
    text = re.sub(r"</p>\s*", "\n\n", html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<li>", "- ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return htmlmod.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()
