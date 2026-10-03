-- Phase 4 of docs/plan-global-pool.md: the shared pool collects openings by itself, on the
-- server, from public sources (Greenhouse, Lever and Ashby job boards, Hacker News "Who is
-- hiring", job listings on company careers pages). No logins, no LinkedIn. Additive only.

-- Pool work runs below anything a person is waiting for: a letter being prepared is claimed
-- before the next job board is read.
alter table public.task_queue add column if not exists priority int not null default 10;
create index if not exists task_queue_claim_idx on public.task_queue (priority desc, id) where status = 'queued';

-- Which board a public opening came from, so a listing that leaves its board expires.
alter table public.jobs add column if not exists board_id uuid references public.source_boards(id) on delete set null;
create index if not exists jobs_board_idx on public.jobs (board_id) where board_id is not null;

-- When a company's own site was last read for its job board and its listed openings.
alter table public.companies add column if not exists careers_checked_at timestamptz;

-- A segment nobody has needed for 14 days pauses; this records since when.
alter table public.pool_segments add column if not exists idle_since timestamptz;

-- Phase 5: a few strong, fresh matches are prepared before the person opens them.
alter table public.matches add column if not exists prewarmed_at timestamptz;
alter table public.profiles add column if not exists last_active_at timestamptz;
