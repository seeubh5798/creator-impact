# Working on creator-impact

Read README.md first. This file is for conventions that aren't obvious from the code.

## Stack and layout
- `backend/` FastAPI + SQLAlchemy 2 + psycopg 3, Python 3.11. Worker in `app/worker.py`.
- `frontend/` Next.js 16 App Router, TypeScript, Tailwind v4. Read `frontend/AGENTS.md`
  and `frontend/node_modules/next/dist/docs/` before touching Next-specific APIs.
- `supabase/migrations/` is the schema source of truth. A schema change = a new
  timestamped `.sql` file there **and** the matching edit in `backend/app/models.py`.
  `python -m scripts.migrate` applies migrations once each (tracked in `schema_migrations`).

## Rules
- Never store commenter usernames or raw comment ids. Comment ids are HMAC-hashed
  (`security.hash_comment_id`); comment text lives in `comment_labels.text_excerpt` and is
  purged after 30 days by the worker. Keep it that way: it's a Meta app-review requirement.
- Instagram access tokens are Fernet-encrypted at rest (`security.encrypt_token`).
- Every LLM call must have a rule-based fallback and must never fail a report
  (see `analysis/classifier.py`). Reports must always be producible with partial data.
- Jobs go through `app/queue.py` (`enqueue` with a `dedupe_key`). Handlers live in
  `worker.py`; they must be idempotent because jobs retry.
- Browser → backend calls go through the Next.js `/api/*` rewrite, never directly, so the
  session cookie stays first-party. Server components use `backendUrl()`.
- Money/plan logic is in `services/reports.py` (`usage`, `QuotaExceeded`).

## Testing
- `cd backend && python -m pytest` needs Postgres at `TEST_DATABASE_URL`
  (default `postgresql+psycopg://postgres@127.0.0.1:54329/impact_test`). Tests drop and
  recreate the schema from the migrations, so they also validate the SQL.
- The demo Instagram client (`instagram/demo.py`) is deterministic; the E2E test
  `tests/test_flow.py` runs the whole product against it. Add to it when you add a feature.
- Frontend: `npm run lint && npm run build` must pass (CI runs both).

## Things not done yet (see docs/PRODUCT.md)
Razorpay billing, rate calculator, media kit, campaign (multi-post) reports, brand side.
