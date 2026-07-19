import json
import os

from _latlng_env import bootstrap_env

bootstrap_env()

from psycopg2.extras import execute_values

from run import get_pg_connection

GEO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "geo")
TEAMS_GEO = os.path.join(GEO_DIR, "2026_geo_teams.json")
EVENTS_GEO = os.path.join(GEO_DIR, "2026_geo_events.json")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def backfill_teams(cur):
    """Re-populate teams.lat/lng from the geocoded geo JSON.

    Team coordinates come from offline geocoding (geo/geocode.py), not TBA, so this
    is the durable source. We update ALL matched teams (not only NULLs) so refreshed
    geo data can be re-applied; safe to run repeatedly.
    """
    data = _load(TEAMS_GEO)
    rows = []
    geo_team_numbers = set()
    for t in data:
        tn = t.get("team_number")
        if tn is None:
            continue
        geo_team_numbers.add(int(tn))
        lat, lng = t.get("lat"), t.get("lng")
        if lat is None or lng is None:
            continue
        rows.append((int(tn), float(lat), float(lng)))

    execute_values(
        cur,
        """
        UPDATE teams AS t
        SET lat = v.lat, lng = v.lng
        FROM (VALUES %s) AS v(team_number, lat, lng)
        WHERE t.team_number = v.team_number::int
        """,
        rows,
        template="(%s, %s::float8, %s::float8)",
        page_size=max(len(rows), 1),
    )
    updated = cur.rowcount

    cur.execute("SELECT COUNT(*) FROM teams")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM teams WHERE lat IS NOT NULL AND lng IS NOT NULL")
    with_coords = cur.fetchone()[0]
    cur.execute("SELECT team_number FROM teams WHERE lat IS NULL OR lng IS NULL")
    null_team_numbers = [r[0] for r in cur.fetchall()]
    missing_from_geo = [tn for tn in null_team_numbers if tn not in geo_team_numbers]

    return {
        "geo_rows_with_coords": len(rows),
        "geo_teams_total": len(geo_team_numbers),
        "rows_updated": updated,
        "db_total": total,
        "db_with_coords": with_coords,
        "db_null": total - with_coords,
        "null_missing_from_geo": len(missing_from_geo),
        "null_present_in_geo_but_no_coords": len(null_team_numbers) - len(missing_from_geo),
    }


def backfill_events(cur):
    """Populate events.lat/lng from the 2026 events geo JSON (TBA-sourced coordinates)."""
    data = _load(EVENTS_GEO)
    rows = []
    for e in data:
        key = e.get("key")
        if not key:
            continue
        lat, lng = e.get("lat"), e.get("lng")
        if lat is None or lng is None:
            continue
        rows.append((key, float(lat), float(lng)))

    execute_values(
        cur,
        """
        UPDATE events AS e
        SET lat = v.lat, lng = v.lng
        FROM (VALUES %s) AS v(event_key, lat, lng)
        WHERE e.event_key = v.event_key
        """,
        rows,
        template="(%s, %s::float8, %s::float8)",
        page_size=max(len(rows), 1),
    )
    updated = cur.rowcount

    cur.execute("SELECT COUNT(*) FROM events")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM events WHERE lat IS NOT NULL AND lng IS NOT NULL")
    with_coords = cur.fetchone()[0]
    cur.execute(
        """
        SELECT LEFT(event_key, 4) AS yr, COUNT(*)
        FROM events
        WHERE lat IS NULL OR lng IS NULL
        GROUP BY yr ORDER BY yr
        """
    )
    null_by_year = cur.fetchall()

    return {
        "geo_rows_with_coords": len(rows),
        "rows_updated": updated,
        "db_total": total,
        "db_with_coords": with_coords,
        "db_null": total - with_coords,
        "null_by_year": null_by_year,
    }


def main():
    conn = get_pg_connection()
    cur = conn.cursor()

    print("Backfilling teams...")
    team_stats = backfill_teams(cur)
    print("Backfilling events...")
    event_stats = backfill_events(cur)

    conn.commit()
    cur.close()
    conn.close()

    print("\n=== TEAMS ===")
    for k, v in team_stats.items():
        print(f"  {k}: {v}")
    print("\n=== EVENTS ===")
    for k, v in event_stats.items():
        if k == "null_by_year":
            print("  null_by_year:")
            for yr, cnt in v:
                print(f"    {yr}: {cnt}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
