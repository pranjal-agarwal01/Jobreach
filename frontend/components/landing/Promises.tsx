"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { IconCheck, IconExternal, IconFile, IconX } from "@/components/icons";
import { Postmark } from "@/components/ui";
import { EASE, Reveal } from "./primitives";

/** Five promises, five cells, one grid: the big one is the one that matters most. */
export default function Promises() {
  return (
    <section id="promises" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-[1320px]">
        <Reveal className="max-w-3xl">
          <h2 className="text-balance text-[34px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[48px]">Built to protect your name.</h2>
          <p className="mt-4 max-w-[56ch] text-[18px] leading-relaxed text-text-2">
            Every letter goes out under your name, to someone who may hire you. These rules are in the code, not in a policy page.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-flow-dense gap-4 md:grid-cols-6">
          <Cell className="relative bg-inland shadow-paper ring-1 ring-inland-edge md:col-span-3 md:row-span-2" delay={0}>
            <div className="airmail-edge absolute inset-x-0 top-0 h-2" />
            <div className="flex h-full flex-col p-7 pt-9 sm:p-9 sm:pt-11">
              <h3 className="text-[28px] font-bold tracking-[-0.025em] sm:text-[34px]">Nothing goes out unless you say so.</h3>
              <p className="mt-3 max-w-[40ch] text-[17px] leading-relaxed text-text-2">
                Jobreach finds, checks, writes and files. You press Send, or turn on Send for me and it sends a few a day,
                in the hours you choose, after you&apos;ve had time to read them. It never submits an application for you,
                and there is no bulk send.
              </p>
              <div className="relative mt-10 flex min-h-[170px] flex-1 items-end">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-[15px] font-semibold text-white dark:text-[#0b1020]">
                    <IconExternal size={17} /> Open in Gmail
                  </span>
                  <span className="rounded-full px-4 py-2.5 text-[15px] font-semibold text-text-2 ring-1 ring-inland-edge">Copy letter</span>
                </div>
                <motion.div className="absolute bottom-6 right-0 size-32 sm:size-36"
                  initial={{ opacity: 0, scale: 1.7 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.8 }}
                  transition={{ duration: 0.5, delay: 0.5, ease: [0.2, 0.9, 0.3, 1.2] }}>
                  <Postmark date={new Date().toISOString()} className="size-full!" />
                </motion.div>
              </div>
            </div>
          </Cell>

          <Cell className="border border-border bg-surface md:col-span-3" delay={0.06}>
            <Body title="Nothing made up"
              text="Every line on your resume comes from your CV, your projects or your GitHub. A number we can't find in what you gave us does not go on the page." />
            <div className="mx-6 mb-6 rounded-2xl bg-sunken p-4 sm:mx-8 sm:mb-8">
              <p className="text-[14px] leading-relaxed text-text-2">
                Moved processing to a Celery worker pool, handling <mark className="rounded bg-ok-soft px-1 font-semibold text-ok">about 60 images per second</mark> on a four-core machine.
              </p>
              <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-muted"><IconFile size={14} /> Found in Rohan_Das_CV.pdf</p>
            </div>
          </Cell>

          <Cell className="bg-sunken ring-1 ring-border md:col-span-3" delay={0.12}>
            <Body title="Only published addresses"
              text="We write to an address only when the company published it for hiring, in the post or on its careers page. We never guess one." />
            <div className="mx-6 mb-6 flex flex-wrap items-center gap-2 sm:mx-8 sm:mb-8">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3.5 py-1.5 text-sm font-semibold ring-1 ring-border">
                <IconCheck size={15} className="text-ok" /> careers@kitebox.example <span className="font-normal text-muted">from the post</span>
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold text-muted ring-1 ring-border">
                <IconX size={15} className="text-bad" /> <s className="decoration-bad/60">riya@kitebox.example</s> <span className="font-normal">guessed</span>
              </span>
            </div>
          </Cell>

          <Cell className="bg-accent-soft md:col-span-3" delay={0.06}>
            <Body title="No LinkedIn scraping"
              text="We never log in to LinkedIn or copy anything from it. A post you paste yourself stays private to you and is never added to the shared pool." />
          </Cell>

          <Cell className="border border-border bg-surface md:col-span-3" delay={0.12}>
            <Body title="Yours to delete"
              text="Your CV, resumes and letters are private to your account. Delete all of it from your profile whenever you like." />
          </Cell>
        </div>
      </div>
    </section>
  );
}

function Cell({ children, className, delay }: { children: ReactNode; className: string; delay: number }) {
  return (
    <motion.div className={`flex flex-col overflow-hidden rounded-[26px] ${className}`}
      initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.75, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

function Body({ title, text }: { title: string; text: string }) {
  return (
    <div className="p-6 sm:p-8">
      <h3 className="text-[22px] font-bold tracking-[-0.02em]">{title}</h3>
      <p className="mt-2 max-w-[52ch] text-[16px] leading-relaxed text-text-2">{text}</p>
    </div>
  );
}
