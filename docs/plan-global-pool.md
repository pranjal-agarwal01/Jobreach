# Plan: simpler onboarding, global opportunity pool, per-user matching

Status: agreed 2026-10-01. All five phases built (2026-10-03). onboarding_messages is kept read-only for now.
It changes the founder's flow from 2026-10-01 (commit 2b67578) and spec sections 4.1, 4.2 and 13 (Phase 3).

## 0. Where this plan departs from the brief, and why

1. **No per-line approval, but the guardrail moves into code.**
   - Spec principle 2 says every line traces to a *confirmed* fact.
   - Without approval, "confirmed" becomes "found in the user's own documents".
   - Every extracted line is checked against the source text before it can be used:
     - each number in it must appear in the source;
     - each technology in it must appear in the source;
     - its wording must largely match a line or passage of the source.
   - Lines that fail are left out, never asked about.
   - The review screen lists them under "Left out" so the user can restore one with a click.
2. **Experience bands must not leave gaps.**
   - The brief's bands (1-2, then 3-5) leave nobody with 2 to 3 years.
   - Bands here are half-open intervals: `intern` (student, internship), `entry` 0-1, `junior` 1-3, `mid` 3-5, `senior` 5-8, `lead` 8+.
   - A post's requirement is stored as numbers (`exp_min`, `exp_max`) plus the *set* of bands it overlaps. "2-4 years" sits in junior and mid.
   - Eligibility compares numbers, with one year of tolerance marked as a gap. Bands are for pools and display only.
3. **A pool is a bookkeeping row, not a separate search.**
   - Job sources return all seniority levels at once. One Greenhouse board lists every opening that company has.
   - So collection runs per *role family*, never per (family, band).
   - `pool_segments(role_family, experience_band)` keeps the brief's check ("does Fresher + Backend exist?") and holds the status, refresh times and active count.
   - Refreshing a family updates every one of its segments. "Fresher Backend" and "3-5 yr Backend" never pay for the same fetch twice.
4. **Which contact to use depends on where the address was published, not on how senior the person is.**
   - A founder's address on a press page is not an invitation to apply. Writing there hurts the user.
   - Order of preference:
     1. An address the post itself gives for applying. Within that: a named hiring manager or founder, then HR, then a generic mailbox.
     2. A hiring address on the company's own careers page.
     3. A generic company address (hello@, contact@), used only with a visible flag.
   - Never used:
     - an address published for another purpose (press, support, investors, blog authors);
     - anything not written verbatim;
     - anything pattern-guessed.
5. **Matching runs in two stages to keep cost flat as users grow.**
   - Stage 1 is code only, for every eligible user and opportunity pair: eligibility rules, then a score. The score weighs:
     - required skills the user has, counting skills a project shows above skills only listed;
     - role family match;
     - experience fit;
     - freshness;
     - whether there is a usable contact.
   - The code also writes "why it matches" and the gaps, for example "FastAPI: used in Invoice API" and "asks for Kubernetes".
   - Stage 2 is the model (S5 select), and runs only when an application is prepared.
   - A per-pair model call would cost about 1,000 users × 200 new opportunities = 200k calls a day.
6. **Prepare on open, pre-warm only a few.**
   - Writing a letter and resume for every match of every user is the expensive path.
   - Pasted leads keep auto-drafting, because the user showed intent by pasting.
   - Pool matches are prepared when the user opens one (about 40 s, with a progress state).
   - The top 3 strong fresh matches per user per day are prepared ahead. The number is a setting.
   - This changes the earlier decision "draft automatically for every kept lead" for pool matches only.
7. **Freshness is measured differently per source.**
   - The 72-hour ceiling comes from founder posts on LinkedIn.
   - A Greenhouse opening is still valid after 10 days.
   - Social posts: 72-hour ceiling, as now.
   - Job-board and careers-page listings: valid while the company still lists them, ranked by age.
