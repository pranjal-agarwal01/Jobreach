"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";
import { api } from "@/lib/api";
import { BUCKET, contactLine, experienceLabel, kindLabel, payLabel, placeLabel, preparing } from "@/lib/opportunity";
import type { Bucket, Opportunity } from "@/lib/types";
import { IconAlert, IconCheck, IconChevronRight, IconMail, IconExternal } from "./icons";
import { Button, Monogram, hoursLabel } from "./ui";

const DIAL: Record<Bucket, string> = { strong: "text-ok", good: "text-accent", gaps: "text-warn" };

/** The match score as a small dial: how well this opening suits this person, out of 100. */
export function MatchDial({ score, bucket, size = 46 }: { score: number | null; bucket: Bucket | null; size?: number }) {
  const s = Math.max(0, Math.min(100, Math.round(Number(score ?? 0))));
  const r = 15.5, c = 2 * Math.PI * r;
  return (
    <span className={`relative inline-grid shrink-0 place-items-center ${bucket ? DIAL[bucket] : "text-muted"}`}
      style={{ width: size, height: size }} title={`Match ${s} out of 100`}>
      <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90" aria-hidden="true">
        <circle cx="18" cy="18" r={r} fill="none" stroke="currentColor" strokeOpacity="0.16" strokeWidth="3" />
        <circle cx="18" cy="18" r={r} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
          strokeDasharray={`${(s / 100) * c} ${c}`} className="transition-[stroke-dasharray] duration-700" />
      </svg>
      <span className="font-bold tabular-nums tracking-tight" style={{ fontSize: size * 0.32 }}>{s}</span>
      <span className="sr-only">match score {s} out of 100</span>
    </span>
  );
}

/** How old the posting is, in words a person scans: "posted 3h ago". */
export function Posted({ hours }: { hours: number | null }) {
  if (hours === null || hours === undefined) return null;
  const tone = hours < 6 ? "text-post" : hours < 24 ? "text-accent" : "text-muted";
  return <span className={`font-semibold ${tone}`}>posted {hoursLabel(Number(hours))} ago</span>;
}

export function Meta({ o }: { o: Opportunity }) {
  const parts: ReactNode[] = [placeLabel(o), kindLabel(o), experienceLabel(o), payLabel(o)].filter(Boolean);
  if (o.age_hours !== null) parts.push(<Posted hours={o.age_hours} />);
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted sm:gap-x-2">
      {parts.map((p, i) => (
        <span key={i} className="inline-flex items-center gap-2">
          {i > 0 && <span aria-hidden="true" className="hidden text-border-strong sm:inline">·</span>}{p}
        </span>
      ))}
    </p>
  );
}

export default function OpportunityCard({ o, onChange }: { o: Opportunity; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const company = o.company_name ?? o.domain ?? "Company";
  const contact = contactLine(o);
  const act = async (k: string, f: () => Promise<unknown>) => {
    setBusy(k); setError(null);
    try { await f(); onChange(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  };

  return (
    <article className="group relative rounded-2xl border border-border bg-surface p-4 transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-[var(--paper-shadow)] sm:p-5">
      <div className="flex gap-3.5 sm:gap-4">
        <Monogram name={company} size={42} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-[16px] font-bold tracking-tight">
                <Link href={`/opportunities/${o.id}`} className="outline-none after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-4 focus-visible:after:ring-accent/25">
                  {company}
                </Link>
              </h3>
              <p className="truncate text-[15px] text-text-2">{o.title}</p>
            </div>
            <MatchDial score={o.score} bucket={o.bucket} />
          </div>
          <div className="mt-1.5"><Meta o={o} /></div>

          {o.why.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1.5 text-sm leading-snug">
              {o.why.slice(0, 2).map((w) => (
                <li key={w} className="flex gap-2 text-text-2"><IconCheck size={15} className="mt-0.5 shrink-0 text-ok" strokeWidth={2.4} />{w}</li>
              ))}
            </ul>
          )}
          {o.gaps.length > 0 && (
            <ul className="mt-2.5 flex flex-wrap gap-1.5" aria-label="Gaps">
              {o.gaps.slice(0, 3).map((g) => <li key={g} className="rounded-full bg-warn-soft px-2.5 py-0.5 text-xs font-medium text-warn">{g}</li>)}
              {o.gaps.length > 3 && <li className="rounded-full bg-sunken px-2.5 py-0.5 text-xs text-muted">+{o.gaps.length - 3} more</li>}
            </ul>
          )}

          <footer className="mt-3.5 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-dashed border-border pt-3">
            <span className={`inline-flex min-w-0 items-center gap-1.5 text-[13px] ${contact.weak ? "text-warn" : "text-text-2"}`}>
              {o.route === "portal" ? <IconExternal size={15} className="shrink-0" /> : contact.weak ? <IconAlert size={15} className="shrink-0" /> : <IconMail size={15} className="shrink-0 text-muted" />}
              <span className="truncate">
                <span className="font-medium">{contact.who}</span>
                {contact.where && <span className="hidden text-muted sm:inline">, {contact.where}</span>}
              </span>
            </span>
            <div className="relative z-10 ml-auto flex items-center gap-1.5">
              {o.application_id ? (
                <Link href={`/jobs/${o.application_id}`} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-accent hover:bg-accent-soft">
                  Open letter <IconChevronRight size={16} />
                </Link>
              ) : preparing(o) ? (
                <span className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-3 py-1 text-[13px] font-semibold text-accent">
                  <span className="size-2 animate-pulse rounded-full bg-accent" /> Writing your letter
                </span>
              ) : (
                <>
                  <button type="button" disabled={busy !== null} onClick={() => act("dismiss", () => api.post(`/opportunities/${o.id}/dismiss`))}
                    className="rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-muted hover:bg-sunken hover:text-text disabled:opacity-50">
                    Not for me
                  </button>
                  <Button variant="secondary" busy={busy === "prepare"} disabled={busy !== null}
                    onClick={() => act("prepare", () => api.post(`/opportunities/${o.id}/prepare`))}>
                    {o.prepare_status === "failed" ? "Try again" : o.route === "portal" ? "Prepare resume" : "Prepare letter"}
                  </Button>
                </>
              )}
            </div>
          </footer>
          {(error || o.prepare_status === "failed") && (
            <p role="alert" className="mt-2 text-[13px] text-bad">{error ?? o.prepare_error ?? "Couldn't prepare this letter."}</p>
          )}
        </div>
      </div>
    </article>
  );
}

export function BucketHeading({ bucket, count }: { bucket: Bucket; count: number }) {
  const b = BUCKET[bucket];
  const dot = { ok: "bg-ok", accent: "bg-accent", warn: "bg-warn" }[b.tone];
  return (
    <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h3 className="inline-flex items-center gap-2 text-[15px] font-semibold">
        <span className={`size-2 rounded-full ${dot}`} aria-hidden="true" />{b.label}
        <span className="font-normal tabular-nums text-muted">{count}</span>
      </h3>
      <p className="text-sm text-muted">{b.blurb}</p>
    </div>
  );
}
