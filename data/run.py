import statistics
import json
from collections import defaultdict
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type, stop_after_attempt
import requests
import os
import concurrent.futures
from datetime import datetime, date, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import random
from typing import Dict, List, Optional, Union
from functools import wraps
import signal
import sys
import threading
import time  # <-- Added for runtime tracking
import math
import traceback

from yearmodels import *

start_time = time.time()

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

import psycopg2
from psycopg2.extras import execute_values
from urllib.parse import urlparse

# Global variables for cleanup
active_executors = []
active_connections = []
shutdown_event = threading.Event()

# Serialize EPA ingest across processes (e.g. Heroku Scheduler: a new one-off dyno every N
# minutes does not wait for the previous run; long runs overlap and can corrupt work).
_PIPELINE_ADV_LOCK_KEY1 = 893741
_PIPELINE_ADV_LOCK_KEY2 = 20260401


def _release_pipeline_lock(conn) -> None:
    if conn is None or conn.closed:
        return
    try:
        c = conn.cursor()
        c.execute(
            "SELECT pg_advisory_unlock(%s, %s)",
            (_PIPELINE_ADV_LOCK_KEY1, _PIPELINE_ADV_LOCK_KEY2),
        )
        c.close()
    except Exception as e:
        print(f"[pipeline] pg_advisory_unlock failed: {e}", flush=True)
    try:
        if conn in active_connections:
            active_connections.remove(conn)
    except ValueError:
        pass
    try:
        conn.close()
    except Exception:
        pass

# Global match cache to avoid redundant API calls
match_cache = {}

# API call counter
api_call_counter = 0

# Confidence calculation constants
CONFIDENCE_WEIGHTS = {
    "consistency": 0.35,
    "dominance": 0.35,
    "record_alignment": 0.10,
    "veteran": 0.10,
    "events": 0.10,
}

CONFIDENCE_THRESHOLDS = {
    "high": 0.9,  # Lower threshold for high confidence boost
    "low": 0.7,   # Higher threshold for low confidence reduction
}

CONFIDENCE_MULTIPLIERS = {
    "high_boost": 1.05,  # Reduced multiplier for high confidence
    "low_reduction": 0.85  # Increased multiplier for low confidence
}

EVENT_BOOSTS = {
    1: 0.5,   # Single event
    2: 0.8,  # Two events
    3: 1.0    # Three or more events
}

WEEK_RANGES_BY_YEAR = None


def load_week_ranges():
    global WEEK_RANGES_BY_YEAR
    if WEEK_RANGES_BY_YEAR is not None:
        return WEEK_RANGES_BY_YEAR
    possible_paths = [
        'week_ranges.json',
        'data/week_ranges.json',
        '../data/week_ranges.json',
        os.path.join(os.path.dirname(__file__), 'week_ranges.json'),
        os.path.join(os.path.dirname(__file__), '..', 'data', 'week_ranges.json')
    ]
    for path in possible_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                WEEK_RANGES_BY_YEAR = json.load(f)
            break
        except (FileNotFoundError, IOError, json.JSONDecodeError):
            continue
    if WEEK_RANGES_BY_YEAR is None:
        WEEK_RANGES_BY_YEAR = {}
        print("Warning: Could not load week_ranges.json from any of the attempted paths")
    return WEEK_RANGES_BY_YEAR

def get_event_week_number(start_date: Optional[str], end_date: Optional[str], event_key: Optional[str] = None) -> Optional[int]:
    week_ranges_by_year = load_week_ranges()
    if not week_ranges_by_year:
        return None

    start_dt = None
    end_dt = None
    year = None

    if start_date:
        try:
            start_dt = date.fromisoformat(start_date)
            year = str(start_dt.year)
        except Exception:
            start_dt = None
    if end_date:
        try:
            end_dt = date.fromisoformat(end_date)
            if year is None:
                year = str(end_dt.year)
        except Exception:
            end_dt = None
    if year is None and event_key and len(event_key) >= 4 and event_key[:4].isdigit():
        year = event_key[:4]

    if not year:
        return None

    week_ranges = week_ranges_by_year.get(year)
    if not week_ranges:
        return None

    def week_for_date(dt: date) -> Optional[int]:
        for i, (start, end) in enumerate(week_ranges):
            try:
                start_range = date.fromisoformat(start)
                end_range = date.fromisoformat(end)
            except Exception:
                continue
            if start_range <= dt <= end_range:
                return i
        return None

    if start_dt:
        week = week_for_date(start_dt)
        if week is not None:
            return week
    if end_dt:
        week = week_for_date(end_dt)
        if week is not None:
            return week

    if start_dt and end_dt:
        for i, (start, end) in enumerate(week_ranges):
            try:
                start_range = date.fromisoformat(start)
                end_range = date.fromisoformat(end)
            except Exception:
                continue
            if start_dt <= end_range and end_dt >= start_range:
                return i

    return None

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    global api_call_counter
    api_call_counter += 1
    print(f"API call {api_call_counter}: {endpoint}")
    
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, headers=headers, timeout=30)  # Add 30 second timeout
        if r.status_code == 200:
            return r.json()
        else:
            print(f"TBA API error for {endpoint}: {r.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout for {endpoint}")
        raise  # Let retry handle it
    except requests.exceptions.RequestException as e:
        print(f"Request error for {endpoint}: {e}")
        raise  # Let retry handle it
    except Exception as e:
        print(f"Unexpected error for {endpoint}: {e}")
        raise  # Let retry handle it

def signal_handler(signum, frame):
    # Handle Ctrl+C and other termination signals gracefully
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    shutdown_event.set()
    
    # Cancel all running futures
    for executor in active_executors:
        if hasattr(executor, 'shutdown'):
            executor.shutdown(wait=False, cancel_futures=True)
    
    # Close all database connections
    for conn in active_connections:
        try:
            if conn and not conn.closed:
                conn.close()
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")
    
    print("Cleanup complete. Exiting.")
    # sys.exit(0) waits for non-daemon ThreadPoolExecutor workers; Heroku then hits
    # R12 (SIGKILL after 30s). os._exit terminates immediately after the cleanup above.
    os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup_executor(executor):
    # Safely shutdown an executor
    if executor and hasattr(executor, 'shutdown'):
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            print(f"Warning: Error shutting down executor: {e}")

def cleanup_connection(conn):
    # Safely close a database connection
    if conn and not conn.closed:
        try:
            conn.close()
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")

