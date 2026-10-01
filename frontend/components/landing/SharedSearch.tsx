"use client";

import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { IconAlert, IconCheck } from "@/components/icons";
import { Freshness, Monogram } from "@/components/ui";
import { EASE, Reveal } from "./primitives";

// The global pool in one picture: one opening, found once, matched separately to two people
// with the same years and different work. The lines draw from the opening out to each person.
const PEOPLE = [
  { name: "Nandini", years: "3 years", work: "Built a RAG search over support tickets with FastAPI at her current job.",
    verdict: "Strong match", tone: "ok" as const,
    notes: [["ok", "FastAPI and RAG: her support-ticket search"], ["ok", "3 years: inside 3 to 5"]] },
  { name: "Arjun", years: "3 years", work: "Computer vision with TensorFlow: defect detection on a factory line.",
    verdict: "Match with gaps", tone: "warn" as const,
    notes: [["ok", "Python: yes, in every project"], ["warn", "No FastAPI or RAG work yet"]] },
];

export default function SharedSearch() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.4 });
  return (
    <section id="pool" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-[1320px]">
        <Reveal className="mx-auto max-w-3xl text-center">
          <h2 className="text-balance text-[34px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[48px]">Found once. Matched only to you.</h2>
          <p className="mx-auto mt-4 max-w-[60ch] text-[18px] leading-relaxed text-text-2">
            Openings are collected and checked once, then shared, so nobody waits for a search. The match is yours
            alone: your skills, your projects, your years.
          </p>
        </Reveal>

        <div ref={ref} className="mx-auto mt-16 grid max-w-[1160px] items-center gap-y-4 lg:grid-cols-[minmax(0,1fr)_96px_minmax(0,1.15fr)_96px_minmax(0,1fr)]">
          <Person p={PEOPLE[0]} seen={seen} className="order-3 lg:order-1" />
          <Connector seen={seen} flip className="order-2 lg:order-2" />
          <Opening seen={seen} className="order-1 lg:order-3" />
          <Connector seen={seen} className="order-4 max-lg:hidden lg:order-4" />
          <Person p={PEOPLE[1]} seen={seen} className="order-5 lg:order-5" />
        </div>

        <Reveal className="mx-auto mt-12 max-w-xl">
          <p className="text-center text-[15px] leading-relaxed text-muted">
            Only the opening is shared. Your resume, your match scores and your letters are never shown to anyone else.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function Opening({ seen, className }: { seen: boolean; className: string }) {
  return (
    <motion.div className={`paper relative p-6 sm:p-7 ${className}`}
      initial={{ opacity: 0, y: 24 }} animate={seen ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7, ease: EASE }}>
      <div className="flex items-center gap-3">
        <Monogram name="Saltpan AI" size={42} />
        <div className="min-w-0">
          <p className="text-[17px] font-bold">AI Engineer</p>
          <p className="text-sm text-muted">Saltpan AI, Bengaluru, hybrid</p>
        </div>
        <span className="ml-auto"><Freshness hours={4} compact /></span>
      </div>
      <p className="mt-5 text-[13px] font-semibold text-muted">Asks for</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {["Python", "FastAPI", "RAG", "3 to 5 years"].map((a) => (
          <span key={a} className="rounded-full bg-sunken px-3 py-1 text-sm font-semibold text-text-2">{a}</span>
        ))}
      </div>
      <p className="mt-5 border-t border-dashed border-border pt-4 text-[13px] text-muted">Collected once, from the company&apos;s own careers page</p>
    </motion.div>
  );
}

/** A line from the opening to a person: horizontal on wide screens, vertical on phones. */
function Connector({ seen, flip = false, className }: { seen: boolean; flip?: boolean; className: string }) {
  const draw = { initial: { pathLength: 0 }, animate: seen ? { pathLength: 1 } : {}, transition: { duration: 0.8, delay: 0.5, ease: EASE } };
  return (
    <div aria-hidden="true" className={`flex justify-center ${className}`}>
      <svg viewBox="0 0 96 24" className="hidden h-6 w-24 text-accent lg:block" style={{ transform: flip ? "scaleX(-1)" : undefined }}>
        <motion.path d="M0 12 H90" fill="none" stroke="currentColor" strokeWidth="2" {...draw} />
        <motion.path d="M84 6 L91 12 L84 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          initial={{ opacity: 0 }} animate={seen ? { opacity: 1 } : {}} transition={{ delay: 1.2, duration: 0.3 }} />
      </svg>
      <svg viewBox="0 0 24 40" className="h-10 w-6 text-accent lg:hidden">
        <motion.path d="M12 0 V34" fill="none" stroke="currentColor" strokeWidth="2" {...draw} />
        <motion.path d="M6 28 L12 35 L18 28" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          initial={{ opacity: 0 }} animate={seen ? { opacity: 1 } : {}} transition={{ delay: 1.2, duration: 0.3 }} />
      </svg>
    </div>
  );
}

function Person({ p, seen, className }: { p: (typeof PEOPLE)[number]; seen: boolean; className: string }) {
  const ok = p.tone === "ok";
  return (
    <motion.div className={`rounded-[22px] border border-border bg-surface p-5 ${className}`}
      initial={{ opacity: 0, y: 24 }} animate={seen ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7, delay: 0.25, ease: EASE }}>
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-full bg-inland text-[15px] font-bold text-accent">{p.name[0]}</span>
        <div>
          <p className="font-bold">{p.name}</p>
          <p className="text-sm text-muted">{p.years}</p>
        </div>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-text-2">{p.work}</p>
      <motion.div className={`mt-4 rounded-2xl px-3.5 py-3 ${ok ? "bg-ok-soft" : "bg-warn-soft"}`}
        initial={{ opacity: 0, scale: 0.94 }} animate={seen ? { opacity: 1, scale: 1 } : {}}
        transition={{ duration: 0.45, delay: 1.35, ease: [0.2, 0.9, 0.3, 1.2] }}>
        <p className={`text-sm font-bold ${ok ? "text-ok" : "text-warn"}`}>{p.verdict}</p>
        <ul className="mt-1.5 flex flex-col gap-1">
          {p.notes.map(([tone, text]) => (
            <li key={text} className="flex items-start gap-1.5 text-[13px] leading-snug text-text-2">
              {tone === "ok" ? <IconCheck size={14} className="mt-0.5 shrink-0 text-ok" /> : <IconAlert size={14} className="mt-0.5 shrink-0 text-warn" />}
              {text}
            </li>
          ))}
        </ul>
      </motion.div>
    </motion.div>
  );
}
