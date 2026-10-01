-- Simpler onboarding, a global opportunity pool and per-user matching (docs/plan-global-pool.md).
-- Additive only: nothing is dropped or renamed here. role_options, pool_watches and
-- pool_watch_users go in phase 5, once the new flow is live.
--
-- Three concepts, three tables (names kept to avoid churn):
--   jobs     one real opening, found once. visibility = 'public' rows are the shared pool;
--            a pasted lead stays 'private' to the user who pasted it.
--   matches  how well one opening suits one user. Never shared.
--   applications (+ resumes, drafts, events)  what the user chose to pursue.

-- ------------------------------------------------------------------ profile: stage and experience

alter table public.profiles
  add column if not exists career_stage text check (career_stage in ('student', 'graduate', 'experienced')),
  add column if not exists experience_years numeric(4,1),      -- full-time years from work periods; editable
  add column if not exists experience_band text
    check (experience_band in ('intern', 'entry', 'junior', 'mid', 'senior', 'lead')),
  add column if not exists portfolio_url text,
  add column if not exists linkedin_url text;                  -- stored for the resume header, never fetched

alter table public.preferences
  add column if not exists target_families text[] not null default '{}',
  add column if not exists salary_floor int,                   -- per year, for full-time roles
  add column if not exists notice_period text;

-- 'data' became two families (app/taxonomy.py).
update public.preferences set role_types = array_replace(role_types, 'data', 'data_analytics')
  where 'data' = any(role_types);

-- ------------------------------------------------------------------ fact bank: where each line came from

-- `confirmed` now means "usable": set when a line passes the provenance check against the
-- user's own documents. provenance records the document and passage that backs it.
alter table public.items     add column if not exists provenance jsonb;
alter table public.bullets   add column if not exists provenance jsonb;
alter table public.entries   add column if not exists provenance jsonb;
alter table public.education add column if not exists provenance jsonb;
alter table public.facts     add column if not exists provenance jsonb;

-- ------------------------------------------------------------------ baselines: one track per role family

alter table public.tracks
  add column if not exists role_family text,
  add column if not exists fit text check (fit in ('strong', 'good', 'stretch')),
  add column if not exists fit_why text,
  add column if not exists gaps text[] not null default '{}';
alter table public.tracks alter column approved set default true;

-- ------------------------------------------------------------------ opportunities

-- Real columns for everything the pool filters or indexes on; extracted keeps the rest.
-- `source` already names where an opening came from; it gains the collector kinds.
alter table public.jobs
  add column if not exists title text,
  add column if not exists role_family text,
  add column if not exists role_families text[] not null default '{}',   -- the family and its neighbours
  add column if not exists employment_type text,
  add column if not exists exp_min numeric(4,1),
  add column if not exists exp_max numeric(4,1),
  add column if not exists experience_bands text[] not null default '{}',
  add column if not exists country text,
  add column if not exists city text,
  add column if not exists work_mode text check (work_mode in ('remote', 'hybrid', 'onsite', 'unknown')),
  add column if not exists pay_min numeric,
  add column if not exists pay_max numeric,
  add column if not exists pay_currency text,
  add column if not exists pay_period text check (pay_period in ('month', 'year', 'total')),
  add column if not exists skills_must text[] not null default '{}',
  add column if not exists skills_nice text[] not null default '{}',
  add column if not exists batch_years int[] not null default '{}',
  add column if not exists cgpa_min numeric(4,2),
  add column if not exists source_job_id text,
  add column if not exists apply_url text,
  add column if not exists dedupe_key text,
  add column if not exists last_seen_at timestamptz not null default now(),
  add column if not exists state text not null default 'active' check (state in ('active', 'expired', 'closed'));

alter table public.jobs drop constraint if exists jobs_source_check;
alter table public.jobs add constraint jobs_source_check
  check (source in ('paste', 'greenhouse', 'lever', 'ashby', 'hn', 'careers'));

-- Public openings may only come from collectors; a paste is always private.
alter table public.jobs drop constraint if exists jobs_public_source_check;
alter table public.jobs add constraint jobs_public_source_check
  check (visibility = 'private' or source <> 'paste');

create index if not exists jobs_pool_family_idx on public.jobs (role_family, state, posted_at desc)
  where visibility = 'public';
