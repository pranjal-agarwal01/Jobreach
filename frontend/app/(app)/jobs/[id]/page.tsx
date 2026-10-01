"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { FileIcon, FolderIcon, MailIcon } from "@/components/FileIcons";
import { Badge, Button, Card, ErrorNote, Field, STATUS_TONE, hoursLabel, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppDetail, Draft, ResumeLink } from "@/lib/types";

const CHECK_LABELS: Record<string, string> = {
  no_em_dash: "No em dash", no_bare_urls: "No bare links", html_well_formed: "Clean formatting",
  no_placeholders: "No placeholders", recipient_published: "Address published by the company",
  numbers_backed: "Every number from your facts or the post", length: "Length for the recipient",
  resume_attached: "Mentions the resume", one_role: "One role only",
  availability_not_narrowed: "Availability not narrowed", stipend_rule: "Stipend line", signature_verbatim: "Signature intact",
};

const EVENT_TYPES = ["reply", "interview", "assignment", "rejection", "bounce", "auto_ack", "gated_unpaid", "form_request", "other"];

const ATTACHED = /resume is attached/i;
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** The same email, pointing at the share link instead of an attachment. */
function withLink(draft: Draft, url: string, filename: string): { html: string; plain: string } {
  const a = `<a href="${esc(url)}">linked here</a>`;
  if (ATTACHED.test(draft.html)) {
    return {
      html: draft.html.replace(ATTACHED, (m) => m.slice(0, -"attached".length) + a),
      plain: draft.plain.replace(ATTACHED, (m) => m.slice(0, -"attached".length) + "linked here: " + url),
    };
  }
  return { html: draft.html + `<p>My resume: <a href="${esc(url)}">${esc(filename)}</a></p>`,
           plain: draft.plain + `\n\nMy resume: ${url}` };
}

