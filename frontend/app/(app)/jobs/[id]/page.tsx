"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  IconAlert, IconCheck, IconChevronDown, IconCopy, IconDownload, IconExternal, IconEye, IconLink, IconSend, IconX,
} from "@/components/icons";
import {
  Badge, Button, ErrorNote, Field, Monogram, Postmark, SENT_STATES, STATUS_LABEL, fmtDayInline, fmtWhen,
  hoursLabel, inputCls,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { AppDetail, Draft, ResumeLink } from "@/lib/types";

const CHECK_LABELS: Record<string, string> = {
  no_em_dash: "No em dashes", no_bare_urls: "No bare links", html_well_formed: "Clean formatting",
  no_placeholders: "No placeholders left", recipient_published: "Address published by the company",
  numbers_backed: "Every number is from your facts or the post", length: "Right length for the reader",
  resume_attached: "Mentions the resume", one_role: "Asks for one role", availability_not_narrowed: "Your availability as you stated it",
  stipend_rule: "Stipend line", signature_verbatim: "Your signature, exactly",
};
const EVENT_TYPES: [string, string][] = [
  ["reply", "They replied"], ["interview", "Interview"], ["assignment", "Assignment"], ["rejection", "Rejection"],
  ["bounce", "Bounced"], ["auto_ack", "Automatic acknowledgement"], ["gated_unpaid", "Offer, but unpaid"],
  ["form_request", "Asked me to fill a form"], ["other", "Something else"],
];
const STATUSES = ["drafted", "needs_review", "sent", "replied", "interview", "assignment", "rejected", "bounced", "closed"];

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

/** The letter, rendered from its plain text: paragraphs, and "- " lines as a list. */
function LetterBody({ plain }: { plain: string }) {
  return (
    <div className="font-letter text-[16px] leading-[1.75] text-text sm:text-[16.5px]">
      {plain.split(/\n{2,}/).map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => l.startsWith("- "))) {
          return <ul key={i} className="mb-4 list-disc pl-6">{lines.map((l, j) => <li key={j}>{l.slice(2)}</li>)}</ul>;
        }
        return <p key={i} className="mb-4 last:mb-0">{lines.map((l, j) => <span key={j}>{j > 0 && <br />}{l}</span>)}</p>;
      })}
    </div>
  );
}

