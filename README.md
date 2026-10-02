# Jobreach

A student gives their real history once. For every good, fresh opening they paste, Jobreach
screens it, checks the company is real, builds a truthful one-page resume from their confirmed
facts, and drafts the outreach email. **The student presses Send.** Jobreach never sends email,
never submits applications, and never touches LinkedIn. See [PRODUCT-SPEC.md](PRODUCT-SPEC.md).

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
   ../.venv/Scripts/python -m app.worker                            # pipeline, in a second terminal
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
