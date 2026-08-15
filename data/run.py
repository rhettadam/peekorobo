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
from typing import Dict, List, Optional, Tuple
from functools import wraps
import signal
import sys
import threading
import time  # <-- Added for runtime tracking
import math
import traceback

from yearmodels import *
from active_events import get_active_event_keys
from ace_attribution import Method, simulate_event, TeamPhaseState
from prediction import PredictionConfig, load_prediction_data_from_db, predict_all_matches_db

start_time = time.time()

load_dotenv()

# Verbose per-team EPA trace logs; off in production to reduce log I/O and noise.
_EPA_DEBUG = os.environ.get("EPA_DEBUG", "").lower() in ("1", "true", "yes")

# ACE attribution method. residual_shrink (default) = residual obs blended toward S/n
# to limit carry-inflation / stacked-alliance suppression. Override with ACE_METHOD.
_ACE_METHOD: Method = os.environ.get("ACE_METHOD", "residual_shrink").strip().lower()  # type: ignore[assignment]
if _ACE_METHOD not in ("residual", "equal_split", "residual_shrink"):
    _ACE_METHOD = "residual_shrink"

# Blend toward equal share when using residual_shrink (0 = pure residual).
_ACE_SHRINK = float(os.environ.get("ACE_SHRINK", "0.05"))

# EMA learning rate and spike dampening (1.0 = no damp).
_ACE_K_BASE = float(os.environ.get("ACE_K_BASE", "0.4"))
_ACE_SPIKE_DAMP = float(os.environ.get("ACE_SPIKE_DAMP", "1.0"))
# Asymmetric EMA multipliers (1.0 = symmetric). Kept for experiments; production
# defaults stay symmetric after partner-cap became the elite-lift lever.
_ACE_K_UP = float(os.environ.get("ACE_K_UP", "1.0"))
_ACE_K_DOWN = float(os.environ.get("ACE_K_DOWN", "1.0"))

# Cap each partner's credited RAW at alpha * (S/n) when forming residual obs.
# 0 disables. Local #3 experiment uses 1.25; prod Neon unchanged until explicit allow.
_ACE_PARTNER_CAP = float(os.environ.get("ACE_PARTNER_CAP", "1.25"))

# Cross-event RAW prior: seed each event from season-to-date phase estimates.
_ACE_CARRY_PRIOR = os.environ.get("ACE_CARRY_PRIOR", "1").strip().lower() in ("1", "true", "yes")
_ACE_PRIOR_BLEND = float(os.environ.get("ACE_PRIOR_BLEND", "1.0"))

# Logistic scale on normalized ACE margin (pooled 2024-2026 tune: 6.4).

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = [k.strip() for k in (os.getenv("TBA_API_KEYS") or "").split(",") if k.strip()]

import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import pool as psycopg2_pool
from contextlib import contextmanager
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
# event_key -> {team_key: event_epa dict} for match-centric residual attribution
_event_epa_cache: Dict[str, Dict[str, dict]] = {}
_event_epa_lock = threading.Lock()

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

# Component-weighted sum is typically ~0.55–0.93. Divide by this ceiling so
# elite sums (~0.88+) map to ~1.0, strong teams (~0.79) land near ~0.90, and a
# mid-pack sum (~0.54) lands near ~0.60. No nonlinear high/low cut.
CONFIDENCE_CEILING = float(os.environ.get("ACE_CONFIDENCE_CEILING", "0.88"))

