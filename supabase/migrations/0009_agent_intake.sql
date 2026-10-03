-- A person's own agent can hand Jobreach the posts it finds for them (docs/agent-intake.md).
-- It authenticates with a personal intake key, not the person's login. Each post becomes a
-- private lead of that person, exactly like one they pasted, and can never enter the shared
-- pool.

-- Keys are random and shown once; only their SHA-256 is stored (the prefix identifies a key in
-- the app without revealing it).
create table if not exists public.intake_keys (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  name          text not null,
  prefix        text not null,
  key_hash      text not null unique,
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz,
  revoked_at    timestamptz
);
create index if not exists intake_keys_user_idx on public.intake_keys (user_id);

alter table public.intake_keys enable row level security;
create policy own_keys on public.intake_keys for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
revoke all on public.intake_keys from anon;

-- 'agent': a post the person's own agent found. Private, like a paste.
alter table public.jobs drop constraint if exists jobs_source_check;
alter table public.jobs add constraint jobs_source_check
  check (source in ('paste', 'agent', 'greenhouse', 'lever', 'ashby', 'hn', 'careers'));
alter table public.jobs drop constraint if exists jobs_public_source_check;
alter table public.jobs add constraint jobs_public_source_check
  check (visibility = 'private' or source not in ('paste', 'agent'));
