"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Bullet, Education, Entry, Fact, FactBank, Item, Provenance } from "@/lib/types";
import { IconX } from "./icons";
import { Badge, Button, Card, Empty, ErrorNote, inputCls } from "./ui";

type Run = (fn: () => Promise<unknown>) => Promise<void>;
type Kind = "item" | "bullet" | "entry" | "education" | "skill";

function Editable({ value, onSave, multiline = false, placeholder, label }:
  { value: string; onSave: (v: string) => Promise<void>; multiline?: boolean; placeholder?: string; label: string }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  if (!editing) {
    return (
      <button type="button" aria-label={`Edit ${label}`} className="text-left decoration-dotted underline-offset-4 hover:underline"
        onClick={() => { setDraft(value); setEditing(true); }}>
        {value || <span className="text-muted">{placeholder ?? "Add…"}</span>}
      </button>
    );
  }
  const save = async () => { setEditing(false); if (draft.trim() !== value) await onSave(draft.trim()); };
  return multiline ? (
    <textarea autoFocus aria-label={label} className={inputCls} rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={save} />
  ) : (
    <input autoFocus aria-label={label} className={inputCls} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={save}
      onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }} />
  );
}

/** An inline "add" row: a text field and a button, in place of a pop-up prompt. */
function AddRow({ label, placeholder, onAdd, multiline = false }:
  { label: string; placeholder: string; onAdd: (text: string) => Promise<void>; multiline?: boolean }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!open) return <Button variant="ghost" className="self-start" onClick={() => setOpen(true)}>{label}</Button>;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true); await onAdd(text.trim()); setBusy(false); setText(""); setOpen(false);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-start">
      {multiline
        ? <textarea autoFocus aria-label={label} className={inputCls} rows={2} placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} />
        : <input autoFocus aria-label={label} className={inputCls} placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} />}
      <div className="flex shrink-0 gap-2">
        <Button type="submit" busy={busy}>Add</Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}

/** A line the check couldn't back: shown muted, with why, and a way to put it back. */
function NotUsed({ provenance, onUse }: { provenance?: Provenance | null; onUse: () => void }) {
  return (
    <span className="flex flex-wrap items-center gap-2 text-xs">
      <Badge tone="warn">Not used</Badge>
      {provenance?.reason && <span className="text-muted">{provenance.reason}</span>}
      <button type="button" className="font-semibold text-accent hover:underline" onClick={onUse}>Use it</button>
    </span>
  );
}

function DeleteButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" aria-label={label} onClick={onClick}
      className="grid size-7 shrink-0 place-items-center rounded-md text-muted hover:bg-sunken hover:text-bad"><IconX size={15} /></button>
  );
}

/** The profile everything is built from. Every line came from what the user gave us, or from
 *  their own edits; click any text to change it. `onChange` fires after every edit, so the
 *  caller can offer to re-render the resumes. */