8. **Set expectations about supply.**
   - The public feeds (Greenhouse, Lever, Ashby, careers pages) skew to funded companies and to portal applications. Spec 11.3 says these converted worst.
   - The best-converting source, fresh founder posts on LinkedIn, cannot be automated (spec 11.1).
   - So the pool gives breadth, and pasting stays the high-converting channel. Both feed the same per-user pipeline.
9. **Keep the role audit as a signal, not a screen.**
   - Each baseline shows an honest fit (strong, good or stretch, with the gaps) on the review screen.
   - Roles the evidence strongly supports but the user did not list appear as optional suggestions there. No extra question.
10. **Defaults depend on career stage.**
    - Today's defaults suit a student: `open_to = internship` and `excluded_company_types = big_tech`.
    - For experienced users they are wrong: full-time, no company types excluded, a salary floor per year instead of a stipend per month, and a notice period.
11. **LinkedIn links are stored, not read** (spec 11.1).
    - A user who wants their LinkedIn history included uploads LinkedIn's own "Save to PDF" export of their profile.
    - GitHub stays: public API, the user's own repos.
    - We also read up to 6 READMEs, since there is no interview any more to fill gaps.
    - Portfolio sites are fetched with the existing SSRF-safe fetcher.
12. **Keep the table names.**
    - `jobs` is the global opportunity table, and already has `visibility = public | private` with RLS.
    - `matches` is the user-opportunity match table.
    - Renaming them touches about 40 SQL strings for no behaviour change. The code and docs use the new words.

## A. Architecture

```
GLOBAL PIPELINE  (system role; shared rows; no user data)
  scheduler tick ──► pool_segments due ──► refresh_family(role_family)
      sources: ATS boards (Greenhouse, Lever, Ashby), HN "Who is hiring", careers pages of verified companies
      ──► title pre-filter (code: only titles that map to a watched family get extracted)
      ──► S1 extract (Luna) ──► normalise: role family, experience range → bands, work mode, pay, must/nice skills
      ──► dedupe (source job id, then domain + title + city) ──► S4 verify company (cached 30 days, unchanged)
      ──► contact candidates with provenance ──► jobs (visibility = public, state = active)
      ──► fan-out: enqueue match for users in the affected segments
  expiry: a listing gone from its board, or 30 days unseen ──► state = expired

PRIVATE LEAD  (pasted by one user)
  same S1 → contacts steps; the row stays visibility = private, owner only; never pooled

PER-USER PIPELINE  (user_tx, RLS)
  profile + baselines (one per target role family)
  + active opportunities in the user's families and neighbours
      ──► S3 eligibility (code: experience, mode, place, pay, employment type, batch, CGPA,
          excluded companies, one role per company, freshness)
      ──► match score, bucket (strong / good / gaps), reasons, gaps (code) ──► matches
  user opens a match (or top-3 pre-warm)
      ──► choose baseline (best family) ──► S5 select + order (model, ids only)
      ──► S6 tailored one-page resume (title line, summary and skill order may change; only the user's own facts)
      ──► choose contact ──► S7 draft ──► S8 lint (+ rewrites) ──► application (drafted / needs_review)
  USER REVIEWS AND SENDS ──► marks sent ──► outcomes
```

## B. End-to-end user flow

1. **Sign in.** Consent is a checkbox in the form (DPDP requires it), not a step of its own.
2. **One form** (about 3 minutes):
   - CV files;
   - optional free text for education, experience, projects and skills, when the CV doesn't cover them;
   - links (GitHub, portfolio, LinkedIn);
   - target roles, as chips that show the role family each maps to;
   - stage: student looking for internships, recent graduate, or experienced / switching;
   - locations and work mode;
   - employment type;
   - pay floor (stipend per month or CTC per year);
   - notice period or start date;
   - companies to skip.
