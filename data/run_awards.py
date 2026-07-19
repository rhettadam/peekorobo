import sys
import os

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from run import get_pg_connection, tba_get, tba_team_key_is_surrogate, parse_tba_team_number
from active_events import resolve_event_keys


def get_existing_awards(conn, event_key):
    """Get existing awards for an event from the database."""
    cur = conn.cursor()
    cur.execute(
        "SELECT team_number, award_name FROM event_awards WHERE event_key = %s",
        (event_key,),
    )
    awards = set((row[0], row[1]) for row in cur.fetchall())
    cur.close()
    return awards


def fetch_awards_for_event(event_key):
    """Fetch awards from TBA for a single event.

    Returns None when the underlying TBA request FAILED (tba_get returned None),
    so callers can distinguish a transient failure from an authoritative empty
    result. Returns a list (possibly empty) when TBA actually responded.
    """
    awards_data = tba_get(f"event/{event_key}/awards")
    if awards_data is None:
        # Transient TBA failure (non-200 / exhausted retries). Signal failure so
        # the caller can skip this event rather than wiping existing rows.
        return None
    if not awards_data:
        # TBA responded but there are genuinely no awards yet.
        return []

    result = []
    for aw in awards_data:
        for r in aw.get("recipient_list", []):
            if r.get("team_key"):
                team_key = r["team_key"]
                # Skip TBA surrogate entries (frc254B, frc498E, ...).
                if tba_team_key_is_surrogate(team_key):
                    continue
                t_num = parse_tba_team_number(team_key)
                if t_num is None:
                    continue
                result.append((event_key, t_num, aw.get("name")))
    return result


def get_events_for_year(conn, year):
    """Get event keys for a year from the database."""
    cur = conn.cursor()
    cur.execute(
        "SELECT event_key FROM events WHERE event_key LIKE %s",
        (f"{year}%",),
    )
    event_keys = [row[0] for row in cur.fetchall()]
    cur.close()
    return event_keys


def update_awards_for_year(year, active_only=False):
    """Fetch awards for events in a year and update the database.

    When active_only is True, only events currently in their competition window
    are refreshed - the cheap, high-frequency in-season path.
    """
    print(f"\nFetching awards for {year}{' (active events only)' if active_only else ''}...")

    conn = get_pg_connection()
    event_keys = resolve_event_keys(conn, year, active_only)

    if not event_keys:
        print(f"No {'active ' if active_only else ''}events found for {year} in database")
        conn.close()
        return

    updated = 0
    skipped = 0

    for event_key in event_keys:
        existing = get_existing_awards(conn, event_key)
        new_awards = fetch_awards_for_event(event_key)

        # Fetch failed (transient TBA error): skip entirely, never wipe.
        if new_awards is None:
            print(f"  WARNING: awards fetch failed for {event_key}; skipping to avoid wiping existing data")
            skipped += 1
            continue

        # Fetch returned empty but we already have rows: treat as suspicious
        # (likely a failure that slipped through) and skip rather than wipe.
        if not new_awards and existing:
            print(f"  WARNING: awards fetch returned empty for {event_key} which has existing rows; skipping to avoid wiping")
            skipped += 1
            continue

        new_set = set((a[1], a[2]) for a in new_awards)
        if existing == new_set:
            skipped += 1
            continue

        # Only reach here when there is new, non-empty data to write. Delete the
        # old rows and insert the fresh set inside the same branch so we never
        # delete-then-insert-nothing.
        seen = set()
        deduped = []
        for award in new_awards:
            key = (award[0], award[1], award[2])
            if key not in seen:
                seen.add(key)
                deduped.append(award)

        cur = conn.cursor()
        cur.execute("DELETE FROM event_awards WHERE event_key = %s", (event_key,))
        cur.executemany(
            """
            INSERT INTO event_awards (event_key, team_number, award_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (event_key, team_number, award_name) DO NOTHING
            """,
            deduped,
        )
        cur.close()
        updated += 1

    conn.commit()
    conn.close()

    print(f"\nAwards update complete for {year}:")
    print(f"  Updated: {updated} events")
    print(f"  Unchanged: {skipped} events")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    active_only = "--active-only" in sys.argv[1:]
    if len(args) != 1:
        print("Usage: python run_awards.py <year> [--active-only]")
        print("Example: python run_awards.py 2026 --active-only")
        sys.exit(1)

    try:
        year = int(args[0])
    except ValueError:
        print("Year must be an integer.")
        sys.exit(1)

    update_awards_for_year(year, active_only=active_only)
