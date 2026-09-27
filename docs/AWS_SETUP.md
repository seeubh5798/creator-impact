# Proofluence: AWS + Supabase setup, dev and prod, from zero

Written for someone who has never used AWS. Follow top to bottom once; it takes about
half a day spread over 1–2 days (DNS and Meta verification involve waiting).

**The one rule: secrets never go into GitHub.** Every real value below goes into one of
three places: the `.env` file on a server, GitHub *Environment secrets*, or the Amplify
console. The repo only has `*.example` templates, `.gitignore` blocks `.env` files and
`.pem` keys, and CI runs a secret scanner (gitleaks) on every push.

---

## 0. The names (use exactly these)

| | **dev** | **prod** |
|---|---|---|
| Git branch | `main` | `prod` |
| Website | `https://dev.proofluence.com` | `https://proofluence.com` (+ `www`) |
| API | `https://api-dev.proofluence.com` | `https://api.proofluence.com` |
| Supabase project | `proofluence-dev` | `proofluence-prod` |
| EC2 instance | `proofluence-dev-api` (t3.micro) | `proofluence-prod-api` (t3.small) |
| EC2 key pair | `proofluence-dev` → `proofluence-dev.pem` | `proofluence-prod` → `proofluence-prod.pem` |
| Security group | `proofluence-api-sg` (shared) | `proofluence-api-sg` (shared) |
| Elastic IP (Name tag) | `proofluence-dev-eip` | `proofluence-prod-eip` |
| GitHub Environment | `dev` | `production` |
| Amplify | app `proofluence-web`, branch `main` | same app, branch `prod` |
| Meta app | `Proofluence Dev` | `Proofluence` |
| Razorpay | Test mode | Live mode |
| Backend image | `ghcr.io/seeubh5798/proofluence-backend:dev` | `…:production` |
| Server folder | `/opt/proofluence` | `/opt/proofluence` |
| AWS region | **ap-south-1 (Mumbai)** everywhere | same |

How code flows: push to `main` → GitHub Actions deploys the backend to the **dev** box and
Amplify deploys the **dev** site. Test there. Merge `main` into `prod` → same thing on
**prod**. Database migrations run automatically on each deploy against that
environment's Supabase database.

```
            GitHub (main / prod)
             │                 │
   GitHub Actions          Amplify (Next.js)
   test→build→deploy        dev.proofluence.com / proofluence.com
             │                 │  /api/* proxied
             ▼                 ▼
   EC2 (Caddy HTTPS → api + worker containers)
   api-dev.proofluence.com / api.proofluence.com
             │
             ▼
   Supabase Postgres: proofluence-dev / proofluence-prod
```

If you end up with a different domain (e.g. `proofluence.ai`), replace `proofluence.com`
everywhere below; nothing in the code hard-codes it.

---

## 1. Domain (GoDaddy, 10 min)

1. godaddy.com → search `proofluence.com` → buy it (1 year is fine; skip the add-ons:
   no email, no website builder, no "full domain privacy" upsell unless you want it).
2. My Products → the domain → **DNS**. Delete the default `A @ Parked` record and the
   `CNAME www @` record. Leave NS and SOA alone. You'll add records in steps 4, 5 and 9.

## 2. AWS account (30 min, do this carefully once)

1. aws.amazon.com → **Create an AWS account**. Use a dedicated email (e.g.
   `aws@proofluence.com` later; your Gmail is fine now). Account name `proofluence`.
   Personal or Business: Business if you have a registered entity, else Personal.
   Add a card (a ₹2 verification charge is refunded), verify phone, choose **Basic support (free)**.
2. **Secure the root user** (the email login): top-right account menu → Security
   credentials → **Assign MFA device** → Authenticator app (Google Authenticator/Authy).
   After this, you use root only for billing emergencies.
3. **Create your daily admin login**: search "IAM" → Users → Create user →
   name `shubham-admin` → ✓ Provide console access → custom password → Next →
   Attach policies directly → `AdministratorAccess` → Create. Then open the user →
   Security credentials → assign MFA. Note the **sign-in URL** shown on the IAM dashboard
   (`https://<account-id>.signin.aws.amazon.com/console`), sign out, sign in with this user.
4. **Budget alarm** (so you never get a surprise bill): search "Budgets" → Create budget →
   Use a template → **Monthly cost budget** → amount `$30` → your email → Create.
