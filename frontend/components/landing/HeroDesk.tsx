"use client";

import Image from "next/image";
import { AnimatePresence, motion, stagger, useAnimate, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { IconFile, IconSend } from "@/components/icons";
import { Freshness, Postmark } from "@/components/ui";
import { EASE } from "./primitives";

// The whole product in one short scene: a fresh post, a resume made for it, a letter that
// writes itself from the student's own facts, and the student pressing Send. It plays once;
// with reduced motion it shows the finished desk.
const CAPTIONS = [
  "Riya, a founder, posts an opening. It is two hours old.",
  "Jobreach makes a one-page resume for this job from Rohan's own CV.",
  "It writes the letter. Every claim in it is Rohan's.",
  "Rohan reads it and presses Send.",
];

const hidden = { opacity: 0 };
const unwritten = { clipPath: "inset(0 100% 0 0)" };
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Set the desk to blank (before a run) or finished (reduced motion) at once. Written to the
 *  DOM directly: a zero-length Motion animation never settles its promise. */
function paint(root: Element | null, finished: boolean) {
  root?.querySelectorAll<HTMLElement>("[data-a]").forEach((el) => { el.style.opacity = finished ? "1" : "0"; });
  root?.querySelectorAll<HTMLElement>("[data-line]").forEach((el) => { el.style.clipPath = finished ? "none" : "inset(0 100% 0 0)"; });
}

export default function HeroDesk() {
  const [scope, animate] = useAnimate();
  const reduce = useReducedMotion();
  const [stage, setStage] = useState(-1);
  const [done, setDone] = useState(false);
  const run = useRef(0);

  const play = useCallback(async () => {
    const id = ++run.current;
    const live = () => run.current === id;
    setDone(false);
    paint(scope.current, false);
    setStage(0);
    await animate("[data-post]", { opacity: [0, 1], y: [26, 0] }, { duration: 0.7, ease: EASE });
    await wait(700);
    if (!live()) return;
    setStage(1);
    await animate("[data-resume]", { opacity: [0, 1], x: [-70, 0], y: [14, 0] }, { duration: 0.85, ease: EASE });
    await wait(650);
    if (!live()) return;
    setStage(2);
    await animate("[data-letter]", { opacity: [0, 1], y: [44, 0] }, { duration: 0.65, ease: EASE });
    await animate("[data-line]", { clipPath: ["inset(0 100% 0 0)", "inset(0 0% 0 0)"] },
      { duration: 0.55, delay: stagger(0.3), ease: EASE });
    await wait(600);
    if (!live()) return;
    setStage(3);
    await animate("[data-send]", { scale: [1, 0.88, 1] }, { duration: 0.32, ease: EASE });
    await animate("[data-stamp]", { opacity: [0, 1], scale: [1.7, 1] }, { duration: 0.45, ease: [0.2, 0.9, 0.3, 1.2] });
    if (live()) setDone(true);
  }, [animate, scope]);

  useEffect(() => {
    if (reduce === null) return;
    if (reduce) {
      paint(scope.current, true);
      return;
    }
    const t = setTimeout(play, 450);
    const token = run; // a run counter, not a DOM node: bumping it cancels the scene in flight
    return () => { clearTimeout(t); token.current++; };
  }, [reduce, play, scope]);

  const shown = reduce ? 3 : stage;

  return (
    <div ref={scope} className="relative mx-auto w-full max-w-[600px] [container-type:inline-size]">
      <div aria-hidden="true" className="relative aspect-[1/0.97]">
        {/* The post, as the founder wrote it. */}
        <div className="absolute left-0 top-[1%] w-[57%] -rotate-[2.5deg]">
          <div data-a data-post style={hidden} className="paper p-[3.6cqw]">
            <div className="flex items-center gap-[2cqw]">
              <span className="grid size-[7.4cqw] shrink-0 place-items-center rounded-[1.6cqw] bg-[#13703f] text-[3cqw] font-bold text-white">KL</span>
              <div className="min-w-0 leading-tight">
                <p className="text-[max(9px,2.5cqw)] font-bold">Riya Sen</p>
                <p className="truncate text-[max(8px,2.1cqw)] text-muted">Founder at Kitebox Labs</p>
              </div>
              <span className="ml-auto"><Freshness hours={2} compact /></span>
            </div>
            <p className="mt-[2.6cqw] text-[max(8.5px,2.3cqw)] leading-[1.55] text-text-2">
              We&apos;re hiring a Backend Developer Intern for our upload pipeline. Python, FastAPI and Redis.
              Remote, six months.
            </p>
            <p className="mt-[1.6cqw] text-[max(8.5px,2.3cqw)] leading-[1.55] text-text-2">
              Send your resume to <span className="rounded bg-accent-soft px-1 font-semibold text-accent">careers@kitebox.example</span>
            </p>
          </div>
        </div>

        {/* The resume Jobreach made for this post: a real render of the made-up student's page. */}
        <div className="absolute right-0 top-[7%] w-[40%] rotate-[3deg]">
          <div data-a data-resume style={hidden} className="overflow-hidden rounded-[3px] border border-border bg-white shadow-paper">
            <Image src="/landing/resume-rohan-backend.png" alt="" width={910} height={1287}
              sizes="(min-width: 1024px) 260px, 43vw" fetchPriority="high" className="h-auto w-full" />
          </div>
        </div>

        {/* The letter. */}
        <div className="absolute bottom-0 left-[5%] w-[78%] -rotate-[0.6deg]">
          <div data-a data-letter style={hidden} className="paper-inland relative overflow-hidden">
            <div className="airmail-edge h-[1.3cqw] min-h-1.5" />
            <div data-a data-stamp style={hidden} className="absolute right-[2.6cqw] top-[3cqw] size-[16cqw]">
              <Postmark date={new Date().toISOString()} className="size-full!" />
            </div>
            <div className="px-[4.4cqw] pb-[3.4cqw] pt-[2.8cqw]">
              <p data-line style={unwritten} className="pr-[17cqw] text-[max(8px,2.1cqw)] text-muted">To careers@kitebox.example</p>
              <p data-line style={unwritten} className="mt-[0.8cqw] pr-[17cqw] text-[max(8.5px,2.35cqw)] font-semibold">
                Backend Developer Intern: Rohan Das
              </p>
              <div className="mt-[2.2cqw] font-letter text-[max(8.5px,2.4cqw)] leading-[1.6] text-text-2">
                <p data-line style={unwritten} className="text-text">Hi Riya,</p>
                <p data-line style={unwritten} className="mt-[1cqw]">
                  I saw your post for the Backend Developer Intern role this morning. I built PixelForge, an image API
                  in FastAPI that handles about 60 images a second with Celery and Redis.
                </p>
                <p data-line style={unwritten} className="mt-[1cqw]">My resume is attached. I can start right away.</p>
              </div>
              <div data-line style={unwritten} className="mt-[2.4cqw] flex items-center gap-[2cqw]">
                <span className="inline-flex min-w-0 items-center gap-[1cqw] rounded-[1.2cqw] border border-inland-edge bg-surface/70 px-[1.6cqw] py-[0.8cqw] text-[max(8px,2cqw)] font-semibold text-text-2">
                  <IconFile className="size-[2.6cqw] shrink-0" /> <span className="truncate">resume_Rohan_Das.pdf</span>
                </span>
                <span data-send className="ml-auto inline-flex items-center gap-[1cqw] rounded-full bg-accent px-[2.6cqw] py-[1cqw] text-[max(8.5px,2.2cqw)] font-semibold text-white dark:text-[#0b1020]">
                  <IconSend className="size-[2.4cqw]" /> Send
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* What is happening, in words: also the only part a screen reader needs. */}
      <div className="mt-7 flex min-h-12 flex-wrap items-start gap-x-4 gap-y-2 sm:flex-nowrap">
        <div className="mt-2 flex shrink-0 gap-1.5" aria-hidden="true">
          {CAPTIONS.map((_, i) => (
            <span key={i} className={`h-1 w-6 rounded-full transition-colors duration-500 ${i <= shown ? "bg-accent" : "bg-border-strong/60"}`} />
          ))}
        </div>
        <div className="relative order-last min-w-0 basis-full sm:order-none sm:basis-auto sm:flex-1" aria-live="polite">
          <AnimatePresence mode="wait" initial={false}>
            <motion.p key={shown} className="text-[15px] leading-snug text-text-2"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3, ease: EASE }}>
              {shown >= 0 ? CAPTIONS[shown] : " "}
            </motion.p>
          </AnimatePresence>
        </div>
        {done && (
          <button type="button" onClick={play} className="-mt-1 ml-auto shrink-0 rounded-full px-3 py-1 text-sm font-semibold text-accent hover:bg-accent-soft">
            Replay
          </button>
        )}
      </div>
    </div>
  );
}
