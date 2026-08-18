#!/usr/bin/env python3
"""Geocode FRC teams and events with Mapbox and write lat/lng to Postgres.

Reads city / state_prov / postal_code / country from the database (no TBA
calls). Teams are always rewritten. Events are only filled when lat/lng is missing.

Usage:
    python data/geo/geocode.py --teams
    python data/geo/geocode.py --events --year 2026
    python data/geo/geocode.py --dry-run --limit 20

Env:
    DB_URL or DATABASE_URL     Postgres connection string
    MAPBOX_ACCESS_TOKEN        Mapbox token (pk. or sk.)
    ACE_ALLOW_PROD_WRITE=1     Required when pointing at hosted Neon
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv
from tqdm import tqdm

_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_DATA_DIR)
for _path in (_DATA_DIR, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_DATA_DIR, ".env.local"), override=True)

from db_connection import get_pg_connection, return_pg_connection  # noqa: E402
from db_target import assert_safe_db_target, describe_db_target  # noqa: E402

MAPBOX_FORWARD_URL = "https://api.mapbox.com/search/geocode/v6/forward"
MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN") or os.getenv("MAPBOX_TOKEN") or ""

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapbox_geo_cache.json")
_permanent_ok: Optional[bool] = None

# TBA uses full country names; Mapbox structured `country` is a hard filter when
# given an ISO 3166-1 alpha-2 code.
COUNTRY_ISO = {
    "usa": "US",
    "united states": "US",
    "united states of america": "US",
    "canada": "CA",
    "mexico": "MX",
    "israel": "IL",
    "australia": "AU",
    "brazil": "BR",
    "china": "CN",
    "chinese taipei": "TW",
    "taiwan": "TW",
    "turkey": "TR",
    "türkiye": "TR",
    "united kingdom": "GB",
    "england": "GB",
    "netherlands": "NL",
    "india": "IN",
    "japan": "JP",
    "france": "FR",
    "germany": "DE",
    "singapore": "SG",
    "dominican republic": "DO",
    "czech republic": "CZ",
    "czechia": "CZ",
    "poland": "PL",
    "kazakhstan": "KZ",
    "south africa": "ZA",
    "new zealand": "NZ",
    "colombia": "CO",
    "chile": "CL",
    "argentina": "AR",
    "panama": "PA",
    "croatia": "HR",
    "greece": "GR",
    "switzerland": "CH",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "belgium": "BE",
    "spain": "ES",
    "italy": "IT",
    "portugal": "PT",
    "hungary": "HU",
    "romania": "RO",
    "ukraine": "UA",
    "philippines": "PH",
    "thailand": "TH",
    "vietnam": "VN",
    "malaysia": "MY",
    "indonesia": "ID",
    "south korea": "KR",
    "korea": "KR",
    "republic of korea": "KR",
    "united arab emirates": "AE",
    "qatar": "QA",
    "egypt": "EG",
    "morocco": "MA",
    "tunisia": "TN",
    "cyprus": "CY",
    "bosnia-herzegovina": "BA",
    "bosnia and herzegovina": "BA",
    "slovakia": "SK",
    "slovenia": "SI",
    "lithuania": "LT",
    "latvia": "LV",
    "estonia": "EE",
    "finland": "FI",
    "ireland": "IE",
    "austria": "AT",
    "puerto rico": "PR",
}

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def country_iso(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    raw = country.strip()
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    return COUNTRY_ISO.get(raw.lower())


def cache_key(city: Optional[str], state: Optional[str], postal: Optional[str], country: Optional[str]) -> str:
    return json.dumps(
        {
            "city": (city or "").strip().lower(),
            "state": (state or "").strip().lower(),
            "postal": (postal or "").strip().lower(),
            "country": (country or "").strip().lower(),
        },
        sort_keys=True,
    )


def load_cache() -> Dict[str, List[Optional[float]]]:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(cache: Dict[str, List[Optional[float]]]) -> None:
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_PATH)


def ensure_location_columns(conn) -> None:
    """Add postal_code if TBA ingest has not created it yet."""
    cur = conn.cursor()
    for table in ("teams", "events"):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS postal_code TEXT")
    cur.execute("ALTER TABLE event_teams DROP COLUMN IF EXISTS postal_code")
    conn.commit()
    cur.close()


def _parse_mapbox_coords(payload: Any) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(payload, dict):
        return None, None
    features = payload.get("features") or []
    if not features:
        return None, None
    feature = features[0]
    props = feature.get("properties") or {}
    coords = props.get("coordinates") or {}
    lat = coords.get("latitude")
    lng = coords.get("longitude")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    geometry = feature.get("geometry") or {}
    pair = geometry.get("coordinates")
    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
        return float(pair[1]), float(pair[0])
    return None, None


def _mapbox_get(params: Dict[str, Any], permanent: bool) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    global _permanent_ok
    if _permanent_ok is False:
        permanent = False

    query = dict(params)
    query["access_token"] = MAPBOX_ACCESS_TOKEN
    query["permanent"] = "true" if permanent else "false"
    query["autocomplete"] = "false"
    query["limit"] = 1
    query["language"] = "en"
    query.setdefault("types", "postcode,place,locality,region")

    last_error = None
    for attempt in range(4):
        try:
            r = requests.get(MAPBOX_FORWARD_URL, params=query, timeout=20)
            if r.status_code == 200:
                if permanent:
                    _permanent_ok = True
                lat, lng = _parse_mapbox_coords(r.json())
                return lat, lng, None
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                last_error = "rate limited"
                continue
            if r.status_code in (400, 404):
                return None, None, None
            if r.status_code in (401, 403, 422) and permanent:
                _permanent_ok = False
                print(
                    f"Mapbox permanent geocoding not available for this token "
                    f"(HTTP {r.status_code}); using temporary for stored coords."
                )
                return _mapbox_get(params, permanent=False)
            last_error = f"http {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_error = str(e)
        time.sleep(1 + attempt)
    return None, None, last_error


def geocode_location(
    city: Optional[str],
    state: Optional[str],
    postal: Optional[str],
    country: Optional[str],
    *,
    cache: Dict[str, List[Optional[float]]],
    permanent: bool,
    min_interval: float,
) -> Tuple[Optional[float], Optional[float]]:
    city, state, postal, country = (_clean(city), _clean(state), _clean(postal), _clean(country))
    if not any((city, state, postal, country)):
        return None, None

    key = cache_key(city, state, postal, country)
    if key in cache:
        pair = cache[key]
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            return pair[0], pair[1]

    iso = country_iso(country)
    structured: Dict[str, Any] = {}
    if city:
        structured["place"] = city
    if state:
        structured["region"] = state
    if postal:
        structured["postcode"] = postal
    if iso:
        structured["country"] = iso
    elif country:
        structured["country"] = country

    attempts: List[Dict[str, Any]] = []
    if structured:
        attempts.append(dict(structured))
        if postal and (city or state):
            no_zip = dict(structured)
            no_zip.pop("postcode", None)
            attempts.append(no_zip)
    query_parts = [p for p in (city, state, postal, country) if p]
    if query_parts:
        attempts.append({"q": ", ".join(query_parts)})
        if postal:
            attempts.append({"q": ", ".join(p for p in (city, state, country) if p)})

    lat = lng = None
    for params in attempts:
        time.sleep(min_interval)
        lat, lng, _err = _mapbox_get(params, permanent=permanent)
        if lat is not None and lng is not None:
            break

    cache[key] = [lat, lng]
    return lat, lng


def _table_has_column(conn, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    found = cur.fetchone() is not None
    cur.close()
    return found


def fetch_teams(conn, limit: Optional[int]) -> List[dict]:
    sql = """
        SELECT team_number, nickname, city, state_prov, country, postal_code, lat, lng
        FROM teams
        ORDER BY team_number
    """
    if limit:
        sql += " LIMIT %s"
        cur = conn.cursor()
        cur.execute(sql, (limit,))
    else:
        cur = conn.cursor()
        cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "team_number": r[0],
            "nickname": r[1],
            "city": r[2],
            "state_prov": r[3],
            "country": r[4],
            "postal_code": r[5],
            "lat": r[6],
            "lng": r[7],
        }
        for r in rows
    ]


def fetch_events(conn, year: Optional[int], limit: Optional[int]) -> List[dict]:
    clauses: List[str] = ["(lat IS NULL OR lng IS NULL)"]
    params: List[Any] = []
    if year is not None:
        clauses.append("LEFT(event_key, 4) = %s")
        params.append(str(year))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT event_key, name, city, state_prov, country, postal_code, lat, lng
        FROM events
        {where}
        ORDER BY event_key
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "event_key": r[0],
            "name": r[1],
            "city": r[2],
            "state_prov": r[3],
            "country": r[4],
            "postal_code": r[5],
            "lat": r[6],
            "lng": r[7],
        }
        for r in rows
    ]


def update_coords(conn, table: str, id_column: str, rows: Sequence[Tuple[Any, float, float]]) -> None:
    if not rows:
        return
    cur = conn.cursor()
    cur.executemany(
        f"UPDATE {table} SET lat = %s, lng = %s WHERE {id_column} = %s",
        [(lat, lng, key) for key, lat, lng in rows],
    )
    conn.commit()
    cur.close()


def geocode_rows(
    rows: Iterable[dict],
    *,
    id_field: str,
    label: str,
    cache: Dict[str, List[Optional[float]]],
    permanent: bool,
    min_interval: float,
    conn=None,
    table: Optional[str] = None,
    id_column: Optional[str] = None,
    dry_run: bool = False,
    commit_every: int = 50,
) -> Tuple[int, int, int]:
    pending: List[Tuple[Any, float, float]] = []
    written = 0
    skipped = 0
    failed = 0
    for row in tqdm(list(rows), desc=f"Geocoding {label}", unit=label.rstrip("s")):
        city, state, postal, country = (
            row.get("city"),
            row.get("state_prov"),
            row.get("postal_code"),
            row.get("country"),
        )
        if not any(_clean(v) for v in (city, state, postal, country)):
            skipped += 1
            continue
        lat, lng = geocode_location(
            city,
            state,
            postal,
            country,
            cache=cache,
            permanent=permanent,
            min_interval=min_interval,
        )
        if lat is None or lng is None:
            failed += 1
            ident = row.get(id_field)
            print(f"  no result for {label.rstrip('s')} {ident}: {city}, {state}, {postal}, {country}")
            continue
        pending.append((row[id_field], lat, lng))
        if not dry_run and conn and table and id_column and len(pending) >= commit_every:
            update_coords(conn, table, id_column, pending)
            written += len(pending)
            pending = []
            save_cache(cache)
    if not dry_run and conn and table and id_column and pending:
        update_coords(conn, table, id_column, pending)
        written += len(pending)
        pending = []
    elif dry_run:
        written = len(pending)
    return written, skipped, failed


def run(args: argparse.Namespace) -> int:
    if not MAPBOX_ACCESS_TOKEN:
        print("MAPBOX_ACCESS_TOKEN is not set.", file=sys.stderr)
        return 1

    assert_safe_db_target("geocode")
    print(f"DB target: {describe_db_target()}")
    print(f"Mapbox: {'permanent' if args.permanent else 'temporary'} geocoding")

    conn = get_pg_connection()
    try:
        ensure_location_columns(conn)
        if not _table_has_column(conn, "teams", "lat"):
            print("teams.lat/lng columns are missing; add them before geocoding.", file=sys.stderr)
            return 1

        do_teams = args.teams or not args.events
        do_events = args.events or not args.teams
        cache = load_cache()
        started = time.time()

        if do_teams:
            teams = fetch_teams(conn, limit=args.limit)
            print(f"Teams to geocode (rewrite all): {len(teams)}")
            written, skipped, failed = geocode_rows(
                teams,
                id_field="team_number",
                label="teams",
                cache=cache,
                permanent=args.permanent,
                min_interval=args.interval,
                conn=conn,
                table="teams",
                id_column="team_number",
                dry_run=args.dry_run,
            )
            save_cache(cache)
            verb = "Would update" if args.dry_run else "Updated"
            print(f"{verb} {written} team(s) (skipped {skipped}, failed {failed})")

        if do_events:
            events = fetch_events(conn, year=args.year, limit=args.limit)
            print(f"Events to geocode: {len(events)}")
            written, skipped, failed = geocode_rows(
                events,
                id_field="event_key",
                label="events",
                cache=cache,
                permanent=args.permanent,
                min_interval=args.interval,
                conn=conn,
                table="events",
                id_column="event_key",
                dry_run=args.dry_run,
            )
            save_cache(cache)
            verb = "Would update" if args.dry_run else "Updated"
            print(f"{verb} {written} event(s) (skipped {skipped}, failed {failed})")

        print(f"Done in {time.time() - started:.1f}s. Cache: {CACHE_PATH}")
        return 0
    finally:
        return_pg_connection(conn)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Geocode teams and events via Mapbox into Postgres.")
    parser.add_argument("--teams", action="store_true", help="Geocode teams only")
    parser.add_argument("--events", action="store_true", help="Geocode events only")
    parser.add_argument("--year", type=int, help="Limit events to this season (event_key prefix)")
    parser.add_argument("--dry-run", action="store_true", help="Call Mapbox but do not write to the DB")
    parser.add_argument("--limit", type=int, help="Max rows per table (for testing)")
    parser.add_argument(
        "--temporary",
        dest="permanent",
        action="store_false",
        help="Use Mapbox temporary geocoding (do not store results under Mapbox TOS)",
    )
    parser.set_defaults(permanent=True)
    parser.add_argument(
        "--interval",
        type=float,
        default=0.12,
        help="Minimum seconds between Mapbox requests (default 0.12)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
