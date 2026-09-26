# creator-impact

Verified impact reports for Instagram creators. A creator connects Instagram, tags a
sponsored post, and gets a shareable one-page report: buying-intent comments (English,
Hindi, Hinglish), top audience questions and objections, and saves/shares/reach compared
with the creator's own recent posts. The report is what the creator sends to the brand.

**Status:** MVP. Works end to end in demo mode today; real Instagram login needs a Meta app
(see [docs/SETUP.md](docs/SETUP.md)). Product name is still a placeholder (`NEXT_PUBLIC_APP_NAME`).

## Run it in 5 minutes

```bash
git clone https://github.com/seeubh5798/creator-impact && cd creator-impact
docker compose up --build
```

Open http://localhost:3000 → **Try the demo account** → tag the post with `#ad` in its
caption → the report is ready in a few seconds.

Without Docker, see [docs/SETUP.md](docs/SETUP.md#running-locally-without-docker).

## How it works

```
Next.js (frontend)  ──/api/*──▶  FastAPI (backend/app/api)  ──▶  Postgres (Supabase)
                                        │ enqueues                    ▲
                                        ▼                             │
                                 jobs table (Postgres queue)          │
                                        │ claims                      │
                                        ▼                             │
                                 worker (backend/app/worker.py) ──────┘
                                   fetch comments + insights (Instagram Graph API)
                                   preprocess → classify (rules or Claude Haiku)
                                   aggregate → score vs baseline → report JSON
```

- **Backend**: `backend/app`. `api/` routes, `services/` business logic, `analysis/` the
  comment pipeline, `instagram/` the Graph client and a deterministic demo client,
  `queue.py` a tiny Postgres job queue (no Redis), `worker.py` the background process.
- **Frontend**: `frontend/src`. `app/dashboard` post picker, `app/reports/[id]` owner view,
  `app/r/[slug]` public share page (with OpenGraph image), `components/ReportView.tsx`
  the report itself.
- **Database**: `supabase/migrations/*.sql` is the schema source of truth;
  `backend/app/models.py` mirrors it.
- **Scoring**: `backend/app/analysis/scoring.py`. 40% buying-intent rate, 20% saves,
  15% shares, 15% reach, 10% comment rate, each vs the creator's median of their last 20
  non-sponsored posts.

## Development

```bash
# backend
cd backend && pip install -r requirements-dev.txt
python -m scripts.migrate            # applies supabase/migrations to DATABASE_URL
python -m pytest                     # needs a Postgres, see docs/SETUP.md
uvicorn app.main:app --reload        # API on :8000
python -m app.worker                 # background worker

# frontend
cd frontend && npm install && npm run dev   # :3000, proxies /api to :8000
```

Tests: 47 backend tests (unit, full demo flow, billing) run in CI against Postgres; the
frontend is linted and built in CI.

## Docs

- [docs/CHECKLIST.md](docs/CHECKLIST.md): **start here**. Everything you need to do, in order.
- [docs/DEPLOY.md](docs/DEPLOY.md): AWS EC2 + Amplify + Supabase + GoDaddy, CI/CD, releasing.
- [docs/SETUP.md](docs/SETUP.md): local setup, Supabase, Meta app, Razorpay, Claude API.
- [docs/FEATURES.md](docs/FEATURES.md): what creators get, brand side status, plans, how to run the pilot.
- [docs/PRODUCT.md](docs/PRODUCT.md): roadmap and known limitations.
- [CLAUDE.md](CLAUDE.md): conventions for working on this repo with Claude Code.

## Branches and deploys

`main` = development (CI on every push). `prod` = what runs in production: pushing to it
deploys the backend to EC2 via GitHub Actions (tests → image → migrate → roll out) and the
frontend via Amplify. Release with `git checkout prod && git merge --ff-only main && git push`.
