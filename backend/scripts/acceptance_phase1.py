"""
Phase 1 acceptance report over real runs in the database (spec 13, Phase 1):

  - zero drafts marked ready (lint_ok) contain an em dash, a bare URL, an address not
    written in the post, or a number outside the fact bank and the post
  - every stored resume verified at exactly one page
  - time from paste to a finished draft
  - measured model cost per lead and per drafted application

    python scripts/acceptance_phase1.py            # all users (run as the database owner)

Re-checks stored drafts independently of the lint that passed them, so a lint bug shows up
here rather than in a recipient's inbox.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import system_tx  # noqa: E402
from app.pipeline.extract import published_emails  # noqa: E402
from app.pipeline.lint import EMAIL_RE, EM_DASH, URL_RE, _numbers  # noqa: E402


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"'))


def main():
    with system_tx() as conn:
        drafts = conn.execute(
            """select d.id, d.user_id, d.subject, d.html, d.to_addrs, d.lint_ok, j.raw_text,
                      p.signature_html
               from drafts d join applications a on a.id = d.application_id join jobs j on j.id = a.job_id
               left join preferences p on p.user_id = d.user_id""").fetchall()
        facts = {}
        for r in conn.execute("""select user_id, string_agg(text, ' ') as t from (
                                   select user_id, text from facts where confirmed_at is not null
                                   union all select user_id, concat_ws(' ', institution, degree, meta, result,
                                     array_to_string(lines, ' ')) from education where confirmed
                                   union all select user_id, concat_ws(' ', grad_date, batch_year::text, cgpa::text) from profiles
                                   union all select user_id, concat_ws(' ', stipend_floor::text, duration_flex, start_date) from preferences
                                   union all select user_id, title_line from tracks) x group by user_id""").fetchall():
            facts[r["user_id"]] = r["t"]
        pages = conn.execute("select pages_verified, count(*) as n from resumes group by pages_verified").fetchall()
        timing = conn.execute(
            """select count(*) as n, round(avg(extract(epoch from a.created_at - j.first_seen_at))) as avg_to_app_s,
                      round(max(extract(epoch from d.created_at - j.first_seen_at))) as max_to_draft_s,
                      round(avg(extract(epoch from d.created_at - j.first_seen_at))) as avg_to_draft_s
               from applications a join jobs j on j.id = a.job_id
               left join lateral (select created_at from drafts where application_id = a.id order by version limit 1) d on true""").fetchone()
        cost = conn.execute(
            """select (select round(avg(c), 4) from (select sum(cost_usd) c from llm_calls where job_id is not null group by job_id) t) as per_lead,
                      (select round(avg(c), 4) from (select sum(cost_usd) c from llm_calls where application_id is not null
                                                      or job_id in (select job_id from applications) group by coalesce(job_id, application_id)) t) as per_application,
                      (select count(*) from llm_calls) as calls""").fetchone()

    bad = []
    for d in drafts:
        if not d["lint_ok"]:
            continue
        body = plain(d["html"])
        sig = d["signature_html"] or ""
        if sig:
            body = body.replace(re.sub(r"\s+", " ", sig), " ")
        problems = []
        if EM_DASH in d["subject"] + body:
            problems.append("em dash")
        if URL_RE.findall(EMAIL_RE.sub(" ", body.replace(sig, ""))):
            problems.append("bare URL")
        for to in d["to_addrs"]:
            if to.lower() not in published_emails(d["raw_text"]):
                problems.append("unpublished address " + to)
        allowed = _numbers(facts.get(d["user_id"], "")) | _numbers(d["raw_text"]) | _numbers(sig)
        unknown = _numbers(d["subject"] + " " + body) - allowed
        if unknown:
            problems.append("numbers not backed: " + ", ".join(sorted(unknown)))
        if problems:
            bad.append((d["id"], problems))

    ready = sum(1 for d in drafts if d["lint_ok"])
    print("Drafts: {} total, {} marked ready".format(len(drafts), ready))
    print("Ready drafts failing the independent re-check: {}".format(len(bad)))
    for i, p in bad:
        print("  {}  {}".format(i, "; ".join(p)))
    print("Resumes by verified page count: {}".format({r["pages_verified"]: r["n"] for r in pages}))
    print("Paste to draft: avg {}s, max {}s over {} applications (target: under 120s)".format(
        timing["avg_to_draft_s"], timing["max_to_draft_s"], timing["n"]))
    print("Model cost: {} per lead, {} per drafted application ({} calls)".format(
        cost["per_lead"], cost["per_application"], cost["calls"]))
    ok = not bad and all(r["pages_verified"] == 1 for r in pages)
    print("\nAcceptance (no bad ready drafts, every resume one page): {}".format("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
