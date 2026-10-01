-- Onboarding as the founder described it (2026-10-01): one sign-up form, an audit of
-- everything the student gives, the roles that audit supports, a choice of specific roles or
-- a mixed pool, and a job pool that starts collecting for any role it does not cover yet.
-- Resumes are delivered as PDF, from per-company folders, as a download or a share link.

-- ------------------------------------------------------------------ sign-up inputs

alter table public.profiles add column if not exists github_url text;

-- role_types keeps holding discipline keys (the S3 filter). target_roles holds the job titles
-- the student chose from the audit; pool_mode says whether they picked roles or took the mix.
alter table public.preferences add column if not exists desired_roles text[] not null default '{}';
alter table public.preferences add column if not exists target_roles text[] not null default '{}';
alter table public.preferences add column if not exists pool_mode text not null default 'mix'
  check (pool_mode in ('specific', 'mix'));

-- ------------------------------------------------------------------ role audit

create table public.role_options (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  field               text not null,              -- a discipline key, as S1 extracts it
  role                text not null,              -- a job title as companies post it
  fit                 text not null check (fit in ('strong', 'good', 'stretch')),
  why                 text not null default '',
  evidence_item_keys  text[] not null default '{}',
  gaps                text[] not null default '{}',
  desired             boolean not null default false,   -- the student asked for it at sign-up
  selected            boolean not null default false,
  sort                int not null default 0,
  created_at          timestamptz not null default now(),
  unique (user_id, field, role)
);
create index role_options_user_idx on public.role_options (user_id);

-- ------------------------------------------------------------------ job pool watches

-- One row per (field, role) the pool should collect. Shared and free of personal data; the
-- daily collector (Phase 3) reads it. Users see watches, only the backend writes them.
create table public.pool_watches (
  id           uuid primary key default gen_random_uuid(),
  field        text not null,
  role         text not null,
  role_norm    text not null,
  status       text not null default 'active' check (status in ('active', 'paused')),
  last_run_at  timestamptz,
  last_found   int,
  created_at   timestamptz not null default now(),
  unique (field, role_norm)
);

create table public.pool_watch_users (
  watch_id    uuid not null references public.pool_watches(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (watch_id, user_id)
);
create index pool_watch_users_user_idx on public.pool_watch_users (user_id);

create index if not exists jobs_pool_field_idx on public.jobs ((extracted->>'discipline'), first_seen_at)
  where visibility = 'public';

-- ------------------------------------------------------------------ PDF resumes and share links

alter table public.resume_files add column if not exists pdf bytea;
alter table public.resume_files add column if not exists pdf_filename text;

-- A share link is a random token the student can revoke. The public endpoint looks it up as
-- the backend's own role; users only ever see their own links.
create table public.resume_links (
  token       text primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  resume_id   uuid not null references public.resumes(id) on delete cascade,
  opens       int not null default 0,
  last_opened_at timestamptz,
  revoked_at  timestamptz,
  created_at  timestamptz not null default now()
);
create index resume_links_resume_idx on public.resume_links (resume_id);
create index resume_links_user_idx on public.resume_links (user_id);

-- ------------------------------------------------------------------ row-level security

do $$
declare t text;
begin
  foreach t in array array['role_options', 'pool_watch_users', 'resume_links'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy own_rows on public.%I for all to authenticated
         using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))', t);
  end loop;
end $$;

alter table public.pool_watches enable row level security;
create policy read_watches on public.pool_watches for select to authenticated using (true);

revoke all on public.role_options, public.pool_watches, public.pool_watch_users, public.resume_links from anon;