def restart_heroku_app():
    # Restart the Heroku app to reload updated data.
    app_name = os.environ.get("HEROKU_APP_NAME")
    api_key = os.environ.get("HEROKU_API_KEY")

    if not app_name or not api_key:
        print("HEROKU_APP_NAME or HEROKU_API_KEY not set, skipping app restart")
        return

    try:
        url = f"https://api.heroku.com/apps/{app_name}/dynos"
        headers = {
            "Accept": "application/vnd.heroku+json; version=3",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Restart all dynos.
        response = requests.delete(url, headers=headers)
        if response.status_code == 202:
            print(f"Successfully restarted Heroku app: {app_name}")
        else:
            print(f"Failed to restart app: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error restarting app: {e}")

# Robust retry for DB connection
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_pg_connection():
    if shutdown_event.is_set():
        raise Exception("Shutdown requested")
        
    url = os.environ.get("DATABASE_URL")
    if url is None:
        raise Exception("DATABASE_URL not set in environment.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    result = urlparse(url)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        connect_timeout=30,
        options='-c statement_timeout=300000'
    )
    active_connections.append(conn)
    return conn

def _normalize_district_key(key):
    """TBA uses 2024fim; normalize to FIM."""
    if not key or len(key) <= 4:
        return key
    if key[:4].isdigit():
        return key[4:].upper()
    return key.upper()


def upsert_district(cur, district_key, district_abbrev, district_name):
    """Upsert district into districts table (if it exists). Normalizes 2024fim -> FIM."""
    if not district_key:
        return
    base_key = _normalize_district_key(district_key)
    if not base_key:
        return
    try:
        cur.execute("""
            INSERT INTO districts (district_key, name, abbreviation, state_names, state_abbrevs)
            VALUES (%s, %s, %s, '[]'::jsonb, '[]'::jsonb)
            ON CONFLICT (district_key) DO UPDATE SET
                name = COALESCE(NULLIF(EXCLUDED.name, ''), districts.name),
                abbreviation = COALESCE(NULLIF(EXCLUDED.abbreviation, ''), districts.abbreviation)
        """, (base_key, district_name or base_key, district_abbrev or base_key))
    except Exception:
        pass  # districts table may not exist yet

def upsert_team_profile(result):
    # Insert or update a team's general profile data
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO teams (team_number, nickname, city, state_prov, country, website)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_number) DO UPDATE SET
            nickname = EXCLUDED.nickname,
            city = EXCLUDED.city,
            state_prov = EXCLUDED.state_prov,
            country = EXCLUDED.country,
            website = EXCLUDED.website
        """,
        (
            result.get("team_number"),
            result.get("nickname"),
            result.get("city"),
            result.get("state_prov"),
            result.get("country"),
            result.get("website"),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def insert_team_epa(result, year):
    # Insert or update a team's EPA data for a given year
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO team_epas (
            team_number, year,
            raw, ace, confidence, auto_raw, teleop_raw, endgame_raw,
            wins, losses, ties, event_perf
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_number, year) DO UPDATE SET
            raw = EXCLUDED.raw,
            ace = EXCLUDED.ace,
            confidence = EXCLUDED.confidence,
            auto_raw = EXCLUDED.auto_raw,
            teleop_raw = EXCLUDED.teleop_raw,
            endgame_raw = EXCLUDED.endgame_raw,
            wins = EXCLUDED.wins,
            losses = EXCLUDED.losses,
            ties = EXCLUDED.ties,
            event_perf = EXCLUDED.event_perf
        """,
        (
            result.get("team_number"),
            year,
            result.get("raw"),
            result.get("ace"),
            result.get("confidence"),
            result.get("auto_raw"),
            result.get("teleop_raw"),
            result.get("endgame_raw"),
            result.get("wins"),
            result.get("losses"),
            result.get("ties"),
            json.dumps(result.get("event_perf", [])),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def _is_demo_team_rank(team_number):
    try:
        n = int(team_number)
        return 9970 <= n <= 9999
    except (TypeError, ValueError):
        return False


def _team_has_season_competition(team):
    """True if the team has at least one qual/playoff result row for the season (not just registration)."""
    w = team.get("wins") or 0
    l = team.get("losses") or 0
    t = team.get("ties") or 0
    try:
        return int(w) + int(l) + int(t) > 0
    except (TypeError, ValueError):
        return False


def _is_eligible_for_ace_rank(team):
    """
    Teams included in ACE rank pools: real team numbers, ACE != 0, and competed this season.
    Excludes demo teams (9970–9999), ACE 0 / NULL, and teams with no counted matches.
    """
    if _is_demo_team_rank(team.get("team_number")):
        return False
    ace = team.get("ace")
    if ace is None:
        return False
    try:
        if float(ace) == 0.0:
            return False
    except (TypeError, ValueError):
        return False
    return _team_has_season_competition(team)


def _district_key_normalized_rank(key):
    """Align with utils.normalize_district_key for grouping."""
    if not key or not isinstance(key, str):
        return None
    s = key.strip()
    if len(s) > 4 and s[:4].isdigit():
        return s[4:].upper()
    return s.upper() if s else None


def _district_bucket_rank(team):
    """Stable district bucket for same-district comparisons (key preferred, else display name)."""
    dk = team.get("district_key")
    nk = _district_key_normalized_rank(dk)
    if nk:
        return nk
    if dk and str(dk).strip():
        return str(dk).strip().upper()
    dn = (team.get("district") or "").strip()
    return dn.upper() if dn else None


def _team_has_district_key_for_ui(team):
    """Match layouts: rank shown only when TBA district_key is present."""
    return bool(_district_key_normalized_rank(team.get("district_key")) or (team.get("district_key") or "").strip())


def _same_district_rank(sel, t):
    """Match teams in the same district bucket (aligned with team insights filtering)."""
    a = _district_bucket_rank(sel)
    b = _district_bucket_rank(t)
    if not a or not b:
        return False
    return a == b


def _block_competition_ranks(members):
    """
    members: iterable of (team_number, ace) with ace not None.
    Competition rank = 1 + count of others with strictly higher ACE (ties share rank).
    Returns dict team_number -> int rank.
    """
    lst = sorted(members, key=lambda x: (-(x[1] if x[1] is not None else 0.0), x[0]))
    ranks = {}
    n = len(lst)
    i = 0
    while i < n:
        ace_i = lst[i][1]
        ai = ace_i if ace_i is not None else 0.0
        j = i + 1
        while j < n:
            aj = lst[j][1]
            aj = aj if aj is not None else 0.0
            if aj != ai:
                break
            j += 1
        block_rank = i + 1
        for k in range(i, j):
            ranks[lst[k][0]] = block_rank
        i = j
    return ranks


def compute_and_store_team_epa_ranks(year: int, quiet: bool = False, conn=None):
    """
    Compute global / country / state / district ACE ranks for one season and UPDATE team_epas.

    Competition-style ranks: rank = 1 + count of eligible peers in scope with strictly higher ACE
    (ties share the same rank). Eligible peers exclude demo teams (9970–9999), ACE 0, and teams
    with no season W/L/T. District scope uses teams.district_key + districts display join the
    same way as datagather.

    District ranks are only stored when the team has a district_key (regional teams: NULL).

    Pass ``conn`` to reuse a single connection (e.g. backfill); otherwise a new connection is opened.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT te.team_number, te.ace,
                   te.wins, te.losses, te.ties,
                   t.country, t.state_prov, t.district_key,
                   COALESCE(d.display_name, d.name) AS district
            FROM team_epas te
            LEFT JOIN teams t ON te.team_number = t.team_number
            LEFT JOIN districts d ON (
                CASE WHEN t.district_key ~ '^[0-9]{4}[a-zA-Z]+$'
                     THEN UPPER(SUBSTRING(t.district_key FROM 5))
                     ELSE UPPER(TRIM(t.district_key))
                END
            ) = d.district_key
            WHERE te.year = %s
            """,
            (year,),
        )
        rows = cur.fetchall()
    except Exception as e:
        cur.close()
        if own_conn:
            conn.close()
        print(f"compute_and_store_team_epa_ranks: query failed (missing columns or join?): {e}")
        raise

    teams = []
    for team_number, ace, wins, losses, ties, country, state_prov, district_key, district in rows:
        teams.append(
            {
                "team_number": team_number,
                "ace": ace,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "country": (country or "").lower(),
                "state_prov": (state_prov or "").lower(),
                "district_key": district_key,
                "district": district,
            }
        )

    rankable = [t for t in teams if _is_eligible_for_ace_rank(t)]
    has_rankable_pool = len(rankable) > 0

    count_country_tot = defaultdict(int)
    count_state_tot = defaultdict(int)
    for t in rankable:
        count_country_tot[t["country"]] += 1
        count_state_tot[t["state_prov"]] += 1

    global_members = []
    country_groups = defaultdict(list)
    state_groups = defaultdict(list)
    district_groups = defaultdict(list)

    for t in rankable:
        te = t.get("ace")
        if te is None:
            continue
        tn = t["team_number"]
        global_members.append((tn, te))
        country_groups[t["country"]].append((tn, te))
        state_groups[t["state_prov"]].append((tn, te))
        bk = _district_bucket_rank(t)
        if bk:
            district_groups[bk].append((tn, te))

    global_ranks = _block_competition_ranks(global_members)
    country_ranks = {}
    for _c, members in country_groups.items():
        country_ranks.update(_block_competition_ranks(members))
    state_ranks = {}
    for _s, members in state_groups.items():
        state_ranks.update(_block_competition_ranks(members))
    district_ranks = {}
    for _b, members in district_groups.items():
        district_ranks.update(_block_competition_ranks(members))

    updates = []
    for sel in teams:
        tn = sel["team_number"]
        null_row = (None,) * 8
        if not has_rankable_pool or not _is_eligible_for_ace_rank(sel):
            updates.append(null_row + (tn, year))
            continue

        sel_country = sel["country"]
        sel_state = sel["state_prov"]

        count_global = len(rankable)
        count_c = count_country_tot[sel_country]
        count_s = count_state_tot[sel_state]

        gr = global_ranks.get(tn)
        cr = country_ranks.get(tn)
        sr = state_ranks.get(tn)

        dr = cd = None
        if _team_has_district_key_for_ui(sel):
            district_peers = [x for x in rankable if _same_district_rank(sel, x)]
            cd = len(district_peers)
            if cd > 0:
                dr = district_ranks.get(tn)
            else:
                dr = None
                cd = None

        updates.append((gr, cr, sr, dr, count_global, count_c, count_s, cd, tn, year))

    if updates:
        batch_rows = [
            (tn, y, gr, cr, sr, dr, cg, cc, cs, cd)
            for (gr, cr, sr, dr, cg, cc, cs, cd, tn, y) in updates
        ]
        execute_values(
            cur,
            """
            UPDATE team_epas AS te SET
                rank_global = v.rank_global::integer,
                rank_country = v.rank_country::integer,
                rank_state = v.rank_state::integer,
                rank_district = v.rank_district::integer,
                count_global = v.count_global::integer,
                count_country = v.count_country::integer,
                count_state = v.count_state::integer,
                count_district = v.count_district::integer
            FROM (VALUES %s) AS v(
                team_number,
                year,
                rank_global,
                rank_country,
                rank_state,
                rank_district,
                count_global,
                count_country,
                count_state,
                count_district
            )
            WHERE te.team_number = v.team_number::integer AND te.year = v.year::integer
            """,
            batch_rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=len(batch_rows),
        )
    conn.commit()
    cur.close()
    if own_conn:
        conn.close()
    if not quiet:
        print(f"Stored ACE ranks for year {year} ({len(updates)} teams).")


# Robust retry for team experience
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_experience_pg(team_number, up_to_year):
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT year) FROM team_epas
        WHERE team_number = %s AND year <= %s
    """, (team_number, up_to_year))
    years = cur.fetchone()[0]
    cur.close()
    conn.close()
    return years if years else 1

# Robust retry for team events
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_events(team_number, year):
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT event_key FROM event_teams
        WHERE team_number = %s AND LEFT(event_key, 4) = %s
    """, (team_number, str(year)))
    events = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return events

