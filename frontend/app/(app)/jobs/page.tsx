"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FolderIcon } from "@/components/FileIcons";
import { Badge, Card, Empty, ErrorNote, STATUS_TONE, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";

/** One folder per company, like the reference pipeline's local folders: the tailored
 *  resume (PDF) and the email draft for that company live inside. */
export default function JobsPage() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  useEffect(() => { api.get<Application[]>("/applications").then(setApps).catch((e) => setError(e.message)); }, []);

  const needle = q.trim().toLowerCase();
  const shown = apps?.filter((a) => (filter === "all" || a.status === filter)
    && (!needle || `${name(a)} ${a.role_title ?? ""}`.toLowerCase().includes(needle))) ?? [];
  const statuses = Array.from(new Set(apps?.map((a) => a.status) ?? []));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Jobs</h1>
        <span className="text-sm text-muted">{apps ? `${apps.length} compan${apps.length === 1 ? "y" : "ies"}` : ""}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          <input className={`${inputCls} w-48`} placeholder="Search company or role" value={q}
            onChange={(e) => setQ(e.target.value)} aria-label="Search jobs" />
          <select className="rounded-md border border-border bg-surface px-2 py-1 text-sm" value={filter}
            onChange={(e) => setFilter(e.target.value)} aria-label="Filter by status">
            <option value="all">All</option>
            {statuses.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>
      </div>
      <ErrorNote error={error} />
      {!apps ? <p className="text-sm text-muted">Loading…</p> : shown.length === 0 ? (
        <Card>
          <Empty>
            {apps.length === 0
              ? "Every company you apply to gets a folder here, with its tailored resume (PDF) and email draft. Paste a lead to start."
              : "Nothing matches."}
          </Empty>
        </Card>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((a) => (
            <li key={a.id}>
              <Link href={`/jobs/${a.id}`}
                className="group flex h-full gap-3 rounded-lg border border-border bg-surface p-4 transition hover:border-accent">
                <FolderIcon />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="truncate font-semibold group-hover:text-accent">{name(a)}</span>
                  <span className="truncate text-sm text-muted">{a.role_title ?? "Role"}</span>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge tone={STATUS_TONE[a.status]}>{a.status.replace("_", " ")}</Badge>
                    <span className="text-xs text-muted">
                      {a.resume_filename ? "resume PDF" : "no resume"}{a.route === "email" ? " · email draft" : " · apply on portal"}
                    </span>
                  </div>
                  <span className="text-xs text-muted">{new Date(a.created_at).toLocaleDateString()}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const name = (a: Application) => a.company_name ?? a.domain ?? "Company";
