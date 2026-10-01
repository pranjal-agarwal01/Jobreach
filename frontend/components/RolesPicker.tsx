"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FIELD_LABEL } from "@/lib/fields";
import type { RoleOption } from "@/lib/types";
import { IconCheck, IconSpark } from "./icons";
import { Badge, Button, ErrorNote } from "./ui";

const FIT = {
  strong: { bars: 3, color: "bg-ok", text: "text-ok", label: "Strong fit", help: "Two or more of your confirmed projects or jobs show this work." },
  good: { bars: 2, color: "bg-accent", text: "text-accent", label: "Good fit", help: "One confirmed project or job shows this work." },
  stretch: { bars: 1, color: "bg-warn", text: "text-warn", label: "Stretch", help: "No confirmed project shows it yet. You can still choose it." },
} as const;

function FitMeter({ fit }: { fit: RoleOption["fit"] }) {
  const f = FIT[fit];
  return (
    <span className={`inline-flex items-center gap-2 text-xs font-semibold ${f.text}`} title={f.help}>
      <span className="flex items-end gap-[3px]" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={`w-[5px] rounded-sm ${i <= f.bars ? f.color : "bg-border-strong"}`} style={{ height: 6 + i * 3 }} />
        ))}
      </span>
      {f.label}
    </span>
  );
}

/** The audit's verdict: every role the student's confirmed record supports, with an honest
 *  fit and what the job pool holds for it. The student takes the mix or picks roles. */
