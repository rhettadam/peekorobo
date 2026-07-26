#!/usr/bin/env python3
"""Bootstrap a local Postgres DB for ACE model experiments.

Creates database ``peekorobo_local`` (or --dbname), copies schema (+ optional
reference data) from a source URL (usually Neon), and never writes ACE results
back to the source.

Usage (from data/):

    # 1. Put local URL in data/.env.local (see .env.local.example)
    # 2. Schema-only clone from Neon (read-only on source):
    python setup_local_db.py --source-url "$env:NEON_URL"

    # Optional: also copy teams/events/districts/event_teams for year 2026
    python setup_local_db.py --source-url "$env:NEON_URL" --seed-year 2026
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _python() -> Path:
    for p in (
        ROOT.parent / "peekorobo-api" / ".venv" / "Scripts" / "python.exe",
        ROOT.parent / "peekorobo-api" / ".venv" / "bin" / "python",
    ):
        if p.exists():
            return p
    return Path(sys.executable)


def _find_tool(name: str) -> str | None:
    import shutil

    found = shutil.which(name)
    if found:
        return found
    for base in (
        Path(r"C:\Program Files\PostgreSQL\17\bin"),
        Path(r"C:\Program Files\PostgreSQL\16\bin"),
        Path(r"C:\Program Files\PostgreSQL\15\bin"),
    ):
        cand = base / f"{name}.exe"
        if cand.exists():
            return str(cand)
    return None


def _parse_url(url: str) -> dict:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    u = urlparse(url)
    db = (u.path or "/").lstrip("/").split("?", 1)[0]
    return {
        "url": url,
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "dbname": db,
    }


def _admin_url(local: dict, admin_db: str = "postgres") -> str:
    # postgresql://user:pass@host:port/postgres
    u = urlparse(local["url"])
    return urlunparse((u.scheme, u.netloc, "/" + admin_db, "", "", ""))


def _run(cmd: list[str], env: dict | None = None) -> None:
    print("+", " ".join(cmd[:4]), "...")
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    _load_env_file(ROOT / ".env.local")
    _load_env_file(ROOT.parent / "peekorobo-api" / ".env")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--local-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("LOCAL_DATABASE_URL"),
        help="Target local DATABASE_URL (default: from data/.env.local)",
    )
    ap.add_argument(
        "--source-url",
        default=os.environ.get("SOURCE_DATABASE_URL")
        or os.environ.get("NEON_URL")
        or os.environ.get("DB_URL"),
        help="Read-only source (Neon) for schema/seed dump",
    )
    ap.add_argument("--dbname", default="peekorobo_local")
    ap.add_argument(
        "--seed-year",
        type=int,
        default=None,
        help="If set, copy teams/events/districts/event_teams (+ event_matches for that year)",
    )
    ap.add_argument("--skip-schema", action="store_true")
    args = ap.parse_args()

    if not args.local_url:
        raise SystemExit(
            "Pass --local-url or set DATABASE_URL in data/.env.local "
            "(see data/.env.local.example)."
        )

    local = _parse_url(args.local_url)
    if local["host"] not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(
            f"Refusing setup: local URL host is {local['host']!r}, expected localhost. "
            "Do not point --local-url at Neon."
        )

    # Force dbname if URL still says postgres
    if local["dbname"] in ("", "postgres"):
        local["dbname"] = args.dbname
        u = urlparse(local["url"])
        local["url"] = urlunparse((u.scheme, u.netloc, "/" + args.dbname, "", "", ""))

    psql = _find_tool("psql")
    pg_dump = _find_tool("pg_dump")
    if not psql or not pg_dump:
        raise SystemExit("Need psql and pg_dump on PATH (PostgreSQL bin directory).")

    env = os.environ.copy()
    env["PGPASSWORD"] = local["password"]

    print(f"Creating database {local['dbname']!r} on {local['host']}...")
    # CREATE DATABASE cannot run inside a transaction; ignore "already exists"
    create_sql = f"SELECT 1 FROM pg_database WHERE datname = '{local['dbname']}'"
    check = subprocess.run(
        [
            psql,
            "-h",
            local["host"],
            "-p",
            local["port"],
            "-U",
            local["user"],
            "-d",
            "postgres",
            "-tAc",
            create_sql,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        print(check.stderr)
        raise SystemExit("Could not connect to local Postgres (check password in .env.local).")
    if check.stdout.strip() != "1":
        subprocess.run(
            [
                psql,
                "-h",
                local["host"],
                "-p",
                local["port"],
                "-U",
                local["user"],
                "-d",
                "postgres",
                "-c",
                f'CREATE DATABASE "{local["dbname"]}"',
            ],
            env=env,
            check=True,
        )
        print("created.")
    else:
        print("already exists.")

    if not args.skip_schema:
        if not args.source_url:
            raise SystemExit("Need --source-url (Neon) to copy schema, or pass --skip-schema.")
        src = _parse_url(args.source_url)
        src_env = os.environ.copy()
        src_env["PGPASSWORD"] = src["password"]
        schema_path = ROOT / "tmp_eval" / "local_schema.sql"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Dumping schema from {src['host']} → {schema_path}")
        _run(
            [
                pg_dump,
                "-h",
                src["host"],
                "-p",
                src["port"],
                "-U",
                src["user"],
                "-d",
                src["dbname"],
                "--schema-only",
                "--no-owner",
                "--no-privileges",
                "-f",
                str(schema_path),
            ],
            env=src_env,
        )
        print("Applying schema to local...")
        _run(
            [
                psql,
                "-h",
                local["host"],
                "-p",
                local["port"],
                "-U",
                local["user"],
                "-d",
                local["dbname"],
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(schema_path),
            ],
            env=env,
        )

    if args.seed_year is not None:
        if not args.source_url:
            raise SystemExit("--seed-year requires --source-url")
        src = _parse_url(args.source_url)
        src_env = os.environ.copy()
        src_env["PGPASSWORD"] = src["password"]
        year = args.seed_year
        # Copy reference tables needed for ranks + event metadata. Matches for the
        # year help active-only paths; full ACE recompute still refetches TBA.
        tables = [
            "districts",
            "teams",
            "events",
            "event_teams",
        ]
        data_path = ROOT / "tmp_eval" / f"local_seed_{year}.sql"
        print(f"Dumping seed tables for {year}...")
        dump_cmd = [
            pg_dump,
            "-h",
            src["host"],
            "-p",
            src["port"],
            "-U",
            src["user"],
            "-d",
            src["dbname"],
            "--data-only",
            "--no-owner",
            "--no-privileges",
            "-f",
            str(data_path),
        ]
        for t in tables:
            dump_cmd.extend(["-t", t])
        # event_matches / event_rankings filtered via COPY in a follow-up query is
        # heavy; skip for now — run.py pulls matches from TBA.
        _run(dump_cmd, env=src_env)
        print("Loading seed into local (may take a minute)...")
        _run(
            [
                psql,
                "-h",
                local["host"],
                "-p",
                local["port"],
                "-U",
                local["user"],
                "-d",
                local["dbname"],
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(data_path),
            ],
            env=env,
        )

    print("\nLocal DB ready.")
    print(f"  DATABASE_URL={local['url']}")
    print("Put that in data/.env.local, then:")
    print("  python recompute_years.py --start 2026 --end 2026")
    print("Prod Neon writes stay blocked unless ACE_ALLOW_PROD_WRITE=1.")


if __name__ == "__main__":
    main()
