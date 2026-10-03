"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { IconCheck, IconChevronDown, IconChevronRight, IconExternal, IconX } from "@/components/icons";
import { Badge, Button, Empty, ErrorNote, Field, PageHeader, fmtDayInline, hoursLabel, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { GmailBanner } from "@/components/GmailConnect";
import { BUCKET } from "@/lib/opportunity";
import type { Lead } from "@/lib/types";

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [foundBy, setFoundBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => api.get<Lead[]>("/leads").then(setLeads).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const active = leads?.some((l) => l.status === "queued" || l.status === "processing"
    || l.prepare_status === "queued" || l.prepare_status === "running");
  useEffect(() => {
    if (!active) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [active, load]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const r = await api.post<{ duplicate: boolean }>("/leads", { text, source_ref: url || null, found_by: foundBy || null });
      setNote(r.duplicate ? "You already pasted this post." : "Got it. It's read, scored for you and, if it suits you, its letter is written: usually under two minutes.");
      if (!r.duplicate) { setText(""); setUrl(""); }
      load();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-10">
      <PageHeader title="Add a lead"
        sub="Paste a hiring post you copied yourself, from LinkedIn or a careers page. It's screened, the company is checked, and a letter is written for you to read." />

      <form onSubmit={submit} className="paper max-w-3xl overflow-hidden">
        <label className="block">
          <span className="sr-only">The post</span>
          <textarea className="block min-h-56 w-full resize-y border-0 bg-transparent px-5 py-5 text-[15px] leading-relaxed outline-none placeholder:text-muted/80 sm:px-7"
            value={text} onChange={(e) => setText(e.target.value)} required
            placeholder={"Paste the whole post here, including who posted it and how old it is (like “3h”).\nPay terms are often in the last line, so copy to the end."} />
        </label>
        <details className="group border-t border-border">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-5 py-3 text-sm font-semibold text-text-2 sm:px-7">
            Link and source <span className="font-normal text-muted">(optional)</span>
            <IconChevronDown size={16} className="text-muted transition-transform group-open:rotate-180" />
          </summary>
          <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2 sm:px-7">
            <Field label="Link to the post"><input className={inputCls} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></Field>
            <Field label="How you found it" hint="The search you ran. Recorded to learn which searches lead to replies.">
              <input className={inputCls} value={foundBy} onChange={(e) => setFoundBy(e.target.value)} />
            </Field>
          </div>
        </details>
        <div className="flex flex-wrap items-center gap-3 border-t border-border bg-sunken/50 px-5 py-3 sm:px-7">
          <Button type="submit" busy={busy} className="min-h-10 px-5" disabled={text.trim().length < 40}>Screen and draft</Button>
          <span className="text-[13px] text-muted">Jobreach never logs into or scrapes LinkedIn. Pasted posts stay private to you.</span>
        </div>
      </form>
      <div className="-mt-6 flex max-w-3xl flex-col gap-3">
        {(note || (leads && leads.length > 0)) && <GmailBanner />}
        <ErrorNote error={error} />
        {note && <p className="inline-flex items-center gap-2 text-sm font-medium text-ok"><IconCheck size={16} /> {note}</p>}
      </div>

      <section aria-labelledby="yours" className="max-w-3xl">
        <h2 id="yours" className="mb-3 text-[15px] font-semibold">Posts you&apos;ve added</h2>
        {!leads ? <div className="h-40 animate-pulse rounded-2xl bg-sunken" /> : leads.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border-strong"><Empty>Nothing yet. Your first pasted post will show its result here.</Empty></div>
        ) : (
          <ul className="flex flex-col divide-y divide-border rounded-2xl border border-border bg-surface">
            {leads.map((l) => <LeadRow key={l.id} l={l} reload={load} />)}
          </ul>
        )}
      </section>
    </div>
  );
}

function LeadRow({ l, reload }: { l: Lead; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const pending = l.status === "queued" || l.status === "processing";
  const writing = l.prepare_status === "queued" || l.prepare_status === "running";
  const dropped = l.decision === "drop";
  return (
    <li className="px-4 py-3.5 sm:px-5">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className={`mt-1.5 size-2.5 shrink-0 rounded-full ${pending || writing ? "animate-pulse bg-accent" : l.status === "failed" || l.prepare_status === "failed" ? "bg-bad" : dropped ? "bg-border-strong" : "bg-ok"}`} />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">
            {l.company_name ?? (pending ? "Reading the post…" : "Unknown company")}
            {l.title && <span className="font-normal text-text-2"> {l.title}</span>}
          </p>
          <p className="mt-0.5 text-sm text-muted">
            {pending ? "Reading the post, checking the company and scoring it for you" :
              l.status === "failed" ? (l.error ?? "Something went wrong") :
              dropped ? l.reasons?.join(" ") :
              l.application_id ? "Letter ready" :
              writing ? "Suits you. Writing the letter and tailoring your resume" :
              l.source === "agent" && l.bucket === "gaps" ? "Worth a look, with gaps. Open it to prepare a letter" :
              l.prepare_status === "failed" ? `Couldn't prepare the letter: ${l.prepare_error ?? "try again from its page"}` :
              (l.error ?? "Suits you")}
            {l.posted_age_hours !== null && !pending && <span>{`, post was ${hoursLabel(l.posted_age_hours)} old`}</span>}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {l.source === "agent" && <Badge>Found by your agent</Badge>}
          {l.bucket && !dropped && <Badge tone={BUCKET[l.bucket].tone}>{BUCKET[l.bucket].short}</Badge>}
          {l.verification === "flag" && <Badge tone="warn">Check company</Badge>}
          {l.overridden && <Badge>Your call</Badge>}
          {l.application_id ? (
            <Link href={`/jobs/${l.application_id}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-accent hover:bg-accent-soft">
              Open folder <IconChevronRight size={16} />
            </Link>
          ) : l.match_id && !dropped && !pending && !writing ? (
            <Link href={`/opportunities/${l.match_id}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-accent hover:bg-accent-soft">
              Open <IconChevronRight size={16} />
            </Link>
          ) : !pending && (
            <button onClick={() => setOpen(!open)} aria-expanded={open} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-sunken" aria-label="More">
              <IconChevronDown size={18} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className="ml-5 mt-3 flex flex-wrap items-center gap-2 border-t border-dashed border-border pt-3">
          <span className="mr-auto text-xs text-muted">Added {fmtDayInline(l.first_seen_at)}</span>
          {l.source_ref && <a className="inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline" href={l.source_ref} target="_blank" rel="noreferrer"><IconExternal size={14} /> Original post</a>}
          {dropped && <Button variant="secondary" onClick={async () => { await api.post(`/leads/${l.id}/override`); reload(); }}>Write anyway</Button>}
          <Button variant="ghost" onClick={async () => { if (confirm("Delete this lead?")) { await api.del(`/leads/${l.id}`); reload(); } }}><IconX size={15} /> Delete</Button>
        </div>
      )}
    </li>
  );
}
