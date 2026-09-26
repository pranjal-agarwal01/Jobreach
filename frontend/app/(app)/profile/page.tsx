"use client";

import { useEffect, useState } from "react";
import { useMe } from "@/components/AppShell";
import FactBankEditor from "@/components/FactBankEditor";
import PreferencesForm from "@/components/PreferencesForm";
import TracksEditor from "@/components/TracksEditor";
import { Button, Card, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const TABS = [["facts", "Fact bank"], ["prefs", "Preferences"], ["tracks", "Tracks"], ["data", "Usage & data"]] as const;

interface Usage {
  steps: { step: string; calls: number; input_tokens: number; output_tokens: number; cache_read_tokens: number;
           cost_usd: number; avg_latency_ms: number }[];
  per_application: { avg_cost_per_application: number | null; applications: number };
  per_lead: { avg_cost_per_lead: number | null; leads: number };
  total: { cost_usd: number };
}

export default function ProfilePage() {
  const { me, refresh } = useMe();
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("facts");
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-4 text-xl font-semibold">Profile</h1>
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`rounded-md px-3 py-1 text-sm ${tab === k ? "bg-accent-soft text-accent" : "text-muted hover:text-text"}`}>{l}</button>
        ))}
      </div>
      {tab === "facts" && <FactBankEditor />}
      {tab === "prefs" && <PreferencesForm prefs={me.preferences} profile={me.profile} onSaved={refresh} />}
      {tab === "tracks" && <TracksEditor />}
      {tab === "data" && <DataTab />}
    </div>
  );
}

function DataTab() {
  const [u, setU] = useState<Usage | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get<Usage>("/usage").then(setU); }, []);
  const usd = (n: number | null | undefined) => (n === null || n === undefined ? "–" : `$${Number(n).toFixed(4)}`);
  return (
    <div className="flex flex-col gap-5">
      <Card title="Model usage (measured)">
        {!u ? <p className="text-sm text-muted">Loading…</p> : u.steps.length === 0 ? <Empty>No model calls yet.</Empty> : (
          <>
            <div className="mb-3 flex flex-wrap gap-6 text-sm">
              <span>Total <strong>{usd(u.total.cost_usd)}</strong></span>
              <span>Per lead <strong>{usd(u.per_lead.avg_cost_per_lead)}</strong> ({u.per_lead.leads})</span>
              <span>Per application <strong>{usd(u.per_application.avg_cost_per_application)}</strong> ({u.per_application.applications})</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-muted"><tr><th className="py-1 pr-3">Step</th><th className="pr-3">Calls</th>
                  <th className="pr-3">Input</th><th className="pr-3">Cached</th><th className="pr-3">Output</th><th className="pr-3">Cost</th><th>Avg time</th></tr></thead>
                <tbody className="divide-y divide-border">
                  {u.steps.map((s) => (
                    <tr key={s.step}><td className="py-1 pr-3 font-mono text-xs">{s.step}</td><td className="pr-3">{s.calls}</td>
                      <td className="pr-3">{s.input_tokens}</td><td className="pr-3">{s.cache_read_tokens}</td><td className="pr-3">{s.output_tokens}</td>
                      <td className="pr-3">{usd(s.cost_usd)}</td><td>{(s.avg_latency_ms / 1000).toFixed(1)}s</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
      <Card title="Delete everything">
        <p className="mb-3 text-sm text-muted">
          Deletes your account, fact bank, resumes, drafts, leads and outcomes. This cannot be undone.
        </p>
        <Button variant="danger" busy={busy} onClick={async () => {
          if (prompt('Type DELETE to delete your account and all data') !== "DELETE") return;
          setBusy(true);
          await api.del("/account");
          await supabase.auth.signOut();
        }}>Delete my account and data</Button>
      </Card>
    </div>
  );
}
