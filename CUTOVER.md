# Production cutover — remaining account steps

Neon restore is done (row counts match the old DB). Repo config for Render +
Cloudflare Pages + GitHub Actions is in place. Finish these account steps once,
then the stack is live.

## A. Point local/API env at Neon (pooled)

Your `NEON_URL` may be the direct host. For Render + GitHub Actions prefer pooled:

```text
postgresql://neondb_owner:PASSWORD@ep-misty-hill-awge61ox-pooler.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require
```

In `peekorobo-api/.env`, set `DB_URL` to that pooled URL when you are ready for the
new API to use Neon (keep the old `DB_URL` backed up until Heroku is gone).

## B. Deploy API on Render (~5 min)

1. Open https://dashboard.render.com → New → Blueprint
2. Connect `rhettadam/peekorobo`, root path `peekorobo-api` (or New Web Service →
   Docker, Dockerfile in `peekorobo-api/`)
3. Set env:
   - `DB_URL` = Neon **pooled** URL above
   - `JWT_SECRET` = auto or `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - leave other values from `peekorobo-api/render.yaml`
4. Deploy. Copy the service URL, e.g. `https://peekorobo-api.onrender.com`
5. Check `/` and `/docs`

Blueprint file: `peekorobo-api/render.yaml` (free plan).

## C. Cloudflare Pages project

1. https://dash.cloudflare.com → Workers & Pages → Create → Pages → Direct Upload
   (or empty project named **`peekorobo`**)
2. Create an API Token: Templates → **Edit Cloudflare Workers** (includes Pages)
   with Account + Pages edit permissions
3. Note Account ID (overview sidebar)

## D. GitHub Actions secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|--------|
| `DATABASE_URL` | Neon pooled URL (same as Render `DB_URL`) |
| `TBA_API_KEYS` | same as local |
| `CLOUDFLARE_API_TOKEN` | from C |
| `CLOUDFLARE_ACCOUNT_ID` | from C |
| `VITE_API_BASE_URL` | Render URL from B (no trailing slash) |

Optional: `CLOUDFLARE_PAGES_PROJECT=peekorobo` (workflows default to `peekorobo`).

Push/commit the workflow files, then: Actions → **Data pipeline** → Run workflow →
mode **full**. That regenerates ACE + deploys SPA with `/data` and `/assets`.

Or run **Deploy Pages** for a frontend-only deploy.

## E. DNS (after smoke test on `*.onrender.com` / `*.pages.dev`)

1. Keep Heroku Dash up
2. `api.peekorobo.com` → Render custom domain
3. `peekorobo.com` / `www` → Cloudflare Pages custom domain
4. Update `VITE_API_BASE_URL` to `https://api.peekorobo.com`, redeploy Pages
5. Set Render `CORS_ORIGINS=https://peekorobo.com`
6. Turn off Heroku Scheduler; scale Heroku to 0

## Smoke

Search, teams, team page, events, event tabs, match, compare, insights, map, login.
