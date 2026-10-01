"use client";

import { MotionValue, motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { Reveal } from "./primitives";

// The position, read as you scroll: each word inks in as it passes, so the sentence is read
// at reading pace rather than skimmed.
const STATEMENT =
  "Most job tools help you apply to more places. Jobreach helps you write to the right person while the opening is still fresh, with a resume made for that one job.";

// From the job search Jobreach grew out of (PRODUCT-SPEC.md, section 2.1).
const LESSONS = [
  ["Fresh posts get read.", "The fastest replies came to posts only hours old. Posts three days old mostly got polite acknowledgements."],
  ["Write to the company.", "Every reply came from a post by a founder, someone on the team or the company itself. None came through a recruiter or a reposting page."],
  ["Small companies answer.", "Replies came from startups and small companies of roughly 10 to 200 people. None came from larger ones."],
] as const;

export default function Lessons() {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.45"] });
  const words = STATEMENT.split(" ");
  return (
    <section id="why" className="px-4 py-28 sm:px-6 sm:py-36">
      <div className="mx-auto max-w-[1100px]">
        <h2 className="sr-only">Why Jobreach</h2>
        <p ref={ref} className="text-[30px] font-bold leading-[1.16] tracking-[-0.025em] sm:text-[44px] lg:text-[54px]">
          {words.map((w, i) => (
            <Word key={i} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]}
              fresh={w.startsWith("fresh")}>{w}</Word>
          ))}
        </p>

        <Reveal className="mt-24 sm:mt-32">
          <p className="max-w-xl text-[17px] text-text-2">Jobreach grew out of a real job search. It taught us three things.</p>
        </Reveal>
        <dl className="mt-8">
          {LESSONS.map(([k, v], i) => (
            <Reveal key={k} delay={i * 0.08}>
              <div className="grid gap-2 border-t border-border py-7 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] sm:gap-10">
                <dt className="text-[24px] font-bold tracking-[-0.02em] sm:text-[28px]">{k}</dt>
                <dd className="max-w-[52ch] text-[17px] leading-relaxed text-text-2 sm:pt-1.5">{v}</dd>
              </div>
            </Reveal>
          ))}
        </dl>
      </div>
    </section>
  );
}

function Word({ children, progress, range, fresh }:
  { children: string; progress: MotionValue<number>; range: [number, number]; fresh: boolean }) {
  const opacity = useTransform(progress, range, [0.14, 1]);
  return (
    <>
      <motion.span style={{ opacity }} className={fresh ? "text-post" : undefined}>{children}</motion.span>{" "}
    </>
  );
}