export default function JobFolderPage() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<AppDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [justSent, setJustSent] = useState(false);
  const load = useCallback(() => api.get<AppDetail>(`/applications/${id}`).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  if (!d) return error ? <ErrorNote error={error} /> : <div className="h-96 animate-pulse rounded-2xl bg-sunken" />;
  const { application: a, draft, resume, events } = d;
  const company = a.company_name ?? a.domain ?? "Company";
  const sent = SENT_STATES.has(a.status);

  const flash = (k: string) => { setCopied(k); setTimeout(() => setCopied((c) => (c === k ? null : c)), 1600); };
  async function copyRich(html: string, plain: string, k: string) {
    // Rich copy: Gmail keeps paragraphs and the link text, with no raw URLs.
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([html], { type: "text/html" }),
      "text/plain": new Blob([plain], { type: "text/plain" }),
    })]);
    flash(k);
  }
  async function copyWithLink() {
    if (!draft || !resume) return;
    try {
      const link = resume.link ?? await api.post<ResumeLink>(`/resumes/${resume.id}/link`);
      if (!resume.link) load();
      const v = withLink(draft, link.url, resume.filename);
      await copyRich(v.html, v.plain, "email-link");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  const copyText = async (text: string, k: string) => { await navigator.clipboard.writeText(text); flash(k); };
  const setStatus = async (status: string) => {
    await api.patch(`/applications/${id}`, { status });
    if (status === "sent") setJustSent(true);
    load();
  };
  const failed = draft?.lint.filter((c) => !c.ok) ?? [];

  return (
    <div className="flex flex-col gap-8">
      <nav aria-label="Breadcrumb" className="-mb-4 text-sm text-muted">
        <Link href="/jobs" className="hover:text-text">Jobs</Link>
        <span className="mx-2 text-border-strong">/</span>
        <span className="text-text-2">{company}</span>
      </nav>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <Monogram name={company} size={52} />
          <div className="min-w-0 flex-1">
            <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] sm:truncate sm:text-[28px]">{company}</h1>
            <p className="text-[15px] text-text-2">{a.role_title}
              {a.age_at_draft_hours !== null && <span className="text-muted">, post was {hoursLabel(a.age_at_draft_hours)} old when drafted</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 [&>*]:flex-1 sm:[&>*]:flex-none">
          {!sent && <Button onClick={() => setStatus("sent")} className="min-h-10 px-4"><IconSend size={17} /> I sent it</Button>}
          <label className="relative">
            <span className="sr-only">Status</span>
            <select value={a.status} onChange={(e) => setStatus(e.target.value)}
              className="min-h-10 w-full appearance-none rounded-[10px] border border-border-strong bg-surface py-2 pl-3 pr-9 text-sm font-semibold hover:border-muted">
              {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
            </select>
            <IconChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
          </label>
        </div>
      </header>

      {a.judgment_calls?.length > 0 && (
        <div className="flex gap-3 rounded-2xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-text">
          <IconAlert size={18} className="mt-0.5 shrink-0 text-warn" />
          <div>
            <p className="font-semibold">Your call before sending</p>
            <ul className="mt-1 list-disc pl-5 text-text-2">
              {a.judgment_calls.map((j, i) => <li key={i}>{j.startsWith("Check the company page yourself: ")
                ? <>Check the company page yourself: <a className="font-semibold text-accent hover:underline" target="_blank" rel="noreferrer" href={j.split(": ")[1]}>search LinkedIn</a></>
                : j}</li>)}
            </ul>
          </div>
        </div>
      )}
      <ErrorNote error={error} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-4">
          {a.route === "email" && draft ? (
            <>
              <article className="paper-inland relative overflow-hidden" aria-label="Email draft">
                <div className="airmail-edge h-2" />
                {sent && (
                  <Postmark date={a.user_marked_sent_at ?? new Date().toISOString()} animate={justSent}
                    className="absolute right-2 top-4 size-16 sm:right-8 sm:top-6 sm:size-24" />
                )}
                <div className="px-5 pb-8 pt-6 sm:px-10">
                  <dl className={`mb-6 grid grid-cols-[64px_minmax(0,1fr)] gap-y-2 border-b border-dashed border-inland-edge pb-5 text-sm ${sent ? "pr-14 sm:pr-24" : ""}`}>
                    <dt className="text-muted">To</dt>
                    <dd className="min-w-0"><CopyInline text={draft.to_addrs.join(", ")} done={copied === "to"} onCopy={() => copyText(draft.to_addrs[0] ?? "", "to")} /></dd>
                    <dt className="text-muted">Subject</dt>
                    <dd className="min-w-0 font-semibold"><CopyInline text={draft.subject} done={copied === "subject"} onCopy={() => copyText(draft.subject, "subject")} /></dd>
                  </dl>
                  <LetterBody plain={draft.plain} />
                </div>
                <footer className="flex flex-wrap items-center gap-2 border-t border-inland-edge bg-surface/70 px-5 py-3 sm:px-10">
                  <Button onClick={() => copyRich(draft.html, draft.plain, "email")}>
                    {copied === "email" ? <><IconCheck size={17} /> Copied</> : <><IconCopy size={17} /> Copy email</>}
                  </Button>
                  {resume && (
                    <Button variant="secondary" onClick={copyWithLink}>
                      {copied === "email-link" ? <><IconCheck size={17} /> Copied</> : <><IconLink size={17} /> Copy with resume link</>}
                    </Button>
                  )}
                  {draft.gmail_url && (
                    <a href={draft.gmail_url} target="_blank" rel="noreferrer"><Button variant="ghost"><IconExternal size={16} /> Open in Gmail</Button></a>
                  )}
                </footer>
              </article>
              <p className="px-1 text-[13px] leading-relaxed text-muted">
                Paste into Gmail, attach the PDF, press Send. &ldquo;Copy with resume link&rdquo; swaps &ldquo;resume is attached&rdquo;
                for a link, so there&apos;s nothing to attach.
              </p>
              <Checks draft={draft} failed={failed.length} />
            </>
          ) : (
            <article className="paper p-6">
              <h2 className="text-lg font-bold tracking-tight">Apply on their portal</h2>
              <p className="mt-1 text-[15px] text-text-2">This post has no published email address, so there&apos;s no letter. Upload the PDF on their page:</p>
              {a.apply_to && (a.apply_to.startsWith("http")
                ? <a className="mt-4 inline-flex items-center gap-2 font-semibold text-accent hover:underline" href={a.apply_to} target="_blank" rel="noreferrer"><IconExternal size={16} /> Open the application page</a>
                : <p className="mt-3 text-sm text-muted">{a.apply_to.replace("_", " ")}</p>)}
            </article>
          )}

          <details className="group rounded-2xl border border-border bg-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold">
              The post you pasted <IconChevronDown size={18} className="text-muted transition-transform group-open:rotate-180" />
            </summary>
            <pre className="whitespace-pre-wrap border-t border-border px-5 py-4 font-sans text-sm leading-relaxed text-text-2">{d.job.raw_text}</pre>
          </details>
        </div>

        <aside className="flex flex-col gap-6">
          {resume ? <ResumeSheet resume={resume} reload={load} copyText={copyText} copied={copied} /> : (
            <p className="text-sm text-muted">No resume was built for this job.</p>
          )}

          <section className="rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-[15px] font-semibold">About {company}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              {a.domain && <span className="text-text-2">{a.domain}</span>}
              {a.verification && (
                <Badge tone={a.verification === "pass" ? "ok" : a.verification === "flag" ? "warn" : "bad"}>
                  {a.verification === "pass" ? <><IconCheck size={13} /> Verified</> : a.verification === "flag" ? "Check yourself" : "Failed checks"}
                </Badge>
              )}
            </div>
            {a.business_summary && <p className="mt-3 text-sm leading-relaxed text-text-2">{a.business_summary}</p>}
            {a.source_ref && <a className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:underline" href={a.source_ref} target="_blank" rel="noreferrer"><IconExternal size={15} /> Original post</a>}
          </section>

          <Outcomes id={id} events={events} reload={load} />
        </aside>
      </div>
    </div>
  );
}

function CopyInline({ text, done, onCopy }: { text: string; done: boolean; onCopy: () => void }) {
  return (
    <button onClick={onCopy} className="group inline-flex max-w-full items-center gap-2 text-left hover:text-accent" title="Copy">
      <span className="break-words">{text}</span>
      {done ? <IconCheck size={14} className="shrink-0 text-ok" /> : <IconCopy size={14} className="shrink-0 text-muted opacity-0 transition-opacity group-hover:opacity-100" />}
    </button>
  );
}

function Checks({ draft, failed }: { draft: Draft; failed: number }) {
  return (
    <details className="group rounded-2xl border border-border bg-surface" open={failed > 0}>
      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4 text-sm">
        {failed === 0
          ? <span className="grid size-6 place-items-center rounded-full bg-ok-soft text-ok"><IconCheck size={15} strokeWidth={2.5} /></span>
          : <span className="grid size-6 place-items-center rounded-full bg-warn-soft text-warn"><IconAlert size={15} /></span>}
        <span className="flex-1 font-semibold">
          {failed === 0 ? `All ${draft.lint.length} checks passed` : `${failed} of ${draft.lint.length} checks need you before sending`}
        </span>
        <IconChevronDown size={18} className="text-muted transition-transform group-open:rotate-180" />
      </summary>
      <ul className="grid gap-x-6 gap-y-2 border-t border-border px-5 py-4 text-sm sm:grid-cols-2">
        {draft.lint.map((c) => (
          <li key={c.check} className="flex items-start gap-2">
            {c.ok ? <IconCheck size={16} className="mt-0.5 shrink-0 text-ok" /> : <IconX size={16} className="mt-0.5 shrink-0 text-bad" />}
            <span className={c.ok ? "text-text-2" : "font-semibold"}>{CHECK_LABELS[c.check] ?? c.check}
              {!c.ok && c.detail && <span className="block font-normal text-muted">{c.detail}</span>}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function ResumeSheet({ resume, reload, copyText, copied }: {
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
  const open = () => run("preview", async () => { setPreview(URL.createObjectURL(await api.blob(`/resumes/${resume.id}/pdf`))); });
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
    <section aria-label="Resume">
      <button onClick={open} className="paper group relative block w-full overflow-hidden text-left" aria-label={`Preview ${resume.filename}`}>
        {/* A sketch of the two-column page itself. */}
        <span aria-hidden="true" className="grid aspect-[1/0.62] grid-cols-[1.75fr_1fr] gap-4 p-5">
          <span className="flex flex-col gap-1.5">
            <span className="h-2.5 w-1/2 rounded-sm bg-text/80" />
            <span className="h-1.5 w-3/4 rounded-sm bg-accent/50" />
            <span className="mt-2 h-1 w-full rounded-sm bg-border-strong" /><span className="h-1 w-11/12 rounded-sm bg-border-strong" />
            <span className="mt-2 h-1.5 w-1/3 rounded-sm bg-accent/60" />
            {[0, 1, 2, 3, 4].map((i) => <span key={i} className="h-1 rounded-sm bg-border" style={{ width: `${92 - (i % 3) * 9}%` }} />)}
          </span>
          <span className="flex flex-col gap-1.5 border-l border-border pl-3">
            <span className="h-1.5 w-2/3 rounded-sm bg-accent/60" />
            {[0, 1, 2, 3].map((i) => <span key={i} className="h-1 rounded-sm bg-border" style={{ width: `${88 - i * 10}%` }} />)}
            <span className="mt-2 h-1.5 w-1/2 rounded-sm bg-accent/60" />
            {[0, 1, 2].map((i) => <span key={i} className="h-1 rounded-sm bg-border" style={{ width: `${80 - i * 12}%` }} />)}
          </span>
        </span>
        <span className="flex items-center justify-between gap-2 border-t border-border bg-surface px-4 py-3">
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{resume.filename}</span>
            <span className="text-xs text-muted">{resume.pages_verified} page, checked by rendering it</span>
          </span>
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-accent group-hover:underline">
            {busy === "preview" ? <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <IconEye size={16} />} View
          </span>
        </span>
      </button>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="secondary" busy={busy === "download"} onClick={() => run("download", () => api.download(`/resumes/${resume.id}/download`))}>
          <IconDownload size={16} /> Download
        </Button>
        <Button variant="secondary" busy={busy === "link"} onClick={copyLink}>
          {copied === "link" ? <><IconCheck size={16} /> Copied</> : <><IconLink size={16} /> {resume.link ? "Copy link" : "Share link"}</>}
        </Button>
      </div>
      {resume.link && (
        <p className="mt-2 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <span>Link opened {resume.link.opens} time{resume.link.opens === 1 ? "" : "s"}{resume.link.last_opened_at && `, last ${fmtDayInline(resume.link.last_opened_at)}`}.</span>
          <button className="font-semibold text-bad hover:underline" onClick={revoke}>Turn off</button>
        </p>
      )}
      <ErrorNote error={error} />

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <Stat label="ATS score" value={resume.ats_score ?? "–"} />
        <Stat label="Keyword match" value={resume.jd_match !== null ? `${Math.round(resume.jd_match)}%` : "–"} />
        <Stat label="Lines cut" value={resume.dropped_ids.length} />
      </dl>

      {preview && <PdfDialog url={preview} name={resume.filename} onClose={() => setPreview(null)} />}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-sunken px-2 py-2.5">
      <dd className="text-[17px] font-bold tabular-nums tracking-tight">{value}</dd>
      <dt className="text-[11px] font-medium text-muted">{label}</dt>
    </div>
  );
}

function PdfDialog({ url, name, onClose }: { url: string; name: string; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div role="dialog" aria-modal="true" aria-label={name} className="fixed inset-0 z-50 flex flex-col bg-[rgb(11_16_32/0.72)] p-3 backdrop-blur-sm sm:p-8" onClick={onClose}>
      <div className="mx-auto flex w-full max-w-4xl items-center justify-between pb-3 text-white">
        <span className="truncate text-sm font-semibold">{name}</span>
        <button ref={closeRef} onClick={onClose} className="grid size-10 place-items-center rounded-full hover:bg-white/10" aria-label="Close preview"><IconX size={20} /></button>
      </div>
      <iframe src={url} title={name} className="mx-auto w-full max-w-4xl flex-1 rounded-md bg-white" onClick={(e) => e.stopPropagation()} />
    </div>
  );
}

function Outcomes({ id, events, reload }: { id: string; events: AppDetail["events"]; reload: () => void }) {
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
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-[15px] font-semibold">What happened</h2>
      {events.length > 0 ? (
        <ol className="mt-3 flex flex-col gap-3 border-l border-border pl-4">
          {events.map((ev) => (
            <li key={ev.id} className="relative text-sm">
              <span className="absolute -left-[21px] top-1.5 size-2.5 rounded-full border-2 border-surface bg-accent" />
              <p className="font-semibold">{EVENT_TYPES.find(([k]) => k === ev.type)?.[1] ?? (ev.type === "sent" ? "Sent" : ev.type)}
                <span className="font-normal text-muted"> {fmtDayInline(ev.occurred_at)}</span></p>
              {ev.deadline_at && <p className="text-warn">Due {fmtWhen(ev.deadline_at)}</p>}
              {ev.summary && <p className="text-text-2">{ev.summary}</p>}
            </li>
          ))}
        </ol>
      ) : <p className="mt-1 text-sm text-muted">Log replies and interviews here to track them on Today.</p>}
      <details className="group mt-4">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-sm font-semibold text-accent">
          Log something <IconChevronDown size={16} className="transition-transform group-open:rotate-180" />
        </summary>
        <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
          <Field label="What happened">
            <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
              {EVENT_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </Field>
          <Field label="Deadline, if there is one"><input className={inputCls} type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
          <Field label="Note"><input className={inputCls} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="e.g. 30-minute call with the CTO" /></Field>
          <Button type="submit" busy={busy} className="self-start">Save</Button>
        </form>
      </details>
    </section>
  );
}
