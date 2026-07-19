"""
Helpers to select the subset of a season's events that are currently "active".

Used by the lighter, higher-frequency refresh path (rankings/awards) so that
in-season runs only hit The Blue Alliance for events happening right now instead
of every event in the season. This is safe for per-event upserts (rankings,
awards) because each event's rows are independent.
"""
from datetime import date, datetime, timedelta, timezone


def _as_date(value):
    """Coerce a stored start/end date (date, datetime, or 'YYYY-MM-DD' text) to a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def get_all_event_keys(conn, year):
    """Every event key for a season."""
    cur = conn.cursor()
    cur.execute("SELECT event_key FROM events WHERE event_key LIKE %s", (f"{year}%",))
    keys = [row[0] for row in cur.fetchall()]
    cur.close()
    return keys


def get_active_event_keys(conn, year, buffer_days=2):
    """
    Event keys whose competition window overlaps 'now' (inclusive of a small
    buffer on each side). Events with unparseable dates are included to be safe.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT event_key, start_date, end_date FROM events WHERE event_key LIKE %s",
        (f"{year}%",),
    )
    rows = cur.fetchall()
    cur.close()

    # Timezone-aware UTC "now" (datetime.utcnow() is deprecated and naive).
    today = datetime.now(timezone.utc).date()
    buffer = timedelta(days=buffer_days)
    active = []
    for event_key, start_date, end_date in rows:
        start = _as_date(start_date)
        end = _as_date(end_date)
        if start is None or end is None:
            # Keep undated/unparseable events in the active set to be safe for
            # genuinely-live events lacking dates. This relies on the rankings/
            # awards fetch fix: a failed or authoritatively-empty fetch now skips
            # the event instead of wiping its existing rows, so over-including an
            # undated event here can no longer cause data loss.
            active.append(event_key)
            continue
        if (start - buffer) <= today <= (end + buffer):
            active.append(event_key)
    return active


def resolve_event_keys(conn, year, active_only, buffer_days=2):
    """Return active-window keys when active_only, else all keys for the year."""
    if active_only:
        return get_active_event_keys(conn, year, buffer_days=buffer_days)
    return get_all_event_keys(conn, year)
