from dotenv import load_dotenv
import functools
import os
from urllib.parse import urlparse
import psycopg2
from psycopg2 import pool
import json
from collections import defaultdict
import threading
import time
from datetime import date

load_dotenv()

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()

# Cached avatar set for efficient lookups (loaded once at startup)
_available_avatars = None
_avatar_cache_lock = threading.Lock()

def get_connection_pool():
    """Get or create the database connection pool."""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:  # Double-check pattern
                _connection_pool = create_connection_pool()
    
    return _connection_pool

def create_connection_pool():
    """Create a new database connection pool."""
    url = os.environ.get("DATABASE_URL")
    if url is None:
        raise Exception("DATABASE_URL not set in environment.")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    result = urlparse(url)
    
    # Pool configuration optimized for Heroku 512MB memory
    # Smaller pool size to conserve memory
    pool_config = {
        'database': result.path[1:],
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port,
        'minconn': 1,      # Minimum connections
        'maxconn': 10,      # Maximum connections (conservative for 512MB)
        'connect_timeout': 10,
        'options': '-c statement_timeout=300000'  # 5 minute timeout
    }
    
    try:
        pool_obj = pool.ThreadedConnectionPool(**pool_config)
        print(f"Database connection pool created: {pool_config['minconn']}-{pool_config['maxconn']} connections")
        return pool_obj
    except Exception as e:
        print(f"Failed to create connection pool: {e}")
        raise

def get_pg_connection():
    """Get a connection from the pool."""
    pool_obj = get_connection_pool()
    
    try:
        conn = pool_obj.getconn()
        if conn is None:
            raise Exception("Failed to get connection from pool")
        return conn
    except Exception as e:
        print(f"Error getting connection from pool: {e}")
        raise

def return_pg_connection(conn):
    """Return a connection to the pool."""
    if conn is None:
        return
        
    pool_obj = get_connection_pool()
    try:
        pool_obj.putconn(conn)
    except Exception as e:
        print(f"Error returning connection to pool: {e}")
        # If we can't return to pool, close it
        try:
            conn.close()
        except:
            pass

def close_connection_pool():
    """Close the connection pool (for cleanup)."""
    global _connection_pool
    
    if _connection_pool is not None:
        with _pool_lock:
            if _connection_pool is not None:
                try:
                    _connection_pool.closeall()
                    print("Database connection pool closed")
                except Exception as e:
                    print(f"Error closing connection pool: {e}")
                finally:
                    _connection_pool = None

# Context manager for database connections
class DatabaseConnection:
    """Context manager for database connections."""
    
    def __init__(self):
        self.conn = None
        
    def __enter__(self):
        self.conn = get_pg_connection()
        return self.conn
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            return_pg_connection(self.conn)
            self.conn = None


def _compress_dict(d: dict) -> dict:
    """Drop None/empty string; keep empty string for 'wa' (match ties)."""
    return {k: v for k, v in d.items() if v not in (None, "") or k == "wa"}


def _event_perf_from_db(val):
    if val is None:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return []
    return val or []


def _match_sql_row_to_dict(row) -> dict:
    (
        match_key, event_key, comp_level, match_number, set_number,
        red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time,
        red_win_prob, blue_win_prob,
    ) = row
    return _compress_dict({
        "k": match_key,
        "ek": event_key,
        "cl": comp_level,
        "mn": match_number,
        "sn": set_number,
        "rt": red_teams,
        "bt": blue_teams,
        "rs": red_score,
        "bs": blue_score,
        "wa": winning_alliance,
        "yt": youtube_key,
        "pt": predicted_time,
        "rp": red_win_prob,
        "bp": blue_win_prob,
    })