# Confidence "event_boost" from number of distinct played events in the season (not chronological).
EVENT_BOOSTS = {
    1: 0.75,  # Was 0.5 — single-event teams were over-penalized
    2: 0.90,
    3: 1.0,
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
    headers = {
        "X-TBA-Auth-Key": api_key,
        "User-Agent": "peekorobo-eval/1.0 (local bakeoff; contact github.com/peekorobo)",
        "Accept": "application/json",
    }
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

    # Close pooled connections used by the hot per-team/per-event helpers.
    _close_db_pool()

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
    """
    Best-effort restart of all web/worker dynos so the app reloads (clears in-memory caches).

    Not automatic: set a Platform API token on the app (or Scheduler job):
      heroku config:set HEROKU_API_KEY="$(heroku auth:token)" -a <your-app>

    HEROKU_APP_NAME is set automatically for apps running on Heroku. For local/CI runs, set it
    explicitly. Disable with RESTART_HEROKU=0.
    """
    if os.environ.get("RESTART_HEROKU", "1").strip().lower() in ("0", "false", "no", "off"):
        print("[heroku] RESTART_HEROKU=0, skipping app restart", flush=True)
        return

    app_name = (os.environ.get("HEROKU_APP_NAME") or os.environ.get("HEROKU_APP") or "").strip()
    api_key = (os.environ.get("HEROKU_API_KEY") or "").strip()

    if not api_key:
        print(
            "[heroku] HEROKU_API_KEY is not set — skipping dyno restart. "
            "Set it to a valid Heroku authorizations token so the web app reloads after this job.",
            flush=True,
        )
        return
    if not app_name:
        print(
            "[heroku] HEROKU_APP_NAME (or HEROKU_APP) is not set — skipping dyno restart.",
            flush=True,
        )
        return

    try:
        url = f"https://api.heroku.com/apps/{app_name}/dynos"
        headers = {
            "Accept": "application/vnd.heroku+json; version=3",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.delete(url, headers=headers, timeout=60)
        if response.status_code == 202:
            print(f"[heroku] Restart requested for app {app_name} (all dynos).", flush=True)
        else:
            print(
                f"[heroku] Dyno restart failed: HTTP {response.status_code} — {response.text!r}. "
                "If 401/403, ensure the token is valid and the account can manage this app.",
                flush=True,
            )
    except Exception as e:
        print(f"[heroku] Error requesting dyno restart: {e}", flush=True)

# Robust retry for DB connection (Neon pooler can cold-start / flake after heavy runs).
@retry(
    stop=stop_after_attempt(12),
    wait=wait_exponential(multiplier=1.5, min=2, max=45),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_pg_connection():
    if shutdown_event.is_set():
        raise Exception("Shutdown requested")
    kwargs, host = _connect_kwargs_from_database_url()
    try:
        conn = psycopg2.connect(**kwargs)
    except Exception as e:
        print(f"[db] connect failed ({host}): {e}", flush=True)
        raise
    if "-pooler." in host:
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout TO 300000")
        except Exception:
            pass
    active_connections.append(conn)
    return conn

# ---------------------------------------------------------------------------
# Connection pooling for the hot per-team / per-event helpers.
#
# The team loop fans out across a 10-worker ThreadPoolExecutor and each hot
# helper previously opened + committed + closed a brand-new Postgres connection
# on every call (~5*E + 4 fresh connections per team, across thousands of teams
# every 6h). That connection churn is the dominant cost and a Heroku
# connection-limit risk. These helpers now borrow a connection from a bounded,
# thread-safe pool instead.
#
# get_pg_connection() above is deliberately left untouched so it stays backward
# compatible: external importers (run_rankings / run_awards / active_events)
# and the bounded one-off internal callers
# keep receiving a fresh, self-owned raw connection that they close themselves.
# ---------------------------------------------------------------------------

# Bounded to the 10 worker threads + a little headroom (the main thread writes
# results via insert_team_epa while workers read → ~11 concurrent borrowers max).
# Kept small to respect Heroku's connection limit. minconn == maxconn on purpose:
# psycopg2's pool only KEEPS up to minconn idle connections on putconn and closes
# any beyond it, so a smaller minconn would re-introduce per-call churn under the
# 10-thread fan-out. Equal min/max means returned connections are always retained
# and reused, with a hard cap of maxconn total open at once.
_DB_POOL_MAXCONN = int(os.environ.get("PG_POOL_MAXCONN", "12"))
_db_pool = None
_db_pool_lock = threading.Lock()


def _connect_kwargs_from_database_url():
    """Shared DSN kwargs for get_pg_connection / the ThreadedConnectionPool."""
    url = os.environ.get("DATABASE_URL")
    if url is None:
        raise Exception("DATABASE_URL not set in environment.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    result = urlparse(url)
    dbname = (result.path or "/").lstrip("/")
    if "?" in dbname:
        dbname = dbname.split("?", 1)[0]
    host = result.hostname or ""
    # GitHub Actions runners often cannot reach Neon over IPv6 ("Network is
    # unreachable"). Prefer an IPv4 hostaddr while keeping `host` for TLS/SNI.
    hostaddr = None
    try:
        import socket

        infos = socket.getaddrinfo(host, result.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            hostaddr = infos[0][4][0]
    except Exception:
        hostaddr = None
    kwargs = dict(
        database=dbname,
        user=result.username,
        password=result.password,
        host=host,
        port=result.port or 5432,
        connect_timeout=int(os.environ.get("PG_CONNECT_TIMEOUT", "60")),
    )
    if hostaddr:
        kwargs["hostaddr"] = hostaddr
    if "neon.tech" in host or "sslmode=require" in url:
        kwargs["sslmode"] = "require"
    # Neon pooler rejects startup `options`; set timeout after connect instead.
    if "-pooler." not in host:
        kwargs["options"] = "-c statement_timeout=300000"
    return kwargs, host


def _get_db_pool():
    """Lazily build a bounded, thread-safe pool (same DSN/options as get_pg_connection)."""
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                kwargs, _host = _connect_kwargs_from_database_url()
                maxconn = max(2, _DB_POOL_MAXCONN)
                _db_pool = psycopg2_pool.ThreadedConnectionPool(
                    minconn=maxconn,
                    maxconn=maxconn,
                    **kwargs,
                )
    return _db_pool


@contextmanager
def _pooled_connection():
    """
    Borrow a connection from the pool and guarantee it is returned exactly once.

    On success any lingering (read) transaction is rolled back so we never hand
    an "idle in transaction" connection back to the pool; writers commit
    explicitly inside the block first (a rollback after commit is a no-op). On
    error the connection is closed and dropped from the pool (a fresh one is
    created on demand) so a poisoned/aborted connection is never reused. This is
    the pooled analogue of the old open-per-call/close-per-call pattern, and it
    cooperates with the @retry decorators on the read helpers.
    """
    pool = _get_db_pool()
    conn = pool.getconn()
    broken = False
    try:
        yield conn
    except Exception:
        broken = True
        raise
    finally:
        if broken:
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
        else:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                pool.putconn(conn)
            except Exception:
                pass


def _close_db_pool():
    """Close every pooled connection (called during finalize / shutdown)."""
    global _db_pool
    pool = _db_pool
    _db_pool = None
    if pool is not None:
        try:
            pool.closeall()
        except Exception:
            pass


# Per-run memoization caches for values that are constant within a single run.
# All are cleared at the start of _fetch_and_store_team_data_impl (mirrors the
# existing match_cache.clear()).
_team_experience_cache = {}
_team_experience_lock = threading.Lock()
_team_played_events_cache = {}
_team_played_events_lock = threading.Lock()
# Preloaded season event metadata: event_key -> start_date (str or None), built
# once per run so the per-event chronological weight + start-date reads (which
# previously read the SAME events row twice per event) become dict lookups.
_event_start_date_cache = {}
_event_meta_lock = threading.Lock()


def preload_event_metadata(year):
    """
    Load start_date for every event of the season once so per-event chronological
    weighting / sorting are dict lookups instead of two identical DB reads per
    event. Falsy start_dates are normalized to None to exactly match the old
    get_event_start_date_from_db behavior (which returned None for empty values).
    """
    try:
        with _pooled_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT event_key, start_date FROM events WHERE LEFT(event_key, 4) = %s",
                (str(year),),
            )
            rows = cur.fetchall()
            cur.close()
    except Exception as e:
        # Non-fatal: helpers fall back to per-event DB reads if the cache is empty.
        print(f"preload_event_metadata failed for {year}: {e}", flush=True)
        return
    with _event_meta_lock:
        for event_key, start_date in rows:
            _event_start_date_cache[event_key] = start_date if start_date else None

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
    with _pooled_connection() as conn:
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


def insert_team_epa(result, year):
    # Insert or update a team's EPA data for a given year
    with _pooled_connection() as conn:
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


def _db_int_or_none(x):
    if x is None:
        return None
    return int(x)


def _rank_and_count_row_unchanged(
    new8: tuple, old8: tuple
) -> bool:
    """True if computed rank/count columns match what is already stored (skip noisy UPDATEs)."""
    for a, b in zip(new8, old8):
        na, nb = _db_int_or_none(a), _db_int_or_none(b)
        if na != nb:
            return False
    return True


def _probs_unchanged(
    p_red: float, p_blue: float, ex_red, ex_blue, eps: float = 1e-9
) -> bool:
    if ex_red is None and ex_blue is None:
        return False
    if ex_red is None or ex_blue is None:
        return False
    try:
        return abs(float(p_red) - float(ex_red)) < eps and abs(float(p_blue) - float(ex_blue)) < eps
    except (TypeError, ValueError):
        return False


def compute_and_store_team_epa_ranks(year: int, quiet: bool = False, conn=None):
    """
    Compute global / country / state / district ACE ranks for one season and UPDATE team_epas.

    Competition-style ranks: rank = 1 + count of eligible peers in scope with strictly higher ACE
    (ties share the same rank). Eligible peers exclude demo teams (9970–9999), ACE 0, and teams
    with no season W/L/T. District scope uses teams.district_key + districts display join the
    same way as datagather.

    District ranks are only stored when the team has a district_key (regional teams: NULL).

    Ranks and pool sizes are recomputed every run, but a row is written only when at least one
    rank or count value differs from what is already in ``team_epas`` (avoids no-op updates).

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
        cur.execute(
            """
            SELECT team_number, rank_global, rank_country, rank_state, rank_district,
                   count_global, count_country, count_state, count_district
            FROM team_epas
            WHERE year = %s
            """,
            (year,),
        )
        existing_ranks = {r[0]: r[1:9] for r in cur.fetchall()}
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

    batch_rows = []
    if updates:
        for (gr, cr, sr, dr, cg, cc, cs, cd, tn, y) in updates:
            new8 = (gr, cr, sr, dr, cg, cc, cs, cd)
            old8 = existing_ranks.get(tn)
            if old8 is not None and _rank_and_count_row_unchanged(new8, old8):
                continue
            batch_rows.append((tn, y, gr, cr, sr, dr, cg, cc, cs, cd))
        if batch_rows:
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
        n_tot = len(updates)
        n_wrote = len(batch_rows) if updates else 0
        n_skip = n_tot - n_wrote
        if n_wrote:
            print(
                f"Stored ACE ranks for year {year} ({n_wrote} row(s) updated"
                f"{f', {n_skip} unchanged skipped' if n_skip else ''})."
            )
        elif n_tot:
            print(f"ACE ranks for year {year}: all {n_tot} team row(s) already up to date, no DB writes.")
        else:
            print(f"compute_and_store_team_epa_ranks: no team_epas rows for year {year}.")


# Robust retry for team experience
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_experience_pg(team_number, up_to_year):
    with _pooled_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(DISTINCT year) FROM team_epas
            WHERE team_number = %s AND year <= %s
        """, (team_number, up_to_year))
        years = cur.fetchone()[0]
        cur.close()
    return years if years else 1

# Robust retry for team events
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_events(team_number, year):
    with _pooled_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT event_key FROM event_teams
            WHERE team_number = %s AND LEFT(event_key, 4) = %s
        """, (team_number, str(year)))
        events = [row[0] for row in cur.fetchall()]
        cur.close()
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
def _query_team_played_events(team_number, year):
    with _pooled_connection() as conn:
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


def get_team_played_events(team_number, year):
    # Depends only on (team_number, year) and event_matches is stable during the
    # team loop (populated by create_event_db before it, predictions written
    # after), so memoize once per team+year instead of re-querying per event.
    key = (team_number, year)
    with _team_played_events_lock:
        if key in _team_played_events_cache:
            return list(_team_played_events_cache[key])
    result = _query_team_played_events(team_number, year)
    with _team_played_events_lock:
        _team_played_events_cache[key] = result
    return list(result)

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


def stratified_team_sample(teams: List[dict], year: int, fraction: float, seed: int = 42) -> List[dict]:
    """Pick ~fraction of teams across ACE performance strata for fast iteration.

    Buckets by existing season ACE (zeros / missing in their own bucket), then
    samples ``fraction`` from each stratum so elites, midfield, and bottom are
    all represented.
    """
    import random as _random

    fraction = max(0.01, min(1.0, float(fraction)))
    if fraction >= 0.999 or len(teams) <= 20:
        return list(teams)

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT team_number, COALESCE(ace, 0) FROM team_epas WHERE year = %s",
        (year,),
    )
    ace_by_team = {int(r[0]): float(r[1] or 0) for r in cur.fetchall()}
    cur.close()
    conn.close()

    scored = []
    unscored = []
    for t in teams:
        tn = int(t["team_number"])
        ace = ace_by_team.get(tn)
        if ace is None or ace <= 0:
            unscored.append(t)
        else:
            scored.append((ace, t))

    scored.sort(key=lambda x: x[0])
    n_bins = 5
    bins: List[List[dict]] = [[] for _ in range(n_bins)]
    if scored:
        for i, (_, t) in enumerate(scored):
            bins[min(n_bins - 1, (i * n_bins) // len(scored))].append(t)
    if unscored:
        bins.append(unscored)

    rng = _random.Random(seed)
    picked: List[dict] = []
    for bucket in bins:
        if not bucket:
            continue
        k = max(1, int(round(len(bucket) * fraction)))
        k = min(k, len(bucket))
        picked.extend(rng.sample(bucket, k))

    picked.sort(key=lambda t: t["team_number"])
    return picked


def event_keys_for_teams(year: int, team_numbers) -> List[str]:
    """All event keys in ``year`` attended by any of ``team_numbers``."""
    team_numbers = list(team_numbers)
    if not team_numbers:
        return []
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT event_key
        FROM event_teams
        WHERE LEFT(event_key, 4) = %s AND team_number = ANY(%s)
        """,
        (str(year), team_numbers),
    )
    keys = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return keys


def get_active_scope(year, buffer_days=2):
    """
    Resolve the incremental ("active-only") work set for a season.

    Returns a dict with:
      - active_events:  event keys whose competition window overlaps "now"
                        (via active_events.get_active_event_keys).
      - active_teams:   set of team numbers registered for any active event.
                        These are the ONLY teams whose team_epas rows are
                        recomputed in active-only mode.
      - needed_events:  every event key attended (this season) by any active
                        team, unioned with active_events. create_event_db must
                        fetch matches for all of these so each active team's
                        FULL season is present in match_cache and its overall
                        EPA recomputes identically to a full run.

    A non-active team plays no active event, so none of its matches change; a
    full recompute would reproduce its existing row byte-for-byte. Leaving those
    rows untouched is therefore lossless. Ranks/predictions are recomputed over
    the full team set afterwards from stored + freshly-updated ACE.
    """
    conn = get_pg_connection()
    try:
        active_events = get_active_event_keys(conn, year, buffer_days=buffer_days)
        if not active_events:
            return {"active_events": [], "active_teams": set(), "needed_events": []}

        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT team_number FROM event_teams WHERE event_key = ANY(%s)",
            (list(active_events),),
        )
        active_teams = {r[0] for r in cur.fetchall() if r[0] is not None}

        if not active_teams:
            cur.close()
            # Active events exist but have no registered teams yet: still refresh
            # those events so scores/schedules stay current, but there is nothing
            # to recompute.
            return {
                "active_events": list(active_events),
                "active_teams": set(),
                "needed_events": list(active_events),
            }

        cur.execute(
            """
            SELECT DISTINCT event_key
            FROM event_teams
            WHERE LEFT(event_key, 4) = %s AND team_number = ANY(%s)
            """,
            (str(year), list(active_teams)),
        )
        needed_events = {r[0] for r in cur.fetchall()}
        needed_events.update(active_events)
        cur.close()
        return {
            "active_events": list(active_events),
            "active_teams": active_teams,
            "needed_events": list(needed_events),
        }
    finally:
        if conn in active_connections:
            active_connections.remove(conn)
        conn.close()

def get_existing_event_data(event_key):
    # Get existing event data from database for comparison
    with _pooled_connection() as conn:
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

    return {
        "event": event_row,
        "teams": teams,
        "matches": matches,
    }

def get_existing_team_epa(team_number, year):
    # Get existing team EPA data from database for comparison
    with _pooled_connection() as conn:
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

def create_event_db(year, only_event_keys=None):
    # Create and populate the events database for the specified year, only updating what's changed.
    #
    # only_event_keys (active-only mode): restrict fetching/upserts to this set of event keys.
    # This is the union of every event attended by a team playing at a currently-active event,
    # so each active team's FULL season is still fetched into match_cache (required to recompute
    # that team's overall EPA identically to a full run) while events no active team attends are
    # skipped. When None, every event of the season is processed (full-run behavior, unchanged).
    print(f"\nevents database update for {year}...")

    only_set = set(only_event_keys) if only_event_keys is not None else None
    if only_set is not None:
        print(f"  active-only: restricting to {len(only_set)} event(s) attended by active teams")

    try:
        events = tba_get(f"events/{year}")
    except Exception as e:
        print(f"Failed to load events for {year}: {e}")
        return
    
    events_to_process = []
    events_skipped_future = 0
    
    print(f"Checking {len(events)} events for updates...")
    
    for event in events:
        if shutdown_event.is_set():
            print("Shutdown requested, stopping event processing...")
            return
            
        event_key = event["key"]

        # active-only: skip events not attended by any active team.
        if only_set is not None and event_key not in only_set:
            continue
        
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
                event_week,
                event.get("lat"), event.get("lng")
            ),
            "teams": [], "matches": []
        }
        
        # Fetch teams once
        try:
            teams = tba_get(f"event/{key}/teams")
            if teams:
                for t in teams:
                    team_number = t.get("team_number")
                    if team_number is None:
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
            print(f"Error processing teams for event {key}: {e}")

        
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
                        t_num = parse_tba_team_number(team_key)
                        if t_num is not None:
                            red_teams.append(str(t_num))
                    for team_key in m["alliances"]["blue"]["team_keys"]:
                        t_num = parse_tba_team_number(team_key)
                        if t_num is not None:
                            blue_teams.append(str(t_num))
                    
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
            except Exception as e:
                print(f"Error processing event: {e}")
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
                    city, state_prov, country, website, webcast_type, webcast_channel, week,
                    lat, lng
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    week = EXCLUDED.week,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng
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


