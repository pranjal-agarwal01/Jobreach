"use client";

import { useRouter } from "next/navigation";
import { DragEvent, FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useMe } from "@/components/AppShell";
import { BaselineGrid, LeftOutPanel, useReview } from "@/components/Baselines";
import FactBankEditor from "@/components/FactBankEditor";
import { IconAlert, IconCheck, IconFile, IconGithub, IconLink, IconUpload, IconX } from "@/components/icons";
import PreferencesForm, { Toggle } from "@/components/PreferencesForm";
import StageEditor from "@/components/StageEditor";
import { Button, ErrorNote, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { isDemo } from "@/lib/demo";
import { FIELDS } from "@/lib/fields";
import { STAGES, describe } from "@/lib/stage";
import type { Build, Stage } from "@/lib/types";

// One form, a background build, one review. Nothing is asked in between (docs/plan-global-pool.md).
type Screen = "form" | "building" | "review";
const MAX_FAMILIES = 4;
const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

export default function Onboarding() {
  const { me, refresh } = useMe();
  const router = useRouter();
  // Demo mode can open any screen: /demo?to=/onboarding?step=review
  const demo = isDemo() ? new URLSearchParams(window.location.search).get("step") : null;
  const saved = me.profile.onboarding_step;
  const [screen, setScreen] = useState<Screen>(
    (demo as Screen | null) ?? (saved === "building" ? "building" : saved === "review" ? "review" : "form"));
  const go = (s: Screen) => { setScreen(s); window.scrollTo(0, 0); };

  if (screen === "building") {
    return <Building onDone={async () => { await refresh(); go("review"); }}
      onBack={async () => { await api.put("/profile", { onboarding_step: "form" }); await refresh(); go("form"); }} />;
  }
  if (screen === "review") {
    return <ReviewScreen onFinish={async () => { await api.post("/onboarding/finish"); await refresh(); router.replace("/today"); }} />;
  }
  return <OneForm onStarted={() => go("building")} />;
}

// ------------------------------------------------------------------ the form

function Section({ title, hint, optional, children }: { title: string; hint?: ReactNode; optional?: boolean; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <h2 className="text-[17px] font-bold tracking-tight">
        {title} {optional && <span className="text-sm font-normal text-muted">(optional)</span>}
      </h2>
      {hint && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function OneForm({ onStarted }: { onStarted: () => void }) {
  const { me } = useMe();
  const p = me.preferences;
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [stage, setStage] = useState<Stage | null>(me.profile.career_stage);
  const [families, setFamilies] = useState<string[]>(p.target_families ?? []);
  const [titles, setTitles] = useState((p.desired_roles ?? []).join(", "));
  const [github, setGithub] = useState(me.profile.github_url ?? "");
  const [portfolio, setPortfolio] = useState(me.profile.portfolio_url ?? "");
  const [linkedin, setLinkedin] = useState(me.profile.linkedin_url ?? "");
  const [otherLinks, setOtherLinks] = useState("");
  const [notes, setNotes] = useState(me.profile.about ?? "");
  const [modes, setModes] = useState({ remote_ok: p.remote_ok, hybrid_ok: p.hybrid_ok, onsite_ok: p.onsite_ok });
  const [cities, setCities] = useState(p.locations.join(", "));
  const [openTo, setOpenTo] = useState<string[] | null>(null);           // null: follow the stage
  const [skipBigTech, setSkipBigTech] = useState<boolean | null>(null);  // null: follow the stage
  const [stipend, setStipend] = useState(p.stipend_floor ? String(p.stipend_floor) : "");
  const [salary, setSalary] = useState(p.salary_floor ? String(p.salary_floor / 100000) : "");
  const [notice, setNotice] = useState(p.notice_period ?? "");
  const [start, setStart] = useState("");
  const [skip, setSkip] = useState(p.excluded_companies.join(", "));
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const student = stage === "student";
  const open = openTo ?? (student ? ["internship"] : ["full_time"]);
  const bigTech = skipBigTech ?? student;
  const add = (l: FileList | null) => {
    const ok = Array.from(l ?? []).filter((f) => /\.(pdf|docx|txt)$/i.test(f.name));
    setFiles((cur) => [...cur, ...ok.filter((f) => !cur.some((c) => c.name === f.name && c.size === f.size))].slice(0, 6));
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); };
  const toggleFamily = (k: string) => setFamilies(families.includes(k) ? families.filter((x) => x !== k)
    : families.length < MAX_FAMILIES ? [...families, k] : families);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!stage) return setError("Tell us where you are: student, recent graduate or experienced.");
    if (families.length === 0 && !titles.trim()) return setError("Pick at least one kind of role.");
    if (files.length === 0 && notes.trim().length < 80 && !github.trim())
      return setError("Upload your CV, or write a few lines about your work, so there is something to build from.");
    if (me.needs_consent && !agreed) return setError("Please read and agree to how your data is used.");
    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("form", JSON.stringify({
      stage, families, titles: list(titles), github, portfolio, linkedin, other_links: otherLinks, notes,
      open_to: open, ...modes, locations: list(cities),
      stipend_floor: stipend ? Number(stipend) : null,
      salary_floor: salary ? Math.round(Number(salary) * 100000) : null,
      notice_period: notice || null, start_date: start || null, excluded_companies: list(skip),
      skip_big_tech: bigTech, consent_version: me.needs_consent ? me.consent_version : null,
    }));
    setBusy(true);
    try { await api.upload("/onboarding/start", form); onStarted(); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); setBusy(false); }
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-12">
      <form onSubmit={submit} className="flex min-w-0 flex-col gap-5">
        <header className="mb-2">
          <h1 className="text-[30px] font-bold leading-tight tracking-[-0.025em] sm:text-[36px]">Tell us once</h1>
          <p className="mt-2 max-w-2xl text-[16px] leading-relaxed text-text-2">
            One form. We read your CV, keep every line we can find in it, and build a one-page resume for each kind of
            role you want. There is no interview.
          </p>
        </header>

        <Section title="Your CV" hint="Every version you have: each may mention work the others don't. PDF, DOCX or TXT, up to six files.">
          <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors
              ${drag ? "border-accent bg-accent-soft" : "border-border-strong hover:border-accent hover:bg-sunken/60"}`}>
            <span className="grid size-11 place-items-center rounded-full bg-accent-soft text-accent"><IconUpload size={22} /></span>
            <span className="text-[15px] font-semibold">Drop your CV here, or <span className="text-accent underline underline-offset-2">choose files</span></span>
            <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" className="sr-only" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          </label>
          {files.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {files.map((f) => (
                <li key={f.name + f.size} className="inline-flex items-center gap-2 rounded-lg border border-border bg-sunken py-1.5 pl-2.5 pr-1.5 text-sm">
                  <IconFile size={16} className="text-accent" /> {f.name}
                  <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}
                    className="grid size-6 place-items-center rounded-md text-muted hover:bg-surface hover:text-bad"><IconX size={14} /></button>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Where you are">
          <div role="radiogroup" aria-label="Where you are" className="grid gap-2 sm:grid-cols-3">
            {STAGES.map((x) => (
              <button key={x.key} type="button" role="radio" aria-checked={stage === x.key} onClick={() => setStage(x.key)}
                className={`rounded-xl border px-4 py-3.5 text-left transition-colors ${stage === x.key ? "border-accent bg-accent-soft" : "border-border-strong bg-surface hover:border-accent"}`}>
                <span className="block font-semibold">{x.label}</span>
                <span className="block text-[13px] text-muted">{x.hint}</span>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Roles you want" hint={`Up to ${MAX_FAMILIES}. You'll get one resume for each, and openings matched to them.`}>
          <div className="flex flex-wrap gap-2">
            {FIELDS.map(([k, l]) => <Toggle key={k} on={families.includes(k)} set={() => toggleFamily(k)}>{l}</Toggle>)}
          </div>
          <p className="mt-2 text-xs tabular-nums text-muted">{families.length} of {MAX_FAMILIES} chosen</p>
          <div className="mt-4">
            <Field label="Specific job titles (optional)" hint="Comma separated, for example: SDE II, ML Engineer Intern. We place each in the right kind of role.">
              <input className={inputCls} value={titles} onChange={(e) => setTitles(e.target.value)} />
            </Field>
          </div>
        </Section>

        <Section title="Links" hint="We read your public GitHub repositories and your portfolio page. Your LinkedIn link goes on your resume, but we never read LinkedIn: to include it, save your profile as a PDF from LinkedIn and add it above.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="GitHub">
              <span className="relative">
                <IconGithub size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input className={`${inputCls} pl-9`} placeholder="github.com/your-username" value={github} onChange={(e) => setGithub(e.target.value)} />
              </span>
            </Field>
            <Field label="Portfolio">
              <span className="relative">
                <IconLink size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input className={`${inputCls} pl-9`} placeholder="your-site.com" value={portfolio} onChange={(e) => setPortfolio(e.target.value)} />
              </span>
            </Field>
            <Field label="LinkedIn">
              <input className={inputCls} placeholder="linkedin.com/in/you" value={linkedin} onChange={(e) => setLinkedin(e.target.value)} />
            </Field>
            <Field label="Other links" hint="LeetCode, Kaggle, a live project. One per line.">
              <textarea className={inputCls} rows={2} value={otherLinks} onChange={(e) => setOtherLinks(e.target.value)} />
            </Field>
          </div>
        </Section>

        <Section title="Anything your CV leaves out" optional
          hint="Projects, freelance or client work, things you deployed and who used them, hackathons, roles in clubs. Plain words are fine; real numbers only if you know them.">
          <textarea className={inputCls} rows={5} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Section>

        <Section title="What you're looking for" hint="These decide which openings you see. You can change them any time.">
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap gap-x-8 gap-y-4">
              <Field label="Open to">
                <div className="flex gap-2">
                  <Toggle on={open.includes("internship")} set={() => setOpenTo(open.includes("internship") ? open.filter((x) => x !== "internship") : [...open, "internship"])}>Internships</Toggle>
                  <Toggle on={open.includes("full_time")} set={() => setOpenTo(open.includes("full_time") ? open.filter((x) => x !== "full_time") : [...open, "full_time"])}>Full-time</Toggle>
                </div>
              </Field>
              <Field label="Work mode">
                <div className="flex gap-2">
                  <Toggle on={modes.remote_ok} set={(v) => setModes({ ...modes, remote_ok: v })}>Remote</Toggle>
                  <Toggle on={modes.hybrid_ok} set={(v) => setModes({ ...modes, hybrid_ok: v })}>Hybrid</Toggle>
                  <Toggle on={modes.onsite_ok} set={(v) => setModes({ ...modes, onsite_ok: v })}>Onsite</Toggle>
                </div>
              </Field>
            </div>
            <Field label="Cities for onsite or hybrid work" hint='Comma separated, or "Anywhere in India".'>
              <input className={inputCls} value={cities} onChange={(e) => setCities(e.target.value)} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              {student ? (
                <>
                  <Field label="Lowest stipend you'd take (per month)" hint="Posts offering less are skipped.">
                    <input className={inputCls} type="number" min="0" value={stipend} onChange={(e) => setStipend(e.target.value)} />
                  </Field>
                  <Field label="Earliest start"><input className={inputCls} placeholder="For example: January 2027" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
                </>
              ) : (
                <>
                  <Field label="Lowest salary you'd take (lakh per year)" hint="Posts offering less are skipped.">
                    <input className={inputCls} type="number" min="0" step="0.5" value={salary} onChange={(e) => setSalary(e.target.value)} />
                  </Field>
                  {stage === "experienced"
                    ? <Field label="Notice period"><input className={inputCls} placeholder="For example: 30 days" value={notice} onChange={(e) => setNotice(e.target.value)} /></Field>
                    : <Field label="Earliest start"><input className={inputCls} placeholder="For example: Immediately" value={start} onChange={(e) => setStart(e.target.value)} /></Field>}
                </>
              )}
            </div>
            <div className="flex flex-col gap-3">
              <Toggle on={bigTech} set={(v) => setSkipBigTech(v)}>Skip big tech companies</Toggle>
              <Field label="Companies to skip" hint="Comma separated.">
                <input className={inputCls} value={skip} onChange={(e) => setSkip(e.target.value)} />
              </Field>
            </div>
          </div>
        </Section>

        {me.needs_consent && (
          <section className="paper p-5 text-[15px] leading-relaxed sm:p-6">
            <h2 className="text-[17px] font-bold tracking-tight">How your data is used</h2>
            <p className="mt-2">Jobreach stores what you give it so it can build resumes and draft emails for you:</p>
            <ul className="my-3 flex flex-col gap-1.5 pl-1">
              {["your resume text, contact details, grades and the facts you confirm;",
                "job posts you paste (private to you) and the resumes and drafts made from them;",
                "replies and outcomes you log."].map((t) => (
                <li key={t} className="flex gap-2.5"><IconCheck size={17} className="mt-1 shrink-0 text-accent" />{t}</li>
              ))}
            </ul>
            <p className="text-text-2">
              It is used only to produce your resumes and drafts. To read posts and write drafts, text is processed by
              OpenAI models through Microsoft&apos;s Azure OpenAI service, which does not use it to train models.
              Jobreach never sends an email or submits an application for you. You can delete your account and all of
              your data at any time from Profile.
            </p>
            <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-border-strong p-4 has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
              <input type="checkbox" className="mt-0.5 size-5 accent-[var(--accent)]" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>I understand and agree. <span className="text-muted">Notice version {me.consent_version}.</span></span>
            </label>
          </section>
        )}

        <ErrorNote error={error} />
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" busy={busy} className="min-h-12 px-7 text-[16px]">Build my resumes</Button>
          <span className="text-sm text-muted">Takes a minute or two.</span>
        </div>
      </form>

      <aside className="hidden lg:block">
        <div className="sticky top-8 flex flex-col gap-5 rounded-2xl bg-inland p-6 ring-1 ring-inland-edge">
          <h2 className="font-bold tracking-tight">What happens next</h2>
          {[
            ["We read what you gave us", "Your CV, notes, GitHub and portfolio."],
            ["Every line is checked against it", "Anything we can't find stays off your resumes. We don't ask you about it."],
            ["One resume for each kind of role", "Each fits on one page. You see them all, and change anything, before you start."],
          ].map(([t, d]) => (
            <div key={t} className="flex gap-3">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-surface text-accent ring-1 ring-inland-edge"><IconCheck size={14} /></span>
              <div>
                <p className="text-sm font-semibold">{t}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-text-2">{d}</p>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

// ------------------------------------------------------------------ building

const STEPS: [NonNullable<Build["step"]>, string][] = [
  ["reading", "Reading your CV and links"],
  ["checking", "Checking every line against what you gave us"],
  ["writing", "Writing a resume for each kind of role"],
  ["rendering", "Fitting each one to a single page"],
];

function Building({ onDone, onBack }: { onDone: () => void; onBack: () => void }) {
  const [build, setBuild] = useState<Build | null>(null);
  const done = useRef(onDone);
  useEffect(() => { done.current = onDone; });
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.get<{ step: string; build: Build }>("/onboarding/status");
        if (!alive) return;
        setBuild(s.build);
        if (s.build.status === "done" || s.step === "review" || s.step === "done") { setTimeout(() => alive && done.current(), 600); return; }
        if (s.build.status !== "failed") setTimeout(tick, 1500);
      } catch { if (alive) setTimeout(tick, 3000); }
    };
    tick();
    return () => { alive = false; };
  }, []);

  const failed = build?.status === "failed";
  const at = STEPS.findIndex(([k]) => k === build?.step);
  const finished = build?.status === "done";
  return (
    <div className="mx-auto grid max-w-4xl items-center gap-12 py-6 md:grid-cols-[minmax(0,1fr)_260px]">
      <div>
        <h1 className="text-[30px] font-bold leading-tight tracking-[-0.025em] sm:text-[36px]">
          {failed ? "Something went wrong" : "Building your resumes"}
        </h1>
        <p className="mt-2 text-[16px] text-text-2">
          {failed ? "Nothing you gave us is lost. Go back to the form and try again." : "This takes a minute or two. You can leave this page; it carries on."}
        </p>
        <ol className="mt-8 flex flex-col gap-4" aria-live="polite">
          {STEPS.map(([k, label], i) => {
            const state = finished || i < at ? "done" : i === at && !failed ? "active" : i === at && failed ? "failed" : "waiting";
            return (
              <li key={k} className="flex items-center gap-3.5">
                <span className={`grid size-8 shrink-0 place-items-center rounded-full border-2 transition-colors duration-500
                  ${state === "done" ? "border-ok bg-ok text-white dark:text-[#0b1020]" : state === "active" ? "border-accent text-accent" :
                    state === "failed" ? "border-bad text-bad" : "border-border-strong text-muted"}`}>
                  {state === "done" ? <IconCheck size={16} strokeWidth={2.5} /> : state === "active" ? <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    : state === "failed" ? <IconAlert size={15} /> : <span className="text-xs font-bold">{i + 1}</span>}
                </span>
                <span className={`text-[16px] ${state === "waiting" ? "text-muted" : "font-semibold"}`}>{label}</span>
              </li>
            );
          })}
        </ol>
        {(build?.kept ?? 0) > 0 && !failed && (
          <p className="mt-6 text-sm text-muted">
            Kept {build!.kept} lines{build!.left_out ? `, left out ${build!.left_out} we couldn't find in your documents` : ""}.
          </p>
        )}
        {build?.github && !build.github.read && <p className="mt-2 text-sm text-warn">We couldn&apos;t read GitHub just now; carrying on with the rest.</p>}
        {failed && (
          <div className="mt-6 flex flex-col gap-3">
            <ErrorNote error={build?.error ?? "The build stopped."} />
            <Button className="self-start" onClick={onBack}>Back to the form</Button>
          </div>
        )}
      </div>
      {/* A sheet being written: the lines fill in while the build runs. */}
      <div aria-hidden="true" className="paper mx-auto hidden w-[240px] p-5 md:block">
        <div className="h-3 w-1/2 rounded-sm bg-text/80" />
        <div className="mt-1.5 h-2 w-3/4 rounded-sm bg-accent/50" />
        {Array.from({ length: 11 }, (_, i) => (
          <div key={i} className={`mt-2.5 h-1.5 rounded-sm ${i % 4 === 0 ? "w-1/3 bg-accent/60" : "bg-border"} ${failed ? "" : "animate-pulse"}`}
            style={{ width: i % 4 === 0 ? undefined : `${96 - (i % 3) * 11}%`, animationDelay: `${i * 120}ms` }} />
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ review

function ReviewScreen({ onFinish }: { onFinish: () => Promise<void> }) {
  const { me, refresh } = useMe();
  const { review, reload, busy, error } = useReview();
  const [stageOpen, setStageOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<"profile" | "prefs">("profile");
  const [dirty, setDirty] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [updating, setUpdating] = useState(false);

  if (!review) return error ? <ErrorNote error={error} /> : <div className="h-96 animate-pulse rounded-2xl bg-sunken" />;
  const p = review.profile;
  const c = review.counts;
  const finish = async () => { setFinishing(true); await onFinish(); };
  const rerender = async () => { setUpdating(true); await api.post("/onboarding/rerender"); setDirty(false); await reload(); setUpdating(false); };

  return (
    <div className="flex flex-col gap-10 pb-24">
      <header>
        <h1 className="text-[30px] font-bold leading-tight tracking-[-0.025em] sm:text-[36px]">Here&apos;s what we built</h1>
        <div className="mt-5 rounded-2xl bg-inland p-5 ring-1 ring-inland-edge sm:p-6">
          <p className="text-[20px] font-bold leading-snug tracking-[-0.015em] sm:text-[24px]">
            {describe(p.career_stage, p.experience_years, review.preferences.target_families)}
          </p>
          <p className="mt-2 text-sm text-text-2">
            {c.items} projects and jobs, {c.bullets} lines and {c.skills} skills, all from what you gave us.
          </p>
          {!stageOpen
            ? <button type="button" className="mt-3 text-sm font-semibold text-accent hover:underline" onClick={() => setStageOpen(true)}>Not quite right? Change it</button>
            : <div className="mt-4"><StageEditor stage={p.career_stage} years={p.experience_years}
                onSaved={async () => { setStageOpen(false); await Promise.all([reload(), refresh()]); }} onCancel={() => setStageOpen(false)} /></div>}
        </div>
      </header>

      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-[20px] font-bold tracking-tight">Your resumes</h2>
          <p className="mt-1 max-w-2xl text-[15px] leading-relaxed text-muted">
            One for each kind of role. When you pursue an opening, it gets its own copy of the closest one, reordered and
            trimmed for that job.
          </p>
        </div>
        {busy && <p className="inline-flex items-center gap-2 text-sm font-semibold text-accent">
          <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> Updating your resumes…</p>}
        <BaselineGrid review={review} busy={busy} reload={reload} />
      </section>

      <LeftOutPanel items={review.left_out} onUsed={() => { setDirty(true); reload(); }} />

      <section className="paper-inland relative overflow-hidden" aria-labelledby="the-question">
        <div className="airmail-edge h-2" />
        <div className="p-6 sm:p-8">
          <h2 id="the-question" className="font-letter text-[22px] leading-snug sm:text-[26px]">
            Would you like to add, remove or change anything in your profile or resumes?
          </h2>
          <div className="mt-5 flex flex-wrap gap-3">
            {!editing && <Button variant="secondary" className="min-h-11 px-5" onClick={() => setEditing(true)}>Yes, let me make changes</Button>}
            <Button className="min-h-11 px-5" busy={finishing} disabled={busy || updating || dirty} onClick={finish}>
              {editing ? "I'm done, finish setup" : "No, it looks good"}
            </Button>
          </div>
          {dirty && <p className="mt-3 text-sm text-warn">Update your resumes first, so they show your changes.</p>}
        </div>
      </section>

      {editing && (
        <section className="flex flex-col gap-4">
          <div role="tablist" aria-label="What to change" className="flex gap-1 self-start rounded-xl bg-sunken p-1">
            {([["profile", "Your profile"], ["prefs", "Preferences"]] as const).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={`rounded-lg px-4 py-1.5 text-sm font-semibold ${tab === k ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"}`}>{l}</button>
            ))}
          </div>
          {tab === "profile" ? <FactBankEditor onChange={() => setDirty(true)} />
            : <PreferencesForm prefs={me.preferences} profile={me.profile} onSaved={refresh} />}
        </section>
      )}

      {dirty && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
            <p className="flex-1 text-sm"><strong>Your profile changed.</strong> <span className="text-muted">Update the resumes so they show it.</span></p>
            <Button busy={updating} onClick={rerender}>Update my resumes</Button>
          </div>
        </div>
      )}
    </div>
  );
}