def _predicted_time_to_datetime(predicted_time):
    if not predicted_time:
        return None
    if isinstance(predicted_time, datetime):
        return predicted_time if predicted_time.tzinfo else predicted_time.replace(tzinfo=timezone.utc)
    if isinstance(predicted_time, (int, float)):
        return datetime.fromtimestamp(predicted_time, tz=timezone.utc)
    if isinstance(predicted_time, str):
        try:
            if predicted_time.isdigit():
                return datetime.fromtimestamp(int(predicted_time), tz=timezone.utc)
            return datetime.fromisoformat(predicted_time.replace("Z", "+00:00"))
        except Exception:
            return None
    return None

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_played_events(team_number, year):
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT event_key, red_score, blue_score, winning_alliance, predicted_time
        FROM event_matches
        WHERE LEFT(event_key, 4) = %s
          AND (%s = ANY(string_to_array(red_teams, ',')) OR %s = ANY(string_to_array(blue_teams, ',')))
        """,
        (str(year), str(team_number), str(team_number)),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    played_events = set()
    now_utc = datetime.now(timezone.utc)
    for event_key, red_score, blue_score, winning_alliance, predicted_time in rows:
        if (red_score and red_score > 0) or (blue_score and blue_score > 0) or winning_alliance in ("red", "blue"):
            played_events.add(event_key)
            continue
        predicted_dt = _predicted_time_to_datetime(predicted_time)
        if predicted_dt and predicted_dt <= now_utc:
            played_events.add(event_key)
    return list(played_events)

def get_teams_for_year(year):
    # Return a list of all teams that played in a given year, using teams table for profile data
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT
            et.team_number,
            COALESCE(t.nickname, et.nickname),
            COALESCE(t.city, et.city),
            COALESCE(t.state_prov, et.state_prov),
            COALESCE(t.country, et.country),
            t.website
        FROM event_teams et
        LEFT JOIN teams t ON et.team_number = t.team_number
        WHERE LEFT(et.event_key, 4) = %s
        """,
        (str(year),),
    )
    teams = []
    for row in cur.fetchall():
        teams.append(
            {
                "team_number": row[0],
                "nickname": row[1],
                "city": row[2],
                "state_prov": row[3],
                "country": row[4],
                "website": row[5] if row[5] else "N/A",
                "key": f"frc{row[0]}",
            }
        )
    cur.close()
    conn.close()
    return teams

def get_existing_event_data(event_key):
    # Get existing event data from database for comparison
    conn = get_pg_connection()
    cur = conn.cursor()
    
    # Get event (including webcast info)
    cur.execute("""
        SELECT name, start_date, end_date, event_type,
               district_key, district_abbrev, district_name,
               city, state_prov, country, website, webcast_type, webcast_channel, week
        FROM events WHERE event_key = %s
    """, (event_key,))
    event_row = cur.fetchone()
    
    # Get teams - ensure we always return a dict, even if empty
    cur.execute("SELECT team_number, nickname, city, state_prov, country FROM event_teams WHERE event_key = %s", (event_key,))
    teams = {row[0]: {"nickname": row[1], "city": row[2], "state_prov": row[3], "country": row[4]} for row in cur.fetchall()}
    if not teams:
        teams = {}  # Ensure it's always a dict, not None
    
    # Get matches
    cur.execute("SELECT match_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time FROM event_matches WHERE event_key = %s", (event_key,))
    matches = {row[0]: {"comp_level": row[1], "match_number": row[2], "set_number": row[3], "red_teams": row[4], "blue_teams": row[5], "red_score": row[6], "blue_score": row[7], "winning_alliance": row[8], "youtube_key": row[9], "predicted_time": row[10]} for row in cur.fetchall()}
    if not matches:
        matches = {}
    
    cur.close()
    conn.close()
    
    return {
        "event": event_row,
        "teams": teams,
        "matches": matches,
    }

def event_has_started(event_key, start_date):
    try:
        now = datetime.now(timezone.utc)
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                if start_date_obj > now.date():
                    return False
            except Exception:
                pass

        conn = get_pg_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT red_score, blue_score, winning_alliance, predicted_time
            FROM event_matches
            WHERE event_key = %s
            """,
            (event_key,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return True  # No match data yet; allow initial load (create_event_db needs this to process new events)

        for red_score, blue_score, winning_alliance, _ in rows:
            if (red_score and red_score > 0) or (blue_score and blue_score > 0) or winning_alliance in ("red", "blue"):
                return True

        predicted_times = [_predicted_time_to_datetime(r[3]) for r in rows]
        predicted_times = [pt for pt in predicted_times if pt is not None]
        if predicted_times and min(predicted_times) > now:
            return False
        return True
    except Exception:
        return True

def get_existing_team_epa(team_number, year):
    # Get existing team EPA data from database for comparison
    conn = get_pg_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT raw, ace, confidence,
               auto_raw, teleop_raw, endgame_raw, wins, losses, ties, event_perf
        FROM team_epas WHERE team_number = %s AND year = %s
        """,
        (team_number, year),
    )
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        event_perf_raw = row[9]
        if event_perf_raw is None:
            event_perf = []
        elif isinstance(event_perf_raw, str):
            try:
                event_perf = json.loads(event_perf_raw)
            except (json.JSONDecodeError, TypeError):
                event_perf = []
        elif isinstance(event_perf_raw, list):
            event_perf = event_perf_raw
        else:
            event_perf = []
        auto_raw = row[3] if row[3] is not None else 0.0
        teleop_raw = row[4] if row[4] is not None else 0.0
        endgame_raw = row[5] if row[5] is not None else 0.0
        return {
            "raw": row[0],
            "ace": row[1],
            "confidence": row[2],
            "auto_raw": auto_raw,
            "teleop_raw": teleop_raw,
            "endgame_raw": endgame_raw,
            "wins": row[6],
            "losses": row[7],
            "ties": row[8],
            "event_perf": event_perf
        }
    return None

def data_has_changed(existing, new_data, data_type):
    # Compare existing data with new data to determine if an update is needed
    if not existing:
        return True  # No existing data, needs to be inserted
    
    if data_type == "event":
        existing_event = existing["event"]
        if not existing_event:
            return True
        
        new_event = new_data["event"]
        return (
            existing_event[0] != new_event[1] or  # name
            existing_event[1] != new_event[2] or  # start_date
            existing_event[2] != new_event[3] or  # end_date
            existing_event[3] != new_event[4] or  # event_type
            existing_event[4] != new_event[5] or  # district_key
            existing_event[5] != new_event[6] or  # district_abbrev
            existing_event[6] != new_event[7] or  # district_name
            existing_event[7] != new_event[8] or  # city
            existing_event[8] != new_event[9] or  # state_prov
            existing_event[9] != new_event[10] or  # country
            existing_event[10] != new_event[11] or  # website
            existing_event[11] != new_event[12] or # webcast_type
            existing_event[12] != new_event[13] or  # webcast_channel
            existing_event[13] != new_event[14]    # week
        )
    
    elif data_type == "teams":
        existing_teams = existing.get("teams", {}) or {}
        new_teams = new_data.get("teams", []) or []
        
        # Handle None values
        if existing_teams is None:
            existing_teams = {}
        if new_teams is None:
            new_teams = []
        
        # Check if team lists are different
        existing_team_nums = set(existing_teams.keys()) if isinstance(existing_teams, dict) else set()
        new_team_nums = set(team[1] for team in new_teams if len(team) > 1)
        
        if existing_team_nums != new_team_nums:
            return True
        
        # Check if any team data has changed
        for team_data in new_teams:
            if len(team_data) < 6:
                continue  # Skip invalid team data
            team_num = team_data[1]
            if team_num not in existing_teams:
                return True
            
            existing_team = existing_teams[team_num]
            if (
                existing_team.get("nickname") != team_data[2] or
                existing_team.get("city") != team_data[3] or
                existing_team.get("state_prov") != team_data[4] or
                existing_team.get("country") != team_data[5]
            ):
                return True
        
        return False
    
    elif data_type == "matches":
        existing_matches = existing["matches"]
        new_matches = new_data["matches"]
        
        # Check if match lists are different
        existing_match_keys = set(existing_matches.keys())
        new_match_keys = set(match[0] for match in new_matches)
        
        if existing_match_keys != new_match_keys:
            return True
        
        # Check if any match data has changed
        for match_data in new_matches:
            match_key = match_data[0]
            if match_key not in existing_matches:
                return True
            
            existing_match = existing_matches[match_key]
            if (
                existing_match["comp_level"] != match_data[2] or
                existing_match["match_number"] != match_data[3] or
                existing_match["set_number"] != match_data[4] or
                existing_match["red_teams"] != match_data[5] or
                existing_match["blue_teams"] != match_data[6] or
                existing_match["red_score"] != match_data[7] or
                existing_match["blue_score"] != match_data[8] or
                existing_match["winning_alliance"] != match_data[9] or
                existing_match["youtube_key"] != match_data[10] or
                existing_match["predicted_time"] != match_data[11]
            ):
                return True
        
        return False
    
    elif data_type == "team_epa":
        # For team EPA, we'll do a more detailed comparison
        if not existing:
            return True

        # Patch: ensure all perf fields are never None
        for key in ["raw", "ace", "confidence", "auto_raw", "teleop_raw", "endgame_raw"]:
            if existing.get(key) is None:
                existing[key] = 0.0
            if new_data.get(key) is None:
                new_data[key] = 0.0

        # Compare key values with tolerance for floating point differences
        def float_equal(a, b, tolerance=0.01):
            a = a if a is not None else 0.0
            b = b if b is not None else 0.0
            return abs(a - b) < tolerance

        if (
            not float_equal(existing.get("raw"), new_data.get("raw")) or
            not float_equal(existing.get("ace"), new_data.get("ace")) or
            not float_equal(existing.get("confidence"), new_data.get("confidence")) or
            not float_equal(existing.get("auto_raw"), new_data.get("auto_raw")) or
            not float_equal(existing.get("teleop_raw"), new_data.get("teleop_raw")) or
            not float_equal(existing.get("endgame_raw"), new_data.get("endgame_raw")) or
            existing.get("wins", 0) != new_data.get("wins", 0) or
            existing.get("losses", 0) != new_data.get("losses", 0) or
            existing.get("ties", 0) != new_data.get("ties", 0) or
            False
        ):
            return True
        
        # Compare event_perf
        existing_event_perf = {p.get("event_key"): p for p in existing.get("event_perf", [])}
        new_event_perf = {p.get("event_key"): p for p in new_data.get("event_perf", [])}
        
        if set(existing_event_perf.keys()) != set(new_event_perf.keys()):
            return True
        
        for event_key, new_epa in new_event_perf.items():
            if event_key not in existing_event_perf:
                return True
            
            existing_epa = existing_event_perf[event_key]
            if (
                not float_equal(existing_epa.get("raw", 0), new_epa.get("raw", 0)) or
                not float_equal(existing_epa.get("confidence", 0), new_epa.get("confidence", 0)) or
                existing_epa.get("match_count", 0) != new_epa.get("match_count", 0)
            ):
                return True
        
        return False
    
    return True  # Default to updating if we don't know

