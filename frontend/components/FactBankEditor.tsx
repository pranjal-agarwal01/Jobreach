"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Bullet, Education, Entry, Fact, FactBank, Item } from "@/lib/types";
import { Badge, Button, Card, Empty, ErrorNote, inputCls } from "./ui";

function Editable({ value, onSave, multiline = false, placeholder }:
  { value: string; onSave: (v: string) => Promise<void>; multiline?: boolean; placeholder?: string }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  if (!editing) {
    return (
      <button className="text-left hover:underline hover:decoration-dotted" onClick={() => { setDraft(value); setEditing(true); }} title="Click to edit">
        {value || <span className="text-muted">{placeholder ?? "Add…"}</span>}
      </button>
    );
  }
  const save = async () => { setEditing(false); if (draft !== value) await onSave(draft); };
  return multiline ? (
    <textarea autoFocus className={inputCls} rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={save} />
  ) : (
    <input autoFocus className={inputCls} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={save}
      onKeyDown={(e) => e.key === "Enter" && save()} />
  );
}

function Check({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-muted" title="Confirm this is true">
      <input type="checkbox" className="size-4 accent-[var(--accent)]" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export default function FactBankEditor({ onChange }: { onChange?: (fb: FactBank) => void }) {
  const [fb, setFb] = useState<FactBank | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = useCallback((data: FactBank) => { setFb(data); onChange?.(data); }, [onChange]);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
  const load = useCallback(async () => { apply(await api.get<FactBank>("/factbank")); }, [apply]);
  useEffect(() => { api.get<FactBank>("/factbank").then(apply).catch(fail); }, [apply]);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); await load(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  if (!fb) return <p className="text-sm text-muted">Loading your fact bank…</p>;

  const unconfirmed = {
    item_ids: fb.items.filter((i) => !i.confirmed).map((i) => i.id),
    bullet_ids: fb.items.flatMap((i) => i.bullets.filter((b) => !b.confirmed).map((b) => b.id)),
    entry_ids: fb.sections.flatMap((s) => s.entries.filter((e) => !e.confirmed).map((e) => e.id)),
    education_ids: fb.education.filter((e) => !e.confirmed).map((e) => e.id),
    fact_ids: fb.facts.filter((f) => !f.confirmed_at).map((f) => f.id),
  };
  const pending = Object.values(unconfirmed).reduce((n, a) => n + a.length, 0);
  const skills = fb.facts.filter((f) => f.kind === "skill");
  const others = fb.facts.filter((f) => f.kind !== "skill");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3 text-sm">
        <span>
          Only <strong>confirmed</strong> lines ever reach a resume or an email. Tick each line you can
          stand behind in an interview; edit or delete anything that is wrong.
        </span>
        {pending > 0 && (
          <Button variant="secondary" busy={busy} onClick={async () => {
            if (!confirm(`Confirm all ${pending} unconfirmed lines as true?`)) return;
            setBusy(true); await run(() => api.post("/factbank/confirm", unconfirmed)); setBusy(false);
          }}>Confirm all {pending} remaining</Button>
        )}
      </div>
      <ErrorNote error={error} />

      {fb.items.map((it) => <ItemCard key={it.id} item={it} run={run} />)}
      <Button variant="secondary" className="self-start" onClick={() => {
        const name = prompt("Project or job name");
        if (name) run(() => api.post("/items", { name, kind: "project", confirmed: true }));
      }}>Add a project or job</Button>

      {fb.sections.map((s) => (
        <Card key={s.id} title={s.heading}>
          {s.entries.length === 0 && <Empty>Nothing yet.</Empty>}
          <ul className="flex flex-col gap-2">
            {s.entries.map((e) => <EntryRow key={e.id} entry={e} run={run} />)}
          </ul>
        </Card>
      ))}
      <div className="flex flex-wrap gap-2">
        {(["awards", "roles"] as const).map((sec) => (
          <Button key={sec} variant="secondary" onClick={() => {
            const text = prompt(sec === "awards" ? "Award, certification or result" : "Role or position (e.g. Web Lead, Coding Club)");
            if (text) run(() => api.post("/entries", { section: sec, text, confirmed: true }));
          }}>Add {sec === "awards" ? "an award" : "a role"}</Button>
        ))}
      </div>

      <Card title="Education">
        <ul className="flex flex-col gap-3">
          {fb.education.map((ed) => <EducationRow key={ed.id} ed={ed} run={run} />)}
        </ul>
        <Button variant="ghost" className="mt-2" onClick={() => {
          const institution = prompt("Institution");
          if (institution) run(() => api.post("/education", { institution, confirmed: true }));
        }}>Add education</Button>
      </Card>

      <Card title="Skills" actions={<Button variant="ghost" onClick={() => {
        const text = prompt("Skill, tool or language");
        if (text) run(() => api.post("/facts", { kind: "skill", text, confirmed: true }));
      }}>Add skill</Button>}>
        <div className="flex flex-wrap gap-2">
          {skills.map((f) => <SkillChip key={f.id} fact={f} run={run} />)}
          {skills.length === 0 && <Empty>No skills yet.</Empty>}
        </div>
      </Card>

      {others.length > 0 && (
        <Card title="Other facts" actions={<span className="text-xs text-muted">From the interview or your notes; bullets are written from these once confirmed.</span>}>
          <ul className="flex flex-col gap-2">
            {others.map((f) => (
              <li key={f.id} className="flex items-start gap-3 text-sm">
                <Check checked={!!f.confirmed_at} onChange={(v) => run(() => api.patch(`/facts/${f.id}`, { confirmed: v }))} />
                <div className="flex-1"><Editable value={f.text} multiline onSave={(t) => run(() => api.patch(`/facts/${f.id}`, { text: t }))} /></div>
                <Badge>{f.kind}</Badge>
                <button className="text-xs text-muted hover:text-bad" onClick={() => run(() => api.del(`/facts/${f.id}`))}>Delete</button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

type Run = (fn: () => Promise<unknown>) => Promise<void>;

function ItemCard({ item, run }: { item: Item; run: Run }) {
  const patch = (b: Partial<Item>) => run(() => api.patch(`/items/${item.id}`, b));
  return (
    <Card>
      <div className={`mb-3 flex flex-wrap items-start gap-3 ${item.confirmed ? "" : "rounded-md bg-warn-soft p-2"}`}>
        <Check checked={item.confirmed} onChange={(v) => patch({ confirmed: v })} />
        <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold"><Editable value={item.name} onSave={(v) => patch({ name: v })} /></span>
            <span className="text-muted">—</span>
            <Editable value={item.tagline ?? ""} placeholder="tagline or company" onSave={(v) => patch({ tagline: v })} />
            <Badge tone={item.kind === "experience" ? "accent" : "neutral"}>{item.kind}</Badge>
          </div>
          <div className="text-xs text-muted"><Editable value={item.period ?? ""} placeholder="period, e.g. Jan 2026 – Apr 2026" onSave={(v) => patch({ period: v })} /></div>
          <div className="text-xs"><span className="text-muted">{item.stack_label}: </span>
            <Editable value={item.stack ?? ""} placeholder="tools used" onSave={(v) => patch({ stack: v })} /></div>
        </div>
        <button className="text-xs text-muted hover:text-bad" onClick={() => confirm(`Delete ${item.name}?`) && run(() => api.del(`/items/${item.id}`))}>Delete</button>
      </div>
      <ul className="flex flex-col gap-2 pl-7">
        {item.bullets.map((b) => <BulletRow key={b.id} b={b} run={run} />)}
      </ul>
      <Button variant="ghost" className="ml-7 mt-2" onClick={() => {
        const text = prompt("New bullet (only what is true, with real numbers)");
        if (text) run(() => api.post("/bullets", { item_id: item.id, text, confirmed: true }));
      }}>Add bullet</Button>
    </Card>
  );
}

function BulletRow({ b, run }: { b: Bullet; run: Run }) {
  return (
    <li className={`flex items-start gap-3 text-sm ${b.confirmed ? "" : "rounded-md bg-warn-soft p-1.5"}`}>
      <Check checked={b.confirmed} onChange={(v) => run(() => api.patch(`/bullets/${b.id}`, { confirmed: v }))} />
      <div className="flex-1"><Editable value={b.text} multiline onSave={(t) => run(() => api.patch(`/bullets/${b.id}`, { text: t }))} /></div>
      {!b.has_metric && <span title="No number in this line. Onboarding may ask about it."><Badge>no metric</Badge></span>}
      <button className="text-xs text-muted hover:text-bad" onClick={() => run(() => api.del(`/bullets/${b.id}`))}>Delete</button>
    </li>
  );
}

function EntryRow({ entry, run }: { entry: Entry; run: Run }) {
  const patch = (b: Partial<Entry>) => run(() => api.patch(`/entries/${entry.id}`, b));
  return (
    <li className={`flex items-start gap-3 text-sm ${entry.confirmed ? "" : "rounded-md bg-warn-soft p-1.5"}`}>
      <Check checked={entry.confirmed} onChange={(v) => patch({ confirmed: v })} />
      <div className="flex-1">
        {entry.lead !== null && <strong><Editable value={entry.lead} onSave={(v) => patch({ lead: v })} /></strong>}
        <Editable value={entry.text} multiline onSave={(v) => patch({ text: v })} />
        {entry.tracks && <span className="ml-2 text-xs text-muted">only on: {entry.tracks.join(", ")}</span>}
      </div>
      <button className="text-xs text-muted hover:text-bad" onClick={() => run(() => api.del(`/entries/${entry.id}`))}>Delete</button>
    </li>
  );
}

function EducationRow({ ed, run }: { ed: Education; run: Run }) {
  const patch = (b: Partial<Education>) => run(() => api.patch(`/education/${ed.id}`, b));
  return (
    <li className={`flex items-start gap-3 text-sm ${ed.confirmed ? "" : "rounded-md bg-warn-soft p-1.5"}`}>
      <Check checked={ed.confirmed} onChange={(v) => patch({ confirmed: v })} />
      <div className="flex flex-1 flex-col gap-0.5">
        <strong><Editable value={ed.institution} onSave={(v) => patch({ institution: v })} /></strong>
        <Editable value={ed.degree ?? ""} placeholder="degree" onSave={(v) => patch({ degree: v })} />
        <span className="text-xs text-muted"><Editable value={ed.meta ?? ""} placeholder="place · dates" onSave={(v) => patch({ meta: v })} /></span>
        <Editable value={ed.result ?? ""} placeholder="CGPA / result" onSave={(v) => patch({ result: v })} />
        <Editable value={ed.lines.join("\n")} multiline placeholder="other lines (one per line)"
          onSave={(v) => patch({ lines: v.split("\n").map((s) => s.trim()).filter(Boolean) })} />
      </div>
      <button className="text-xs text-muted hover:text-bad" onClick={() => run(() => api.del(`/education/${ed.id}`))}>Delete</button>
    </li>
  );
}

function SkillChip({ fact, run }: { fact: Fact; run: Run }) {
  const unbacked = fact.confirmed_at && fact.evidence_items.length === 0;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs
      ${fact.confirmed_at ? (unbacked ? "border-warn text-warn" : "border-border") : "border-dashed border-border bg-warn-soft"}`}
      title={unbacked ? "No project, job or role mentions this skill. Add evidence or remove it." : undefined}>
      <input type="checkbox" className="size-3.5" checked={!!fact.confirmed_at}
        onChange={(e) => run(() => api.patch(`/facts/${fact.id}`, { confirmed: e.target.checked }))} />
      {fact.text}
      <button className="text-muted hover:text-bad" onClick={() => run(() => api.del(`/facts/${fact.id}`))} aria-label="Remove">×</button>
    </span>
  );
}