3. **Build** (1 to 2 minutes, progress screen, nothing asked). Steps:
   1. extract;
   2. provenance check;
   3. years of experience from work periods (internships not counted) and the band;
   4. skill evidence;
   5. one track per target family, with fit;
   6. calibrate and render one-page baselines;
   7. register pool segments;
   8. match against the opportunities already in the pool, so a user whose segments exist sees matches at once.
4. **Review.** One screen shows:
   - the profile summary ("3.2 years, mid band, targeting SDE and AI/ML");
   - each baseline as a PDF preview with its fit and gaps;
   - the "Left out" lines.

   The only question: "Would you like to add, remove or change anything in your profile or resumes?" Every field edits in place, and an edit re-renders the affected baselines. "Looks good" finishes onboarding.
5. **Dashboard (Today).** A sentence about the user, then:
   - strong, good and "with gaps" groups;
   - each card shows company, role, freshness, match, why, gaps and route;
   - letters already prepared;
   - deadlines.
6. **Open a match.** The letter and tailored resume are prepared, or already pre-warmed. The user reviews them on the letter page that exists now, then sends from their own mailbox. "I sent it" records the send, and outcomes follow.
7. **Add a lead** (paste) stays and goes through the same per-user pipeline.

## C. Database changes (migration 0004, additive first)

**`profiles`**
- `career_stage` (student | graduate | experienced)
- `experience_years` numeric (computed, editable)
- `experience_band`
- `portfolio_url`, `linkedin_url`
- `onboarding_step` gains the values `form`, `building`, `review`, `done`

**`preferences`**
- `target_families` text[]
- `salary_floor` int (per year)
- `notice_period` text
- defaults set by career stage at onboarding

**`items`, `bullets`, `entries`, `education`, `facts`**
- `confirmed` stays and now means "usable". Lines that pass the provenance check are set true; lines that fail stay false and are shown as "Left out".
- New `provenance` jsonb: source document id, matched passage, check result.

**`tracks`** (the baselines)
- `role_family`, `fit`, `fit_why`, `gaps` text[]
- `approved` defaults true; edits no longer reset it.

**`jobs`** (opportunities): real columns for everything we filter or index on. `extracted` jsonb keeps the rest.

| Group | Columns |
|---|---|
| Title and family | `title`, `role_family`, `role_families` (primary + neighbours) |
| Type | `employment_type` |
| Experience | `exp_min`, `exp_max`, `experience_bands` text[] |
| Place | `country`, `city`, `work_mode` (remote / hybrid / onsite / unknown) |
| Pay | `pay_min`, `pay_max`, `pay_currency`, `pay_period` |
| Skills | `skills_must` text[], `skills_nice` text[] |
| Restrictions | `batch_years` int[], `cgpa_min` |
| Source | `source_kind` (paste / greenhouse / lever / ashby / hn / careers), `source_job_id`, `apply_url` |
| Dedupe and lifecycle | `dedupe_key`, `last_seen_at`, `state` (active / expired / closed) |

- Indexes:
  - `(role_family, state, posted_at)` where public;
  - unique `(source_kind, source_job_id)` where public;
  - unique `dedupe_key` where public.
- Freshness is computed at query time from `posted_at` / `first_seen_at`.

**New `opportunity_contacts`** (shared for public jobs, private for pasted)
- `job_id`, `email`, `person_name`, `person_role`
- `context` (post_apply | careers_page | site_generic)
- `source_url`, `is_generic`, `domain_matches`, `confidence`
- RLS: readable when its job is readable; written by the backend only.
- Deleted 30 days after the job expires (third-party personal data; purpose limitation).

**`matches`** (user × opportunity)
- `score`, `bucket` (strong / good / gaps), `why` jsonb, `gaps` jsonb
- `contact_id`, `computed_at`, `seen_at`, `dismissed_at`
- `decision`, `reasons`, `screen` and `track_key` stay.

**`applications`**: `match_id`, `contact_id`. One role per company stays (`unique (user_id, company_key)`).