@functools.lru_cache(maxsize=512)
def get_event_matches_tuple(event_key: str) -> tuple:
    """All matches for one event; cached to avoid duplicating work across /match, team, event pages."""
    with DatabaseConnection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT match_key, event_key, comp_level, match_number, set_number,
                       red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time,
                       red_win_prob, blue_win_prob
                FROM event_matches
                WHERE event_key = %s
                ORDER BY event_key, match_number
                """,
                (event_key,),
            )
            rows = cursor.fetchall()
    return tuple(_match_sql_row_to_dict(r) for r in rows)


def get_event_matches_for_key(event_key: str) -> list:
    return list(get_event_matches_tuple(event_key))


def count_season_matches(year: int) -> int:
    pfx = f"{int(year)}%"
    with DatabaseConnection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT COUNT(*) FROM event_matches WHERE event_key LIKE %s",
                (pfx,),
            )
            n = c.fetchone()[0]
    return int(n) if n is not None else 0


@functools.lru_cache(maxsize=512)
def get_event_rankings_for_key(event_key: str) -> dict:
    """event_key -> {team_number: rank_row dict} for one event (same shape as load_year_data rankings)."""
    out = {}
    with DatabaseConnection() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT event_key, team_number, rank, wins, losses, ties, dq
                FROM event_rankings
                WHERE event_key = %s
                ORDER BY team_number
                """,
                (event_key,),
            )
            for row in c.fetchall():
                ek, team_number, rank, wins, losses, ties, dq = row
                out[team_number] = _compress_dict(
                    {
                        "ek": ek,
                        "tk": team_number,
                        "rk": rank,
                        "w": wins,
                        "l": losses,
                        "t": ties,
                        "dq": dq,
                    }
                )
    return out


@functools.lru_cache(maxsize=512)
def get_event_awards_tuple(event_key: str) -> tuple:
    out = []
    with DatabaseConnection() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT event_key, team_number, award_name
                FROM event_awards
                WHERE event_key = %s
                ORDER BY team_number, award_name
                """,
                (event_key,),
            )
            for ek, tk, award_name in c.fetchall():
                y = int(str(ek)[:4]) if str(ek)[:4].isdigit() else None
                out.append(
                    _compress_dict(
                        {
                            "ek": ek,
                            "tk": tk,
                            "an": award_name,
                            "y": y,
                        }
                    )
                )
    return tuple(out)


def get_event_awards_for_key(event_key: str) -> list:
    return list(get_event_awards_tuple(event_key))


@functools.lru_cache(maxsize=4096)
def get_season_awards_for_team_tuple(year: int, team_number: int) -> tuple:
    """All award rows for one team in one season (e.g. Google Sheets / chatbot export)."""
    pfx = f"{int(year)}%"
    out = []
    with DatabaseConnection() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT event_key, team_number, award_name
                FROM event_awards
                WHERE event_key LIKE %s AND team_number = %s
                ORDER BY event_key, award_name
                """,
                (pfx, team_number),
            )
            for event_key, tn, award_name in c.fetchall():
                y = int(str(event_key)[:4]) if str(event_key)[:4].isdigit() else None
                out.append(
                    _compress_dict(
                        {
                            "ek": event_key,
                            "tk": tn,
                            "an": award_name,
                            "y": y,
                        }
                    )
                )
    return tuple(out)


def get_season_awards_for_team(year: int, team_number: int) -> list:
    return list(get_season_awards_for_team_tuple(int(year), int(team_number)))


def _load_avatar_cache():
    """Load the set of available avatar team numbers (lazy initialization)."""
    global _available_avatars
    
    if _available_avatars is None:
        with _avatar_cache_lock:
            if _available_avatars is None:  # Double-check pattern
                avatar_dir = "assets/avatars"
                if os.path.exists(avatar_dir):
                    # Load all PNG files and extract team numbers (filename without .png)
                    _available_avatars = set()
                    try:
                        for filename in os.listdir(avatar_dir):
                            if filename.endswith(".png") and filename != "stock.png" and filename != "bbot.png":
                                # Extract team number from filename (e.g., "1234.png" -> "1234")
                                team_num_str = filename[:-4]  # Remove .png
                                try:
                                    # Only add if it's a valid integer (team number)
                                    team_num = int(team_num_str)
                                    _available_avatars.add(team_num)
                                except ValueError:
                                    # Skip non-numeric filenames
                                    pass
                    except OSError:
                        # If directory doesn't exist or can't be read, use empty set
                        _available_avatars = set()
                else:
                    _available_avatars = set()
                print(f"Loaded {len(_available_avatars)} team avatars into cache")
    
    return _available_avatars

