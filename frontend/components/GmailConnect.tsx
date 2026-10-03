"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GmailStatus } from "@/lib/types";
import { IconAlert, IconCheck, IconMail, IconX } from "./icons";
import { Button, Card, ErrorNote } from "./ui";

/** The person's Gmail connection, and a way to start one (Google's consent screen, then back here). */
export function useGmail() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get<GmailStatus>("/gmail").then(setStatus).catch(() => setStatus(null)), []);
  useEffect(() => { load(); }, [load]);
  const connect = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.post<{ url: string }>("/gmail/connect", { return_to: window.location.pathname });
      window.location.href = r.url;
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setBusy(false); }
  };
  const disconnect = async () => {
    if (!confirm("Disconnect Gmail? Jobreach stops drafting there. Drafts already in Gmail stay.")) return;
    setBusy(true);
    try { await api.del("/gmail"); await load(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  return { status, load, connect, disconnect, busy, error };
}

const PERMISSION = "Google will ask you to let Jobreach “manage drafts and send emails”: Gmail has no permission " +
  "for drafts alone. Jobreach only ever creates drafts; it has no way to send, read or delete your mail.";

/** On Today and Add leads: the offer to connect, and the outcome when Google sends you back. */
export function GmailBanner() {
  return <Suspense><Banner /></Suspense>;
}

function Banner() {
  const params = useSearchParams();
  const result = params.get("gmail");
  const { status, connect, busy, error } = useGmail();
  const [hidden, setHidden] = useState(false);
  if (!status?.available || hidden) return null;

  if (result === "connected" && status.connected) {
    return (
      <Note tone="ok" icon={<IconCheck size={18} />} onClose={() => setHidden(true)}>
        <span className="font-semibold">Gmail connected as {status.email}.</span> Letters that are ready go into your Gmail
        drafts with their resume attached; new ones follow as they&apos;re written.
      </Note>
    );
  }
  if (result === "denied" || result === "error") {
    return (
      <Note tone="warn" icon={<IconAlert size={18} />} onClose={() => setHidden(true)}
        action={<Button variant="secondary" busy={busy} onClick={connect}>Try again</Button>}>
        {result === "denied" ? "Gmail wasn't connected: the permission was not given." : "Gmail couldn't be connected. Try again in a moment."}
      </Note>
    );
  }
  if (status.connected) return null;
  return (
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

function Note({ tone, icon, children, action, onClose }: {
  tone: "ok" | "warn"; icon: React.ReactNode; children: React.ReactNode; action?: React.ReactNode; onClose: () => void;
}) {
  const cls = tone === "ok" ? "border-ok/30 bg-ok-soft/70 text-ok" : "border-warn/30 bg-warn-soft text-warn";
  return (
    <div role="status" className={`flex items-start gap-3 rounded-2xl border px-4 py-3 ${cls}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p className="min-w-0 flex-1 text-sm leading-relaxed text-text">{children}</p>
      {action}
      <button type="button" onClick={onClose} aria-label="Dismiss" className="rounded p-1 text-muted hover:bg-surface/60"><IconX size={15} /></button>
    </div>
  );
}

/** Profile > Gmail: the connection, what it allows, and a way out. */
export function GmailCard() {
  const { status, connect, disconnect, busy, error } = useGmail();
  if (!status) return <div className="h-32 animate-pulse rounded-2xl bg-sunken" />;
  return (
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
      {status.available && <p className="mt-4 max-w-2xl text-[13px] leading-relaxed text-muted">{PERMISSION} Disconnecting removes Jobreach&apos;s access at Google.</p>}
    </Card>
  );
}
