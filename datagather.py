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

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()

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
        return {k: v for k, v in d.items() if v not in (None, "")}

    # === Load team EPA data from PostgreSQL ===
    with DatabaseConnection() as conn:
        team_cursor = conn.cursor()
        
        # Get all team EPA data
        team_cursor.execute("""
            SELECT team_number, year, nickname, city, state_prov, country, website,
                   normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                   wins, losses, event_epas
            FROM team_epas
            ORDER BY year, team_number
        """)
        
        team_data = {}
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
            team_data.setdefault(year, {})[team_number] = team

        # === Load event data from PostgreSQL ===
        # Events
        event_cursor = conn.cursor()
        event_cursor.execute("""
            SELECT event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website
            FROM events
            ORDER BY year, event_key
        """)
        
        event_data = {}
        for row in event_cursor.fetchall():
            event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website = row
            ev = compress_dict({
                "k": event_key,
                "n": name,
                "y": year,
                "sd": start_date,
                "ed": end_date,
                "et": event_type,
                "c": city,
                "s": state_prov,
                "co": country,
                "w": website
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
            SELECT event_key, team_number, award_name, year
            FROM event_awards
            ORDER BY year, event_key, team_number
        """)
        
        EVENTS_AWARDS = []
        for row in event_cursor.fetchall():
            event_key, team_number, award_name, year = row
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
                   red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key
            FROM event_matches
            ORDER BY event_key, match_number
        """)
        
        EVENT_MATCHES = {}
        for row in event_cursor.fetchall():
            match_key, event_key, comp_level, match_number, set_number, \
            red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key = row
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
                "yt": youtube_key
            })
            EVENT_MATCHES.setdefault(year, []).append(match_data)

        event_cursor.close()
        team_cursor.close()

    return team_data, event_data, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES

def get_team_avatar(team_number, year=2025):
    """
    Returns the relative URL path to a team's avatar image if it exists,
    otherwise returns the path to a stock avatar.
    """
    # Use bbot.png for team numbers 9970-9999
    if 9970 <= team_number <= 9999:
        return "/assets/avatars/bbot.png?v=1"
    
    avatar_path = f"assets/avatars/{team_number}.png"
    if os.path.exists(avatar_path):
        return f"/assets/avatars/{team_number}.png?v=1"
    return "/assets/avatars/stock.png"

def load_data_2025():
    """Load only 2025 data for better performance."""
    def compress_dict(d):
        """Remove any None or empty string values. Keep empty lists and dictionaries."""
        return {k: v for k, v in d.items() if v not in (None, "")}

    # === Load team EPA data from PostgreSQL for 2025 only ===
    with DatabaseConnection() as conn:
        team_cursor = conn.cursor()
        
        # Get only 2025 team EPA data
        team_cursor.execute("""
            SELECT team_number, year, nickname, city, state_prov, country, website,
                   normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                   wins, losses, event_epas
            FROM team_epas
            WHERE year = 2025
            ORDER BY team_number
        """)
        
        team_data = {2025: {}}
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
            team_data[2025][team_number] = team

        # === Load event data from PostgreSQL for 2025 only ===
        # Events
        event_cursor = conn.cursor()
        event_cursor.execute("""
            SELECT event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website
            FROM events
            WHERE year = 2025
            ORDER BY event_key
        """)
        
        event_data = {2025: {}}
        for row in event_cursor.fetchall():
            event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website = row
            ev = compress_dict({
                "k": event_key,
                "n": name,
                "y": year,
                "sd": start_date,
                "ed": end_date,
                "et": event_type,
                "c": city,
                "s": state_prov,
                "co": country,
                "w": website
            })
            event_data[2025][event_key] = ev

        # Event Teams for 2025
        event_cursor.execute("""
            SELECT event_key, team_number, nickname, city, state_prov, country
            FROM event_teams
            WHERE event_key LIKE '2025%'
            ORDER BY event_key, team_number
        """)
        
        EVENT_TEAMS = {2025: {}}
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
            EVENT_TEAMS[2025].setdefault(event_key, []).append(team)

        # Rankings for 2025
        event_cursor.execute("""
            SELECT event_key, team_number, rank, wins, losses, ties, dq
            FROM event_rankings
            WHERE event_key LIKE '2025%'
            ORDER BY event_key, team_number
        """)
        
        EVENT_RANKINGS = {2025: {}}
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
            EVENT_RANKINGS[2025].setdefault(event_key, {})[team_number] = ranking

        # Awards for 2025
        event_cursor.execute("""
            SELECT event_key, team_number, award_name, year
            FROM event_awards
            WHERE year = 2025
            ORDER BY event_key, team_number
        """)
        
        EVENTS_AWARDS = []
        for row in event_cursor.fetchall():
            event_key, team_number, award_name, year = row
            award = compress_dict({
                "ek": event_key,
                "tk": team_number,
                "an": award_name,
                "y": year
            })
            EVENTS_AWARDS.append(award)

        # Matches for 2025
        event_cursor.execute("""
            SELECT match_key, event_key, comp_level, match_number, set_number, 
                   red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key
            FROM event_matches
            WHERE event_key LIKE '2025%'
            ORDER BY event_key, match_number
        """)
        
        EVENT_MATCHES = {2025: []}
        for row in event_cursor.fetchall():
            match_key, event_key, comp_level, match_number, set_number, \
            red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key = row
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
                "yt": youtube_key
            })
            EVENT_MATCHES[2025].append(match_data)

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
        for year in range(1992, 2026):
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
        return {k: v for k, v in d.items() if v not in (None, "")}

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
                SELECT team_number, year, nickname, city, state_prov, country, website,
                       normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                       wins, losses, event_epas
                FROM team_epas
                WHERE year = %s
                ORDER BY team_number
            """, (year,))
            for row in cursor.fetchall():
                (
                    team_number, year, nickname, city, state_prov, country, website,
                    normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                    wins, losses, event_epas
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
                    "event_epas": safe_json_load(event_epas)
                }

                team_data[team_number] = compress_dict(raw_team_data)

        # === Load event data for specific year ===
        event_data = {}
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website
                FROM events
                WHERE year = %s
                ORDER BY event_key
            """, (year,))
            for row in cursor.fetchall():
                event_key, name, y, start_date, end_date, event_type, city, state_prov, country, website = row
                event_data[event_key] = compress_dict({
                    "k": event_key,
                    "n": name,
                    "y": y,
                    "sd": start_date,
                    "ed": end_date,
                    "et": event_type,
                    "c": city,
                    "s": state_prov,
                    "co": country,
                    "w": website
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
                SELECT event_key, team_number, award_name, year
                FROM event_awards
                WHERE year = %s
                ORDER BY event_key, team_number
            """, (year,))
            for event_key, team_number, award_name, y in cursor.fetchall():
                EVENTS_AWARDS.append(compress_dict({
                    "ek": event_key,
                    "tk": team_number,
                    "an": award_name,
                    "y": y
                }))

        # === Load matches for specific year ===
        EVENT_MATCHES = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT match_key, event_key, comp_level, match_number, set_number, 
                       red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key
                FROM event_matches
                WHERE event_key LIKE %s
                ORDER BY event_key, match_number
            """, (f"{year}%",))
            for row in cursor.fetchall():
                (
                    match_key, event_key, comp_level, match_number, set_number,
                    red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key
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
                    "yt": youtube_key
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