def create_event_db(year):
    # Create and populate the events database for the specified year, only updating what's changed
    print(f"\nevents database update for {year}...")
    
    try:
        events = tba_get(f"events/{year}")
    except Exception as e:
        print(f"Failed to load events for {year}: {e}")
        return
    
    events_to_process = []
    events_skipped = 0
    events_skipped_future = 0
    try:
        is_historical = int(year) < datetime.now().year
    except Exception:
        is_historical = False
    
    print(f"Checking {len(events)} events for updates...")
    
    for event in events:
        if shutdown_event.is_set():
            print("Shutdown requested, stopping event processing...")
            return
            
        event_key = event["key"]
        
        # Track future events for logging, but DO process them so team schedules and
        # event_teams stay up-to-date when teams add new events to their schedule.
        # Future events will have empty matches/rankings/awards until they start.
        start_date = event.get("start_date")
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                if start_date_obj > datetime.now(timezone.utc).date():
                    events_skipped_future += 1
            except Exception:
                pass

        # Get existing data for comparison
        existing_data = get_existing_event_data(event_key)
        
        # Check if event needs updating
        if not existing_data["event"]:
            # New event, needs full processing
            events_to_process.append(event)
            continue
        
        # Process event (we need to fetch matches for match_cache even if event ended -
        # teams need match_cache for EPA calculation)
        events_to_process.append(event)

    print(f"Processing {len(events_to_process)} events (including {events_skipped_future} future events for team schedules)")
    print(f"DEBUG: Events to process: {[e['key'] for e in events_to_process[:5]]}")  # Show first 5 event keys

    def fetch_and_compare(event):
        if shutdown_event.is_set():
            return None
            
        key = event["key"]
        existing_data = get_existing_event_data(key)
        
        # Fetch new data
        event_start = event.get("start_date")
        event_end = event.get("end_date")
        event_week = get_event_week_number(event_start, event_end, key)
        new_data = {
            "event": (
                key, event.get("name"),
                event_start, event_end,
                event.get("event_type_string"),
                (event.get("district") or {}).get("key"),
                (event.get("district") or {}).get("abbreviation"),
                (event.get("district") or {}).get("display_name"),
                event.get("city"), event.get("state_prov"), event.get("country"),
                event.get("website"),
                # Webcast info (store first webcast if available)
                (event.get("webcasts", [{}]) or [{}])[0].get("type"),
                (event.get("webcasts", [{}]) or [{}])[0].get("channel"),
                event_week
            ),
            "teams": [], "matches": []
        }
        
        # Fetch teams once
        try:
            teams = tba_get(f"event/{key}/teams")
            if not teams:
                print(f"DEBUG: No teams found for event {key} - continuing with event data only")
                # Don't return None - continue processing the event even without teams
            else:
                for t in teams:
                    team_number = t.get("team_number")
                    if team_number is None:
                        print(f"DEBUG: Skipping team with null team_number in event {key}: {t.get('nickname', 'Unknown')}")
                        continue
                    new_data["teams"].append((
                        key,
                        team_number,
                        t.get("nickname"),
                        t.get("city"),
                        t.get("state_prov"),
                        t.get("country")
                    ))
        except Exception as e:
            print(f"DEBUG: Error processing teams for event {key}: {e}")
            # Don't return None on team fetch error - continue with event data

        
        # Fetch matches
        try:
            matches = tba_get(f"event/{key}/matches")
            if matches:
                # Store raw matches in cache for team processing
                match_cache[key] = matches
                for m in matches:
                    red_teams = []
                    blue_teams = []

                    for team_key in m["alliances"]["red"]["team_keys"]:
                        red_teams.append(str(int(team_key[3:].rstrip("B"))))
                    for team_key in m["alliances"]["blue"]["team_keys"]:
                        blue_teams.append(str(int(team_key[3:].rstrip("B"))))
                    
                    # Get first YouTube video if available
                    videos = m.get("videos", [])
                    youtube_videos = [v for v in videos if v.get("type") == "youtube"]
                    best_video = youtube_videos[0]["key"] if youtube_videos else None
                    
                    new_data["matches"].append((
                        m["key"], key, m["comp_level"], m["match_number"],
                        m["set_number"],
                        ",".join(red_teams),
                        ",".join(blue_teams),
                        m["alliances"]["red"]["score"], m["alliances"]["blue"]["score"],
                        m.get("winning_alliance"),
                        best_video,
                        m.get("predicted_time")
                    ))
        except Exception as e:
            print(f"Error fetching matches for event {key}: {e}")
        
        # Determine what needs updating
        updates_needed = {
            "event": data_has_changed(existing_data, new_data, "event"),
            "teams": data_has_changed(existing_data, new_data, "teams"),
            "matches": data_has_changed(existing_data, new_data, "matches"),
        }
        
        return {
            "event_key": key,
            "data": new_data,
            "updates_needed": updates_needed,
            "has_changes": any(updates_needed.values())
        }

    all_results = []
    executor = None
    try:
        executor = ThreadPoolExecutor(max_workers=10)
        active_executors.append(executor)
        
        futures = [executor.submit(fetch_and_compare, ev) for ev in events_to_process]
        for f in tqdm(as_completed(futures), total=len(events_to_process), desc=f"Analyzing {year} events"):
            if shutdown_event.is_set():
                print("Shutdown requested, stopping analysis...")
                break
                
            try:
                result = f.result()
                if result:
                    all_results.append(result)
                    print(f"DEBUG: Successfully processed event {result.get('event_key', 'unknown')}")
                else:
                    print(f"DEBUG: Event processing returned None")
            except Exception as e:
                print(f"DEBUG: Error processing event: {e}")
    finally:
        if executor:
            cleanup_executor(executor)
            if executor in active_executors:
                active_executors.remove(executor)

    if shutdown_event.is_set():
        print("Shutdown requested, stopping event database update...")
        return

    # Count what needs updating
    total_events = len(all_results)
    events_with_changes = sum(1 for r in all_results if r["has_changes"])
    event_updates = sum(1 for r in all_results if r["updates_needed"]["event"])
    team_updates = sum(1 for r in all_results if r["updates_needed"]["teams"])
    match_updates = sum(1 for r in all_results if r["updates_needed"]["matches"])
    
    print(f"\n Update Summary for {year}:")
    print(f"  Total events processed: {total_events}")
    print(f"  Events with changes: {events_with_changes}")
    print(f"  Event data updates: {event_updates}")
    print(f"  Team data updates: {team_updates}")
    print(f"  Match updates: {match_updates}")

    # Only update what's changed
    if events_with_changes > 0:
        insert_event_data(all_results, year)
        print(f"\n{year} events update complete")
    else:
        print(f"\nNo updates needed for {year} events")