def get_team_avatar(team_number, year=2025):
    """
    Returns the relative URL path to a team's avatar image if it exists,
    otherwise returns the path to a stock avatar.
    Uses cached avatar set for O(1) lookup instead of file system checks.
    """
    # Use bbot.png for team numbers 9970-9999
    if 9970 <= team_number <= 9999:
        return "/assets/avatars/bbot.png?v=1"
    
    # Use cached set for fast lookup
    available_avatars = _load_avatar_cache()
    if team_number in available_avatars:
        return f"/assets/avatars/{team_number}.png?v=1"
    return "/assets/avatars/stock.png"

def load_search_data():
    """
    Load minimal data for search. Returns a 3-tuple:
    - team_by_number: {team_number: {team_number, nickname, last_year}} — one entry per team
      (avoids the previous ~35× duplicate per year, which was a large heroku memory cost).
    - event_data: {year: {event_key: {k, n}}}
    - all_events_list: precomputed flat list of every event dict for the search combobox, built once
      so callbacks do not allocate this list on every keystroke.
    """
    with open("data/teams.json", "r", encoding="utf-8") as f:
        team_nicknames = json.load(f)
    team_by_number = {}
    for team_number_str, info in team_nicknames.items():
        try:
            team_number = int(team_number_str)
        except Exception:
            continue
        team_by_number[team_number] = {
            "team_number": team_number,
            "nickname": info.get("nickname", ""),
            "last_year": info.get("last_year", None),
        }
    with open("data/events.json", "r", encoding="utf-8") as f:
        event_names = json.load(f)
    event_data = {}
    for event_key, name in event_names.items():
        try:
            year = int(event_key[:4])
        except Exception:
            continue
        event_data.setdefault(year, {})[event_key] = {
            "k": event_key,
            "n": name
        }
    all_events_list = [ev for yd in event_data.values() for ev in yd.values()]
    return team_by_number, event_data, all_events_list


def load_season_event_matches(year, conn=None):
    """
    Only `event_matches` rows for a season (same shape as in `load_year_data`).
    Use for duel, etc., instead of full `load_year_data`. Pass `conn` to reuse a connection.
    """
    ypfx = f"{int(year)}%"
    out = []

    def _fill(c):
        with c.cursor() as cursor:
            cursor.execute(
                """
                SELECT match_key, event_key, comp_level, match_number, set_number,
                       red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time,
                       red_win_prob, blue_win_prob
                FROM event_matches
                WHERE event_key LIKE %s
                ORDER BY event_key, match_number
                """,
                (ypfx,),
            )
            for row in cursor.fetchall():
                out.append(_match_sql_row_to_dict(row))

    if conn is not None:
        _fill(conn)
        return out
    with DatabaseConnection() as own:
        _fill(own)
    return out


@functools.lru_cache(maxsize=8)
def load_season_matches_cached(year: int) -> tuple:
    """Full season match rows (e.g. duel). Loaded on first use, not at web startup."""
    return tuple(load_season_event_matches(int(year)))


