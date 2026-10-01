"use client";

import Image from "next/image";
import { AnimatePresence, motion, useInView } from "motion/react";
import { ReactNode, useEffect, useRef, useState } from "react";
import { IconCheck, IconFile, IconGithub, IconSend } from "@/components/icons";
import { Freshness, Monogram, Postmark } from "@/components/ui";
import { EASE, Reveal } from "./primitives";

const STEPS = [
  { title: "Tell us once",
    body: "Upload your CV, add your GitHub and the roles you want. One form, a few minutes. No interview and no boxes to tick." },
  { title: "Get a resume for every role",
    body: "Jobreach builds one strong one-page resume for each kind of role you want, using only what you gave it. Change anything before you start." },
  { title: "See what fits you",
    body: "Openings are checked and scored against your own work: what matches, what is missing, and how fresh the post is." },
  { title: "Open one, read it, press Send",
    body: "The letter and a resume made for that job are ready. Send it from your own inbox, then log the reply when it comes." },
];

const VISUALS = [TellVisual, BaselinesVisual, MatchesVisual, SendVisual];

/** Scrollytelling: on wide screens the desk stays pinned while the steps scroll past it;
 *  on phones each step carries its own picture. */
export default function HowItWorks() {
  const [active, setActive] = useState(0);
  const Visual = VISUALS[active];
  return (
    <section id="how" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-[1320px]">
        <Reveal className="max-w-3xl">
          <h2 className="text-balance text-[34px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[48px]">Tell us once. We do the legwork.</h2>
        </Reveal>

        <div className="mt-14 grid gap-10 lg:mt-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-20">
          <div className="hidden lg:block">
            <div className="sticky top-24 flex h-[min(640px,calc(100dvh-8rem))] items-center justify-center overflow-hidden rounded-[28px] bg-inland/70 p-8 ring-1 ring-inland-edge">
              <AnimatePresence mode="wait">
                <motion.div key={active} className="w-full"
                  initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -16, scale: 0.98 }} transition={{ duration: 0.45, ease: EASE }}>
                  <Visual />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <ol className="flex flex-col">
            {STEPS.map((s, i) => (
              <Step key={s.title} index={i} active={active === i} onActive={setActive} title={s.title} body={s.body} />
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function Step({ index, active, onActive, title, body }:
  { index: number; active: boolean; onActive: (i: number) => void; title: string; body: string }) {
  const ref = useRef<HTMLLIElement>(null);
  const centred = useInView(ref, { margin: "-45% 0px -45% 0px" });
  useEffect(() => { if (centred) onActive(index); }, [centred, index, onActive]);
  const Visual = VISUALS[index];
  return (
    <li ref={ref} className="flex flex-col justify-center py-8 lg:min-h-[78vh] lg:py-0">
      <div className="mb-8 overflow-hidden rounded-[24px] bg-inland/70 p-5 ring-1 ring-inland-edge sm:p-8 lg:hidden">
        <WhenSeen><Visual /></WhenSeen>
      </div>
      <div className={`border-l-2 pl-6 transition-colors duration-500 lg:pl-8 ${active ? "border-accent" : "border-border lg:border-transparent"}`}>
        <h3 className={`text-[26px] font-bold tracking-[-0.025em] transition-colors duration-500 sm:text-[32px] ${active ? "text-text" : "text-text lg:text-muted"}`}>{title}</h3>
        <p className={`mt-3 max-w-[46ch] text-[17px] leading-relaxed transition-colors duration-500 sm:text-[18px] ${active ? "text-text-2" : "text-text-2 lg:text-muted"}`}>{body}</p>
      </div>
    </li>
  );
}

/** Mount a picture only once it scrolls into view, so its entrance plays where it is seen. */
function WhenSeen({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.3 });
  return <div ref={ref} className="min-h-[300px]">{seen && children}</div>;
}

const rise = (delay: number) => ({
  initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.6, delay, ease: EASE },
});

function Label({ children }: { children: ReactNode }) {
  return <p className="mb-2 text-[13px] font-semibold text-muted">{children}</p>;
}

// ------------------------------------------------------------------ the four pictures

function TellVisual() {
  return (
    <div className="paper mx-auto w-full max-w-[460px] p-6">
      <Label>Your CV</Label>
      <motion.div {...rise(0.1)} className="flex items-center gap-3 rounded-xl border border-dashed border-border-strong bg-sunken/60 p-3.5">
        <span className="grid size-10 place-items-center rounded-lg bg-surface text-accent ring-1 ring-border"><IconFile size={20} /></span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">Rohan_Das_CV.pdf</p>
          <p className="text-xs text-muted">Read: 4 projects, education, skills</p>
        </div>
        <IconCheck size={18} className="ml-auto shrink-0 text-ok" />
      </motion.div>

      <div className="mt-5"><Label>GitHub</Label></div>
      <motion.div {...rise(0.3)} className="flex items-center gap-2.5 rounded-xl border border-border-strong px-3.5 py-2.5 text-sm">
        <IconGithub size={17} className="text-muted" /> github.com/rohan-das-example
        <span className="ml-auto text-xs font-semibold text-ok">Repositories read</span>
      </motion.div>

      <div className="mt-5"><Label>Roles you want</Label></div>
      <div className="flex flex-wrap gap-2">
        {["Full stack", "Frontend", "Backend"].map((r, i) => (
          <motion.span key={r} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.55 + i * 0.12, ease: EASE }}
            className="rounded-full bg-accent-soft px-3.5 py-1.5 text-sm font-semibold text-accent">{r}</motion.span>
        ))}
      </div>

      <div className="mt-5"><Label>Where you are</Label></div>
      <motion.div {...rise(0.9)} className="grid grid-cols-3 rounded-xl bg-sunken p-1 text-center text-[13px] font-semibold">
        <span className="rounded-lg bg-surface py-1.5 shadow-sm">Student</span>
        <span className="py-1.5 text-muted">New graduate</span>
        <span className="py-1.5 text-muted">Experienced</span>
      </motion.div>
    </div>
  );
}

