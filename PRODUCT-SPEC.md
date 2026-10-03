# Job Outreach Copilot: Product Spec and Build Brief

> **Working name only.** Author: Pranjal Agarwal. Written 2026-09-26.
>
> This document is the complete handoff for building a multi-user product out of a personal
> job-search pipeline that has been running since 2026-08-10. It is written to be given to a
> coding agent (for example Claude Code) in a **new, separate project**. Everything the builder
> needs is in here: what the original system does, what it learned, what the product is, how to
> build it, the legal limits, the costs, and the order to build in.

---

## 0. Read this first: rules for whoever builds this

### 0.1 Do not touch the original setup

The original pipeline lives in `C:\Users\agarw\Downloads\TARGET`. **It is live.** Pranjal's own job
search runs from it, with interviews and take-home deadlines in flight. Mishandling it costs
real opportunities.

- **Never write, edit, rename, move or delete anything inside `TARGET`.**
- **Never run any script inside `TARGET`.** Several have side effects there:
  `new_application.py` creates dated folders under `TARGET/applications/`, and
  `calibrate_scale.py --pick` **rewrites `TARGET/profile/resume_data.json`**.
- If you need a file from it, **copy it into this project** (section 15 has the exact list and a
  copy command), then work only on the copy.
- `TARGET` contains personal data (phone number, email, CGPA, client work). Copies go in a
  `reference/` folder that is **git-ignored** and is never used as seed or test data in any
  deployed environment. Build synthetic test profiles instead.

### 0.2 How to work

- Build **phase by phase** (section 13). Stop at the end of each phase and show the founder the
  acceptance checks before starting the next.
- **Propose, do not decide**, anything listed in section 14 (open decisions).
- Before writing any Claude API code, load current Claude API documentation (in Claude Code:
  the `claude-api` skill). Model IDs, prices and parameters in section 10 were correct in
  September 2026 and drift.
- The pipeline is a **code-orchestrated workflow with a few model calls**, not a free-roaming
  agent. The original was run by an agent driving a browser. That is the most expensive and
  least controllable way to do this job, and it cannot be offered to many users (section 11).

### 0.3 Glossary

| Term | Meaning |
|---|---|
| **Lead** | A job post or listing that might be worth applying to |
| **Track** | One resume variant aimed at a family of roles (the original had four: SDE, ML/CV, AI/Automation, Full-stack web) |
| **Fact bank** | Every true, user-confirmed statement that may appear on a resume, with its real numbers. Nothing else may appear |
| **Draft** | An outreach email written for one lead. The user always presses Send |
| **Portal route** | A lead with no email, only a form, ATS or LinkedIn apply link. Output is a tailored resume plus form answers for the user to submit |
| **Post age** | Hours between a post going up and the draft being written. The strongest predictor of a reply in the original data |
| **Mill** | An "internship" that is really a paid training or certificate product |

---

## 1. The reference system (what exists today)

### 1.1 What it is

A personal job-search pipeline for one final-year B.Tech CS student in India (graduating May
2027), targeting SDE internships and new-grad roles at startups and product or service companies,
remote or anywhere in India, with a stipend floor of Rs 10,000 per month. Big tech is excluded.

It does four things, then stops at the irreversible step:

1. **Find** fresh hiring posts (LinkedIn Posts search, LinkedIn Jobs search, company careers pages).
2. **Verify** the company is real (company page, live website, domain that accepts mail).
3. **Build** a one-page resume tailored to the role, from a fixed bank of true bullets.
4. **Draft** an outreach email in Gmail. **The human attaches the resume and presses Send.**

### 1.2 The run loop ("hunt"), run 2-3 times a day

| Step | What happens |
|---|---|
| 0. Load state | Read the state file, the conversion findings, the email rules, the search playbook. Build a dedupe list of every company already applied to |
| 1. Replies first | List Gmail drafts, search the inbox for the last 3 days. Interview invites and deadlines go to the top of the report. Record bounces and replies |
| 2. Search | LinkedIn Posts, `datePosted=past-24h`, relevance sort, rotating role-title queries. Widen to past-week only if 24h is empty. Then Jobs search, then careers pages |
| 3. Filter | Keep / drop rules (section 5.3). Unpaid-and-remote is drafted with the stipend floor stated |
| 4. Verify | Company page + live domain + mail records. Flag or drop (section 5.4) |
| 5. Build | `new_application.py` creates a dated folder, a tailored `.docx` and a `notes.md`. Then Word confirms exactly one page |
| 6. Draft | Email written to strict house rules (section 7), read back once to check it rendered right |
| 7. Record | `notes.md` gets the search query, post age, stipend, verification result and any judgment call. State file updated |
| 8. Report | Replies first, then drafts, then rejections with reasons, then decisions left for the human |

### 1.3 The four resume tracks

| Track | Used for | Leads with |
|---|---|---|
| A (default) | SDE, backend, most full-stack | Forecasting platform, web platform, newsletter pipeline (SDE framing) |
| B | ML, computer vision, data science | Two CV projects, newsletter pipeline |
| C | AI engineer, LLM, RAG, agents, automation | Newsletter pipeline (AI framing), CV project, forecasting platform |
| D | Frontend-leaning web roles | Web platform, forecasting platform, newsletter pipeline |

Each track is the same layout with a different title line, summary, project order, skills list
and type scale.

### 1.4 Scale reached (as of 2026-09-25)

- 186 application folders, each with a tailored resume and a `notes.md`.
- Sources: LinkedIn Posts (email-first, small pool), LinkedIn Jobs (volume, mostly ATS),
  careers pages (per verified lead). Internshala and Unstop were declined by the user.

