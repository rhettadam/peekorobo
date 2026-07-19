# Peekorobo Deployment & Cutover

Minimal stack (off Heroku, low cost):

```
The Blue Alliance
      |
      v
GitHub Actions (ACE pipeline + rankings/awards + static regen)
      |                                   \
      v                                    v
Neon Postgres                      Cloudflare Pages
      |                             (SPA + /data + /assets)
      v
Render (FastAPI)
      |
      v
Users  <---------------------------- Cloudflare Pages
```

Target spend: **$0–7/mo** (Neon free, Pages free, Actions free, Render free or Starter).

## 1. Database: Neon

1. Create a Neon project (Postgres **16**, Neon Auth **off**).
2. Restore from the old Heroku/RDS database (`pg_dump -Fc` → `pg_restore --no-owner --no-acl --exclude-schema=_heroku`).
3. Verify row counts for `teams`, `team_epas`, `events`, `event_matches`,
   `event_rankings`, `event_awards`, `event_teams`, `users`.
4. Use the **pooled** connection string for the API and GitHub Actions
   (host contains `-pooler`). Direct host is fine for one-off `pg_restore`.

## 2. API: Render

Deploy [`peekorobo-api/`](peekorobo-api/) with [`render.yaml`](peekorobo-api/render.yaml) or the Dockerfile.

Required env:
- `DB_URL` — Neon **pooled** URL (`?sslmode=require`)
- `JWT_SECRET` — long random string (blueprint can auto-generate)
- `PUBLIC_READ=true`
- `CORS_ORIGINS=*` initially; tighten to the Pages origin after DNS

Confirm `https://<service>.onrender.com/` and `/docs` load.

## 3. SPA + static files: Cloudflare Pages

One Pages project hosts:
- the React build (`dist/`)
- `/data/teams.json`, `/data/events.json`, `/data/leaderboards/`, filter JSON, geojson
- `/assets/` (logos, avatars, banners)

The **full** job in [`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml) rebuilds the SPA, copies those files into `dist/`, and deploys with Wrangler.

Build-time secrets/vars used by Actions:
- `VITE_API_BASE_URL` — Render URL (or `https://api.peekorobo.com` after DNS)
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`

SPA env (also set in Pages if you use git-connected builds):
- `VITE_SEARCH_BASE_URL=/data`
- `VITE_ASSETS_BASE_URL=/assets`
- `VITE_CURRENT_YEAR=2026`

## 4. Pipeline: GitHub Actions

Secrets:
- `DATABASE_URL` — Neon pooled URL (same DB as API)
- `TBA_API_KEYS`
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`
- `VITE_API_BASE_URL`

Cadence:
- In-season: live every 30 min (`run.py --active-only` + rankings/awards); full every 6h
- Off-season: full daily

Trigger once: Actions → Data pipeline → Run workflow → mode `full`.

## 5. DNS cutover

1. Keep Heroku Dash running during overlap.
2. `api.peekorobo.com` → Render; `peekorobo.com` / `www` → Cloudflare Pages.
3. Rebuild/redeploy SPA if the API URL changed.
4. Set API `CORS_ORIGINS` to `https://peekorobo.com`.
5. After smoke tests: disable Heroku Scheduler, scale Heroku to 0 / delete.

## 6. Smoke checklist

- Search, `/teams`, `/team/:n/:year`, `/events`, `/event/:key`, `/match/...`, `/compare`, `/insights`, `/map`
- Login/profile if shipping auth day one
- Pipeline green; ACE rows updating on Neon
