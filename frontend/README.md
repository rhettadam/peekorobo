# Peekorobo Frontend

Client-side React SPA for Peekorobo (FRC team & event scouting/analysis). Built
with Vite + React + TypeScript, Mantine (UI + charts), React Router, and
TanStack Query. It consumes the Peekorobo FastAPI backend and a small set of
static JSON served from `/data` (leaderboard snapshots, filter options).

## Stack

- **Vite + React + TypeScript** - fast, pure client-side rendering
- **Mantine** (`@mantine/core`, `@mantine/hooks`, `@mantine/charts`) - components + charts
- **React Router** - routing
- **TanStack Query** - server-state caching, de-duplication, background refetch
  (this is what replaces the old Dash "callback hell")

## Project structure

```
src/
  api/         typed fetch client, TanStack Query hooks, static search loader
  components/  app shell, navbar, footer, search bar, shared UI
  lib/         formatting + ACE color/percentile helpers (ported from utils.py)
  routes/      one file per page (Home, Team, Event, Match, TeamsLeaderboard,
               Events, Compare, Insights)
  types/       TypeScript types mirroring the backend Pydantic schemas
```

## Data flow

```
FastAPI  ─► CDN cache (~5 min TTL, search index ~1 hr) ─► React (TanStack Query cache) ─► UI
Static /data JSON (leaderboards, filters) ────────────────────────────────────────────────┘
```

Components declare what data they need via query hooks in `src/api/queries.ts`.
Each hook caches for ~5 minutes to match the backend/CDN freshness target. The
search index is fetched once per session from `GET /search/index`.

## Local development

1. Install dependencies:

```bash
npm install
```

2. Configure environment (copy and edit):

```bash
cp .env.example .env
```

3. Run the API somewhere reachable. Options:
   - Standalone on port 8000 from `../peekorobo-api`:

```bash
cd ../peekorobo-api
uvicorn main:app --reload --port 8000
```

   The Vite dev server proxies `/api/*` to `http://localhost:8000` (see
   `vite.config.ts`), so the default `VITE_API_BASE_URL=/api` works out of the box.

4. Start the dev server:

```bash
npm run dev
```

## Build

```bash
npm run build      # type-check + production build to dist/
npm run preview    # preview the production build locally
```

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Base URL of the FastAPI backend | `/api` |
| `VITE_SEARCH_BASE_URL` | Base URL for static `/data` JSON (leaderboards, filters) | `/data` |
| `VITE_CURRENT_YEAR` | Default FRC season | `2026` |

## Deployment

Deploy `dist/` to any static host (Cloudflare Pages, Vercel, Netlify). Set the
`VITE_*` env vars at build time to point at the deployed API and static data.
Because it is an SPA, configure the host to serve `index.html` for unknown
routes (SPA fallback).
