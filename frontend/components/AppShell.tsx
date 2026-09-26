"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Me } from "@/lib/types";

const MeContext = createContext<{ me: Me; refresh: () => Promise<void> } | null>(null);

export function useMe() {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe outside AppShell");
  return ctx;
}

const NAV = [
  { href: "/today", label: "Today" },
  { href: "/leads", label: "Leads" },
  { href: "/applications", label: "Applications" },
  { href: "/profile", label: "Profile" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/me"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) router.replace("/login");
      else refresh();
    });
    const { data: sub } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") router.replace("/login");
    });
    return () => sub.subscription.unsubscribe();
  }, [router, refresh]);

  const onboarding = me && (me.needs_consent || me.profile.onboarding_step !== "done");
  useEffect(() => {
    if (onboarding && !path.startsWith("/onboarding")) router.replace("/onboarding");
  }, [onboarding, path, router]);

  if (error) {
    return (
      <div className="mx-auto max-w-md p-8 text-sm">
        <p className="mb-2 font-medium">Could not reach the Jobreach API.</p>
        <p className="text-muted">{error}</p>
      </div>
    );
  }
  if (!me) return <div className="p-8 text-sm text-muted">Loading…</div>;

  return (
    <MeContext.Provider value={{ me, refresh }}>
      <header className="sticky top-0 z-10 border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href="/today" className="text-lg font-semibold text-accent">Jobreach</Link>
          {!onboarding && (
            <nav className="flex gap-1 text-sm">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href}
                  className={`rounded-md px-2.5 py-1 ${path.startsWith(n.href) ? "bg-accent-soft text-accent" : "text-muted hover:text-text"}`}>
                  {n.label}
                </Link>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm text-muted">
            <span className="hidden sm:inline">{me.user.email}</span>
            <button className="hover:text-text" onClick={() => supabase.auth.signOut()}>Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </MeContext.Provider>
  );
}