def insert_event_data(results, year):
    # Insert only the changed data into PostgreSQL
    conn = get_pg_connection()
    cur = conn.cursor()
    
    for result in tqdm(results, desc="Updating changed data"):
        if not result["has_changes"]:
            continue
            
        data = result["data"]
        updates = result["updates_needed"]
        
        # Update event if needed
        if updates["event"]:
            ev = data["event"]
            upsert_district(cur, ev[4], ev[5], ev[6])
            cur.execute("""
                INSERT INTO events (
                    event_key, name, start_date, end_date, event_type,
                    district_key, district_abbrev, district_name,
                    city, state_prov, country, website, webcast_type, webcast_channel, week
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    event_type = EXCLUDED.event_type,
                    district_key = EXCLUDED.district_key,
                    district_abbrev = EXCLUDED.district_abbrev,
                    district_name = EXCLUDED.district_name,
                    city = EXCLUDED.city,
                    state_prov = EXCLUDED.state_prov,
                    country = EXCLUDED.country,
                    website = EXCLUDED.website,
                    webcast_type = EXCLUDED.webcast_type,
                    webcast_channel = EXCLUDED.webcast_channel,
                    week = EXCLUDED.week
            """, data["event"])
        
        # Update teams if needed
        if updates["teams"] and data["teams"]:
            # Filter out teams with null team_number before inserting
            valid_teams = [team for team in data["teams"] if team[1] is not None]
            if not valid_teams:
                print(f"WARNING: No valid teams (with team_number) for event {data['event'][0]}")
            else:
                # Delete existing teams for this event and reinsert
                cur.execute("DELETE FROM event_teams WHERE event_key = %s", (data["event"][0],))
                cur.executemany("""
                    INSERT INTO event_teams (event_key, team_number, nickname, city, state_prov, country)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, valid_teams)
        
        # Update matches if needed
        if updates["matches"] and data["matches"]:
            # DELETE + INSERT would drop red_win_prob / blue_win_prob (defaults NULL). Preserve
            # per match_key so scores/TBA refreshes do not wipe predictions until
            # calculate_and_store_match_predictions runs (or if a run times out early).
            event_key = data["event"][0]
            cur.execute(
                """
                SELECT match_key, red_win_prob, blue_win_prob
                FROM event_matches
                WHERE event_key = %s
                """,
                (event_key,),
            )
            preserved_probs = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
            cur.execute("DELETE FROM event_matches WHERE event_key = %s", (event_key,))
            rows_with_probs = [
                row + preserved_probs.get(row[0], (None, None)) for row in data["matches"]
            ]
            cur.executemany(
                """
                INSERT INTO event_matches (
                    match_key, event_key, comp_level, match_number, set_number,
                    red_teams, blue_teams, red_score, blue_score, winning_alliance,
                    youtube_key, predicted_time, red_win_prob, blue_win_prob
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows_with_probs,
            )
    
    conn.commit()
    cur.close()
    conn.close()


def fetch_and_store_team_data(year):
    """
    Fetch and store team EPA data. Uses a Postgres advisory lock so only one pipeline
    runs at a time across scheduler one-off dynos; if another run holds the lock, exit.
    """
    lock_conn = get_pg_connection()
    cur = lock_conn.cursor()
    cur.execute(
        "SELECT pg_try_advisory_lock(%s, %s)",
        (_PIPELINE_ADV_LOCK_KEY1, _PIPELINE_ADV_LOCK_KEY2),
    )
    locked = bool(cur.fetchone()[0])
    cur.close()
    if not locked:
        if lock_conn in active_connections:
            active_connections.remove(lock_conn)
        lock_conn.close()
        print(
            "[pipeline] Another EPA pipeline run is in progress; exiting so schedulers "
            "do not overlap (increase interval or shorten the job if this happens often).",
            flush=True,
        )
        return

    try:
        _fetch_and_store_team_data_impl(year)
    finally:
        _release_pipeline_lock(lock_conn)


def _fetch_and_store_team_data_impl(year):
    # Fetch and store team data, only updating what's changed
    global match_cache
    match_cache.clear()  # Clear cache for new year
    create_event_db(year)
    
    if shutdown_event.is_set():
        print("Shutdown requested, stopping team data processing...")
        return
        
    print(f"\nProcessing year {year} teams...")

    # Get all teams directly from PostgreSQL
    all_teams = get_teams_for_year(year)
    print(f"Total unique teams found from events: {len(all_teams)}")

    def fetch_and_compare_team(team):
        if shutdown_event.is_set():
            return None
        
        team_number = team["team_number"]
        
        # Get existing ACEdata for comparison
        existing_epa = get_existing_team_epa(team_number, year)
        
        # Fetch new EPA data
        try:
            new_epa_data = fetch_team_components(team, year)
        except Exception as e:
            print(f"FATAL ERROR in fetch_team_components for team {team_number}: {e}")
            traceback.print_exc()
            print(f"Locals: {locals()}")
            return None
        
        if not new_epa_data:
            return None
        
        # Always upsert team profile data
        upsert_team_profile(new_epa_data)

        # Check if EPA data has changed
        if not data_has_changed(existing_epa, new_epa_data, "team_epa"):
            return {"team_number": team_number, "updated": False, "reason": "No changes"}
        
        return {"team_number": team_number, "updated": True, "data": new_epa_data}

    updated_count = 0
    skipped_count = 0
    failed_teams = []
    executor = None
    
    try:
        executor = ThreadPoolExecutor(max_workers=10)
        active_executors.append(executor)
        
        futures = [executor.submit(fetch_and_compare_team, team) for team in all_teams]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Analyzing team changes"):
            if shutdown_event.is_set():
                print("Shutdown requested, stopping team analysis...")
                break
                
            try:
                result = future.result()
                if result is None:
                    failed_teams.append("Unknown team (result was None)")
                elif result["updated"]:
                    # Insert updated team EPA data
                    insert_team_epa(result["data"], year)
                    updated_count += 1
                else:
                    skipped_count += 1
                    
                if (updated_count + skipped_count) % 100 == 0:
                    print(f"Processed {updated_count + skipped_count} teams (updated: {updated_count}, skipped: {skipped_count})...")
                    
            except Exception as e:
                team_info = "Unknown team"
                try:
                    if hasattr(future, '_args') and future._args:
                        team_info = f"Team {future._args[0].get('team_number', 'Unknown')}"
                except Exception:
                    pass  # Keep team_info as "Unknown team"
                failed_teams.append(f"{team_info}: {str(e)}")
                print(f"Failed to process {team_info}: {e}")
                continue
    finally:
        if executor:
            cleanup_executor(executor)
            if executor in active_executors:
                active_executors.remove(executor)
    
    if shutdown_event.is_set():
        print("Shutdown requested, stopping team data update...")
        return

    if not shutdown_event.is_set():
        try:
            compute_and_store_team_epa_ranks(year)
        except Exception as e:
            print(f"Failed to compute/store team ACE ranks for {year}: {e}")
            traceback.print_exc()
    
    print(f"\nTeam Update Summary for {year}:")
    print(f"  Total teams processed: {len(all_teams)}")
    print(f"  Teams updated: {updated_count}")
    print(f"  Teams skipped (no changes): {skipped_count}")
    print(f"  Teams failed: {len(failed_teams)}")
    
    if failed_teams:
        print(f"Failed to process {len(failed_teams)} teams:")
        for failed in failed_teams[:10]:
            print(f"  - {failed}")
        if len(failed_teams) > 10:
            print(f"  ... and {len(failed_teams) - 10} more")

    # Calculate and store match predictions after team EPAs are up to date
    if not shutdown_event.is_set():
        try:
            calculate_and_store_match_predictions(year)
        except Exception as e:
            print(f"Failed to calculate match predictions for {year}: {e}")
        finally:
            restart_heroku_app()

def get_team_experience(team_number: int, up_to_year: int) -> int:
    # Determine how many years a team has competed up to and including up_to_year.
    try:
        return get_team_experience_pg(team_number, up_to_year)
    except Exception as e:
        print(f"Failed to get team experience: {e}")
        return 1  # Default to first year if we can't determine

def get_veteran_boost(years: int) -> float:
    # Calculate veteran boost based on years of experience.
    if years <= 1:
        return 0.2
    elif years == 2:
        return 0.4
    elif years == 3:
        return 0.6
    elif years == 5:
        return 0.8
    else:
        return 1.0

def calculate_confidence(consistency: float, dominance: float, event_boost: float, team_number: int, wins: int = 0, losses: int = 0, year: int = None) -> tuple[float, float, float]:
    # Calculate confidence score using universal parameters.
    years = get_team_experience(team_number, year) if year is not None else get_team_experience(team_number, 2025)
    veteran_boost = get_veteran_boost(years)
    
    # Calculate record alignment based on win-loss record
    total_matches = wins + losses
    if total_matches > 0:
        win_rate = wins / total_matches
        # Scale win rate to be between 0.5 and 1.0
        # 0% win rate = 0.5, 50% win rate = 0.75, 100% win rate = 1.0
        record_alignment = 0.5 + (win_rate * 0.5)
    else:
        record_alignment = 0.5  # Default to lower value if no matches
    
    raw_confidence = (
        CONFIDENCE_WEIGHTS["consistency"] * consistency +
        CONFIDENCE_WEIGHTS["dominance"] * dominance +
        CONFIDENCE_WEIGHTS["record_alignment"] * record_alignment +
        CONFIDENCE_WEIGHTS["veteran"] * veteran_boost +
        CONFIDENCE_WEIGHTS["events"] * event_boost
    )
    
    # Apply non-linear scaling
    if raw_confidence > CONFIDENCE_THRESHOLDS["high"]:
        raw_confidence = CONFIDENCE_THRESHOLDS["high"] + (raw_confidence - CONFIDENCE_THRESHOLDS["high"]) * CONFIDENCE_MULTIPLIERS["high_boost"]
    elif raw_confidence < CONFIDENCE_THRESHOLDS["low"]:
        raw_confidence = raw_confidence * CONFIDENCE_MULTIPLIERS["low_reduction"]
    
    capped_confidence = max(0.0, min(1.0, raw_confidence))
    return raw_confidence, capped_confidence, record_alignment

def _effective_epa(team_infos: List[Dict]) -> float:
    if not team_infos:
        return 0.0
    weighted_epas = []
    for t in team_infos:
        epa = t.get("ace", 0) or 0
        conf = t.get("confidence", 0) or 0
        reliability = 1.0 * conf
        weighted_epas.append(epa * reliability)
    return float(sum(weighted_epas) / len(weighted_epas)) if weighted_epas else 0.0

def predict_win_probability(red_info: List[Dict], blue_info: List[Dict]) -> tuple[float, float]:
    red_eff = _effective_epa(red_info)
    blue_eff = _effective_epa(blue_info)
    all_infos = (red_info or []) + (blue_info or [])
    reliability = float(sum(t.get("confidence", 0) or 0 for t in all_infos) / len(all_infos)) if all_infos else 0.0

    if red_eff + blue_eff == 0:
        return 0.5, 0.5

    diff = red_eff - blue_eff
    scale = (0.06 + 0.3 * (1 - reliability))
    p_red = 1 / (1 + math.exp(-scale * diff))
    p_red = max(0.02, min(0.98, p_red))
    return p_red, 1 - p_red

def _load_team_prediction_lookup(year: int) -> Dict[int, Dict[str, float]]:
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT team_number, ace, confidence
            FROM team_epas
            WHERE year = %s
            """,
            (year,),
        )
        return {row[0]: {"ace": row[1] or 0.0, "confidence": row[2] or 0.0} for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

def _team_prediction_info(team_number: int, current_year_lookup: Dict[int, Dict[str, float]], prev_year_lookup: Dict[int, Dict[str, float]]) -> Dict[str, float]:
    data = current_year_lookup.get(team_number)
    if data and data.get("ace", 0):
        return data
    data = prev_year_lookup.get(team_number)
    if data and data.get("ace", 0):
        return data
    return {"ace": 0.0, "confidence": 0.7}


def _parse_match_alliance_teams(team_csv) -> List[int]:
    """
    Parse red_teams / blue_teams from event_matches (comma-separated).
    Matches TBA ingest: numeric strings; tolerate leading 'frc' and trailing 'B' surrogate markers.
    """
    if team_csv is None:
        return []
    out: List[int] = []
    for raw in str(team_csv).split(","):
        tok = raw.strip()
        if not tok:
            continue
        low = tok.lower()
        if low.startswith("frc"):
            tok = tok[3:]
        tok = tok.rstrip("Bb")
        if not tok.isdigit():
            continue
        try:
            out.append(int(tok))
        except ValueError:
            continue
    return out


def calculate_and_store_match_predictions(year: int):
    if shutdown_event.is_set():
        return

    current_lookup = _load_team_prediction_lookup(year)
    prev_lookup = _load_team_prediction_lookup(year - 1)

    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT match_key, red_teams, blue_teams
            FROM event_matches
            WHERE LEFT(event_key, 4) = %s
            """,
            (str(year),),
        )
        match_rows = cur.fetchall()

        updates = []
        skipped_no_teams = 0
        skipped_bad_prob = 0
        for match_key, red_teams, blue_teams in match_rows:
            red_list = _parse_match_alliance_teams(red_teams)
            blue_list = _parse_match_alliance_teams(blue_teams)
            if not red_list or not blue_list:
                # Do not UPDATE with NULL — preserves existing probs if alliances were briefly empty/malformed.
                skipped_no_teams += 1
                continue

            red_info = [
                _team_prediction_info(t, current_lookup, prev_lookup) for t in red_list
            ]
            blue_info = [
                _team_prediction_info(t, current_lookup, prev_lookup) for t in blue_list
            ]

            p_red, p_blue = predict_win_probability(red_info, blue_info)
            if not math.isfinite(p_red) or not math.isfinite(p_blue):
                skipped_bad_prob += 1
                continue
            updates.append((p_red, p_blue, match_key))

        if updates:
            # COALESCE: never overwrite existing non-NULL probs with NULL (defense in depth).
            # Rows we skip above are not in `updates`, so good predictions stay untouched.
            cur.executemany(
                """
                UPDATE event_matches
                SET red_win_prob = COALESCE(%s::double precision, red_win_prob),
                    blue_win_prob = COALESCE(%s::double precision, blue_win_prob)
                WHERE match_key = %s
                """,
                updates,
            )
        conn.commit()
        msg = f"Stored match predictions for {len(updates)} matches in {year}."
        if skipped_no_teams or skipped_bad_prob:
            msg += f" (skipped: {skipped_no_teams} missing alliances, {skipped_bad_prob} non-finite probs)"
        print(msg)
    finally:
        cur.close()
        conn.close()