### 1.5 Outcomes (the evidence the product is built on)

- First ~30 cold emails (25 Aug to 10 Sep): **6 replies, about 20%**, 3 of them interview or
  offer-track. The rate has not been recomputed since.
- By 25 Sep: **interviews or take-home assignments from 8 companies**, including one
  founding-team offer track; **2 further shortlists that were conditional on accepting unpaid
  terms**; several acknowledgements and form requests; **1 template rejection** (from a large
  company, 8 minutes after sending); **3 hard bounces**.
- **Every positive reply came from a startup or SME of roughly 10 to 200 people.** Every
  application to a large company through its ATS went silent.
- **Assignment-first screens became the normal next step**: 4 of the last 6 positive replies
  were take-home assignments.

**Caveat:** this is one person and a small sample. Treat section 2 as hypotheses the product
should keep measuring across users (section 12.5), not laws.

---

## 2. What the reference system learned

### 2.1 What predicts a reply

1. **Post age beats match quality.** Posts under 2 hours old produced interview or founding-team
   tracks with replies inside 45 minutes. 3-day-old posts produced polite acknowledgements.
   Later data kept supporting it on *outcome* (assignment-stage replies from posts under 8 hours
   old) but weakened the "reply within the hour" part: many came 3 to 6 days later. And on one day
   two 2-day-old posts replied inside 11 minutes while sub-11-hour posts stayed silent. **Freshness
   is strong, not monotonic.** A wider date window raises count and lowers conversion.
2. **No converter ever published a competitive cash stipend.** Posts that say nothing about pay,
   or say "unpaid", get replies. Posts advertising Rs 20-25k draw heavy competition and produced
   nothing. Likely mechanism: a stated figure attracts volume and buries the candidate.
3. **Only companies convert, never intermediaries.** Every reply came from a post written by a
   founder, a named employee or the company page. No third-party recruiter or aggregator post ever
   converted.
4. **Company size:** startups and SMEs of roughly 10 to 200 people. Nothing larger.
5. **Stating the floor against an unpaid post works as a filter.** Two of two such emails got
   fast, warm replies that declined the floor but offered to continue. It surfaces the refusal
   before interview time is spent.
6. **Both SDE and AI tracks convert.** The ML/CV track was the quietest.
7. **Both `hr@company` and `firstname@company` addresses convert.** A live website does not prove a
   live mailbox; the occasional bounce is a normal cost. An address *inferred* from a pattern
   (careers@) bounced. Never guess addresses.

### 2.2 Search lessons (LinkedIn, for the record)

- Relevance sort inside a tight date window (`past-24h`) beats date sort, which returns noise.
- Free-account boolean: quoted phrases and uppercase `OR` with parentheses work; `NOT`,
  wildcards, `+` and `-` do not. One quoted phrase plus one OR group; two quoted phrases ANDed
  return nothing.
- Posts search has no location filter. Posts from Pakistan, Nepal and Sri Lanka appear in the same
  results. **Read location before stack.**
- AI-titled anchors are now dominated by internship mills. Role-title anchors with a stack
  qualifier still work, e.g. `("AI intern" OR "AI engineer intern") (RAG OR LangChain OR LLM)`.
- The **absence of a published email** caps email volume more than freshness or pay rules do.
  Roughly half of good leads publish no address. They still get a folder and a tailored resume
  for the portal route.
- An aggregator post is undraftable but useful as a pointer: take the company name, discard the
  post, verify the company from scratch.

### 2.3 Why leads get rejected (the taxonomy)

| Pattern | Example signal | Action |
|---|---|---|
| Unpaid, or paid only after an unpaid evaluation period | Often the *last* line of a strong post | Onsite/hybrid: drop. Remote: draft with the floor stated |
| Asks the candidate for money | "Rs 999 one-time registration" | Hard drop, no verification needed |
| Internship mill | "3 certificates on completion", "Certificate + LOR", "Don't Compromise on Your Career", a menu of 8-15 roles across engineering, HR and marketing | Drop |
| No apply route | "Comment Interested", "DM me", WhatsApp only | Drop (or watch) |
| Aggregator or recruiter repost | Roundups, comment-for-link, staffing agencies posting for an unnamed client | Drop as a lead; use the company name as a pointer |
| Staffing, MSP or offshore-support firm wearing an SDE or AI label | Contact domain differs from website domain; "US shift"; business described as outsourcing | Drop |
| Wrong discipline | Android/React Native, QA/testing, marketing, WordPress, data analytics | Drop |
| Batch-year or CGPA gate the user fails | "2025/2026 graduates only" | Drop. Read the batch line before the stack line |
| Outside supported geography | Location line | Drop |
| Personal Gmail with no named company | | Drop. Allowed only when the poster is a verifiable founder or director of a named company |
| Big tech | | Drop (user preference in the original; make it a setting) |

### 2.4 Operational lessons (these become product features)

- **Measure state in the source system.** A bookkeeping file once claimed a sending backlog that
  did not exist and throttled volume for no reason. Gmail is the truth for sent and replied.
- **Dedupe immediately before creating a draft.** Two sessions once drafted the same follow-up two
  minutes apart. Use an idempotency key per (user, company).
- **Replies can arrive as brand-new threads**, not replies. Reply tracking must search by
  recipient domain across the mailbox, including spam.
- **Search fresh at the moment of drafting.** Leads found earlier closed before they were acted on.
- **Never narrow the user's availability.** A draft once echoed a post's "3 to 6 months" back as
  the candidate's limit. Duration was fully flexible.