**New `pool_segments`**
- `role_family`, `experience_band`, `status` (active / paused), `demand` (active users)
- `last_run_at`, `next_run_at`, `last_found`, `active_count`
- unique `(role_family, experience_band)`
- Readable by signed-in users (counts only); backend writes.
- A segment with no active users for 14 days pauses.

**New `source_boards`** (system only)
- `source_kind`, `board_token`, `company_id`
- `status`, `last_polled_at`, `last_found`

**Removed after the new flow is live** (phase 5): `pool_watches`, `pool_watch_users`, `role_options`. `onboarding_messages` stays read-only, then is dropped.

**`Discipline` becomes the role-family list.** The 17 values S1 already extracts stay, with three changes:
- `data` splits into `data_analytics` and `data_engineering`;
- data science joins `ai_ml`;
- `security` is added.

Existing rows are remapped in the migration.

## D. Files that change

**Backend**

| File | Change |
|---|---|
| `app/pipeline/schemas.py` | `Extracted` gains experience range, must/nice skills and contact candidates with context. Onboarding schemas lose the interview, bullet-proposal and role-audit types; track proposals gain fit. |
| `app/pipeline/prompts.py` | `EXTRACT` covers any seniority (not only students). `ONBOARD_EXTRACT` accepts free text. `TRACKS` writes one track per target family with fit. `SELECT` also orders skills and picks the headline. `DRAFT` says "job seeker" and handles salary. `INTERVIEW`, `BULLETS` and `ROLES` are removed. |
| `app/onboarding.py` | Extraction marks lines usable through the provenance check. New `build_profile` orchestration and experience-years calculation. Interview, bullet proposals and the role screen are removed. Upload parsing and GitHub reading stay. |
| `app/routes/onboarding.py` | `POST /onboarding/start` (form and files, then enqueues the build), `GET /onboarding/status`, `POST /onboarding/finish`. Old step endpoints are removed. |
| `app/routes/me.py` | New profile and preference fields. |
| `app/routes/work.py` | Leads use the split pipeline. New `GET /opportunities`, `POST /opportunities/{id}/prepare` and dismiss. `/today` returns the groups. The track approve step goes. |
| `app/routes/factbank.py` | Edits queue a re-render of the affected baselines. The confirm gate goes. |
| `app/pipeline/run.py` | Split into `process_opportunity` (global steps) and `prepare_application` (per user). |
| `app/pipeline/screen.py` | `global_screen` no longer takes `emails[0]` (contacts decides). `user_match` gains experience and salary rules. |
| `app/pipeline/select.py` | Skill order and headline choice, validated against the user's own skills and history (no seniority word the user's history lacks). |
| `app/pipeline/resume.py` | Builds from a per-opportunity copy of the track (title, summary, skill order). |
| `app/pipeline/draft.py`, `lint.py` | Salary rule for full-time roles; wording. |
| `app/pipeline/verify.py` | Exposes its safe fetcher as `fetch_page(url)` for contacts and careers pages. |
| `app/worker.py` | New task kinds (`build_profile`, `refresh_family`, `process_opportunity`, `match_user`, `match_opportunity`, `prepare_application`) and a scheduler tick. |
| `app/config.py` | Refresh interval, prepare-ahead count, source switches. |
| `tests/test_pipeline_rules.py`, `tests/test_roles_and_pdf.py` | Updated for the screen changes and the removed role screen. |

**Frontend**

| File | Change |
|---|---|
| `app/(app)/onboarding/page.tsx` | Rewritten as three screens: form, building, review. |
| `app/(app)/today/page.tsx` | Becomes the opportunities dashboard. |
| `app/(app)/profile/page.tsx` | The Roles tab becomes "Targets and experience". |
| `components/FactBankEditor.tsx`, `TracksEditor.tsx` | No confirm ticks and no approve step. |
| `components/PreferencesForm.tsx` | Salary, notice period and stage-aware defaults. |
| `app/(app)/jobs/[id]/page.tsx` | Shows the match reasons and the chosen contact with where it was published. |
| `lib/types.ts`, `lib/demo.ts`, `lib/fields.ts` | New fields and role families; demo fixtures. |
| `components/RolesPicker.tsx` | Deleted. |

