"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-strong dark:text-[#0b1020] shadow-[0_1px_0_rgb(255_255_255/0.15)_inset]",
  secondary: "border border-border-strong bg-surface text-text hover:border-accent hover:text-accent",
  ghost: "text-text-2 hover:bg-sunken hover:text-text",
  danger: "border border-bad/40 text-bad hover:bg-bad-soft",
};

export function Button({ variant = "primary", busy, className = "", children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-[10px] px-3.5 py-1.5 text-sm font-semibold
        transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    >
      {busy && <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}

/** A panel on the desk. Paper (letters, resumes) uses the .paper class instead. */
export function Card({ title, actions, children, className = "", id }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={`rounded-2xl border border-border bg-surface p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[28px] font-bold leading-tight tracking-[-0.02em] sm:text-[32px]">{title}</h1>
        {sub && <p className="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

type Tone = "neutral" | "ok" | "warn" | "bad" | "accent" | "post";
const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-text-2",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  accent: "bg-accent-soft text-accent",
  post: "bg-post-soft text-post",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-semibold text-text">{label}</span>
      {children}
      {hint && <span className="text-[13px] leading-snug text-muted">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "w-full rounded-[10px] border border-border-strong bg-surface px-3 py-2 text-[15px] outline-none transition-colors " +
  "placeholder:text-muted/70 hover:border-muted focus:border-accent focus:ring-4 focus:ring-accent/15";

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="rounded-[10px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad">{error}</p>;
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <p className="max-w-md text-[15px] leading-relaxed text-muted">{children}</p>
      {action}
    </div>
  );
}

// ------------------------------------------------------------------ time

export function hoursLabel(h: number | null | undefined): string {
  if (h === null || h === undefined) return "age unknown";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}m`;
  if (h < 48) return `${Math.round(h)}h`;
  return `${Math.round(h / 24)}d`;
}

const dayFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });

/** "Today", "Yesterday", "Tomorrow" or "1 Oct". */
export function fmtDay(iso: string | Date): string {
  const d = new Date(iso);
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(d) - start(new Date())) / 86400000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  return dayFmt.format(d);
}
export const fmtWhen = (iso: string | Date) => `${fmtDay(iso)}, ${timeFmt.format(new Date(iso))}`;
/** fmtDay for mid-sentence use: "today", "yesterday", but "29 Sept" keeps its capital. */
export function fmtDayInline(iso: string | Date): string {
  const d = fmtDay(iso);
  return /^(Today|Yesterday|Tomorrow)$/.test(d) ? d.toLowerCase() : d;
}

// ------------------------------------------------------------------ correspondence

/** How fresh the post was when the letter was drafted. Founders answer fresh posts: under
 *  6 hours is urgent (postal red), the meter empties over the 72-hour ceiling. */
export function Freshness({ hours, compact = false }: { hours: number | null | undefined; compact?: boolean }) {
  if (hours === null || hours === undefined) return <span className="text-xs text-muted">age unknown</span>;
  const left = Math.max(0.06, 1 - hours / 72);
  const tone = hours < 6 ? "bg-post" : hours < 24 ? "bg-accent" : "bg-muted/60";
  const text = hours < 6 ? "text-post" : hours < 24 ? "text-accent" : "text-muted";
  return (
    <span className="inline-flex items-center gap-2" title={`The post was ${hoursLabel(hours)} old when this was drafted`}>
      <span className={`relative h-1.5 overflow-hidden rounded-full bg-sunken ${compact ? "w-10" : "w-16"}`}>
        <span className={`absolute inset-y-0 left-0 rounded-full ${tone}`} style={{ width: `${left * 100}%` }} />
      </span>
      <span className={`text-xs font-semibold tabular-nums ${text}`}>{hoursLabel(hours)} old</span>
    </span>
  );
}

const MONO_TINTS = ["#2846c4", "#13703f", "#935700", "#7a3fb8", "#0f6f86", "#b8261c"];

/** A company's monogram, like a letterhead initial. */
export function Monogram({ name, size = 40 }: { name: string; size?: number }) {
  const letters = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?";
  const tint = MONO_TINTS[[...name].reduce((n, c) => n + c.charCodeAt(0), 0) % MONO_TINTS.length];
  return (
    <span className="grid shrink-0 place-items-center rounded-[10px] font-bold tracking-tight text-white"
      style={{ width: size, height: size, background: tint, fontSize: size * 0.38 }} aria-hidden="true">
      {letters}
    </span>
  );
}

/** The postmark a letter gets once the student has sent it. */
export function Postmark({ date, label = "SENT", animate = false, className = "" }:
  { date: string; label?: string; animate?: boolean; className?: string }) {
  const d = new Date(date);
  const day = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short" }).format(d).toUpperCase();
  return (
    <svg viewBox="0 0 100 100" className={`pointer-events-none size-20 text-post opacity-80 mix-blend-multiply dark:mix-blend-screen ${animate ? "stamp-in" : "-rotate-12"} ${className}`}
      role="img" aria-label={`${label.toLowerCase()} ${day}`}>
      <circle cx="50" cy="50" r="46" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="50" cy="50" r="38" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <text x="50" y="45" textAnchor="middle" fontSize="15" fontWeight="800" fill="currentColor" letterSpacing="2">{label}</text>
      <text x="50" y="64" textAnchor="middle" fontSize="12" fontWeight="700" fill="currentColor">{day}</text>
      <path d="M8 50h6M86 50h6" stroke="currentColor" strokeWidth="3" />
    </svg>
  );
}

export const STATUS_TONE: Record<string, Tone> = {
  drafted: "accent", needs_review: "warn", sent: "neutral", replied: "ok", interview: "ok",
  assignment: "ok", rejected: "bad", bounced: "bad", closed: "neutral",
};
export const STATUS_LABEL: Record<string, string> = {
  drafted: "Ready to send", needs_review: "Needs a look", sent: "Sent", replied: "Replied", interview: "Interview",
  assignment: "Assignment", rejected: "Rejected", bounced: "Bounced", closed: "Closed",
};
export const SENT_STATES = new Set(["sent", "replied", "interview", "assignment", "rejected", "bounced", "closed"]);
