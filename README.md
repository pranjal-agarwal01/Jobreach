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

## The pipeline, per pasted lead

| Step | Who | What |
|---|---|---|
| S1 extract | Claude, low effort | Post → structured fields; email addresses kept only if written in the post |
| S2 screen | code | Mills, money asks, recruiters/aggregators, no apply route, geography |
| S3 match | code | The student's preferences: location, stipend floor, batch year, CGPA, freshness, one role per company |
| S4 verify | code + Claude | DNS, MX, homepage (fetch locked to public hosts), business summary; cached 30 days |
| S5 select | Claude, medium | Track, item order, bullets: ids only, validated against confirmed bullets |
| S6 resume | code | Build, render with LibreOffice, one page or step down / drop a line |
| S7 draft | Claude, medium | Paragraphs only; code renders HTML and appends the signature verbatim |
| S8 lint | code | Blocks em dashes, bare URLs, unpublished addresses, unbacked numbers, wrong length, narrowed availability; two rewrites with feedback |
| S9 deliver | student | Copy email, Open in Gmail, download `.docx`, press Send |

Every model call is logged with tokens and cost (`llm_calls`); Profile → Usage shows it.

## Tests

```bash
cd backend
../.venv/Scripts/python -m pytest -q                                   # everything
../.venv/Scripts/python -m pytest -q --deselect tests/test_render.py   # without LibreOffice
```

Phase 1 acceptance: `backend/scripts/eval_extract.py` (S1 vs a human reading of 20 real
posts) and `backend/scripts/acceptance_phase1.py` (stored drafts, page counts, timing, cost).

`reference/` holds the original personal pipeline's files for parity tests. It is git-ignored
and never used as seed or test data.
