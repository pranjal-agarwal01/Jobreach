-- Phase 5 of docs/plan-global-pool.md: the founder's 2026-10-01 role flow is gone. Its role
-- audit (role_options) and its per-role search registrations (pool_watches, pool_watch_users)
-- are replaced by preferences.target_families, tracks (one baseline per role family) and
-- pool_segments. No code reads or writes these tables since phase 2.
--
-- onboarding_messages (the old interview) is kept, read-only, for now: it holds what users
-- typed, and nothing new is written to it.

drop table if exists public.pool_watch_users;
drop table if exists public.pool_watches;
drop table if exists public.role_options;