const BASELINES = [
  { label: "Full stack", src: "/landing/resume-rohan-fullstack.png", left: "0%", top: "7%", rotate: "-6deg" },
  { label: "Frontend", src: "/landing/resume-rohan-frontend.png", left: "27%", top: "0%", rotate: "0deg" },
  { label: "Backend", src: "/landing/resume-rohan-backend.png", left: "54%", top: "7%", rotate: "6deg" },
];

function BaselinesVisual() {
  return (
    <div className="mx-auto w-full max-w-[540px]">
      <div className="relative aspect-[540/400]">
        {BASELINES.map((b, i) => (
          <div key={b.label} className="absolute w-[46%]" style={{ left: b.left, top: b.top, rotate: b.rotate, zIndex: i === 1 ? 2 : 1 }}>
            <motion.div className="overflow-hidden rounded-[3px] border border-border bg-white shadow-paper"
              initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.1 + i * 0.14, ease: EASE }}>
              <Image src={b.src} alt={`Rohan's ${b.label} resume`} width={910} height={1287} sizes="250px" className="h-auto w-full" />
            </motion.div>
          </div>
        ))}
      </div>
      <ul className="mt-5 grid grid-cols-3 text-center text-[13px] font-semibold">
        {BASELINES.map((b, i) => (
          <motion.li key={b.label} {...rise(0.6 + i * 0.1)}>
            {b.label}
            <span className="mt-0.5 flex items-center justify-center gap-0.5 text-xs text-ok"><IconCheck size={13} /> One page</span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

const MATCHES = [
  { group: "Strong", company: "Kitebox Labs", role: "Backend Developer Intern", hours: 2, why: "FastAPI and Redis, used in PixelForge" },
  { group: "Strong", company: "Pinewheel Health", role: "Full-stack Developer Intern", hours: 9, why: "Next.js and PostgreSQL, used in TutorLink" },
  { group: "Good", company: "Ledgerleaf", role: "Frontend Engineer Intern", hours: 5, why: "React and TypeScript across three projects" },
  { group: "With gaps", company: "Corvid Systems", role: "Platform Engineer Intern", hours: 20, why: "Asks for Kubernetes, not in your projects yet" },
];
const GROUP_TONE: Record<string, string> = { Strong: "text-ok", Good: "text-accent", "With gaps": "text-warn" };

function MatchesVisual() {
  return (
    <div className="paper mx-auto w-full max-w-[480px] p-5">
      <p className="text-[15px] font-semibold leading-snug">You&apos;re a final-year student looking for backend and full-stack internships.</p>
      <ul className="mt-4 flex flex-col gap-2">
        {MATCHES.map((m, i) => (
          <motion.li key={m.company} {...rise(0.15 + i * 0.12)} className="rounded-xl border border-border bg-surface p-3">
            <div className="flex items-center gap-3">
              <Monogram name={m.company} size={34} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{m.role}</p>
                <p className="truncate text-xs text-muted">{m.company}</p>
              </div>
              <span className={`shrink-0 text-xs font-bold ${GROUP_TONE[m.group]}`}>{m.group}</span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 pl-[46px]">
              <p className="truncate text-xs text-text-2">{m.why}</p>
              <Freshness hours={m.hours} compact />
            </div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

function SendVisual() {
  return (
    <div className="relative mx-auto h-[400px] w-full max-w-[500px] sm:h-[440px]">
      <motion.div className="absolute right-0 top-0 w-[46%] rotate-[4deg]" {...rise(0.05)}>
        <div className="overflow-hidden rounded-[3px] border border-border bg-white shadow-paper">
          <Image src="/landing/resume-rohan-backend.png" alt="" width={910} height={1287} sizes="230px" className="h-auto w-full" />
        </div>
      </motion.div>
      <motion.article className="paper-inland absolute bottom-0 left-0 w-[86%] overflow-hidden" {...rise(0.2)}>
        <div className="airmail-edge h-2" />
        <motion.div className="absolute right-4 top-5 size-20" initial={{ opacity: 0, scale: 1.7 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.45, delay: 1.1, ease: [0.2, 0.9, 0.3, 1.2] }}>
          <Postmark date={new Date().toISOString()} className="size-full!" />
        </motion.div>
        <div className="px-6 pb-5 pt-4">
          <p className="pr-24 text-xs text-muted">To careers@kitebox.example</p>
          <p className="mt-1 pr-24 text-sm font-semibold">Backend Developer Intern: Rohan Das</p>
          <div className="mt-3 font-letter text-[14px] leading-[1.65] text-text-2">
            <p className="text-text">Hi Riya,</p>
            <p className="mt-1.5">I saw your post for the Backend Developer Intern role this morning. I built PixelForge, an image API in FastAPI that handles about 60 images a second&hellip;</p>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-inland-edge bg-surface/70 px-2.5 py-1 text-xs font-semibold text-text-2">
              <IconFile size={14} /> resume_Rohan_Das.pdf
            </span>
            <motion.span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-1.5 text-xs font-semibold text-white dark:text-[#0b1020]"
              animate={{ scale: [1, 1, 0.88, 1] }} transition={{ duration: 0.5, times: [0, 0.6, 0.8, 1], delay: 0.6 }}>
              <IconSend size={14} /> Send
            </motion.span>
          </div>
        </div>
      </motion.article>
    </div>
  );
}