export default function RolesPicker({ initialMode, onSaved, saveLabel = "Save my roles" }:
  { initialMode: "specific" | "mix"; onSaved?: () => void; saveLabel?: string }) {
  const [rows, setRows] = useState<RoleOption[] | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [mode, setMode] = useState(initialMode);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const show = (r: RoleOption[]) => { setRows(r); setPicked(new Set(r.filter((o) => o.selected).map((o) => o.id))); };

  async function audit() {
    setBusy("Reading your confirmed work against the roles companies post. About 20 seconds…");
    setError(null);
    try {
      const r = await api.post<{ summary: string; options: RoleOption[] }>("/onboarding/roles");
      setSummary(r.summary);
      show(r.options);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  }

  useEffect(() => {
    api.get<RoleOption[]>("/onboarding/roles").then((r) => {
      if (r.length) show(r);
      else audit();
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mix = rows?.filter((o) => o.fit !== "stretch") ?? [];
  const chosen = mode === "mix" ? new Set(mix.map((o) => o.id)) : picked;
  const fields = Array.from(new Set(rows?.map((o) => o.field) ?? []));
  const poolTotal = rows?.filter((o) => chosen.has(o.id)).reduce((n, o) => n + o.pool_jobs, 0) ?? 0;

  async function save() {
    setBusy("Saving");
    setError(null);
    setSaved(false);
    try {
      show(await api.post<RoleOption[]>("/onboarding/roles/select", { mode, option_ids: Array.from(picked) }));
      setSaved(true);
      onSaved?.();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  }

  if (!rows) {
    return (
      <div className="flex max-w-2xl items-center gap-4 rounded-2xl border border-border bg-surface p-6">
        <span className="size-5 shrink-0 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        <p className="text-[15px] text-text-2">{busy ?? "Loading your roles…"}</p>
        <ErrorNote error={error} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {summary && (
        <blockquote className="max-w-2xl border-l-[3px] border-accent pl-5">
          <p className="font-letter text-[20px] leading-[1.55] text-text sm:text-[22px]">{summary}</p>
          <footer className="mt-2 inline-flex items-center gap-1.5 text-sm text-muted"><IconSpark size={15} /> From your confirmed facts only</footer>
        </blockquote>
      )}

      <div className="grid max-w-3xl gap-3 sm:grid-cols-2" role="radiogroup" aria-label="How to choose roles">
        <ModeCard on={mode === "mix"} onClick={() => setMode("mix")} title="Mixed pool"
          text={`Every strong and good fit, ${mix.length} role${mix.length === 1 ? "" : "s"}. The most openings; each still gets its own resume.`} />
        <ModeCard on={mode === "specific"} onClick={() => setMode("specific")} title="Only the roles I pick"
          text="Fewer, more focused openings. Tick roles below." />
      </div>

      <div className="flex max-w-3xl flex-col gap-7">
        {fields.map((f) => (
          <section key={f} aria-label={FIELD_LABEL[f] ?? f}>
            <h3 className="mb-2.5 text-sm font-semibold text-muted">{FIELD_LABEL[f] ?? f}</h3>
            <ul className="flex flex-col gap-2.5">
              {rows.filter((o) => o.field === f).map((o) => {
                const on = chosen.has(o.id);
                return (
                  <li key={o.id}>
                    <label className={`flex gap-4 rounded-2xl border p-4 transition-colors sm:p-5
                      ${on ? "border-accent bg-accent-soft/60" : "border-border bg-surface"}
                      ${mode === "specific" ? "cursor-pointer hover:border-accent" : ""}`}>
                      <input type="checkbox" className="sr-only" checked={on} disabled={mode === "mix"}
                        onChange={() => {
                          const next = new Set(picked);
                          if (next.has(o.id)) next.delete(o.id); else next.add(o.id);
                          setPicked(next);
                        }} />
                      <span aria-hidden="true" className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-md border-2 transition-colors
                        ${on ? "border-accent bg-accent text-white dark:text-[#0b1020]" : "border-border-strong bg-surface"}`}>
                        {on && <IconCheck size={14} strokeWidth={3} />}
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-2">
                        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span className="text-[16px] font-semibold tracking-tight">{o.role}</span>
                          <FitMeter fit={o.fit} />
                          {o.desired && <Badge>You asked for this</Badge>}
                        </span>
                        {o.why && <span className="text-[15px] leading-relaxed text-text-2">{o.why}</span>}
                        {(o.evidence_item_keys.length > 0 || o.gaps.length > 0) && (
                          <span className="flex flex-wrap items-center gap-1.5">
                            {o.evidence_item_keys.map((k) => (
                              <span key={k} className="rounded-md border border-border bg-surface px-2 py-0.5 text-xs font-medium text-text-2">{k}</span>
                            ))}
                            {o.gaps.map((g) => (
                              <span key={g} className="rounded-md bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">missing: {g}</span>
                            ))}
                          </span>
                        )}
                        <PoolStatus o={o} />
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      <ErrorNote error={error} />
      <div className="sticky bottom-20 z-10 flex max-w-3xl flex-wrap items-center gap-3 rounded-2xl border border-border bg-surface/95 p-3 shadow-[0_12px_30px_-16px_rgb(20_27_52/0.4)] backdrop-blur md:bottom-4">
        <Button className="min-h-10 px-5" busy={busy === "Saving"} disabled={!!busy || chosen.size === 0} onClick={save}>
          {chosen.size === 0 ? "Choose at least one role" : `${saveLabel} (${chosen.size})`}
        </Button>
        <span className="text-sm text-muted">
          {saved ? <span className="inline-flex items-center gap-1 font-semibold text-ok"><IconCheck size={15} /> Saved</span>
            : poolTotal > 0 ? `${poolTotal} fresh openings in the pool this week for these roles` : "Openings arrive as the pool collects them"}
        </span>
        <Button variant="ghost" className="ml-auto" disabled={!!busy} onClick={audit}>Re-run audit</Button>
      </div>
      {busy && busy !== "Saving" && <p className="text-sm text-muted">{busy}</p>}
    </div>
  );
}

function ModeCard({ on, onClick, title, text }: { on: boolean; onClick: () => void; title: string; text: string }) {
  return (
    <button type="button" role="radio" aria-checked={on} onClick={onClick}
      className={`rounded-2xl border-2 p-4 text-left transition-colors ${on ? "border-accent bg-accent-soft/60" : "border-border bg-surface hover:border-border-strong"}`}>
      <span className="flex items-center gap-2.5 text-[15px] font-semibold">
        <span className={`grid size-[18px] place-items-center rounded-full border-2 ${on ? "border-accent" : "border-border-strong"}`}>
          {on && <span className="size-2 rounded-full bg-accent" />}
        </span>
        {title}
      </span>
      <span className="mt-1.5 block pl-7 text-sm leading-relaxed text-muted">{text}</span>
    </button>
  );
}

function PoolStatus({ o }: { o: RoleOption }) {
  if (o.pool_jobs > 0) {
    return (
      <span className="inline-flex items-center gap-2 text-[13px] font-medium text-ok">
        <span className="size-1.5 rounded-full bg-ok" /> {o.pool_jobs} fresh opening{o.pool_jobs === 1 ? "" : "s"} in the pool this week
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-muted">
      <span className="size-1.5 rounded-full bg-border-strong" />
      {o.watched ? "Not in the pool yet. Being collected daily." : "Not in the pool yet. Choosing it starts daily collection."}
    </span>
  );
}
