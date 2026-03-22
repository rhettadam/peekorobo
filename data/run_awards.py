import sys
import os

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from run import get_pg_connection, tba_get


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
    """Fetch awards from TBA for a single event. Returns list of (event_key, team_number, award_name)."""
    awards_data = tba_get(f"event/{event_key}/awards")
    if not awards_data:
        return []

    result = []
    for aw in awards_data:
        for r in aw.get("recipient_list", []):
            if r.get("team_key"):
                team_key = r["team_key"]
                if team_key.endswith("B"):
                    continue  # Skip B teams
                t_num = int(team_key[3:])
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


def update_awards_for_year(year):
    """Fetch awards for all events in a year and update the database."""
    print(f"\nFetching awards for {year}...")

    conn = get_pg_connection()
    event_keys = get_events_for_year(conn, year)

    if not event_keys:
        print(f"No events found for {year} in database")
        conn.close()
        return

    updated = 0
    skipped = 0

    for event_key in event_keys:
        existing = get_existing_awards(conn, event_key)
        new_awards = fetch_awards_for_event(event_key)
        new_set = set((a[1], a[2]) for a in new_awards)

        if existing == new_set:
            skipped += 1
            continue

        # Delete and reinsert
        cur = conn.cursor()
        cur.execute("DELETE FROM event_awards WHERE event_key = %s", (event_key,))

        if new_awards:
            seen = set()
            deduped = []
            for award in new_awards:
                key = (award[0], award[1], award[2])
                if key not in seen:
                    seen.add(key)
                    deduped.append(award)
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
    if len(sys.argv) != 2:
        print("Usage: python run_awards.py <year>")
        print("Example: python run_awards.py 2026")
        sys.exit(1)

    try:
        year = int(sys.argv[1])
    except ValueError:
        print("Year must be an integer.")
        sys.exit(1)

    update_awards_for_year(year)
