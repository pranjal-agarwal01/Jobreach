"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { Brand } from "@/components/AppShell";
import { IconCheck } from "@/components/icons";
import { Button, ErrorNote, Field, Postmark, inputCls } from "@/components/ui";
import { supabase } from "@/lib/supabase";

/** The landing page's "Get started" opens this in sign-up mode (?mode=signup). */
export default function Login() {
  return <Suspense><LoginForm /></Suspense>;
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<"signin" | "signup">(params.get("mode") === "signup" ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => { if (data.session) router.replace("/today"); });
  }, [router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNote(null);
    const res = mode === "signin"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + "/login" } });
    setBusy(false);
    if (res.error) return setError(res.error.message);
    if (res.data.session) router.replace("/today");
    else setNote("Check your inbox to confirm your email, then sign in.");
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* The product, shown by what it makes: a letter, written while the post is fresh. */}
      <section className="relative hidden overflow-hidden bg-inland px-12 py-10 lg:flex lg:flex-col xl:px-16">
        <Link href="/" aria-label="Jobreach, home" className="self-start rounded-lg"><Brand /></Link>
        <div className="my-auto max-w-xl py-12">
          <h1 className="text-[44px] font-bold leading-[1.05] tracking-[-0.03em] xl:text-[52px]">
            Write to founders while the post is still fresh.
          </h1>
          <ul className="mt-6 flex flex-col gap-2.5 text-[16px] text-text-2">
            {["Every line comes from your own CV and projects", "A one-page resume made for each opening",
              "You read it and press Send. Always."].map((t) => (
              <li key={t} className="flex items-center gap-2.5"><IconCheck size={18} className="text-accent" />{t}</li>
            ))}
          </ul>
          <article className="paper relative mt-12 max-w-lg -rotate-[1.2deg] overflow-hidden" aria-label="An example letter">
            <div className="airmail-edge h-2" />
            <Postmark date={new Date().toISOString()} label="FRESH" className="absolute right-5 top-5 size-20" />
            <div className="px-7 pb-7 pt-5 font-letter text-[15px] leading-[1.7] text-text-2">
              <p className="pr-20 font-sans text-xs text-muted">To careers@kitebox.example</p>
              <p className="mt-3 text-text">Hi Riya,</p>
              <p className="mt-2">
                I saw your post about the Backend Developer Intern role, two hours ago. At my college fest I built a job queue
                that took lost registration emails from about 40 to zero&hellip;
              </p>
            </div>
          </article>
        </div>
        <p className="text-sm text-muted">Jobreach never sends email, submits applications, or logs into LinkedIn for you.</p>
      </section>

      <section className="flex flex-col px-5 py-8 sm:px-10">
        <div className="lg:hidden"><Link href="/" aria-label="Jobreach, home" className="rounded-lg"><Brand /></Link></div>
        <div className="m-auto w-full max-w-sm py-10">
          <h2 className="text-[30px] font-bold tracking-[-0.02em]">{mode === "signin" ? "Sign in" : "Create your account"}</h2>
          <p className="mt-1.5 text-[15px] text-muted">
            {mode === "signin" ? "Your letters and folders are where you left them." : "One form, then a letter for every opening that fits you."}
          </p>
          <p className="mt-4 text-[15px] leading-relaxed text-text-2 lg:hidden">
            Write to founders while the post is still fresh. Every line comes from your own CV, and you press Send.
          </p>
          <form onSubmit={submit} className="mt-8 flex flex-col gap-4">
            <Field label="Email">
              <input className={inputCls} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Password" hint={mode === "signup" ? "At least 8 characters" : undefined}>
              <input className={inputCls} type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"}
                required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <ErrorNote error={error} />
            {note && <p className="rounded-[10px] bg-ok-soft px-3.5 py-2.5 text-sm text-ok">{note}</p>}
            <Button type="submit" busy={busy} className="mt-2 min-h-11 text-[15px]">{mode === "signin" ? "Sign in" : "Create account"}</Button>
          </form>
          <p className="mt-6 text-sm text-muted">
            {mode === "signin" ? "New here? " : "Already have an account? "}
            <button className="font-semibold text-accent hover:underline" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null); setNote(null); }}>
              {mode === "signin" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </div>
      </section>
    </div>
  );
}
