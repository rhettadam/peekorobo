# Production cutover — status

## Done

- [x] Surrogate team-key fix (`frc498E`, etc.)
- [x] Neon Postgres restored (row counts match old DB)
- [x] GitHub Actions secrets: `DATABASE_URL` (Neon pooler), `TBA_API_KEYS`
- [x] Neon pooler connection fix (`sslmode=require`, no startup `statement_timeout`)
- [x] Full pipeline green on Neon:  
  https://github.com/rhettadam/peekorobo/actions/runs/29703848131  
  (ACE + rankings/awards + `teams.json`/`events.json` artifact)
- [x] Workflows: `.github/workflows/pipeline.yml`, `pages.yml`
- [x] React SPA pushed to `main`
- [x] Render blueprint: `peekorobo-api/render.yaml` (free plan + `JWT_SECRET`)

## Your turn (account clicks — ~15 min)

### 1. Render API

Browser is on the Render login screen. Sign in (GitHub is easiest).

Then:

1. **New** → **Web Service**
2. Connect repo `rhettadam/peekorobo`
3. Root directory: `peekorobo-api`
4. Runtime: **Docker**
5. Instance: **Free**
6. Env vars:
   - `DB_URL` = Neon **pooled** URL  
     `postgresql://neondb_owner:PASSWORD@ep-misty-hill-awge61ox-pooler.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require`
   - `JWT_SECRET` = generate with  
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `PUBLIC_READ=true`
   - `CORS_ORIGINS=*`
7. Deploy. Copy the URL (e.g. `https://peekorobo-api.onrender.com`)
8. Open `/` and `/docs` to confirm

Then tell me the Render URL (or set it yourself):

```bash
gh secret set VITE_API_BASE_URL -b "https://YOUR-SERVICE.onrender.com"
```

### 2. Cloudflare Pages + token

1. https://dash.cloudflare.com → **Workers & Pages** → Create → Pages → create project named **`peekorobo`** (Direct Upload is fine)
2. **My Profile** → **API Tokens** → Create Token → use **Edit Cloudflare Workers** template (includes Pages)
3. Copy **Account ID** from the dashboard sidebar
4. Set secrets:

```bash
gh secret set CLOUDFLARE_API_TOKEN
gh secret set CLOUDFLARE_ACCOUNT_ID
```

5. Re-run: Actions → **Data pipeline** → mode `full`  
   (or **Deploy Pages**) — this builds the SPA and uploads `/data` + `/assets`

### 3. DNS (after smoke on `*.pages.dev` / `*.onrender.com`)

1. Keep Heroku Dash running
2. `api.peekorobo.com` → Render custom domain
3. `peekorobo.com` / `www` → Cloudflare Pages
4. Update `VITE_API_BASE_URL` to `https://api.peekorobo.com`, redeploy Pages
5. Set Render `CORS_ORIGINS=https://peekorobo.com`
6. Disable Heroku Scheduler; scale Heroku to 0

## Smoke

Search, teams, team/event/match pages, compare, insights, map, login.
