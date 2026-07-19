![logo](assets/logo.png)

# Peekorobo

FRC scouting and analysis for teams and events — ACE ratings, rankings, matches, map, and more.

## Stack

| Piece | Location |
|-------|----------|
| React SPA | [`frontend/`](frontend/) (Vite + Mantine) |
| FastAPI | [`peekorobo-api/`](peekorobo-api/) |
| ACE + TBA pipeline | [`data/`](data/) (GitHub Actions) |
| Postgres | Neon |
| Hosting | Render (API) + Cloudflare Pages (SPA + static data/assets) |

See [`DEPLOYMENT.md`](DEPLOYMENT.md) / [`CUTOVER.md`](CUTOVER.md) for cutover steps.

## Local development

**API**

```bash
cd peekorobo-api
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # set DB_URL to Neon pooled URL
uvicorn main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm ci
npm run dev
```

Copy `data/teams.json` and `data/events.json` into `frontend/public/data/` for local search (or run the generators against your DB).

**Pipeline (optional)**

```bash
pip install -r requirements.txt
set DATABASE_URL=...   # or DB_URL
set TBA_API_KEYS=...
python data/run.py 2026 --active-only
```

## License

See [LICENSE](LICENSE).
