# Product notes

## What's built (MVP)

| Feature | Where |
|---|---|
| Instagram login (official API with Instagram Login), 60-day tokens auto-refreshed | `backend/app/api/auth.py`, `instagram/client.py`, `worker.py` |
| Demo account so the product works before Meta approval | `instagram/demo.py`, "Try the demo account" on `/login` |
| Post picker, tag a post as sponsored with brand name | `frontend/src/app/dashboard` |
| Comment fetch (incl. replies), spam/duplicate/own-comment filtering, language detection (en/hi/hinglish) | `analysis/preprocess.py` |
| Classification: buying intent / question / objection / praise / other / spam, with topics | `analysis/classifier.py` (LLM + rules), `analysis/topics.py` |
| Baseline from the creator's last 20 non-sponsored posts (medians) | `services/baseline.py` |
| Impact score 0–100, verdict, percentile vs own posts | `analysis/scoring.py` |
| Re-analysis at 24h / 72h / 7d as comments keep coming; manual re-analyse | `services/reports.py`, `queue.py` |
| Owner report page: copy link, download PNG, print to PDF, make private | `frontend/src/app/reports/[id]` |
| Public share page with OpenGraph preview and creator CTA (the growth loop) | `frontend/src/app/r/[slug]` |
| Free plan: 3 reports/month; pro/pro_plus/founding unlimited | `services/reports.py` |
| Privacy: no commenter names stored, comment text purged after 30 days, encrypted tokens, Meta deletion callbacks | `security.py`, `api/meta.py`, `worker.py` |

## Next (in order)

1. **Pilot with 2 creators** as Instagram testers. Measure: do they send the report to a brand?
2. **Razorpay subscriptions** (Pro ₹299, Pro+ ₹999): checkout page, webhook → `users.plan`.
3. **Rate calculator**: suggested fee from the creator's own impact history + followers.
4. **Live media kit** at `/c/<username>`: public profile with impact stats across reports.
5. **Campaign reports**: several posts/stories for one brand in a single report.
6. **White-label** (logo, colours) for managers; Manager plan.
7. **Brand side**: invite creators, dashboard comparing creators, per-report billing.
8. Stories (24h) support: needs `instagram_business_manage_insights` on stories and polling before expiry.

## Known limitations

- Instagram insights are only available for posts made after the account became a
  Creator/Business account; older posts fall back to like/comment counts.
- `views` has no baseline yet (not in the samples), shown as a plain number.
- Topic labels come from rules unless `ANTHROPIC_API_KEY` is set; rules give coarse buckets
  ("Where to buy") rather than specific questions ("Is it good for oily skin?").
- The demo account is shared by everyone who clicks "Try the demo". Fine for a pilot; turn
  off `DEMO_MODE` in production.
- No email/notifications yet: creators must open the app to see the finished report.

## Pricing (planned)

Creators: Free (3 reports/month, footer) · Pro ₹299/month · Pro+ ₹999/month.
Managers: ₹2,999/month for 10 creators. Brands: ₹499/report, Starter ₹9,999/month,
Growth ₹29,999/month. Founding creators (pilot): free Pro for 6 months.
