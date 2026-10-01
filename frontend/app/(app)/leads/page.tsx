"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Empty, ErrorNote, Field, hoursLabel, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
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
  const active = leads?.some((l) => l.status === "queued" || l.status === "processing");
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
      setNote(r.duplicate ? "You already pasted this post." : "Added. Screening, verifying and drafting now, usually under two minutes.");
      if (!r.duplicate) { setText(""); setUrl(""); }
      load();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Leads</h1>
      <Card title="Paste a post or job description">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <textarea className={inputCls} rows={8} value={text} onChange={(e) => setText(e.target.value)} required
            placeholder="Copy the whole post, including the poster's name and the post's age (e.g. '3h'). Pay terms are often in the last line." />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Link to the post (optional)"><input className={inputCls} value={url} onChange={(e) => setUrl(e.target.value)} /></Field>
            <Field label="How you found it (optional)" hint="e.g. the LinkedIn search you ran. Recorded to learn what converts.">
              <input className={inputCls} value={foundBy} onChange={(e) => setFoundBy(e.target.value)} />
            </Field>
          </div>
          <ErrorNote error={error} />
          {note && <p className="text-sm text-ok">{note}</p>}
          <Button type="submit" className="self-start" busy={busy}>Screen and draft</Button>
        </form>
        <p className="mt-3 text-xs text-muted">
          Paste text you copied yourself. Jobreach never logs into or scrapes LinkedIn. Pasted posts stay private to you.
        </p>
      </Card>

      <Card title="Your leads">
        {!leads ? <p className="text-sm text-muted">Loading…</p> : leads.length === 0 ? <Empty>No leads yet.</Empty> : (
          <ul className="divide-y divide-border">
            {leads.map((l) => <LeadRow key={l.id} l={l} reload={load} />)}
          </ul>
        )}
      </Card>
    </div>
  );
}

function LeadRow({ l, reload }: { l: Lead; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const pending = l.status === "queued" || l.status === "processing";
  return (
    <li className="py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <button className="min-w-0 flex-1 text-left font-medium hover:underline" onClick={() => setOpen(!open)}>
          {l.company_name ?? (pending ? "Reading post…" : "Unknown company")} · {l.title ?? "role"}
        </button>
        <span className="text-muted">{l.posted_age_hours !== null ? `posted ${hoursLabel(l.posted_age_hours)} before paste` : ""}</span>
        {pending && <Badge tone="accent">{l.status}…</Badge>}
        {l.status === "failed" && <Badge tone="bad">failed</Badge>}
        {l.decision === "keep" && <Badge tone="ok">{l.overridden ? "kept (your call)" : "kept"}</Badge>}
        {l.decision === "drop" && <Badge tone="bad">dropped</Badge>}
        {l.verification && <Badge tone={l.verification === "pass" ? "ok" : l.verification === "flag" ? "warn" : "bad"}>company {l.verification}</Badge>}
        {l.application_id && <Link href={`/jobs/${l.application_id}`} className="text-accent hover:underline">open folder →</Link>}
      </div>
      {l.decision === "drop" && l.reasons?.length ? <p className="mt-1 text-muted">{l.reasons.join(" · ")}</p> : null}
      {l.error && <p className="mt-1 text-muted">{l.error}</p>}
      {open && (
        <div className="mt-2 flex flex-col gap-2 rounded-md bg-bg p-3">
          {l.flags?.length ? (
            <div><p className="font-medium">Judgment calls</p>
              <ul className="list-disc pl-5 text-muted">{l.flags.map((f, i) => <li key={i}>{f}</li>)}</ul></div>
          ) : null}
          {l.source_ref && <a className="text-accent hover:underline" href={l.source_ref} target="_blank" rel="noreferrer">Original post</a>}
          <div className="flex gap-2">
            {l.decision === "drop" && !l.application_id && (
              <Button variant="secondary" onClick={async () => { await api.post(`/leads/${l.id}/override`); reload(); }}>Draft anyway</Button>
            )}
            <Button variant="ghost" onClick={async () => { if (confirm("Delete this lead?")) { await api.del(`/leads/${l.id}`); reload(); } }}>Delete</Button>
          </div>
        </div>
      )}
    </li>
  );
}
