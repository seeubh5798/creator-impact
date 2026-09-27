# What's built, for whom, and how to test it

## For creators (everything below is live in the app)

| Feature | What the creator sees | Why it matters to them |
|---|---|---|
| Instagram login | "Continue with Instagram" (official Meta login, no password shared) | Zero setup; works on phone |
| Post picker | Their last 50 posts/reels with likes and comments; "Tag as sponsored" + brand name | One tap per brand deal |
| Impact report | Score /100, verdict, "better than X% of your own posts" | The number they quote to the brand |
| Buying-intent count | "69 buying-intent comments · 13% of comments" in English, Hindi, Hinglish | Proof the audience wanted to buy, not just like |
| Vs their usual | Saves, shares, reach as "2.2× this creator's usual" | Shows the brand post outperformed, on the creator's own baseline |
| Comment breakdown | Bar: buying intent / questions / praise / objections / other / spam removed | Honest numbers; bots don't count |
| Top questions & objections | "Is it good for oily skin?" ×84, "Price feels high" ×37 | Free product research the brand didn't ask for |
| Quotes | Two real buying-intent comments, usernames hidden | Makes it human |
| Auto re-analysis | Report refreshes at 24h, 72h and 7 days as comments keep coming; "Re-analyse" button | No stale numbers |
| Share | Copy link (`/r/<slug>`), download PNG, print to PDF, make private | Send on WhatsApp or email |
| Public page | What the brand opens: same report + "Are you a creator? First 3 reports free" | Every share recruits the next creator |
| Link previews | OpenGraph image with the score when the link is pasted in WhatsApp/Slack/LinkedIn | The brand sees the score before clicking |
| Plans | Free 3 reports/month → Pro ₹299/mo or ₹2,999/yr → Pro+ ₹999/mo or ₹9,999/yr, via Razorpay (UPI/cards) | Revenue |
| Privacy | Delete account button; Meta deauthorize/deletion callbacks; commenter names never stored; comment text purged after 30 days | Meta app review and DPDP Act |

Not built yet for creators: rate calculator, live media kit, campaign (multi-post)
reports, white-label. Pro/Pro+ are sold on unlimited reports + no footer today; the
"coming soon" items are labelled as such on `/billing`.

## For brands

**Nothing brand-facing is built yet, on purpose.** Brands see the public report page
(`/r/<slug>`) that a creator shares with them; that is the whole brand experience for the
pilot. It has no login and no dashboard.

The brand side (invite creators, compare creators, request a verified report, ₹499/report
and ₹9,999/₹29,999 monthly plans) is next after the pilot proves creators send reports.
Everything it needs already exists in the data model: reports are per post, tagged with a
brand name, and `view_count` records when a brand opened the link.

## Payments and plans (Razorpay)

| Plan | Price | Limit | `users.plan` |
|---|---|---|---|
| Free | ₹0 | 3 reports/month, "Made with" footer | `free` |
| Pro | ₹299/month or ₹2,999/year | Unlimited | `pro` |
| Pro+ | ₹999/month or ₹9,999/year | Unlimited + coming features | `pro_plus` |
| Founding | ₹0 (you set it manually for pilot creators) | Unlimited | `founding` |

How it works: `/billing` → "Upgrade" → backend creates a Razorpay **subscription** →
Razorpay Checkout opens (UPI autopay, cards, netbanking) → on success the backend verifies
the signature and activates the plan immediately → Razorpay webhooks (`subscription.charged`,
`.cancelled`, `.halted`, ...) keep it in sync → the worker downgrades lapsed plans daily.
Cancelling keeps access until the end of the paid period. Setup: [SETUP.md §5](SETUP.md#5-razorpay-subscriptions).

To give a pilot creator free Pro: Supabase → Table editor → `users` → set `plan` to
`founding`. To see who paid: `subscriptions` table; every webhook is in `billing_events`.

## How to run the pilot

Goal: learn whether creators **send** the report to brands. Not whether they like it.

**Week 1: before they touch it**
1. Deploy (AWS_SETUP.md). Keep `DEMO_MODE=true` so the "Try the demo account" button exists;
   send creators the public demo report link as the pitch.
2. Meta app: add both creators' Instagram accounts as **Instagram testers** (SETUP.md §3).
   They accept the invite in Instagram → Settings → Apps and websites → Tester invites.
   Their accounts must be Creator or Business type.
3. In Supabase, after they log in once, set their `users.plan = 'founding'`.

**Week 1: onboarding call (20 min, screen share)**
1. They open proofluence.com → Continue with Instagram → approve the 3 permissions.
2. Dashboard shows their posts. Ask them to tag their **last 3 brand posts** with brand names.
3. Reports take 1–3 minutes each (real posts have more comments than the demo). Open each
   together. Ask: *"Is anything here wrong?"* (spam not caught, a comment misread as buying
   intent, Hinglish missed). Note every answer; that's your classifier backlog.
4. Ask: *"Which brand would you send this to, and what would you say?"* Then ask them to
   actually send it, on the call, from their WhatsApp.

**Weeks 2–4: measure**
- `reports.view_count` in Supabase tells you if the brand opened the link. That's the metric.
- Ask each creator weekly (WhatsApp is fine): did the brand reply? did it change the rate
  or get a repeat deal?
- New brand post → do they tag it without being asked? If yes on both, build the brand side.

**What "working" looks like after 4 weeks**: both creators tagged at least one new post on
their own, at least one brand opened a report, and one creator can name a deal where the
report helped. If none of that happened, the problem is the report, not the code; fix
what they said was wrong before adding features.

**Things that will go wrong the first time** (all recoverable, fix and redeploy):
- Instagram returns a metric the client doesn't expect → analysis job fails, report says
  "failed" → `docker compose logs worker` shows the exact API error.
- A creator's post is older than their switch to a Creator account → no insights →
  report still renders, with saves/shares missing.
- Hinglish spelling variants the rules miss → add them to `backend/app/analysis/lexicon.py`
  or set `ANTHROPIC_API_KEY` for the LLM classifier.
