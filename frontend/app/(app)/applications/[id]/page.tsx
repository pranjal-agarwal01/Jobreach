"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorNote, Field, STATUS_TONE, hoursLabel, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppDetail } from "@/lib/types";

const CHECK_LABELS: Record<string, string> = {
  no_em_dash: "No em dash", no_bare_urls: "No bare links", html_well_formed: "Clean formatting",
  no_placeholders: "No placeholders", recipient_published: "Address published by the company",
  numbers_backed: "Every number from your facts or the post", length: "Length for the recipient",
  resume_attached: "Says the resume is attached", one_role: "One role only",
  availability_not_narrowed: "Availability not narrowed", stipend_rule: "Stipend line", signature_verbatim: "Signature intact",
};

const EVENT_TYPES = ["reply", "interview", "assignment", "rejection", "bounce", "auto_ack", "gated_unpaid", "form_request", "other"];

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<AppDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const load = useCallback(() => api.get<AppDetail>(`/applications/${id}`).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  if (!d) return error ? <ErrorNote error={error} /> : <p className="text-sm text-muted">Loading…</p>;
  const { application: a, draft, resume, events } = d;

  async function copy(kind: "email" | "subject" | "address") {
    if (!draft) return;
    if (kind === "email") {
      // Rich copy: Gmail keeps paragraphs, and there are no raw URLs to rewrite.
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([draft.html], { type: "text/html" }),
        "text/plain": new Blob([draft.plain], { type: "text/plain" }),
      })]);
    } else {
      await navigator.clipboard.writeText(kind === "subject" ? draft.subject : draft.to_addrs[0] ?? "");
    }
    setCopied(kind);
    setTimeout(() => setCopied(null), 1500);
  }

  const setStatus = async (status: string) => { await api.patch(`/applications/${id}`, { status }); load(); };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">{a.company_name ?? a.domain ?? "Company"} · {a.role_title}</h1>
        <Badge tone={STATUS_TONE[a.status]}>{a.status.replace("_", " ")}</Badge>
        <span className="text-sm text-muted">post was {hoursLabel(a.age_at_draft_hours)} old when drafted · track {a.track_key}</span>
      </div>

      {a.judgment_calls?.length > 0 && (
        <Card title="Your call" className="border-warn">
          <ul className="list-disc pl-5 text-sm">
            {a.judgment_calls.map((j, i) => <li key={i}>{j.startsWith("Check the company page yourself: ")
              ? <>Check the company page yourself: <a className="text-accent hover:underline" target="_blank" rel="noreferrer" href={j.split(": ")[1]}>search LinkedIn</a></>
              : j}</li>)}
          </ul>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-5">
          {a.route === "email" && draft ? (
            <Card title="Email draft" actions={<>
              <Button onClick={() => copy("email")}>{copied === "email" ? "Copied" : "Copy email"}</Button>
              {draft.gmail_url && <a href={draft.gmail_url} target="_blank" rel="noreferrer"><Button variant="secondary">Open in Gmail</Button></a>}
            </>}>
              {!draft.lint_ok && (
                <p className="mb-3 rounded-md bg-warn-soft px-3 py-2 text-sm text-warn">
                  Some checks failed after two rewrites. Read it closely and fix the flagged lines in Gmail before sending.
                </p>
              )}
              <dl className="mb-3 grid grid-cols-[70px_1fr] gap-y-1 text-sm">
                <dt className="text-muted">To</dt>
                <dd><button className="hover:underline" onClick={() => copy("address")}>{draft.to_addrs.join(", ")}</button>
                  {copied === "address" && <span className="ml-2 text-xs text-ok">copied</span>}</dd>
                <dt className="text-muted">Subject</dt>
                <dd><button className="text-left hover:underline" onClick={() => copy("subject")}>{draft.subject}</button>
                  {copied === "subject" && <span className="ml-2 text-xs text-ok">copied</span>}</dd>
              </dl>
              <div className="whitespace-pre-wrap rounded-md border border-border bg-bg p-3 text-sm leading-relaxed">{draft.plain}</div>
              <p className="mt-2 text-xs text-muted">
                Attach the resume yourself, then press Send in Gmail. Open in Gmail pre-fills plain text and puts the
                body in your browser history; Copy email keeps the formatting.
              </p>
            </Card>
          ) : (
            <Card title="Apply through the portal">
              <p className="text-sm">This post has no published email. Submit the tailored resume yourself:</p>
              {a.apply_to && (a.apply_to.startsWith("http")
                ? <a className="text-sm text-accent hover:underline" href={a.apply_to} target="_blank" rel="noreferrer">{a.apply_to}</a>
                : <p className="text-sm text-muted">{a.apply_to.replace("_", " ")}</p>)}
            </Card>
          )}

          {draft && (
            <Card title="Checks" actions={<Badge tone={draft.lint_ok ? "ok" : "warn"}>{draft.lint_ok ? "all passed" : "needs review"}</Badge>}>
              <ul className="grid gap-1 text-sm sm:grid-cols-2">
                {draft.lint.map((c) => (
                  <li key={c.check} className="flex items-start gap-2">
                    <span className={c.ok ? "text-ok" : "text-bad"}>{c.ok ? "✓" : "✗"}</span>
                    <span>{CHECK_LABELS[c.check] ?? c.check}{!c.ok && c.detail && <span className="block text-xs text-muted">{c.detail}</span>}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <EventLog id={id} events={events} reload={load} />
        </div>

        <div className="flex flex-col gap-5">
          <Card title="Resume">
            {resume ? (
              <div className="flex flex-col gap-2 text-sm">
                <Button onClick={() => api.download(`/resumes/${resume.id}/download`)}>Download .docx</Button>
                <dl className="grid grid-cols-2 gap-y-1">
                  <dt className="text-muted">Pages (verified)</dt><dd>{resume.pages_verified}</dd>
                  <dt className="text-muted">Type scale</dt><dd>{resume.scale}</dd>
                  <dt className="text-muted">ATS score</dt><dd>{resume.ats_score ?? "–"}</dd>
                  <dt className="text-muted">JD keyword match</dt><dd>{resume.jd_match !== null ? `${resume.jd_match}%` : "–"}</dd>
                </dl>
                {resume.dropped_ids.length > 0 && <p className="text-xs text-muted">{resume.dropped_ids.length} line(s) left out to fit one page.</p>}
                <p className="text-xs text-muted">Send the .docx, not a PDF: PDF text extraction mixes the two columns. Google Drive previews may show two pages; Word shows one.</p>
              </div>
            ) : <p className="text-sm text-muted">No resume.</p>}
          </Card>

          <Card title="Status">
            <div className="flex flex-col gap-2">
              {a.status !== "sent" && ["drafted", "needs_review"].includes(a.status) && (
                <Button onClick={() => setStatus("sent")}>I sent it</Button>
              )}
              <select className={inputCls} value={a.status} onChange={(e) => setStatus(e.target.value)}>
                {["drafted", "needs_review", "sent", "replied", "interview", "assignment", "rejected", "bounced", "closed"].map((s) =>
                  <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
          </Card>

          <Card title="Company">
            <div className="flex flex-col gap-1 text-sm">
              {a.domain && <span>{a.domain}</span>}
              {a.verification && <Badge tone={a.verification === "pass" ? "ok" : a.verification === "flag" ? "warn" : "bad"}>check: {a.verification}</Badge>}
              {a.business_summary && <p className="text-muted">{a.business_summary}</p>}
              {a.source_ref && <a className="text-accent hover:underline" href={a.source_ref} target="_blank" rel="noreferrer">Original post</a>}
            </div>
          </Card>
        </div>
      </div>

      <details className="rounded-lg border border-border bg-surface p-4 text-sm">
        <summary className="cursor-pointer font-medium">The post you pasted</summary>
        <pre className="mt-3 whitespace-pre-wrap font-sans text-muted">{d.job.raw_text}</pre>
      </details>
    </div>
  );
}

function EventLog({ id, events, reload }: { id: string; events: AppDetail["events"]; reload: () => void }) {
  const [type, setType] = useState("reply");
  const [deadline, setDeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    await api.post(`/applications/${id}/events`, {
      type, summary: summary || null, deadline_at: deadline ? new Date(deadline).toISOString() : null,
    });
    setSummary(""); setDeadline(""); setBusy(false);
    reload();
  }
  return (
    <Card title="Outcomes">
      <form onSubmit={submit} className="mb-3 grid gap-2 sm:grid-cols-[150px_200px_1fr_auto] sm:items-end">
        <Field label="What happened">
          <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
            {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
          </select>
        </Field>
        <Field label="Deadline (if any)"><input className={inputCls} type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
        <Field label="Note"><input className={inputCls} value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
        <Button type="submit" busy={busy}>Log</Button>
      </form>
      <ul className="flex flex-col gap-1 text-sm">
        {events.map((ev) => (
          <li key={ev.id} className="flex flex-wrap gap-2">
            <span className="text-muted">{new Date(ev.occurred_at).toLocaleString()}</span>
            <Badge>{ev.type.replace("_", " ")}</Badge>
            {ev.deadline_at && <span className="text-warn">due {new Date(ev.deadline_at).toLocaleString()}</span>}
            {ev.summary && <span>{ev.summary}</span>}
          </li>
        ))}
      </ul>
    </Card>
  );
}