def fetch_and_store_team_data(year, active_only=False, sample_fraction: Optional[float] = None):
    """
    Fetch and store team EPA data. Uses a Postgres advisory lock so only one pipeline
    runs at a time across scheduler one-off dynos; if another run holds the lock, exit.

    When active_only is True, only teams playing at a currently-active event are
    recomputed (their full season is refetched and re-aggregated exactly as a full
    run would); all other teams' rows are left untouched. Ranks and predictions are
    still recomputed over the full team set. The advisory lock also serializes the
    active-only path against the full recompute so they never overlap.

    sample_fraction (e.g. 0.1): stratified ~N% of teams across ACE levels for fast
    local iteration. Skips global ranks/predictions so a partial write cannot distort
    the full leaderboard.
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
        print(
            "[heroku] App restart is skipped (this process did not run the pipeline).",
            flush=True,
        )
        return

    try:
        _fetch_and_store_team_data_impl(
            year, active_only=active_only, sample_fraction=sample_fraction
        )
    finally:
        _release_pipeline_lock(lock_conn)


def _fetch_and_store_team_data_impl(
    year, active_only=False, sample_fraction: Optional[float] = None
):
    # Fetch and store team data, only updating what's changed
    global match_cache
    match_cache.clear()  # Clear cache for new year
    with _event_epa_lock:
        _event_epa_cache.clear()
    # Clear per-run memoization caches (mirrors match_cache) so a re-run in the
    # same process never serves stale team/event values.
    _team_experience_cache.clear()
    _team_played_events_cache.clear()
    _event_start_date_cache.clear()

    sample_mode = sample_fraction is not None and float(sample_fraction) < 0.999

    # Active-only: resolve the set of teams playing at currently-active events and
    # the full set of events those teams attend (needed so each active team's whole
    # season is fetched and re-aggregated identically to a full run).
    active_team_numbers = None
    only_event_keys = None
    if active_only:
        scope = get_active_scope(year)
        active_events = scope["active_events"]
        active_team_numbers = scope["active_teams"]
        only_event_keys = scope["needed_events"]
        if not active_events:
            print(f"No active events for {year}; nothing to recompute (active-only).")
            return
        print(
            f"Active-only mode: {len(active_events)} active event(s), "
            f"{len(active_team_numbers)} active team(s), "
            f"{len(only_event_keys)} event(s) to fetch."
        )
        if not active_team_numbers:
            # Active events exist but no registered teams yet: refresh those events
            # (schedules/scores) but there is nothing to recompute.
            create_event_db(year, only_event_keys=only_event_keys)
            print("No active teams registered yet; refreshed active events only.")
            return

    # Sample mode resolves the team list before event fetch so we only pull their events.
    all_teams = get_teams_for_year(year)
    if active_only:
        all_teams = [t for t in all_teams if t["team_number"] in active_team_numbers]
    if sample_mode:
        before = len(all_teams)
        all_teams = stratified_team_sample(all_teams, year, float(sample_fraction))
        only_event_keys = event_keys_for_teams(year, [t["team_number"] for t in all_teams])
        print(
            f"Sample mode: {len(all_teams)}/{before} teams "
            f"(~{100 * float(sample_fraction):.0f}% stratified by ACE), "
            f"{len(only_event_keys)} event(s) to fetch."
        )

    create_event_db(year, only_event_keys=only_event_keys)
    
    if shutdown_event.is_set():
        print("Shutdown requested, stopping team data processing...")
        return
        
    print(f"\nProcessing year {year} teams...")

    # Preload this season's event start dates once (after create_event_db has
    # written the events table) so per-event chronological weighting/sorting are
    # dict lookups instead of two identical DB reads per event. This reads every
    # event of the season (cheap single query) so active teams' PAST events still
    # get correct chronological weights during an active-only run.
    preload_event_metadata(year)

    # One chronological simulation pass over match_cache (applies K/shrink/spike
    # and optional cross-event priors before per-team aggregation).
    precompute_season_event_epas(year)

    if active_only and not sample_mode:
        print(f"Total active teams to process: {len(all_teams)}")
    elif sample_mode:
        print(f"Total sample teams to process: {len(all_teams)}")
    else:
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

    if not shutdown_event.is_set() and not sample_mode:
        try:
            compute_and_store_team_epa_ranks(year)
        except Exception as e:
            print(f"Failed to compute/store team ACE ranks for {year}: {e}")
            traceback.print_exc()
    elif sample_mode:
        print("Sample mode: skipping full-season ranks refresh.")
    
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

    # Match predictions + Heroku restart (in-memory app cache; see restart_heroku_app).
    if not shutdown_event.is_set() and not sample_mode:
        try:
            calculate_and_store_match_predictions(year)
        except Exception as e:
            print(f"Failed to calculate match predictions for {year}: {e}")
        finally:
            # Runs after predictions success or exception; not reached if we returned early above
            # (e.g. shutdown) or if this process never got the pipeline lock in fetch_and_store_team_data.
            restart_heroku_app()
    elif sample_mode:
        print("Sample mode: skipping match predictions + app restart.")

def get_team_experience(team_number: int, up_to_year: int) -> int:
    # Determine how many years a team has competed up to and including up_to_year.
    # Constant within a run for a given (team, year); memoized so the two identical
    # COUNT queries per event (calculate_confidence + calculate_event_epa) collapse
    # to a single query per team+year. Only successful results are cached so the
    # exception path keeps retrying exactly like before.
    key = (team_number, up_to_year)
    with _team_experience_lock:
        if key in _team_experience_cache:
            return _team_experience_cache[key]
    try:
        val = get_team_experience_pg(team_number, up_to_year)
    except Exception as e:
        print(f"Failed to get team experience: {e}")
        return 1  # Default to first year if we can't determine
    with _team_experience_lock:
        _team_experience_cache[key] = val
    return val

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

    # Linear map only: elite component sums (~0.90+) → ~1.0; mid-pack (~0.54) → ~0.60.
    ceiling = CONFIDENCE_CEILING if CONFIDENCE_CEILING > 0 else 1.0
    capped_confidence = max(0.0, min(1.0, raw_confidence / ceiling))
    return raw_confidence, capped_confidence, record_alignment

def _ensure_prediction_score_columns() -> None:
    """Add predicted score columns if missing (idempotent)."""
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            ALTER TABLE event_matches
            ADD COLUMN IF NOT EXISTS red_predicted_score DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS blue_predicted_score DOUBLE PRECISION
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()



def parse_tba_team_number(team_key) -> Optional[int]:
    """
    Parse a TBA team key/token into a team number.

    Accepts ``frc254``, ``254``, ``frc254B``, ``frc498E``, etc. Any trailing
    surrogate letter suffix is ignored; returns None when there are no leading digits.
    """
    if team_key is None:
        return None
    tok = str(team_key).strip()
    if not tok:
        return None
    if tok.lower().startswith("frc"):
        tok = tok[3:]
    i = 0
    while i < len(tok) and tok[i].isdigit():
        i += 1
    if i == 0:
        return None
    try:
        return int(tok[:i])
    except ValueError:
        return None


def tba_team_key_is_surrogate(team_key) -> bool:
    """True when the key has a non-digit surrogate suffix (e.g. frc254B, frc498E)."""
    if team_key is None:
        return False
    tok = str(team_key).strip()
    if tok.lower().startswith("frc"):
        tok = tok[3:]
    i = 0
    while i < len(tok) and tok[i].isdigit():
        i += 1
    return i > 0 and i < len(tok)


def calculate_and_store_match_predictions(year: int):
    """
    DB-only predictions from stored season / event_perf RAW and ACE ratings.

    Writes ``red_win_prob``, ``blue_win_prob``, and predicted scores to
    ``event_matches``. Does not call TBA or replay score breakdowns.
    """
    if shutdown_event.is_set():
        return

    _ensure_prediction_score_columns()
    config = PredictionConfig.from_env()

    conn = get_pg_connection()
    try:
        data = load_prediction_data_from_db(conn, year)
    finally:
        conn.close()

    if not data.matches:
        print(f"Match predictions {year}: no matches in DB", flush=True)
        return

    predictions = predict_all_matches_db(data, config)
    pred_by_key = {p.match_key: p for p in predictions}

    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT match_key, red_win_prob, blue_win_prob,
                   red_predicted_score, blue_predicted_score
            FROM event_matches
            WHERE LEFT(event_key, 4) = %s
            """,
            (str(year),),
        )
        existing = {row[0]: row[1:] for row in cur.fetchall()}

        updates = []
        skipped_missing = 0
        skipped_unchanged = 0
        skipped_bad = 0

        for match_key, pred in pred_by_key.items():
            if match_key not in existing:
                skipped_missing += 1
                continue
            ex_pr, ex_pb, ex_rs, ex_bs = existing[match_key]
            if not math.isfinite(pred.p_red) or not math.isfinite(pred.p_blue):
                skipped_bad += 1
                continue
            if (
                _probs_unchanged(pred.p_red, pred.p_blue, ex_pr, ex_pb)
                and ex_rs is not None
                and ex_bs is not None
                and abs(float(ex_rs) - pred.red_predicted_score) < 1e-6
                and abs(float(ex_bs) - pred.blue_predicted_score) < 1e-6
            ):
                skipped_unchanged += 1
                continue
            updates.append(
                (
                    pred.p_red,
                    pred.p_blue,
                    pred.red_predicted_score,
                    pred.blue_predicted_score,
                    match_key,
                )
            )

        if updates:
            cur.executemany(
                """
                UPDATE event_matches
                SET red_win_prob = COALESCE(%s::double precision, red_win_prob),
                    blue_win_prob = COALESCE(%s::double precision, blue_win_prob),
                    red_predicted_score = COALESCE(%s::double precision, red_predicted_score),
                    blue_predicted_score = COALESCE(%s::double precision, blue_predicted_score)
                WHERE match_key = %s
                """,
                updates,
            )
        conn.commit()
        print(
            f"Match predictions {year}: wrote {len(updates)} of {len(pred_by_key)} computed "
            f"(scope={config.rating_scope} field={config.rating_field} agg={config.aggregation}) — "
            f"skipped: {skipped_unchanged} unchanged, {skipped_missing} not in DB, "
            f"{skipped_bad} non-finite",
            flush=True,
        )
    finally:
        cur.close()
        conn.close()

