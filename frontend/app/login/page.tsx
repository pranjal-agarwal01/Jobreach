"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, ErrorNote, Field, inputCls } from "@/components/ui";
import { supabase } from "@/lib/supabase";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
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
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-6">
        <h1 className="text-xl font-semibold text-accent">Jobreach</h1>
        <p className="mb-5 mt-1 text-sm text-muted">
          A truthful, tailored resume and email for every fresh opening. You press Send.
        </p>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Field label="Email">
            <input className={inputCls} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" hint={mode === "signup" ? "At least 8 characters" : undefined}>
            <input className={inputCls} type="password" required minLength={8} value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <ErrorNote error={error} />
          {note && <p className="rounded-md bg-ok-soft px-3 py-2 text-sm text-ok">{note}</p>}
          <Button type="submit" busy={busy}>{mode === "signin" ? "Sign in" : "Create account"}</Button>
        </form>
        <button className="mt-4 text-sm text-muted hover:text-text"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>
          {mode === "signin" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