- **Verify in the renderer the recipient uses** (section 6.4).
- **The strongest evidence was missing from the original resumes.** The production RAG
  assistant for a paying client appeared nowhere in the original PDFs. Onboarding must dig for
  work people forget to list.
- **Claims without evidence are an interview risk.** One skill was listed with nothing behind it;
  one deployment claim ("self-hosted on cloud") was not true at the time. The fact bank must
  catch both.

---

## 3. The product

### 3.1 One-liner

A job seeker gives the product their real history once. From then on, for every good fresh
lead, it produces a truthful one-page tailored resume and a ready-to-send outreach draft, stored in
their own private workspace. They press Send.

### 3.2 Target user (first market)

Indian students and freshers applying to startups and small product or service companies, where
direct outreach to a founder or HR person on a fresh post beats applying through a portal.

### 3.3 Positioning

Tools such as Simplify, Teal, Jobscan and LazyApply mostly optimise ATS applications or
auto-apply at volume. (Verify the landscape before launch; this line is not researched.) This
product does the opposite, on evidence: **fast, truthful, human-sent outreach to startups**, with
the resume and email built per lead.

### 3.4 Non-negotiable principles

1. **The user presses Send and Submit. Always.** The product never sends email and never submits
   an application.
2. **Selection, never invention.** Every resume line and every claim in an email traces to the
   user's own record: a line found in the documents they gave (code checks each line's numbers,
   tools and wording against those documents), or a line they wrote or restored themselves. A
   line that cannot be found is left out and shown to the user, never used silently. No invented
   metrics, skills, dates or counts. (Changed 2026-10-01: confirming every line by hand became
   this check; see `docs/plan-global-pool.md`.)
3. **Counts that cannot be shown stay vague.** For example "multiple clients", never an invented
   "5+".
4. **Only published contacts.** An email address must appear verbatim in the post, the JD or the
   company's own site. Never guess or pattern-infer an address.
5. **One role per company** at a time.
6. **No account creation, password entry or CAPTCHA solving** on the user's behalf.
7. **Never narrow the user's stated availability** (duration, location, start date).
8. **Freshness first** in ranking.

### 3.5 Non-goals (for now)

- Auto-sending or auto-submitting.
- Automated LinkedIn access of any kind (section 11.1).
- Mass email. Sending stays one message at a time from the user's own mailbox.
- Big-company ATS optimisation as the core feature.

---

## 4. User journey and features

### 4.1 Onboarding (target: about 3 minutes of the user's time)

One form, one background build, one review (rewritten 2026-10-02; `docs/plan-global-pool.md`, B).
The guided interview, per-line confirmation and the role audit are gone.

1. **One form:** CVs (PDF or DOCX); stage (student, recent graduate, experienced); up to four
   kinds of role (role families, `backend/app/taxonomy.py`); GitHub, portfolio and LinkedIn links
   (LinkedIn is stored for the resume header, never read); anything the CV leaves out; and the
   preferences. Defaults follow the stage: a student gets internships, a monthly stipend floor and
   the unpaid policy (draft with the floor if remote, drop if onsite or hybrid); everyone else
   gets full-time roles, a yearly salary floor and a notice period. Consent is a checkbox here.
2. **A background build, with nothing asked:** read the CVs, GitHub (repositories and up to six
   READMEs) and the portfolio; extract the profile; hold every line to those documents in code
   (principle 2); count full-time years from work dates (internships do not count) and set the
   experience band; write one baseline resume per kind of role, with an honest fit (strong, good,
   stretch) and its gaps; render and page-check each to one page.
3. **One review:** the profile in a sentence, the baselines, the lines that were left out (each
   with "use it anyway"), other kinds of role the work fits, and one question: would you like to
   add, remove or change anything? Edits re-render the affected baselines.
4. **Format and signature** as before: one template in Phase 1, format rules stored as settings,
   the signature block stored verbatim.
5. **Finishing** registers the user's (kind of role, experience band) segments with the shared
   opportunity pool, and the openings already in it are matched at once.

### 4.2 Adding leads

| Source | Phase | Notes |
|---|---|---|
| **Paste** a post, JD or URL text | Built | The user copies the text themselves. Prepared at once |
| Public ATS job-board APIs (Greenhouse, Lever, Ashby) | Built (shared pool) | Public, no auth. Read on the server every 6 hours while someone needs a kind of role. Skews to funded companies |
| Careers pages of verified companies | Built (shared pool) | Openings in the page's JobPosting markup, the job board it links to, published hiring addresses. robots.txt respected |
| Hacker News "Who is hiring" | Built (shared pool) | Public API, twice a day. Mostly remote roles |
| Browser extension "clip this post" | Maybe, after legal review | **Grey area under LinkedIn's terms** (section 11.1) |

### 4.3 Workspace ("personal space")

