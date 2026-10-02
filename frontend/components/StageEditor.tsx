"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { STAGES } from "@/lib/stage";
import type { Stage } from "@/lib/types";
import { Button, ErrorNote, Field, inputCls } from "./ui";

/** Where the user is in their career and how many full-time years they have. Both decide
 *  which openings they are matched with; years were worked out from their job dates. */
export default function StageEditor({ stage, years, onSaved, onCancel }:
  { stage: Stage | null; years: number | null; onSaved: () => void; onCancel?: () => void }) {
  const [s, setS] = useState<Stage>(stage ?? "student");
  const [y, setY] = useState(years !== null ? String(years) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true); setError(null);
    try {
      await api.put("/profile", { career_stage: s, experience_years: y.trim() === "" ? null : Number(y) });
      onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <div role="radiogroup" aria-label="Where you are" className="grid gap-2 sm:grid-cols-3">
        {STAGES.map((x) => (
          <button key={x.key} type="button" role="radio" aria-checked={s === x.key} onClick={() => setS(x.key)}
            className={`rounded-xl border px-4 py-3 text-left transition-colors ${s === x.key ? "border-accent bg-accent-soft" : "border-border-strong bg-surface hover:border-accent"}`}>
            <span className="block text-sm font-semibold">{x.label}</span>
            <span className="block text-xs text-muted">{x.hint}</span>
          </button>
        ))}
      </div>
      {s !== "student" && (
        <Field label="Full-time years of experience" hint="Worked out from the dates of your jobs. Internships don't count.">
          <input className={`${inputCls} max-w-32`} type="number" min="0" max="60" step="0.1" value={y} onChange={(e) => setY(e.target.value)} />
        </Field>
      )}
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button busy={busy} onClick={save}>Save</Button>
        {onCancel && <Button variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </div>
  );
}
