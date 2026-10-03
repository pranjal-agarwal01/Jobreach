-- Letters drafted in the person's own Gmail (app/gmail.py). The person connects Gmail once; each
-- prepared letter is then created as a draft there, with the resume PDF attached. Jobreach only
-- ever creates drafts: the person opens Gmail and presses Send.

-- One connection per person. The refresh token is encrypted with a key only the backend holds,
-- and the table has no policies: no signed-in user can read it through the database API, not
-- even its owner. The backend reads it for that person only.
create table if not exists public.gmail_connections (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  email              text not null,                -- the Gmail address the drafts go into
  refresh_token_enc  text not null,
  scope              text not null,
  connected_at       timestamptz not null default now(),
  last_used_at       timestamptz,
  status             text not null default 'active' check (status in ('active', 'expired')),
  last_error         text
);
alter table public.gmail_connections enable row level security;
revoke all on public.gmail_connections from anon, authenticated;

-- Where each letter landed in Gmail (drafts.gmail_draft_id exists since 0001).
alter table public.drafts
  add column if not exists gmail_message_id text,
  add column if not exists gmail_drafted_at timestamptz,
  add column if not exists gmail_error text;