5. Region: top-right region picker → **Asia Pacific (Mumbai) ap-south-1**. Check this every
   time you open the console; resources in another region are invisible here.

## 3. Supabase: two databases (15 min)

1. supabase.com → Sign in with GitHub → **New organization** `Proofluence` (Free plan).
2. **New project** → Name `proofluence-dev` → Database password: click *Generate* and
   **save it in your password manager** → Region **South Asia (Mumbai)** → Create.
3. Repeat: project `proofluence-prod`, new generated password, Mumbai.
4. For each project get the connection string: open the project → **Connect** button
   (top bar) → **Session pooler** → copy the URI. It looks like
   `postgresql://postgres.abcdefghij:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
   - Replace `[YOUR-PASSWORD]` with the saved password. If the password contains `@ : / ? #`,
     URL-encode them (`@`→`%40`, `:`→`%3A`, `/`→`%2F`, `?`→`%3F`, `#`→`%23`). Generated
     passwords are alphanumeric, so usually nothing to do.
   - Change the prefix `postgresql://` to `postgresql+psycopg://`.
   - That final string is `DATABASE_URL` for that environment (step 6).
5. **Don't create tables by hand.** The deploy pipeline runs the migrations in
   `supabase/migrations/` automatically. After the first deploy you'll see the tables in
   Table Editor.
6. Free-tier note: a Supabase free project pauses after 7 days with no activity. The worker
   touches the DB constantly, so a running server keeps it awake. Before real paying users,
   upgrade `proofluence-prod` to Pro ($25/mo) for daily backups.

## 4. EC2: the dev server (30 min)

**4a. Security group** (firewall, create once, used by both servers)
EC2 → Network & Security → **Security Groups** → Create →
name `proofluence-api-sg`, description "Proofluence API", VPC default. Inbound rules:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | My IP | you, from your laptop |
| SSH | 22 | 0.0.0.0/0 | GitHub Actions deploys (see note) |
| HTTP | 80 | 0.0.0.0/0 | HTTPS certificate issuance + redirect |
| HTTPS | 443 | 0.0.0.0/0 | the API |

Note: GitHub's runner IPs change constantly, so SSH must be open to the internet for
deploys. It is key-only (passwords are disabled by the setup script) and fail2ban blocks
brute force. That's standard for this setup.

