# Sending posts from your own agent

If you run your own agent that finds hiring posts for you, it can hand them to Jobreach
directly instead of you pasting them. Each post becomes **your private lead**, the same as a
post you paste: it is read, the company is checked, it is scored against your own work, and
when it is a strong or good match its letter and tailored resume are prepared. You read them
and press Send. Posts from your agent are never shared with other users and never enter the
shared pool (the database refuses it).

## 1. Make a key

Profile → **Your agent** → Make a key. The key (`jri_...`) is shown once: give it to your
agent as a secret. Turn it off there if it leaks; anything still using it is refused.

## 2. Where to send

```
POST <API address>/intake/leads
Authorization: Bearer jri_...
Content-Type: application/json
```

The API address is the one your web app uses (`NEXT_PUBLIC_API_URL`): `http://localhost:8000`
on your machine, or the Render address once the API is deployed.

## 3. What to send

```json
{
  "leads": [
    {
      "text": "The whole post, to the end, including the poster's name line and its age (\"3h\")",
      "url": "https://www.linkedin.com/posts/...",
      "age_label": "3h",
      "found_by": "posts: backend intern pune, past 24 hours",
      "found_at": "2026-10-03T09:15:00+05:30"
    }
  ]
}
```

| Field | Required | What it is |
|---|---|---|
| `text` | yes | The post exactly as shown, to the very end (pay terms are often in the last line). 40 to 40,000 characters |
| `url` | no | The post's link. Tracking parameters are removed; the same link sent twice is one lead |
| `age_label` | no | The age as shown on the post ("45m", "3h", "2d") |
| `found_at` | no | When the agent saw the post (ISO 8601). With `age_label`, this dates the post precisely |
| `found_by` | no | The search that found it, so you can see later which searches lead to replies |

Send only what the agent saw. **Do not** extract email addresses, verify the company, write
letters or create Gmail drafts: Jobreach does all of that by the same rules as a pasted post
(an address is used only if it is written in the post; never a guessed one).

Limits: up to 25 posts per call, 100 per day.

## 4. The answer

```json
{"received": 2, "queued": 1,
 "results": [{"job_id": "…", "status": "queued"}, {"job_id": "…", "status": "duplicate"}]}
```

`duplicate` means the same text or the same link is already one of your leads. `401` means the
key is wrong or turned off; `429` means today's limit is reached; `422` means a post is missing
its text or is too short.

Queued posts appear on **Add leads** within a couple of minutes, marked "Found by your agent",
and the strong and good matches on **Today** with their letters.

## 5. A brief you can give your agent

> For each hiring post you find, send it to Jobreach and do nothing else with it.
> POST it to `<API address>/intake/leads` with the header `Authorization: Bearer <key>` and a
> JSON body `{"leads": [...]}`, up to 25 posts per call. For each post send `text` (the whole
> post exactly as shown, to the end, including the poster's line and the age line), `url`,
> `age_label` (the age as shown, like "3h"), `found_at` (when you saw it, ISO 8601) and
> `found_by` (the search you ran). Do not extract emails, verify companies, write letters or
> create Gmail drafts: Jobreach does that. A `duplicate` status means it already has the post.
> Keep the key secret. Keep to about 8 LinkedIn searches per run.

## 6. Everyone's pool (curators only)

An account on the server's curator list (`CURATOR_EMAILS`) can make a key whose posts go to
**everyone's pool** instead of its own leads: Profile → Your agent → "Its posts go to: Everyone's
pool". Same address, same format, plus one optional field:

| Field | What it is |
|---|---|
| `combo` | The search combination that found it, e.g. `"student / backend"`, so you can see later which combinations bring openings people reply to |

What happens to each post:

- **One post, one opening.** Its identity is its LinkedIn activity number (from the link, in any
  of LinkedIn's link forms), else its link without tracking, else its text with case, spacing,
  links, "...see more" and hashtags ignored. A post already in the pool, sent by any key, under any
  combo, comes back `duplicate` and costs nothing.
- It is read once (company check, the address only from the post itself), then matched for every
  user who targets that kind of role.
- **Letters for the best three only.** The three strongest matches (strong or good) get a letter
  prepared, so one poster never receives a pile of near-identical letters. Everyone else it suits
  sees it among their openings and can still choose to apply.
- **Nobody writes twice to one company.** If someone already pasted the same post, or already has a
  letter for that company, they are skipped: the database allows one letter per person per company.

Limits: 25 posts per call, 500 a day into the pool.

### The ten search combinations

LinkedIn → search → **Posts**, filters **Date posted: Past 24 hours**, **Sort by: Latest**. Run each
search every 2 to 3 hours and stop a search when Jobreach answers `duplicate` for most of what it
returns: everything newer has been sent.

| `combo` | Search (LinkedIn understands quotes and OR) |
|---|---|
| `student / software engineering` | `"SDE intern" OR "software engineering intern" OR "software developer intern" hiring` |
| `student / backend` | `"backend intern" OR "backend developer intern" OR "node.js intern" OR "python developer intern" hiring` |
| `student / frontend` | `"frontend intern" OR "react intern" OR "front end developer intern" hiring` |
| `student / full stack` | `"full stack intern" OR "MERN stack intern" OR "full stack developer intern" hiring` |
| `student / ai and ml` | `"machine learning intern" OR "AI intern" OR "ML intern" OR "GenAI intern" hiring` |
| `student / data analytics` | `"data analyst intern" OR "data analytics intern" OR "business analyst intern" hiring` |
| `recent graduate / software engineering` | `fresher "software engineer" OR "SDE 1" OR "backend developer" OR "java developer" hiring` |
| `recent graduate / full stack` | `fresher "full stack developer" OR "frontend developer" OR "react developer" hiring` |
| `recent graduate / ai, ml and data` | `fresher "data analyst" OR "data scientist" OR "ML engineer" OR "AI engineer" hiring` |
| `experienced / backend and devops` | `"backend engineer" OR "SDE 2" OR "DevOps engineer" OR "cloud engineer" "2+ years" hiring` |

Send every hiring post a search finds, also those without an email: Jobreach decides the route
(a letter when the post publishes an address, otherwise the apply link). Posts outside India
that aren't open to India are skipped by Jobreach, not by the agent.

**The LinkedIn account doing the searching is yours, and LinkedIn's terms don't allow automated
use.** Keep the agent at a human pace (a few searches an hour, pauses between pages) so the
account isn't restricted. Jobreach itself never logs into LinkedIn.
