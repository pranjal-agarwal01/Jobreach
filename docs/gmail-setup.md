# Setting up "Continue with Google" and Gmail drafts

One Google Cloud OAuth client serves both: signing in with Google (through Supabase) and
connecting Gmail so letters are created as drafts (through the Jobreach API). About 10 minutes.

While the app is in **Testing** (step 4), only the Gmail addresses you list can connect, up to 100,
and a Gmail connection lasts 7 days before the person reconnects. Opening Jobreach to the public
needs Google's app verification and a yearly security assessment, because the permission that
allows drafts (`gmail.compose`) is one Google classes as restricted.

## Google Cloud (console.cloud.google.com)

1. **Create a project**, for example "Jobreach", with the Google account that should own the app.
2. **Enable the Gmail API**: APIs & Services → Library → search "Gmail API" → Enable.
3. **Branding** (Google Auth Platform, formerly "OAuth consent screen"): app name `Jobreach`, your
   support email, your developer contact email.
4. **Audience**: user type **External**, publishing status **Testing**. Under Test users, add
   every Gmail address that will test (your three).
5. **Data access** → Add or remove scopes: `openid`, `.../auth/userinfo.email`,
   `.../auth/userinfo.profile` and `https://www.googleapis.com/auth/gmail.compose` (search
   "gmail.compose"). Save.
6. **Clients** → Create client → **Web application**, name `Jobreach web`.
   - Authorized JavaScript origins: `http://localhost:3000`
   - Authorized redirect URIs:
     - `http://localhost:8000/gmail/callback` (Gmail drafts)
     - `https://pksaqwmgibkuyydlwdfb.supabase.co/auth/v1/callback` (Continue with Google)

   Create, then copy the **Client ID** and **Client secret**.

## Jobreach (backend/.env)

7. Fill in the two lines that are already there (the encryption key was generated for you):
   ```
   GOOGLE_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=...
   ```
   Then restart the API and the worker.

## Supabase (supabase.com/dashboard/project/pksaqwmgibkuyydlwdfb)

8. Open the Google provider directly:
   https://supabase.com/dashboard/project/pksaqwmgibkuyydlwdfb/auth/providers?provider=Google
   (or Authentication → Sign In / Providers → the **Supabase Auth** tab → Auth Providers → Google;
   not the Third-Party Auth tab). Turn on "Enable Sign in with Google", paste the same Client ID
   and Client secret, and Save. Its Callback URL is the second redirect URI in step 6.

   Leave **OAuth Server** (Authentication → OAuth Server) off: it would make Jobreach a sign-in
   provider for other apps, which Jobreach doesn't need.
9. Authentication → URL Configuration: Site URL `http://localhost:3000`, and add
   `http://localhost:3000/**` to Redirect URLs.

## What testers will see

- **Continue with Google** on the sign-in page: no password and no confirmation email.
- **Connect Gmail** on Today and Add leads. Before anyone is sent to Google, Jobreach shows a short
  guide to the pages Google will show:
  1. choose the Gmail account;
  2. "Google hasn't verified this app" while the app is in Testing: press Continue, not "Back to
     safety" ("Access blocked" means the address isn't a test user yet);
  3. "Manage drafts and send emails": tick the box if there is one, then Continue. Gmail has no
     drafts-only permission, and Jobreach only ever creates drafts (the code refuses every other
     Gmail call);
  4. back in Jobreach.

  If the drafts box is left unticked, Jobreach says so and offers to try again.
- Letters that pass every check land in Gmail Drafts with the resume attached; ones that need a
  look have a **Draft in Gmail** button on their page. Disconnecting (Profile → Gmail) removes the
  access at Google.

## Send for me (opt-in)

Off by default. A person turns it on in Profile, under Gmail, after a screen that says plainly what it
does. From then on, letters that passed every check are sent from their Gmail (drafts.send, the
same gmail.compose permission): at random moments inside the hours they chose, at most their
daily number (20 at most), and never sooner than their waiting time after the letter reached their
drafts. Until then they can edit it in Gmail (the edited version goes) or press "Don't send this
one" on its page. Letters that need a look, letters marked sent or closed, and letters whose post
is more than three days old are never sent for them. It pauses itself after two bounces in a week,
or when Gmail's own sending limit is reached. Only Send for me can call drafts.send; the code
refuses it anywhere else, and refuses sending a new message or reading mail everywhere.

## When Google has verified the app

Set `GOOGLE_APP_VERIFIED=1` (backend/.env and Render). The guide then leaves out the "Google hasn't
verified this app" step, and anyone can connect without being listed as a test user.

## When the API runs on Render

- Add `https://<your-render-api>/gmail/callback` to the client's redirect URIs.
- Give Render `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and the **same** `TOKEN_ENCRYPTION_KEY` as
  `backend/.env` (a different key cannot read connections already stored).
- When the web app is hosted, add its address to the JavaScript origins, to Supabase's redirect
  URLs, and set `FRONTEND_URL` and `CORS_ORIGINS` on Render.
