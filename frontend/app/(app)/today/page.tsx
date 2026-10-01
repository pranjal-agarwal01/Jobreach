"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { IconAlert, IconChevronRight, IconClock, IconPaste } from "@/components/icons";
import { Badge, Button, Empty, ErrorNote, Freshness, Monogram, PageHeader, fmtWhen, hoursLabel } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, Lead } from "@/lib/types";

interface Today {
  deadlines: { id: string; type: string; deadline_at: string | null; summary: string | null; application_id: string;
               company_name: string | null; role_title: string | null }[];
  drafts: Application[];
  decisions: Lead[];
  gaps: { id: string; text: string; item_name: string }[];
  processing: number;
}

const EVENT_LABEL: Record<string, string> = {
  interview: "Interview", assignment: "Assignment due", form_request: "Form to fill", gated_unpaid: "Unpaid offer to decide",
};

export default function TodayPage() {
  const [t, setT] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.get<Today>("/today").then(setT).catch((e) => setError(String(e.message ?? e))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!t?.processing) return;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [t?.processing, load]);

  if (!t) return error ? <ErrorNote error={error} /> : <Skeleton />;
  const n = t.drafts.length;
  const freshest = t.drafts.reduce<number | null>((m, a) => a.age_at_draft_hours === null ? m
    : m === null ? a.age_at_draft_hours : Math.min(m, a.age_at_draft_hours), null);

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        title={n ? `${n} letter${n === 1 ? "" : "s"} ready to send` : "Nothing waiting to send"}
        sub={n && freshest !== null
          ? `The freshest post is ${hoursLabel(freshest)} old. Founders reply most to posts under six hours, so start at the top.`
          : "Paste a fresh post from LinkedIn or a careers page and its letter will be here in about two minutes."}
        actions={<Link href="/leads"><Button variant="secondary"><IconPaste size={17} /> Paste a post</Button></Link>}
      />

      {t.processing > 0 && (
        <p className="-mt-6 inline-flex items-center gap-2 self-start rounded-full bg-accent-soft px-3 py-1 text-sm font-medium text-accent">
          <span className="size-2 animate-pulse rounded-full bg-accent" />
          Writing {t.processing} more letter{t.processing === 1 ? "" : "s"}
        </p>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-10">
          <section aria-labelledby="outbox">
            <h2 id="outbox" className="mb-3 text-[15px] font-semibold">Outbox</h2>
            {n === 0 ? (
              <div className="rounded-2xl border border-dashed border-border-strong">
                <Empty action={<Link href="/leads"><Button>Paste a post</Button></Link>}>
                  Every letter is drafted from your confirmed facts and checked before it lands here. You read it, attach the PDF and press Send.
                </Empty>
              </div>
            ) : (
              <ol className="paper divide-y divide-border overflow-hidden">
                {t.drafts.map((a) => (
                  <li key={a.id}>
                    <Link href={`/jobs/${a.id}`} className="group flex items-center gap-4 px-4 py-4 transition-colors hover:bg-sunken/60 sm:px-5">
                      <Monogram name={a.company_name ?? a.domain ?? "?"} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold">{a.company_name ?? a.domain ?? "Company"}</p>
                        <p className="truncate text-sm text-muted">{a.role_title}</p>
                      </div>
                      <div className="hidden flex-col items-end gap-1.5 sm:flex">
                        <Freshness hours={a.age_at_draft_hours} />
                        <span className="text-xs text-muted">{a.route === "email" ? `to ${a.apply_to}` : "apply on their portal"}</span>
                      </div>
                      {a.status === "needs_review" && <span className="hidden sm:inline-flex"><Badge tone="warn"><IconAlert size={13} /> Needs a look</Badge></span>}
                      <IconChevronRight size={18} className="shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
                    </Link>
                    <div className="-mt-2 flex items-center gap-3 px-4 pb-3 sm:hidden">
                      <Freshness hours={a.age_at_draft_hours} compact />
                      {a.status === "needs_review" && <Badge tone="warn"><IconAlert size={13} /> Needs a look</Badge>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {t.decisions.length > 0 && (
            <section aria-labelledby="dropped">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="dropped" className="text-[15px] font-semibold">Dropped for you</h2>
                <p className="text-sm text-muted">You can still draft any of these.</p>
              </div>
              <ul className="flex flex-col gap-2">
                {t.decisions.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-border bg-surface px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{l.company_name ?? "Unknown company"} <span className="font-normal text-muted">{l.title}</span></p>
                      <p className="text-sm text-muted">{l.reasons?.[0]}</p>
                    </div>
                    <Button variant="ghost" onClick={async () => { await api.post(`/leads/${l.id}/override`); load(); }}>Draft anyway</Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="flex flex-col gap-8">
          <section aria-labelledby="coming">
            <h2 id="coming" className="mb-3 text-[15px] font-semibold">Coming up</h2>
            {t.deadlines.length === 0 ? (
              <p className="text-sm leading-relaxed text-muted">Interviews and assignments you log on a job show up here with their deadlines.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {t.deadlines.map((d) => (
                  <li key={d.id}>
                    <Link href={`/jobs/${d.application_id}`} className="block rounded-2xl border border-ok/25 bg-ok-soft/60 p-4 transition-colors hover:border-ok/50">
                      <p className="text-sm font-semibold text-ok">{EVENT_LABEL[d.type] ?? d.type}</p>
                      <p className="mt-1 font-semibold">{d.company_name ?? "Company"}</p>
                      {d.deadline_at && (
                        <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-text-2"><IconClock size={15} /> {fmtWhen(d.deadline_at)}</p>
                      )}
                      {d.summary && <p className="mt-1 text-sm text-muted">{d.summary}</p>}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {t.gaps.length > 0 && (
            <section aria-labelledby="gaps">
              <h2 id="gaps" className="mb-1 text-[15px] font-semibold">Lines that need a number</h2>
              <p className="mb-3 text-sm text-muted">Only if you know the real one. A vague line beats an invented figure.</p>
              <ul className="flex flex-col gap-3">
                {t.gaps.map((g) => (
                  <li key={g.id} className="border-l-2 border-accent/40 pl-3 text-sm leading-relaxed">
                    <p className="text-xs font-semibold text-accent">{g.item_name}</p>
                    <p className="text-text-2">{g.text}</p>
                  </li>
                ))}
              </ul>
              <Link href="/profile" className="mt-3 inline-block text-sm font-semibold text-accent hover:underline">Open your fact bank</Link>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-6" aria-hidden="true">
      <div className="h-9 w-80 rounded-lg bg-sunken" />
      <div className="h-4 w-[28rem] max-w-full rounded bg-sunken" />
      <div className="mt-6 h-64 rounded-xl bg-sunken" />
    </div>
  );
}