export default function FactBankEditor({ onChange }: { onChange?: () => void }) {
  const [fb, setFb] = useState<FactBank | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => setFb(await api.get<FactBank>("/factbank")), []);
  useEffect(() => {
    api.get<FactBank>("/factbank").then(setFb).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const run: Run = async (fn) => {
    setError(null);
    try { await fn(); await load(); onChange?.(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const use = (kind: Kind, id: string) => run(() => api.post("/onboarding/use", { kind, id }));

  if (!fb) return <div className="h-64 animate-pulse rounded-2xl bg-sunken" />;
  const skills = fb.facts.filter((f) => f.kind === "skill");
  const others = fb.facts.filter((f) => f.kind !== "skill");

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-2xl text-[15px] leading-relaxed text-muted">
        Every line here came from what you gave us. Click any text to change it. Lines marked <strong className="font-semibold text-text-2">Not used</strong> weren&apos;t
        found in your documents, so they stay off your resumes unless you put them back.
      </p>
      <ErrorNote error={error} />

      {fb.items.map((it) => <ItemCard key={it.id} item={it} run={run} use={use} />)}
      <Card>
        <AddRow label="Add a project or job" placeholder="Its name, for example: Splitsy"
          onAdd={(name) => run(() => api.post("/items", { name, kind: "project" }))} />
      </Card>

      {fb.sections.map((s) => (
        <Card key={s.id} title={s.heading}>
          {s.entries.length === 0 && <Empty>Nothing yet.</Empty>}
          <ul className="flex flex-col gap-2.5">
            {s.entries.map((e) => <EntryRow key={e.id} entry={e} run={run} use={use} />)}
          </ul>
          <div className="mt-3">
            <AddRow label={s.key === "awards" ? "Add an award" : "Add a role"}
              placeholder={s.key === "awards" ? "Award, certification or result" : "Role, for example: Web Lead, Coding Club"}
              onAdd={(text) => run(() => api.post("/entries", { section: s.key, text }))} />
          </div>
        </Card>
      ))}

      <Card title="Education">
        <ul className="flex flex-col gap-3">
          {fb.education.map((ed) => <EducationRow key={ed.id} ed={ed} run={run} use={use} />)}
        </ul>
        <div className="mt-3">
          <AddRow label="Add education" placeholder="Institution" onAdd={(institution) => run(() => api.post("/education", { institution }))} />
        </div>
      </Card>

      <Card title="Skills">
        <div className="flex flex-wrap gap-2">
          {skills.map((f) => <SkillChip key={f.id} fact={f} run={run} use={use} />)}
          {skills.length === 0 && <Empty>No skills yet.</Empty>}
        </div>
        <div className="mt-3">
          <AddRow label="Add a skill" placeholder="Skill, tool or language" onAdd={(text) => run(() => api.post("/facts", { kind: "skill", text }))} />
        </div>
      </Card>

      {others.length > 0 && (
        <Card title="Other details">
          <ul className="flex flex-col gap-2">
            {others.map((f) => (
              <li key={f.id} className={`flex items-start gap-3 text-sm ${f.confirmed_at ? "" : "opacity-70"}`}>
                <div className="flex-1">
                  <Editable label="detail" value={f.text} multiline onSave={(t) => run(() => api.patch(`/facts/${f.id}`, { text: t, confirmed: true }))} />
                  {!f.confirmed_at && <NotUsed provenance={f.provenance} onUse={() => run(() => api.patch(`/facts/${f.id}`, { confirmed: true }))} />}
                </div>
                <DeleteButton label="Delete this detail" onClick={() => run(() => api.del(`/facts/${f.id}`))} />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ItemCard({ item, run, use }: { item: Item; run: Run; use: (k: Kind, id: string) => Promise<void> }) {
  const patch = (b: Partial<Item>) => run(() => api.patch(`/items/${item.id}`, b));
  return (
    <Card>
      <div className={`flex flex-wrap items-start gap-3 ${item.confirmed ? "" : "opacity-70"}`}>
        <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[15px] font-semibold"><Editable label="name" value={item.name} onSave={(v) => patch({ name: v })} /></span>
            <span className="text-text-2"><Editable label="tagline" value={item.tagline ?? ""} placeholder="what it is, or the employer" onSave={(v) => patch({ tagline: v })} /></span>
            <Badge tone={item.kind === "experience" ? "accent" : "neutral"}>{item.kind === "experience" ? "Job" : "Project"}</Badge>
          </div>
          <div className="text-xs text-muted"><Editable label="period" value={item.period ?? ""} placeholder="period, e.g. Jan 2026 - Apr 2026" onSave={(v) => patch({ period: v })} /></div>
          <div className="text-xs"><span className="text-muted">{item.stack_label}: </span>
            <Editable label="tools" value={item.stack ?? ""} placeholder="tools used" onSave={(v) => patch({ stack: v })} /></div>
          {!item.confirmed && <NotUsed provenance={item.provenance} onUse={() => use("item", item.id)} />}
          {item.provenance?.trimmed && item.provenance.trimmed.length > 0 && (
            <p className="text-xs text-muted">Left off the header, not found in your documents: {item.provenance.trimmed.join("; ")}.</p>
          )}
        </div>
        <DeleteButton label={`Delete ${item.name}`} onClick={() => confirm(`Delete ${item.name}?`) && run(() => api.del(`/items/${item.id}`))} />
      </div>
      <ul className="mt-3 flex flex-col gap-2 border-l-2 border-border pl-4">
        {item.bullets.map((b) => <BulletRow key={b.id} b={b} run={run} use={use} />)}
      </ul>
      <div className="mt-2 pl-4">
        <AddRow label="Add a line" placeholder="Only what is true, with real numbers" multiline
          onAdd={(text) => run(() => api.post("/bullets", { item_id: item.id, text }))} />
      </div>
    </Card>
  );
}

function BulletRow({ b, run, use }: { b: Bullet; run: Run; use: (k: Kind, id: string) => Promise<void> }) {
  return (
    <li className={`flex items-start gap-3 text-sm leading-relaxed ${b.confirmed ? "" : "opacity-70"}`}>
      <div className="flex-1">
        <Editable label="line" value={b.text} multiline onSave={(t) => run(() => api.patch(`/bullets/${b.id}`, { text: t }))} />
        {!b.confirmed && <NotUsed provenance={b.provenance} onUse={() => use("bullet", b.id)} />}
      </div>
      <DeleteButton label="Delete this line" onClick={() => run(() => api.del(`/bullets/${b.id}`))} />
    </li>
  );
}

function EntryRow({ entry, run, use }: { entry: Entry; run: Run; use: (k: Kind, id: string) => Promise<void> }) {
  const patch = (b: Partial<Entry>) => run(() => api.patch(`/entries/${entry.id}`, b));
  return (
    <li className={`flex items-start gap-3 text-sm ${entry.confirmed ? "" : "opacity-70"}`}>
      <div className="flex-1">
        {entry.lead !== null && <strong><Editable label="title" value={entry.lead} onSave={(v) => patch({ lead: v })} /></strong>}
        <Editable label="text" value={entry.text} multiline onSave={(v) => patch({ text: v })} />
        {!entry.confirmed && <NotUsed provenance={entry.provenance} onUse={() => use("entry", entry.id)} />}
      </div>
      <DeleteButton label="Delete this entry" onClick={() => run(() => api.del(`/entries/${entry.id}`))} />
    </li>
  );
}

function EducationRow({ ed, run, use }: { ed: Education; run: Run; use: (k: Kind, id: string) => Promise<void> }) {
  const patch = (b: Partial<Education>) => run(() => api.patch(`/education/${ed.id}`, b));
  return (
    <li className={`flex items-start gap-3 text-sm ${ed.confirmed ? "" : "opacity-70"}`}>
      <div className="flex flex-1 flex-col gap-0.5">
        <strong><Editable label="institution" value={ed.institution} onSave={(v) => patch({ institution: v })} /></strong>
        <Editable label="degree" value={ed.degree ?? ""} placeholder="degree" onSave={(v) => patch({ degree: v })} />
        <span className="text-xs text-muted"><Editable label="place and dates" value={ed.meta ?? ""} placeholder="place and dates" onSave={(v) => patch({ meta: v })} /></span>
        <Editable label="result" value={ed.result ?? ""} placeholder="CGPA or result" onSave={(v) => patch({ result: v })} />
        {!ed.confirmed && <NotUsed provenance={ed.provenance} onUse={() => use("education", ed.id)} />}
      </div>
      <DeleteButton label={`Delete ${ed.institution}`} onClick={() => run(() => api.del(`/education/${ed.id}`))} />
    </li>
  );
}

function SkillChip({ fact, run, use }: { fact: Fact; run: Run; use: (k: Kind, id: string) => Promise<void> }) {
  const usable = !!fact.confirmed_at;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border py-1 pl-3 pr-1 text-sm
      ${usable ? "border-border bg-surface" : "border-dashed border-warn/50 bg-warn-soft/50 text-text-2"}`}
      title={usable ? undefined : fact.provenance?.reason ?? "Not found in your documents"}>
      {fact.text}
      {!usable && <button type="button" className="text-xs font-semibold text-accent hover:underline" onClick={() => use("skill", fact.id)}>Use it</button>}
      <button type="button" aria-label={`Remove ${fact.text}`} onClick={() => run(() => api.del(`/facts/${fact.id}`))}
        className="grid size-6 place-items-center rounded-full text-muted hover:bg-sunken hover:text-bad"><IconX size={13} /></button>
    </span>
  );
}
