# Static data (local dev)

`VITE_SEARCH_BASE_URL` (default `/data`) serves static JSON and GeoJSON used by
the SPA for leaderboard filter options, per-year leaderboard snapshots, and map
district boundaries.

The navbar search index is loaded from the API (`GET /search/index`) instead of
static files.

For local development, leaderboard snapshots and filter JSON can live here when
present. In production they are copied into `dist/data/` during deploy.