def calculate_event_epa(matches: List[Dict], team_key: str, team_number: int) -> Dict:
    try:
        # --- BEGIN FUNCTION BODY ---
        importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
        matches = sorted(matches, key=lambda m: m.get("time") or 0)

        # DEBUG: Print team and year
        if matches:
            print(f"EPA DEBUG: Processing team {team_key} for year {matches[0]['event_key'][:4]}")
        else:
            print(f"EPA DEBUG: Processing team {team_key} (no matches)")

        match_count = 0
        overall_epa = 0.0
        auto_epa = 0.0
        teleop_epa = 0.0
        endgame_epa = 0.0
        contributions, teammate_epas = [], []
        breakdowns = []
        dominance_scores = []
        event_wins = 0
        event_losses = 0
        event_ties = 0  # Add tie counter

        # Get the year from the first match's event key
        year = matches[0]["event_key"][:4] if matches else "2025"
        try:
            year_int = int(year)
        except Exception:
            year_int = 2025

        # Get the appropriate scoring functions for this year
        try:
            auto_func = globals()[f"auto_{year}"]
            teleop_func = globals()[f"teleop_{year}"]
            endgame_func = globals()[f"endgame_{year}"]
        except KeyError:
            auto_func = auto_2025
            teleop_func = teleop_2025
            endgame_func = endgame_2025

        early_match_target = 5
        early_weight_floor = 0.75  # Don't over-decay early matches; they may show true performance

        for match in matches:
            if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                continue

            red_score = match["alliances"]["red"]["score"]
            blue_score = match["alliances"]["blue"]["score"]
            winning_alliance = match.get("winning_alliance")

            # Unplayed matches are typically 0-0 with no winning alliance.
            # Skip them entirely so they do not inflate match_count or tie count.
            if red_score == 0 and blue_score == 0 and winning_alliance not in ("red", "blue"):
                continue

            match_count += 1
            early_weight = max(early_weight_floor, min(1.0, match_count / early_match_target)) if match_count > 0 else early_weight_floor
            alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
            opponent_alliance = "blue" if alliance == "red" else "red"

            # Track wins/losses/ties (existing logic) ...
            if year == "2015":
                if alliance == "red":
                    if red_score > blue_score:
                        event_wins += 1
                    elif red_score < blue_score:
                        event_losses += 1
                    else:
                        event_ties += 1
                else:
                    if blue_score > red_score:
                        event_wins += 1
                    elif blue_score < red_score:
                        event_losses += 1
                    else:
                        event_ties += 1
            else:
                # Determine win/loss/tie based on scores instead of winning_alliance
                # Handle disqualifications (score of 0) as ties
                if red_score == 0 or blue_score == 0:
                    event_ties += 1
                elif alliance == "red":
                    if red_score > blue_score:
                        event_wins += 1
                    elif red_score < blue_score:
                        event_losses += 1
                    else:  # Equal scores = tie
                        event_ties += 1
                else:  # alliance == "blue"
                    if blue_score > red_score:
                        event_wins += 1
                    elif blue_score < red_score:
                        event_losses += 1
                    else:  # Equal scores = tie
                        event_ties += 1

            team_keys = match["alliances"][alliance].get("team_keys", [])
            team_count = len(team_keys)
            index = team_keys.index(team_key) + 1

            breakdown = match.get("score_breakdown")
            legacy_year = 1992 <= year_int <= 2014

            # --- Legacy years: use alliance score ---
            if legacy_year:
                auto = 0
                endgame = 0
                scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
                teleop = match["alliances"][alliance]["score"] * scaling_factor if team_count else 0
                actual_overall = teleop
                opponent_score = match["alliances"][opponent_alliance]["score"] * scaling_factor if team_count else 0
                margin = actual_overall - opponent_score
                scaled_margin = margin / (opponent_score + 1e-6)
                norm_margin = (scaled_margin + 1) / 1.3
                dominance_scores.append(min(1.0, max(0.0, norm_margin)))
                # Robust fallback: set to 0.0 if any are None
                if auto_epa is None or teleop_epa is None or endgame_epa is None:
                    print(f"EPA DEBUG: NoneType EPA before math in match {match.get('key', 'unknown')}: auto_epa={auto_epa}, teleop_epa={teleop_epa}, endgame_epa={endgame_epa}, teleop={teleop}")
                if auto_epa is None:
                    auto_epa = 0.0
                if teleop_epa is None:
                    teleop_epa = 0.0
                if endgame_epa is None:
                    endgame_epa = 0.0
                if overall_epa == 0.0 and auto_epa == 0.0 and teleop_epa == 0.0 and endgame_epa == 0.0:
                    overall_epa = actual_overall * early_weight
                    auto_epa = auto * early_weight
                    endgame_epa = endgame * early_weight
                    teleop_epa = teleop * early_weight
                    continue
                K = 0.4 * early_weight
                if teleop_epa > 10 and teleop > teleop_epa * 1.4:
                    K *= 0.5
                # Fallback: always ensure teleop_epa is a float
                try:
                    delta_teleop = K * (teleop - teleop_epa)
                except Exception as e:
                    print(f"EPA DEBUG ERROR: teleop={teleop}, teleop_epa={teleop_epa}, match={match.get('key', 'unknown')}, error={e}")
                    teleop_epa = 0.0
                    delta_teleop = K * (teleop - teleop_epa)
                teleop_epa += delta_teleop
                overall_epa = teleop_epa
                contributions.append(actual_overall)
                continue

            # --- Modern years: use breakdown as before ---
            # (existing breakdown logic)
            # Safely get and validate breakdown
            if isinstance(breakdown, str):
                try:
                    breakdown = json.loads(breakdown)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse breakdown JSON for match {match.get('key', 'unknown')}")
                    continue
            if not isinstance(breakdown, dict):
                print(f"Warning: Invalid breakdown format for match {match.get('key', 'unknown')}: {type(breakdown)}")
                continue
            alliance_breakdown = breakdown.get(alliance, {})
            if not isinstance(alliance_breakdown, dict):
                print(f"Warning: Invalid alliance breakdown format for match {match.get('key', 'unknown')}: {type(alliance_breakdown)}")
                continue
            breakdowns.append(alliance_breakdown)
            # Robust fallback for modern years
            if auto_epa is None:
                auto_epa = 0.0
            if teleop_epa is None:
                teleop_epa = 0.0
            if endgame_epa is None:
                endgame_epa = 0.0
            try:
                actual_auto = auto_func(breakdowns, team_count)
                actual_teleop = teleop_func(breakdowns, team_count)
                if year == "2023" or year == "2017" or year == "2016":
                    actual_endgame = endgame_func(breakdowns, team_count)
                else:
                    actual_endgame = endgame_func(alliance_breakdown, index)
                actual_overall = actual_auto + actual_teleop + actual_endgame
                opponent_score = match["alliances"][opponent_alliance]["score"] / team_count
                margin = actual_overall - opponent_score
                scaled_margin = margin / (opponent_score + 1e-6)
                norm_margin = (scaled_margin + 1) / 1.3
                # Scale down dominance if team was carried (contributed less than alliance average)
                alliance_total = match["alliances"][alliance]["score"] or 1
                alliance_avg = alliance_total / team_count
                contribution_share = actual_overall / (alliance_avg + 1e-6)
                adjustment = min(1.0, contribution_share)
                norm_margin = norm_margin * adjustment
                dominance_scores.append(min(1.0, max(0.0, norm_margin)))
                match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
                decay = early_weight
                if overall_epa == 0.0 and auto_epa == 0.0 and teleop_epa == 0.0 and endgame_epa == 0.0:
                    overall_epa = actual_overall * early_weight
                    auto_epa = actual_auto * early_weight
                    endgame_epa = actual_endgame * early_weight
                    teleop_epa = actual_teleop * early_weight
                    continue
                K = 0.4
                K *= match_importance * decay
                # Dampen large positive surprises (possible carried matches) - don't let a few spikes overestimate
                if overall_epa > 10 and actual_overall > overall_epa * 1.4:
                    K *= 0.5
                delta_auto = K * (actual_auto - auto_epa)
                delta_teleop = K * (actual_teleop - teleop_epa)
                delta_endgame = K * (actual_endgame - endgame_epa)
                auto_epa += delta_auto
                teleop_epa += delta_teleop
                endgame_epa += delta_endgame
                overall_epa = auto_epa + teleop_epa + endgame_epa
                contributions.append(actual_overall)
            except Exception as e:
                print(f"EPA DEBUG ERROR: Modern block, match={match.get('key', 'unknown')}, error={e}")

        if not match_count:
            return {
                "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
                "confidence": 0.0, "ace": 0.0,
                "match_count": 0, "raw_confidence": 0.0,
                "consistency": 0.0, "dominance": 0.0,
                "event_boost": 0.0, "veteran_boost": 0.0,
                "years_experience": 0, "weights": {}, "record_alignment": 0.0,
                "wins": 0, "losses": 0, "ties": 0
            }

        if len(contributions) >= 2:
            peak = max(contributions)
            stdev = statistics.stdev(contributions)
            consistency = max(0.0, 1.0 - stdev / (peak + 1e-6))
        else:
            consistency = 0.7

        dominance = min(1., statistics.mean(dominance_scores)) if dominance_scores else 0.0

        # Get total number of played events for this team
        played_event_keys = get_team_played_events(team_number, int(year))
        total_events = len(played_event_keys)

        # Calculate event boost based on number of played events
        event_boost = EVENT_BOOSTS.get(min(total_events, 3), EVENT_BOOSTS[3])
        
        # Calculate confidence using universal function
        raw_confidence, confidence, record_alignment = calculate_confidence(consistency, dominance, event_boost, team_number, event_wins, event_losses, int(year))
        actual_epa = (overall_epa * confidence) if overall_epa is not None else 0.0

        # Get years of experience for display
        years = get_team_experience(team_number, int(year))
        veteran_boost = get_veteran_boost(years)

        return {
            "raw": round(overall_epa, 2) if overall_epa is not None else 0.0,
            "auto_raw": round(auto_epa, 2) if auto_epa is not None else 0.0,
            "teleop_raw": round(teleop_epa, 2) if teleop_epa is not None else 0.0,
            "endgame_raw": round(endgame_epa, 2) if endgame_epa is not None else 0.0,
            "confidence": round(confidence, 2),
            "ace": round(actual_epa, 2),
            "match_count": match_count,
            "raw_confidence": raw_confidence,
            "consistency": consistency,
            "dominance": dominance,
            "event_boost": event_boost,
            "veteran_boost": veteran_boost,
            "years_experience": years,
            "weights": CONFIDENCE_WEIGHTS,
            "record_alignment": record_alignment,
            "wins": event_wins,
            "losses": event_losses,
            "ties": event_ties
        }
    except Exception as e:
        print(f"EPA FATAL ERROR for team {team_key}: {e}")
        traceback.print_exc()
        print(f"Locals: {locals()}")
        return {
            "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
            "confidence": 0.0, "ace": 0.0,
            "match_count": 0, "raw_confidence": 0.0,
            "consistency": 0.0, "dominance": 0.0,
            "event_boost": 0.0, "veteran_boost": 0.0,
            "years_experience": 0, "weights": {}, "record_alignment": 0.0,
            "wins": 0, "losses": 0, "ties": 0
        }