## E. New files

**Backend**
- `supabase/migrations/0004_global_pool.sql`
- `app/taxonomy.py`: role families (label, search aliases, title patterns, neighbours), title → family, experience bands, years → band, a post's range → bands, a small skill-alias map ("ReactJS" = "React")
- `app/pipeline/opportunity.py`: normalise, dedupe and store (the global half of today's `run.py`)
- `app/pipeline/contacts.py`: harvest candidates (post, careers page) with provenance, and choose one
- `app/pipeline/match.py`: eligibility, score, bucket, why and gaps (code only)
- `app/pool.py`: segments, demand, scheduling, refresh, expiry, match fan-out
- `app/sources/__init__.py`, `greenhouse.py`, `lever.py`, `ashby.py`, `hn_hiring.py`, `careers.py`
- `scripts/seed_boards.py` and a seed list of company boards that the founder curates
- `tests/test_taxonomy.py`, `test_onboarding_auto.py`, `test_match.py`, `test_contacts.py`, `test_pool.py`, `test_sources.py`, with recorded JSON from each public feed
- An experienced synthetic profile (`06_…_sde_3yrs.json`). The five existing ones are all students.

**Frontend**
- `components/OpportunityCard.tsx`
- `components/ProfileReview.tsx`
- an opportunity detail state on the letter page while it is being prepared

## F. What stays as it is

**Backend**
- `resume_engine/` in full: builder, calibration, page check, ATS score, JD match, schema. The tailored title, summary and skill order go in as an in-memory copy of the track, so the engine needs no change.
- `app/llm.py`, `app/db.py` (`user_tx` / `system_tx`), `app/auth.py`, the task queue and its retry logic.
- S1 text rules: `enforce_text`, `deobfuscate`, `published_emails`, `parse_age_hours`.
- S4 company verification: DNS, MX, homepage, business type, SSRF guard, 30-day shared cache.
- S8 lint checks: em dash, URLs, numbers not in the facts, guessed address, length.
- Resume PDFs, downloads, share links, outcomes and events.
- These tables: `companies`, `applications`, `resumes`, `resume_files`, `resume_links`, `drafts`, `events`, `llm_calls`, `task_queue`.
- RLS: every per-user table stays own-rows.

**Frontend**
- The design system, app shell, login, Jobs folders, letter page, Add a lead and demo mode.

## Phases (each ends with tests, a live check and a commit)

1. **Foundations.**
   - Build: migration 0004 (additive); `taxonomy.py`; years and bands.
   - Accept when: titles map to the right family on a made-up fixture set of about 100 titles; band edges are covered; the existing 102 tests pass.
2. **Onboarding.**
   - Build: form, build, review (backend and frontend); provenance check; stage defaults.
   - Accept when:
     - synthetic profile 01 (a fresher targeting full stack, frontend and backend) gets three one-page baselines without one question;
     - the new experienced profile (SDE and AI/ML targets) gets two;
     - no baseline line is missing from its source documents.
3. **Split pipeline, matching, contacts, dashboard.**
   - Build: pasted leads move onto the new path; Today shows the groups; prepare on open.
   - Accept when:
     - a pasted post becomes a match card, then a prepared letter, in under 2 minutes;
     - two synthetic users get different scores and reasons for the same opportunity;
     - the contact chosen follows the publication-context order.
4. **Global pool.**
   - Build: sources, scheduler, segments, expiry, fan-out.
   - Accept when:
     - a new user whose segments already exist sees matches without any fetch;
     - a new segment triggers a refresh;
     - postings that leave their board expire;
     - fetched postings outside watched families are never extracted.
5. **Pre-warm and clean-up.** Top-3 pre-warm; removing the old tables and endpoints; spec principle 2 and section 4.1 rewritten; README.
