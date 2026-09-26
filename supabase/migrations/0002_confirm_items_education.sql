-- Nothing extracted from an upload reaches a resume until the user confirms it (spec 4.1).
-- Project/experience headers (name, period, stack) and education lines are claims too.
alter table public.items add column confirmed boolean not null default false;
alter table public.education add column confirmed boolean not null default false;

-- Skills listed on a track must each be backed by a confirmed skill fact; evidence_items
-- records which items or entries back a skill (the onboarding evidence check).
alter table public.facts add column evidence_items text[] not null default '{}';
