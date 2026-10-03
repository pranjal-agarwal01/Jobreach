"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { GmailBanner } from "@/components/GmailConnect";
import OpportunityCard, { BucketHeading } from "@/components/OpportunityCard";
import { IconAlert, IconChevronRight, IconClock, IconMail, IconPaste } from "@/components/icons";
import { Badge, Button, Empty, ErrorNote, Freshness, Monogram, PageHeader, fmtWhen, hoursLabel } from "@/components/ui";
import { api } from "@/lib/api";
import { describe } from "@/lib/stage";
import type { Bucket, Today } from "@/lib/types";

const EVENT_LABEL: Record<string, string> = {
  interview: "Interview", assignment: "Assignment due", form_request: "Form to fill", gated_unpaid: "Unpaid offer to decide",
};
const ORDER: Bucket[] = ["strong", "good", "gaps"];
const FIRST_SHOWN = 5;

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
  const n = t.ready.length;
  const openings = ORDER.reduce((k, b) => k + t.groups[b].length, 0);
  const freshest = t.ready.reduce<number | null>((m, a) => a.age_at_draft_hours === null ? m
    : m === null ? a.age_at_draft_hours : Math.min(m, a.age_at_draft_hours), null);
  const who = t.me?.target_families?.length ? describe(t.me.career_stage, t.me.experience_years, t.me.target_families) : null;

  const title = n ? `${n} letter${n === 1 ? "" : "s"} ready to send`
    : openings ? `${openings} opening${openings === 1 ? "" : "s"} suit you` : "Nothing waiting yet";
  const sub = [
    who,
    n && openings ? `${openings} more opening${openings === 1 ? "" : "s"} below, best match first.` : null,
    n && freshest !== null ? `The freshest post is ${hoursLabel(freshest)} old; founders reply most to posts under six hours, so start at the top.` : null,
    !n && !openings ? "Openings from company job boards are scored for you as they're found, and appear here. Found a post yourself? Paste it and its letter is ready in about two minutes." : null,
  ].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-10">
      <PageHeader title={title} sub={sub}
        actions={<Link href="/leads"><Button variant="secondary"><IconPaste size={17} /> Paste a post</Button></Link>} />

      <GmailBanner />

      {t.processing > 0 && (
        <p className="-mt-6 inline-flex items-center gap-2 self-start rounded-full bg-accent-soft px-3 py-1 text-sm font-medium text-accent">
          <span className="size-2 animate-pulse rounded-full bg-accent" />
          Working on {t.processing} more: reading posts and writing letters
        </p>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-10">
          {n > 0 && (
            <section aria-labelledby="outbox">
              <h2 id="outbox" className="mb-3 text-[15px] font-semibold">Ready to send</h2>
              <ol className="paper divide-y divide-border overflow-hidden">
                {t.ready.map((a) => (
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
                      {a.in_gmail && <span className="hidden sm:inline-flex"><Badge tone="ok"><IconMail size={13} /> In Gmail</Badge></span>}
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
            </section>
          )}

          <section aria-labelledby="openings" className="flex flex-col gap-8">
            <div className="-mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="openings" className="text-[15px] font-semibold">Openings for you</h2>
              {openings > 0 && <p className="text-sm text-muted">Scored against your own work. Nothing is sent until you press Send.</p>}
            </div>
            {openings === 0 ? (
              <div className="rounded-2xl border border-dashed border-border-strong">
                <Empty action={<Link href="/leads"><Button>Paste a post</Button></Link>}>
                  Jobreach reads company job boards for the kinds of role you target. Each opening is checked and scored
                  against your own work, with the reasons and gaps spelled out. Pick one and its letter and tailored resume
                  are ready in about a minute. You read them, attach the PDF and press Send.
                </Empty>
              </div>
            ) : ORDER.filter((b) => t.groups[b].length > 0).map((b) => <Group key={b} bucket={b} t={t} reload={load} />)}
          </section>

          {t.decisions.length > 0 && (
            <section aria-labelledby="dropped">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="dropped" className="text-[15px] font-semibold">Dropped for you</h2>
                <p className="text-sm text-muted">You can still write to any of these.</p>
              </div>
              <ul className="flex flex-col gap-2">
                {t.decisions.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-border bg-surface px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{l.company_name ?? "Unknown company"} <span className="font-normal text-muted">{l.title}</span></p>
                      <p className="text-sm text-muted">{l.reasons?.[0]}</p>
                    </div>
                    <Button variant="ghost" onClick={async () => { await api.post(`/leads/${l.id}/override`); load(); }}>Write anyway</Button>
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

          {t.number_gaps.length > 0 && (
            <section aria-labelledby="numbers">
              <h2 id="numbers" className="mb-1 text-[15px] font-semibold">Lines that need a number</h2>
              <p className="mb-3 text-sm text-muted">Only if you know the real one. A vague line beats an invented figure.</p>
              <ul className="flex flex-col gap-3">
                {t.number_gaps.map((g) => (
                  <li key={g.id} className="border-l-2 border-accent/40 pl-3 text-sm leading-relaxed">
                    <p className="text-xs font-semibold text-accent">{g.item_name}</p>
                    <p className="text-text-2">{g.text}</p>
                  </li>
                ))}
              </ul>
              <Link href="/profile" className="mt-3 inline-block text-sm font-semibold text-accent hover:underline">Open your profile</Link>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function Group({ bucket, t, reload }: { bucket: Bucket; t: Today; reload: () => void }) {
  const [all, setAll] = useState(false);
  const items = t.groups[bucket];
  const shown = all ? items : items.slice(0, FIRST_SHOWN);
  return (
    <div>
      <BucketHeading bucket={bucket} count={items.length} />
      <ul className="flex flex-col gap-3">
        {shown.map((o) => <li key={o.id}><OpportunityCard o={o} onChange={reload} /></li>)}
      </ul>
      {items.length > shown.length && (
        <button type="button" onClick={() => setAll(true)} className="mt-3 text-sm font-semibold text-accent hover:underline">
          Show {items.length - shown.length} more
        </button>
      )}
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
