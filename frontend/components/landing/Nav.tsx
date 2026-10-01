"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Brand } from "@/components/AppShell";
import { supabase } from "@/lib/supabase";
import { EASE, GetStarted } from "./primitives";

const LINKS = [
  ["#how", "How it works"],
  ["#tailor", "Your resume"],
  ["#promises", "Promises"],
  ["#faq", "FAQ"],
] as const;

/** A floating island, so the page shows through around it. Signed-in visitors get a way
 *  back to their desk instead of the sign-up button. */
export default function Nav() {
  const [open, setOpen] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSignedIn(Boolean(data.session))).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open]);

  return (
    <>
      <header className="fixed inset-x-0 top-3 z-40 px-3 sm:top-4 sm:px-4">
        <nav aria-label="Main"
          className="mx-auto flex h-14 w-full max-w-5xl items-center gap-2 rounded-full border border-border/80 bg-surface/80 pl-4 pr-2 shadow-[0_1px_0_rgb(255_255_255/0.5)_inset,0_12px_32px_-18px_rgb(20_27_52/0.35)] backdrop-blur-xl sm:pl-5">
          <Link href="/" aria-label="Jobreach, home" className="mr-auto rounded-lg"><Brand small /></Link>
          <ul className="hidden items-center gap-1 md:flex">
            {LINKS.map(([href, label]) => (
              <li key={href}>
                <a href={href} className="rounded-full px-3.5 py-2 text-sm font-semibold text-text-2 transition-colors hover:bg-sunken hover:text-text">{label}</a>
              </li>
            ))}
          </ul>
          {signedIn ? (
            <Link href="/today" className="ml-2 inline-flex h-10 items-center rounded-full bg-accent px-5 text-sm font-semibold text-white hover:bg-accent-strong dark:text-[#0b1020]">
              Open Jobreach
            </Link>
          ) : (
            <>
              <Link href="/login" className="ml-1 hidden rounded-full px-3.5 py-2 text-sm font-semibold text-text-2 hover:text-text sm:inline-flex">Sign in</Link>
              <GetStarted size="sm" />
            </>
          )}
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            className="relative grid size-10 place-items-center rounded-full text-text hover:bg-sunken md:hidden">
            <span className={`absolute h-[1.75px] w-[18px] rounded-full bg-current transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${open ? "rotate-45" : "-translate-y-[4px]"}`} />
            <span className={`absolute h-[1.75px] w-[18px] rounded-full bg-current transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${open ? "-rotate-45" : "translate-y-[4px]"}`} />
          </button>
        </nav>
      </header>

      <AnimatePresence>
        {open && (
          <motion.div id="mobile-menu" className="fixed inset-0 z-30 flex flex-col bg-bg/95 px-6 pb-10 pt-28 backdrop-blur-2xl md:hidden"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
            <ul className="flex flex-col gap-1">
              {LINKS.map(([href, label], i) => (
                <motion.li key={href} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.05 + i * 0.05, ease: EASE }}>
                  <a href={href} onClick={() => setOpen(false)} className="block py-3 text-[32px] font-bold tracking-[-0.03em]">{label}</a>
                </motion.li>
              ))}
            </ul>
            <motion.div className="mt-auto flex flex-col gap-3" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3, ease: EASE }}>
              {signedIn
                ? <Link href="/today" className="rounded-full bg-accent py-3.5 text-center font-semibold text-white dark:text-[#0b1020]">Open Jobreach</Link>
                : <>
                    <GetStarted size="lg" className="justify-between" />
                    <Link href="/login" className="py-2 text-center font-semibold text-text-2">Sign in</Link>
                  </>}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
