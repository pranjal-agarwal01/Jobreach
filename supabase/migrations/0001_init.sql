-- Jobreach schema, Phase 1 (PRODUCT-SPEC.md section 8.2).
--
-- Tenancy: every per-user table carries user_id and has row-level security that limits
-- a signed-in user to their own rows. The backend runs user-scoped work under the
-- `authenticated` role with the user's id in request.jwt.claims, so RLS applies to the
-- backend too, not only to direct API access. Shared tables (companies, public jobs) are
-- readable by any signed-in user and written only by the backend.
--
-- Deleting a user from auth.users cascades to every row they own (DPDP deletion).

-- ------------------------------------------------------------------ profile & consent

create table public.profiles (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  name             text,
  headline         text,
  location         text,
  phone            text,
  email            text,
  links            jsonb not null default '[]'::jsonb,      -- [{text, url}]
  about            text,
  grad_date        text,
  batch_year       int,
  cgpa             numeric(4,2),
  onboarding_step  text not null default 'upload',
  consent_version  text,
  consented_at     timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create table public.preferences (
  user_id                 uuid primary key references auth.users(id) on delete cascade,
  role_types              text[] not null default '{}',
  open_to                 text[] not null default '{internship}',   -- internship, full_time
  locations               text[] not null default '{}',
  remote_ok               boolean not null default true,
  onsite_ok               boolean not null default true,
  hybrid_ok               boolean not null default true,
  stipend_floor           int,
  currency                text not null default 'INR',
  unpaid_remote_policy    text not null default 'draft_with_floor'
                          check (unpaid_remote_policy in ('draft_with_floor', 'drop')),
  unpaid_onsite_policy    text not null default 'drop'
                          check (unpaid_onsite_policy in ('draft_with_floor', 'drop')),
  excluded_company_types  text[] not null default '{big_tech}',
  excluded_companies      text[] not null default '{}',
  freshness_ceiling_hours int not null default 72,
  duration_flex           text not null default 'Flexible on duration',
  start_date              text not null default 'Immediately',
  signature_html          text,
  format_settings         jsonb not null default '{}'::jsonb,
  updated_at              timestamptz not null default now()
);

-- Onboarding inputs. Only extracted text is kept; uploaded files are not stored.
create table public.source_documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        text not null check (kind in ('resume', 'about', 'links', 'other')),
  filename    text,
  text        text not null,
  created_at  timestamptz not null default now()
);

