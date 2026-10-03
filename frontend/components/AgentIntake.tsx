"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { IntakeKey } from "@/lib/types";
import { IconCheck, IconCopy } from "./icons";
import { Badge, Button, Card, ErrorNote, Field, fmtDayInline, inputCls } from "./ui";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const EXAMPLE = `POST ${API_BASE}/intake/leads
Authorization: Bearer jri_...your key...
Content-Type: application/json

{
  "leads": [
    {
      "text": "The whole post, to the end, with who posted it and its age line",
      "url": "https://www.linkedin.com/posts/...",
      "age_label": "3h",
      "found_by": "posts: backend intern pune, past 24 hours",
      "found_at": "2026-10-03T09:15:00+05:30"
    }
  ]
}`;

const POOL_EXAMPLE = EXAMPLE.replace('"found_at": "2026-10-03T09:15:00+05:30"',
  '"found_at": "2026-10-03T09:15:00+05:30",\n      "combo": "student / backend"');

/** Your own agent hands Jobreach the posts it finds for you: a personal key, the address, the format.
 *  A curator can also make a key for everyone's pool. */
export default function AgentIntake({ curator = false }: { curator?: boolean }) {
  const [keys, setKeys] = useState<IntakeKey[] | null>(null);
  const [name, setName] = useState("My agent");
  const [scope, setScope] = useState<"private" | "pool">("private");
  const [fresh, setFresh] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.get<IntakeKey[]>("/intake/keys").then(setKeys)
    .catch((e) => setError(e instanceof Error ? e.message : String(e))), []);
  useEffect(() => { load(); }, [load]);

  const copy = async (text: string, k: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(k);
    setTimeout(() => setCopied((c) => (c === k ? null : c)), 1600);
  };
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.post<IntakeKey & { key: string }>("/intake/keys", { name: name.trim() || "My agent", scope });
      setFresh(r.key);
      load();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(false);
  }
  async function revoke(k: IntakeKey) {
    if (!confirm(`Turn off "${k.name}"? Anything still using it will be refused.`)) return;
    await api.del(`/intake/keys/${k.id}`);
    load();
  }

  return (
    <div className="flex flex-col gap-4">
      <Card title="Your agent">
        <p className="max-w-2xl text-[15px] leading-relaxed text-text-2">
          If you run your own agent that finds posts for you, it can hand them straight to Jobreach instead of you pasting them.
          Each post becomes a private lead of yours: read, checked, scored against your work, and given a letter when it&apos;s a
          strong or good match. Posts from your agent are never shared with anyone or added to the shared pool.
        </p>
        {curator && (
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-text-2">
            As a curator you can also make a key for <span className="font-semibold text-text">everyone&apos;s pool</span>. Posts
            sent with it become shared openings: read once, matched for every user, with letters prepared for the best three
            matches only, so no poster gets a pile of near-identical letters. The same post sent twice, by any key, is kept once.
          </p>
        )}

        <form onSubmit={create} className="mt-5 flex flex-wrap items-end gap-3">
          <div className="w-64"><Field label="Name for a new key"><input className={inputCls} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} /></Field></div>
          {curator && (
            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1.5 text-sm font-semibold">Its posts go to</legend>
              <div className="flex rounded-[10px] border border-border-strong p-0.5">
                {([["private", "My own leads"], ["pool", "Everyone's pool"]] as const).map(([v, label]) => (
                  <label key={v} className={`cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-colors has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-accent/20 ${
                    scope === v ? "bg-accent text-white dark:text-[#0b1020]" : "text-text-2 hover:text-text"}`}>
                    <input type="radio" name="scope" value={v} checked={scope === v} onChange={() => setScope(v)} className="sr-only" />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <Button type="submit" busy={busy}>Make a key</Button>
        </form>
        <ErrorNote error={error} />

        {fresh && (
          <div role="status" className="mt-4 rounded-xl border border-ok/30 bg-ok-soft/60 p-4">
            <p className="text-sm font-semibold">Your new key. Copy it now: you won&apos;t see it again.</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-lg bg-surface px-3 py-2 font-mono text-[13px]">{fresh}</code>
              <Button variant="secondary" onClick={() => copy(fresh, "key")}>
                {copied === "key" ? <><IconCheck size={16} /> Copied</> : <><IconCopy size={16} /> Copy</>}
              </Button>
            </div>
            <p className="mt-2 text-[13px] text-text-2">Give it to your agent as a secret. Anyone with it can add posts to your account, so turn it off if it leaks.</p>
          </div>
        )}

        <div className="mt-6">
          <h3 className="text-sm font-semibold">Keys in use</h3>
          {!keys ? <div className="mt-2 h-12 animate-pulse rounded-xl bg-sunken" /> : keys.length === 0 ? (
            <p className="mt-1 text-sm text-muted">None yet.</p>
          ) : (
            <ul className="mt-2 flex flex-col divide-y divide-border rounded-xl border border-border">
              {keys.map((k) => (
                <li key={k.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
                  <span className="font-semibold">{k.name}</span>
                  {k.scope === "pool" && <Badge tone="accent">Everyone&apos;s pool</Badge>}
                  <code className="font-mono text-[13px] text-muted">{k.prefix}…</code>
                  <span className="text-muted">{k.last_used_at ? `last used ${fmtDayInline(k.last_used_at)}` : "never used"}</span>
                  <button type="button" onClick={() => revoke(k)} className="ml-auto rounded-lg px-2 py-1 font-medium text-muted hover:bg-sunken hover:text-bad">Turn off</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card title="What your agent sends">
        <ul className="flex max-w-2xl list-disc flex-col gap-1.5 pl-5 text-[15px] leading-relaxed text-text-2">
          <li>Only what it saw: the whole post (to the end, with the poster&apos;s line), its link, its age as shown, and the search it ran.</li>
          <li>Nothing else. Jobreach reads the post, checks the company, finds the published address and writes the letter itself, by the same rules as a post you paste.</li>
          <li>Up to 25 posts a call and 100 a day. A post already sent (same text or same link) comes back as a duplicate.</li>
          {curator && <li>With a pool key: add <code className="font-mono text-[13px]">combo</code> (the search combination, for example
            &ldquo;student / backend&rdquo;); up to 500 posts a day into the pool. A post already in the pool, from any key, is a duplicate.</li>}
        </ul>
        <div className="relative mt-4">
          <pre className="overflow-x-auto rounded-xl bg-sunken p-4 font-mono text-[13px] leading-relaxed text-text-2">{scope === "pool" ? POOL_EXAMPLE : EXAMPLE}</pre>
          <button type="button" onClick={() => copy(scope === "pool" ? POOL_EXAMPLE : EXAMPLE, "example")} aria-label="Copy the format"
            className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-lg bg-surface px-2 py-1 text-xs font-semibold text-accent shadow-sm hover:bg-accent-soft">
            {copied === "example" ? <><IconCheck size={13} /> Copied</> : <><IconCopy size={13} /> Copy</>}
          </button>
        </div>
        <p className="mt-3 text-[13px] text-muted">
          The answer lists each post as queued or duplicate. Queued posts show on Add leads within a couple of minutes, marked as found by your agent.
        </p>
      </Card>
    </div>
  );
}
