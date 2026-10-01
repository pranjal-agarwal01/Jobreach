"use client";

import { AnimatePresence, LayoutGroup, motion, useInView, useReducedMotion } from "motion/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { IconCheck } from "@/components/icons";
import { Freshness, Monogram } from "@/components/ui";
import { OPENINGS, PROJECTS } from "./content";
import { EASE, Reveal } from "./primitives";

const CYCLE_MS = 5200;

/** The same person's resume, re-cut for three openings. Lines move, they are never rewritten:
 *  the reorder animation is the argument. Cycles on its own until the visitor picks one. */
export default function TailorBench() {
  const [index, setIndex] = useState(0);
  const [touched, setTouched] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.35 });
  const reduce = useReducedMotion();
  const cycling = !touched && inView && !reduce;

  useEffect(() => {
    if (!cycling) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % OPENINGS.length), CYCLE_MS);
    return () => clearInterval(t);
  }, [cycling]);

  const o = OPENINGS[index];
  const pick = (i: number) => { setTouched(true); setIndex(i); };

  return (
    <section id="tailor" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-[1320px]">
        <Reveal className="max-w-3xl">
          <h2 className="text-balance text-[34px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[48px]">A different resume for every opening.</h2>
          <p className="mt-4 max-w-[58ch] text-[18px] leading-relaxed text-text-2">
            Same person, same facts. Jobreach starts from the right resume, then reorders and trims your own lines
            to fit the job. It adds nothing.
          </p>
        </Reveal>

        <Reveal className="mt-12">
          <div ref={ref} className="rounded-[30px] bg-sunken/80 p-2 ring-1 ring-border">
            <div className="rounded-[24px] bg-surface p-3 sm:p-5">
              <div role="tablist" aria-label="Openings" className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
                {OPENINGS.map((x, i) => (
                  <button key={x.id} role="tab" aria-selected={i === index} aria-controls="tailored-resume" onClick={() => pick(i)}
                    className={`relative flex min-w-[240px] flex-1 items-center gap-3 overflow-hidden rounded-2xl px-3.5 py-3 text-left transition-colors ${i === index ? "bg-inland ring-1 ring-inland-edge" : "hover:bg-sunken"}`}>
                    <Monogram name={x.company} size={36} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold">{x.role}</span>
                      <span className="block truncate text-xs text-muted">{x.company}</span>
                    </span>
                    <Freshness hours={x.hoursOld} compact />
                    {i === index && cycling && (
                      <motion.span key={`${index}-bar`} aria-hidden="true" className="absolute inset-x-3 bottom-1 h-0.5 origin-left rounded-full bg-accent/60"
                        initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: CYCLE_MS / 1000, ease: "linear" }} />
                    )}
                  </button>
                ))}
              </div>

              <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] lg:gap-8">
                <MiniResume key="resume" opening={o} />
                <aside className="flex flex-col gap-6 px-1 pb-2 lg:pt-3">
                  <div>
                    <p className="text-[13px] font-semibold text-muted">The post asks for</p>
                    <ul className="mt-2.5 flex flex-wrap gap-2">
                      <AnimatePresence mode="popLayout" initial={false}>
                        {o.asks.map((a) => (
                          <motion.li key={o.id + a} layout initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.85 }} transition={{ duration: 0.35, ease: EASE }}
                            className="inline-flex items-center gap-1 rounded-full bg-ok-soft px-3 py-1 text-sm font-semibold capitalize text-ok">
                            <IconCheck size={14} /> {a}
                          </motion.li>
                        ))}
                      </AnimatePresence>
                    </ul>
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-muted">What changed for this job</p>
                    <ul className="mt-3 flex flex-col gap-2.5">
                      {o.changes.map((c, k) => (
                        <motion.li key={o.id + k} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.45, delay: 0.1 + k * 0.07, ease: EASE }}
                          className="flex gap-2.5 text-[15px] leading-snug text-text-2">
                          <span aria-hidden="true" className="mt-[10px] h-[1.5px] w-3 shrink-0 bg-accent" />{c}
                        </motion.li>
                      ))}
                    </ul>
                  </div>
                  <p className="mt-auto flex items-start gap-2 rounded-2xl bg-inland px-4 py-3 text-sm leading-snug text-text-2">
                    <IconCheck size={17} className="mt-px shrink-0 text-accent" />
                    Nothing new was written. Every line is Rohan&apos;s own, from the CV he uploaded.
                  </p>
                </aside>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function MiniResume({ opening: o }: { opening: (typeof OPENINGS)[number] }) {
  return (
    <article id="tailored-resume" role="tabpanel" aria-label={`Rohan's resume for ${o.role} at ${o.company}`}
      className="paper min-h-[600px] px-5 py-6 sm:min-h-[560px] sm:px-8 sm:py-7">
      <p className="text-[22px] font-extrabold tracking-[-0.01em] text-accent-strong sm:text-[26px]">ROHAN DAS</p>
      <div className="relative overflow-hidden">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.p key={o.titleLine} className="text-[13px] text-muted sm:text-sm"
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -14 }} transition={{ duration: 0.4, ease: EASE }}>
            {o.titleLine}
          </motion.p>
        </AnimatePresence>
      </div>
      <h3 className="mt-4 border-b border-accent-strong/40 pb-1 text-[12px] font-bold text-accent-strong">PROJECTS</h3>
      <LayoutGroup>
        <div className="mt-2">
          <AnimatePresence mode="popLayout" initial={false}>
            {o.items.map((it) => {
              const p = PROJECTS[it.project];
              return (
                <motion.section key={p.id} layout="position" className="py-2"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.2 } }}
                  transition={{ layout: { duration: 0.6, ease: EASE }, opacity: { duration: 0.35 } }}>
                  <p className="text-[14px] font-bold">{p.name} <span className="font-semibold text-text-2">{p.tagline}</span></p>
                  <p className="text-[12px] text-muted"><span className="font-semibold">Stack:</span> <Marked text={p.stack} asks={o.asks} /></p>
                  <ul className="mt-1.5 flex flex-col gap-1">
                    <AnimatePresence mode="popLayout" initial={false}>
                      {it.bullets.map((bid) => {
                        const b = p.bullets.find((x) => x.id === bid)!;
                        return (
                          <motion.li key={bid} layout="position" className="relative pl-3.5 text-[12.5px] leading-[1.5] text-text-2"
                            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}
                            transition={{ layout: { duration: 0.6, ease: EASE }, opacity: { duration: 0.35, delay: 0.15 } }}>
                            <span aria-hidden="true" className="absolute left-0 top-[0.6em] size-1 rounded-full bg-text-2" />
                            <Marked text={b.text} asks={o.asks} />
                          </motion.li>
                        );
                      })}
                    </AnimatePresence>
                  </ul>
                </motion.section>
              );
            })}
          </AnimatePresence>
        </div>
        <motion.div layout="position" transition={{ layout: { duration: 0.6, ease: EASE } }}>
          <h3 className="mt-3 border-b border-accent-strong/40 pb-1 text-[12px] font-bold text-accent-strong">SKILLS</h3>
          <p className="mt-2 text-[12.5px] leading-relaxed text-text-2">
            {o.skills.map((s, i) => (
              <Fragment key={s}>
                {i > 0 && ", "}
                <span className={o.asks.some((a) => a.toLowerCase() === s.toLowerCase()) ? "font-semibold text-accent" : undefined}>{s}</span>
              </Fragment>
            ))}
          </p>
        </motion.div>
      </LayoutGroup>
    </article>
  );
}

/** Underline the words the post asked for, wherever they already appear in his own lines. */
function Marked({ text, asks }: { text: string; asks: string[] }) {
  const rx = new RegExp(`(${asks.map((a) => a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(rx).map((part, i) =>
        i % 2 === 1
          ? <mark key={i} className="bg-transparent font-semibold text-accent underline decoration-accent/40 underline-offset-[3px]">{part}</mark>
          : <Fragment key={i}>{part}</Fragment>)}
    </>
  );
}
