"use client";

import { useRouter } from "next/navigation";
import { DragEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useMe } from "@/components/AppShell";
import FactBankEditor from "@/components/FactBankEditor";
import { IconCheck, IconFile, IconGithub, IconUpload, IconX } from "@/components/icons";
import PreferencesForm, { Toggle } from "@/components/PreferencesForm";
import RolesPicker from "@/components/RolesPicker";
import TracksEditor from "@/components/TracksEditor";
import { Badge, Button, Card, ErrorNote, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { isDemo } from "@/lib/demo";
import { FIELDS } from "@/lib/fields";
import type { Preferences, Profile } from "@/lib/types";

// The founder's flow: one sign-up form, an audit of everything given (facts, questions,
// skills), the roles that audit supports, then preferences and the resumes for those roles.
const STEPS = [
  ["consent", "Your data", "You"], ["upload", "About you", "You"],
  ["confirm", "Your facts", "Audit"], ["interview", "A few questions", "Audit"],
  ["review", "New facts", "Audit"], ["evidence", "Skills check", "Audit"],
  ["roles", "Your roles", "Roles"],
  ["preferences", "Preferences", "Set up"], ["tracks", "Resumes", "Set up"],
] as const;
type Step = (typeof STEPS)[number][0];
const PHASES = ["You", "Audit", "Roles", "Set up"] as const;

export default function Onboarding() {
  const { me, refresh } = useMe();
  const router = useRouter();
  // Demo mode can open any step: /demo?to=/onboarding?step=roles
  const saved: string = (isDemo() && new URLSearchParams(window.location.search).get("step")) || me.profile.onboarding_step;
  const initial: Step = me.needs_consent ? "consent" : (STEPS.find(([k]) => k === saved)?.[0] ?? "upload");
  const [step, setStep] = useState<Step>(initial);
  const index = STEPS.findIndex(([k]) => k === step);

  const go = async (s: Step | "done") => {
    await api.put("/profile", { onboarding_step: s });
    if (s === "done") { await refresh(); router.replace("/today"); return; }
    setStep(s);
    window.scrollTo(0, 0);
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-14">
      {/* Phone: where you are, in one line. */}
      <div className="lg:hidden">
        <div className="flex items-baseline justify-between text-sm">
          <span className="font-semibold">{STEPS[index][2]}: {STEPS[index][1]}</span>
          <span className="tabular-nums text-muted">{index + 1} of {STEPS.length}</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunken">
          <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${((index + 1) / STEPS.length) * 100}%` }} />
        </div>
      </div>

      {/* Desktop: the whole journey, grouped. */}
      <nav aria-label="Setup steps" className="hidden lg:block">
        <ol className="sticky top-8 flex flex-col gap-5">
          {PHASES.map((phase) => (
            <li key={phase}>
              <p className="mb-1.5 text-xs font-semibold text-muted">{phase}</p>
              <ol className="flex flex-col">
                {STEPS.map(([k, label, ph], i) => ph !== phase ? null : (
                  <li key={k}>
                    <button disabled={me.needs_consent} onClick={() => setStep(k)} aria-current={k === step ? "step" : undefined}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm transition-colors disabled:cursor-default
                        ${k === step ? "bg-accent-soft font-semibold text-accent" : i < index ? "text-text-2 hover:bg-sunken" : "text-muted hover:bg-sunken"}`}>
                      <span className={`grid size-5 shrink-0 place-items-center rounded-full border text-[10px] font-bold
                        ${i < index ? "border-accent bg-accent text-white dark:text-[#0b1020]" : k === step ? "border-accent text-accent" : "border-border-strong"}`}>
                        {i < index ? <IconCheck size={12} strokeWidth={3} /> : i + 1}
                      </span>
                      {label}
                    </button>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      </nav>

      <div className="min-w-0">
        {step === "consent" && <Consent version={me.consent_version} onDone={async () => { await refresh(); await go("upload"); }} />}
        {step === "upload" && <Upload prefs={me.preferences} profile={me.profile} onDone={() => go("confirm")} />}
        {step === "confirm" && (
          <Stage title="Check what we found" next={() => go("interview")}
            intro="This is what we read from everything you gave us. Nothing is used until you tick it as true. Fix anything that is wrong or overstated.">
            <FactBankEditor />
          </Stage>
        )}
        {step === "interview" && <Interview onDone={() => go("review")} />}
        {step === "review" && <Review onDone={() => go("evidence")} />}
        {step === "evidence" && <Evidence onDone={() => go("roles")} />}
        {step === "roles" && (
          <Stage title="Here's what you can apply for"
            intro="From everything you confirmed: the roles your work backs, including the ones you asked for, each with an honest fit. Take the mixed pool or pick roles yourself. Roles our job pool doesn't cover yet start being collected daily.">
            <RolesPicker initialMode={me.preferences.pool_mode ?? "mix"} saveLabel="Continue with these roles"
              onSaved={async () => { await refresh(); await go("preferences"); }} />
          </Stage>
        )}
        {step === "preferences" && (
          <Stage title="Where, when and for how much" intro="These rules decide which openings you see, and what every email may say about your availability.">
            <PreferencesForm prefs={me.preferences} profile={me.profile} submitLabel="Save and continue"
              onSaved={async () => { await refresh(); await go("tracks"); }} />
          </Stage>
        )}
        {step === "tracks" && <Tracks onDone={() => go("done")} />}
      </div>
    </div>
  );
}

