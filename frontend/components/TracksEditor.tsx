"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FactBank, Track } from "@/lib/types";
import { Badge, Button, Card, Empty, ErrorNote, Field, inputCls } from "./ui";

export default function TracksEditor({ onApprovedChange }: { onApprovedChange?: (n: number) => void }) {
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [items, setItems] = useState<{ key: string; name: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [proposing, setProposing] = useState(false);
  const [warnings, setWarnings] = useState<Record<string, string>>({});

  const fetchAll = () => Promise.all([api.get<Track[]>("/tracks"), api.get<FactBank>("/factbank")]);
  const apply = useCallback(([t, fb]: [Track[], FactBank]) => {
    setTracks(t);
    setItems(fb.items.filter((i) => i.confirmed).map((i) => ({ key: i.key, name: i.name })));
    onApprovedChange?.(t.filter((x) => x.approved && x.baseline).length);
  }, [onApprovedChange]);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
  const load = useCallback(async () => { try { apply(await fetchAll()); } catch (e) { fail(e); } }, [apply]);
  useEffect(() => { fetchAll().then(apply).catch(fail); }, [apply]);

  // Poll while an approved track is still being calibrated.
  const calibrating = tracks?.some((t) => t.approved && !t.baseline);
  useEffect(() => {
    if (!calibrating) return;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [calibrating, load]);

  async function propose() {
    setProposing(true);
    setError(null);
    try {
      const r = await api.post<{ warnings: Record<string, string> }>("/onboarding/tracks");
      setWarnings(r.warnings ?? {});
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setProposing(false);
  }

  if (!tracks) return <p className="text-sm text-muted">Loading tracks…</p>;
  const names = Object.fromEntries(items.map((i) => [i.key, i.name]));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted">
          A track is one resume variant for a family of roles. Each lead is matched to the best one.
        </span>
        <Button variant="secondary" busy={proposing} onClick={propose}>
          {tracks.length ? "Propose again" : "Propose tracks from my evidence"}
        </Button>
      </div>
      <ErrorNote error={error} />
      {tracks.length === 0 && !proposing && <Empty>No tracks yet.</Empty>}
      {tracks.map((t) => (
        <TrackCard key={`${t.key}:${JSON.stringify(t)}`} t={t} names={names} allItems={items} warning={warnings[t.key]} reload={load} setError={setError} />
      ))}
    </div>
  );
}

function TrackCard({ t, names, allItems, warning, reload, setError }: {
  t: Track; names: Record<string, string>; allItems: { key: string; name: string }[]; warning?: string;
  reload: () => Promise<void>; setError: (e: string | null) => void;
}) {
  // Reset from props by remounting (the parent keys this card on its data), not by an effect.
  const [edit, setEdit] = useState(t);
  const [busy, setBusy] = useState(false);
  const dirty = JSON.stringify(edit) !== JSON.stringify(t);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await reload(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  const save = () => act(() => api.put(`/tracks/${t.key}`, {
    label: edit.label, title_line: edit.title_line, summary: edit.summary,
    left_sections: edit.left_sections, skills: edit.skills,
  }));
  const move = (si: number, i: number, d: -1 | 1) => {
    const secs = edit.left_sections.map((s) => ({ ...s, item_keys: [...s.item_keys] }));
    const keys = secs[si].item_keys;
    const j = i + d;
    if (j < 0 || j >= keys.length) return;
    [keys[i], keys[j]] = [keys[j], keys[i]];
    setEdit({ ...edit, left_sections: secs });
  };
  const remove = (si: number, i: number) => {
    const secs = edit.left_sections.map((s) => ({ ...s, item_keys: s.item_keys.filter((_, k) => k !== i) }));
    setEdit({ ...edit, left_sections: secs.filter((s) => s.item_keys.length) });
  };
  const used = new Set(edit.left_sections.flatMap((s) => s.item_keys));

  return (
    <Card
      title={<span className="flex items-center gap-2">{t.label}
        {t.approved ? (t.baseline ? <Badge tone="ok">approved · one page at {t.baseline.scale}</Badge> : <Badge tone="warn">calibrating…</Badge>)
          : <Badge>not approved</Badge>}</span>}
      actions={<>
        {t.baseline && <Button variant="secondary" onClick={() => api.download(`/resumes/${t.baseline!.id}/download`)}>Download baseline</Button>}
        {dirty && <Button busy={busy} onClick={save}>Save changes</Button>}
        {!dirty && !t.approved && <Button busy={busy} onClick={() => act(() => api.post(`/tracks/${t.key}/approve`))}>Approve</Button>}
        <Button variant="ghost" onClick={() => confirm(`Delete track ${t.label}?`) && act(() => api.del(`/tracks/${t.key}`))}>Delete</Button>
      </>}>
      {warning && <p className="mb-3 rounded-md bg-warn-soft px-3 py-2 text-sm text-warn">{warning}</p>}
      <div className="flex flex-col gap-3">
        <Field label="Title line"><input className={inputCls} value={edit.title_line} onChange={(e) => setEdit({ ...edit, title_line: e.target.value })} /></Field>
        <Field label="Summary" hint="Only claims your confirmed facts back up.">
          <textarea className={inputCls} rows={4} value={edit.summary} onChange={(e) => setEdit({ ...edit, summary: e.target.value })} />
        </Field>
        <div>
          <p className="mb-1 text-sm font-medium">Order on the page</p>
          {edit.left_sections.map((s, si) => (
            <div key={si} className="mb-2">
              <input className={`${inputCls} mb-1 w-48 text-xs font-semibold uppercase`} value={s.heading}
                onChange={(e) => setEdit({ ...edit, left_sections: edit.left_sections.map((x, k) => k === si ? { ...x, heading: e.target.value } : x) })} />
              <ol className="flex flex-col gap-1">
                {s.item_keys.map((k, i) => (
                  <li key={k} className="flex items-center gap-2 text-sm">
                    <span className="w-5 text-muted">{i + 1}.</span>
                    <span className="flex-1">{names[k] ?? k}</span>
                    <button type="button" className="text-muted hover:text-text" onClick={() => move(si, i, -1)}>↑</button>
                    <button type="button" className="text-muted hover:text-text" onClick={() => move(si, i, 1)}>↓</button>
                    <button type="button" className="text-xs text-muted hover:text-bad" onClick={() => remove(si, i)}>remove</button>
                  </li>
                ))}
              </ol>
            </div>
          ))}
          {allItems.some((i) => !used.has(i.key)) && (
            <select className={`${inputCls} mt-1 w-auto`} value="" onChange={(e) => {
              const key = e.target.value;
              if (!key) return;
              const secs = edit.left_sections.length ? edit.left_sections : [{ heading: "Projects", item_keys: [] }];
              setEdit({ ...edit, left_sections: secs.map((s, k) => k === secs.length - 1 ? { ...s, item_keys: [...s.item_keys, key] } : s) });
            }}>
              <option value="">Add an item…</option>
              {allItems.filter((i) => !used.has(i.key)).map((i) => <option key={i.key} value={i.key}>{i.name}</option>)}
            </select>
          )}
        </div>
        <div>
          <p className="mb-1 text-sm font-medium">Technical skills</p>
          {edit.skills.map((g, gi) => (
            <div key={gi} className="mb-1 flex gap-2">
              <input className={`${inputCls} w-40`} value={g.label}
                onChange={(e) => setEdit({ ...edit, skills: edit.skills.map((x, k) => k === gi ? { ...x, label: e.target.value } : x) })} />
              <input className={inputCls} value={g.items}
                onChange={(e) => setEdit({ ...edit, skills: edit.skills.map((x, k) => k === gi ? { ...x, items: e.target.value } : x) })} />
              <button type="button" className="text-xs text-muted hover:text-bad"
                onClick={() => setEdit({ ...edit, skills: edit.skills.filter((_, k) => k !== gi) })}>remove</button>
            </div>
          ))}
          <Button variant="ghost" onClick={() => setEdit({ ...edit, skills: [...edit.skills, { label: "Group", items: "" }] })}>Add group</Button>
        </div>
      </div>
    </Card>
  );
}
