# Setup: local → Supabase → Meta app → production

Follow in order. Steps 1–2 give you a working product in demo mode. Steps 3–5 make it
real. Budget: Supabase free tier, Vercel free tier, Railway ~$5/month, Claude API a few
hundred rupees a month at pilot scale.

## 1. Running locally without Docker

You need Python 3.11+, Node 22+, and a Postgres. Easiest Postgres: `docker run -e
POSTGRES_PASSWORD=postgres -e POSTGRES_DB=impact -p 54329:5432 postgres:16`
(or install Postgres.app on macOS and create a database called `impact`).

```bash
cd backend
cp .env.example .env
python scripts/gen_keys.py >> .env        # appends SECRET_KEY, TOKEN_ENCRYPTION_KEY, COMMENT_HASH_SALT
# edit .env: set DATABASE_URL to your Postgres (add :postgres@ password if needed)
pip install -r requirements-dev.txt
python -m scripts.migrate                 # creates all tables
uvicorn app.main:app --reload             # terminal 1: API on http://localhost:8000
python -m app.worker                      # terminal 2: worker

cd ../frontend
cp .env.example .env.local
npm install && npm run dev                # terminal 3: http://localhost:3000
```

Open http://localhost:3000 → **Try the demo account**. The demo account has 24 fake posts;
the three with `#ad` in the caption behave like real sponsored posts (higher saves, more
buying-intent comments).

Run the tests: create a second database `impact_test`, then `cd backend && python -m pytest`.

## 2. Supabase (production database)

1. Create a project at supabase.com. Region: **Mumbai (ap-south-1)**. Save the database
   password.
2. Apply the schema. Either:
   - **SQL editor**: paste `supabase/migrations/20260926000000_init.sql` and run it, then
     run `create table schema_migrations (name text primary key, applied_at timestamptz default now()); insert into schema_migrations (name) values ('20260926000000_init.sql');`
     so the migrate script knows it's applied; or
   - **CLI**: `npm i -g supabase && supabase login && supabase link --project-ref <ref> && supabase db push`.
3. Get the connection string: Project settings → Database → Connection string → **URI**,
   choose the **session pooler** (port 5432). Turn it into
   `postgresql+psycopg://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
   and put it in `DATABASE_URL`. (The transaction pooler on 6543 also works; the code
   disables prepared statements for it.)
4. Row Level Security is enabled on every table with no policies, so the anon/public keys
   can never read data. The backend uses the Postgres connection directly. You do **not**
   need the Supabase JS client or the anon key anywhere.
5. Later migrations: add a new file in `supabase/migrations/` and run
   `python -m scripts.migrate` (or `supabase db push`) against production before deploying
   code that needs it.

## 3. Meta app (real Instagram login)

Until this is done, only demo mode works. Meta's process takes a few weeks of calendar
time, so start it early.

1. **Prerequisites**: a Facebook account, and your own Instagram account switched to
   **Creator** or **Business** (Instagram → Settings → Account type and tools). You'll test
   with it.
2. Go to developers.facebook.com → My apps → **Create app** → use case
   **"Other" → Business**. Name it after the product.
3. In the app dashboard, add the product **Instagram** and choose **"API setup with
   Instagram login"** (not "with Facebook login").
4. Under *Business login settings*:
   - OAuth redirect URI: `https://<your-domain>/api/auth/instagram/callback`
     (and `http://localhost:3000/api/auth/instagram/callback` for local testing)
   - Deauthorize callback URL: `https://<your-domain>/api/meta/deauthorize`
   - Data deletion request URL: `https://<your-domain>/api/meta/data-deletion`
5. Copy the **Instagram app ID** and **Instagram app secret** (from the Instagram product
   page, not the main app settings) into `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET`.
6. **Testing before review**: App roles → Instagram testers → add your Instagram account,
   then accept the invite in Instagram (Settings → Apps and websites → Tester invites).
   Now "Continue with Instagram" works for tester accounts, up to ~25 of them. Add your
   two pilot influencers here.
7. **App review** (needed before strangers can log in). Request these permissions:
   `instagram_business_basic`, `instagram_business_manage_comments`,
   `instagram_business_manage_insights`. For each you need a screen recording showing
   the login → tag post → report flow and a sentence on why you need it. Also required:
   a public privacy policy URL (`/privacy` in this app — fill in the placeholders first),
   the data deletion URL above, and **Business verification** (Meta Business Suite →
   Settings → Business info; upload your Udyam certificate or GST registration and a
   utility bill/bank statement with the same address).
8. After approval, switch the app from Development to **Live** mode.

Tokens: the app stores a 60-day long-lived token per creator and refreshes it daily when
it is within 10 days of expiry (`worker.handle_refresh_tokens`). If a creator changes
their password or revokes access, their next analysis fails with a "reconnect" message.

## 4. Claude API (better comment classification)

Without a key the rule-based classifier runs (free, decent on Hinglish keywords). With a
key, comments are classified by `claude-haiku-4-5` in batches of 100 and topics are
merged by `claude-sonnet-5`; rules remain the fallback for any failed batch.

1. console.anthropic.com → API keys → create one → `ANTHROPIC_API_KEY`.
2. Set a monthly spend limit in the console (₹2–5k is plenty for a pilot).
3. Cost per report: roughly ₹10–40 for a post with 2,000 comments.

## 5. Deploy

**Backend + worker → Railway** (Render works the same way)

1. New project → Deploy from GitHub → this repo. Set the root directory to `/`
   and the Dockerfile path to `backend/Dockerfile`.
2. Variables: everything from `backend/.env.example` with production values.
   `ENV=production`, `DEMO_MODE=false` (keep `true` while the two influencers pilot if you
   want the sample report visible on the login page), `FRONTEND_URL=https://<your-domain>`.
   The app refuses to start in production with the dev secrets.
3. Add a second service from the same repo/Dockerfile with **start command**
   `python -m app.worker`. Same variables. This is the worker.
4. Add a **pre-deploy command** `python -m scripts.migrate` on the API service, or run it
   manually from the Railway shell after each deploy that includes a migration.
5. Note the API service's public URL, e.g. `https://api-production-xxxx.up.railway.app`.

**Frontend → Vercel**

1. Import the repo, root directory `frontend`.
2. Environment variables: `BACKEND_URL=<Railway API URL>`, `NEXT_PUBLIC_APP_NAME=<name>`,
   `NEXT_PUBLIC_SITE_URL=https://<your-domain>`, `NEXT_PUBLIC_CONTACT_EMAIL=<email>`.
3. Add your domain. Because `/api/*` is proxied by Next.js, the browser only ever talks to
   your domain; the Railway URL never appears in the client.

**After deploy**

- `https://<your-domain>/api/health` should return `{"ok": true, ...}`.
- Sign in with your own tester Instagram account, tag a post, and check the worker logs on
  Railway for the analysis run.

## 6. Going-live checklist

- [ ] Fill in `[LEGAL ENTITY NAME]` and contact email on `/privacy` and `/terms`; have a lawyer read them.
- [ ] Udyam registration (free, udyamregistration.gov.in) — needed for Meta business verification and Razorpay.
- [ ] Meta app approved and set to Live.
- [ ] `DEMO_MODE=false` in production.
- [ ] Anthropic spend limit set.
- [ ] Supabase: enable daily backups (Pro plan) once there are paying users.
- [ ] Error tracking: add Sentry DSN to both services (not wired yet; ~20 lines).
- [ ] Razorpay: not built yet. Until then, upgrade pilot creators by setting `users.plan = 'founding'` in Supabase.
