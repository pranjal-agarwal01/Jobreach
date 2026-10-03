"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IconSearch } from "@/components/icons";
import {
  Badge, Button, Empty, ErrorNote, Freshness, PageHeader, Postmark, SENT_STATES, STATUS_LABEL, STATUS_TONE, fmtDayInline, inputCls,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";

const FILTERS: [string, string, (s: string) => boolean][] = [
  ["all", "All", () => true],
  ["send", "To send", (s) => s === "drafted" || s === "needs_review"],
  ["sent", "Sent", (s) => s === "sent"],
  ["replies", "Replies", (s) => ["replied", "interview", "assignment"].includes(s)],
  ["closed", "Closed", (s) => ["rejected", "bounced", "closed"].includes(s)],
];

/** One folder per company, like the reference pipeline's local folders: the tailored resume
 *  (PDF) and the letter for that company live inside. */
export default function JobsPage() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  useEffect(() => { api.get<Application[]>("/applications").then(setApps).catch((e) => setError(e.message)); }, []);

  const needle = q.trim().toLowerCase();
  const test = FILTERS.find(([k]) => k === filter)![2];
  const shown = apps?.filter((a) => test(a.status)
    && (!needle || `${name(a)} ${a.role_title ?? ""}`.toLowerCase().includes(needle))) ?? [];

  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Jobs" sub="A folder for every company you write to, holding the letter and the one-page resume made for it." />

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Filter jobs" className="-mx-1 flex max-w-full gap-1 overflow-x-auto rounded-xl bg-sunken p-1 [scrollbar-width:none]">
          {FILTERS.map(([k, label, f]) => {
            const count = apps?.filter((a) => f(a.status)).length ?? 0;
            return (
              <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}
                className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${filter === k ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"}`}>
                {label} <span className="ml-0.5 tabular-nums text-muted">{count}</span>
              </button>
            );
          })}
        </div>
        <label className="relative ml-auto w-full sm:w-64">
          <span className="sr-only">Search jobs</span>
          <IconSearch size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input className={`${inputCls} pl-9`} placeholder="Search company or role" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
      </div>

      <ErrorNote error={error} />
      {!apps ? (
        <div className="grid animate-pulse gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
          {[0, 1, 2].map((i) => <div key={i} className="h-40 rounded-2xl bg-sunken" />)}
        </div>
      ) : shown.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border-strong">
          <Empty action={apps.length === 0 ? <Link href="/leads"><Button>Paste a post</Button></Link> : undefined}>
            {apps.length === 0
              ? "Your first folder appears here when you prepare a letter for an opening: the letter and a resume made for that company, side by side."
              : "No folders match. Try another filter or search."}
          </Empty>
        </div>
      ) : (
        <ul className="grid gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((a) => <li key={a.id}><Folder a={a} /></li>)}
        </ul>
      )}
    </div>
  );
}

const name = (a: Application) => a.company_name ?? a.domain ?? "Company";

function Folder({ a }: { a: Application }) {
  const sent = SENT_STATES.has(a.status);
  return (
    <Link href={`/jobs/${a.id}`} className="group relative block pt-9 outline-none" aria-label={`${name(a)}, ${a.role_title ?? ""}, ${STATUS_LABEL[a.status] ?? a.status}`}>
      {/* The folder's back panel and its tab. */}
      <span aria-hidden="true" className="absolute inset-x-0 bottom-0 top-3 rounded-[16px] bg-inland-edge" />
      <span aria-hidden="true" className="absolute left-0 top-0 h-5 w-28 rounded-t-[12px] bg-inland-edge" />
      {/* What's inside, peeking out: the resume and the letter. */}
      <span aria-hidden="true" className="paper absolute left-5 right-10 top-5 h-20 -rotate-[1.5deg] transition-transform duration-200 group-hover:-translate-y-1.5" />
      <span aria-hidden="true" className="paper-inland absolute left-10 right-5 top-6 h-20 rotate-1 overflow-hidden transition-transform duration-200 group-hover:-translate-y-1">
        <span className="airmail-edge block h-1" />
      </span>
      {/* The front. */}
      <div className="relative flex min-h-36 flex-col rounded-[16px] border border-inland-edge bg-[color-mix(in_oklab,var(--inland)_55%,var(--surface))] p-5 shadow-[0_-1px_0_rgb(255_255_255/0.6)_inset,0_10px_24px_-18px_rgb(20_27_52/0.45)] transition-shadow group-hover:shadow-[0_-1px_0_rgb(255_255_255/0.6)_inset,0_16px_30px_-18px_rgb(20_27_52/0.55)] group-focus-visible:ring-2 group-focus-visible:ring-accent">
        <p className="truncate pr-16 text-[17px] font-bold tracking-tight">{name(a)}</p>
        <p className="truncate pr-16 text-sm text-text-2">{a.role_title}</p>
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-5">
          <Badge tone={STATUS_TONE[a.status]}>{STATUS_LABEL[a.status] ?? a.status}</Badge>
          {sent
            ? <span className="text-xs text-muted">sent {fmtDayInline(a.user_marked_sent_at ?? a.created_at)}</span>
            : <Freshness hours={a.age_at_draft_hours} compact />}
          {a.route === "portal" && <span className="text-xs text-muted">portal</span>}
        </div>
        {sent && <Postmark date={a.user_marked_sent_at ?? a.created_at} className="absolute -right-2 -top-6" />}
      </div>
    </Link>
  );
}
