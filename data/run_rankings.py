"""
Fetch and store event rankings from TBA. Run separately from the main run.py pipeline.

Usage: python run_rankings.py <year>
Example: python run_rankings.py 2026
"""
import sys
import os

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from run import get_pg_connection, tba_get, tba_team_key_is_surrogate, parse_tba_team_number
from active_events import resolve_event_keys


def get_existing_rankings(conn, event_key):
    """Get existing rankings for an event from the database."""
    cur = conn.cursor()
    cur.execute(
        "SELECT team_number, rank, wins, losses, ties, dq FROM event_rankings WHERE event_key = %s",
        (event_key,),
    )
    rankings = {row[0]: {"rank": row[1], "wins": row[2], "losses": row[3], "ties": row[4], "dq": row[5]} for row in cur.fetchall()}
    cur.close()
    return rankings or {}


def fetch_rankings_for_event(event_key, year):
    """Fetch rankings from TBA for a single event.

    Returns None when the underlying TBA request FAILED (tba_get returned None),
    so callers can distinguish a transient failure from an authoritative empty
    result. Returns a list (possibly empty) when TBA actually responded.
    """
    ranks = tba_get(f"event/{event_key}/rankings")
    if ranks is None:
        # Transient TBA failure (non-200 / exhausted retries). Signal failure so
        # the caller can skip this event rather than wiping existing rows.
        return None
    if not ranks.get("rankings"):
        # TBA responded but there are genuinely no rankings yet.
        return []

    result = []
    for r in ranks.get("rankings", []):
        team_key = r.get("team_key", "frc0")
        # Skip TBA surrogate entries (frc254B, frc498E, ...); keep real team numbers only.
        if tba_team_key_is_surrogate(team_key):
            continue
        t_num = parse_tba_team_number(team_key)
        if t_num is None:
            continue

        if str(year) == "2015":
            qual_avg = r.get("qual_average")
            result.append((event_key, t_num, r.get("rank"), qual_avg, None, None, r.get("dq")))
        else:
            record = r.get("record", {})
            result.append((
                event_key, t_num, r.get("rank"),
                record.get("wins"), record.get("losses"), record.get("ties"),
                r.get("dq")
            ))
    return result


def rankings_changed(existing, new_rankings):
    """Check if rankings have changed."""
    existing_team_nums = set(existing.keys())
    new_team_nums = set(r[1] for r in new_rankings)
    if existing_team_nums != new_team_nums:
        return True
    for row in new_rankings:
        team_num = row[1]
        if team_num not in existing:
            return True
        ex = existing[team_num]
        if (ex["rank"] != row[2] or ex["wins"] != row[3] or ex["losses"] != row[4] or
                ex["ties"] != row[5] or ex["dq"] != row[6]):
            return True
    return False


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


def update_rankings_for_year(year, active_only=False):
    """Fetch rankings for events in a year and update the database.

    When active_only is True, only events currently in their competition window
    are refreshed - the cheap, high-frequency in-season path.
    """
    print(f"\nFetching rankings for {year}{' (active events only)' if active_only else ''}...")

    conn = get_pg_connection()
    event_keys = resolve_event_keys(conn, year, active_only)

    if not event_keys:
        print(f"No {'active ' if active_only else ''}events found for {year} in database")
        conn.close()
        return

    updated = 0
    skipped = 0

    for event_key in event_keys:
        existing = get_existing_rankings(conn, event_key)
        new_rankings = fetch_rankings_for_event(event_key, year)

        # Fetch failed (transient TBA error): skip entirely, never wipe.
        if new_rankings is None:
            print(f"  WARNING: rankings fetch failed for {event_key}; skipping to avoid wiping existing data")
            skipped += 1
            continue

        # Fetch returned empty but we already have rows: treat as suspicious
        # (likely a failure that slipped through) and skip rather than wipe.
        if not new_rankings and existing:
            print(f"  WARNING: rankings fetch returned empty for {event_key} which has existing rows; skipping to avoid wiping")
            skipped += 1
            continue

        if not rankings_changed(existing, new_rankings):
            skipped += 1
            continue

        # Only reach here when there is new, non-empty data to write. Delete the
        # old rows and insert the fresh set inside the same branch so we never
        # delete-then-insert-nothing.
        cur = conn.cursor()
        cur.execute("DELETE FROM event_rankings WHERE event_key = %s", (event_key,))
        cur.executemany(
            """
            INSERT INTO event_rankings (event_key, team_number, rank, wins, losses, ties, dq)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key, team_number) DO UPDATE SET
                rank = EXCLUDED.rank,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                ties = EXCLUDED.ties,
                dq = EXCLUDED.dq
            """,
            new_rankings,
        )
        cur.close()
        updated += 1

    conn.commit()
    conn.close()

    print(f"\nRankings update complete for {year}:")
    print(f"  Updated: {updated} events")
    print(f"  Unchanged: {skipped} events")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    active_only = "--active-only" in sys.argv[1:]
    if len(args) != 1:
        print("Usage: python run_rankings.py <year> [--active-only]")
        print("Example: python run_rankings.py 2026 --active-only")
        sys.exit(1)

    try:
        year = int(args[0])
    except ValueError:
        print("Year must be an integer.")
        sys.exit(1)

    update_rankings_for_year(year, active_only=active_only)
