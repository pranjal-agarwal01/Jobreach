"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isDemo, setDemo } from "@/lib/demo";
import { supabase } from "@/lib/supabase";
import type { Me } from "@/lib/types";
import { IconFolder, IconLogout, IconMail, IconOutbox, IconPaste, IconUser } from "./icons";

const MeContext = createContext<{ me: Me; refresh: () => Promise<void> } | null>(null);

export function useMe() {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe outside AppShell");
  return ctx;
}

const NAV = [
  { href: "/today", label: "Today", icon: IconOutbox },
  { href: "/jobs", label: "Jobs", icon: IconFolder },
  { href: "/leads", label: "Add leads", icon: IconPaste },
  { href: "/profile", label: "Profile", icon: IconUser },
];

/** The brand mark: an envelope inside an air-mail border. */
export function Brand({ small = false }: { small?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className={`airmail-edge-fine grid shrink-0 place-items-center rounded-[9px] p-[3px] ${small ? "size-7" : "size-8"}`}>
        <span className="grid size-full place-items-center rounded-[6px] bg-surface text-accent"><IconMail size={small ? 14 : 16} strokeWidth={2.2} /></span>
      </span>
      <span className={`font-extrabold tracking-[-0.03em] ${small ? "text-[17px]" : "text-[19px]"}`}>Jobreach</span>
    </span>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemoState] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/me"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const d = isDemo();
      setDemoState(d);
      if (!data.session && !d) router.replace("/login");
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
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-2 p-8 text-sm">
        <Brand />
        <p className="mt-6 text-base font-semibold">Jobreach can&apos;t reach its server.</p>
        <p className="text-muted">{error}</p>
        <p className="text-muted">Check that the API is running on port 8000, then reload.</p>
      </div>
    );
  }
  if (!me) {
    return <div className="grid min-h-screen place-items-center"><span className="size-5 animate-spin rounded-full border-2 border-accent border-t-transparent" /></div>;
  }

  const signOut = () => {
    if (demo) { setDemo(false); router.replace("/login"); }
    else supabase.auth.signOut();
  };
  const active = (href: string) => path.startsWith(href);

  return (
    <MeContext.Provider value={{ me, refresh }}>
      {demo && (
        <div className="sticky top-0 z-30 flex items-center justify-center gap-3 bg-text px-4 py-1.5 text-xs text-bg">
          <span>Demo: a made-up student and fictional companies. Nothing you do here is saved.</span>
          <button className="font-semibold underline underline-offset-2" onClick={signOut}>Exit demo</button>
        </div>
      )}

      {onboarding ? (
        <header className="border-b border-border bg-surface/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
            <Brand small />
            <button className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text" onClick={signOut}>
              <IconLogout size={16} /> Sign out
            </button>
          </div>
        </header>
      ) : (
        <>
          {/* Desktop: a quiet rail. */}
          <aside className={`fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-surface md:flex ${demo ? "top-[30px]" : ""}`}>
            <div className="px-5 pb-6 pt-5"><Link href="/today" aria-label="Jobreach home"><Brand /></Link></div>
            <nav className="flex flex-col gap-0.5 px-3" aria-label="Main">
              {NAV.map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
                  className={`group flex items-center gap-3 rounded-[10px] px-3 py-2 text-[15px] font-medium transition-colors
                    ${active(href) ? "bg-accent-soft text-accent" : "text-text-2 hover:bg-sunken hover:text-text"}`}>
                  <Icon size={19} className={active(href) ? "" : "text-muted group-hover:text-text"} />
                  <span className="flex-1">{label}</span>
                  {href === "/jobs" && me.counts.applications > 0 && (
                    <span className="text-xs tabular-nums text-muted">{me.counts.applications}</span>
                  )}
                </Link>
              ))}
            </nav>
            <div className="mt-auto border-t border-border p-4">
              <p className="truncate text-sm font-semibold">{me.profile.name ?? "You"}</p>
              <p className="truncate text-xs text-muted">{me.user.email}</p>
              <button onClick={signOut} className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
                <IconLogout size={16} /> {demo ? "Exit demo" : "Sign out"}
              </button>
            </div>
          </aside>

          {/* Phone: brand on top, the four places at the thumb. */}
          <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-surface/90 px-4 py-2.5 backdrop-blur md:hidden">
            <Link href="/today" aria-label="Jobreach home"><Brand small /></Link>
            <button onClick={signOut} className="grid size-10 place-items-center rounded-full text-muted hover:bg-sunken" aria-label="Sign out">
              <IconLogout size={18} />
            </button>
          </header>
          <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
                className={`flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-semibold ${active(href) ? "text-accent" : "text-muted"}`}>
                <Icon size={21} />
                {label}
              </Link>
            ))}
          </nav>
        </>
      )}

      <main className={onboarding ? "mx-auto max-w-6xl px-4 py-8 sm:px-6" : "px-4 pb-28 pt-6 sm:px-6 md:ml-60 md:px-10 md:pb-12 md:pt-10"}>
        <div className={onboarding ? "" : "mx-auto max-w-[1080px]"}>{children}</div>
      </main>
    </MeContext.Provider>
  );
}