def get_event_chronological_weight(event_key: str, year: int) -> tuple[float, str]:
    # Calculate chronological weight for an event based on its timing in the season
    try:
        # Load week ranges for the year
        week_ranges = load_week_ranges()
        if not week_ranges:
            return 1.0, 'unknown'
        
        year_str = str(year)
        if year_str not in week_ranges:
            return 1.0, 'unknown'
        
        # Get event start date from database instead of API
        conn = get_pg_connection()
        cur = conn.cursor()
        cur.execute("SELECT start_date, event_type FROM events WHERE event_key = %s", (event_key,))
        event_row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not event_row or not event_row[0]:  # start_date is None or empty
            return 1.0, 'unknown'
        
        event_start = datetime.strptime(event_row[0], '%Y-%m-%d')
        
        # Pre-season events (before first regular week)
        first_regular_week = datetime.strptime(week_ranges[year_str][0][0], '%Y-%m-%d')
        if event_start < first_regular_week:
            return 0.05, 'preseason'  # Minimal weight for pre-season
        
        # Off-season events (after last regular week)
        last_regular_week = datetime.strptime(week_ranges[year_str][-1][1], '%Y-%m-%d')
        if event_start > last_regular_week:
            return 0.1, 'offseason'  # Very minimal weight for off-season
        
        # Regular season events - calculate position within season
        season_start = first_regular_week
        season_end = last_regular_week
        season_duration = (season_end - season_start).days
        
        if season_duration <= 0:
            return 1.0, 'regular'
        
        # Calculate how far into the season this event is (0.0 to 1.0)
        days_into_season = (event_start - season_start).days
        season_progress = max(0.0, min(1.0, days_into_season / season_duration))
        
        # Apply enhanced chronological weighting curve
        # Early events (first 20% of season): 0.2-0.4 weight (more aggressive penalty)
        # Mid events (20-80% of season): 0.4-0.8 weight (gradual improvement)
        # Late events (last 20% of season): 0.8-1.0 weight (full recognition)
        if season_progress <= 0.2:
            # Early season: linear from 0.2 to 0.4 (more aggressive penalty)
            weight = 0.2 + (season_progress / 0.2) * 0.2
        elif season_progress <= 0.8:
            # Mid season: linear from 0.4 to 0.8 (gradual improvement)
            weight = 0.4 + ((season_progress - 0.2) / 0.6) * 0.4
        else:
            # Late season: linear from 0.8 to 1.0 (full recognition)
            weight = 0.8 + ((season_progress - 0.8) / 0.2) * 0.2
        
        return round(weight, 3), 'regular'
        
    except Exception as e:
        print(f"Error calculating chronological weight for {event_key}: {e}")
        return 1.0, 'unknown'

def get_event_start_date_from_db(event_key: str) -> str:
    """Get event start date from database instead of making API call."""
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
        cur.execute("SELECT start_date FROM events WHERE event_key = %s", (event_key,))
        event_row = cur.fetchone()
        cur.close()
        conn.close()
        
        if event_row and event_row[0]:
            return event_row[0]
        return None
    except Exception as e:
        print(f"Error getting start date for {event_key}: {e}")
        return None

def sort_events_chronologically(event_epas: List[Dict], year: int) -> List[Dict]:
    # Sort events chronologically and add timing information
    for event_epa in event_epas:
        event_key = event_epa.get('event_key', '')
        if event_key:
            weight, event_type = get_event_chronological_weight(event_key, year)
            event_epa['chronological_weight'] = weight
            event_epa['event_type'] = event_type
            event_epa['event_start_date'] = None
            
            # Get event start date from database instead of API
            event_epa['event_start_date'] = get_event_start_date_from_db(event_key)
    
    # Sort by start date, with events without dates at the end
    def sort_key(event_epa):
        start_date = event_epa.get('event_start_date')
        if start_date:
            return datetime.strptime(start_date, '%Y-%m-%d')
        return datetime.max  # Put events without dates at the end
    
    return sorted(event_epas, key=sort_key)