**4b. Key pair** EC2 → Key Pairs → Create → name `proofluence-dev`, type ED25519, format
`.pem` → it downloads `proofluence-dev.pem`. On your Mac:
```bash
mkdir -p ~/.ssh && mv ~/Downloads/proofluence-dev.pem ~/.ssh/ && chmod 400 ~/.ssh/proofluence-dev.pem
```
Never put this file in the repo (it's gitignored anyway).

**4c. Launch** EC2 → Instances → **Launch instances**:
- Name `proofluence-dev-api`
- AMI **Ubuntu Server 24.04 LTS**, architecture 64-bit (x86)
- Instance type **t3.micro** (dev is light; free-tier eligible on new accounts)
- Key pair `proofluence-dev`
- Network settings → Edit → Select existing security group → `proofluence-api-sg`
- Storage 20 GiB gp3
- Launch.

**4d. Elastic IP** (a permanent IP; without it the IP changes on every stop/start)
EC2 → Elastic IPs → **Allocate** → Allocate. Select it → Actions → **Associate** →
instance `proofluence-dev-api` → Associate. Add tag Name = `proofluence-dev-eip`.
Copy the IP, e.g. `13.233.10.20`. An Elastic IP attached to a running instance is cheap
(about $3.6/mo); an unattached one costs the same, so release any you stop using.

**4e. DNS** GoDaddy → DNS → Add record: **Type A, Name `api-dev`, Value `<dev Elastic IP>`,
TTL 600**. Check after a few minutes: `dig +short api-dev.proofluence.com` should print the IP.

**4f. Bootstrap the box** (from the repo folder on your Mac)
```bash
scp -i ~/.ssh/proofluence-dev.pem deploy/ec2-setup.sh ubuntu@<DEV_IP>:~
ssh -i ~/.ssh/proofluence-dev.pem ubuntu@<DEV_IP> 'bash ec2-setup.sh'
```
It installs Docker, creates `/opt/proofluence/.env` (empty, permissions 600), enables
automatic security updates, fail2ban and swap.

Tip: add this to `~/.ssh/config` so you can just type `ssh proofluence-dev`:
```
Host proofluence-dev
  HostName <DEV_IP>
  User ubuntu
  IdentityFile ~/.ssh/proofluence-dev.pem
Host proofluence-prod
  HostName <PROD_IP>
  User ubuntu
  IdentityFile ~/.ssh/proofluence-prod.pem
```

## 5. EC2: the prod server (15 min)

Repeat step 4 with: key pair `proofluence-prod`, instance `proofluence-prod-api`, type
**t3.small** (2 GB RAM; comment analysis of big reels needs it), same security group,
Elastic IP tagged `proofluence-prod-eip`, DNS record **A `api` → prod IP**, then
`ec2-setup.sh` on it.

## 6. The server `.env` files (20 min)

Generate secrets on your Mac, **separately for dev and for prod** (never share them):
```bash
python3 backend/scripts/gen_keys.py      # prints SECRET_KEY, TOKEN_ENCRYPTION_KEY, COMMENT_HASH_SALT
```
(needs `pip3 install cryptography` once).

On each server, `ssh proofluence-dev` then `nano /opt/proofluence/.env`, paste the
template, fill it, `Ctrl+O Enter Ctrl+X`. Templates: `deploy/env.dev.example`,
`deploy/env.prod.example`. Filled-in dev example:

```dotenv
ENV=production
DATABASE_URL=postgresql+psycopg://postgres.abcdefghij:Xk29fLq8TzM3@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
FRONTEND_URL=https://dev.proofluence.com
API_DOMAIN=api-dev.proofluence.com
SECRET_KEY=<from gen_keys.py>
TOKEN_ENCRYPTION_KEY=<from gen_keys.py>
COMMENT_HASH_SALT=<from gen_keys.py>
INSTAGRAM_APP_ID=
INSTAGRAM_APP_SECRET=
DEMO_MODE=true
ANTHROPIC_API_KEY=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
RAZORPAY_PLAN_PRO_MONTHLY=
RAZORPAY_PLAN_PRO_YEARLY=
RAZORPAY_PLAN_PRO_PLUS_MONTHLY=
RAZORPAY_PLAN_PRO_PLUS_YEARLY=
```

What each line is:

| Variable | dev | prod | Where you get it |
|---|---|---|---|
| `ENV` | `production` | `production` | literal. Enables secure cookies and refuses to start with dev secrets |
| `DATABASE_URL` | proofluence-dev URI | proofluence-prod URI | step 3 |
| `FRONTEND_URL` | `https://dev.proofluence.com` | `https://proofluence.com` | your domain |
| `API_DOMAIN` | `api-dev.proofluence.com` | `api.proofluence.com` | your domain; Caddy gets the HTTPS cert for it |
| `SECRET_KEY` / `TOKEN_ENCRYPTION_KEY` / `COMMENT_HASH_SALT` | generated | **different** generated | `gen_keys.py`. Never change `TOKEN_ENCRYPTION_KEY` or `COMMENT_HASH_SALT` after users exist (it breaks stored tokens / comment de-dup) |
| `INSTAGRAM_APP_ID/SECRET` | Proofluence Dev app | Proofluence app | step 10; empty = demo only |
| `DEMO_MODE` | `true` | `true` during pilot, `false` after Meta approval | |
| `ANTHROPIC_API_KEY` | optional | optional | console.anthropic.com → API keys (one key per env) |
| `RAZORPAY_*` | Test mode keys + plan ids | Live mode keys + plan ids | step 11; empty = billing off |

`BACKEND_IMAGE` gets appended by the deploy pipeline automatically; don't add it yourself.
Back up both filled files in your password manager (1Password/Bitwarden secure note).

## 7. GitHub: environments and secrets (10 min)

1. **Make the repo private** (it is public right now): repo → Settings → General → bottom
   → Danger zone → Change visibility → Private. Nothing breaks.
2. Settings → **Environments** → New environment `dev` → **Add environment secret** ×3:

   | Secret | Value |
   |---|---|
   | `EC2_HOST` | dev Elastic IP |
   | `EC2_USER` | `ubuntu` |
   | `EC2_SSH_KEY` | entire contents of `~/.ssh/proofluence-dev.pem` (`cat ~/.ssh/proofluence-dev.pem \| pbcopy`), including the BEGIN/END lines |

   Under "Deployment branches" choose **Selected branches** → add `main`.
3. New environment `production` → same three secrets with the **prod** IP and
   `proofluence-prod.pem`. Deployment branches → `prod` only. If available on your plan,
   tick **Required reviewers** → yourself, so prod deploys wait for your click.

## 8. First backend deploys (10 min)

1. GitHub → Actions → **Deploy backend** → Run workflow → branch `main`. Watch
   test → build → deploy. The deploy job copies the compose files, runs migrations on
   `proofluence-dev`, starts `api`, `worker`, `caddy`, and health-checks.
2. Check: `curl https://api-dev.proofluence.com/health` →
   `{"ok":true,"demo_mode":true,"llm":false,"billing":false}`.
   In Supabase `proofluence-dev` → Table Editor you now see all tables.
3. Same for prod: Run workflow → branch `prod` → approve if you set a reviewer →
   `curl https://api.proofluence.com/health`.

From now on you never run this by hand: every push to `main`/`prod` that touches the
backend deploys itself.

## 9. Amplify: the websites (20 min)

1. AWS console (Mumbai) → **Amplify** → Create new app → **GitHub** → authorize →
   repository `seeubh5798/creator-impact`, branch **`main`** → ✓ *My app is a monorepo* →
   root directory `frontend` → Next. App name `proofluence-web`. Amplify reads `amplify.yml`.
2. Advanced settings → **Environment variables** (these are the **dev** values):

   | Variable | Value |
   |---|---|
   | `BACKEND_URL` | `https://api-dev.proofluence.com` |
   | `NEXT_PUBLIC_APP_NAME` | `Proofluence` |
   | `NEXT_PUBLIC_SITE_URL` | `https://dev.proofluence.com` |
   | `NEXT_PUBLIC_CONTACT_EMAIL` | `hello@proofluence.com` (or your Gmail for now) |
   | `AMPLIFY_MONOREPO_APP_ROOT` | `frontend` |

   Save and deploy (~5 min). You get `https://main.xxxx.amplifyapp.com`.
3. **Add the prod branch**: app → Hosting → **Branches** → Connect branch → `prod`. Then
   Hosting → **Environment variables** → Manage variables → for `BACKEND_URL` and
   `NEXT_PUBLIC_SITE_URL` click **Add variable override** → branch `prod` →
   `https://api.proofluence.com` and `https://proofluence.com`. Redeploy `prod`.
4. **Domains**: Hosting → **Custom domains** → Add domain → `proofluence.com` → Configure:
   subdomain *(root)* → branch `prod`, `www` → `prod`, `dev` → `main`. Amplify shows DNS
   records. In GoDaddy DNS add each one exactly as shown:
   - the **CNAME** for SSL verification (`_abc123…` → `_xyz….acm-validations.aws.`)
   - **CNAME `www`** → `xxxx.cloudfront.net`
   - **CNAME `dev`** → `xxxx.cloudfront.net`
   - root `@`: GoDaddy can't CNAME the root. Use GoDaddy **Forwarding**
     (Domain → Forwarding → `https://www.proofluence.com`, permanent 301), and in Amplify
     set `www` as the primary. Visitors to proofluence.com land on www.proofluence.com.
     (Alternative later: move DNS to Route 53, which supports root aliases.)
   Wait until Amplify shows *Available* (5–45 min). SSL is automatic.
   If you use `www` as primary, set prod `NEXT_PUBLIC_SITE_URL` and prod `FRONTEND_URL`
   (server `.env`) to `https://www.proofluence.com` so cookies and OAuth redirects match.
5. Open `https://dev.proofluence.com` → Try the demo account → tag a post → report. Done.

## 10. Meta apps (when you're ready for real Instagram logins)

Two apps so dev experiments never touch the reviewed prod app. developers.facebook.com →
Create app → Other → Business. Add product **Instagram → API setup with Instagram login**.

| Setting | Proofluence Dev | Proofluence |
|---|---|---|
| OAuth redirect URI | `https://dev.proofluence.com/api/auth/instagram/callback` and `http://localhost:3000/api/auth/instagram/callback` | `https://www.proofluence.com/api/auth/instagram/callback` (match your primary domain) |
| Deauthorize callback | `https://dev.proofluence.com/api/meta/deauthorize` | `https://www.proofluence.com/api/meta/deauthorize` |
| Data deletion URL | `https://dev.proofluence.com/api/meta/data-deletion` | `https://www.proofluence.com/api/meta/data-deletion` |
| Privacy policy URL | `https://dev.proofluence.com/privacy` | `https://www.proofluence.com/privacy` |

Put each app's **Instagram app ID / secret** into that server's `.env`, then on the box:
`cd /opt/proofluence && docker compose up -d` (restarts with the new values).
Pilot creators: App roles → Instagram testers (details in SETUP.md §3).

## 11. Razorpay

- **dev**: Test mode keys (`rzp_test_…`), 4 plans created in Test mode, webhook
  `https://api-dev.proofluence.com/billing/webhook`.
- **prod**: Live mode keys (`rzp_live_…`, after KYC), the same 4 plans re-created in Live
  mode, webhook `https://api.proofluence.com/billing/webhook`.
Plans, amounts and webhook events: SETUP.md §5. After editing `.env`: `docker compose up -d`.

## 12. Daily workflow

```bash
git checkout main && git pull
# ...code, commit...
git push                                   # -> dev deploys itself (backend + site)
# test on dev.proofluence.com
git checkout prod && git merge --ff-only main && git push   # -> prod deploys itself
git checkout main
```
Changing a server secret: `ssh proofluence-prod`, `nano /opt/proofluence/.env`,
`cd /opt/proofluence && docker compose up -d`. Changing a site variable: Amplify →
Environment variables → Redeploy the branch.

## 13. Local development `.env` files (on your Mac, never committed)

| File | Copy from | Used by |
|---|---|---|
| `.env` (repo root) | `.env.docker.example` | `docker compose up` (optional keys only) |
| `backend/.env` | `backend/.env.example` | running the API/worker without Docker |
| `frontend/.env.local` | `frontend/.env.example` | `npm run dev` |

For local work use `DEMO_MODE=true`, Razorpay **test** keys, and the local database
(`DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:54329/impact` with
`docker compose up db`). Don't point your laptop at the prod database.

## 14. When something breaks

| Symptom | Fix |
|---|---|
| Deploy job: "EC2_HOST / EC2_SSH_KEY are not set" | Step 7: secrets must be in the *Environment* (`dev`/`production`), not repo secrets |
| Deploy job: `Permission denied (publickey)` | `EC2_SSH_KEY` must be the whole `.pem` incl. BEGIN/END lines; `EC2_USER=ubuntu` |
| Deploy job: `.env is missing` / `API_DOMAIN missing` | Step 6 on that box |
| `curl https://api-dev…/health` hangs | Security group ports 80/443; DNS A record points at the Elastic IP (`dig +short`) |
| Certificate error on the API | DNS wasn't ready when Caddy started: `ssh` in, `cd /opt/proofluence && docker compose restart caddy` |
| API container restarts | `docker compose logs --tail=100 api`. Usually a wrong `DATABASE_URL` (prefix must be `postgresql+psycopg://`) or dev secrets left in (`Set these env vars for production`) |
| Site loads, "Try the demo" does nothing | Amplify `BACKEND_URL` wrong for that branch; fix and **Redeploy** (it's read at build time) |
| Report stuck on "Analysing" | Worker: `docker compose logs --tail=100 worker` |
| Amplify build fails on Next.js version | Amplify lags Next releases. Fallback: Vercel, same env vars, root `frontend` (SETUP.md §6) |

## 15. Monthly cost (pilot)

| Item | dev | prod |
|---|---|---|
| EC2 | t3.micro ≈ $8 (free-tier credits on new accounts) | t3.small ≈ $17 |
| Elastic IP + 20 GB disk | ≈ $5 | ≈ $5 |
| Amplify | ≈ $0–2 | ≈ $1–5 |
| Supabase | free | free (Pro $25 once paying users) |
| Domain | ≈ ₹1,000/yr | — |
| **Total** | **≈ $13** | **≈ $25** |

Tight on money? Skip the dev EC2 box at first (use local Docker as dev) and create it
when a second person joins or before the first public launch. Everything above still
applies to prod.
