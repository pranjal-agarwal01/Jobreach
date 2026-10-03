-- Curated posts: hiring posts the founder (or the founder's own agent) collects for everyone.
-- They enter the shared pool as public openings (source 'curated'), are read once, matched for
-- every user, and at most a few users get a letter prepared for each post, so no poster is sent
-- a pile of near-identical letters.
--
-- post_key: one post's identity however it arrives (its LinkedIn activity number, else its link,
-- else its text), so the same post is never in the pool twice.

alter table public.jobs drop constraint if exists jobs_source_check;
alter table public.jobs add constraint jobs_source_check
  check (source in ('paste', 'agent', 'curated', 'greenhouse', 'lever', 'ashby', 'hn', 'careers'));

alter table public.jobs add column if not exists post_key text;
create unique index if not exists jobs_public_post_key_idx on public.jobs (post_key)
  where visibility = 'public' and post_key is not null;

-- An intake key now says where its posts go: the key holder's own leads, or everyone's pool
-- (only accounts on the server's curator list can make a pool key).
alter table public.intake_keys add column if not exists scope text not null default 'private'
  check (scope in ('private', 'pool'));