create table public.onboarding_messages (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        text not null check (role in ('assistant', 'user')),
  content     text not null,
  created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------------ fact bank

create table public.facts (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  kind           text not null check (kind in ('project', 'role', 'award', 'education', 'skill', 'metric', 'other')),
  text           text not null,
  value          text,
  source         text not null default 'upload' check (source in ('upload', 'interview', 'edit')),
  evidence_note  text,
  confirmed_at   timestamptz,
  created_at     timestamptz not null default now()
);
create index facts_user_idx on public.facts (user_id);

-- Left-column blocks: projects and experience entries.
create table public.items (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  key          text not null,
  kind         text not null default 'project' check (kind in ('project', 'experience')),
  name         text not null,
  tagline      text,
  period       text,
  stack        text,
  stack_label  text not null default 'Stack',
  links        jsonb not null default '[]'::jsonb,
  sort         int not null default 0,
  created_at   timestamptz not null default now(),
  unique (user_id, key)
);

create table public.bullets (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  item_id     uuid not null references public.items(id) on delete cascade,
  text        text not null,
  fact_ids    uuid[] not null default '{}',
  has_metric  boolean not null default false,
  confirmed   boolean not null default false,
  sort        int not null default 0,
  created_at  timestamptz not null default now()
);
create index bullets_user_idx on public.bullets (user_id);

-- Right-column bullet sections (awards, roles, certifications ...).
create table public.resume_sections (
  id       uuid primary key default gen_random_uuid(),
  user_id  uuid not null references auth.users(id) on delete cascade,
  key      text not null,
  heading  text not null,
  style    text not null default 'detail' check (style in ('list', 'detail')),
  sort     int not null default 0,
  unique (user_id, key)
);

create table public.entries (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  section_id  uuid not null references public.resume_sections(id) on delete cascade,
  lead        text,
  text        text not null,
  tracks      text[],                      -- null = every track
  fact_ids    uuid[] not null default '{}',
  confirmed   boolean not null default false,
  sort        int not null default 0,
  created_at  timestamptz not null default now()
);

create table public.education (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  institution  text not null,
  degree       text,
  meta         text,
  result       text,
  lines        text[] not null default '{}',
  sort         int not null default 0
);

create table public.tracks (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  key            text not null,
  label          text not null,
  title_line     text not null,
  summary        text not null default '',
  left_sections  jsonb not null default '[]'::jsonb,   -- [{heading, item_keys: []}]
  skills         jsonb not null default '[]'::jsonb,   -- [{label, items}]
  scale          numeric(4,3),
  calibrated_at  timestamptz,
  approved       boolean not null default false,
  sort           int not null default 0,
  unique (user_id, key)
);

-- ------------------------------------------------------------------ shared: companies

create table public.companies (
  id                uuid primary key default gen_random_uuid(),
  name              text not null,
  domain            text unique,
  dns_ok            boolean,
  mx_ok             boolean,
  homepage_ok       boolean,
  business_summary  text,
  business_type     text,       -- product, service, staffing, msp, training, placement, unknown
  is_intermediary   boolean,
  size_band         text,
  verification      text check (verification in ('pass', 'flag', 'fail')),
  flags             jsonb not null default '[]'::jsonb,
  checked_at        timestamptz,
  created_at        timestamptz not null default now()
);

-- ------------------------------------------------------------------ leads ("jobs")

-- Pasted leads are private to the user who pasted them: a pasted post carries a third
-- party's name and email, and pooling it would redistribute that content.
create table public.jobs (
  id                     uuid primary key default gen_random_uuid(),
  visibility             text not null default 'private' check (visibility in ('private', 'public')),
  owner_user_id          uuid references auth.users(id) on delete cascade,
  source                 text not null default 'paste',
  source_ref             text,
  found_by               text,        -- the exact search or source that found it
  raw_text               text not null,
  content_hash           text not null,
  extracted              jsonb,
  company_id             uuid references public.companies(id),
  posted_age_hours       numeric,     -- at capture, from the post's own age label
  posted_at              timestamptz,
  status                 text not null default 'queued'
                         check (status in ('queued', 'processing', 'done', 'failed')),
  error                  text,
  first_seen_at          timestamptz not null default now(),
  check (visibility = 'public' or owner_user_id is not null)
);
create unique index jobs_owner_hash_idx on public.jobs (owner_user_id, content_hash);

create table public.matches (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  job_id      uuid not null references public.jobs(id) on delete cascade,
  decision    text not null check (decision in ('keep', 'drop', 'flag')),
  reasons     jsonb not null default '[]'::jsonb,
  screen      jsonb,                   -- S2 global screen result
  track_key   text,
  rank        numeric,
  overridden  boolean not null default false,
  created_at  timestamptz not null default now(),
  unique (user_id, job_id)
);

-- One application per (user, company): the idempotency key for "one role per company".
create table public.applications (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users(id) on delete cascade,
  job_id               uuid not null references public.jobs(id) on delete cascade,
  company_id           uuid references public.companies(id),
  company_key          text not null,
  role_title           text,
  track_key            text,
  route                text not null check (route in ('email', 'portal')),
  apply_to             text,           -- the published address or form link
  status               text not null default 'drafted'
                       check (status in ('drafted', 'needs_review', 'sent', 'replied', 'interview',
                                         'assignment', 'rejected', 'bounced', 'closed')),
  found_by             text,
  age_at_capture_hours numeric,
  age_at_draft_hours   numeric,
  judgment_calls       jsonb not null default '[]'::jsonb,
  notes                text,
  created_at           timestamptz not null default now(),
  user_marked_sent_at  timestamptz,
  unique (user_id, company_key)
);

create table public.resume_files (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  filename    text not null,
  content     bytea not null,
  created_at  timestamptz not null default now()
);

create table public.resumes (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  application_id  uuid references public.applications(id) on delete cascade,
  track_key       text not null,
  is_baseline     boolean not null default false,
  file_id         uuid not null references public.resume_files(id) on delete cascade,
  item_keys       text[] not null default '{}',
  bullet_ids      uuid[] not null default '{}',
  entry_ids       uuid[] not null default '{}',
  dropped_ids     text[] not null default '{}',
  scale           numeric(4,3) not null,
  pages_verified  int not null,
  renderer        text not null,
  ats_score       numeric,
  jd_match        numeric,
  created_at      timestamptz not null default now()
);

create table public.drafts (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  application_id   uuid not null references public.applications(id) on delete cascade,
  to_addrs         text[] not null default '{}',
  cc_addrs         text[] not null default '{}',
  subject          text not null,
  html             text not null,
  facts_used       jsonb not null default '[]'::jsonb,
  lint             jsonb not null default '[]'::jsonb,
  lint_ok          boolean not null,
  gmail_draft_id   text,
  version          int not null default 1,
  idempotency_key  text not null unique,
  created_at       timestamptz not null default now()
);

create table public.events (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  application_id  uuid not null references public.applications(id) on delete cascade,
  type            text not null check (type in ('sent', 'reply', 'bounce', 'interview', 'assignment',
                                                'rejection', 'auto_ack', 'gated_unpaid', 'form_request', 'other')),
  occurred_at     timestamptz not null default now(),
  deadline_at     timestamptz,
  source          text not null default 'manual' check (source in ('manual', 'gmail')),
  summary         text,
  created_at      timestamptz not null default now()
);

-- ------------------------------------------------------------------ system

create table public.llm_calls (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid references auth.users(id) on delete cascade,
  job_id              uuid references public.jobs(id) on delete set null,
  application_id      uuid references public.applications(id) on delete set null,
  step                text not null,
  model               text not null,
  input_tokens        int not null default 0,
  output_tokens       int not null default 0,
  cache_read_tokens   int not null default 0,
  cache_write_tokens  int not null default 0,
  cost_usd            numeric(10,5) not null default 0,
  latency_ms          int,
  stop_reason         text,
  created_at          timestamptz not null default now()
);

create table public.task_queue (
  id            bigserial primary key,
  user_id       uuid references auth.users(id) on delete cascade,
  kind          text not null,
  payload       jsonb not null default '{}'::jsonb,
  status        text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
  attempts      int not null default 0,
  max_attempts  int not null default 3,
  run_after     timestamptz not null default now(),
  locked_at     timestamptz,
  locked_by     text,
  last_error    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index task_queue_ready_idx on public.task_queue (run_after) where status = 'queued';

create table public.audit_log (
  id          bigserial primary key,
  user_id     uuid,
  action      text not null,
  detail      jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------------ indexes on user_id

create index items_user_idx        on public.items (user_id);
create index entries_user_idx      on public.entries (user_id);
create index education_user_idx    on public.education (user_id);
create index sections_user_idx     on public.resume_sections (user_id);
create index srcdocs_user_idx      on public.source_documents (user_id);
create index onbmsg_user_idx       on public.onboarding_messages (user_id);
create index matches_user_idx      on public.matches (user_id);
create index resumes_user_idx      on public.resumes (user_id);
create index resume_files_user_idx on public.resume_files (user_id);
create index drafts_user_idx       on public.drafts (user_id);
create index drafts_app_idx        on public.drafts (application_id);
create index events_user_idx       on public.events (user_id);
create index events_app_idx        on public.events (application_id);
create index llm_calls_user_idx    on public.llm_calls (user_id);
create index applications_job_idx  on public.applications (job_id);
create index jobs_company_idx      on public.jobs (company_id);

-- ------------------------------------------------------------------ row-level security

do $$
declare t text;
begin
  -- Per-user tables: a signed-in user sees and changes only their own rows.
  foreach t in array array[
    'profiles', 'preferences', 'source_documents', 'onboarding_messages', 'facts', 'items',
    'bullets', 'resume_sections', 'entries', 'education', 'tracks', 'matches', 'applications',
    'resume_files', 'resumes', 'drafts', 'events'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy own_rows on public.%I for all to authenticated
         using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))', t);
  end loop;

  -- System tables: RLS on, no policies. Only the backend (table owner) touches them.
  foreach t in array array['task_queue', 'audit_log'] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

alter table public.llm_calls enable row level security;
create policy own_usage on public.llm_calls for select to authenticated
  using (user_id = (select auth.uid()));

alter table public.companies enable row level security;
create policy read_companies on public.companies for select to authenticated using (true);

alter table public.jobs enable row level security;
create policy read_jobs on public.jobs for select to authenticated
  using (visibility = 'public' or owner_user_id = (select auth.uid()));
create policy write_own_jobs on public.jobs for insert to authenticated
  with check (visibility = 'private' and owner_user_id = (select auth.uid()));
create policy update_own_jobs on public.jobs for update to authenticated
  using (owner_user_id = (select auth.uid())) with check (owner_user_id = (select auth.uid()));
create policy delete_own_jobs on public.jobs for delete to authenticated
  using (owner_user_id = (select auth.uid()));

-- Nothing is readable without signing in.
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