def _empty_event_epa() -> Dict:
    return {
        "raw": 0.0, "auto_raw": 0.0, "teleop_raw": 0.0, "endgame_raw": 0.0,
        "confidence": 0.0, "ace": 0.0,
        "match_count": 0, "raw_confidence": 0.0,
        "consistency": 0.0, "dominance": 0.0,
        "event_boost": 0.0, "veteran_boost": 0.0,
        "years_experience": 0, "weights": {}, "record_alignment": 0.0,
        "wins": 0, "losses": 0, "ties": 0,
    }


def _event_key_from_matches(matches: List[Dict]) -> Optional[str]:
    if not matches:
        return None
    m = matches[0]
    if m.get("event_key"):
        return m["event_key"]
    key = m.get("key") or ""
    for marker in ("_qm", "_qf", "_sf", "_f", "_ef"):
        if marker in key:
            return key.split(marker)[0]
    return key or None


def _consistency_from_contributions(contributions: List[float]) -> float:
    """Stability of the smoothed RAW path (skip cold-start ramp)."""
    if len(contributions) < 2:
        return 0.7
    # Drop the first third so the initial climb from 0 does not look "inconsistent."
    start = 0 if len(contributions) < 6 else len(contributions) // 3
    series = contributions[start:]
    if len(series) < 2:
        series = contributions
    peak = max(abs(x) for x in series) or 1.0
    mean_c = abs(statistics.mean(series)) or 1.0
    stdev = statistics.stdev(series)
    # Softer than pure peak CV: blend peak + mean so stable mid-tier estimates score well.
    scale = 0.6 * peak + 0.4 * mean_c
    return max(0.55, min(1.0, 1.0 - stdev / (scale + 1e-6)))


