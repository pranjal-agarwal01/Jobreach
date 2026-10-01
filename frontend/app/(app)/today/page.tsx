"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Empty, ErrorNote, STATUS_TONE, hoursLabel } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application, Lead } from "@/lib/types";

interface Today {
  deadlines: { id: string; type: string; deadline_at: string | null; summary: string | null; application_id: string;
               company_name: string | null; role_title: string | null }[];
  drafts: Application[];
  decisions: Lead[];
  gaps: { id: string; text: string; item_name: string }[];
  processing: number;
}

export default function TodayPage() {
  const [t, setT] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.get<Today>("/today").then(setT).catch((e) => setError(String(e.message ?? e))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!t?.processing) return;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [t?.processing, load]);

  if (!t) return error ? <ErrorNote error={error} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Today</h1>
        <div className="flex items-center gap-3">
          {t.processing > 0 && <Badge tone="accent">{t.processing} lead(s) processing…</Badge>}
          <Link href="/leads"><Button>Paste a lead</Button></Link>
        </div>
      </div>

      <Card title="Live threads and deadlines">
        {t.deadlines.length === 0 ? <Empty>No interviews or assignments logged. Log replies on each application.</Empty> : (
          <ul className="flex flex-col gap-2 text-sm">
            {t.deadlines.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-2">
                <Badge tone="ok">{d.type.replace("_", " ")}</Badge>
                <Link className="font-medium hover:underline" href={`/jobs/${d.application_id}`}>
                  {d.company_name ?? "Company"} · {d.role_title}
                </Link>
                {d.deadline_at && <span className="text-warn">due {new Date(d.deadline_at).toLocaleString()}</span>}
                {d.summary && <span className="text-muted">{d.summary}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Ready to send" actions={<span className="text-xs text-muted">Freshest post first: post age is the strongest predictor of a reply.</span>}>
        {t.drafts.length === 0 ? <Empty>No drafts waiting. Paste a fresh post from LinkedIn or a careers page.</Empty> : (
          <ul className="divide-y divide-border">
            {t.drafts.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <Link className="min-w-0 flex-1 font-medium hover:underline" href={`/jobs/${a.id}`}>
                  {a.company_name ?? a.domain ?? "Company"} · {a.role_title}
                </Link>
                <span className="text-muted">post {hoursLabel(a.age_at_draft_hours)} old</span>
                <Badge>{a.route === "email" ? "email" : "portal"}</Badge>
                <Badge tone={STATUS_TONE[a.status]}>{a.status === "needs_review" ? "needs review" : "ready"}</Badge>
                {a.judgment_calls?.length > 0 && <Badge tone="warn">{a.judgment_calls.length} judgment call(s)</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {t.decisions.length > 0 && (
        <Card title="Dropped in the last 3 days" actions={<span className="text-xs text-muted">Your call: draft any of these anyway.</span>}>
          <ul className="flex flex-col gap-2 text-sm">
            {t.decisions.map((l) => (
              <li key={l.id} className="flex flex-wrap items-start gap-2">
                <span className="font-medium">{l.company_name ?? "Unknown"} · {l.title ?? "role"}</span>
                <span className="flex-1 text-muted">{l.reasons?.[0]}</span>
                <Button variant="secondary" onClick={async () => { await api.post(`/leads/${l.id}/override`); load(); }}>Draft anyway</Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {t.gaps.length > 0 && (
        <Card title="Lines that would be stronger with a number" actions={<Link href="/profile" className="text-sm text-accent hover:underline">Edit fact bank</Link>}>
          <ul className="flex flex-col gap-1 text-sm">
            {t.gaps.map((g) => <li key={g.id}><span className="text-muted">{g.item_name}:</span> {g.text}</li>)}
          </ul>
          <p className="mt-2 text-xs text-muted">Only add a number you actually know. Leave it out otherwise.</p>
        </Card>
      )}
    </div>
  );
}
