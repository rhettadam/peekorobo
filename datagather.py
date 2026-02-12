from dotenv import load_dotenv
import os
import random
import requests
from urllib.parse import urlparse
import psycopg2
from psycopg2 import pool
import json
from collections import defaultdict
import threading
import time
from datetime import date

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

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
        'maxconn': 1000,      # Maximum connections (conservative for 512MB)
        'connect_timeout': 10,
        'options': '-c statement_timeout=300000'  # 5 minute timeout
    }
    
    try:
        pool_obj = pool.ThreadedConnectionPool(**pool_config)
        print(f"✅ Database connection pool created: {pool_config['minconn']}-{pool_config['maxconn']} connections")
        return pool_obj
    except Exception as e:
        print(f"❌ Failed to create connection pool: {e}")
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
        print(f"❌ Error getting connection from pool: {e}")
        raise

def return_pg_connection(conn):
    """Return a connection to the pool."""
    if conn is None:
        return
        
    pool_obj = get_connection_pool()
    try:
        pool_obj.putconn(conn)
    except Exception as e:
        print(f"❌ Error returning connection to pool: {e}")
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
                    print("✅ Database connection pool closed")
                except Exception as e:
                    print(f"❌ Error closing connection pool: {e}")
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

def tba_get(endpoint: str):
    # Cycle through keys by selecting one randomly or using a round-robin approach.
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def load_data():
    def compress_dict(d):
        """Remove any None or empty string values. Keep empty lists and dictionaries."""
        # Special case: preserve empty string for winning_alliance (wa) as it indicates ties
        return {k: v for k, v in d.items() if v not in (None, "") or k == "wa"}

    # === Load team EPA data from PostgreSQL ===
    with DatabaseConnection() as conn:
        team_cursor = conn.cursor()
        
        # Get all team EPA data
        team_cursor.execute("""
            SELECT te.team_number, te.year,
                   t.nickname, t.city, t.state_prov, t.country, t.website,
                   te.normal_epa, te.epa, te.confidence, te.auto_epa, te.teleop_epa, te.endgame_epa,
                   te.wins, te.losses, te.ties, te.event_epas
            FROM team_epas te
            LEFT JOIN teams t ON te.team_number = t.team_number
            ORDER BY te.year, te.team_number
        """)
        
        team_data = {}
        for row in team_cursor.fetchall():
            team_number, year, nickname, city, state_prov, country, website, \
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa, \
            wins, losses, ties, event_epas = row
            
            raw_team_data = {
                "team_number": team_number,
                "year": year,
                "nickname": nickname,
                "city": city,
                "state_prov": state_prov,
                "country": country,
                "website": website,
                "normal_epa": normal_epa,
                "epa": epa,
                "confidence": confidence,
                "auto_epa": auto_epa,
                "teleop_epa": teleop_epa,
                "endgame_epa": endgame_epa,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "event_epas": event_epas
            }
            
            # Parse event_epas from JSON if it's a string
            if raw_team_data["event_epas"] is None:
                raw_team_data["event_epas"] = []
            elif isinstance(raw_team_data["event_epas"], str):
                try:
                    raw_team_data["event_epas"] = json.loads(raw_team_data["event_epas"])
                except json.JSONDecodeError:
                    raw_team_data["event_epas"] = []
            
            # Compress the dictionary
            team = compress_dict(raw_team_data)
            team_data.setdefault(year, {})[team_number] = team

        # === Load event data from PostgreSQL ===
        # Events
        event_cursor = conn.cursor()
        event_cursor.execute("""
            SELECT event_key, name, start_date, end_date, event_type,
                   district_key, district_abbrev, district_name,
                   city, state_prov, country, website, webcast_type, webcast_channel
            FROM events
            ORDER BY event_key
        """)
        
        event_data = {}
        for row in event_cursor.fetchall():
            (
                event_key, name, start_date, end_date, event_type,
                district_key, district_abbrev, district_name,
                city, state_prov, country, website, webcast_type, webcast_channel
            ) = row
            year = int(event_key[:4])
            ev = compress_dict({
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
                "wc": webcast_channel
            })
            event_data.setdefault(year, {})[event_key] = ev

        # Event Teams
        event_cursor.execute("""
            SELECT event_key, team_number, nickname, city, state_prov, country
            FROM event_teams
            ORDER BY event_key, team_number
        """)
        
        EVENT_TEAMS = {}
        for row in event_cursor.fetchall():
            event_key, team_number, nickname, city, state_prov, country = row
            year = int(event_key[:4])
            team = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "nn": nickname,
                "c": city,
                "s": state_prov,
                "co": country
            })
            EVENT_TEAMS.setdefault(year, {}).setdefault(event_key, []).append(team)

        # Rankings
        event_cursor.execute("""
            SELECT event_key, team_number, rank, wins, losses, ties, dq
            FROM event_rankings
            ORDER BY event_key, team_number
        """)
        
        EVENT_RANKINGS = {}
        for row in event_cursor.fetchall():
            event_key, team_number, rank, wins, losses, ties, dq = row
            year = int(event_key[:4])
            ranking = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "rk": rank,
                "w": wins,
                "l": losses,
                "t": ties,
                "dq": dq
            })
            EVENT_RANKINGS.setdefault(year, {}).setdefault(event_key, {})[team_number] = ranking

        # Awards
        event_cursor.execute("""
            SELECT event_key, team_number, award_name
            FROM event_awards
            ORDER BY event_key, team_number
        """)
        
        EVENTS_AWARDS = []
        for row in event_cursor.fetchall():
            event_key, team_number, award_name = row
            try:
                year = int(str(event_key)[:4])
            except Exception:
                year = None
            award = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "an": award_name,
                "y": year
            })
            EVENTS_AWARDS.append(award)

        # Matches
        event_cursor.execute("""
            SELECT match_key, event_key, comp_level, match_number, set_number, 
                   red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time
            FROM event_matches
            ORDER BY event_key, match_number
        """)
        
        EVENT_MATCHES = {}
        for row in event_cursor.fetchall():
            match_key, event_key, comp_level, match_number, set_number, \
            red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time = row
            year = int(event_key[:4])
            match_data = compress_dict({
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
                "pt": predicted_time
            })
            EVENT_MATCHES.setdefault(year, []).append(match_data)

        event_cursor.close()
        team_cursor.close()

    return team_data, event_data, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES

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
                print(f"✅ Loaded {len(_available_avatars)} team avatars into cache")
    
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

