"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, Empty, ErrorNote, STATUS_TONE, hoursLabel } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => { api.get<Application[]>("/applications").then(setApps).catch((e) => setError(e.message)); }, []);

  const shown = apps?.filter((a) => filter === "all" || a.status === filter) ?? [];
  const statuses = Array.from(new Set(apps?.map((a) => a.status) ?? []));
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Applications</h1>
        <select className="rounded-md border border-border px-2 py-1 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All ({apps?.length ?? 0})</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
      </div>
      <ErrorNote error={error} />
      <Card>
        {!apps ? <p className="text-sm text-muted">Loading…</p> : shown.length === 0 ? <Empty>One row per company. Paste a lead to start.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr><th className="py-2 pr-3">Company · role</th><th className="pr-3">Track</th><th className="pr-3">Route</th>
                  <th className="pr-3">Post age at draft</th><th className="pr-3">Status</th><th>Created</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {shown.map((a) => (
                  <tr key={a.id}>
                    <td className="py-2 pr-3"><Link className="font-medium hover:underline" href={`/applications/${a.id}`}>
                      {a.company_name ?? a.domain ?? "Company"} · {a.role_title}</Link></td>
                    <td className="pr-3">{a.track_key}</td>
                    <td className="pr-3">{a.route}</td>
                    <td className="pr-3">{hoursLabel(a.age_at_draft_hours)}</td>
                    <td className="pr-3"><Badge tone={STATUS_TONE[a.status]}>{a.status.replace("_", " ")}</Badge></td>
                    <td className="text-muted">{new Date(a.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
