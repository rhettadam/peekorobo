#!/usr/bin/env python3
"""Chronological multi-year ACE recompute with locked knobs + smoke checks.

Usage (from data/):

    python recompute_years.py --start 2015 --end 2026
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "tmp_eval"  # gitignored scratch for per-year logs


def _python() -> Path:
    candidates = [
        ROOT.parent / "peekorobo-api" / ".venv" / "Scripts" / "python.exe",
        ROOT.parent / "peekorobo-api" / ".venv" / "bin" / "python",
        ROOT.parent / ".venv" / "Scripts" / "python.exe",
        ROOT.parent / ".venv" / "bin" / "python",
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path(sys.executable)


def _clear_locks() -> None:
    import psycopg2

    url = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL") or os.environ.get("NEON_URL")
    if not url:
        print("No DB URL; skip lock clear")
        return
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT pid FROM pg_locks WHERE locktype='advisory' AND granted")
    for (pid,) in cur.fetchall():
        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        print(f"terminated lock holder {pid}")
    cur.close()
    conn.close()


def _smoke(year: int) -> None:
    import psycopg2

    url = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL") or os.environ.get("NEON_URL")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT team_number, ROUND(ace::numeric,1), ROUND(raw::numeric,1), wins, losses
        FROM team_epas WHERE year=%s ORDER BY ace DESC NULLS LAST LIMIT 5
        """,
        (year,),
    )
    rows = cur.fetchall()
    cur.execute(
        """
        SELECT COUNT(*), ROUND(AVG(ace)::numeric,1), ROUND(MAX(ace)::numeric,1)
        FROM team_epas WHERE year=%s AND COALESCE(raw,0)>0
        """,
        (year,),
    )
    summary = cur.fetchone()
    cur.close()
    conn.close()
    print(f"[smoke {year}] n/avg/max ace={summary}")
    print(f"[smoke {year}] top5={rows}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2026)
    args = ap.parse_args()

    # Locked ACE principles
    os.environ["RESTART_HEROKU"] = "0"
    os.environ["ACE_METHOD"] = "residual_shrink"
    os.environ["ACE_SHRINK"] = "0.05"
    os.environ["ACE_K_BASE"] = "0.4"
    os.environ["ACE_SPIKE_DAMP"] = "1.0"
    os.environ["ACE_CARRY_PRIOR"] = "1"
    os.environ["ACE_PRIOR_BLEND"] = "1.0"
    os.environ["ACE_WIN_PROB_SCALE"] = "0.04"
    os.environ["PYTHONUNBUFFERED"] = "1"

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    py = _python()
    years = list(range(args.start, args.end + 1))
    print(f"Recomputing years {years} with shrink=0.05 residual_shrink prior carry")
    print(f"Using python: {py}")

    for y in years:
        print("\n" + "=" * 60)
        print(f"YEAR {y}")
        print("=" * 60)
        _clear_locks()
        log_path = LOG_DIR / f"full_recompute_{y}.log"
        with open(log_path, "w", encoding="utf-8") as logf:
            proc = subprocess.run(
                [str(py), "-u", str(ROOT / "run.py"), str(y)],
                cwd=str(ROOT),
                env=os.environ.copy(),
                stdout=logf,
                stderr=subprocess.STDOUT,
            )
        if proc.returncode != 0:
            print(f"FAILED year {y} exit={proc.returncode}; see {log_path}")
            sys.exit(proc.returncode)
        # Tail summary lines
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "Team Update Summary" in line or "Teams updated" in line or "Script runtime" in line or "Precomputed event EPA" in line:
                print(line)
        _smoke(y)
        print(f"YEAR {y} complete -> {log_path}")

    print("\nAll years complete.")


if __name__ == "__main__":
    main()