def load_data_current_year():
    """Load only current year data for better performance."""
    current_year = 2026
    def compress_dict(d):
        """Remove any None or empty string values. Keep empty lists and dictionaries."""
        # Special case: preserve empty string for winning_alliance (wa) as it indicates ties
        return {k: v for k, v in d.items() if v not in (None, "") or k == "wa"}

    # === Load team EPA data from PostgreSQL for current year only ===
    with DatabaseConnection() as conn:
        team_cursor = conn.cursor()
        
        # Get only current year team EPA data
        team_cursor.execute("""
            SELECT te.team_number, te.year,
                   t.nickname, t.city, t.state_prov, t.country, t.website,
                   te.normal_epa, te.epa, te.confidence, te.auto_epa, te.teleop_epa, te.endgame_epa,
                   te.wins, te.losses, te.event_epas
            FROM team_epas te
            LEFT JOIN teams t ON te.team_number = t.team_number
            WHERE te.year = %s
            ORDER BY te.team_number
        """, (current_year,))
        
        team_data = {current_year: {}}
        for row in team_cursor.fetchall():
            team_number, year, nickname, city, state_prov, country, website, \
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa, \
            wins, losses, event_epas = row
            
            raw_team_data = {
                "team_number": team_number,
                "year": year,
                "nickname": nickname,
                "city": city,
                "state_prov": state_prov,
                "country": country,
                "website": website,
                "normal_epa": normal_epa,
                "epa": epa,
                "confidence": confidence,
                "auto_epa": auto_epa,
                "teleop_epa": teleop_epa,
                "endgame_epa": endgame_epa,
                "wins": wins,
                "losses": losses,
                "event_epas": event_epas
            }
            
            # Parse event_epas from JSON if it's a string
            if raw_team_data["event_epas"] is None:
                raw_team_data["event_epas"] = []
            elif isinstance(raw_team_data["event_epas"], str):
                try:
                    raw_team_data["event_epas"] = json.loads(raw_team_data["event_epas"])
                except json.JSONDecodeError:
                    raw_team_data["event_epas"] = []
            
            # Compress the dictionary
            team = compress_dict(raw_team_data)
            team_data[current_year][team_number] = team

        # === Load event data from PostgreSQL for current year only ===
        # Events
        event_cursor = conn.cursor()
        event_cursor.execute("""
            SELECT event_key, name, start_date, end_date, event_type,
                   district_key, district_abbrev, district_name,
                   city, state_prov, country, website, webcast_type, webcast_channel
            FROM events
            WHERE event_key LIKE %s
            ORDER BY event_key
        """, (f"{current_year}%",))
        
        event_data = {current_year: {}}
        for row in event_cursor.fetchall():
            (
                event_key, name, start_date, end_date, event_type,
                district_key, district_abbrev, district_name,
                city, state_prov, country, website, webcast_type, webcast_channel
            ) = row
            ev = compress_dict({
                "k": event_key,
                "n": name,
                "y": current_year,
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
                "wc": webcast_channel
            })
            event_data[current_year][event_key] = ev

        # Event Teams for current year
        event_cursor.execute("""
            SELECT event_key, team_number, nickname, city, state_prov, country
            FROM event_teams
            WHERE event_key LIKE %s
            ORDER BY event_key, team_number
        """, (f"{current_year}%",))
        
        EVENT_TEAMS = {current_year: {}}
        for row in event_cursor.fetchall():
            event_key, team_number, nickname, city, state_prov, country = row
            team = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "nn": nickname,
                "c": city,
                "s": state_prov,
                "co": country
            })
            EVENT_TEAMS[current_year].setdefault(event_key, []).append(team)

        # Rankings for current year
        event_cursor.execute("""
            SELECT event_key, team_number, rank, wins, losses, ties, dq
            FROM event_rankings
            WHERE event_key LIKE %s
            ORDER BY event_key, team_number
        """, (f"{current_year}%",))
        
        EVENT_RANKINGS = {current_year: {}}
        for row in event_cursor.fetchall():
            event_key, team_number, rank, wins, losses, ties, dq = row
            ranking = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "rk": rank,
                "w": wins,
                "l": losses,
                "t": ties,
                "dq": dq
            })
            EVENT_RANKINGS[current_year].setdefault(event_key, {})[team_number] = ranking

        # Awards for current year
        event_cursor.execute("""
            SELECT event_key, team_number, award_name
            FROM event_awards
            WHERE event_key LIKE %s
            ORDER BY event_key, team_number
        """, (f"{current_year}%",))
        
        EVENTS_AWARDS = []
        for row in event_cursor.fetchall():
            event_key, team_number, award_name = row
            award = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "an": award_name,
                "y": current_year
            })
            EVENTS_AWARDS.append(award)

        # Matches for current year
        event_cursor.execute("""
            SELECT match_key, event_key, comp_level, match_number, set_number, 
                   red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time
            FROM event_matches
            WHERE event_key LIKE %s
            ORDER BY event_key, match_number
        """, (f"{current_year}%",))
        
        EVENT_MATCHES = {current_year: []}
        for row in event_cursor.fetchall():
            match_key, event_key, comp_level, match_number, set_number, \
            red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time = row
            match_data = compress_dict({
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
                "pt": predicted_time
            })
            EVENT_MATCHES[current_year].append(match_data)

        event_cursor.close()
        team_cursor.close()

    return team_data, event_data, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES

