"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FIELDS, FIELD_LABEL } from "@/lib/fields";
import type { LeftOut, Review } from "@/lib/types";
import BaselineCard from "./BaselineCard";
import { IconCheck, IconChevronDown, IconSpark } from "./icons";
import { Button, ErrorNote, inputCls } from "./ui";

const MAX_FAMILIES = 4;

/** The review data (/onboarding/review), refreshed every few seconds while the background
 *  build, a re-render or a new family is still running. */
export function useReview() {
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    try { setReview(await api.get<Review>("/onboarding/review")); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, []);
  useEffect(() => {
    api.get<Review>("/onboarding/review").then(setReview).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  const status = review?.profile.build?.status;
  const busy = status === "queued" || status === "running";
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(reload, 2500);
    return () => clearInterval(id);
  }, [busy, reload]);
  return { review, reload, busy, error };
}

export function BaselineGrid({ review, busy, reload }: { review: Review; busy: boolean; reload: () => void }) {
  const failed = review.profile.build?.failed_tracks ?? {};
  const step = review.profile.build?.step;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {review.tracks.map((t) => (
          <BaselineCard key={`${t.key}:${t.baseline?.id ?? "none"}`} track={t} itemNames={review.item_names}
            rendering={busy && (step === "rendering" || step === "writing")} failed={failed[t.key]}
            onChanged={reload} removable={review.tracks.length > 1} />
        ))}
      </div>
      <AddFamily review={review} busy={busy} reload={reload} />
    </div>
  );
}

function AddFamily({ review, busy, reload }: { review: Review; busy: boolean; reload: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const have = new Set(review.tracks.map((t) => t.key));
  const full = have.size >= MAX_FAMILIES;
  const add = async (family: string) => {
    setAdding(family); setError(null);
    try { await api.post("/onboarding/families", { family }); await reload(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setAdding(null);
  };
  const suggestions = review.suggestions.filter((s) => !have.has(s.family));
  return (
    <div className="flex flex-col gap-3">
      {suggestions.length > 0 && !full && (
        <div className="flex flex-col gap-2 rounded-2xl bg-accent-soft/60 p-4">
          <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-accent"><IconSpark size={16} /> Your work also fits</p>
          {suggestions.map((s) => (
            <div key={s.family} className="flex flex-wrap items-center gap-3">
              <p className="min-w-0 flex-1 text-sm text-text-2"><span className="font-semibold text-text">{s.label}.</span> {s.why}</p>
              <Button variant="secondary" disabled={busy} busy={adding === s.family} onClick={() => add(s.family)}>Add a {s.label} resume</Button>
            </div>
          ))}
        </div>
      )}
      {!full && (
        <label className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Want another kind of role?</span>
          <select className={`${inputCls} w-auto! py-1.5 text-sm`} value="" disabled={busy || adding !== null}
            onChange={(e) => e.target.value && add(e.target.value)}>
            <option value="">Add a resume for…</option>
            {FIELDS.filter(([k]) => !have.has(k)).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          {adding && <span className="text-muted">Writing your {FIELD_LABEL[adding]} resume…</span>}
        </label>
      )}
      <ErrorNote error={error} />
    </div>
  );
}

const KIND_LABEL: Record<LeftOut["kind"], string> = {
  item: "Project or job", bullet: "Line", entry: "Award or role", education: "Education", skill: "Skill",
};

/** Lines the check couldn't find in the user's documents. Never asked about; listed so the
 *  user can put back anything that is true. */
export function LeftOutPanel({ items, onUsed }: { items: LeftOut[]; onUsed: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (items.length === 0) {
    return (
      <p className="inline-flex items-center gap-2 text-sm text-ok">
        <IconCheck size={16} /> Every line we read is backed by what you gave us. Nothing was left out.
      </p>
    );
  }
  const use = async (x: LeftOut) => {
    setBusy(x.id); setError(null);
    try { await api.post("/onboarding/use", { kind: x.kind, id: x.id }); onUsed(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  };
  return (
    <section className="rounded-2xl border border-border bg-surface">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center gap-3 px-5 py-4 text-left">
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">Left out: {items.length} line{items.length === 1 ? "" : "s"} we couldn&apos;t find in what you gave us</span>
          <span className="block text-sm text-muted">They stay off your resumes. Put one back only if it&apos;s true.</span>
        </span>
        <IconChevronDown size={18} className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul className="flex flex-col divide-y divide-border border-t border-border">
          {items.map((x) => (
            <li key={x.kind + x.id} className="flex flex-wrap items-start gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-muted">{KIND_LABEL[x.kind]}{x.context ? `, ${x.context}` : ""}</p>
                <p className="mt-0.5 text-[15px] leading-relaxed">{x.text}</p>
                {x.reason && <p className="mt-0.5 text-[13px] text-warn">{x.reason}</p>}
              </div>
              <Button variant="secondary" busy={busy === x.id} onClick={() => use(x)}>Use it anyway</Button>
            </li>
          ))}
        </ul>
      )}
      <div className="px-5"><ErrorNote error={error} /></div>
    </section>
  );
}
