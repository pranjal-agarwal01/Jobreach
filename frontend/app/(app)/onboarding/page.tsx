"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useMe } from "@/components/AppShell";
import FactBankEditor from "@/components/FactBankEditor";
import PreferencesForm, { Toggle } from "@/components/PreferencesForm";
import RolesPicker from "@/components/RolesPicker";
import TracksEditor from "@/components/TracksEditor";
import { Badge, Button, Card, ErrorNote, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { FIELDS } from "@/lib/fields";
import type { Preferences, Profile } from "@/lib/types";

// The founder's flow: one sign-up form, an audit of everything given (facts, questions,
// skills), the roles that audit supports, then preferences and the resumes for those roles.
const STEPS = [
  ["consent", "Consent"], ["upload", "About you"], ["confirm", "Audit: facts"], ["interview", "Audit: questions"],
  ["review", "Audit: new facts"], ["evidence", "Audit: skills"], ["roles", "Your roles"], ["preferences", "Preferences"],
  ["tracks", "Resumes"],
] as const;
type Step = (typeof STEPS)[number][0];

export default function Onboarding() {
  const { me, refresh } = useMe();
  const router = useRouter();
  const saved: string = me.profile.onboarding_step;
  const initial: Step = me.needs_consent ? "consent"
    : (STEPS.find(([k]) => k === saved)?.[0] ?? (saved === "extract" ? "upload" : "upload"));
  const [step, setStep] = useState<Step>(initial);

  const go = async (s: Step | "done") => {
    await api.put("/profile", { onboarding_step: s });
    if (s === "done") { await refresh(); router.replace("/today"); return; }
    setStep(s);
    window.scrollTo(0, 0);
  };

  return (
    <div className="flex flex-col gap-5">
      <ol className="flex flex-wrap gap-2 text-xs">
        {STEPS.map(([k, label], i) => (
          <li key={k}>
            <button onClick={() => !me.needs_consent && setStep(k)}
              className={`rounded-full px-3 py-1 ${k === step ? "bg-accent text-surface" : "bg-surface text-muted border border-border"}`}>
              {i + 1}. {label}
            </button>
          </li>
        ))}
      </ol>
      {step === "consent" && <Consent version={me.consent_version} onDone={async () => { await refresh(); await go("upload"); }} />}
      {step === "upload" && <Upload prefs={me.preferences} profile={me.profile} onDone={() => go("confirm")} />}
      {step === "confirm" && (
        <Stage title="Confirm your facts" next={() => go("interview")}
          intro="This is what we read from your resume. Nothing is used until you confirm it. Fix anything that is wrong or overstated.">
          <FactBankEditor />
        </Stage>
      )}
      {step === "interview" && <Interview onDone={() => go("review")} />}
      {step === "review" && <Review onDone={() => go("evidence")} />}
      {step === "evidence" && <Evidence onDone={() => go("roles")} />}
      {step === "roles" && (
        <Stage title="The roles your profile supports"
          intro="From everything you confirmed, these are the roles you can credibly apply for, including the ones you asked for, with an honest fit. Take the mixed pool or pick roles. Openings come from the job pool; roles it does not cover yet are added to its daily collection.">
          <RolesPicker initialMode={me.preferences.pool_mode ?? "mix"} saveLabel="Continue with these roles"
            onSaved={async () => { await refresh(); await go("preferences"); }} />
        </Stage>
      )}
      {step === "preferences" && (
        <Stage title="What you want" intro="These rules decide which leads are kept, and what every email may say about you.">
          <PreferencesForm prefs={me.preferences} profile={me.profile} submitLabel="Save and continue"
            onSaved={async () => { await refresh(); await go("tracks"); }} />
        </Stage>
      )}
      {step === "tracks" && <Tracks onDone={() => go("done")} />}
    </div>
  );
}

function Stage({ title, intro, next, nextLabel = "Continue", children }:
  { title: string; intro?: string; next?: () => void; nextLabel?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {intro && <p className="mt-1 max-w-3xl text-sm text-muted">{intro}</p>}
      </div>
      {children}
      {next && <Button className="self-start" onClick={next}>{nextLabel}</Button>}
    </div>
  );
}

function Consent({ version, onDone }: { version: string; onDone: () => void }) {
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Stage title="Before we start">
      <Card>
        <div className="flex max-w-3xl flex-col gap-2 text-sm">
          <p>Jobreach stores what you give it so it can build resumes and draft emails for you:</p>
          <ul className="list-disc pl-5">
            <li>your resume text, contact details, grades and the facts you confirm;</li>
            <li>job posts you paste (private to you) and the resumes and drafts made from them;</li>
            <li>replies and outcomes you log.</li>
          </ul>
          <p>
            It is used only to produce your resumes and drafts. To read posts and write drafts, text is processed by
            OpenAI models through Microsoft&apos;s Azure OpenAI service, which does not use it to train models.
            Jobreach never sends an email or submits an application for you. You can delete your account and all of
            your data at any time from Profile.
          </p>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />
            I understand and agree (notice version {version}).
          </label>
        </div>
      </Card>
      <Button className="self-start" disabled={!ok} busy={busy}
        onClick={async () => { setBusy(true); await api.post("/consent", { version }); onDone(); }}>
        Agree and continue
      </Button>
    </Stage>
  );
}

