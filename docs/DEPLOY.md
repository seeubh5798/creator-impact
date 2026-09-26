# Production on AWS: EC2 (backend) + Amplify (frontend) + Supabase (database)

```
GoDaddy DNS
  yourdomain.com      ──CNAME──▶  AWS Amplify (Next.js, auto-deploys `prod`)
  api.yourdomain.com  ──A─────▶  EC2 Elastic IP ──▶ Caddy (HTTPS) ──▶ api + worker containers
                                                              │
                                                              ▼
                                                       Supabase Postgres (Mumbai)
```

Monthly cost at pilot scale: EC2 t3.small ≈ $17 (or t4g.small ≈ $13), Amplify ≈ $0–5,
Supabase free, Razorpay 2% of revenue. Use the **ap-south-1 (Mumbai)** region everywhere.

## 1. GoDaddy DNS

You'll add records here in steps 2 and 4. GoDaddy → My Products → your domain → **DNS**.
Delete the placeholder "Parked" A record and the `www` CNAME to `@` that GoDaddy pre-creates.

## 2. EC2: backend + worker

1. AWS console → EC2 → **Launch instance**
   - Name: `creator-impact-api`
   - AMI: **Ubuntu Server 24.04 LTS** (64-bit x86)
   - Type: **t3.small** (2 GB RAM). t3.micro works for a pilot but will swap during big analyses.
   - Key pair: create one, download the `.pem`, keep it safe (it becomes a GitHub secret).
   - Network: allow **SSH (22)**, **HTTP (80)**, **HTTPS (443)** from anywhere. Nothing else.
   - Storage: 20 GB gp3.
2. EC2 → **Elastic IPs** → Allocate → Associate with the instance. (Without this the IP
   changes on every reboot and your DNS breaks.)
3. GoDaddy DNS → add record: **Type A, Name `api`, Value `<Elastic IP>`, TTL 600**.
4. SSH in and bootstrap:
   ```bash
   ssh -i creator-impact.pem ubuntu@<Elastic IP>
   curl -fsSL https://raw.githubusercontent.com/seeubh5798/creator-impact/prod/deploy/ec2-setup.sh | bash
   nano /opt/creator-impact/.env        # fill EVERY value; see deploy/env.prod.example
   exit                                 # log out so the docker group applies
   ```
   Generate the three secrets on your laptop with `python backend/scripts/gen_keys.py`.
   `API_DOMAIN=api.yourdomain.com`, `FRONTEND_URL=https://yourdomain.com`, `ENV=production`.
5. Nothing is running yet: the first deploy from GitHub (step 3) starts it.

The server runs three containers from `deploy/docker-compose.prod.yml`: `api`, `worker`
and `caddy`. Caddy obtains the HTTPS certificate for `api.yourdomain.com` automatically
on first start (needs the A record to already point at the box).

Useful commands on the box: `cd /opt/creator-impact && docker compose ps`,
`docker compose logs -f worker`, `docker compose restart api`.

## 3. GitHub secrets and the first deploy

Repo → Settings → Secrets and variables → Actions → **New repository secret**:

| Secret | Value |
|---|---|
| `EC2_HOST` | the Elastic IP |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | the full contents of the `.pem` file |

Optional but recommended: Settings → Environments → create `production` → add yourself as
a **required reviewer**. Then every backend deploy waits for your click in the Actions tab.

First deploy: Actions → **Deploy backend (prod)** → **Run workflow** (branch `prod`).
Watch the three jobs: test → build → deploy. The deploy job runs the migrations against
Supabase, starts the containers and health-checks the API. Then:

```
curl https://api.yourdomain.com/health
{"ok":true,"demo_mode":true,"llm":false,"billing":true}
```

If it fails on "certificate", the DNS A record hasn't propagated yet: wait 10 minutes and
re-run the workflow.

## 4. Amplify: frontend

1. AWS console → **Amplify** → Create new app → **GitHub** → authorise → pick
   `seeubh5798/creator-impact`, branch **`prod`**.
2. Amplify detects the monorepo. Confirm: **Monorepo → app root `frontend`**, framework
   Next.js SSR. The build settings come from `amplify.yml` in the repo root.
3. **Environment variables** (Advanced settings, before the first build):

   | Variable | Value |
   |---|---|
   | `BACKEND_URL` | `https://api.yourdomain.com` |
   | `NEXT_PUBLIC_APP_NAME` | your product name |
   | `NEXT_PUBLIC_SITE_URL` | `https://yourdomain.com` |
   | `NEXT_PUBLIC_CONTACT_EMAIL` | your support email |

4. Save and deploy. First build ≈ 5 minutes. You get a `https://prod.xxxx.amplifyapp.com` URL.
5. **Custom domain**: Amplify → Hosting → Custom domains → Add domain → `yourdomain.com`.
   Amplify shows a CNAME for verification and CNAMEs for `yourdomain.com` and `www`.
   Add them in GoDaddy DNS exactly as shown (for the root domain GoDaddy accepts Amplify's
   ANAME/ALIAS-style record as a CNAME on `@`; if it refuses, use "Forwarding" from `@` to
   `www` and point `www` at Amplify). Verification takes 5–30 minutes; the SSL certificate
   is issued automatically.
6. Any push to `prod` that touches `frontend/` now redeploys automatically. Amplify →
   the branch → build history shows each one.

The browser only ever talks to `yourdomain.com`; Next.js proxies `/api/*` to the EC2 API
server-side, so cookies are first-party and the API domain never appears in the client.

## 5. Releasing

`main` is where work lands (CI runs tests on every push and PR). `prod` is what runs.

```bash
git checkout prod
git merge --ff-only main        # or open a PR main -> prod on GitHub and merge it
git push
```

- Backend workflow (`.github/workflows/deploy-backend.yml`) triggers when `backend/`,
  `supabase/` or `deploy/` changed: tests → image to `ghcr.io/seeubh5798/creator-impact-backend`
  → SSH to EC2 → `python -m scripts.migrate` → `docker compose up -d` → health check.
  A failed migration or health check stops the rollout; the previous containers keep serving.
- Amplify triggers when anything in `frontend/` changed.
- Database migrations: add a new `supabase/migrations/<timestamp>_<name>.sql`, ship it on
  `prod` **before or together with** the code that needs it. The deploy job applies it
  once; `schema_migrations` in Supabase records what ran.

Rollback: Actions → re-run the last green "Deploy backend" run (it redeploys that commit's
image), or `git revert` on `prod` and push. Amplify → branch → "Redeploy this version" on
any earlier build.

## 6. Monitoring (minimum)

- AWS → CloudWatch → EC2 → create an alarm on `StatusCheckFailed` and `CPUUtilization > 90%
  for 15 min`, action: email you (SNS).
- UptimeRobot (free) → HTTPS monitor on `https://api.yourdomain.com/health` and on the site.
- Supabase → Reports shows DB size and connections; the free tier pauses projects idle for
  a week, so keep the worker's daily jobs running (they are, by default).
