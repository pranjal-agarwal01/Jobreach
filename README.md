# Jobreach

A job seeker gives their real history once. Jobreach finds openings on its own (public company job
boards, careers pages, Hacker News), scores each one against their own work, and for the ones they
pick builds a truthful one-page resume and drafts the outreach email. Posts they find themselves
can be pasted too. **The person presses Send.** Jobreach never sends email, never submits
applications, and never touches LinkedIn. See [PRODUCT-SPEC.md](PRODUCT-SPEC.md) and
[docs/plan-global-pool.md](docs/plan-global-pool.md).

| Part | What | Where |
|---|---|---|
| Web app | Next.js 16, React 19, Tailwind 4, Supabase Auth | `frontend/` |
| API + pipeline | Python, FastAPI, background worker on a Postgres queue | `backend/app/` |
| Resume engine | python-docx builder, LibreOffice page check, calibration | `backend/resume_engine/` |
| Database | Supabase Postgres, row-level security on every per-user table | `supabase/migrations/` |
| AI | Azure OpenAI (GPT-6.1 Sol, GPT-6 Luna for extraction) or Claude, one setting; structured outputs, prompt caching | `backend/app/llm.py` |

## Run it locally (Windows)

Needs Python 3.10+, Node 20+, LibreOffice (`winget install TheDocumentFoundation.LibreOffice`).

1. **Backend secrets.** Copy `backend/.env.example` to `backend/.env` and fill in
   `DATABASE_URL` (Supabase → Connect → Session pooler) and the model provider's endpoint
   and key (Azure OpenAI by default; Claude is one setting away).
