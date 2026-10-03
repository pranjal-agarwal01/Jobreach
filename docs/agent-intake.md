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
