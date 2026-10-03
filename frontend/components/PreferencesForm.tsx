"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { Preferences, Profile } from "@/lib/types";
import { Button, Card, ErrorNote, Field, inputCls } from "./ui";

const COMPANY_TYPES: [string, string][] = [
  ["big_tech", "Big tech"], ["it_services_major", "IT services majors"], ["large_enterprise", "Large enterprises"],
];

const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

const titleCase = (s: string) => s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

/**
 * The sign-off a letter gets when the person hasn't written their own. Mirrors default_signature in
 * backend/app/pipeline/draft.py, which is what the letters actually use.
 */
export function standardSignature(p: Pick<Profile, "name" | "phone" | "linkedin_url" | "github_url" | "portfolio_url">) {
  const bare = (u: string) => u.trim().replace(/^(?:https?:\/\/)?(?:www\.)?/, "").replace(/\/+$/, "");
  const name = (p.name ?? "").trim().replace(/\s+/g, " ");
  const shown = name && (name === name.toUpperCase() || name === name.toLowerCase()) ? titleCase(name) : name;
  const links = [...new Set([p.linkedin_url, p.github_url, p.portfolio_url].filter((u): u is string => !!u?.trim()).map(bare))];
  return ["Best regards,", shown, (p.phone ?? "").trim(), links.join(" | ")].filter(Boolean).join("\n");
}

export function Toggle({ on, set, children }: { on: boolean; set: (v: boolean) => void; children: string }) {
  return (
    <button type="button" onClick={() => set(!on)} aria-pressed={on}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors
        ${on ? "border-accent bg-accent text-white dark:text-[#0b1020]" : "border-border-strong bg-surface text-text-2 hover:border-accent hover:text-accent"}`}>
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
  // The sign-off: the standard one follows the name, phone and links until the person writes their own.
  const [sigOwn, setSigOwn] = useState(!!prefs.signature_html?.trim());
  const [sigText, setSigText] = useState(prefs.signature_html ?? "");
  const standard = standardSignature(pr);
  const sigShown = sigOwn ? sigText : standard;
  const sigUsed = sigShown.trim() || standard;
  const student = profile.career_stage === "student" || !profile.career_stage;
  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => { setP({ ...p, [k]: v }); setSaved(false); };
  const setProf = <K extends keyof Profile>(k: K, v: Profile[K]) => { setPr({ ...pr, [k]: v }); setSaved(false); };
  const toggleIn = (k: "open_to" | "excluded_company_types", v: string) =>
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
      const { open_to, remote_ok, onsite_ok, hybrid_ok, stipend_floor, salary_floor, notice_period, currency,
        unpaid_remote_policy, unpaid_onsite_policy, excluded_company_types, freshness_ceiling_hours, duration_flex,
        start_date } = p;
      await api.put("/preferences", {
        open_to, remote_ok, onsite_ok, hybrid_ok, stipend_floor, salary_floor, notice_period, currency, unpaid_remote_policy,
        unpaid_onsite_policy, excluded_company_types, freshness_ceiling_hours, duration_flex, start_date,
        signature_html: sigOwn && sigText.trim() && sigText.trim() !== standard ? sigText.trim() : null,
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
          {!student && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Salary floor (lakh per year)" hint="Posts stating less are dropped.">
                <input className={inputCls} type="number" step="0.5" min="0" value={p.salary_floor ? p.salary_floor / 100000 : ""}
                  onChange={(e) => set("salary_floor", e.target.value ? Math.round(Number(e.target.value) * 100000) : null)} />
              </Field>
              <Field label="Notice period" hint="Letters mention it only when a post asks.">
                <input className={inputCls} placeholder="For example: 30 days" value={p.notice_period ?? ""}
                  onChange={(e) => set("notice_period", e.target.value || null)} />
              </Field>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Stipend floor (per month)" hint="For internships. Posts stating less are dropped.">
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

      <Card title="Availability">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Earliest start" hint="Emails never narrow this.">
            <input className={inputCls} value={p.start_date} onChange={(e) => set("start_date", e.target.value)} />
          </Field>
          <Field label="Duration" hint="Emails never echo a post's duration as your limit.">
            <input className={inputCls} value={p.duration_flex} onChange={(e) => set("duration_flex", e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card title="How your letters end">
        <p className="max-w-2xl text-[15px] leading-relaxed text-text-2">
          Gmail doesn&apos;t add your usual Gmail signature to drafts Jobreach makes, so this closes every letter,
          exactly as written.
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div>
            <Field label="Sign-off and signature">
              <textarea className={inputCls} rows={5} value={sigShown} spellCheck={false}
                onChange={(e) => { setSigOwn(true); setSigText(e.target.value); setSaved(false); }} />
            </Field>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
              {sigOwn
                ? <>Your own wording. <button type="button" className="font-semibold text-accent hover:underline"
                    onClick={() => { setSigOwn(false); setSigText(""); setSaved(false); }}>Use the standard one</button></>
                : "Made from your name, phone and links. Edit it to write your own."}
            </p>
          </div>
          <figure className="paper self-start px-5 py-4" aria-label="How a letter ends">
            <figcaption className="font-sans text-xs text-muted">How a letter ends</figcaption>
            <p className="mt-2 font-letter text-[15px] leading-[1.7] text-text-2">
              &hellip; My resume is attached. Would you be open to a quick call this week?
            </p>
            <p className="mt-3 whitespace-pre-line break-words font-letter text-[15px] leading-[1.7] text-text">{sigUsed}</p>
          </figure>
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