def load_search_data():
    """Load minimal data needed for search: event key, event name, team name, team key."""
    # Load teams from JSON
    with open("data/teams.json", "r", encoding="utf-8") as f:
        team_nicknames = json.load(f)
    # Build team_data dict: {year: {team_number: {...}}} for all years
    team_data = {}
    for team_number_str, info in team_nicknames.items():
        try:
            team_number = int(team_number_str)
        except Exception:
            continue
        nickname = info.get("nickname", "")
        last_year = info.get("last_year", None)
        for year in range(1992, 2027):
            team_data.setdefault(year, {})[team_number] = {
                "team_number": team_number,
                "nickname": nickname,
                "last_year": last_year
            }
    # Load events from JSON
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
    return team_data, event_data

def load_year_data(year):
    """Load data for a specific year on-demand."""
    def compress_dict(d):
        """Remove any None or empty string values. Keep empty lists and dictionaries."""
        # Special case: preserve empty string for winning_alliance (wa) as it indicates ties
        return {k: v for k, v in d.items() if v not in (None, "") or k == "wa"}

    def safe_json_load(value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return value or []

    with DatabaseConnection() as conn:
        # === Load team EPA data for specific year ===
        team_data = {}
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT te.team_number, te.year,
                       t.nickname, t.city, t.state_prov, t.country, t.website,
                       te.normal_epa, te.epa, te.confidence, te.auto_epa, te.teleop_epa, te.endgame_epa,
                       te.wins, te.losses, te.ties, te.event_epas
                FROM team_epas te
                LEFT JOIN teams t ON te.team_number = t.team_number
                WHERE te.year = %s
                ORDER BY te.team_number
            """, (year,))
            for row in cursor.fetchall():
                (
                    team_number, year, nickname, city, state_prov, country, website,
                    normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                    wins, losses, ties, event_epas
                ) = row

                raw_team_data = {
                    "team_number": team_number,
                    "year": year,
                    "nickname": nickname,
                    "city": city,
                    "state_prov": state_prov,
                    "country": country,
                    "website": website,
                    "normal_epa": normal_epa,
                    "epa": epa,
                    "confidence": confidence,
                    "auto_epa": auto_epa,
                    "teleop_epa": teleop_epa,
                    "endgame_epa": endgame_epa,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "event_epas": safe_json_load(event_epas)
                }

                team_data[team_number] = compress_dict(raw_team_data)

        # === Load event data for specific year ===
        event_data = {}
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT event_key, name, start_date, end_date, event_type,
                       district_key, district_abbrev, district_name,
                       city, state_prov, country, website, webcast_type, webcast_channel
                FROM events
                WHERE event_key LIKE %s
                ORDER BY event_key
            """, (f"{year}%",))
            for row in cursor.fetchall():
                (
                    event_key, name, start_date, end_date, event_type,
                    district_key, district_abbrev, district_name,
                    city, state_prov, country, website, webcast_type, webcast_channel
                ) = row
                event_data[event_key] = compress_dict({
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
                    "wc": webcast_channel
                })

        # === Load event teams for specific year ===
        EVENT_TEAMS = defaultdict(list)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT event_key, team_number, nickname, city, state_prov, country
                FROM event_teams
                WHERE event_key LIKE %s
                ORDER BY event_key, team_number
            """, (f"{year}%",))
            for event_key, team_number, nickname, city, state_prov, country in cursor.fetchall():
                EVENT_TEAMS[event_key].append(compress_dict({
                    "ek": event_key,
                    "tk": team_number,
                    "nn": nickname,
                    "c": city,
                    "s": state_prov,
                    "co": country
                }))

        # === Load event rankings for specific year ===
        EVENT_RANKINGS = defaultdict(dict)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT event_key, team_number, rank, wins, losses, ties, dq
                FROM event_rankings
                WHERE event_key LIKE %s
                ORDER BY event_key, team_number
            """, (f"{year}%",))
            for event_key, team_number, rank, wins, losses, ties, dq in cursor.fetchall():
                EVENT_RANKINGS[event_key][team_number] = compress_dict({
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
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT event_key, team_number, award_name
                FROM event_awards
                WHERE event_key LIKE %s
                ORDER BY event_key, team_number
            """, (f"{year}%",))
            for event_key, team_number, award_name in cursor.fetchall():
                EVENTS_AWARDS.append(compress_dict({
                    "ek": event_key,
                    "tk": team_number,
                    "an": award_name,
                    "y": year
                }))

        # === Load matches for specific year ===
        EVENT_MATCHES = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT match_key, event_key, comp_level, match_number, set_number, 
                       red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time
                FROM event_matches
                WHERE event_key LIKE %s
                ORDER BY event_key, match_number
            """, (f"{year}%",))
            for row in cursor.fetchall():
                (
                    match_key, event_key, comp_level, match_number, set_number,
                    red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key, predicted_time
                ) = row
                EVENT_MATCHES.append(compress_dict({
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
                    "pt": predicted_time
                }))

    return team_data, event_data, dict(EVENT_TEAMS), dict(EVENT_RANKINGS), EVENTS_AWARDS, EVENT_MATCHES


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