def _finalize_state_to_event_epa(
    st: TeamPhaseState, team_key: str, team_number: int, year: int
) -> Dict:
    if st.match_count <= 0:
        return _empty_event_epa()

    consistency = _consistency_from_contributions(st.contributions)
    dominance = min(1.0, statistics.mean(st.dominance_scores)) if st.dominance_scores else 0.0
    played_event_keys = get_team_played_events(team_number, int(year))
    total_events = len(played_event_keys)
    event_boost = EVENT_BOOSTS.get(min(total_events, 3), EVENT_BOOSTS[3])
    raw_confidence, confidence, record_alignment = calculate_confidence(
        consistency, dominance, event_boost, team_number, st.wins, st.losses, int(year)
    )
    overall = max(0.0, st.raw)
    years = get_team_experience(team_number, int(year))
    veteran_boost = get_veteran_boost(years)
    return {
        "raw": round(overall, 2),
        "auto_raw": round(max(0.0, st.auto), 2),
        "teleop_raw": round(max(0.0, st.teleop), 2),
        "endgame_raw": round(max(0.0, st.endgame), 2),
        "confidence": round(confidence, 2),
        "ace": round(overall * confidence, 2),
        "match_count": st.match_count,
        "raw_confidence": raw_confidence,
        "consistency": consistency,
        "dominance": dominance,
        "event_boost": event_boost,
        "veteran_boost": veteran_boost,
        "years_experience": years,
        "weights": CONFIDENCE_WEIGHTS,
        "record_alignment": record_alignment,
        "wins": st.wins,
        "losses": st.losses,
        "ties": st.ties,
    }