- **Today view** (replaces the original's state file): live threads with deadlines first
  (interviews, take-homes), then new drafts, then leads needing a decision (the judgment calls),
  then gaps that would strengthen the resume (missing metrics).
- **Leads:** kept and dropped, with reasons. The user can override a drop.
- **Applications:** one row per company: track, resume, draft, route, status, post age, notes.
- **Resumes:** per-track baselines and per-application tailored copies, downloadable as `.docx`.
- **Drafts:** subject and body, copy button, "Open in Gmail" (Phase 1), real Gmail draft with
  attachment (Phase 2).
- **Form answers:** a bank of standard answers for portal forms ("tell us about yourself" in ~60
  words, "why this company", notice period, start date). Demographic questions are left for the user.
- **Outcomes:** replies, interviews, assignments, rejections, bounces. Manual in Phase 1,
  from Gmail in Phase 4.

---

## 5. The per-lead pipeline

Each step lists **who does it** (code or model), its output, and its rules. Steps 1, 2 and 4 are
per lead and cacheable; steps 3 and 5-9 are per user.

### 5.1 S1 Extract (model, structured output)

Input: raw post or JD text plus source metadata. Output (validated JSON):

```
title, company_name, company_domain, poster_name, poster_role,
poster_type: founder | employee | company_page | recruiter | aggregator | unknown,
location_text, country, remote: bool, onsite_city, hybrid: bool,
stipend: { stated: figure | unpaid | unstated | performance_based,
           min, max, currency, unpaid_period_months },
batch_years[], cgpa_min, duration_text, start_text,
discipline: sde | backend | fullstack | frontend | ai_ml | cv | data | qa | mobile | marketing | other,
stack[], apply_routes[ { type: email | form | ats | linkedin_apply | dm_only | whatsapp, value } ],
posted_age_label (e.g. "3h"), mill_signals[], asks_candidate_for_money: bool
```

Rules: **read to the end** (the unpaid line is usually last). Extract emails **exactly as
written**; never correct or complete one. If the text is ambiguous, return null, not a guess.

### 5.2 S2 Global screen (code first, model for fuzzy signals)

Apply the taxonomy in section 2.3 that does not depend on the user: money asked, mill signals,
no apply route, aggregator or recruiter poster, geography. Output `pass | drop | flag` with reasons.

**Flag, do not drop:** branded Gmail alias from a named employee; dead website but a real company
and a named poster; contact domain differs from website domain; post shared by a third party.

### 5.3 S3 User match (code rules, then model ranking)

Hard rules in code, from the user's preferences:

- Location or remote mismatch: drop.
- Stated stipend below the floor: drop. **Unstated: keep and ask in the email.**
- Unpaid (including "paid after an unpaid period"): if remote, apply the user's policy (default:
  draft with the floor stated); if onsite or hybrid, drop.
- Batch year or CGPA gate the user fails: drop.
- Excluded company type or company: drop.
- Already applied to this company (any role): skip. One role per company.
- Older than the user's freshness ceiling: drop. The ceiling is a per-user setting, and the user
  may change it per session.

Then a model call ranks the survivors: **freshness first**, then fit to the user's tracks. Output
per lead: keep or drop, reasons, suggested track, rank.

### 5.4 S4 Verify company (code + model, cached per company for 30 days)

- DNS: does the domain resolve (A/AAAA)? Does it accept mail (MX)?
- Fetch the homepage in code; a model summarises what the business actually is (product company,
  staffing agency, MSP, training academy, placement cell...).
- Optional: domain age via RDAP.
- The product **cannot** check LinkedIn company pages automatically (section 11.1). Show the user
  a link to check it themselves.

Outcome:

| Situation | Result |
|---|---|
| Domain live, MX live, business matches the post | pass |
| Website dead but MX live and poster is a named employee | pass, **flagged** |
| Business is staffing, MSP, or training | drop |
| No domain and no findable company | drop |

A live site does not prove a live mailbox. Do **not** probe mailboxes over SMTP; it is
unreliable and harms sender reputation. Treat bounces as a normal cost and record them.

### 5.5 S5 Track and bullet selection (model, constrained)

- Choose the track and the project order for this JD.
- Select bullets **only from confirmed bullets** in the fact bank; order them for the JD.
- Optionally drop a low-relevance line to fit the page.
- **Phase 1: selection and ordering only.** Rewording toward the JD's vocabulary may come later
  as a *proposed* edit the user approves, and a validator must reject any reworded line that
  introduces a number, tool, skill or claim not present in the fact bank.

### 5.6 S6 Build and verify the resume (code, no model)

See section 6. The build must produce a `.docx` that is **exactly one page** in the page check,
or it does not ship.

### 5.7 S7 Draft the email (model)

See section 7 for the rules. Output: subject, HTML body, and which facts it used.

### 5.8 S8 Lint the draft (code; blocks delivery on failure)

- No em dash (U+2014) anywhere.
- No bare URLs in the body text; links only as anchors. The user's own signature is exempt.
- HTML is well formed; no escaped tags (`&lt;p&gt;`), no stray parameter or template text, no
  placeholders (`PASTE`, `TODO`, `{{`, `[link]`).
