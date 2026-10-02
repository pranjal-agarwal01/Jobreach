"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { MatchDial, Meta } from "@/components/OpportunityCard";
import { IconAlert, IconCheck, IconChevronDown, IconExternal, IconMail, IconX } from "@/components/icons";
import { Badge, Button, ErrorNote, Monogram } from "@/components/ui";
import { api } from "@/lib/api";
import { FIELD_LABEL } from "@/lib/fields";
import { BUCKET, preparing } from "@/lib/opportunity";
import type { ContactCandidate, OpportunityDetail } from "@/lib/types";

const STEPS = ["Tailoring your resume to this opening", "Fitting it to one page", "Writing the letter", "Checking every line"];

export default function OpportunityPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [o, setO] = useState<OpportunityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.get<OpportunityDetail>(`/opportunities/${id}`).then(setO)
    .catch((e) => setError(e instanceof Error ? e.message : String(e))), [id]);
  useEffect(() => { load(); }, [load]);

  const working = o ? preparing(o) : false;
  useEffect(() => {
    if (!working) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [working, load]);
  // Prepared while the person watched: open the letter.
  const watched = useRef(false);
  useEffect(() => { if (working) watched.current = true; }, [working]);
  const appId = o?.application_id;
  useEffect(() => { if (appId && watched.current) router.push(`/jobs/${appId}`); }, [appId, router]);

  if (!o) return error ? <ErrorNote error={error} /> : <div className="h-96 animate-pulse rounded-2xl bg-sunken" />;
  const company = o.company_name ?? o.domain ?? "Company";
  const chosen = o.contacts.find((c) => c.chosen) ?? null;
  const others = o.contacts.filter((c) => !c.chosen);
  const dropped = o.decision === "drop" && !o.overridden;

  return (
    <div className="flex flex-col gap-8">
      <nav aria-label="Breadcrumb" className="-mb-4 text-sm text-muted">
        <Link href="/today" className="hover:text-text">Today</Link>
        <span className="mx-2 text-border-strong">/</span>
        <span className="text-text-2">{company}</span>
      </nav>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <Monogram name={company} size={52} />
          <div className="min-w-0 flex-1">
            <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] sm:text-[28px]">{company}</h1>
            <p className="text-[15px] text-text-2">{o.title}</p>
            <div className="mt-1"><Meta o={o} /></div>
          </div>
        </div>
        {o.bucket && !dropped && (
          <div className="flex items-center gap-3 self-start sm:self-center">
            <MatchDial score={o.score} bucket={o.bucket} size={58} />
            <div>
              <Badge tone={BUCKET[o.bucket].tone}>{BUCKET[o.bucket].short}</Badge>
              <p className="mt-1 text-xs text-muted">out of 100, for you</p>
            </div>
          </div>
        )}
      </header>
      <ErrorNote error={error} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          {dropped ? (
            <section className="rounded-2xl border border-warn/30 bg-warn-soft p-5">
              <h2 className="inline-flex items-center gap-2 font-semibold"><IconAlert size={18} className="text-warn" /> Ruled out for you</h2>
              <ul className="mt-2 list-disc pl-5 text-sm leading-relaxed text-text-2">{o.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </section>
          ) : (
            <section className="paper p-5 sm:p-6" aria-labelledby="why">
              <h2 id="why" className="text-[17px] font-bold tracking-tight">Why it suits you</h2>
              <ul className="mt-3 flex flex-col gap-2.5">
                {o.why.map((w) => (
                  <li key={w} className="flex gap-2.5 text-[15px] leading-snug">
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-ok-soft text-ok"><IconCheck size={13} strokeWidth={2.6} /></span>{w}
                  </li>
                ))}
              </ul>
              {o.gaps.length > 0 && (
                <>
                  <h3 className="mt-5 text-sm font-semibold">What it asks for that your record doesn&apos;t show</h3>
                  <ul className="mt-2 flex flex-col gap-2">
                    {o.gaps.map((g) => (
                      <li key={g} className="flex gap-2.5 text-[15px] leading-snug text-text-2">
                        <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-warn-soft text-warn"><IconX size={12} strokeWidth={2.6} /></span>{g}
                      </li>
                    ))}
                  </ul>
                  {o.route === "email" && (
                    <p className="mt-3 text-[13px] leading-relaxed text-muted">The letter names a gap in one honest clause and says what you have instead. It never claims it.</p>
                  )}
                </>
              )}
              {o.track_key && (
                <p className="mt-5 border-t border-dashed border-border pt-4 text-sm text-muted">
                  Your resume for it starts from your <span className="font-semibold text-text-2">{FIELD_LABEL[o.track_key] ?? o.track_key}</span> baseline:
                  the title line, summary, order and skills are tailored, using only your own record.
                </p>
              )}
            </section>
          )}

          <section className="rounded-2xl border border-border bg-surface p-5 sm:p-6" aria-labelledby="who">
            <h2 id="who" className="text-[17px] font-bold tracking-tight">Who you&apos;d write to</h2>
            {chosen ? <ContactBlock c={chosen} company={company} /> : o.route === "portal" ? (
              <div className="mt-3 text-[15px] text-text-2">
                <p>No hiring address is published for this opening, so the route is their own application page.</p>
                {o.apply_to?.startsWith("http") && (
                  <a href={o.apply_to} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1.5 font-semibold text-accent hover:underline">
                    <IconExternal size={15} /> Open the application page
                  </a>
                )}
              </div>
            ) : <p className="mt-3 text-[15px] text-muted">No published address and no portal.</p>}
            {others.length > 0 && (
              <div className="mt-5 border-t border-dashed border-border pt-4">
                <p className="text-sm font-semibold">Also published</p>
                <ul className="mt-2 flex flex-col gap-1.5 text-sm text-text-2">
                  {others.map((c) => <li key={c.id}><span className="font-medium">{c.person_name ?? c.email}</span>
                    {c.person_name && <span className="text-muted"> ({c.email})</span>}<span className="text-muted">, {c.where}</span></li>)}
                </ul>
              </div>
            )}
            <p className="mt-4 text-[13px] leading-relaxed text-muted">
              Jobreach only writes to addresses published for hiring: in the post, then on the company&apos;s own site.
              It never guesses one, and never uses an address published for press or support.
            </p>
          </section>

          {(o.flags?.length ?? 0) > 0 && (
            <section className="flex gap-3 rounded-2xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm">
              <IconAlert size={18} className="mt-0.5 shrink-0 text-warn" />
              <div>
                <p className="font-semibold">Worth knowing before you write</p>
                <ul className="mt-1 list-disc pl-5 text-text-2">
                  {o.flags!.map((f) => <li key={f}>{f.startsWith("Check the company page yourself: ")
                    ? <>Check the company page yourself: <a className="font-semibold text-accent hover:underline" target="_blank" rel="noreferrer" href={f.split(": ")[1]}>search LinkedIn</a></>
                    : f}</li>)}
                </ul>
              </div>
            </section>
          )}

          <details className="group rounded-2xl border border-border bg-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold">
              The post <IconChevronDown size={18} className="text-muted transition-transform group-open:rotate-180" />
            </summary>
            <pre className="whitespace-pre-wrap border-t border-border px-5 py-4 font-sans text-sm leading-relaxed text-text-2">{o.job.raw_text}</pre>
          </details>
        </div>

        <aside className="flex flex-col gap-6 lg:sticky lg:top-6 lg:self-start">
          <PreparePanel o={o} reload={load} dropped={dropped} />
          {o.company && (o.company.business_summary || o.company.domain) && (
            <section className="rounded-2xl border border-border bg-surface p-5">
              <h2 className="text-[15px] font-semibold">About {company}</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                {o.company.domain && <span className="text-text-2">{o.company.domain}</span>}
                {o.company.verification && (
                  <Badge tone={o.company.verification === "pass" ? "ok" : o.company.verification === "flag" ? "warn" : "bad"}>
                    {o.company.verification === "pass" ? <><IconCheck size={13} /> Verified</> : o.company.verification === "flag" ? "Check yourself" : "Failed checks"}
                  </Badge>
                )}
              </div>
              {o.company.business_summary && <p className="mt-3 text-sm leading-relaxed text-text-2">{o.company.business_summary}</p>}
              {o.source_ref && <a className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:underline" href={o.source_ref} target="_blank" rel="noreferrer"><IconExternal size={15} /> Original post</a>}
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function ContactBlock({ c, company }: { c: ContactCandidate; company: string }) {
  const name = c.person_name ?? (c.context === "site_generic" ? `${company}'s general inbox` : `The hiring team at ${company}`);
  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="grid size-9 place-items-center rounded-full bg-accent-soft text-accent"><IconMail size={17} /></span>
        <div className="min-w-0">
          <p className="font-semibold">{name}{c.person_role && <span className="font-normal text-text-2">, {c.person_role}</span>}</p>
          <p className="truncate text-sm text-muted">{c.email}</p>
        </div>
        <span className="ml-auto"><Badge tone={c.context === "site_generic" ? "warn" : c.context === "post_apply" ? "ok" : "accent"}>
          {c.context === "post_apply" ? "From the post" : c.context === "careers_page" ? "From their site" : "General inbox"}</Badge></span>
      </div>
      {c.evidence && (
        <figure className="mt-4 rounded-xl bg-inland/70 px-4 py-3">
          <blockquote className="font-letter text-[15px] leading-relaxed text-text">&ldquo;{c.evidence}&rdquo;</blockquote>
          <figcaption className="mt-1.5 text-xs text-muted">
            {c.where}{c.source_url && <>, <a className="font-semibold text-accent hover:underline" href={c.source_url} target="_blank" rel="noreferrer">see the page</a></>}
          </figcaption>
        </figure>
      )}
    </div>
  );
}

function PreparePanel({ o, reload, dropped }: { o: OpportunityDetail; reload: () => void; dropped: boolean }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const working = preparing(o);
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 11000);
    return () => clearInterval(t);
  }, [working]);
  const act = async (k: string, f: () => Promise<unknown>) => {
    setBusy(k); setError(null);
    try { await f(); await reload(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(null);
  };
  const prepare = (override = false) => act("prepare", () => api.post(`/opportunities/${o.id}/prepare`, override ? { override } : {}));
  const who = o.contact_name ? o.contact_name.split(" ")[0] : o.route === "portal" ? null : "the hiring team";

  if (o.application_id) {
    return (
      <section className="paper-inland overflow-hidden">
        <div className="airmail-edge h-2" />
        <div className="p-5">
          <p className="font-semibold">Your letter and resume are ready</p>
          <p className="mt-1 text-sm text-text-2">Read them, attach the PDF and press Send from your own mailbox.</p>
          <Link href={`/jobs/${o.application_id}`} className="mt-4 block"><Button className="w-full">Open the letter</Button></Link>
        </div>
      </section>
    );
  }
  if (working) {
    return (
      <section className="paper-inland overflow-hidden" aria-live="polite">
        <div className="airmail-edge h-2" />
        <div className="p-5">
          <p className="font-semibold">Preparing your letter</p>
          <p className="mt-1 text-sm text-text-2">About a minute. You can leave this page; it will be on Today when it&apos;s ready.</p>
          <ol className="mt-4 flex flex-col gap-2.5">
            {STEPS.map((s, i) => (
              <li key={s} className={`flex items-center gap-2.5 text-sm ${i <= step ? "text-text" : "text-muted"}`}>
                {i < step ? <span className="grid size-5 place-items-center rounded-full bg-ok-soft text-ok"><IconCheck size={12} strokeWidth={2.8} /></span>
                  : i === step ? <span className="size-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                  : <span className="size-5 rounded-full border-2 border-border" />}
                {s}
              </li>
            ))}
          </ol>
        </div>
      </section>
    );
  }
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      {dropped ? (
        <>
          <p className="font-semibold">Write anyway?</p>
          <p className="mt-1 text-sm text-text-2">It was ruled out for the reasons on the left. It&apos;s your call: the letter is written the same careful way.</p>
          <Button variant="secondary" className="mt-4 w-full" busy={busy === "prepare"} onClick={() => prepare(true)}>Prepare it anyway</Button>
        </>
      ) : (
        <>
          <p className="font-semibold">{o.route === "portal" ? "Prepare your tailored resume" : "Prepare your letter and resume"}</p>
          <p className="mt-1 text-sm leading-relaxed text-text-2">
            {o.route === "portal"
              ? "A one-page resume tailored to this opening, to upload on their page."
              : `A one-page resume tailored to this opening and a short letter to ${who}, from your own record. Nothing is sent: you read it and press Send.`}
          </p>
          <Button className="mt-4 w-full" busy={busy === "prepare"} onClick={() => prepare()}>
            {o.prepare_status === "failed" ? "Try again" : o.route === "portal" ? "Prepare resume" : "Prepare letter"}
          </Button>
          {o.prepare_status === "failed" && o.prepare_error && <p role="alert" className="mt-2 text-[13px] text-bad">{o.prepare_error}</p>}
        </>
      )}
      <ErrorNote error={error} />
      <button type="button" disabled={busy !== null} onClick={() => act("dismiss", () => api.post(`/opportunities/${o.id}/dismiss`, { dismissed: !o.dismissed_at }))}
        className="mt-3 w-full rounded-lg py-1.5 text-sm font-medium text-muted hover:bg-sunken hover:text-text disabled:opacity-50">
        {o.dismissed_at ? "Bring it back to Today" : "Not for me"}
      </button>
    </section>
  );
}