export default function JobFolderPage() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<AppDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const load = useCallback(() => api.get<AppDetail>(`/applications/${id}`).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  if (!d) return error ? <ErrorNote error={error} /> : <p className="text-sm text-muted">Loading…</p>;
  const { application: a, draft, resume, events } = d;
  const company = a.company_name ?? a.domain ?? "Company";

  const flash = (k: string) => { setCopied(k); setTimeout(() => setCopied(null), 1500); };
  async function copyRich(html: string, plain: string, k: string) {
    // Rich copy: Gmail keeps paragraphs and the link text, with no raw URLs.
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([html], { type: "text/html" }),
      "text/plain": new Blob([plain], { type: "text/plain" }),
    })]);
    flash(k);
  }
  async function ensureLink(): Promise<ResumeLink> {
    const link = resume!.link ?? await api.post<ResumeLink>(`/resumes/${resume!.id}/link`);
    if (!resume!.link) load();
    return link;
  }
  async function copyWithLink() {
    if (!draft || !resume) return;
    try {
      const link = await ensureLink();
      const v = withLink(draft, link.url, resume.filename);
      await copyRich(v.html, v.plain, "email-link");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  const copyText = async (text: string, k: string) => { await navigator.clipboard.writeText(text); flash(k); };
  const setStatus = async (status: string) => { await api.patch(`/applications/${id}`, { status }); load(); };

  return (
    <div className="flex flex-col gap-5">
      <nav className="flex items-center gap-1.5 text-sm text-muted" aria-label="Breadcrumb">
        <Link href="/jobs" className="hover:text-text">Jobs</Link><span>/</span><span className="text-text">{company}</span>
      </nav>
      <div className="flex flex-wrap items-center gap-3">
        <FolderIcon className="size-8" />
        <h1 className="text-xl font-semibold">{company}</h1>
        <span className="text-muted">{a.role_title}</span>
        <Badge tone={STATUS_TONE[a.status]}>{a.status.replace("_", " ")}</Badge>
      </div>
      <ErrorNote error={error} />

      {a.judgment_calls?.length > 0 && (
        <Card title="Your call" className="border-warn">
          <ul className="list-disc pl-5 text-sm">
            {a.judgment_calls.map((j, i) => <li key={i}>{j.startsWith("Check the company page yourself: ")
              ? <>Check the company page yourself: <a className="text-accent hover:underline" target="_blank" rel="noreferrer" href={j.split(": ")[1]}>search LinkedIn</a></>
              : j}</li>)}
          </ul>
        </Card>
      )}

      <Card title="In this folder">
        <ul className="flex flex-col divide-y divide-border">
          {resume ? <ResumeFile resume={resume} reload={load} copyText={copyText} copied={copied} /> : (
            <li className="py-2 text-sm text-muted">No resume was built for this job.</li>
          )}
          {draft && (
            <li className="flex items-center gap-3 py-3">
              <MailIcon />
              <div className="min-w-0 flex-1 text-sm">
                <a href="#email" className="font-medium hover:underline">Email to {draft.to_addrs.join(", ")}</a>
                <p className="truncate text-xs text-muted">{draft.subject}</p>
              </div>
              <Badge tone={draft.lint_ok ? "ok" : "warn"}>{draft.lint_ok ? "checks passed" : "needs review"}</Badge>
            </li>
          )}
        </ul>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-5">
          {a.route === "email" && draft ? (
            <section id="email" className="scroll-mt-20">
              <Card title="Email draft" actions={<>
                <Button onClick={() => copyRich(draft.html, draft.plain, "email")}>
                  {copied === "email" ? "Copied" : "Copy email (attach the PDF)"}
                </Button>
                {resume && (
                  <Button variant="secondary" onClick={copyWithLink}>
                    {copied === "email-link" ? "Copied" : "Copy email with resume link"}
                  </Button>
                )}
                {draft.gmail_url && <a href={draft.gmail_url} target="_blank" rel="noreferrer"><Button variant="ghost">Open in Gmail</Button></a>}
              </>}>
                {!draft.lint_ok && (
                  <p className="mb-3 rounded-md bg-warn-soft px-3 py-2 text-sm text-warn">
                    Some checks failed after two rewrites. Read it closely and fix the flagged lines in Gmail before sending.
                  </p>
                )}
                <dl className="mb-3 grid grid-cols-[70px_1fr] gap-y-1 text-sm">
                  <dt className="text-muted">To</dt>
                  <dd><button className="hover:underline" onClick={() => copyText(draft.to_addrs[0] ?? "", "address")}>{draft.to_addrs.join(", ")}</button>
                    {copied === "address" && <span className="ml-2 text-xs text-ok">copied</span>}</dd>
                  <dt className="text-muted">Subject</dt>
                  <dd><button className="text-left hover:underline" onClick={() => copyText(draft.subject, "subject")}>{draft.subject}</button>
                    {copied === "subject" && <span className="ml-2 text-xs text-ok">copied</span>}</dd>
                </dl>
                <div className="whitespace-pre-wrap rounded-md border border-border bg-bg p-3 text-sm leading-relaxed">{draft.plain}</div>
                <p className="mt-2 text-xs text-muted">
                  Paste into Gmail and press Send. &ldquo;Copy email&rdquo; expects you to attach the PDF; &ldquo;with resume
                  link&rdquo; changes &ldquo;resume is attached&rdquo; to a &ldquo;linked here&rdquo; link instead. Open in Gmail
                  pre-fills plain text only and puts the body in your browser history.
                </p>
              </Card>
            </section>
          ) : (
            <Card title="Apply through the portal">
              <p className="text-sm">This post has no published email. Submit the tailored PDF yourself:</p>
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
          <Card title="Status">
            <div className="flex flex-col gap-2">
              {["drafted", "needs_review"].includes(a.status) && <Button onClick={() => setStatus("sent")}>I sent it</Button>}
              <select className={inputCls} value={a.status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
                {["drafted", "needs_review", "sent", "replied", "interview", "assignment", "rejected", "bounced", "closed"].map((s) =>
                  <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
          </Card>

          {resume && (
            <Card title="Resume details">
              <dl className="grid grid-cols-2 gap-y-1 text-sm">
                <dt className="text-muted">Pages (verified)</dt><dd>{resume.pages_verified}</dd>
                <dt className="text-muted">Track</dt><dd>{resume.track_key}</dd>
                <dt className="text-muted">ATS score</dt><dd>{resume.ats_score ?? "–"}</dd>
                <dt className="text-muted">JD keyword match</dt><dd>{resume.jd_match !== null ? `${resume.jd_match}%` : "–"}</dd>
                <dt className="text-muted">Post age at draft</dt><dd>{hoursLabel(a.age_at_draft_hours)}</dd>
              </dl>
              {resume.dropped_ids.length > 0 && <p className="mt-2 text-xs text-muted">{resume.dropped_ids.length} line(s) left out to fit one page.</p>}
            </Card>
          )}

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
        <summary className="cursor-pointer font-medium">The post</summary>
        <pre className="mt-3 whitespace-pre-wrap font-sans text-muted">{d.job.raw_text}</pre>
      </details>
    </div>
  );
}

function ResumeFile({ resume, reload, copyText, copied }: {
  resume: NonNullable<AppDetail["resume"]>; reload: () => void;
  copyText: (t: string, k: string) => Promise<void>; copied: string | null;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function run(k: string, f: () => Promise<void>) {
    setBusy(k);
    setError(null);
    try { await f(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  }
  const togglePreview = () => run("preview", async () => {
    setPreview(preview ? null : URL.createObjectURL(await api.blob(`/resumes/${resume.id}/pdf`)));
  });
  const copyLink = () => run("link", async () => {
    const link = resume.link ?? await api.post<ResumeLink>(`/resumes/${resume.id}/link`);
    await copyText(link.url, "link");
    if (!resume.link) reload();
  });
  const revoke = () => run("revoke", async () => {
    if (!confirm("Turn off this link? Anyone who has it will no longer be able to open your resume.")) return;
    await api.del(`/resumes/${resume.id}/link`);
    reload();
  });

  return (
    <li className="flex flex-col gap-3 py-3 first:pt-0">
      <div className="flex flex-wrap items-center gap-3">
        <FileIcon label="PDF" />
        <div className="min-w-0 flex-1 text-sm">
          <p className="truncate font-medium">{resume.filename}</p>
          <p className="text-xs text-muted">
            {resume.pages_verified} page, checked by rendering
            {resume.link && <> · shared link opened {resume.link.opens} time{resume.link.opens === 1 ? "" : "s"}</>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" busy={busy === "preview"} onClick={togglePreview}>{preview ? "Hide preview" : "Preview"}</Button>
          <Button variant="secondary" busy={busy === "download"}
            onClick={() => run("download", () => api.download(`/resumes/${resume.id}/download`))}>Download</Button>
          <Button variant="secondary" busy={busy === "link"} onClick={copyLink}>
            {copied === "link" ? "Link copied" : resume.link ? "Copy link" : "Create share link"}
          </Button>
          {resume.link && <Button variant="ghost" busy={busy === "revoke"} onClick={revoke}>Turn off link</Button>}
        </div>
      </div>
      <ErrorNote error={error} />
      {preview && (
        <iframe src={preview} title={`Preview of ${resume.filename}`}
          className="h-[80vh] w-full rounded-md border border-border bg-bg" />
      )}
    </li>
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
