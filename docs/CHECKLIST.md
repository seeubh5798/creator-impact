# Your to-do list, in order

Everything a human has to do. Code and pipelines are done; these are accounts, keys and
clicks. Time estimates are for a first pass. Details for each step live in the linked docs.

## Today (1 hour): run it on your laptop

**Option A: Docker (recommended, nothing else to install)**

```bash
git clone https://github.com/seeubh5798/creator-impact && cd creator-impact
docker compose up --build            # first run ~3 min; later runs ~10 s
```
If port 3000 or 8000 is taken on your machine: `WEB_PORT=3001 API_PORT=8001 docker compose up`.

Open http://localhost:3000 → **Try the demo account** → on a post with `#ad` click
**Tag as sponsored** → report appears in ~10 s. Stop with `Ctrl+C`; `docker compose down -v`
wipes the local database.

**Option B: without Docker** (when you want hot-reload while developing)

```bash
# needs Python 3.11+, Node 22+, and Postgres running locally (or `docker compose up db`)
cd backend && cp .env.example .env && python scripts/gen_keys.py >> .env
pip install -r requirements-dev.txt && python -m scripts.migrate
uvicorn app.main:app --reload                  # terminal 1
python -m app.worker                           # terminal 2
cd ../frontend && cp .env.example .env.local && npm install && npm run dev   # terminal 3
```

Tests: `cd backend && python -m pytest` (needs a database named `impact_test`),
`cd frontend && npm run lint && npm run build`.

## This week (half a day): accounts

| # | Do | Where the value goes | Doc |
|---|----|---------------------|-----|
| 1 | Create a Supabase project (Mumbai), run the two SQL files in `supabase/migrations/` in the SQL editor, copy the **session pooler** URI | `DATABASE_URL` | [SETUP.md §2](SETUP.md#2-supabase-production-database) |
| 2 | Buy the domain on GoDaddy. Decide: `yourdomain.com` = app, `api.yourdomain.com` = backend | `FRONTEND_URL`, `API_DOMAIN`, `NEXT_PUBLIC_SITE_URL` | [DEPLOY.md §1](DEPLOY.md#1-godaddy-dns) |
| 3 | AWS account → launch the EC2 box, run `deploy/ec2-setup.sh`, fill `/opt/creator-impact/.env` | server | [DEPLOY.md §2](DEPLOY.md#2-ec2-backend--worker) |
| 4 | GitHub → repo Settings → Secrets: `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` | pipeline | [DEPLOY.md §3](DEPLOY.md#3-github-secrets-and-the-first-deploy) |
| 5 | AWS Amplify → connect the repo, branch `prod`, set env vars, add the domain | frontend | [DEPLOY.md §4](DEPLOY.md#4-amplify-frontend) |
| 6 | Meta developer app → Instagram product → add redirect/deauth/deletion URLs → add your 2 creators as **Instagram testers** | `INSTAGRAM_APP_ID/SECRET` | [SETUP.md §3](SETUP.md#3-meta-app-real-instagram-login) |
| 7 | Razorpay account → KYC → create 4 subscription plans → webhook | `RAZORPAY_*` | [SETUP.md §5](SETUP.md#5-razorpay-subscriptions) |
| 8 | Anthropic console → API key with a ₹2–5k monthly limit (optional, better classification) | `ANTHROPIC_API_KEY` | [SETUP.md §4](SETUP.md#4-claude-api-better-comment-classification) |
| 9 | Udyam registration (free, 15 min) — Meta business verification and Razorpay both ask for it | — | udyamregistration.gov.in |

## Release (5 minutes, every time)

```bash
git checkout prod && git merge --ff-only main && git push
```
Backend: GitHub Actions runs tests → builds the image → migrates the Supabase DB →
restarts API + worker on EC2 (watch it under the Actions tab). Frontend: Amplify builds and
deploys `prod` by itself. Both take ~5 minutes. [DEPLOY.md §5](DEPLOY.md#5-releasing)

## Pilot (weeks 2–6)

Follow [FEATURES.md](FEATURES.md#how-to-run-the-pilot): onboard the two creators as
Instagram testers, generate reports on their last 3–5 brand posts, and track whether they
send a report to a brand. That single metric decides whether to keep building.

## Before Meta app review / public launch

- [ ] Fill `[LEGAL ENTITY NAME]` and contact email on `/privacy` and `/terms` (frontend/src/app/privacy, terms)
- [ ] Meta business verification (Udyam/GST + address proof), submit app review with screen recordings
- [ ] `DEMO_MODE=false` on the server
- [ ] Switch Razorpay from test keys to live keys, re-create the plans in live mode
- [ ] Supabase: enable Point-in-Time Recovery (Pro plan) once paying users exist
- [ ] Pick the final name: change `NEXT_PUBLIC_APP_NAME` in Amplify, buy the domain, done