2. **Backend.**
   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install -r backend/requirements.txt
   cd backend
   ../.venv/Scripts/python -m uvicorn app.main:app --port 8000      # API
   ../.venv/Scripts/python -m app.worker                            # pipeline and pool, in a second terminal
   ../.venv/Scripts/python scripts/seed_boards.py                   # once: the pool's starting job boards
   ```
3. **Frontend.** `frontend/.env.local` holds only public values (copy `frontend/.env.example`).
   ```bash
   cd frontend
   npm install
   npm run dev          # http://localhost:3000
   ```

## Sign-up, once per user

1. **One form**: CVs, where they are (student, recent graduate, experienced), up to four kinds
   of role (role families, `app/taxonomy.py`), GitHub, portfolio and LinkedIn links, anything
   the CV leaves out, and the usual preferences. Defaults follow the stage.
2. **A background build** (`build_profile`, progress on `profiles.build`): read everything
   (GitHub repositories and up to six READMEs, the portfolio page; LinkedIn is never fetched),
   extract the profile, then hold every line to those documents in code (`app/provenance.py`).
   Lines that cannot be found are left out with the reason; nothing is asked. Full-time years
   come from job dates and set the experience band. One baseline resume per role family, with
   an honest fit and gaps, each rendered to one page.
3. **One review**: the profile in a sentence, the baselines, what was left out, and one
   question: add, remove or change anything? Finishing registers the user's
   (role family, band) segments with the opportunity pool.

`backend/scripts/acceptance_onboarding.py` runs the build on two made-up people with the real
model and renderer, without touching any account.

## The pipeline

Every opening is read once, for everyone it may suit (the global half), then scored for each
person (the per-user half). A pasted post goes through the same steps and stays private to the
person who pasted it.

| Step | Who | What |
|---|---|---|
| S1 extract | model (fast) | Post → structured fields: role, years asked for, required and nice-to-have skills, pay, apply routes; email addresses kept only if written in the post (`pipeline/extract.py`) |
| S2 screen | code | What rules an opening out for everyone: mills, money asks, recruiters/aggregators, geography (`pipeline/screen.py`) |
| S4 verify | code + model | DNS, MX, homepage (fetch locked to public hosts), business summary; cached 30 days |
| Contacts | code | Every published address with where it was published, in this order: the post (a named hiring manager or founder, then HR, then a hiring mailbox); a hiring address on the company's own site; the post's portal; the company's general inbox, flagged. Never guessed, never one published for press or support (`pipeline/contacts.py`) |
| S3 match | code | Per person: their rules (place, work mode, type, pay floor, batch, CGPA, freshness, one role per company), the kind of role and years of experience; then a score out of 100 with the reasons and gaps in words, and a group: strong, good or with gaps (`pipeline/match.py`) |
| S5 tailor | model | The baseline for that kind of role, tailored: items, bullets and skill order (ids only, validated), a summary held to the person's documents, and the title line from the post's role without a seniority the record lacks (`pipeline/select.py`) |
| S6 resume | code | Build, render with LibreOffice, one page or step down / drop a line; keep the page-checked PDF |
| S7 draft | model | Paragraphs to the chosen contact only; code renders HTML and appends the signature verbatim |
| S8 lint | code | Blocks em dashes, bare URLs, unpublished addresses, unbacked numbers, wrong length, narrowed availability; two rewrites with feedback |
| S9 deliver | person | Open the company's folder in Jobs: copy the email, download the PDF or copy a revocable share link, press Send |

S1 to contacts run once per opening (`pipeline/opportunity.py`). S5 to S8 run when the person
opens a match and presses "Prepare letter" (`pipeline/prepare.py`); a pasted post is prepared
straight away. Matching is code only, so it reruns whenever the profile, preferences or resumes
change.

## Gmail drafts and Google sign-in

People can sign in with Google, and connect Gmail once so every letter that passes its checks is
created as a draft in their own mailbox with the resume attached (`app/gmail.py`). Jobreach only
creates drafts; the code refuses any other Gmail call. Setup: [docs/gmail-setup.md](docs/gmail-setup.md).

## Your own agent

Someone who runs their own agent to find posts can have it send them to `POST /intake/leads`
with a personal key from Profile → Your agent. Each post becomes that person's private lead,
exactly like a paste (prepared automatically when it is a strong or good match), and can never
enter the shared pool. Format and limits: [docs/agent-intake.md](docs/agent-intake.md).

## The shared pool

Openings are collected on the server, once, for everyone they may suit (`app/pool.py`,
`app/sources/`). Nothing logs in anywhere and nothing reads LinkedIn.

- **Sources:** the public job feeds of company boards on Greenhouse, Lever and Ashby; the job
  listings on companies' own careers pages (schema.org JobPosting markup, robots.txt respected);
  the Hacker News "Who is hiring" thread.
- **Which boards:** a starting list (`scripts/seed_boards.py`), plus every board a company's own
  site links to. Companies enter through the company check, including every company a user
  pastes a post from.
- **When:** the worker queues a pool tick every 15 minutes. A board is read every 6 hours while
  some user needs a kind of role (a `pool_segments` row); a kind someone just started needing
  gets every board read for it at once. Nobody needs anything: nothing is read.
- **What is read:** code passes on postings nobody could want before any model sees them (a kind
  of role nobody targets, not in India or open to it, a seniority nobody needs). The rest go
  through the global half of the pipeline, five per task, below anything a person is waiting for.
- **Expiry:** a listing that leaves its board, or goes unseen for 30 days, expires; contact
  details of expired openings are deleted 30 days after they were last seen.
- **Prepared ahead:** each day, up to three of a person's strongest fresh matches get their letter
  and resume prepared before they open them, for people who used the app in the last week.

Settings (`backend/.env`): `POOL_ENABLED` (default 1), `POOL_TICK_MINUTES` (15),
`PREWARM_PER_DAY` (3). `backend/scripts/acceptance_pool.py` checks the pool live against real
boards.

Every model call is logged with tokens and cost (`llm_calls`); Profile → Usage shows it.

## Tests

```bash
cd backend
../.venv/Scripts/python -m pytest -q                                   # everything
../.venv/Scripts/python -m pytest -q --deselect tests/test_render.py   # without LibreOffice
```

Phase 1 acceptance: `backend/scripts/eval_extract.py` (S1 vs a human reading of 20 real
posts) and `backend/scripts/acceptance_phase1.py` (stored drafts, page counts, timing, cost).
`backend/scripts/acceptance_phase3.py` runs a made-up post from paste to letter, scores it for
two made-up people and checks the contact order, with the real model and renderer and no account.

`reference/` holds the original personal pipeline's files for parity tests. It is git-ignored
and never used as seed or test data.