function Upload({ prefs, profile, onDone }: { prefs: Preferences; profile: Profile; onDone: () => void }) {
  const files = useRef<HTMLInputElement>(null);
  const [about, setAbout] = useState(profile.about ?? "");
  const [projects, setProjects] = useState("");
  const [github, setGithub] = useState(profile.github_url ?? "");
  const [links, setLinks] = useState("");
  const [fields, setFields] = useState<string[]>(prefs.role_types);
  const [roles, setRoles] = useState(prefs.desired_roles.join(", "));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNote(null);
    const form = new FormData();
    for (const f of Array.from(files.current?.files ?? [])) form.append("files", f);
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
      setBusy("Auditing everything you gave us. This takes about a minute…");
      await api.post("/onboarding/extract");
      onDone();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    setBusy(null);
  }

  return (
    <Stage title="Tell us about you, once"
      intro="Everything here is audited into facts you confirm, and every resume and email is built only from those. Add what your resume leaves out: freelance or client work, things you deployed and who uses them, hackathons, clubs.">
      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-4">
        <Card title="Your work">
          <div className="flex flex-col gap-4">
            <Field label="All your CVs" hint="PDF, DOCX or TXT. Upload every version you have: each one may mention something the others don't.">
              <input ref={files} type="file" multiple accept=".pdf,.docx,.txt" className="text-sm" />
            </Field>
            <Field label="About you" hint="Plain words are fine. What you built, for whom, and any real numbers you know.">
              <textarea className={inputCls} rows={5} value={about} onChange={(e) => setAbout(e.target.value)} />
            </Field>
            <Field label="Your projects" hint="One per paragraph: what it does, the stack, who used it, a live link if there is one.">
              <textarea className={inputCls} rows={5} value={projects} onChange={(e) => setProjects(e.target.value)} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="GitHub" hint="We read your public repositories (not forks).">
                <input className={inputCls} placeholder="github.com/your-username" value={github} onChange={(e) => setGithub(e.target.value)} />
              </Field>
              <Field label="Other links" hint="Portfolio, LeetCode, Kaggle and similar, one per line.">
                <textarea className={inputCls} rows={2} value={links} onChange={(e) => setLinks(e.target.value)} />
              </Field>
            </div>
          </div>
        </Card>
        <Card title="What you want">
          <div className="flex flex-col gap-4">
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
        {note && <p className="rounded-md bg-warn-soft px-3 py-2 text-sm text-warn">{note}</p>}
        <Button type="submit" className="self-start" busy={!!busy}>{busy ?? "Audit my profile"}</Button>
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
    <Stage title="A few questions" nextLabel="Continue"
      intro="Short questions to find strong, true evidence your resume is missing. If you don't know a number, say so: nothing is ever estimated.">
      <Card>
        <div className="flex max-w-3xl flex-col gap-3 text-sm">
          {history.map((m, i) => (
            <p key={i} className={m.role === "assistant" ? "font-medium" : "ml-6 rounded-md bg-accent-soft px-3 py-2"}>{m.content}</p>
          ))}
          {done && <p className="text-ok">That&apos;s everything for now.</p>}
          {!done && question && (
            <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (answer.trim()) { turn(answer); setAnswer(""); } }}>
              <textarea className={inputCls} rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)}
                placeholder="Your answer. 'I don't know' is a fine answer." />
              <div className="flex gap-2">
                <Button type="submit" busy={busy}>Answer</Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={onDone}>Skip the rest</Button>
              </div>
            </form>
          )}
          {busy && !question && <p className="text-muted">Thinking of a question…</p>}
          <ErrorNote error={error} />
        </div>
      </Card>
      {done && <Button className="self-start" onClick={onDone}>Continue</Button>}
    </Stage>
  );
}

function Review({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [key, setKey] = useState(0);
  return (
    <Stage title="Review what the interview found" next={onDone}
      intro="New facts from the interview appear under Other facts. Confirm the ones that are true, then write bullets from them. Bullets can only restate confirmed facts, with the same numbers.">
      <div className="flex items-center gap-3">
        <Button variant="secondary" busy={busy} onClick={async () => {
          setBusy(true);
          const r = await api.post<{ proposed: number }>("/onboarding/bullets");
          setMsg(r.proposed ? `${r.proposed} bullet(s) proposed below. Confirm the ones you agree with.` : "No confirmed new facts need bullets.");
          setKey((k) => k + 1);
          setBusy(false);
        }}>Write bullets from confirmed new facts</Button>
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
  return (
    <Stage title="Every skill needs evidence" next={onDone}
      intro="A skill no project, job or role mentions is an interview risk: you may be asked about it. Remove it, or add the work that shows it.">
      <Card title={rows ? `${rows.length - unbacked.length} of ${rows.length} skills backed` : "Checking…"}>
        {unbacked.length === 0 && rows && <p className="text-sm text-ok">Every skill is backed by your confirmed work.</p>}
        <ul className="flex flex-col gap-2">
          {unbacked.map((r) => (
            <li key={r.fact_id} className="flex items-center gap-3 text-sm">
              <Badge tone="warn">no evidence</Badge>
              <span className="flex-1">{r.skill}</span>
              <Button variant="ghost" onClick={async () => { await api.del(`/facts/${r.fact_id}`); load(); }}>Remove</Button>
            </li>
          ))}
        </ul>
      </Card>
    </Stage>
  );
}

function Tracks({ onDone }: { onDone: () => void }) {
  const [ready, setReady] = useState(0);
  return (
    <Stage title="Your resume tracks"
      intro="Approve at least one. Approving builds a one-page baseline at the largest type size that fits, checked by rendering it.">
      <TracksEditor onApprovedChange={setReady} />
      <Button className="self-start" disabled={ready === 0} onClick={onDone}>
        {ready === 0 ? "Approve a track to finish" : "Finish setup"}
      </Button>
    </Stage>
  );
}
