"use client";

import { BaselineGrid, useReview } from "./Baselines";
import { ErrorNote } from "./ui";

/** Profile's Resumes tab: one baseline per kind of role, each editable and re-rendered on save. */
export default function TracksEditor() {
  const { review, reload, busy, error } = useReview();
  if (!review) return error ? <ErrorNote error={error} /> : <div className="h-72 animate-pulse rounded-2xl bg-sunken" />;
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-2xl text-[15px] leading-relaxed text-muted">
        One resume for each kind of role you want. Every opening you pursue gets its own copy of the closest one,
        reordered and trimmed for that job.
      </p>
      <BaselineGrid review={review} busy={busy} reload={reload} />
    </div>
  );
}