def aggregate_overall_epa(event_epas: List[Dict], year: int = None, team_number: int = None) -> Dict:
    try:
        if not event_epas:
            return {
                "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
                "confidence": 0.0, "ace": 0.0,
                "wins": 0, "losses": 0, "ties": 0
            }

        # Check if this is a demo team (9970-9999) - return zeroed overall stats
        if team_number is not None and 9970 <= team_number <= 9999:
            return {
                "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
                "confidence": 0.0, "ace": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        # Filter out events with no valid matches or zero EPAs
        valid_events = [
            epa_data for epa_data in event_epas 
            if epa_data.get("match_count", 0) > 0 and (epa_data.get("raw", 0) or 0) > 0
        ]

        if not valid_events:
            return {
                "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
                "confidence": 0.0, "ace": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        # Sort events chronologically and add timing weights if year is provided
        if year is not None:
            valid_events = sort_events_chronologically(valid_events, year)
            # Log weighting information for debugging (only for teams with multiple events)
            if len(valid_events) > 1:
                # We'll get team number from the calling function instead
                pass

        total_overall = 0.0
        total_auto = 0.0
        total_teleop = 0.0
        total_endgame = 0.0
        total_actual_epa = 0.0
        total_weighted_match_count = 0.0
        total_confidence = 0.0
        total_consistency = 0.0
        total_dominance = 0.0
        total_veteran_boost = 0.0
        total_event_boost = 0.0
        total_record_alignment = 0.0
        total_events = 0
        total_wins = 0
        total_losses = 0
        total_ties = 0

        # Use chronological weighting if available, otherwise fall back to match count weighting
        for epa_data in valid_events:
            match_count = epa_data.get("match_count", 0)
            if match_count == 0:
                continue
                
            # Get chronological weight if available
            chronological_weight = epa_data.get("chronological_weight", 1.0)
            event_type = epa_data.get("event_type", "unknown")
            
            # Calculate effective weight: chronological_weight * match_count
            effective_weight = chronological_weight * match_count
            
            # Fallback for NoneType values
            overall = epa_data.get("raw", 0.0) or 0.0
            auto = epa_data.get("auto_raw", 0.0) or 0.0
            teleop = epa_data.get("teleop_raw", 0.0) or 0.0
            endgame = epa_data.get("endgame_raw", 0.0) or 0.0
            actual_epa = epa_data.get("ace", 0.0) or 0.0
            confidence = epa_data.get("confidence", 0.0) or 0.0
            consistency = epa_data.get("consistency", 0.0) or 0.0
            dominance = epa_data.get("dominance", 0.0) or 0.0
            veteran_boost = epa_data.get("veteran_boost", 0.0) or 0.0
            event_boost = epa_data.get("event_boost", 0.0) or 0.0
            record_alignment = epa_data.get("record_alignment", 0.0) or 0.0
            wins = epa_data.get("wins", 0) or 0
            losses = epa_data.get("losses", 0) or 0
            ties = epa_data.get("ties", 0) or 0
            
            total_overall += overall * effective_weight
            total_auto += auto * effective_weight
            total_teleop += teleop * effective_weight
            total_endgame += endgame * effective_weight
            total_actual_epa += actual_epa * effective_weight
            total_weighted_match_count += effective_weight
            total_confidence += confidence * effective_weight
            total_consistency += consistency * effective_weight
            total_dominance += dominance * effective_weight
            total_veteran_boost += veteran_boost * effective_weight
            total_event_boost += event_boost * effective_weight
            total_record_alignment += record_alignment * effective_weight
            total_wins += wins
            total_losses += losses
            total_ties += ties
            total_events += 1

        if total_weighted_match_count == 0:
            return {
                "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
                "confidence": 0.0, "ace": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        avg_confidence = total_confidence / total_weighted_match_count
        avg_consistency = total_consistency / total_weighted_match_count
        avg_dominance = total_dominance / total_weighted_match_count
        avg_veteran_boost = total_veteran_boost / total_weighted_match_count
        avg_event_boost = total_event_boost / total_weighted_match_count
        avg_record_alignment = total_record_alignment / total_weighted_match_count

        # Calculate the weighted components for display
        weights = valid_events[0].get("weights", {})
        consistency_component = weights.get("consistency", 0.0) * avg_consistency
        record_component = weights.get("record_alignment", 0.0) * avg_record_alignment
        veteran_component = weights.get("veteran", 0.0) * avg_veteran_boost
        dominance_component = weights.get("dominance", 0.0) * avg_dominance
        event_component = weights.get("events", 0.0) * avg_event_boost

        # Calculate raw confidence from components
        raw_confidence = (
            consistency_component +
            record_component +
            veteran_component +
            dominance_component +
            event_component
        )

        # Apply non-linear scaling
        if 'CONFIDENCE_THRESHOLDS' in globals() and 'CONFIDENCE_MULTIPLIERS' in globals():
            if raw_confidence > CONFIDENCE_THRESHOLDS["high"]:
                raw_confidence = CONFIDENCE_THRESHOLDS["high"] + (raw_confidence - CONFIDENCE_THRESHOLDS["high"]) * CONFIDENCE_MULTIPLIERS["high_boost"]
            elif raw_confidence < CONFIDENCE_THRESHOLDS["low"]:
                raw_confidence = raw_confidence * CONFIDENCE_MULTIPLIERS["low_reduction"]
        final_confidence = max(0.0, min(1.0, raw_confidence))

        return {
            "raw": round(total_overall / total_weighted_match_count, 2),
            "auto_raw": round(total_auto / total_weighted_match_count, 2),
            "teleop_raw": round(total_teleop / total_weighted_match_count, 2),
            "endgame_raw": round(total_endgame / total_weighted_match_count, 2),
            "confidence": round(final_confidence, 2),
            "ace": round((total_overall / total_weighted_match_count) * final_confidence, 2),
            "wins": total_wins,
            "losses": total_losses,
            "ties": total_ties,
            "avg_consistency": avg_consistency,
            "avg_dominance": avg_dominance,
            "avg_veteran_boost": avg_veteran_boost,
            "avg_event_boost": avg_event_boost,
            "avg_record_alignment": avg_record_alignment,
            "total_events": total_events,
            "confidence_components": {
                "consistency": consistency_component,
                "record": record_component,
                "veteran": veteran_component,
                "dominance": dominance_component,
                "event": event_component,
                "raw": raw_confidence
            }
        }
    except Exception as e:
        print(f"FATAL ERROR in aggregate_overall_epa: {e}")
        traceback.print_exc()
        print(f"Locals: {locals()}")
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0, "ties": 0,
            "confidence_components": {
                "consistency": 0.0,
                "record": 0.0,
                "veteran": 0.0,
                "dominance": 0.0,
                "event": 0.0,
                "raw": 0.0
            }
        }

# Retry wrapper for fetch_team_components
def retry_team_fetch(max_attempts=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"[Retry {attempt}/{max_attempts}] Error processing team: {e}")
                    if attempt == max_attempts:
                        print(f"[SKIP] Team {args[0].get('team_number', 'Unknown')} after {max_attempts} failed attempts.")
                        return None
        return wrapper
    return decorator

@retry_team_fetch(max_attempts=3)
def fetch_team_components(team, year):
    team_key = team["key"]
    team_number = team["team_number"]

    # Get team events from PostgreSQL
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    event_epa_full = []  # Keep full data for aggregation

    for event_key in event_keys:
        try:
            # Get matches from cache instead of making API call
            matches = match_cache.get(event_key, [])
            if not matches:
                continue  # Skip if no matches in cache

            # Skip events that haven't started yet (or have no meaningful scores)
            # This prevents newly added future events with scheduled matches from affecting EPA
            event_start_date = get_event_start_date_from_db(event_key)
            if not event_has_started(event_key, event_start_date):
                continue  # Exclude from event_epas and total EPA

            # Calculate EPA for this event (which includes wins/losses/ties for the event)
            event_epa = calculate_event_epa(matches, team_key, team_number)
            event_epa["event_key"] = event_key  # Ensure event_key is included
            # Keep full data for aggregation
            event_epa_full.append(event_epa)
            # Only keep essential fields for final event_perf
            simplified_event_epa = {
                "event_key": event_key,
                "raw": event_epa["raw"],
                "auto_raw": event_epa["auto_raw"],
                "teleop_raw": event_epa["teleop_raw"],
                "endgame_raw": event_epa["endgame_raw"],
                "confidence": event_epa["confidence"],
                "ace": event_epa["ace"]
            }
            event_epa_results.append(simplified_event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")
            continue

    # If there are no matches for this team in the year, fall back to previous year data
    has_matches = any(epa.get("match_count", 0) > 0 for epa in event_epa_full)
    overall_epa_data = None
    if not has_matches:
        use_prev_year_fallback = year >= datetime.now().year
        if use_prev_year_fallback:
            prev_year = year - 1
            previous_epa = get_existing_team_epa(team_number, prev_year)
            if previous_epa:
                overall_epa_data = {
                    "raw": previous_epa.get("raw", 0) or 0.0,
                    "auto_raw": previous_epa.get("auto_raw", 0) or 0.0,
                    "teleop_raw": previous_epa.get("teleop_raw", 0) or 0.0,
                    "endgame_raw": previous_epa.get("endgame_raw", 0) or 0.0,
                    "confidence": previous_epa.get("confidence", 0) or 0.0,
                    "ace": previous_epa.get("ace", 0) or 0.0,
                    "wins": 0,
                    "losses": 0,
                    "ties": 0
                }
                event_epa_results = []
            else:
                overall_epa_data = aggregate_overall_epa(event_epa_full, year, team_number)
        else:
            overall_epa_data = aggregate_overall_epa(event_epa_full, year, team_number)
    else:
        # Aggregate overall EPA from full event-specific EPAs
        # This already sums up wins, losses, and ties from each event
        overall_epa_data = aggregate_overall_epa(event_epa_full, year, team_number)

    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": team.get("website"),
        "raw": overall_epa_data.get("raw", 0),
        "confidence": overall_epa_data.get("confidence", 0),
        "ace": overall_epa_data.get("ace", 0),
        "auto_raw": overall_epa_data.get("auto_raw", 0),
        "teleop_raw": overall_epa_data.get("teleop_raw", 0),
        "endgame_raw": overall_epa_data.get("endgame_raw", 0),
        "wins": overall_epa_data.get("wins", 0),
        "losses": overall_epa_data.get("losses", 0),
        "ties": overall_epa_data.get("ties", 0),
        "event_perf": event_epa_results,
    }

# Single team analysis has been moved to single_team_analysis.py
# Import the function from the new file


def finalize():
    """Clean up executors/connections and print runtime. Call from main entry point."""
    print("\nPerforming final cleanup...")
    for executor in active_executors:
        cleanup_executor(executor)
    for conn in active_connections:
        cleanup_connection(conn)
    print("Cleanup complete.")
    elapsed = time.time() - start_time
    print(f"\nScript runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")


def main():
    print("\nEPA Calculator")
    print("="*20)
    year = input("Enter year (e.g., 2025): ").strip()
    try:
        year = int(year)
    except ValueError:
        print("Invalid year. Please enter a valid year.")
        return
    fetch_and_store_team_data(year)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            try:
                year = int(sys.argv[1])
            except ValueError:
                print("Year must be an integer.")
                sys.exit(1)
            if len(sys.argv) > 2 and sys.argv[2] == "--ranks-only":
                compute_and_store_team_epa_ranks(year)
            else:
                fetch_and_store_team_data(year)
        else:
            main()
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        finalize()