function Stage({ title, intro, next, nextLabel = "Continue", children }:
  { title: string; intro?: string; next?: () => void; nextLabel?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] sm:text-[30px]">{title}</h1>
        {intro && <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">{intro}</p>}
      </div>
      {children}
      {next && <Button className="self-start min-h-10 px-5" onClick={next}>{nextLabel}</Button>}
    </div>
  );
}

function Consent({ version, onDone }: { version: string; onDone: () => void }) {
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Stage title="Before we start">
      <div className="paper max-w-2xl p-6 text-[15px] leading-relaxed sm:p-8">
        <p>Jobreach stores what you give it so it can build resumes and draft emails for you:</p>
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
        <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-xl border border-border-strong p-4 has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
          <input type="checkbox" className="mt-0.5 size-5 accent-[var(--accent)]" checked={ok} onChange={(e) => setOk(e.target.checked)} />
          <span>I understand and agree. <span className="text-muted">Notice version {version}.</span></span>
        </label>
      </div>
      <Button className="self-start min-h-10 px-5" disabled={!ok} busy={busy}
        onClick={async () => { setBusy(true); await api.post("/consent", { version }); onDone(); }}>
        Agree and continue
      </Button>
    </Stage>
  );
}

function Upload({ prefs, profile, onDone }: { prefs: Preferences; profile: Profile; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [about, setAbout] = useState(profile.about ?? "");
  const [projects, setProjects] = useState("");
  const [github, setGithub] = useState(profile.github_url ?? "");
  const [links, setLinks] = useState("");
  const [fields, setFields] = useState<string[]>(prefs.role_types);
  const [roles, setRoles] = useState(prefs.desired_roles.join(", "));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const add = (list: FileList | null) => {
    const ok = Array.from(list ?? []).filter((f) => /\.(pdf|docx|txt)$/i.test(f.name));
    setFiles((cur) => [...cur, ...ok.filter((f) => !cur.some((c) => c.name === f.name && c.size === f.size))]);
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); };

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNote(null);
    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("about", about);
    form.append("projects", projects);
    form.append("github", github);
    form.append("links", links);
    form.append("fields", fields.join(","));
    form.append("roles", roles);
    try {
      setBusy(github.trim() ? "Reading your files and GitHub…" : "Reading your files…");
      const r = await api.upload<{ github: { username: string | null; read: boolean } }>("/onboarding/upload", form);
      if (r.github.username && !r.github.read) setNote("Couldn't read your public GitHub repositories right now; carrying on with the rest.");
      setBusy("Auditing everything you gave us. About a minute…");
      await api.post("/onboarding/extract");
      onDone();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(null);
  }

  return (
    <Stage title="Tell us about you, once"
      intro="Everything here is audited into facts you confirm, and every resume and email is built only from those. Add what your resume leaves out: freelance or client work, things you deployed and who uses them, hackathons, clubs.">
      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-6">
        <Card title="Your work">
          <div className="flex flex-col gap-5">
            <div>
              <p className="mb-1.5 text-sm font-semibold">All your CVs</p>
              <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
                className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors
                  ${drag ? "border-accent bg-accent-soft" : "border-border-strong hover:border-accent hover:bg-sunken/60"}`}>
                <span className="grid size-11 place-items-center rounded-full bg-accent-soft text-accent"><IconUpload size={22} /></span>
                <span className="text-[15px] font-semibold">Drop CVs here, or <span className="text-accent underline underline-offset-2">choose files</span></span>
                <span className="text-[13px] text-muted">PDF, DOCX or TXT. Every version you have: each may mention something the others don&apos;t.</span>
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
            </div>
            <Field label="About you" hint="Plain words are fine. What you built, for whom, and any real numbers you know.">
              <textarea className={inputCls} rows={4} value={about} onChange={(e) => setAbout(e.target.value)} />
            </Field>
            <Field label="Your projects" hint="One per paragraph: what it does, the stack, who used it, a live link if there is one.">
              <textarea className={inputCls} rows={4} value={projects} onChange={(e) => setProjects(e.target.value)} />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="GitHub" hint="We read your public repositories, not forks.">
                <span className="relative">
                  <IconGithub size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                  <input className={`${inputCls} pl-9`} placeholder="github.com/your-username" value={github} onChange={(e) => setGithub(e.target.value)} />
                </span>
              </Field>
              <Field label="Other links" hint="Portfolio, LeetCode, Kaggle, one per line.">
                <textarea className={inputCls} rows={2} value={links} onChange={(e) => setLinks(e.target.value)} />
              </Field>
            </div>
          </div>
        </Card>
        <Card title="What you want">
          <div className="flex flex-col gap-5">
            <Field label="Fields" hint="Pick any that interest you. The audit tells you how well your work backs each one.">
              <div className="flex flex-wrap gap-2">
                {FIELDS.map(([k, l]) => (
                  <Toggle key={k} on={fields.includes(k)}
                    set={() => setFields(fields.includes(k) ? fields.filter((x) => x !== k) : [...fields, k])}>{l}</Toggle>
                ))}
              </div>
            </Field>
            <Field label="Roles you want" hint="Comma separated, for example: Backend Developer Intern, ML Engineer Intern.">
              <input className={inputCls} value={roles} onChange={(e) => setRoles(e.target.value)} />
            </Field>
          </div>
        </Card>
        <ErrorNote error={error} />
        {note && <p className="rounded-[10px] bg-warn-soft px-3.5 py-2.5 text-sm text-warn">{note}</p>}
        <Button type="submit" className="self-start min-h-11 px-6 text-[15px]" busy={!!busy}>{busy ?? "Audit my profile"}</Button>
      </form>
    </Stage>
  );
}

function Interview({ onDone }: { onDone: () => void }) {
  const [history, setHistory] = useState<{ role: string; content: string }[]>([]);
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const turn = useCallback(async (a: string | null) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ question: string | null; done: boolean }>("/onboarding/interview", { answer: a });
      setHistory(await api.get("/onboarding/interview"));
      setQuestion(r.question);
      setDone(r.done);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  }, []);

  useEffect(() => {
    api.get<{ role: string; content: string }[]>("/onboarding/interview").then((h) => {
      setHistory(h);
      const last = h[h.length - 1];
      if (last?.role === "assistant") setQuestion(last.content);
      else turn(null);
    });
  }, [turn]);

  return (
    <Stage title="A few questions"
      intro="Short questions to find strong, true evidence your resume is missing. If you don't know a number, say so: nothing is ever estimated.">
      <div className="flex max-w-2xl flex-col gap-4">
        {history.map((m, i) => m.role === "assistant" ? (
          <p key={i} className="font-letter text-[17px] leading-relaxed">{m.content}</p>
        ) : (
          <p key={i} className="ml-8 self-end rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] text-white dark:text-[#0b1020]">{m.content}</p>
        ))}
        {done && <p className="inline-flex items-center gap-2 font-semibold text-ok"><IconCheck size={18} /> That&apos;s everything for now.</p>}
        {!done && question && (
          <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (answer.trim()) { turn(answer); setAnswer(""); } }}>
            <textarea className={inputCls} rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer. “I don't know” is a fine answer." />
            <div className="flex gap-2">
              <Button type="submit" busy={busy}>Answer</Button>
              <Button type="button" variant="ghost" disabled={busy} onClick={onDone}>Skip the rest</Button>
            </div>
          </form>
        )}
        {busy && !question && <p className="text-muted">Thinking of a question…</p>}
        <ErrorNote error={error} />
        {done && <Button className="self-start" onClick={onDone}>Continue</Button>}
      </div>
    </Stage>
  );
}

function Review({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [key, setKey] = useState(0);
  return (
    <Stage title="What the questions found" next={onDone}
      intro="New facts from your answers appear under Other facts. Tick the true ones, then write bullets from them. Bullets can only restate confirmed facts, with the same numbers.">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" busy={busy} onClick={async () => {
          setBusy(true);
          const r = await api.post<{ proposed: number }>("/onboarding/bullets");
          setMsg(r.proposed ? `${r.proposed} bullet${r.proposed === 1 ? "" : "s"} proposed below. Tick the ones you agree with.` : "No confirmed new facts need bullets.");
          setKey((k) => k + 1);
          setBusy(false);
        }}>Write bullets from confirmed facts</Button>
        {msg && <span className="text-sm text-muted">{msg}</span>}
      </div>
      <FactBankEditor key={key} />
    </Stage>
  );
}

function Evidence({ onDone }: { onDone: () => void }) {
  const [rows, setRows] = useState<{ fact_id: string; skill: string; backed_by: string[]; backed: boolean }[] | null>(null);
  const load = useCallback(() => api.get<typeof rows>("/onboarding/evidence").then(setRows), []);
  useEffect(() => { load(); }, [load]);
  const unbacked = rows?.filter((r) => !r.backed) ?? [];
  const backed = rows?.filter((r) => r.backed) ?? [];
  return (
    <Stage title="Every skill needs evidence" next={onDone}
      intro="A skill no project, job or role mentions is an interview risk: you may be asked about it. Remove it, or add the work that shows it.">
      <div className="max-w-2xl">
        <p className="text-[15px]"><span className="text-2xl font-bold tabular-nums">{backed.length}</span>
          <span className="text-muted"> of {rows?.length ?? "…"} skills are backed by your confirmed work.</span></p>
        <div className="mt-3 flex flex-wrap gap-2">
          {backed.map((r) => <Badge key={r.fact_id} tone="ok"><IconCheck size={12} /> {r.skill}</Badge>)}
        </div>
        {unbacked.length > 0 && (
          <ul className="mt-6 flex flex-col divide-y divide-border rounded-2xl border border-warn/30 bg-warn-soft/40">
            {unbacked.map((r) => (
              <li key={r.fact_id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <span className="flex-1"><span className="font-semibold">{r.skill}</span> <span className="text-muted">appears in no project or role</span></span>
                <Button variant="ghost" onClick={async () => { await api.del(`/facts/${r.fact_id}`); load(); }}>Remove</Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Stage>
  );
}

function Tracks({ onDone }: { onDone: () => void }) {
  const [ready, setReady] = useState(0);
  return (
    <Stage title="Your resumes"
      intro="One resume per family of roles you chose. Approving one builds it at the largest type size that still fits one page, checked by rendering it.">
      <TracksEditor onApprovedChange={setReady} />
      <Button className="self-start min-h-11 px-6 text-[15px]" disabled={ready === 0} onClick={onDone}>
        {ready === 0 ? "Approve a resume to finish" : "Finish setup"}
      </Button>
    </Stage>
  );
}