create index if not exists jobs_pool_families_gin on public.jobs using gin (role_families)
  where visibility = 'public';
create unique index if not exists jobs_source_job_idx on public.jobs (source, source_job_id)
  where visibility = 'public' and source_job_id is not null;
create unique index if not exists jobs_dedupe_idx on public.jobs (dedupe_key)
  where visibility = 'public' and dedupe_key is not null;

-- ------------------------------------------------------------------ contact candidates

-- Every published address an opening offers, with where it was published. Never guessed.
-- Rows for public openings are third-party personal data kept for the hiring purpose only:
-- the pool deletes them 30 days after their opening expires.
create table if not exists public.opportunity_contacts (
  id              uuid primary key default gen_random_uuid(),
  job_id          uuid not null references public.jobs(id) on delete cascade,
  email           text not null,
  person_name     text,
  person_role     text,
  context         text not null check (context in ('post_apply', 'careers_page', 'site_generic')),
  source_url      text,
  is_generic      boolean not null default false,   -- careers@, jobs@, hr@, hello@ ...
  domain_matches  boolean,                          -- the address is on the company's own domain
  confidence      numeric(3,2),
  created_at      timestamptz not null default now(),
  unique (job_id, email)
);
create index if not exists opportunity_contacts_job_idx on public.opportunity_contacts (job_id);

-- ------------------------------------------------------------------ per-user matches

alter table public.matches
  add column if not exists score numeric(5,1),
  add column if not exists bucket text check (bucket in ('strong', 'good', 'gaps')),
  add column if not exists why jsonb not null default '[]'::jsonb,
  add column if not exists gaps jsonb not null default '[]'::jsonb,
  add column if not exists contact_id uuid references public.opportunity_contacts(id) on delete set null,
  add column if not exists computed_at timestamptz,
  add column if not exists seen_at timestamptz,
  add column if not exists dismissed_at timestamptz;
create index if not exists matches_user_bucket_idx on public.matches (user_id, bucket, score desc)
  where dismissed_at is null;

alter table public.applications
  add column if not exists match_id uuid references public.matches(id) on delete set null,
  add column if not exists contact_id uuid references public.opportunity_contacts(id) on delete set null;

-- ------------------------------------------------------------------ the pool's bookkeeping

-- One row per (role family, experience band) some user needs. Collection runs per family
-- (sources return every level at once); a refresh updates all of that family's segments.
create table if not exists public.pool_segments (
  id               uuid primary key default gen_random_uuid(),
  role_family      text not null,
  experience_band  text not null check (experience_band in ('intern', 'entry', 'junior', 'mid', 'senior', 'lead')),
  status           text not null default 'active' check (status in ('active', 'paused')),
  demand           int not null default 0,         -- active users who need this segment
  last_run_at      timestamptz,
  next_run_at      timestamptz not null default now(),
  last_found       int,
  active_count     int not null default 0,
  created_at       timestamptz not null default now(),
  unique (role_family, experience_band)
);

-- Public company job boards the collectors poll (Greenhouse, Lever, Ashby). System only.
create table if not exists public.source_boards (
  id              uuid primary key default gen_random_uuid(),
  source          text not null check (source in ('greenhouse', 'lever', 'ashby')),
  board_token     text not null,
  company_id      uuid references public.companies(id) on delete set null,
  status          text not null default 'active' check (status in ('active', 'paused', 'dead')),
  last_polled_at  timestamptz,
  next_poll_at    timestamptz not null default now(),
  last_found      int,
  last_error      text,
  created_at      timestamptz not null default now(),
  unique (source, board_token)
);

-- ------------------------------------------------------------------ row-level security

alter table public.opportunity_contacts enable row level security;
create policy read_contacts on public.opportunity_contacts for select to authenticated
  using (exists (select 1 from public.jobs j where j.id = job_id
                 and (j.visibility = 'public' or j.owner_user_id = (select auth.uid()))));

alter table public.pool_segments enable row level security;
create policy read_segments on public.pool_segments for select to authenticated using (true);

alter table public.source_boards enable row level security;   -- no policies: backend only

revoke all on public.opportunity_contacts, public.pool_segments, public.source_boards from anon;
