"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-surface hover:opacity-90",
  secondary: "border border-border bg-surface text-text hover:bg-accent-soft",
  ghost: "text-muted hover:text-text hover:bg-accent-soft",
  danger: "border border-bad text-bad hover:bg-bad-soft",
};

export function Button({ variant = "primary", busy, className = "", children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition
        disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    >
      {busy && <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className = "" }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-border bg-surface p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

type Tone = "neutral" | "ok" | "warn" | "bad" | "accent";
const TONES: Record<Tone, string> = {
  neutral: "bg-bg text-muted border-border",
  ok: "bg-ok-soft text-ok border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  bad: "bg-bad-soft text-bad border-transparent",
  accent: "bg-accent-soft text-accent border-transparent",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "w-full rounded-md border border-border px-2.5 py-1.5 text-sm outline-none focus:border-accent";

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

export function hoursLabel(h: number | null | undefined): string {
  if (h === null || h === undefined) return "age unknown";
  if (h < 1) return `${Math.round(h * 60)}m`;
  if (h < 48) return `${Math.round(h)}h`;
  return `${Math.round(h / 24)}d`;
}

export const STATUS_TONE: Record<string, Tone> = {
  drafted: "accent", needs_review: "warn", sent: "neutral", replied: "ok", interview: "ok",
  assignment: "ok", rejected: "bad", bounced: "bad", closed: "neutral",
};
