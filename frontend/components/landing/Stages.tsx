"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { IconCheck } from "@/components/icons";
import { EASE } from "./primitives";

// One product, three starting points. The sentence on the left is how Jobreach describes you
// back to yourself on your first day; the list is what changes because of it.
const STAGES = [
  { key: "student", label: "Students", phrase: "students after an internship",
    you: "You're a final-year student looking for backend and full-stack internships.",
    points: ["Internships first, with the stipend floor you set.",
             "Batch-year and CGPA limits in a post are checked before anything is written.",
             "Unpaid onsite posts are skipped, unless you say otherwise."] },
  { key: "graduate", label: "New graduates", phrase: "new graduates after a first job",
    you: "You graduated in 2026 and want frontend roles that ask for 0 to 1 years.",
    points: ["Entry-level roles, matched on what your projects actually show.",
             "Your projects lead the resume, since they are your strongest proof.",
             "A salary floor per year, instead of a monthly stipend."] },
  { key: "experienced", label: "Experienced", phrase: "engineers ready to switch",
    you: "You're a 3-year SDE targeting SDE and AI/ML roles.",
    points: ["Openings matched to your years, from 1 to 3 up to 8 and more.",
             "Your work experience leads, with projects in support.",
             "Notice period and salary floor respected. Large companies included unless you leave them out."] },
];

export default function Stages() {
  const [i, setI] = useState(0);
  const [touched, setTouched] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.5 });
  const reduce = useReducedMotion();

  useEffect(() => {
    if (touched || !inView || reduce) return;
    const t = setInterval(() => setI((x) => (x + 1) % STAGES.length), 4600);
    return () => clearInterval(t);
  }, [touched, inView, reduce]);

  const pick = (n: number) => { setTouched(true); setI((n + STAGES.length) % STAGES.length); };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") pick(i + 1);
    if (e.key === "ArrowLeft") pick(i - 1);
  };
  const s = STAGES[i];

  return (
    <section id="stages" className="px-4 py-24 sm:px-6 sm:py-32">
      <div ref={ref} className="mx-auto max-w-[1320px]">
        <h2 className="text-[34px] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[48px] lg:text-[56px]">
          <span className="block">Built for</span>
          <span className="relative block h-[2.3em] overflow-hidden text-accent lg:h-[1.2em]">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span key={s.key} className="absolute inset-x-0 top-0 block lg:whitespace-nowrap"
                initial={{ y: "105%" }} animate={{ y: "0%" }} exit={{ y: "-105%" }} transition={{ duration: 0.6, ease: EASE }}>
                {s.phrase}.
              </motion.span>
            </AnimatePresence>
          </span>
        </h2>

        <div role="tablist" aria-label="Career stage" onKeyDown={onKey} className="mt-10 inline-flex gap-1 rounded-full bg-sunken p-1 ring-1 ring-border">
          {STAGES.map((x, n) => (
            <button key={x.key} role="tab" aria-selected={n === i} aria-controls="stage-panel" tabIndex={n === i ? 0 : -1}
              onClick={() => pick(n)}
              className={`relative whitespace-nowrap rounded-full px-3.5 py-2 text-[13px] font-semibold transition-colors sm:px-5 sm:text-sm ${n === i ? "text-text" : "text-muted hover:text-text"}`}>
              {n === i && <motion.span layoutId="stage-pill" className="absolute inset-0 rounded-full bg-surface shadow-sm ring-1 ring-border" transition={{ duration: 0.45, ease: EASE }} />}
              <span className="relative">{x.label}</span>
            </button>
          ))}
        </div>

        <div id="stage-panel" role="tabpanel" className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-10">
          <div className="flex min-h-[220px] flex-col justify-between rounded-[26px] bg-inland p-7 ring-1 ring-inland-edge sm:p-9">
            <p className="text-[13px] font-semibold text-muted">How Jobreach describes you on day one</p>
            <AnimatePresence mode="wait" initial={false}>
              <motion.p key={s.key} className="mt-6 text-[26px] font-bold leading-[1.2] tracking-[-0.02em] sm:text-[32px]"
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.45, ease: EASE }}>
                {s.you}
              </motion.p>
            </AnimatePresence>
          </div>
          <div className="flex flex-col justify-center px-1">
            <AnimatePresence mode="wait" initial={false}>
              <motion.ul key={s.key} className="flex flex-col gap-5"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
                {s.points.map((p, k) => (
                  <motion.li key={p} className="flex gap-3.5 text-[18px] leading-snug text-text-2"
                    initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.45, delay: k * 0.08, ease: EASE }}>
                    <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><IconCheck size={15} /></span>
                    {p}
                  </motion.li>
                ))}
              </motion.ul>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}
