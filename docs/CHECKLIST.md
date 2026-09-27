# Proofluence: your to-do list, in order

Code, pipelines and docs are done. These are the accounts, keys and clicks only you can do.
Full click-by-click instructions: **[AWS_SETUP.md](AWS_SETUP.md)**.

## Today: run it on your Mac (15 min)

```bash
git clone https://github.com/seeubh5798/creator-impact && cd creator-impact
docker compose up --build          # port 3000/8000 busy? WEB_PORT=3001 API_PORT=8001 docker compose up --build
```
Open http://localhost:3000 (or :3001) → **Try the demo account** → tag the `#ad` post → report in ~10 s.

## Setup, in order (half a day)

| # | Task | Result | Guide |
|---|------|--------|-------|
| 1 | Buy `proofluence.com` on GoDaddy, clear default DNS records | domain | [§1](AWS_SETUP.md#1-domain-godaddy-10-min) |
| 2 | AWS account, root MFA, `shubham-admin` IAM user + MFA, $30 budget alert, region Mumbai | safe AWS account | [§2](AWS_SETUP.md#2-aws-account-30-min-do-this-carefully-once) |
| 3 | Supabase org `Proofluence`, projects `proofluence-dev` + `proofluence-prod` (Mumbai), save passwords, copy session-pooler URIs | 2 `DATABASE_URL`s | [§3](AWS_SETUP.md#3-supabase-two-databases-15-min) |
| 4 | Security group `proofluence-api-sg`, EC2 `proofluence-dev-api` (t3.micro) + Elastic IP, DNS `A api-dev`, run `ec2-setup.sh` | dev server | [§4](AWS_SETUP.md#4-ec2-the-dev-server-30-min) |
| 5 | Same for `proofluence-prod-api` (t3.small), DNS `A api` | prod server | [§5](AWS_SETUP.md#5-ec2-the-prod-server-15-min) |
| 6 | `gen_keys.py` twice; fill `/opt/proofluence/.env` on each box from `deploy/env.dev.example` / `env.prod.example`; back both up in a password manager | server config | [§6](AWS_SETUP.md#6-the-server-env-files-20-min) |
| 7 | Make repo **private**; GitHub Environments `dev` + `production`, each with `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` | CI/CD can deploy | [§7](AWS_SETUP.md#7-github-environments-and-secrets-10-min) |
| 8 | Actions → Deploy backend → run on `main`, then `prod`; `curl …/health` on both | APIs live, DB tables created | [§8](AWS_SETUP.md#8-first-backend-deploys-10-min) |
| 9 | Amplify app `proofluence-web`: branch `main` (dev vars), branch `prod` (overrides), custom domains `dev.` / `www.` / root forwarding | sites live | [§9](AWS_SETUP.md#9-amplify-the-websites-20-min) |
| 10 | Meta apps `Proofluence Dev` + `Proofluence`, URLs per env, add pilot creators as Instagram testers | real Instagram login | [§10](AWS_SETUP.md#10-meta-apps-when-youre-ready-for-real-instagram-logins) |
| 11 | Razorpay: test keys + test plans → dev; KYC, live keys + live plans → prod; webhooks | payments | [§11](AWS_SETUP.md#11-razorpay), [SETUP §5](SETUP.md#5-razorpay-subscriptions) |
| 12 | Optional: Anthropic API keys (one per env) with a monthly limit | better classification | [SETUP §4](SETUP.md#4-claude-api-better-comment-classification) |
| 13 | Udyam registration (free) — Meta business verification and Razorpay KYC use it | | udyamregistration.gov.in |

## Where every secret lives (never in GitHub)

| Secret | Lives in |
|---|---|
| DB URLs, app secrets, Meta, Razorpay, Anthropic keys | `/opt/proofluence/.env` on each EC2 box (+ your password manager) |
| EC2 IPs and SSH private keys | GitHub → Settings → Environments → `dev` / `production` |
| `.pem` key files | `~/.ssh/` on your Mac only |
| Site config (`BACKEND_URL`, `NEXT_PUBLIC_*`) | Amplify → Environment variables (these aren't secret) |
| Supabase DB passwords, AWS root/admin logins | password manager |

## Every release (2 minutes)

```bash
git push                                                    # main -> dev deploys itself
git checkout prod && git merge --ff-only main && git push   # -> prod deploys itself
git checkout main
```

## Pilot

Follow [FEATURES.md](FEATURES.md#how-to-run-the-pilot). The metric: do creators send the
report to a brand, and does the brand open it (`reports.view_count`)?

## Before public launch

- [ ] Fill `[LEGAL ENTITY NAME]` and contact email on `/privacy` and `/terms` (have a lawyer read them)
- [ ] Meta business verification + app review for the `Proofluence` app; then `DEMO_MODE=false` on prod
- [ ] Razorpay live mode on prod
- [ ] Supabase `proofluence-prod` → Pro plan (daily backups)
- [ ] UptimeRobot monitors on `https://api.proofluence.com/health` and the site