def preload_confidence_lookups_from_match_cache(year: int) -> None:
    """Fill played-event + experience caches without per-team SQL during precompute.

    Played events are derived from ``match_cache`` (already fetched). Experience is
    one grouped query for every team that appears in those matches.
    """
    y = int(year)
    # event_key -> set of team_numbers that have a played match there
    played: Dict[int, set] = {}
    for ek, matches in match_cache.items():
        for match in matches or []:
            red = (match.get("alliances") or {}).get("red", {}).get("score")
            blue = (match.get("alliances") or {}).get("blue", {}).get("score")
            winning = match.get("winning_alliance")
            if red == 0 and blue == 0 and winning not in ("red", "blue"):
                continue
            for color in ("red", "blue"):
                for key in (match.get("alliances") or {}).get(color, {}).get("team_keys") or []:
                    digits = "".join(ch for ch in str(key) if ch.isdigit())
                    if not digits:
                        continue
                    tn = int(digits)
                    played.setdefault(tn, set()).add(ek)

    with _team_played_events_lock:
        for tn, eks in played.items():
            _team_played_events_cache[(tn, y)] = list(eks)

    team_numbers = list(played.keys())
    if not team_numbers:
        return

    try:
        with _pooled_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT team_number, COUNT(DISTINCT year)
                FROM team_epas
                WHERE year <= %s AND team_number = ANY(%s)
                GROUP BY team_number
                """,
                (y, team_numbers),
            )
            rows = cur.fetchall()
            cur.close()
    except Exception as e:
        print(f"preload experience lookup failed (non-fatal): {e}", flush=True)
        return

    with _team_experience_lock:
        for tn, years in rows:
            _team_experience_cache[(int(tn), y)] = int(years) if years else 1
        # Teams with no prior team_epas rows still need a cache hit (rookie = 1).
        for tn in team_numbers:
            key = (tn, y)
            if key not in _team_experience_cache:
                _team_experience_cache[key] = 1


def _get_or_compute_event_epa_map(matches: List[Dict], year: int, method: Method) -> Dict[str, dict]:
    event_key = _event_key_from_matches(matches) or f"unknown-{id(matches)}"
    cache_key = f"{event_key}::{method}"
    with _event_epa_lock:
        cached = _event_epa_cache.get(cache_key)
        if cached is not None:
            return cached

    states = simulate_event(
        matches,
        year,
        method=method,
        k_base=_ACE_K_BASE,
        shrink=_ACE_SHRINK,
        spike_damp=_ACE_SPIKE_DAMP,
        prior_means=None,
        seed_priors=False,
        k_up=_ACE_K_UP,
        k_down=_ACE_K_DOWN,
        partner_cap=_ACE_PARTNER_CAP,
    )
    out: Dict[str, dict] = {}
    for key, st in states.items():
        digits = "".join(ch for ch in str(key) if ch.isdigit())
        tn = int(digits) if digits else 0
        out[key] = _finalize_state_to_event_epa(st, key, tn, year)

    with _event_epa_lock:
        _event_epa_cache[cache_key] = out
    return out


def precompute_season_event_epas(year: int) -> None:
    """Simulate every cached event in chronological order (optional RAW prior carry).

    Must run after ``match_cache`` is populated.
    """
    if not match_cache:
        return

    print(
        f"Precomputing event EPA for {len(match_cache)} cached event(s) "
        f"(carry_prior={int(_ACE_CARRY_PRIOR)})...",
        flush=True,
    )
    preload_confidence_lookups_from_match_cache(year)

    def _start(ek: str) -> str:
        sd = _event_start_date_cache.get(ek)
        return str(sd) if sd else ""

    event_keys = sorted(match_cache.keys(), key=lambda ek: (_start(ek), ek))
    priors: Dict[str, Tuple[float, float, float]] = {}
    computed = 0
    total = len(event_keys)
    for i, ek in enumerate(event_keys, 1):
        matches = match_cache.get(ek) or []
        if not matches:
            continue
        cache_key = f"{ek}::{_ACE_METHOD}"
        with _event_epa_lock:
            if cache_key in _event_epa_cache:
                if _ACE_CARRY_PRIOR:
                    for key, epa in _event_epa_cache[cache_key].items():
                        new = (
                            float(epa.get("auto_raw") or 0.0),
                            float(epa.get("teleop_raw") or 0.0),
                            float(epa.get("endgame_raw") or 0.0),
                        )
                        if new == (0.0, 0.0, 0.0):
                            continue
                        old = priors.get(key)
                        if not old or _ACE_PRIOR_BLEND >= 1.0:
                            priors[key] = new
                        else:
                            b = _ACE_PRIOR_BLEND
                            priors[key] = (
                                (1.0 - b) * old[0] + b * new[0],
                                (1.0 - b) * old[1] + b * new[1],
                                (1.0 - b) * old[2] + b * new[2],
                            )
                continue

        states = simulate_event(
            matches,
            int(year),
            method=_ACE_METHOD,
            k_base=_ACE_K_BASE,
            shrink=_ACE_SHRINK,
            spike_damp=_ACE_SPIKE_DAMP,
            prior_means=priors if _ACE_CARRY_PRIOR else None,
            seed_priors=_ACE_CARRY_PRIOR,
            k_up=_ACE_K_UP,
            k_down=_ACE_K_DOWN,
            partner_cap=_ACE_PARTNER_CAP,
        )
        out: Dict[str, dict] = {}
        for key, st in states.items():
            digits = "".join(ch for ch in str(key) if ch.isdigit())
            tn = int(digits) if digits else 0
            out[key] = _finalize_state_to_event_epa(st, key, tn, int(year))
            if _ACE_CARRY_PRIOR and st.initialized:
                new = (st.auto, st.teleop, st.endgame)
                old = priors.get(key)
                if not old or _ACE_PRIOR_BLEND >= 1.0:
                    priors[key] = new
                else:
                    b = _ACE_PRIOR_BLEND
                    priors[key] = (
                        (1.0 - b) * old[0] + b * new[0],
                        (1.0 - b) * old[1] + b * new[1],
                        (1.0 - b) * old[2] + b * new[2],
                    )
        with _event_epa_lock:
            _event_epa_cache[cache_key] = out
        computed += 1
        if i == 1 or i % 25 == 0 or i == total:
            print(f"  event EPA precompute {i}/{total} ({ek})", flush=True)

    print(
        f"Precomputed event EPA for {computed} event(s) "
        f"(method={_ACE_METHOD}, shrink={_ACE_SHRINK}, k={_ACE_K_BASE}, "
        f"k_up={_ACE_K_UP}, k_down={_ACE_K_DOWN}, partner_cap={_ACE_PARTNER_CAP}, "
        f"spike_damp={_ACE_SPIKE_DAMP}, carry_prior={int(_ACE_CARRY_PRIOR)})",
        flush=True,
    )


def calculate_event_epa(matches: List[Dict], team_key: str, team_number: int) -> Dict:
    """Per-event ACE components for one team (match-centric residual attribution)."""
    try:
        if not matches:
            return _empty_event_epa()
        year = matches[0].get("event_key", matches[0].get("key", "2025"))[:4]
        try:
            year_int = int(year)
        except Exception:
            year_int = 2025

        epa_map = _get_or_compute_event_epa_map(matches, year_int, _ACE_METHOD)
        result = epa_map.get(team_key)
        if result is None:
            alt = f"frc{team_number}"
            result = epa_map.get(alt)
        return result or _empty_event_epa()
    except Exception as e:
        print(f"EPA FATAL ERROR for team {team_key}: {e}")
        traceback.print_exc()
        return _empty_event_epa()


def get_event_chronological_weight(event_key: str, year: int) -> tuple[float, str]:
    """
    Weight for how much an event counts when blending multi-event season ACE (aggregate_overall_epa).
    Effective per-event weight = chronological_weight * match_count.

    Fixed weights:
      - Preseason (before first regular week): 0.05
      - Offseason (after last regular week): 0.10
      - Unknown / no week_ranges / no start_date: 1.0

    Regular season: piecewise linear in season_progress (0 = season start, 1 = season end).
    Steeper than before so late weeks are weighted much more than early weeks:
      - First 20% of season: 0.12 -> 0.32
      - 20% - 80%: 0.32 -> 0.84
      - Last 20%: 0.84 -> 1.00
    """
    try:
        # start_date comes from the per-run preloaded cache (falling back to a DB
        # read on a miss); the weight math below is unchanged.
        start_date = get_event_start_date_from_db(event_key)
        return _chronological_weight_from_start_date(start_date, year)
    except Exception as e:
        print(f"Error calculating chronological weight for {event_key}: {e}")
        return 1.0, 'unknown'


def _chronological_weight_from_start_date(start_date: Optional[str], year: int) -> tuple[float, str]:
    """Pure computation extracted verbatim from get_event_chronological_weight (no DB access)."""
    # Load week ranges for the year
    week_ranges = load_week_ranges()
    if not week_ranges:
        return 1.0, 'unknown'

    year_str = str(year)
    if year_str not in week_ranges:
        return 1.0, 'unknown'

    if not start_date:  # start_date is None or empty
        return 1.0, 'unknown'

    event_start = datetime.strptime(start_date, '%Y-%m-%d')

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

    # Piecewise linear: discount early season, emphasize late season (same structure as before).
    if season_progress <= 0.2:
        weight = 0.12 + (season_progress / 0.2) * 0.2
    elif season_progress <= 0.8:
        weight = 0.32 + ((season_progress - 0.2) / 0.6) * 0.52
    else:
        weight = 0.84 + ((season_progress - 0.8) / 0.2) * 0.16

    return round(weight, 3), 'regular'

def get_event_start_date_from_db(event_key: str) -> str:
    """Get event start date. Uses the per-run preloaded cache; falls back to a DB read."""
    if event_key in _event_start_date_cache:
        return _event_start_date_cache[event_key]
    try:
        with _pooled_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT start_date FROM events WHERE event_key = %s", (event_key,))
            event_row = cur.fetchone()
            cur.close()

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

        # Display components (informational) — do NOT rebuild season confidence from
        # these and re-apply nonlinear scaling. That double-penalized residual noise
        # and dropped median confidence into the mid-50s. Season confidence is the
        # weighted mean of already-computed event confidences.
        weights = valid_events[0].get("weights", {}) or CONFIDENCE_WEIGHTS
        consistency_component = weights.get("consistency", 0.0) * avg_consistency
        record_component = weights.get("record_alignment", 0.0) * avg_record_alignment
        veteran_component = weights.get("veteran", 0.0) * avg_veteran_boost
        dominance_component = weights.get("dominance", 0.0) * avg_dominance
        event_component = weights.get("events", 0.0) * avg_event_boost
        raw_confidence = avg_confidence
        final_confidence = max(0.0, min(1.0, avg_confidence))

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

            # Calculate EPA for this event (which includes wins/losses/ties for the event)
            # and only keep it once this specific team has at least one played match.
            # This avoids dropping early-event stats due to event-level start detection.
            event_epa = calculate_event_epa(matches, team_key, team_number)
            if event_epa.get("match_count", 0) <= 0:
                continue
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


def finalize():
    """Clean up executors/connections and print runtime. Call from main entry point."""
    print("\nPerforming final cleanup...")
    for executor in active_executors:
        cleanup_executor(executor)
    for conn in active_connections:
        cleanup_connection(conn)
    _close_db_pool()
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
        # Prefer data/.env.local over Neon when present (local ACE experiments).
        _env_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
        if os.path.isfile(_env_local):
            with open(_env_local, encoding="utf-8") as _ef:
                for _line in _ef:
                    _line = _line.strip()
                    if not _line or _line.startswith("#") or "=" not in _line:
                        continue
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                    if _k:
                        os.environ[_k] = _v
        from db_target import assert_safe_db_target, describe_db_target

        assert_safe_db_target("run.py")
        print(f"DB target: {describe_db_target()}", flush=True)

        positional = [a for a in sys.argv[1:] if not a.startswith("--")]
        flags = {a for a in sys.argv[1:] if a.startswith("--")}
        ranks_only = "--ranks-only" in flags
        predictions_only = "--predictions-only" in flags
        active_only = "--active-only" in flags
        sample_fraction = None
        for a in list(flags):
            if a.startswith("--sample="):
                try:
                    sample_fraction = float(a.split("=", 1)[1])
                except ValueError:
                    print("Invalid --sample= value; use e.g. --sample=0.1")
                    sys.exit(1)
            elif a == "--sample":
                # Bare flag defaults to 10% stratified sample
                sample_fraction = 0.1
        if positional:
            try:
                year = int(positional[0])
            except ValueError:
                print("Year must be an integer.")
                sys.exit(1)
            if ranks_only:
                compute_and_store_team_epa_ranks(year)
                restart_heroku_app()
            elif predictions_only:
                calculate_and_store_match_predictions(year)
                restart_heroku_app()
            else:
                fetch_and_store_team_data(
                    year, active_only=active_only, sample_fraction=sample_fraction
                )
        else:
            main()
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        finalize()
