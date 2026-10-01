"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { FIELDS as DISCIPLINES } from "@/lib/fields";
import type { Preferences, Profile } from "@/lib/types";
import { Button, Card, ErrorNote, Field, inputCls } from "./ui";

const COMPANY_TYPES: [string, string][] = [
  ["big_tech", "Big tech"], ["it_services_major", "IT services majors"], ["large_enterprise", "Large enterprises"],
];

const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export function Toggle({ on, set, children }: { on: boolean; set: (v: boolean) => void; children: string }) {
  return (
    <button type="button" onClick={() => set(!on)}
      className={`rounded-full border px-3 py-1 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "border-border text-muted"}`}>
      {children}
    </button>
  );
}

export default function PreferencesForm({ prefs, profile, onSaved, submitLabel = "Save" }:
  { prefs: Preferences; profile: Profile; onSaved?: () => void; submitLabel?: string }) {
  const [p, setP] = useState<Preferences>(prefs);
  const [pr, setPr] = useState<Profile>(profile);
  const [locations, setLocations] = useState(prefs.locations.join(", "));
  const [excluded, setExcluded] = useState(prefs.excluded_companies.join(", "));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => { setP({ ...p, [k]: v }); setSaved(false); };
  const setProf = <K extends keyof Profile>(k: K, v: Profile[K]) => { setPr({ ...pr, [k]: v }); setSaved(false); };
  const toggleIn = (k: "role_types" | "open_to" | "excluded_company_types", v: string) =>
    set(k, p[k].includes(v) ? p[k].filter((x) => x !== v) : [...p[k], v]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.put("/profile", {
        name: pr.name, phone: pr.phone, email: pr.email, location: pr.location, links: pr.links,
        grad_date: pr.grad_date, batch_year: pr.batch_year, cgpa: pr.cgpa,
      });
      const { role_types, open_to, remote_ok, onsite_ok, hybrid_ok, stipend_floor, currency, unpaid_remote_policy,
        unpaid_onsite_policy, excluded_company_types, freshness_ceiling_hours, duration_flex, start_date,
        signature_html } = p;
      await api.put("/preferences", {
        role_types, open_to, remote_ok, onsite_ok, hybrid_ok, stipend_floor, currency, unpaid_remote_policy,
        unpaid_onsite_policy, excluded_company_types, freshness_ceiling_hours, duration_flex, start_date,
        signature_html: signature_html?.trim() ? signature_html : null,
        locations: list(locations), excluded_companies: list(excluded),
      });
      setSaved(true);
      onSaved?.();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Card title="You, as the resume shows it">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name"><input className={inputCls} value={pr.name ?? ""} onChange={(e) => setProf("name", e.target.value)} /></Field>
          <Field label="Email on the resume"><input className={inputCls} value={pr.email ?? ""} onChange={(e) => setProf("email", e.target.value)} /></Field>
          <Field label="Phone"><input className={inputCls} value={pr.phone ?? ""} onChange={(e) => setProf("phone", e.target.value)} /></Field>
          <Field label="City, state, country"><input className={inputCls} value={pr.location ?? ""} onChange={(e) => setProf("location", e.target.value)} /></Field>
          <Field label="Graduation (e.g. May 2027)"><input className={inputCls} value={pr.grad_date ?? ""} onChange={(e) => setProf("grad_date", e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Batch year"><input className={inputCls} type="number" value={pr.batch_year ?? ""}
              onChange={(e) => setProf("batch_year", e.target.value ? Number(e.target.value) : null)} /></Field>
            <Field label="CGPA (out of 10)"><input className={inputCls} type="number" step="0.01" value={pr.cgpa ?? ""}
              onChange={(e) => setProf("cgpa", e.target.value ? Number(e.target.value) : null)} /></Field>
          </div>
        </div>
        <Field label="Links on the resume" hint="One per line: label | url  (e.g. github.com/you | https://github.com/you)">
          <textarea className={inputCls} rows={3}
            value={pr.links.map((l) => `${l.text} | ${l.url}`).join("\n")}
            onChange={(e) => setProf("links", e.target.value.split("\n").filter((l) => l.includes("|")).map((l) => {
              const [text, url] = l.split("|").map((s) => s.trim());
              return { text, url };
            }))} />
        </Field>
      </Card>

      <Card title="What you are looking for">
        <div className="flex flex-col gap-4">
          <Field label="Kinds of work" hint="Leads in other disciplines are dropped (you can override any drop).">
            <div className="flex flex-wrap gap-2">
              {DISCIPLINES.map(([k, l]) => <Toggle key={k} on={p.role_types.includes(k)} set={() => toggleIn("role_types", k)}>{l}</Toggle>)}
            </div>
          </Field>
          <Field label="Open to">
            <div className="flex gap-2">
              <Toggle on={p.open_to.includes("internship")} set={() => toggleIn("open_to", "internship")}>Internships</Toggle>
              <Toggle on={p.open_to.includes("full_time")} set={() => toggleIn("open_to", "full_time")}>Full-time</Toggle>
            </div>
          </Field>
          <Field label="Work mode">
            <div className="flex gap-2">
              <Toggle on={p.remote_ok} set={(v) => set("remote_ok", v)}>Remote</Toggle>
              <Toggle on={p.hybrid_ok} set={(v) => set("hybrid_ok", v)}>Hybrid</Toggle>
              <Toggle on={p.onsite_ok} set={(v) => set("onsite_ok", v)}>Onsite</Toggle>
            </div>
          </Field>
          <Field label="Cities for onsite or hybrid" hint='Comma-separated, or "Anywhere in India".'>
            <input className={inputCls} value={locations} onChange={(e) => setLocations(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Stipend floor (per month)" hint="Posts stating less are dropped.">
              <input className={inputCls} type="number" value={p.stipend_floor ?? ""}
                onChange={(e) => set("stipend_floor", e.target.value ? Number(e.target.value) : null)} />
            </Field>
            <Field label="Unpaid and remote">
              <select className={inputCls} value={p.unpaid_remote_policy} onChange={(e) => set("unpaid_remote_policy", e.target.value)}>
                <option value="draft_with_floor">Draft, stating my floor</option>
                <option value="drop">Drop</option>
              </select>
            </Field>
            <Field label="Unpaid and onsite/hybrid">
              <select className={inputCls} value={p.unpaid_onsite_policy} onChange={(e) => set("unpaid_onsite_policy", e.target.value)}>
                <option value="drop">Drop</option>
                <option value="draft_with_floor">Draft, stating my floor</option>
              </select>
            </Field>
          </div>
          <Field label="Skip these company types">
            <div className="flex flex-wrap gap-2">
              {COMPANY_TYPES.map(([k, l]) => <Toggle key={k} on={p.excluded_company_types.includes(k)} set={() => toggleIn("excluded_company_types", k)}>{l}</Toggle>)}
            </div>
          </Field>
          <Field label="Skip these companies" hint="Comma-separated.">
            <input className={inputCls} value={excluded} onChange={(e) => setExcluded(e.target.value)} />
          </Field>
          <Field label="Freshness ceiling (hours)" hint="Older posts are dropped. Fresh posts reply far more often.">
            <input className={inputCls} type="number" value={p.freshness_ceiling_hours}
              onChange={(e) => set("freshness_ceiling_hours", Number(e.target.value) || 72)} />
          </Field>
        </div>
      </Card>

      <Card title="Availability and signature">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Earliest start" hint="Emails never narrow this.">
            <input className={inputCls} value={p.start_date} onChange={(e) => set("start_date", e.target.value)} />
          </Field>
          <Field label="Duration" hint="Emails never echo a post's duration as your limit.">
            <input className={inputCls} value={p.duration_flex} onChange={(e) => set("duration_flex", e.target.value)} />
          </Field>
        </div>
        <div className="mt-3">
          <Field label="Email signature (added verbatim)"
            hint="Leave empty if Gmail adds your signature automatically when you compose.">
            <textarea className={`${inputCls} font-mono`} rows={5} value={p.signature_html ?? ""}
              onChange={(e) => set("signature_html", e.target.value)} />
          </Field>
        </div>
      </Card>

      <ErrorNote error={error} />
      <div className="flex items-center gap-3">
        <Button type="submit" busy={busy}>{submitLabel}</Button>
        {saved && <span className="text-sm text-ok">Saved</span>}
      </div>
    </form>
  );
}
