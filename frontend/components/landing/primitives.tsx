"use client";

import Link from "next/link";
import { MotionConfig, motion } from "motion/react";
import type { ReactNode } from "react";
import { IconChevronRight } from "@/components/icons";

/** The landing page's one easing: fast out, long settle. */
export const EASE = [0.16, 1, 0.3, 1] as const;

/** Respect the visitor's reduced-motion setting everywhere below: Motion then skips
 *  transform and layout animation and keeps only fades. */
export function MotionRoot({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user" transition={{ ease: EASE }}>{children}</MotionConfig>;
}

/** Enter on scroll: a short rise and fade, once. */
export function Reveal({ children, delay = 0, className = "", y = 28 }:
  { children: ReactNode; delay?: number; className?: string; y?: number }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.8, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

/** The one sign-up action, labelled the same everywhere on the page. */
export function GetStarted({ size = "md", className = "" }: { size?: "sm" | "md" | "lg"; className?: string }) {
  const pad = size === "lg" ? "py-2 pl-7 pr-2 text-[17px]" : size === "sm" ? "py-1 pl-4 pr-1 text-sm" : "py-1.5 pl-5 pr-1.5 text-[15px]";
  const dot = size === "lg" ? "size-11" : size === "sm" ? "size-7" : "size-9";
  return (
    <Link href="/login?mode=signup"
      className={`group inline-flex shrink-0 items-center gap-3 whitespace-nowrap rounded-full bg-accent font-semibold text-white shadow-[0_1px_0_rgb(255_255_255/0.2)_inset,0_10px_24px_-12px_rgb(40_70_196/0.7)] transition-[transform,background-color] duration-300 hover:bg-accent-strong active:scale-[0.98] dark:text-[#0b1020] ${pad} ${className}`}>
      Get started
      <span className={`grid place-items-center rounded-full bg-white/15 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-0.5 dark:bg-black/10 ${dot}`}>
        <IconChevronRight size={size === "sm" ? 15 : 18} strokeWidth={2.2} />
      </span>
    </Link>
  );
}
