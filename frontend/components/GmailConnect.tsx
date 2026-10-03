"use client";

import { useSearchParams } from "next/navigation";
import { ReactNode, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import type { GmailStatus, SendForMe as SendSettings } from "@/lib/types";
import { IconAlert, IconCheck, IconChevronRight, IconClock, IconMail, IconSend, IconX } from "./icons";
import { Badge, Button, Card, ErrorNote, Field, inputCls } from "./ui";

/**
 * The person's Gmail connection, and a way to start one. `connect` opens the guide first; the
 * guide's "Continue to Google" goes to Google's consent screen, which sends the person back here.
 * Whoever calls `connect` renders `guide`.
 */
export function useGmail() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [guideError, setGuideError] = useState<string | null>(null);
  const load = useCallback(() => api.get<GmailStatus>("/gmail").then(setStatus).catch(() => setStatus(null)), []);
  useEffect(() => { load(); }, [load]);
  const connect = () => { setGuideError(null); setGuideOpen(true); };
  const toGoogle = async () => {
    setLeaving(true); setGuideError(null);
    try {
      const r = await api.post<{ url: string }>("/gmail/connect", { return_to: window.location.pathname });
      window.location.href = r.url;
    } catch (e) { setGuideError(e instanceof Error ? e.message : String(e)); setLeaving(false); }
  };
  const disconnect = async () => {
    if (!confirm("Disconnect Gmail? Jobreach stops drafting there. Drafts already in Gmail stay.")) return;
    setBusy(true);
    try { await api.del("/gmail"); await load(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  const guide = (
    <GmailGuide open={guideOpen} onClose={() => setGuideOpen(false)} onContinue={toGoogle} busy={leaving}
      error={guideError} unverified={status?.unverified ?? true} reconnect={!!status?.expired} />
  );
  return { status, load, connect, disconnect, busy, error, guide };
}

/** A button's label as it appears on Google's page. */
function Key({ children }: { children: ReactNode }) {
  return (
    <span className="mx-0.5 inline-flex items-center rounded-md border border-border-strong bg-surface px-1.5 text-[13px] font-semibold leading-6 text-text shadow-[0_1px_0_var(--border-strong)]">
      {children}
    </span>
  );
}

const Nowrap = ({ children }: { children: ReactNode }) => <span className="whitespace-nowrap">{children}</span>;

type Step = { title: ReactNode; body: ReactNode; aside?: ReactNode; caution?: boolean };

/**
 * What Google will show, before the person is sent there. While the app is unverified Google puts
 * a warning in front of the consent screen; this is the page that says it is expected.
 */
function GmailGuide({ open, onClose, onContinue, busy, error, unverified, reconnect }: {
  open: boolean; onClose: () => void; onContinue: () => void; busy: boolean; error: string | null;
  unverified: boolean; reconnect: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const goRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // Start at the top: focusing the button at the bottom must not scroll the guide past its first steps.
    if (open && !d.open) { d.showModal(); goRef.current?.focus({ preventScroll: true }); d.scrollTop = 0; }
    if (!open && d.open) d.close();
  }, [open]);

  const steps: Step[] = [
    { title: "Choose your Gmail account",
      body: "Pick the address your letters should come from. It can be different from the one you use for Jobreach." },
    ...(unverified ? [{
      caution: true,
      title: <>Google says &ldquo;Google hasn&apos;t verified this app&rdquo;</>,
      body: <>That&apos;s expected: Jobreach is still in Google&apos;s testing stage. <Nowrap>Press <Key>Continue</Key>.</Nowrap>{" "}
        &ldquo;Back to safety&rdquo; cancels.</>,
      aside: <>If Google says &ldquo;Access blocked&rdquo; instead, your address isn&apos;t on the testers&apos; list yet. Ask the
        person who invited you to add it.</>,
    }] : []),
    { title: "Allow drafts",
      body: <>Google asks to let Jobreach &ldquo;Manage drafts and send emails&rdquo;. If there&apos;s a box beside it, tick it,
        then <Nowrap>press <Key>Continue</Key>.</Nowrap></>,
      aside: "Gmail has no permission for drafts alone. Jobreach creates drafts, and sends one only if you turn on Send for me." },
    { title: "You're back here",
      body: "Letters that are ready go into your Gmail Drafts with their resume attached. New ones follow as they're written." },
  ];

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="gmail-guide-title" aria-describedby="gmail-guide-lead"
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
      className="sheet m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-text shadow-[0_24px_60px_-20px_rgb(11_16_32/0.45)]">
      <div className="p-5 sm:px-7 sm:pb-0 sm:pt-7">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><IconMail size={20} /></span>
          <div className="min-w-0 flex-1 pt-0.5">
            <h2 id="gmail-guide-title" className="text-lg font-bold leading-snug tracking-[-0.01em]">
              {reconnect ? "Reconnecting Gmail" : "Connecting Gmail"} takes about 20 seconds
            </h2>
            <p id="gmail-guide-lead" className="mt-1 text-[15px] leading-relaxed text-text-2">
              {reconnect && unverified
                ? "While Jobreach is in Google's testing stage, Google ends the connection after 7 days. These are the pages you'll see again."
                : "Google shows its own pages for this. Here's what's on them, so nothing comes as a surprise."}
            </p>
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close"
            className="-mr-2 -mt-1 grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-sunken hover:text-text focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/20">
            <IconX size={18} />
          </button>
        </div>

        <ol className="mt-6 flex flex-col gap-5">
          {steps.map((s, i) => (
            <li key={i} className="relative pl-11 after:absolute after:-bottom-4 after:left-[13.5px] after:top-9 after:w-px after:bg-border last:after:hidden">
              <span aria-hidden="true" className={`absolute left-0 top-0 grid size-7 place-items-center rounded-full text-[13px] font-semibold tabular-nums ${
                s.caution ? "bg-warn-soft text-warn" : "border border-border-strong bg-surface text-text-2"}`}>
                {s.caution ? <IconAlert size={14} /> : i + 1}
              </span>
              <p className="pt-0.5 font-semibold leading-snug">{s.title}</p>
              <p className="mt-1 text-[15px] leading-relaxed text-text-2">{s.body}</p>
              {s.aside && <p className="mt-2 text-[13px] leading-relaxed text-muted">{s.aside}</p>}
            </li>
          ))}
        </ol>

        <ErrorNote error={error} />
        {/* On a laptop screen the steps can run past the fold, so the way on stays in view. */}
        <div className="mt-7 flex flex-col-reverse gap-3 border-t border-border pt-5 sm:sticky sm:bottom-0 sm:flex-row sm:items-center sm:gap-4 sm:bg-surface sm:pb-7">
          <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-muted">Disconnect any time in Profile, under Gmail.</p>
          <div className="flex shrink-0 flex-col-reverse gap-2 whitespace-nowrap sm:flex-row">
            <Button variant="ghost" onClick={onClose} disabled={busy} className="min-h-11">Not now</Button>
            <Button ref={goRef} busy={busy} onClick={onContinue} className="min-h-11 px-4">
              Continue to Google {!busy && <IconChevronRight size={16} />}
            </Button>
          </div>
        </div>
      </div>
    </dialog>
  );
}

/** On Today and Add leads: the offer to connect, and the outcome when Google sends you back. */
export function GmailBanner() {
  return <Suspense><Banner /></Suspense>;
}

const NOT_CONNECTED: Record<string, string> = {
  denied: "Gmail wasn't connected: the permission was not given on Google's page.",
  unticked: "Gmail wasn't connected: the box that allows drafts was left unticked on Google's page. Try again and tick it.",
  error: "Gmail couldn't be connected. Try again in a moment.",
};

function Banner() {
  const params = useSearchParams();
  const result = params.get("gmail");
  const { status, connect, busy, error, guide } = useGmail();
  const [hidden, setHidden] = useState(false);
  if (!status?.available || hidden) return null;

  let content: ReactNode = null;
  if (result === "connected" && status.connected) {
    content = (
      <Note tone="ok" icon={<IconCheck size={18} />} onClose={() => setHidden(true)}>
        <span className="font-semibold">Gmail connected as {status.email}.</span> Letters that are ready go into your Gmail
        drafts with their resume attached; new ones follow as they&apos;re written.
      </Note>
    );
  } else if (result && result in NOT_CONNECTED && !status.connected) {
    content = (
      <Note tone="warn" icon={<IconAlert size={18} />} onClose={() => setHidden(true)}
        action={<Button variant="secondary" onClick={connect}>Try again</Button>}>
        {NOT_CONNECTED[result]}
      </Note>
    );
  } else if (!status.connected) {
    content = (
      <section className="flex flex-col gap-3 rounded-2xl border border-accent/25 bg-accent-soft/50 p-4 sm:flex-row sm:items-center sm:p-5">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-surface text-accent"><IconMail size={20} /></span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{status.expired ? "Your Gmail connection ended" : "Get every letter in your Gmail drafts"}</p>
          <p className="mt-0.5 text-sm leading-relaxed text-text-2">
            {status.expired
              ? "Google stopped accepting it. Reconnect and new letters go straight to your drafts again."
              : "Connect Gmail once and each letter is waiting in your Drafts with its resume attached. You open it and press Send."}
          </p>
          <ErrorNote error={error} />
        </div>
        <Button busy={busy} onClick={connect} className="shrink-0">{status.expired ? "Reconnect Gmail" : "Connect Gmail"}</Button>
      </section>
    );
  }
  return <>{content}{guide}</>;
}

function Note({ tone, icon, children, action, onClose }: {
  tone: "ok" | "warn"; icon: ReactNode; children: ReactNode; action?: ReactNode; onClose: () => void;
}) {
  const cls = tone === "ok" ? "border-ok/30 bg-ok-soft/70 text-ok" : "border-warn/30 bg-warn-soft text-warn";
  return (
    <div role="status" className={`flex items-start gap-3 rounded-2xl border px-4 py-3 ${cls}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-relaxed text-text">{children}</p>
        {action && <div className="mt-2.5">{action}</div>}
      </div>
      <button type="button" onClick={onClose} aria-label="Dismiss" className="rounded p-1 text-muted hover:bg-surface/60"><IconX size={15} /></button>
    </div>
  );
}

/** Profile > Gmail: the connection, what it allows, and a way out; then Send for me. */
export function GmailCard() {
  const { status, load, connect, disconnect, busy, error, guide } = useGmail();
  if (!status) return <div className="h-32 animate-pulse rounded-2xl bg-sunken" />;
  return (
    <div className="flex flex-col gap-4">
    <Card title="Gmail">
      {!status.available ? (
        <p className="text-[15px] text-muted">Gmail drafts aren&apos;t set up on this server yet. Copy each letter from its page instead.</p>
      ) : status.connected ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-10 place-items-center rounded-full bg-ok-soft text-ok"><IconCheck size={20} /></span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Connected as {status.email}</p>
            <p className="text-sm text-text-2">Every letter that passes its checks is created as a draft there, with its resume attached.</p>
          </div>
          <Button variant="secondary" busy={busy} onClick={disconnect}>Disconnect</Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{status.expired ? "Your Gmail connection ended" : "Not connected"}</p>
            <p className="text-sm text-text-2">Connect once and your letters wait in your Gmail drafts, resume attached.</p>
          </div>
          <Button busy={busy} onClick={connect}>{status.expired ? "Reconnect Gmail" : "Connect Gmail"}</Button>
        </div>
      )}
      <ErrorNote error={error} />
      {status.available && (
        <p className="mt-4 max-w-2xl text-[13px] leading-relaxed text-muted">
          Google asks you to let Jobreach &ldquo;manage drafts and send emails&rdquo;: Gmail has no permission for drafts
          alone. Jobreach creates drafts, and sends them only if you turn on Send for me. It can&apos;t read or delete your
          mail. Disconnecting removes Jobreach&apos;s access at Google.
        </p>
      )}
      {guide}
    </Card>
    {status.available && status.connected && status.send && <SendForMe email={status.email} s={status.send} reload={load} />}
    </div>
  );
}

// ------------------------------------------------------------------ Send for me

/** "today, 3:42 PM", "tomorrow, 2:10 PM" or "Mon, 2:10 PM", in the person's sending time zone. */
export function fmtSendAt(iso: string, tz?: string | null): string {
  const zone = tz ? { timeZone: tz } : {};
  const day = (d: Date) => new Intl.DateTimeFormat("en-CA", { ...zone, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const at = new Date(iso);
  const time = new Intl.DateTimeFormat(undefined, { ...zone, hour: "numeric", minute: "2-digit" }).format(at);
  if (day(at) === day(new Date())) return "today, " + time;
  if (day(at) === day(new Date(Date.now() + 86_400_000))) return "tomorrow, " + time;
  return new Intl.DateTimeFormat(undefined, { ...zone, weekday: "short" }).format(at) + ", " + time;
}

/** "India Standard Time" rather than "Asia/Kolkata". */
export function zoneName(tz: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { timeZone: tz, timeZoneName: "long" }).formatToParts(new Date())
      .find((x) => x.type === "timeZoneName")?.value ?? tz;
  } catch { return tz; }
}

const HOURS = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);
const hourLabel = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
};
const WAITS: [number, string][] = [[30, "30 minutes"], [60, "1 hour"], [120, "2 hours"], [240, "4 hours"], [720, "12 hours"]];
const waitLabel = (min: number) => WAITS.find(([m]) => m === min)?.[1] ?? `${Math.round(min / 60)} hours`;
const CAPS = [3, 5, 10, 15, 20];

type Form = { window_start: string; window_end: string; daily_cap: number; grace_minutes: number };

/** Profile > Gmail: the opt-in, its hours, what is lined up and a way out. */
function SendForMe({ email, s, reload }: { email: string | null; s: SendSettings; reload: () => Promise<void> | void }) {
  const [form, setForm] = useState<Form>({ window_start: s.window_start, window_end: s.window_end,
    daily_cap: s.daily_cap, grace_minutes: s.grace_minutes });
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : s.timezone;
  const badWindow = form.window_start === form.window_end;

  async function save(enabled: boolean) {
    setBusy(true); setError(null);
    try {
      await api.put("/gmail/send-for-me", { enabled, ...form, timezone: tz });
      setEditing(false); setConfirming(false);
      await reload();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  }

  const hours = `${hourLabel(s.window_start)} and ${hourLabel(s.window_end)}`;
  const settings = (
    <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_1fr]">
      <Field label="From">
        <select className={inputCls} value={form.window_start} onChange={(e) => setForm({ ...form, window_start: e.target.value })}>
          {HOURS.map((h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
        </select>
      </Field>
      <Field label="Until">
        <select className={inputCls} value={form.window_end} onChange={(e) => setForm({ ...form, window_end: e.target.value })}>
          {HOURS.map((h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
        </select>
      </Field>
      <Field label="Letters a day, at most">
        <select className={inputCls} value={form.daily_cap} onChange={(e) => setForm({ ...form, daily_cap: Number(e.target.value) })}>
          {CAPS.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </Field>
      <Field label="Wait in drafts, at least">
        <select className={inputCls} value={form.grace_minutes} onChange={(e) => setForm({ ...form, grace_minutes: Number(e.target.value) })}>
          {WAITS.map(([m, l]) => <option key={m} value={m}>{l}</option>)}
        </select>
      </Field>
    </div>
  );

  return (
    <Card title="Send for me" actions={s.enabled
      ? (s.paused_reason ? <Badge tone="warn">Paused</Badge> : <Badge tone="ok"><IconCheck size={13} /> On</Badge>)
      : <Badge>Off</Badge>}>
      {!s.enabled ? (
        <>
          <p className="max-w-2xl text-[15px] leading-relaxed text-text-2">
            Turn this on and Jobreach sends the letters that passed every check from your Gmail, so you don&apos;t open
            each draft. They go at random moments inside your hours, a few a day, never sooner than your waiting time
            after they reach your drafts. Until a letter goes, you can edit it in Gmail or stop it here.
          </p>
          <div className="mt-5">{settings}</div>
          <p className="mt-2 text-[13px] text-muted">Times are in {zoneName(tz)}.</p>
          {badWindow && <p className="mt-2 text-sm text-warn">Choose an end time different from the start.</p>}
          <ErrorNote error={error} />
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button disabled={badWindow} onClick={() => setConfirming(true)}><IconSend size={16} /> Turn on Send for me</Button>
          </div>
          <p className="mt-4 max-w-2xl text-[13px] leading-relaxed text-muted">
            Never sent for you: letters that need a look, ones you marked sent or stopped, and letters whose post is more than
            three days old. It pauses itself if two letters bounce in a week.
          </p>
        </>
      ) : (
        <>
          {s.paused_reason && (
            <div role="status" className="mb-4 flex items-start gap-3 rounded-xl border border-warn/30 bg-warn-soft px-4 py-3">
              <IconAlert size={18} className="mt-0.5 shrink-0 text-warn" />
              <div className="min-w-0 flex-1 text-sm leading-relaxed">
                <p><span className="font-semibold">Paused.</span> {s.paused_reason}</p>
                <Button variant="secondary" className="mt-2.5" busy={busy} onClick={() => save(true)}>Turn back on</Button>
              </div>
            </div>
          )}
          <p className="max-w-2xl text-[15px] leading-relaxed text-text-2">
            Sending from <span className="font-semibold text-text">{email}</span>: up to {s.daily_cap} letters a day, between{" "}
            {hours}, each at least {waitLabel(s.grace_minutes)} after it reaches your drafts.
            {s.timezone !== tz && <> Times are in {zoneName(s.timezone)}.</>}
          </p>

          <h3 className="mt-5 text-sm font-semibold">Lined up</h3>
          {s.upcoming.length === 0 ? (
            <p className="mt-1 text-sm text-muted">Nothing yet. New letters are lined up as they reach your Gmail drafts.</p>
          ) : (
            <ol className="mt-2 divide-y divide-border rounded-xl border border-border">
              {s.upcoming.map((u) => (
                <li key={u.application_id}>
                  <Link href={`/jobs/${u.application_id}`}
                    className="flex flex-col gap-0.5 px-4 py-2.5 text-sm hover:bg-sunken/60 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/20 sm:flex-row sm:items-center sm:gap-3">
                    <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap font-semibold text-accent sm:w-44">
                      <IconClock size={14} /> <span className="first-letter:uppercase">{fmtSendAt(u.send_at, s.timezone)}</span>
                    </span>
                    <span className="min-w-0 flex-1 sm:truncate">{u.company ?? "A company"}<span className="text-muted"> · {u.role_title}</span></span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-3 text-[13px] text-muted">Sent in the last 24 hours: {s.sent_last_24h}</p>

          {editing && <div className="mt-5 border-t border-border pt-5">{settings}
            {badWindow && <p className="mt-2 text-sm text-warn">Choose an end time different from the start.</p>}</div>}
          <ErrorNote error={error} />
          <div className="mt-5 flex flex-wrap items-center gap-2">
            {editing
              ? <><Button busy={busy} disabled={badWindow} onClick={() => save(true)}>Save hours</Button>
                  <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button></>
              : <Button variant="secondary" onClick={() => setEditing(true)}>Change hours</Button>}
            <Button variant="ghost" busy={busy && !editing} onClick={() => save(false)}>Turn off</Button>
          </div>
        </>
      )}
      <ConfirmSend open={confirming} onClose={() => setConfirming(false)} onConfirm={() => save(true)} busy={busy}
        email={email} form={form} tz={tz} error={confirming ? error : null} />
    </Card>
  );
}

/** The consent: what turning it on means, said plainly, before anything is sent. */
function ConfirmSend({ open, onClose, onConfirm, busy, email, form, tz, error }: {
  open: boolean; onClose: () => void; onConfirm: () => void; busy: boolean; email: string | null; form: Form; tz: string;
  error: string | null;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { d.showModal(); cancelRef.current?.focus({ preventScroll: true }); d.scrollTop = 0; }
    if (!open && d.open) d.close();
  }, [open]);
  const points = [
    <>Letters go from <span className="font-semibold text-text">{email}</span>, as if you pressed Send.</>,
    "Only letters that passed every check. A letter that needs a look always waits for you.",
    <>At most {form.daily_cap} a day, at random moments between {hourLabel(form.window_start)} and {hourLabel(form.window_end)}, {zoneName(tz)}.</>,
    <>Each waits at least {waitLabel(form.grace_minutes)} in your Gmail drafts first. Edit it there and your version goes; stop it on
      its page here.</>,
    "It pauses itself if letters start bouncing, and you can turn it off at any time.",
  ];
  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="send-confirm-title"
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
      className="sheet m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-text shadow-[0_24px_60px_-20px_rgb(11_16_32/0.45)]">
      <div className="p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><IconSend size={19} /></span>
          <h2 id="send-confirm-title" className="min-w-0 flex-1 pt-1.5 text-lg font-bold leading-snug tracking-[-0.01em]">
            Let Jobreach send your letters?
          </h2>
        </div>
        <ul className="mt-5 flex flex-col gap-3 text-[15px] leading-relaxed text-text-2">
          {points.map((pt, i) => (
            <li key={i} className="flex gap-2.5"><IconCheck size={17} className="mt-1 shrink-0 text-accent" /><span>{pt}</span></li>
          ))}
        </ul>
        <ErrorNote error={error} />
        <div className="mt-7 flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:justify-end">
          <Button ref={cancelRef} variant="ghost" onClick={onClose} disabled={busy} className="min-h-11">Not now</Button>
          <Button busy={busy} onClick={onConfirm} className="min-h-11 px-4"><IconSend size={16} /> Turn on</Button>
        </div>
      </div>
    </dialog>
  );
}