def load_year_data(
    year,
    include_matches: bool = True,
    include_rankings: bool = True,
    include_awards: bool = True,
    include_team_epas: bool = True,
    include_events: bool = True,
    include_event_teams: bool = True,
):
    """Load data for a specific year. For the web app, pass include_*=False to skip tables you will
    load elsewhere (per-event getters, targeted queries, or not needed on this code path)."""
    with DatabaseConnection() as conn:
        team_data = {}
        if include_team_epas:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT te.team_number, te.year,
                           t.nickname, t.city, t.state_prov, t.country, t.website,
                           COALESCE(d.display_name, d.name) AS district,
                           t.district_key,
                           te.raw, te.ace, te.confidence, te.auto_raw, te.teleop_raw, te.endgame_raw,
                           te.wins, te.losses, te.ties, te.event_perf,
                           te.rank_global, te.rank_country, te.rank_state, te.rank_district,
                           te.count_global, te.count_country, te.count_state, te.count_district
                    FROM team_epas te
                    LEFT JOIN teams t ON te.team_number = t.team_number
                    LEFT JOIN districts d ON (
                        CASE WHEN t.district_key ~ '^[0-9]{4}[a-zA-Z]+$'
                             THEN UPPER(SUBSTRING(t.district_key FROM 5))
                             ELSE UPPER(TRIM(t.district_key))
                        END
                    ) = d.district_key
                    WHERE te.year = %s
                    ORDER BY te.team_number
                """, (year,))
                for row in cursor.fetchall():
                    (
                        team_number, year, nickname, city, state_prov, country, website, district, district_key,
                        raw, ace, confidence, auto_raw, teleop_raw, endgame_raw,
                        wins, losses, ties, event_perf,
                        rank_global, rank_country, rank_state, rank_district,
                        count_global, count_country, count_state, count_district
                    ) = row

                    raw_team_data = {
                        "team_number": team_number,
                        "year": year,
                        "nickname": nickname,
                        "city": city,
                        "state_prov": state_prov,
                        "country": country,
                        "website": website,
                        "district": district,
                        "district_key": district_key,
                        "raw": raw,
                        "ace": ace,
                        "confidence": confidence,
                        "auto_raw": auto_raw,
                        "teleop_raw": teleop_raw,
                        "endgame_raw": endgame_raw,
                        "wins": wins,
                        "losses": losses,
                        "ties": ties,
                        "event_perf": _event_perf_from_db(event_perf),
                        "rank_global": rank_global,
                        "rank_country": rank_country,
                        "rank_state": rank_state,
                        "rank_district": rank_district,
                        "count_global": count_global,
                        "count_country": count_country,
                        "count_state": count_state,
                        "count_district": count_district,
                    }

                    team_data[team_number] = _compress_dict(raw_team_data)

        event_data = {}
        if include_events:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT event_key, name, start_date, end_date, event_type,
                           district_key, district_abbrev, district_name,
                           city, state_prov, country, website, webcast_type, webcast_channel, week
                    FROM events
                    WHERE event_key LIKE %s
                    ORDER BY event_key
                """, (f"{year}%",))
                for row in cursor.fetchall():
                    (
                        event_key, name, start_date, end_date, event_type,
                        district_key, district_abbrev, district_name,
                        city, state_prov, country, website, webcast_type, webcast_channel, week
                    ) = row
                    event_data[event_key] = _compress_dict({
                        "k": event_key,
                        "n": name,
                        "y": year,
                        "sd": start_date,
                        "ed": end_date,
                        "et": event_type,
                        "dk": district_key,
                        "da": district_abbrev,
                        "dn": district_name,
                        "c": city,
                        "s": state_prov,
                        "co": country,
                        "w": website,
                        "wt": webcast_type,
                        "wc": webcast_channel,
                        "wk": week
                    })

        EVENT_TEAMS = defaultdict(list)
        if include_event_teams:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT event_key, team_number, nickname, city, state_prov, country
                    FROM event_teams
                    WHERE event_key LIKE %s
                    ORDER BY event_key, team_number
                """, (f"{year}%",))
                for event_key, team_number, nickname, city, state_prov, country in cursor.fetchall():
                    EVENT_TEAMS[event_key].append(_compress_dict({
                        "ek": event_key,
                        "tk": team_number,
                        "nn": nickname,
                        "c": city,
                        "s": state_prov,
                        "co": country
                    }))

        # === Load event rankings for specific year ===
        EVENT_RANKINGS = defaultdict(dict)
        if include_rankings:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT event_key, team_number, rank, wins, losses, ties, dq
                    FROM event_rankings
                    WHERE event_key LIKE %s
                    ORDER BY event_key, team_number
                """, (f"{year}%",))
                for event_key, team_number, rank, wins, losses, ties, dq in cursor.fetchall():
                    EVENT_RANKINGS[event_key][team_number] = _compress_dict({
                        "ek": event_key,
                        "tk": team_number,
                        "rk": rank,
                        "w": wins,
                        "l": losses,
                        "t": ties,
                        "dq": dq
                    })

        # === Load awards for specific year ===
        EVENTS_AWARDS = []
        if include_awards:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT event_key, team_number, award_name
                    FROM event_awards
                    WHERE event_key LIKE %s
                    ORDER BY event_key, team_number
                """, (f"{year}%",))
                for event_key, team_number, award_name in cursor.fetchall():
                    EVENTS_AWARDS.append(_compress_dict({
                        "ek": event_key,
                        "tk": team_number,
                        "an": award_name,
                        "y": year
                    }))

        # === Load matches for specific year (optional: web app uses per-event cache instead) ===
        if include_matches:
            EVENT_MATCHES = load_season_event_matches(year, conn)
        else:
            EVENT_MATCHES = []

    return team_data, event_data, dict(EVENT_TEAMS), dict(EVENT_RANKINGS), EVENTS_AWARDS, EVENT_MATCHES


def load_team_epas_for_numbers(year: int, team_numbers: list, conn=None) -> dict:
    """Team EPA rows for a subset of teams (same shape as `load_year_data` team entries)."""
    team_numbers = sorted({int(t) for t in team_numbers})
    if not team_numbers:
        return {}

    ph = ",".join(["%s"] * len(team_numbers))
    sql = f"""
                SELECT te.team_number, te.year,
                       t.nickname, t.city, t.state_prov, t.country, t.website,
                       COALESCE(d.display_name, d.name) AS district,
                       t.district_key,
                       te.raw, te.ace, te.confidence, te.auto_raw, te.teleop_raw, te.endgame_raw,
                       te.wins, te.losses, te.ties, te.event_perf,
                       te.rank_global, te.rank_country, te.rank_state, te.rank_district,
                       te.count_global, te.count_country, te.count_state, te.count_district
                FROM team_epas te
                LEFT JOIN teams t ON te.team_number = t.team_number
                LEFT JOIN districts d ON (
                    CASE WHEN t.district_key ~ '^[0-9]{{4}}[a-zA-Z]+$'
                         THEN UPPER(SUBSTRING(t.district_key FROM 5))
                         ELSE UPPER(TRIM(t.district_key))
                    END
                ) = d.district_key
                WHERE te.year = %s AND te.team_number IN ({ph})
                ORDER BY te.team_number
            """
    params = (year, *team_numbers)

    def _fill(c):
        out = {}
        with c.cursor() as cursor:
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                (
                    team_number, yrow, nickname, city, state_prov, country, website, district, district_key,
                    raw, ace, confidence, auto_raw, teleop_raw, endgame_raw,
                    wins, losses, ties, event_perf,
                    rank_global, rank_country, rank_state, rank_district,
                    count_global, count_country, count_state, count_district
                ) = row
                raw_team_data = {
                    "team_number": team_number,
                    "year": yrow,
                    "nickname": nickname,
                    "city": city,
                    "state_prov": state_prov,
                    "country": country,
                    "website": website,
                    "district": district,
                    "district_key": district_key,
                    "raw": raw,
                    "ace": ace,
                    "confidence": confidence,
                    "auto_raw": auto_raw,
                    "teleop_raw": teleop_raw,
                    "endgame_raw": endgame_raw,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "event_perf": _event_perf_from_db(event_perf),
                    "rank_global": rank_global,
                    "rank_country": rank_country,
                    "rank_state": rank_state,
                    "rank_district": rank_district,
                    "count_global": count_global,
                    "count_country": count_country,
                    "count_state": count_state,
                    "count_district": count_district,
                }
                out[team_number] = _compress_dict(raw_team_data)
        return out

    if conn is not None:
        return _fill(conn)
    with DatabaseConnection() as own:
        return _fill(own)


def load_single_team_epa_year(year: int, team_number: int) -> dict:
    return load_team_epas_for_numbers(year, [team_number]).get(int(team_number), {})


def load_season_ace_values(year: int) -> list:
    """All season ACE values (order matches team_number) for percentile math without loading full rows."""
    with DatabaseConnection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT COALESCE(ace, 0) FROM team_epas WHERE year = %s ORDER BY team_number",
                (int(year),),
            )
            return [max(0.0, float(r[0])) for r in c.fetchall()]


def load_event_layout_data(event_key: str, year: int):
    """
    Rows needed for /event/<key> when the season is not the in-memory current year:
    one event, its team list, and EPA rows for attending teams only. Matches/rankings use per-event caches.
    """
    with DatabaseConnection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_key, name, start_date, end_date, event_type,
                       district_key, district_abbrev, district_name,
                       city, state_prov, country, website, webcast_type, webcast_channel, week
                FROM events
                WHERE event_key = %s
                """,
                (event_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None, [], {}
            (
                ek, name, start_date, end_date, event_type,
                district_key, district_abbrev, district_name,
                city, state_prov, country, website, webcast_type, webcast_channel, week
            ) = row
            event = _compress_dict({
                "k": ek,
                "n": name,
                "y": year,
                "sd": start_date,
                "ed": end_date,
                "et": event_type,
                "dk": district_key,
                "da": district_abbrev,
                "dn": district_name,
                "c": city,
                "s": state_prov,
                "co": country,
                "w": website,
                "wt": webcast_type,
                "wc": webcast_channel,
                "wk": week,
            })
            cursor.execute(
                """
                SELECT event_key, team_number, nickname, city, state_prov, country
                FROM event_teams
                WHERE event_key = %s
                ORDER BY team_number
                """,
                (event_key,),
            )
            event_teams = []
            team_nums = []
            for ek2, team_number, nickname, c, s, co in cursor.fetchall():
                event_teams.append(_compress_dict({
                    "ek": ek2,
                    "tk": team_number,
                    "nn": nickname,
                    "c": c,
                    "s": s,
                    "co": co,
                }))
                team_nums.append(team_number)

        team_data = load_team_epas_for_numbers(year, team_nums, conn=conn)
    return event, event_teams, team_data


def load_data_current_year(year: int = 2026):
    """Nest one season under `year` keys. Skips bulk matches, rankings, awards — per-event getters are cached."""
    td, ed, et, er, ea, _ = load_year_data(
        year,
        include_matches=False,
        include_rankings=False,
        include_awards=False,
    )
    return {year: td}, {year: ed}, {year: et}, {year: er}, ea, {year: []}


def _match_url_label_from_match_row(match: dict) -> str:
    """Same normalization as `normalized_label` in `layouts.match_layout` for prev/next and lookup."""
    label = (match.get("k") or "").split("_", 1)[-1] if match.get("k") else ""
    if label.lower().startswith("sf") and "m" in label.lower():
        label = label.lower().split("m")[0].upper()
    else:
        label = label.upper()
    return label


def load_match_page_data(event_key: str, year: int, match_key: str):
    """
    Load only the DB rows required for a single match page (one event, ~6 teams, and lightweight
    season columns for percentiles). Avoids `load_year_data` which materializes the entire season
    and was causing O(GB) memory under concurrent /match/ traffic.
    Returns (team_db, event_db, event_matches, season_stat_lists) or None if the match is not found.
    season_stat_lists: dict mapping stat name -> list of values for the season (for compute_percentiles).
    """
    mku = (match_key or "").upper()
    event_matches = get_event_matches_for_key(event_key)
    if not event_matches:
        return None

    found = None
    for m in event_matches:
        if _match_url_label_from_match_row(m) == mku:
            found = m
            break
    if not found:
        return None

    def _parse_alliance_csv(csv) -> list:
        if csv is None:
            return []
        out = []
        for raw in str(csv).split(","):
            tok = raw.strip()
            if not tok:
                continue
            low = tok.lower()
            if low.startswith("frc"):
                tok = tok[3:]
            tok = tok.rstrip("Bb")
            if tok.isdigit():
                out.append(int(tok))
        return out

    team_nums = sorted(set(_parse_alliance_csv(found.get("rt")) + _parse_alliance_csv(found.get("bt"))))
    if not team_nums:
        return None
    in_ph = ",".join(["%s"] * len(team_nums))

    team_data = {}
    with DatabaseConnection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT te.team_number, te.year,
                       t.nickname, t.city, t.state_prov, t.country, t.website,
                       COALESCE(d.display_name, d.name) AS district,
                       t.district_key,
                       te.raw, te.ace, te.confidence, te.auto_raw, te.teleop_raw, te.endgame_raw,
                       te.wins, te.losses, te.ties, te.event_perf,
                       te.rank_global, te.rank_country, te.rank_state, te.rank_district,
                       te.count_global, te.count_country, te.count_state, te.count_district
                FROM team_epas te
                LEFT JOIN teams t ON te.team_number = t.team_number
                LEFT JOIN districts d ON (
                    CASE WHEN t.district_key ~ '^[0-9]{{4}}[a-zA-Z]+$'
                         THEN UPPER(SUBSTRING(t.district_key FROM 5))
                         ELSE UPPER(TRIM(t.district_key))
                    END
                ) = d.district_key
                WHERE te.year = %s AND te.team_number IN ({in_ph})
                """,
                (year, *team_nums),
            )
            for row in cursor.fetchall():
                (
                    team_number, yrow, nickname, city, state_prov, country, website, district, district_key,
                    raw, ace, confidence, auto_raw, teleop_raw, endgame_raw,
                    wins, losses, ties, event_perf,
                    rank_global, rank_country, rank_state, rank_district,
                    count_global, count_country, count_state, count_district
                ) = row
                raw_team_data = {
                    "team_number": team_number,
                    "year": yrow,
                    "nickname": nickname,
                    "city": city,
                    "state_prov": state_prov,
                    "country": country,
                    "website": website,
                    "district": district,
                    "district_key": district_key,
                    "raw": raw,
                    "ace": ace,
                    "confidence": confidence,
                    "auto_raw": auto_raw,
                    "teleop_raw": teleop_raw,
                    "endgame_raw": endgame_raw,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "event_perf": _event_perf_from_db(event_perf),
                    "rank_global": rank_global,
                    "rank_country": rank_country,
                    "rank_state": rank_state,
                    "rank_district": rank_district,
                    "count_global": count_global,
                    "count_country": count_country,
                    "count_state": count_state,
                    "count_district": count_district,
                }
                team_data[team_number] = _compress_dict(raw_team_data)

        event_data = {}
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_key, name, start_date, end_date, event_type,
                       district_key, district_abbrev, district_name,
                       city, state_prov, country, website, webcast_type, webcast_channel, week
                FROM events
                WHERE event_key = %s
                """,
                (event_key,),
            )
            er = cursor.fetchone()
            if er:
                (
                    ekey, name, start_date, end_date, event_type,
                    district_key, district_abbrev, district_name,
                    city, state_prov, country, website, webcast_type, webcast_channel, week
                ) = er
                event_data[ekey] = _compress_dict(
                    {
                        "k": ekey,
                        "n": name,
                        "y": year,
                        "sd": start_date,
                        "ed": end_date,
                        "et": event_type,
                        "dk": district_key,
                        "da": district_abbrev,
                        "dn": district_name,
                        "c": city,
                        "s": state_prov,
                        "co": country,
                        "w": website,
                        "wt": webcast_type,
                        "wc": webcast_channel,
                        "wk": week,
                    }
                )

        season_stat_lists = {k: [] for k in ["auto_raw", "teleop_raw", "endgame_raw", "confidence", "ace", "raw"]}
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT auto_raw, teleop_raw, endgame_raw, confidence, ace, raw
                FROM team_epas
                WHERE year = %s
                """,
                (year,),
            )
            for ar, tr, enr, conf, ac, rw in cursor.fetchall():
                if ar is not None:
                    season_stat_lists["auto_raw"].append(float(ar))
                if tr is not None:
                    season_stat_lists["teleop_raw"].append(float(tr))
                if enr is not None:
                    season_stat_lists["endgame_raw"].append(float(enr))
                if conf is not None:
                    season_stat_lists["confidence"].append(float(conf))
                if ac is not None:
                    season_stat_lists["ace"].append(float(ac))
                if rw is not None:
                    season_stat_lists["raw"].append(float(rw))

    return team_data, event_data, event_matches, season_stat_lists


def load_compare_year_from_db(year, team_numbers):
    """
    Minimal load for /compare: EPA rows for the given teams plus event metadata
    for events those teams have in event_perf only (not the full season schedule).
    Skips matches, rankings, event_teams, and awards (large tables).
    """
    team_numbers = sorted({int(t) for t in team_numbers})

    def event_keys_for_compare(yr, team_dict):
        """Event keys from teams' event_perf for this season (same scope as the compare chart)."""
        yp = str(int(yr))
        keys = set()
        for row in (team_dict or {}).values():
            ep = row.get("event_perf")
            if ep is None:
                continue
            if isinstance(ep, str):
                ep = _event_perf_from_db(ep)
            if not isinstance(ep, list):
                continue
            for ev in ep:
                if not isinstance(ev, dict):
                    continue
                ek = (ev.get("event_key") or "").strip()
                if ek and ek.startswith(yp):
                    keys.add(ek)
        return sorted(keys)

    if not team_numbers:
        return {}, {}

    with DatabaseConnection() as conn:
        team_data = {}
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(team_numbers))
            cursor.execute(
                f"""
                SELECT te.team_number, te.year,
                       t.nickname, t.city, t.state_prov, t.country, t.website,
                       COALESCE(d.display_name, d.name) AS district,
                       t.district_key,
                       te.raw, te.ace, te.confidence, te.auto_raw, te.teleop_raw, te.endgame_raw,
                       te.wins, te.losses, te.ties, te.event_perf,
                       te.rank_global, te.rank_country, te.rank_state, te.rank_district,
                       te.count_global, te.count_country, te.count_state, te.count_district
                FROM team_epas te
                LEFT JOIN teams t ON te.team_number = t.team_number
                LEFT JOIN districts d ON (
                    CASE WHEN t.district_key ~ '^[0-9]{{4}}[a-zA-Z]+$'
                         THEN UPPER(SUBSTRING(t.district_key FROM 5))
                         ELSE UPPER(TRIM(t.district_key))
                    END
                ) = d.district_key
                WHERE te.year = %s AND te.team_number IN ({placeholders})
                ORDER BY te.team_number
                """,
                (year, *team_numbers),
            )
            for row in cursor.fetchall():
                (
                    team_number, yrow, nickname, city, state_prov, country, website, district, district_key,
                    raw, ace, confidence, auto_raw, teleop_raw, endgame_raw,
                    wins, losses, ties, event_perf,
                    rank_global, rank_country, rank_state, rank_district,
                    count_global, count_country, count_state, count_district
                ) = row

                raw_team_data = {
                    "team_number": team_number,
                    "year": yrow,
                    "nickname": nickname,
                    "city": city,
                    "state_prov": state_prov,
                    "country": country,
                    "website": website,
                    "district": district,
                    "district_key": district_key,
                    "raw": raw,
                    "ace": ace,
                    "confidence": confidence,
                    "auto_raw": auto_raw,
                    "teleop_raw": teleop_raw,
                    "endgame_raw": endgame_raw,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "event_perf": _event_perf_from_db(event_perf),
                    "rank_global": rank_global,
                    "rank_country": rank_country,
                    "rank_state": rank_state,
                    "rank_district": rank_district,
                    "count_global": count_global,
                    "count_country": count_country,
                    "count_state": count_state,
                    "count_district": count_district,
                }

                team_data[team_number] = _compress_dict(raw_team_data)

        event_keys = event_keys_for_compare(year, team_data)
        event_data = {}
        if event_keys:
            n = len(event_keys)
            in_ph = ",".join(["%s"] * n)
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT event_key, name, start_date, end_date, event_type,
                           district_key, district_abbrev, district_name,
                           city, state_prov, country, website, webcast_type, webcast_channel, week
                    FROM events
                    WHERE event_key IN ({in_ph})
                    ORDER BY event_key
                    """,
                    event_keys,
                )
                for row in cursor.fetchall():
                    (
                        event_key, name, start_date, end_date, event_type,
                        district_key, district_abbrev, district_name,
                        city, state_prov, country, website, webcast_type, webcast_channel, week
                    ) = row
                    event_data[event_key] = _compress_dict({
                        "k": event_key,
                        "n": name,
                        "y": year,
                        "sd": start_date,
                        "ed": end_date,
                        "et": event_type,
                        "dk": district_key,
                        "da": district_abbrev,
                        "dn": district_name,
                        "c": city,
                        "s": state_prov,
                        "co": country,
                        "w": website,
                        "wt": webcast_type,
                        "wc": webcast_channel,
                        "wk": week,
                    })

    return team_data, event_data


def get_team_years_participated(team_number):
    """Return a sorted list of years this team has participated in."""
    with DatabaseConnection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT year FROM team_epas WHERE team_number = %s ORDER BY year DESC", (team_number,))
        years = [row[0] for row in cur.fetchall()]
        cur.close()
    return years


def get_all_team_favorites_counts():
    """Get favorites count for all teams efficiently."""
    favorites_counts = {}
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_key, COUNT(*) as favorites_count
                FROM saved_items 
                WHERE item_type = 'team'
                GROUP BY item_key
            """)
            for team_key, count in cursor.fetchall():
                try:
                    team_number = int(team_key)
                    favorites_counts[team_number] = count
                except ValueError:
                    # Skip invalid team keys
                    continue
    except Exception as e:
        print(f"Error getting favorites counts: {e}")
    
    return favorites_counts

# Load team colors globally for efficient access
try:
    with open('data/team_colors.json', 'r', encoding='utf-8') as f:
        TEAM_COLORS = json.load(f)
except Exception as e:
    print(f"Warning: Could not load team colors: {e}")
    TEAM_COLORS = {} 