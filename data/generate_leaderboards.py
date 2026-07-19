#!/usr/bin/env python3
"""
Generate per-year leaderboard JSON snapshots for the React SPA.

Each file (data/leaderboards/<year>.json) contains every team's season EPA/ACE
summary for that year. These are large, rarely-changing snapshots that the SPA
loads directly from a CDN/static host instead of paginating the API - this is
the main cost/latency win for the leaderboard and insights pages.

Usage:
    python data/generate_leaderboards.py            # current + a few recent years
    python data/generate_leaderboards.py 2025       # a single year
    python data/generate_leaderboards.py all        # every year present in team_epas
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from datagather import DatabaseConnection

load_dotenv()

OUTPUT_DIR = os.path.join("data", "leaderboards")

# Columns copied verbatim from team_epas into each leaderboard row.
COLUMNS = [
    "team_number",
    "ace",
    "raw",
    "confidence",
    "auto_raw",
    "teleop_raw",
    "endgame_raw",
    "wins",
    "losses",
    "ties",
    "rank_global",
    "rank_country",
    "rank_state",
    "rank_district",
    "count_global",
    "count_country",
    "count_state",
    "count_district",
]

FLOAT_COLS = {"ace", "raw", "confidence", "auto_raw", "teleop_raw", "endgame_raw"}
INT_COLS = {
    "team_number",
    "wins",
    "losses",
    "ties",
    "rank_global",
    "rank_country",
    "rank_state",
    "rank_district",
    "count_global",
    "count_country",
    "count_state",
    "count_district",
}


def _coerce(col, value):
    if value is None:
        return None
    if col in FLOAT_COLS:
        return round(float(value), 2)
    if col in INT_COLS:
        return int(value)
    return value


def get_years(cur, requested):
    if requested == "all":
        cur.execute("SELECT DISTINCT year FROM team_epas ORDER BY year")
        return [row[0] for row in cur.fetchall()]
    if requested is not None:
        return [int(requested)]
    # Default: current year and the previous four seasons.
    current_year = int(os.getenv("CURRENT_YEAR", datetime.now(timezone.utc).year))
    return list(range(current_year, current_year - 5, -1))


def generate_year(cur, year):
    col_sql = ", ".join(COLUMNS)
    cur.execute(
        f"SELECT {col_sql} FROM team_epas WHERE year = %s ORDER BY ace DESC NULLS LAST",
        (year,),
    )
    rows = []
    for record in cur.fetchall():
        row = {col: _coerce(col, val) for col, val in zip(COLUMNS, record)}
        rows.append(row)

    payload = {
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "teams": rows,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{year}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"Wrote {len(rows):>5} teams -> {out_path}")


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else None
    with DatabaseConnection() as conn:
        cur = conn.cursor()
        years = get_years(cur, requested)
        for year in years:
            generate_year(cur, year)


if __name__ == "__main__":
    main()