- The recipient address appears verbatim in the lead's source text or the company site.
- Every number in the email exists in the fact bank or the post.
- Length inside the target range for the email type.
- Contains the words "resume is attached" (Gmail's missing-attachment warning then acts as a net).
- Mentions one role only.
- Does not state a duration, location or start date narrower than the user's preferences.
- The stipend line matches the rule (ask if unstated; state the floor if unpaid-remote).
- Signature block present and verbatim.

### 5.9 S9 Deliver

- **Phase 1:** show in the workspace: download `.docx`, copy subject and body, "Open in Gmail"
  compose link (plain text, no attachment; the user attaches). Note that a prefilled compose URL
  puts the body in browser history.
- **Phase 2:** create a real Gmail draft through the Gmail API with the resume attached (section
  11.2). Read the draft back and re-run the lint before showing it as ready. **Never send.**

### 5.10 S10 Record

Write the application row with: source, **the exact search or source that found it**, poster,
**post age at capture and at draft**, email and where it was published, stipend, stack,
verification result, judgment calls, track, resume id, draft id. The original could not analyse
which search query converted for its first batches because this was not recorded. Record it
from day one.

---

## 6. The resume engine

### 6.1 The format (measured, then generalised)

The original layout was measured point by point off the user's own CVs:

- A4, 595.3 x 841.9 pt; margins left 30, right 31, top 41, bottom 42.
- **One real Word table**, 1 row, 2 borderless cells filling the page. Left cell 340 pt (name,
  title line, summary, PROJECTS). Right cell 195 pt (contact, social, technical skills, education,
  awards and certifications, other roles and responsibilities). An 11 pt gutter pad each side of
  a 0.75 pt light divider (`#D6DCE5`).
- Accent `#1F3864`, secondary text `#444444`, Calibri throughout. Section headings 10 pt bold in
  the accent colour, with an accent bottom rule.
- Each project: bold name, a `Stack:` line, four bullets. The first bullet states the problem
  being solved. Bullets are 21-29 words, with every real number surfaced.
- Separators: `·` between a title and its meta trailer, `–` for date ranges, `—` in prose. (The
  no-em-dash rule applies to **email only**, not to the CV.)
- **The columns must be a real table**, never tab stops or text boxes, so ATS text extraction
  reads cell by cell.

### 6.2 Type scale

All font sizes and gaps are base values multiplied by one `scale` per track. The scale is found
by binary search: the largest value at which that track still renders as exactly one page.
Original results: 1.04 to 1.09 (body text 9.25 to 9.75 pt). **Re-calibrate after any content
change**, because a longer bullet at an unchanged scale silently spills to page 2.

For the product: calibrate per user per track on onboarding and whenever the fact bank changes.
A tailored build that swaps projects or drops a line changes length, so **every tailored build
is page-checked**, not just baselines.

### 6.3 Schema (generalise from the original `resume_data.json`)

The original schema (v2) has: `contact`, `titles{track}`, `summary{track}`,
`project_order{track}`, `projects{id: name, tagline, links[], period, stack, bullets[4]}`,
`skills{track}`, `education[]`, `awards[{text, tracks[]}]`, `other_roles[{id, lead, text,
tracks[]}]`, `scale{track}`. Generalise it to any number of tracks, projects, bullets and sections,
and have every bullet reference fact ids.

### 6.4 Page verification (the part that must change)

The original verifies with Microsoft Word through COM automation on Windows. **Word does not
run on a Linux server.** Replace it with:

- **LibreOffice headless** converting the `.docx` to PDF, then count pages (e.g. with `pypdf`).
- Install **Carlito**, which is metric-compatible with Calibri (every glyph takes the same
  width), so line breaks and page count match Word.
- **Parity test before trusting it:** build the original four baseline `.docx` files from the
  copied reference data. All four are exactly one page in Word, and all must also be one page in
  the LibreOffice + Carlito check. Then test tailored variants near the page boundary.
- Known trap: Google Docs has no Calibri and substitutes a wider face, so a correct one-page file
  can preview as two pages in Google Drive. Tell users to view in Word or the product's own
  preview.

### 6.5 Output rules

- **Deliver `.docx`, never a PDF of the two-column layout.** Measured: PDF text extraction
  interleaves the two columns mid-sentence, which wrecks ATS keyword matching. If a portal demands
  PDF, warn the user and offer the plain text for any "paste your resume" box.
- File name `resume_<First>_<Last>.docx` for every copy. The workspace, not the file name,
  distinguishes versions, so the recipient never sees an internal label.
- **One page, always.** If the check fails: step the scale down one grid step, then drop the
  lowest-priority line, then rebuild. Never ship two pages.

### 6.6 Scoring (carry over)

- `ats_score.py`: a JD-independent score out of 100 (parseability, contact completeness,
  recognised headings, date hygiene, content quality, skills coverage, length). Full marks on
  quantification at 40% of bullets carrying a number. It was recalibrated for the two-column
  layout; about 9 points of that format's gap to single-column is structural and permanent.
- `jd_match.py`: literal keyword overlap between a resume and one JD.
- Use both as **advice shown to the user**, never as an excuse to invent content.

---

## 7. Email drafting rules (generalised house rules)

1. **Prose, not a data dump.** Short paragraphs of 2-4 sentences. No label-colon-value lines, no
   bulleted personal details, no emoji headers. Bullets only for distinct pieces of work.
2. **Never an em dash.** It reads as AI-generated. Rewrite the sentence.
3. **No bare URLs** in the body. Say "my resume carries the links". Anchor any link that must be
   there.
4. **Signature block verbatim** from the user's settings. Drafts created through the API do not
   get the Gmail signature automatically.
5. **Length:** recruiter 90-110 words, hiring manager or founder 100-130, referral 150-200.
6. **Stipend:** if unstated, ask directly. If unpaid and remote, state the user's floor plainly.
7. **Never mirror the post's duration, location or start date back as the user's limit.** Say
   the user is flexible, or leave it out.
8. **One role per company.** Pick the role backed by real experience.
9. **Lead with what matches.** For an SDE-only search, lead with the backend or full-stack work
   and let AI work appear as proof of engineering ability.
10. **Name gaps honestly** when the JD asks for something the user lacks (for example a framework
    they have not used). It reads as credible and filters bad fits early.
11. **Keep "resume is attached"** in the body.
12. **HTML only.** Measured in the original through a Gmail connector: when a plain-text part was
    stored, Gmail's `google.com/url?q=` link rewrite became visible text. Re-measure this with the
    real Gmail API in Phase 2 before relying on it.

---

## 8. Architecture

### 8.1 Components

```
 Browser (Next.js app)
   | onboarding, paste lead, workspace, downloads
   v
 API (FastAPI, Python)  <---- auth (Supabase Auth or equivalent)
   |        |
   |        +--> Postgres (row-level security per user)  +  object storage (resumes)
   |
   +--> Job queue + scheduler (e.g. a Postgres-backed queue or Redis worker)
            |
            +--> Pipeline workers (Python)
                   S1/S2/S3/S5/S7 -> Claude API (structured outputs)
                   S4             -> DNS/MX lookups + homepage fetch (+ Claude summary)
                   S6             -> python-docx builder -> LibreOffice headless + Carlito -> page count
                   S8             -> lint (pure code)
                   S9             -> Gmail API (Phase 2+)
            +--> Feed pollers (Phase 3): Greenhouse / Lever / Ashby / careers pages
```

Python on the backend is deliberate: the resume builder, scorer and keyword matcher already exist
in Python with `python-docx`.

### 8.2 Data model (key columns only)

| Table | Scope | Key columns |
|---|---|---|
| `users` | per user | id, email, plan, consent_version, created_at, deleted_at |
| `profiles` | per user | user_id, name, headline, location, grad_date, batch_year, cgpa, contact json, links json |
| `facts` | per user | id, user_id, kind (project, role, award, education, skill, metric), text, value, source (upload, interview, edit), confirmed_at, evidence_note |
| `projects` | per user | id, user_id, key, name, tagline, period, stack, links json |
| `bullets` | per user | id, user_id, parent (project or role), text, fact_ids[], has_metric, confirmed |
| `tracks` | per user | id, user_id, key, label, title_line, summary, project_order[], skills[], scale |
| `preferences` | per user | user_id, role_types[], locations[], remote_ok, stipend_floor, currency, unpaid_remote_policy, unpaid_onsite_policy, excluded_company_types[], excluded_companies[], freshness_ceiling_hours, duration_flex, start_date, signature_html |
| `companies` | **shared** | id, name, domain, dns_ok, mx_ok, business_summary, is_intermediary, size_band, verification (pass, flag, fail), flags json, checked_at |
| `jobs` | **visibility-scoped** | id, visibility (private to one user, or public if from a public feed), owner_user_id, source, source_ref, raw_text, extracted json (section 5.1), company_id, first_seen_at, posted_at, content_hash |
| `matches` | per user | user_id, job_id, decision, reasons[], track, rank, created_at |
| `applications` | per user | id, user_id, job_id, company_id, track, route, status, found_by (query or source), age_at_draft_hours, judgment_calls[], created_at, user_marked_sent_at |
| `resumes` | per user | id, user_id, application_id or track, storage_path, bullet_ids[], scale, pages_verified, renderer, ats_score, jd_match |
| `drafts` | per user | id, application_id, to[], cc[], subject, html, lint json, gmail_draft_id, version, idempotency_key |
| `events` | per user | id, application_id, type (reply, bounce, interview, assignment, rejection, auto_ack, gated_unpaid), occurred_at, deadline_at, source (manual, gmail), summary |
| `audit_log` | system | who, what, when |

**Pasted leads stay private to the user who pasted them.** A pasted post contains a third
party's name and email copied from LinkedIn; pooling it across users redistributes that content.
Only leads from public feeds go in the shared pool.

### 8.3 Multi-tenancy

Row-level security on every per-user table. Resumes in object storage under per-user paths,
served through short-lived signed URLs. No cross-user reads except the shared `companies` table
and public-feed `jobs`.

---

## 9. Reply tracking and outcomes (Phase 4)

- Needs Gmail read access (restricted scope, section 11.2). Until then, the user logs outcomes
  with one click.
- Search by **recipient domain** across the whole mailbox including spam and trash, not just
  reply threads. Positive replies have arrived as new threads.
- Detect bounces (mailer-daemon, 550 "address not found") and mark the application.
- Classify each reply: interview invite, take-home assignment (extract the deadline), shortlist
  gated on accepting unpaid, form request, auto-acknowledgement, template rejection, bulk mail.
- Put anything with a deadline at the top of the Today view.
- A fast reply is not automatically good: an 8-minute template rejection from a large company was
  a screening filter.

---

## 10. Claude API usage and cost

### 10.1 Model and settings (checked September 2026; re-check before building)

- Default model: **`claude-opus-5`** ($5 per million input tokens, $25 per million output).
- Cheaper options, each **a decision to measure, not assume**: `claude-sonnet-5` ($2 / $10),
  `claude-haiku-4-5` ($1 / $5).
- Use the official Python SDK (`anthropic`). Adaptive thinking. Set `output_config.effort` per
  step: `low` for extraction, screening and reply classification; `medium` for ranking and bullet
  selection; `medium` or `high` for drafting.
- **Structured outputs** for every extraction and classification step, validated against a schema.
- **Prompt caching:** put the fixed rules (sections 2.3, 5, 7) and the user's fact bank first in
  the prompt as a stable prefix; cache reads cost a fraction of normal input.
- **Batch API (50% off, asynchronous)** for shared, non-urgent work: extracting and screening feed
  jobs, company summaries. **Do not batch drafting**: freshness is the lever.
- Handle refusals and errors explicitly (check `stop_reason` before reading content).
- No model is needed for: building the `.docx`, the page check, DNS/MX, dedupe, the lint.

### 10.2 Cost estimate (assumptions stated; measure in Phase 1)

| Unit | Assumed tokens | Approx. cost on Opus 5 |
|---|---|---|
| Extract + screen one job (shared, once) | ~2k in, ~0.5k out | ~$0.02 (about $0.01 batched) |
| Summarise one company (shared, 30-day cache) | ~3k in, ~0.4k out | ~$0.025 |
| Rank ~40 leads for one user | ~12k in, ~1.5k out | ~$0.10 |
| Select bullets + draft one email | ~6k in (mostly cached), ~2k out | ~$0.07 |

| User type | Per day | Per month |
|---|---|---|
| Typical: 5 drafts, 1 ranking | ~$0.45 | **~$14** |
| Heavy (the original's pace): 10 drafts, 2 rankings | ~$0.90 | **~$27** |

Shared costs (jobs and companies) scale with the number of jobs processed, not the number of
users. The original produced about 4 applications per day on average (186 in about 46 days).

**Cost levers, in order:** draft only when the user clicks "draft this" instead of drafting
every kept lead; cache the stable prefix; batch shared processing; lower effort on extraction;
then, only if measured quality holds, a cheaper model for extraction. Indian students are
price-sensitive, so set pricing with the measured number, not this estimate.

---

## 11. External constraints (verified September 2026)

### 11.1 LinkedIn

- LinkedIn's User Agreement (section 8.2) bans crawlers, bots, **browser plug-ins and
  extensions** that scrape or copy data, and unauthorized automated access.
- LinkedIn enforces this in court: hiQ ended in a permanent injunction; a 2025 suit against
  ProAPIs ended in a consent judgment banning automated access and sale of its data.
- **So:** no server-side LinkedIn access, no stored LinkedIn sessions, no automated searching.
  The user pasting text they copied themselves is the safe route. A "clip this post" extension
  is a grey area under 8.2 and needs a legal opinion before it is built.
- This is the product's biggest structural gap: the source that converted best in the reference
  data (fresh founder posts on LinkedIn) is exactly what cannot be automated.

### 11.2 Gmail

| Scope | Allows | Google classification |
|---|---|---|
| `gmail.compose` | Create and manage drafts (and send) | **Restricted** |
| `gmail.send` | Send only | Sensitive |
| `gmail.readonly` | Read mail (reply tracking) | **Restricted** |
| `gmail.metadata` | Headers and labels only | **Restricted** |
| `gmail.modify` | Read, compose, send | **Restricted** |

- Restricted scopes need Google's restricted-scope verification, and apps that store or transmit
  restricted-scope data on servers need a **CASA security assessment** by an approved assessor.
  Third-party reports put it at months, with costs ranging widely. Budget months, not weeks.
- **An unverified app has a 100-new-user cap for sensitive or restricted scopes, over the whole
  lifetime of the Google Cloud project, and it cannot be reset.** Do not burn it on casual
  testers.
- `gmail.send` is lighter to get, but sending automatically breaks principle 1. Do not use it.
- Attachments work through the Gmail API (multipart upload; 35 MB limit on the whole encoded
  message). A resume `.docx` is about 40 KB. The original's manual-attachment step was a limit of
  the connector it used, not of Gmail.
- **Phase 1 needs no Gmail scope at all:** copy button plus "Open in Gmail" link.

### 11.3 Job feeds

- Greenhouse Job Board API, Lever Postings API and Ashby Posting API are public, need no key, and
  exist so companies can embed their job boards. You need each company's board token or slug.
- They skew toward larger, funded companies, which converted worst in the reference data. Use
  them for the portal route and for companies already verified, not as the core email engine.

### 11.4 India's DPDP Act

- DPDP Rules 2025 were notified on 14 Nov 2025 with phased commencement: Consent Manager
  provisions from about 13 Nov 2026, and most data-fiduciary obligations from about 13 May 2027.
- The product stores resumes, phone numbers, grades and possibly transcripts. Build for
  compliance from day one: clear consent notice, purpose limitation, deletion on request (real
  deletion, including object storage and backups within a stated window), breach handling,
  security safeguards, records.

### 11.5 Email deliverability

- All mail goes from the user's own mailbox, one message at a time, pressed by the user.
- Evidence from the reference: more than 20 manual sends in a day produced no visible spam
  problems, and the only bounces were dead addresses. Small sample. Show a soft warning above a daily
  count the founder chooses; never offer bulk send.

---

## 12. Security, privacy and trust

1. Encrypt OAuth refresh tokens at rest; request the narrowest scope that does the job; let users
   disconnect at any time.
2. Row-level security everywhere (section 8.3); signed short-lived download URLs.
3. Redact personal data from logs; never log email bodies or resume text.
4. No training on user data. State it.
5. **Selection-never-invention is a trust feature.** Show, for every resume line, which confirmed
   fact it came from.
6. **Aggregate learning is opt-in.** Pooled outcome data (post age, stipend statement, poster
   type, company size, track) across users is the long-term advantage, but only anonymised and
   with consent.

---

## 13. Roadmap and acceptance criteria

### Phase 0: foundations

- New repo; copy reference files (section 15) into a git-ignored `reference/` folder.
- Port the builder, scorer and keyword matcher; generalise the schema (section 6.3).
- Docker image with LibreOffice and Carlito; page-count service.
- Synthetic test profiles (at least 5, different fields and lengths).

**Accept when:** the four original baselines are one page in the LibreOffice + Carlito check
(parity with Word), and synthetic profiles build to one page at calibrated scales.

### Phase 1: MVP (no Gmail scopes, no scraping)

- Auth, onboarding (section 4.1), fact bank, tracks, preferences.
- Paste-a-lead, pipeline S1 to S8, delivery by download + copy + "Open in Gmail".
- Workspace: Today view, leads, applications, manual outcome logging.
- Log real token usage per step.

**Accept when:** on 20 real pasted posts, the stipend, location, batch-year and apply-route
extraction matches a human reading; zero drafts pass lint with an em dash, a bare URL, a guessed
address or a number not in the fact bank; every resume is one page; a user goes from paste to
downloaded resume and copied email in under 2 minutes; measured cost per draft is known.

### Phase 2: Gmail drafts

- OAuth with `gmail.compose`, testing mode, a hand-picked pilot group (mind the lifetime cap).
- Draft with the resume attached; read back and re-lint.
- Start restricted-scope verification and CASA in parallel.

**Accept when:** the draft in Gmail matches the preview exactly, the attachment opens, links
render cleanly, and no draft is ever sent by the product.

### Phase 3: sourcing

- Public ATS feed pollers; careers-page checks for verified companies; the shared job pool for
  public-feed jobs; freshness-first ranking; a daily digest.
- Extension only after a legal opinion on LinkedIn section 8.2.

### Phase 4: outcomes

- Gmail read access for reply and bounce tracking (restricted scope, after verification).
- Outcome classification with deadlines; opt-in cross-user analytics.

### Phase 5: business

- Pricing and payments informed by measured cost (section 10.2).

---

## 14. Open decisions for the founder

1. Product name.
2. Pricing and free tier, given about $14 to $27 per active user per month on Opus 5 before
   optimisation.
3. Draft automatically for every kept lead, or only when the user clicks.
4. Whether to test a cheaper model for extraction and screening.
5. Whether to build the browser extension at all (needs a legal opinion first).
6. First market: Indian freshers only, or wider.
7. Whether "exclude big tech" is a default or purely a user setting.
8. The daily soft-warning threshold for sends.
9. Whether to offer more resume templates after Phase 1.

---

## 15. Reference files to copy (read-only source)

Copy these **out of** `C:\Users\agarw\Downloads\TARGET` into this project's `reference/`
folder. Do not modify the originals. Add `reference/` to `.gitignore` (it holds personal data).

| File in TARGET | What it is | Use in the product |
|---|---|---|
| `templates/build_resume.py` | Two-column `.docx` builder, schema v2, measured geometry | Port and generalise |
| `templates/calibrate_scale.py` | Binary search for the largest one-page scale | Port; replace the Word step with LibreOffice |
| `templates/verify_pages.ps1`, `templates/measure_pages.ps1` | Word COM page counters (Windows only) | Reference for the parity test only |
| `templates/new_application.py` | Creates the dated folder, tailored resume and `notes.md` | Reference for the application record |
| `templates/ats_score.py` | JD-independent ATS score out of 100 | Port |
| `templates/jd_match.py` | JD keyword overlap | Port |
| `templates/EMAIL-HOUSE-RULES.md` | Full email rules with the reasons | Source for section 7 and the lint |
| `profile/resume_data.json` | Real data in schema v2 (**personal**) | Schema reference and parity test only |
| `send/*/resume_Pranjal_Agarwal.docx` | Four baselines, one page in Word (**personal**) | Parity test only |
| `profile/standard-answers.md` | Portal form answer bank | Pattern for the form-answers feature |
| `.claude/skills/hunt/SKILL.md` | The whole run loop | Source for section 5 |
| `conversion-analysis.md` | Reply post-mortem | Source for section 2.1 |
| `sourcing-playbook.md` | Search technique and rejection taxonomy | Source for sections 2.2 and 2.3 |

PowerShell, run from the **new** project's root (copies only; nothing in TARGET changes):

```powershell
$src = "C:\Users\agarw\Downloads\TARGET"
$dst = ".\reference"
New-Item -ItemType Directory -Force "$dst\templates", "$dst\profile", "$dst\send", "$dst\skills" | Out-Null
Copy-Item "$src\templates\build_resume.py","$src\templates\calibrate_scale.py","$src\templates\verify_pages.ps1","$src\templates\measure_pages.ps1","$src\templates\new_application.py","$src\templates\ats_score.py","$src\templates\jd_match.py","$src\templates\EMAIL-HOUSE-RULES.md" "$dst\templates\"
Copy-Item "$src\profile\resume_data.json","$src\profile\standard-answers.md" "$dst\profile\"
foreach ($t in "SDE","ML-CV","AI-Automation","FullStack-Web") {
  New-Item -ItemType Directory -Force "$dst\send\$t" | Out-Null
  Copy-Item "$src\send\$t\resume_Pranjal_Agarwal.docx" "$dst\send\$t\"
}
Copy-Item "$src\.claude\skills\hunt\SKILL.md" "$dst\skills\hunt-SKILL.md"
Copy-Item "$src\conversion-analysis.md","$src\sourcing-playbook.md" "$dst\"
Add-Content .gitignore "reference/"
```

Note: `build_resume.py` finds its data through a path relative to its own folder
(`../profile/resume_data.json`), so the copied layout above keeps it runnable against the copy.

---

## 16. Sources for section 11

- Gmail API scopes and classifications: https://developers.google.com/workspace/gmail/api/auth/scopes
- Restricted scope verification: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- Unverified app user cap: https://support.google.com/cloud/answer/13463817
- CASA security assessment: https://support.google.com/cloud/answer/13465431
- Gmail API attachments: https://developers.google.com/workspace/gmail/api/guides/uploads
- LinkedIn User Agreement: https://www.linkedin.com/legal/user-agreement
- LinkedIn v. ProAPIs consent judgment: https://sigmalawgroup.com/blog/2026-09-18-linkedin-proapis-scraping-consent-judgment/
- DPDP Rules 2025 (PIB): https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf
- DPDP phased timeline: https://www.legal500.com/intelligence/india/privacy/india's-digital-personal-data-protection-act-and-the-dpdp-rules-2025-phased-commencement-core-obligations-and-a-board-ready-compliance-strategy
- Public ATS job-board APIs: https://fantastic.jobs/article/ats-with-api
- Carlito and Calibri metric compatibility: https://wiki.debian.org/SubstitutingCalibriAndCambriaFonts
