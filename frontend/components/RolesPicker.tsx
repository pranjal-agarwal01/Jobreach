"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FIELD_LABEL } from "@/lib/fields";
import type { RoleOption } from "@/lib/types";
import { Badge, Button, Card, ErrorNote } from "./ui";

const FIT_TONE = { strong: "ok", good: "accent", stretch: "warn" } as const;
const FIT_HELP = {
  strong: "Two or more of your confirmed projects or jobs show this work.",
  good: "One confirmed project or job shows this work.",
  stretch: "No confirmed project shows it yet. You can still choose it.",
};

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

  const show = (r: RoleOption[]) => { setRows(r); setPicked(new Set(r.filter((o) => o.selected).map((o) => o.id))); };

  async function audit() {
    setBusy("Auditing your profile against the roles companies post. About 20 seconds…");
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

  async function save() {
    setBusy("Saving");
    setError(null);
    try {
      show(await api.post<RoleOption[]>("/onboarding/roles/select", { mode, option_ids: Array.from(picked) }));
      onSaved?.();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  }

  if (!rows) {
    return <Card><p className="text-sm text-muted">{busy ?? "Loading…"}</p><ErrorNote error={error} /></Card>;
  }

  return (
    <div className="flex flex-col gap-4">
      {summary && <p className="max-w-3xl rounded-md bg-accent-soft px-3 py-2 text-sm">{summary}</p>}

      <div className="grid gap-3 sm:grid-cols-2">
        <ModeCard on={mode === "mix"} onClick={() => setMode("mix")} title="Mixed pool"
          text={`Every strong and good fit: ${mix.length} role${mix.length === 1 ? "" : "s"}. Most openings, and each still gets its own resume.`} />
        <ModeCard on={mode === "specific"} onClick={() => setMode("specific")} title="Only the roles I pick"
          text="Fewer, more focused openings. Tick the roles below." />
      </div>

      {fields.map((f) => (
        <Card key={f} title={FIELD_LABEL[f] ?? f}>
          <ul className="flex flex-col divide-y divide-border">
            {rows.filter((o) => o.field === f).map((o) => {
              const on = chosen.has(o.id);
              return (
                <li key={o.id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                  <input type="checkbox" className="mt-1 size-4 accent-[var(--accent)]" checked={on}
                    disabled={mode === "mix"} aria-label={`Choose ${o.role}`}
                    onChange={() => {
                      const next = new Set(picked);
                      if (next.has(o.id)) next.delete(o.id); else next.add(o.id);
                      setPicked(next);
                    }} />
                  <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{o.role}</span>
                      <span title={FIT_HELP[o.fit]}><Badge tone={FIT_TONE[o.fit]}>{o.fit} fit</Badge></span>
                      {o.desired && <Badge>you asked for this</Badge>}
                    </div>
                    {o.why && <p className="text-muted">{o.why}</p>}
                    {o.evidence_item_keys.length > 0 && (
                      <p className="text-xs text-muted">Shown by: {o.evidence_item_keys.join(", ")}</p>
                    )}
                    {o.gaps.length > 0 && <p className="text-xs text-warn">Missing: {o.gaps.join("; ")}</p>}
                    <PoolStatus o={o} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ))}

      <ErrorNote error={error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button busy={busy === "Saving"} disabled={!!busy || chosen.size === 0} onClick={save}>
          {chosen.size === 0 ? "Choose at least one role" : `${saveLabel} (${chosen.size})`}
        </Button>
        <Button variant="ghost" busy={!!busy && busy !== "Saving"} disabled={!!busy} onClick={audit}>
          Re-run the audit
        </Button>
        {busy && busy !== "Saving" && <span className="text-sm text-muted">{busy}</span>}
      </div>
    </div>
  );
}

function ModeCard({ on, onClick, title, text }: { on: boolean; onClick: () => void; title: string; text: string }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on}
      className={`rounded-lg border p-4 text-left text-sm transition ${on ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-accent"}`}>
      <span className="flex items-center gap-2 font-semibold">
        <span className={`size-3.5 rounded-full border-2 ${on ? "border-accent bg-accent" : "border-border"}`} />
        {title}
      </span>
      <span className="mt-1 block text-muted">{text}</span>
    </button>
  );
}

function PoolStatus({ o }: { o: RoleOption }) {
  if (o.pool_jobs > 0) {
    return <p className="text-xs text-ok">{o.pool_jobs} fresh opening{o.pool_jobs === 1 ? "" : "s"} in the job pool this week</p>;
  }
  return (
    <p className="text-xs text-muted">
      {o.watched ? "Not in the job pool yet. Collection for this role is switched on." : "Not in the job pool yet. Choosing it switches on daily collection."}
    </p>
  );
}
