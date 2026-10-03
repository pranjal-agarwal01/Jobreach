"use client";

import { useEffect, useState } from "react";
import { useMe } from "@/components/AppShell";
import AgentIntake from "@/components/AgentIntake";
import FactBankEditor from "@/components/FactBankEditor";
import PreferencesForm from "@/components/PreferencesForm";
import StageEditor from "@/components/StageEditor";
import TracksEditor from "@/components/TracksEditor";
import { Button, Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const TABS = [["facts", "Profile"], ["tracks", "Resumes"], ["prefs", "Preferences"], ["agent", "Your agent"],
  ["data", "Usage and data"]] as const;

interface Usage {
  steps: { step: string; calls: number; input_tokens: number; output_tokens: number; cache_read_tokens: number;
           cost_usd: number; avg_latency_ms: number }[];
  per_application: { avg_cost_per_application: number | null; applications: number };
  per_lead: { avg_cost_per_lead: number | null; leads: number };
  total: { cost_usd: number };
}

const STEP_LABEL: Record<string, string> = {
  s1_extract: "Reading posts", s4_company: "Checking companies", s5_select: "Choosing resume lines", s7_draft: "Writing letters",
  onb_extract: "Reading your CVs", onb_baselines: "Writing your resumes", onb_interview: "Setup questions (earlier)",
  onb_bullets: "Writing bullets (earlier)", onb_tracks: "Proposing resumes (earlier)", onb_roles: "Roles audit (earlier)",
};

export default function ProfilePage() {
  const { me, refresh } = useMe();
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("facts");
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title={me.profile.name ?? "Your profile"}
        sub="Everything your resumes and letters are built from. Change it here and every new draft follows." />
      <div role="tablist" aria-label="Profile sections" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        <div className="flex gap-1 rounded-xl bg-sunken p-1">
          {TABS.map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-colors ${tab === k ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"}`}>{l}</button>
          ))}
        </div>
      </div>
      <div role="tabpanel">
        {tab === "facts" && <FactBankEditor />}
        {tab === "tracks" && <TracksEditor />}
        {tab === "prefs" && (
          <div className="flex flex-col gap-4">
            <Card title="Where you are">
              <StageEditor key={`${me.profile.career_stage}:${me.profile.experience_years}`} stage={me.profile.career_stage}
                years={me.profile.experience_years} onSaved={refresh} />
            </Card>
            <PreferencesForm prefs={me.preferences} profile={me.profile} onSaved={refresh} />
          </div>
        )}
        {tab === "agent" && <AgentIntake />}
        {tab === "data" && <DataTab />}
      </div>
    </div>
  );
}

function DataTab() {
  const [u, setU] = useState<Usage | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get<Usage>("/usage").then(setU); }, []);
  const usd = (n: number | null | undefined) => (n === null || n === undefined ? "–" : `$${Number(n).toFixed(n < 0.01 ? 4 : 3)}`);
  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <Card title="What your drafts cost to make">
        {!u ? <div className="h-24 animate-pulse rounded-xl bg-sunken" /> : u.steps.length === 0 ? <Empty>No AI work done yet.</Empty> : (
          <>
            <dl className="mb-6 grid grid-cols-3 gap-3">
              {[["Per letter", usd(u.per_application.avg_cost_per_application)], ["Per pasted post", usd(u.per_lead.avg_cost_per_lead)],
                ["In total", usd(u.total.cost_usd)]].map(([l, v]) => (
                <div key={l} className="rounded-xl bg-sunken px-4 py-3">
                  <dd className="text-[22px] font-bold tabular-nums tracking-tight">{v}</dd>
                  <dt className="text-xs font-medium text-muted">{l}</dt>
                </div>
              ))}
            </dl>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-border"><th className="py-2 pr-3 font-medium">Step</th><th className="pr-3 text-right font-medium">Runs</th>
                    <th className="pr-3 text-right font-medium">Tokens in</th><th className="pr-3 text-right font-medium">Tokens out</th>
                    <th className="pr-3 text-right font-medium">Cost</th><th className="text-right font-medium">Avg time</th></tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {u.steps.map((s) => (
                    <tr key={s.step}><td className="py-2 pr-3">{STEP_LABEL[s.step] ?? s.step}</td><td className="pr-3 text-right">{s.calls}</td>
                      <td className="pr-3 text-right">{s.input_tokens.toLocaleString("en-IN")}</td><td className="pr-3 text-right">{s.output_tokens.toLocaleString("en-IN")}</td>
                      <td className="pr-3 text-right">{usd(s.cost_usd)}</td><td className="text-right">{(s.avg_latency_ms / 1000).toFixed(1)}s</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
      <Card title="Delete everything" className="border-bad/30">
        <p className="mb-4 max-w-xl text-[15px] leading-relaxed text-text-2">
          Deletes your account, fact bank, resumes, letters, leads and outcomes, and turns off every share link. This can&apos;t be undone.
        </p>
        <Button variant="danger" busy={busy} onClick={async () => {
          if (prompt("Type DELETE to delete your account and all data") !== "DELETE") return;
          setBusy(true);
          await api.del("/account");
          await supabase.auth.signOut();
        }}>Delete my account and data</Button>
      </Card>
    </div>
  );
}
