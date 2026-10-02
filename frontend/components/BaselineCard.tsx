"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FIT_LABEL, FIT_TONE } from "@/lib/stage";
import type { Track } from "@/lib/types";
import { IconChevronDown, IconDownload, IconEye, IconX } from "./icons";
import PdfDialog from "./PdfDialog";
import { Badge, Button, ErrorNote, Field, inputCls } from "./ui";

/** One baseline resume: the strong general version for a kind of role, which every opening of
 *  that kind is later tailored from. Edits are the user's own words and re-render the page. */
export default function BaselineCard({ track, itemNames, rendering, failed, onChanged, removable = true }: {
  track: Track; itemNames: Record<string, string>; rendering: boolean; failed?: string;
  onChanged: () => void; removable?: boolean;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const run = async (k: string, f: () => Promise<unknown>) => {
    setBusy(k); setError(null);
    try { await f(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  };
  const base = track.baseline;
  const waiting = !base || rendering;
  const order = track.left_sections.flatMap((s) => s.item_keys);

  return (
    <article className={`flex flex-col overflow-hidden rounded-2xl border border-border bg-surface ${editing ? "sm:col-span-2 xl:col-span-3" : ""}`}>
      <button type="button" disabled={!base} onClick={() => base && run("preview", async () =>
        setPreview(URL.createObjectURL(await api.blob(`/resumes/${base.id}/pdf`))))}
        className="group relative block bg-inland/60 px-6 pt-6 text-left disabled:cursor-default" aria-label={`Preview the ${track.label} resume`}>
        {/* The page itself, sketched: its title line and the projects on it, in order. */}
        <span className={`paper block h-44 overflow-hidden px-5 pt-4 transition-transform duration-300 group-hover:-translate-y-1 ${waiting ? "animate-pulse" : ""}`}>
          <span className="block truncate text-[13px] font-extrabold tracking-tight text-accent-strong">{track.title_line}</span>
          <span className="mt-2 block h-1 w-11/12 rounded-sm bg-border" />
          <span className="mt-1 block h-1 w-4/5 rounded-sm bg-border" />
          {order.slice(0, 4).map((k) => (
            <span key={k} className="mt-3 block">
              <span className="block truncate text-[11px] font-bold">{itemNames[k] ?? k}</span>
              <span className="mt-1 block h-1 w-full rounded-sm bg-border" />
              <span className="mt-1 block h-1 w-5/6 rounded-sm bg-border" />
            </span>
          ))}
        </span>
        {base && !rendering && (
          <span className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full bg-surface/90 px-2.5 py-1 text-xs font-semibold text-accent opacity-0 shadow-sm transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
            {busy === "preview" ? <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <IconEye size={14} />} View
          </span>
        )}
      </button>

      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[17px] font-bold tracking-tight">{track.label}</h3>
          {track.fit && <Badge tone={FIT_TONE[track.fit]}>{FIT_LABEL[track.fit]}</Badge>}
          <span className="ml-auto text-xs text-muted">
            {failed ? <span className="text-bad">Couldn&apos;t fit to one page</span>
              : waiting ? "Fitting to one page…" : "One page, checked"}
          </span>
        </div>
        {track.fit_why && <p className="text-sm leading-relaxed text-text-2">{track.fit_why}</p>}
        {failed && <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{failed}</p>}
        {track.gaps.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {track.gaps.map((g) => <span key={g} className="rounded-full bg-sunken px-2.5 py-0.5 text-xs text-text-2">{g}</span>)}
          </div>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
          <Button variant="secondary" disabled={!base || rendering} busy={busy === "download"}
            onClick={() => base && run("download", () => api.download(`/resumes/${base.id}/download`))}>
            <IconDownload size={16} /> Download
          </Button>
          <Button variant="ghost" onClick={() => setEditing(!editing)} aria-expanded={editing}>
            Edit <IconChevronDown size={15} className={`transition-transform ${editing ? "rotate-180" : ""}`} />
          </Button>
          {removable && (
            <button type="button" disabled={busy === "remove"} className="ml-auto rounded-lg px-2 py-1 text-sm text-muted hover:bg-sunken hover:text-bad disabled:opacity-50"
              onClick={() => {
                if (confirm(`Stop targeting ${track.label} roles and delete this resume?`)) {
                  run("remove", async () => { await api.del(`/onboarding/families/${track.key}`); onChanged(); });
                }
              }}>Remove</button>
          )}
        </div>
        <ErrorNote error={error} />
        {editing && <TrackForm track={track} itemNames={itemNames} onSaved={() => { setEditing(false); onChanged(); }} />}
      </div>
      {preview && <PdfDialog url={preview} name={`${track.label} resume`} onClose={() => setPreview(null)} />}
    </article>
  );
}

function TrackForm({ track, itemNames, onSaved }: { track: Track; itemNames: Record<string, string>; onSaved: () => void }) {
  const [edit, setEdit] = useState(track);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const used = new Set(edit.left_sections.flatMap((s) => s.item_keys));
  const spare = Object.keys(itemNames).filter((k) => !used.has(k));

  const move = (si: number, i: number, d: -1 | 1) => {
    const secs = edit.left_sections.map((s) => ({ ...s, item_keys: [...s.item_keys] }));
    const keys = secs[si].item_keys;
    const j = i + d;
    if (j < 0 || j >= keys.length) return;
    [keys[i], keys[j]] = [keys[j], keys[i]];
    setEdit({ ...edit, left_sections: secs });
  };
  const remove = (si: number, i: number) => setEdit({ ...edit, left_sections: edit.left_sections
    .map((s, k) => k === si ? { ...s, item_keys: s.item_keys.filter((_, x) => x !== i) } : s).filter((s) => s.item_keys.length) });
  const add = (key: string) => {
    const secs = edit.left_sections.length ? edit.left_sections : [{ heading: "Projects", item_keys: [] }];
    setEdit({ ...edit, left_sections: secs.map((s, k) => k === secs.length - 1 ? { ...s, item_keys: [...s.item_keys, key] } : s) });
  };
  async function save() {
    setBusy(true); setError(null);
    try {
      await api.put(`/tracks/${track.key}`, { title_line: edit.title_line, summary: edit.summary,
        left_sections: edit.left_sections, skills: edit.skills });
      onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  }

  return (
    <div className="mt-1 flex flex-col gap-4 border-t border-dashed border-border pt-4">
      <Field label="Title line"><input className={inputCls} value={edit.title_line} onChange={(e) => setEdit({ ...edit, title_line: e.target.value })} /></Field>
      <Field label="Summary" hint="In your own words. Keep to what you can talk about in an interview.">
        <textarea className={inputCls} rows={4} value={edit.summary} onChange={(e) => setEdit({ ...edit, summary: e.target.value })} />
      </Field>
      <div>
        <p className="mb-1.5 text-sm font-semibold">Order on the page</p>
        {edit.left_sections.map((s, si) => (
          <div key={si} className="mb-2">
            <input aria-label="Section heading" className={`${inputCls} mb-1 w-48 py-1 text-xs font-semibold`} value={s.heading}
              onChange={(e) => setEdit({ ...edit, left_sections: edit.left_sections.map((x, k) => k === si ? { ...x, heading: e.target.value } : x) })} />
            <ol className="flex flex-col gap-1">
              {s.item_keys.map((k, i) => (
                <li key={k} className="flex items-center gap-2 rounded-lg bg-sunken px-2.5 py-1.5 text-sm">
                  <span className="w-4 text-xs tabular-nums text-muted">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{itemNames[k] ?? k}</span>
                  <button type="button" aria-label="Move up" className="rounded px-1.5 text-muted hover:bg-surface hover:text-text" onClick={() => move(si, i, -1)}>Up</button>
                  <button type="button" aria-label="Move down" className="rounded px-1.5 text-muted hover:bg-surface hover:text-text" onClick={() => move(si, i, 1)}>Down</button>
                  <button type="button" aria-label="Take off this resume" className="grid size-6 place-items-center rounded text-muted hover:bg-surface hover:text-bad" onClick={() => remove(si, i)}><IconX size={14} /></button>
                </li>
              ))}
            </ol>
          </div>
        ))}
        {spare.length > 0 && (
          <select aria-label="Add a project or job" className={`${inputCls} mt-1 w-auto! py-1.5 text-sm`} value="" onChange={(e) => e.target.value && add(e.target.value)}>
            <option value="">Add a project or job…</option>
            {spare.map((k) => <option key={k} value={k}>{itemNames[k]}</option>)}
          </select>
        )}
      </div>
      <div>
        <p className="mb-1.5 text-sm font-semibold">Skills on this resume</p>
        {edit.skills.map((g, gi) => (
          <div key={gi} className="mb-1.5 flex gap-2">
            <input aria-label="Group name" className={`${inputCls} w-36 py-1.5 text-sm`} value={g.label}
              onChange={(e) => setEdit({ ...edit, skills: edit.skills.map((x, k) => k === gi ? { ...x, label: e.target.value } : x) })} />
            <input aria-label="Skills, comma separated" className={`${inputCls} py-1.5 text-sm`} value={g.items}
              onChange={(e) => setEdit({ ...edit, skills: edit.skills.map((x, k) => k === gi ? { ...x, items: e.target.value } : x) })} />
            <button type="button" aria-label="Remove group" className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-sunken hover:text-bad"
              onClick={() => setEdit({ ...edit, skills: edit.skills.filter((_, k) => k !== gi) })}><IconX size={15} /></button>
          </div>
        ))}
        <Button variant="ghost" onClick={() => setEdit({ ...edit, skills: [...edit.skills, { label: "Skills", items: "" }] })}>Add a group</Button>
      </div>
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button busy={busy} onClick={save}>Save and re-render</Button>
        <Button variant="ghost" onClick={() => setEdit(track)}>Undo changes</Button>
      </div>
    </div>
  );
}
