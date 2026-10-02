-- One-form onboarding builds the profile and baselines in the background. `build` records
-- where that is (status, step, error), what it suggested (other role families the record
-- supports) and when it ran, so the building and review screens can follow it.
alter table public.profiles add column if not exists build jsonb not null default '{}'::jsonb;
