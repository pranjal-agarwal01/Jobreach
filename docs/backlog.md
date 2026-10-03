# Backlog

Ideas agreed in conversation and parked on purpose. Nothing here is built.

## "Add to pool": LinkedIn posts collected by hand, for everyone (parked 2026-10-03)

**Partly built (2026-10-03):** the agent path is live: a curator's pool key sends posts to
everyone's pool (docs/agent-intake.md section 6, app/curated.py), with one opening per post and
letters for the best three matches. Still parked: the "Add to pool" page for pasting by hand and
the spreadsheet upload.

The founder copies public LinkedIn hiring posts by hand and adds them to the **shared pool**, so
every matching user gets a letter from them (unlike a paste or an agent's post, which stays
private to one person).

- **Who:** only the founder's account (a curator list in the server settings).
- **How:** an "Add to pool" page like Add leads (paste a post, press Add, paste the next), plus a
  spreadsheet upload for bulk. Same JSON shape as the agent intake (`docs/agent-intake.md`).
- **Fields per post:** `text` (required: the whole post after "...see more", from the poster's
  name line to the end), `url`, `age_label` ("3h"), `collected_at`, `links` (form or careers
  links in the post), `search` (what was searched). Nothing else: no photos, comments, reactions
  or profile links.
- **Stored as:** a public opening in `jobs` (a new source, e.g. `curated`), through the same
  pipeline: company check, the address only from the post itself, matching for everyone, letters
  prepared for strong and good matches, Send for me when on.
- **Per-post limit:** at most 3 to 5 users get the same post, best matches first, so one founder
  never receives a pile of near-identical letters.
- **Privacy:** the poster's address is kept for hiring only and deleted 30 days after the opening
  closes (the existing rule).
- **Keep it manual:** LinkedIn's terms forbid browser plugins and scripts that copy its data, so
  no "Save to Jobreach" extension for this.

## Other parked items

- X (Twitter) reader for founders' hiring posts: needs an X developer account with credits;
  pilot with a hard monthly read cap ($100 = 20,000 posts) and measure usable posts per 1,000.
- Reddit hiring threads: needs Reddit's commercial approval (2 to 4 weeks).
- More job boards: Keka, Darwinbox, Zoho Recruit, Workable (portal openings, not letters).
