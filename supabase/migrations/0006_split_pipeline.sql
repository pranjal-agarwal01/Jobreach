-- Phase 3 of docs/plan-global-pool.md: the pipeline splits into a global half (one opening,
-- read once: extraction, the screens that apply to everyone, the company check, contact
-- candidates) and a per-user half (eligibility, a match score with reasons and gaps, then a
-- tailored resume and letter when the user wants one). Additive only.

-- The screen that applies to everyone (money asks, mills, intermediaries, geography). A
-- per-user screen still lands in matches.screen.
alter table public.jobs add column if not exists screen jsonb;

-- Hiring addresses published on a company's own site, harvested at most once a month per
-- domain: [{email, context, source_url, evidence}]. Only role addresses (careers@, jobs@,
-- hello@ ...); a named person's address on a web page has no stated purpose and is never kept.
alter table public.companies
  add column if not exists site_emails jsonb not null default '[]'::jsonb,
  add column if not exists site_emails_at timestamptz;

-- The sentence an address was published in, so the user can see why it is a hiring address.
alter table public.opportunity_contacts add column if not exists evidence text;

-- Preparing a letter and a tailored resume for one match (on open, or straight away for a
-- pasted post).
alter table public.matches
  add column if not exists prepare_status text
    check (prepare_status in ('queued', 'running', 'done', 'failed')),
  add column if not exists prepare_error text;
