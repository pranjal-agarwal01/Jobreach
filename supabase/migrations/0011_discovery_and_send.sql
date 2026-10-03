-- Two additions.
--
-- 1. Discovery (app/discover.py): companies found without anyone searching, from Y Combinator's
--    public directory (companies marked as hiring) and startup funding news. Each joins the
--    companies the pool scans for a careers page, a job board and a hiring address.
--
-- 2. Send for me (app/send.py): an opt-in. When a person turns it on, letters that passed every
--    check and are in their Gmail drafts are sent from their Gmail at a random moment inside the
--    window they chose, at most a set number a day, and never sooner than a waiting period after
--    the letter was written (they can edit it in Gmail or cancel it until then). Off by default:
--    without it, Jobreach only creates drafts and the person presses Send.

-- ------------------------------------------------------------------ discovery

alter table public.companies
  add column if not exists discovered_via  text check (discovered_via in ('yc', 'funding_news')),
  add column if not exists discovered_at   timestamptz,
  add column if not exists discovery_note  text,        -- "Raised a Series A of $5M (Inc42)"
  add column if not exists discovery_url   text;        -- the article or directory page

-- What each feed has already been read for (an article, a YC company), so nothing is read twice.
create table if not exists public.discovery_items (
  feed        text not null,                -- 'yc', 'inc42', 'yourstory', ...
  item_key    text not null,                -- the article link, or the YC company's slug
  title       text,
  companies   int not null default 0,       -- companies it added
  seen_at     timestamptz not null default now(),
  primary key (feed, item_key)
);
alter table public.discovery_items enable row level security;
revoke all on public.discovery_items from anon, authenticated;

-- ------------------------------------------------------------------ send for me

alter table public.preferences
  add column if not exists auto_send               boolean not null default false,
  add column if not exists auto_send_window_start  time not null default '14:00',
  add column if not exists auto_send_window_end    time not null default '17:00',
  add column if not exists auto_send_timezone      text not null default 'Asia/Kolkata',
  add column if not exists auto_send_daily_cap     int not null default 10
                           check (auto_send_daily_cap between 1 and 20),
  add column if not exists auto_send_grace_minutes int not null default 120
                           check (auto_send_grace_minutes between 30 and 1440),
  add column if not exists auto_send_enabled_at    timestamptz,
  add column if not exists auto_send_paused_reason text;

alter table public.drafts
  add column if not exists send_at               timestamptz,   -- when Jobreach will send it
  add column if not exists send_cancelled_at     timestamptz,   -- the person said "don't send this one"
  add column if not exists gmail_sent_at         timestamptz,   -- sent by Jobreach
  add column if not exists gmail_sent_message_id text,
  add column if not exists send_error            text;
create index if not exists drafts_send_at_idx on public.drafts (user_id, send_at) where send_at is not null;

-- A letter Jobreach sent is recorded as sent through Gmail.
alter table public.events drop constraint if exists events_source_check;
alter table public.events add constraint events_source_check check (source in ('manual', 'gmail', 'jobreach'));
