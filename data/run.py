import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type, stop_after_attempt
import requests
import os
import concurrent.futures
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import random
from typing import Dict, List, Optional, Union
from functools import wraps
import signal
import sys
import threading
import time  # <-- Added for runtime tracking

from epamodels import *

start_time = time.time()

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

import psycopg2
from urllib.parse import urlparse

# Global variables for cleanup
active_executors = []
active_connections = []
shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """Handle Ctrl+C and other termination signals gracefully."""
    print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
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
    
    print("✅ Cleanup complete. Exiting.")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup_executor(executor):
    """Safely shutdown an executor."""
    if executor and hasattr(executor, 'shutdown'):
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            print(f"Warning: Error shutting down executor: {e}")

def cleanup_connection(conn):
    """Safely close a database connection."""
    if conn and not conn.closed:
        try:
            conn.close()
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")

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

def ensure_team_epas_columns():
    """Ensure per-element EPA columns exist in team_epas table."""
    columns = [
        ("l1_epa", "REAL"),
        ("l2_epa", "REAL"),
        ("l3_epa", "REAL"),
        ("l4_epa", "REAL"),
        ("net_epa", "REAL"),
        ("processor_epa", "REAL"),
    ]
    conn = get_pg_connection()
    cur = conn.cursor()
    for col, coltype in columns:
        try:
            cur.execute(f"ALTER TABLE team_epas ADD COLUMN IF NOT EXISTS {col} {coltype}")
        except Exception as e:
            print(f"Warning: Could not add column {col}: {e}")
    conn.commit()
    cur.close()
    conn.close()

def create_epa_tables():
    """Create all necessary tables if they don't exist."""
    # Ensure new columns exist before creating table (safe for existing DBs)
    ensure_team_epas_columns()
    schema = """
    CREATE TABLE IF NOT EXISTS events (
        event_key TEXT PRIMARY KEY,
        name TEXT,
        year INTEGER,
        start_date TEXT,
        end_date TEXT,
        event_type TEXT,
        city TEXT,
        state_prov TEXT,
        country TEXT,
        website TEXT
    );
    CREATE TABLE IF NOT EXISTS event_teams (
        event_key TEXT,
        team_number INTEGER,
        nickname TEXT,
        city TEXT,
        state_prov TEXT,
        country TEXT,
        PRIMARY KEY (event_key, team_number)
    );
    CREATE TABLE IF NOT EXISTS event_rankings (
        event_key TEXT,
        team_number INTEGER,
        rank INTEGER,
        wins INTEGER,
        losses INTEGER,
        ties INTEGER,
        dq INTEGER,
        PRIMARY KEY (event_key, team_number)
    );
    CREATE TABLE IF NOT EXISTS event_matches (
        match_key TEXT PRIMARY KEY,
        event_key TEXT,
        comp_level TEXT,
        match_number INTEGER,
        set_number INTEGER,
        red_teams TEXT,
        blue_teams TEXT,
        red_score INTEGER,
        blue_score INTEGER,
        winning_alliance TEXT,
        youtube_key TEXT
    );
    CREATE TABLE IF NOT EXISTS event_awards (
        event_key TEXT,
        team_number INTEGER,
        award_name TEXT,
        year INTEGER,
        PRIMARY KEY (event_key, team_number, award_name)
    );
    CREATE TABLE IF NOT EXISTS team_epas (
        team_number INTEGER,
        year INTEGER,
        nickname TEXT,
        city TEXT,
        state_prov TEXT,
        country TEXT,
        website TEXT,
        normal_epa REAL,
        epa REAL,
        confidence REAL,
        auto_epa REAL,
        teleop_epa REAL,
        endgame_epa REAL,
        wins INTEGER,
        losses INTEGER,
        event_epas JSONB,
        PRIMARY KEY (team_number, year)
    );
    """
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()

def clear_year_data(year):
    """Delete all data for a specific year from all relevant tables."""
    conn = get_pg_connection()
    cur = conn.cursor()
    for table, year_col in [
        ("events", "year"),
        ("event_teams", "event_key"),
        ("event_rankings", "event_key"),
        ("event_matches", "event_key"),
        ("event_awards", "year"),
        ("team_epas", "year"),
    ]:
        if year_col == "year":
            cur.execute(f"DELETE FROM {table} WHERE year = %s", (year,))
        else:
            cur.execute(f"DELETE FROM {table} WHERE LEFT({year_col}, 4) = %s", (str(year),))
    conn.commit()
    cur.close()
    conn.close()

def insert_event_data(all_data, year):
    """Insert event, teams, rankings, matches, and awards into PostgreSQL."""
    conn = get_pg_connection()
    cur = conn.cursor()
    for i, data in enumerate(tqdm(all_data, desc=f'Inserting {year} events')):
        # Insert event
        cur.execute("""
            INSERT INTO events (event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key) DO UPDATE SET
                name = EXCLUDED.name,
                year = EXCLUDED.year,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                event_type = EXCLUDED.event_type,
                city = EXCLUDED.city,
                state_prov = EXCLUDED.state_prov,
                country = EXCLUDED.country,
                website = EXCLUDED.website
        """, data["event"])
        # Insert teams
        if data["teams"]:
            cur.executemany("""
                INSERT INTO event_teams (event_key, team_number, nickname, city, state_prov, country)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    city = EXCLUDED.city,
                    state_prov = EXCLUDED.state_prov,
                    country = EXCLUDED.country
            """, data["teams"])
        # Insert rankings
        if data["rankings"]:
            cur.executemany("""
                INSERT INTO event_rankings (event_key, team_number, rank, wins, losses, ties, dq)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    rank = EXCLUDED.rank,
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    ties = EXCLUDED.ties,
                    dq = EXCLUDED.dq
            """, data["rankings"])
        # Insert matches
        if data["matches"]:
            cur.executemany("""
                INSERT INTO event_matches (match_key, event_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_key) DO UPDATE SET
                    event_key = EXCLUDED.event_key,
                    comp_level = EXCLUDED.comp_level,
                    match_number = EXCLUDED.match_number,
                    set_number = EXCLUDED.set_number,
                    red_teams = EXCLUDED.red_teams,
                    blue_teams = EXCLUDED.blue_teams,
                    red_score = EXCLUDED.red_score,
                    blue_score = EXCLUDED.blue_score,
                    winning_alliance = EXCLUDED.winning_alliance,
                    youtube_key = EXCLUDED.youtube_key
            """, data["matches"])
        # Insert awards
        if data["awards"]:
            cur.executemany("""
                INSERT INTO event_awards (event_key, team_number, award_name, year)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_key, team_number, award_name) DO NOTHING
            """, data["awards"])
    conn.commit()
    cur.close()
    conn.close()

def insert_team_epa(result, year):
    """Insert or update a team's EPA data for a given year."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO team_epas (team_number, year, nickname, city, state_prov, country, website,
                               normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                               wins, losses, event_epas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_number, year) DO UPDATE SET
            nickname = EXCLUDED.nickname,
            city = EXCLUDED.city,
            state_prov = EXCLUDED.state_prov,
            country = EXCLUDED.country,
            website = EXCLUDED.website,
            normal_epa = EXCLUDED.normal_epa,
            epa = EXCLUDED.epa,
            confidence = EXCLUDED.confidence,
            auto_epa = EXCLUDED.auto_epa,
            teleop_epa = EXCLUDED.teleop_epa,
            endgame_epa = EXCLUDED.endgame_epa,
            wins = EXCLUDED.wins,
            losses = EXCLUDED.losses,
            event_epas = EXCLUDED.event_epas
    """, (
        result.get("team_number"),
        year,
        result.get("nickname"),
        result.get("city"),
        result.get("state_prov"),
        result.get("country"),
        result.get("website"),
        result.get("normal_epa"),
        result.get("epa"),
        result.get("confidence"),
        result.get("auto_epa"),
        result.get("teleop_epa"),
        result.get("endgame_epa"),
        result.get("wins"),
        result.get("losses"),
        json.dumps(result.get("event_epas", []))
    ))
    conn.commit()
    cur.close()
    conn.close()

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

def get_teams_for_year(year):
    """Return a list of all teams that played in a given year, including website from team_epas if available."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT et.team_number, et.nickname, et.city, et.state_prov, et.country, te.website
        FROM event_teams et
        LEFT JOIN team_epas te ON et.team_number = te.team_number AND te.year = %s
        WHERE LEFT(et.event_key, 4) = %s
    """, (year, str(year)))
    teams = []
    for row in cur.fetchall():
        teams.append({
            "team_number": row[0],
            "nickname": row[1],
            "city": row[2],
            "state_prov": row[3],
            "country": row[4],
            "website": row[5] if row[5] else "N/A",
            "key": f"frc{row[0]}"
        })
    cur.close()
    conn.close()
    return teams

def get_existing_event_data(event_key):
    """Get existing event data from database for comparison."""
    conn = get_pg_connection()
    cur = conn.cursor()
    
    # Get event
    cur.execute("SELECT name, year, start_date, end_date, event_type, city, state_prov, country, website FROM events WHERE event_key = %s", (event_key,))
    event_row = cur.fetchone()
    
    # Get teams
    cur.execute("SELECT team_number, nickname, city, state_prov, country FROM event_teams WHERE event_key = %s", (event_key,))
    teams = {row[0]: {"nickname": row[1], "city": row[2], "state_prov": row[3], "country": row[4]} for row in cur.fetchall()}
    
    # Get rankings
    cur.execute("SELECT team_number, rank, wins, losses, ties, dq FROM event_rankings WHERE event_key = %s", (event_key,))
    rankings = {row[0]: {"rank": row[1], "wins": row[2], "losses": row[3], "ties": row[4], "dq": row[5]} for row in cur.fetchall()}
    
    # Get matches
    cur.execute("SELECT match_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key FROM event_matches WHERE event_key = %s", (event_key,))
    matches = {row[0]: {"comp_level": row[1], "match_number": row[2], "set_number": row[3], "red_teams": row[4], "blue_teams": row[5], "red_score": row[6], "blue_score": row[7], "winning_alliance": row[8], "youtube_key": row[9]} for row in cur.fetchall()}
    
    # Get awards
    cur.execute("SELECT team_number, award_name FROM event_awards WHERE event_key = %s", (event_key,))
    awards = set((row[0], row[1]) for row in cur.fetchall())
    
    cur.close()
    conn.close()
    
    return {
        "event": event_row,
        "teams": teams,
        "rankings": rankings,
        "matches": matches,
        "awards": awards
    }

def get_existing_team_epa(team_number, year):
    """Get existing team EPA data from database for comparison."""
    conn = get_pg_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT nickname, city, state_prov, country, website, normal_epa, epa, confidence, 
               auto_epa, teleop_epa, endgame_epa, wins, losses, event_epas
        FROM team_epas WHERE team_number = %s AND year = %s
    """, (team_number, year))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        # Handle event_epas field - it might be a JSON string or already parsed list
        event_epas_raw = row[13]
        if event_epas_raw is None:
            event_epas = []
        elif isinstance(event_epas_raw, str):
            try:
                event_epas = json.loads(event_epas_raw)
            except (json.JSONDecodeError, TypeError):
                event_epas = []
        elif isinstance(event_epas_raw, list):
            event_epas = event_epas_raw
        else:
            event_epas = []
        
        return {
            "nickname": row[0],
            "city": row[1],
            "state_prov": row[2],
            "country": row[3],
            "website": row[4],
            "normal_epa": row[5],
            "epa": row[6],
            "confidence": row[7],
            "auto_epa": row[8],
            "teleop_epa": row[9],
            "endgame_epa": row[10],
            "wins": row[11],
            "losses": row[12],
            "event_epas": event_epas
        }
    return None

def data_has_changed(existing, new_data, data_type):
    """Compare existing data with new data to determine if an update is needed."""
    if not existing:
        return True  # No existing data, needs to be inserted
    
    if data_type == "event":
        existing_event = existing["event"]
        if not existing_event:
            return True
        
        new_event = new_data["event"]
        return (
            existing_event[0] != new_event[1] or  # name
            existing_event[2] != new_event[2] or  # year
            existing_event[3] != new_event[3] or  # start_date
            existing_event[4] != new_event[4] or  # end_date
            existing_event[5] != new_event[5] or  # event_type
            existing_event[6] != new_event[6] or  # city
            existing_event[7] != new_event[7] or  # state_prov
            existing_event[8] != new_event[8] or  # country
            existing_event[9] != new_event[9]     # website
        )
    
    elif data_type == "teams":
        existing_teams = existing["teams"]
        new_teams = new_data["teams"]
        
        # Check if team lists are different
        existing_team_nums = set(existing_teams.keys())
        new_team_nums = set(team[1] for team in new_teams)
        
        if existing_team_nums != new_team_nums:
            return True
        
        # Check if any team data has changed
        for team_data in new_teams:
            team_num = team_data[1]
            if team_num not in existing_teams:
                return True
            
            existing_team = existing_teams[team_num]
            if (
                existing_team["nickname"] != team_data[2] or
                existing_team["city"] != team_data[3] or
                existing_team["state_prov"] != team_data[4] or
                existing_team["country"] != team_data[5]
            ):
                return True
        
        return False
    
    elif data_type == "rankings":
        existing_rankings = existing["rankings"]
        new_rankings = new_data["rankings"]
        
        # Check if ranking lists are different
        existing_team_nums = set(existing_rankings.keys())
        new_team_nums = set(ranking[1] for ranking in new_rankings)
        
        if existing_team_nums != new_team_nums:
            return True
        
        # Check if any ranking data has changed
        for ranking_data in new_rankings:
            team_num = ranking_data[1]
            if team_num not in existing_rankings:
                return True
            
            existing_ranking = existing_rankings[team_num]
            if (
                existing_ranking["rank"] != ranking_data[2] or
                existing_ranking["wins"] != ranking_data[3] or
                existing_ranking["losses"] != ranking_data[4] or
                existing_ranking["ties"] != ranking_data[5] or
                existing_ranking["dq"] != ranking_data[6]
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
                existing_match["youtube_key"] != match_data[10]
            ):
                return True
        
        return False
    
    elif data_type == "awards":
        existing_awards = existing["awards"]
        new_awards = set((award[1], award[2]) for award in new_data["awards"])
        
        return existing_awards != new_awards
    
    elif data_type == "team_epa":
        # For team EPA, we'll do a more detailed comparison
        if not existing:
            return True
        
        # Compare key EPA values with tolerance for floating point differences
        def float_equal(a, b, tolerance=0.01):
            return abs(a - b) < tolerance
        
        if (
            not float_equal(existing["normal_epa"], new_data["normal_epa"]) or
            not float_equal(existing["epa"], new_data["epa"]) or
            not float_equal(existing["confidence"], new_data["confidence"]) or
            not float_equal(existing["auto_epa"], new_data["auto_epa"]) or
            not float_equal(existing["teleop_epa"], new_data["teleop_epa"]) or
            not float_equal(existing["endgame_epa"], new_data["endgame_epa"]) or
            existing["wins"] != new_data["wins"] or
            existing["losses"] != new_data["losses"] or
            existing["nickname"] != new_data["nickname"] or
            existing["city"] != new_data["city"] or
            existing["state_prov"] != new_data["state_prov"] or
            existing["country"] != new_data["country"] or
            existing["website"] != new_data["website"]
        ):
            return True
        
        # Compare event_epas (this is more complex)
        existing_event_epas = {epa.get("event_key"): epa for epa in existing["event_epas"]}
        new_event_epas = {epa.get("event_key"): epa for epa in new_data["event_epas"]}
        
        if set(existing_event_epas.keys()) != set(new_event_epas.keys()):
            return True
        
        for event_key, new_epa in new_event_epas.items():
            if event_key not in existing_event_epas:
                return True
            
            existing_epa = existing_event_epas[event_key]
            if (
                not float_equal(existing_epa.get("overall", 0), new_epa.get("overall", 0)) or
                not float_equal(existing_epa.get("confidence", 0), new_epa.get("confidence", 0)) or
                existing_epa.get("match_count", 0) != new_epa.get("match_count", 0)
            ):
                return True
        
        return False
    
    return True  # Default to updating if we don't know

def optimized_create_event_db(year):
    """Create and populate the events database for the specified year, only updating what's changed."""
    print(f"\n🧹 Optimized events database update for {year}...")
    
    # Create PostgreSQL tables if they don't exist
    create_epa_tables()
    
    try:
        events = tba_get(f"events/{year}")
    except Exception as e:
        print(f"❌ Failed to load events for {year}: {e}")
        return
    
    events_to_process = []
    events_skipped = 0
    
    print(f"🔍 Checking {len(events)} events for updates...")
    
    for event in events:
        if shutdown_event.is_set():
            print("🛑 Shutdown requested, stopping event processing...")
            return
            
        event_key = event["key"]
        
        # Get existing data for comparison
        existing_data = get_existing_event_data(event_key)
        
        # Check if event needs updating
        if not existing_data["event"]:
            # New event, needs full processing
            events_to_process.append(event)
            continue
        
        # Check if event has ended
        end_date = existing_data["event"][4]  # end_date
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                if end_date_obj < datetime.now():
                    # Event has ended, skip unless it's very recent (within last 7 days)
                    if (datetime.now() - end_date_obj).days > 7:
                        events_skipped += 1
                        continue
            except Exception:
                pass  # Bad date format, process anyway
        
        # For ongoing or recent events, check if data has changed
        events_to_process.append(event)

    print(f"📊 Processing {len(events_to_process)} events, skipping {events_skipped} completed events")

    def fetch_and_compare(event):
        if shutdown_event.is_set():
            return None
            
        key = event["key"]
        existing_data = get_existing_event_data(key)
        
        # Fetch new data
        new_data = {
            "event": (
                key, event.get("name"), year,
                event.get("start_date"), event.get("end_date"),
                event.get("event_type_string"), event.get("city"),
                event.get("state_prov"), event.get("country"),
                event.get("website")
            ),
            "teams": [], "rankings": [], "matches": [], "awards": []
        }
        
        # Fetch teams
        try:
            teams = tba_get(f"event/{key}/teams")
            for t in teams:
                t_num = t.get("team_number")
                new_data["teams"].append((key, t_num, t.get("nickname"),
                                          t.get("city"), t.get("state_prov"), t.get("country")))
        except:
            pass
        
        # Fetch rankings
        try:
            ranks = tba_get(f"event/{key}/rankings")
            for r in ranks.get("rankings", []):
                record = r.get("record", {})
                t_num = int(r.get("team_key", "frc0")[3:])
                new_data["rankings"].append((key, t_num, r.get("rank"),
                                             record.get("wins"), record.get("losses"),
                                             record.get("ties"), r.get("dq")))
        except:
            pass
        
        # Fetch matches
        try:
            matches = tba_get(f"event/{key}/matches")
            for m in matches:
                new_data["matches"].append((
                    m["key"], key, m["comp_level"], m["match_number"],
                    m["set_number"],
                    ",".join(str(int(t[3:])) for t in m["alliances"]["red"]["team_keys"]),
                    ",".join(str(int(t[3:])) for t in m["alliances"]["blue"]["team_keys"]),
                    m["alliances"]["red"]["score"], m["alliances"]["blue"]["score"],
                    m.get("winning_alliance"),
                    next((v["key"] for v in m.get("videos", []) if v["type"] == "youtube"), None)
                ))
        except:
            pass
        
        # Fetch awards
        try:
            awards = tba_get(f"event/{key}/awards")
            for aw in awards:
                for r in aw.get("recipient_list", []):
                    if r.get("team_key"):
                        t_num = int(r["team_key"][3:])
                        new_data["awards"].append((key, t_num, aw.get("name"), year))
        except:
            pass
        
        # Determine what needs updating
        updates_needed = {
            "event": data_has_changed(existing_data, new_data, "event"),
            "teams": data_has_changed(existing_data, new_data, "teams"),
            "rankings": data_has_changed(existing_data, new_data, "rankings"),
            "matches": data_has_changed(existing_data, new_data, "matches"),
            "awards": data_has_changed(existing_data, new_data, "awards")
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
                print("🛑 Shutdown requested, stopping analysis...")
                break
                
            try:
                result = f.result()
                if result:
                    all_results.append(result)
            except Exception as e:
                print(f"❌ Error processing event: {e}")
    finally:
        if executor:
            cleanup_executor(executor)
            if executor in active_executors:
                active_executors.remove(executor)

    if shutdown_event.is_set():
        print("🛑 Shutdown requested, stopping event database update...")
        return

    # Count what needs updating
    total_events = len(all_results)
    events_with_changes = sum(1 for r in all_results if r["has_changes"])
    event_updates = sum(1 for r in all_results if r["updates_needed"]["event"])
    team_updates = sum(1 for r in all_results if r["updates_needed"]["teams"])
    ranking_updates = sum(1 for r in all_results if r["updates_needed"]["rankings"])
    match_updates = sum(1 for r in all_results if r["updates_needed"]["matches"])
    award_updates = sum(1 for r in all_results if r["updates_needed"]["awards"])
    
    print(f"\n📈 Update Summary for {year}:")
    print(f"  Total events processed: {total_events}")
    print(f"  Events with changes: {events_with_changes}")
    print(f"  Event data updates: {event_updates}")
    print(f"  Team data updates: {team_updates}")
    print(f"  Ranking updates: {ranking_updates}")
    print(f"  Match updates: {match_updates}")
    print(f"  Award updates: {award_updates}")

    # Only update what's changed
    if events_with_changes > 0:
        optimized_insert_event_data(all_results, year)
        print(f"\n✅ {year} events optimized update complete")
    else:
        print(f"\n✅ No updates needed for {year} events")

def optimized_insert_event_data(results, year):
    """Insert only the changed data into PostgreSQL."""
    conn = get_pg_connection()
    cur = conn.cursor()
    
    for result in tqdm(results, desc="Updating changed data"):
        if not result["has_changes"]:
            continue
            
        data = result["data"]
        updates = result["updates_needed"]
        
        # Update event if needed
        if updates["event"]:
            cur.execute("""
                INSERT INTO events (event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    year = EXCLUDED.year,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    event_type = EXCLUDED.event_type,
                    city = EXCLUDED.city,
                    state_prov = EXCLUDED.state_prov,
                    country = EXCLUDED.country,
                    website = EXCLUDED.website
            """, data["event"])
        
        # Update teams if needed
        if updates["teams"] and data["teams"]:
            # Delete existing teams for this event and reinsert
            cur.execute("DELETE FROM event_teams WHERE event_key = %s", (data["event"][0],))
            cur.executemany("""
                INSERT INTO event_teams (event_key, team_number, nickname, city, state_prov, country)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, data["teams"])
        
        # Update rankings if needed
        if updates["rankings"] and data["rankings"]:
            # Delete existing rankings for this event and reinsert
            cur.execute("DELETE FROM event_rankings WHERE event_key = %s", (data["event"][0],))
            cur.executemany("""
                INSERT INTO event_rankings (event_key, team_number, rank, wins, losses, ties, dq)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, data["rankings"])
        
        # Update matches if needed
        if updates["matches"] and data["matches"]:
            # Delete existing matches for this event and reinsert
            cur.execute("DELETE FROM event_matches WHERE event_key = %s", (data["event"][0],))
            cur.executemany("""
                INSERT INTO event_matches (match_key, event_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data["matches"])
        
        # Update awards if needed
        if updates["awards"] and data["awards"]:
            # Delete existing awards for this event and reinsert
            cur.execute("DELETE FROM event_awards WHERE event_key = %s", (data["event"][0],))
            cur.executemany("""
                INSERT INTO event_awards (event_key, team_number, award_name, year)
                VALUES (%s, %s, %s, %s)
            """, data["awards"])
    
    conn.commit()
    cur.close()
    conn.close()

def optimized_fetch_and_store_team_data(year):
    """Fetch and store team data, only updating what's changed."""
    optimized_create_event_db(year)
    
    if shutdown_event.is_set():
        print("🛑 Shutdown requested, stopping team data processing...")
        return
        
    print(f"\nProcessing year {year} teams...")

    # Get all teams directly from PostgreSQL
    all_teams = get_teams_for_year(year)
    print(f"Total unique teams found from events: {len(all_teams)}")

    def fetch_and_compare_team(team):
        if shutdown_event.is_set():
            return None
            
        team_number = team["team_number"]
        
        # Get existing EPA data for comparison
        existing_epa = get_existing_team_epa(team_number, year)
        
        # Fetch new EPA data
        new_epa_data = fetch_team_components(team, year)
        
        if not new_epa_data:
            return None
        
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
                print("🛑 Shutdown requested, stopping team analysis...")
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
                except:
                    pass
                failed_teams.append(f"{team_info}: {str(e)}")
                print(f"Failed to process {team_info}: {e}")
                continue
    finally:
        if executor:
            cleanup_executor(executor)
            if executor in active_executors:
                active_executors.remove(executor)
    
    if shutdown_event.is_set():
        print("🛑 Shutdown requested, stopping team data update...")
        return
    
    print(f"\n📊 Team Update Summary for {year}:")
    print(f"  Total teams processed: {len(all_teams)}")
    print(f"  Teams updated: {updated_count}")
    print(f"  Teams skipped (no changes): {skipped_count}")
    print(f"  Teams failed: {len(failed_teams)}")
    
    if failed_teams:
        print(f"❌ Failed to process {len(failed_teams)} teams:")
        for failed in failed_teams[:10]:
            print(f"  - {failed}")
        if len(failed_teams) > 10:
            print(f"  ... and {len(failed_teams) - 10} more")
    
# Replace the old functions with the optimized versions
create_event_db = optimized_create_event_db
fetch_and_store_team_data = optimized_fetch_and_store_team_data

# Confidence calculation constants
CONFIDENCE_WEIGHTS = {
    "consistency": 0.35,
    "dominance": 0.35,
    "record_alignment": 0.10,
    "veteran": 0.10,
    "events": 0.10,
}

CONFIDENCE_THRESHOLDS = {
    "high": 0.85,  # Lower threshold for high confidence boost
    "low": 0.65,   # Higher threshold for low confidence reduction
}

CONFIDENCE_MULTIPLIERS = {
    "high_boost": 1.1,  # Reduced multiplier for high confidence
    "low_reduction": 0.9  # Increased multiplier for low confidence
}

EVENT_BOOSTS = {
    1: 0.5,   # Single event
    2: 0.9,  # Two events
    3: 1.0    # Three or more events
}

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
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

def get_team_experience(team_number: int, up_to_year: int) -> int:
    """
    Determine how many years a team has competed up to and including up_to_year.
    Returns the number of years of experience (1 for first year, 2 for second year, etc.)
    """
    try:
        return get_team_experience_pg(team_number, up_to_year)
    except Exception as e:
        print(f"Failed to get team experience: {e}")
        return 1  # Default to first year if we can't determine

def get_veteran_boost(years: int) -> float:
    """
    Calculate veteran boost based on years of experience.
    First year: 0.2
    Second year: 0.4
    Third year: 0.6
    Fourth year and beyond: 1.0
    """
    if years <= 1:
        return 0.2
    elif years == 2:
        return 0.4
    elif years == 3:
        return 0.6
    else:
        return 1.0

def calculate_confidence(consistency: float, dominance: float, event_boost: float, team_number: int, wins: int = 0, losses: int = 0, year: int = None) -> tuple[float, float, float]:
    """
    Calculate confidence score using universal parameters.
    Returns (raw_confidence, capped_confidence, record_alignment)
    """
    years = get_team_experience(team_number, year) if year is not None else get_team_experience(team_number, 2025)
    veteran_boost = get_veteran_boost(years)
    
    # Calculate record alignment based on win-loss record
    total_matches = wins + losses
    if total_matches > 0:
        win_rate = wins / total_matches
        # Scale win rate to be between 0.7 and 1.0
        # 0% win rate = 0.7, 50% win rate = 0.85, 100% win rate = 1.0
        record_alignment = 0.7 + (win_rate * 0.3)
    else:
        record_alignment = 0.7  # Default to middle value if no matches
    
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

def calculate_event_epa(matches: List[Dict], team_key: str, team_number: int) -> Dict:
    importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    breakdowns = []
    dominance_scores = []
    event_wins = 0
    event_losses = 0
    event_ties = 0  # Add tie counter

    # --- Per-element EPA for 2025 ---
    l1_points_sum = l2_points_sum = l3_points_sum = l4_points_sum = 0.0
    net_points_sum = processor_points_sum = 0.0
    l1_count = l2_count = l3_count = l4_count = 0
    net_count = processor_count = 0
    # ---

    # Get the year from the first match's event key
    year = matches[0]["event_key"][:4] if matches else "2025"

    # Get the appropriate scoring functions for this year
    try:
        auto_func = globals()[f"auto_{year}"]
        teleop_func = globals()[f"teleop_{year}"]
        endgame_func = globals()[f"endgame_{year}"]
    except KeyError:
        print(f"Warning: No scoring functions found for year {year}, using 2025 functions")
        auto_func = auto_2025
        teleop_func = teleop_2025
        endgame_func = endgame_2025

    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent_alliance = "blue" if alliance == "red" else "red"

        # Track wins/losses/ties
        winning_alliance = match.get("winning_alliance", "")
        if winning_alliance == alliance:
            event_wins += 1
        elif winning_alliance and winning_alliance != alliance:
            event_losses += 1
        elif not winning_alliance:  # Tie
            event_ties += 1

        team_keys = match["alliances"][alliance].get("team_keys", [])
        team_count = len(team_keys)
        index = team_keys.index(team_key) + 1

        # Safely get and validate breakdown
        breakdown = match.get("score_breakdown", {})
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

        # --- Per-element EPA for 2025 ---
        if year == "2025":
            # Auto phase
            auto_reef = alliance_breakdown.get("autoReef", {})
            l1_auto = auto_reef.get("trough", 0)
            l2_auto = auto_reef.get("tba_botRowCount", 0)
            l3_auto = auto_reef.get("tba_midRowCount", 0)
            l4_auto = auto_reef.get("tba_topRowCount", 0)
            # Teleop phase
            teleop_reef = alliance_breakdown.get("teleopReef", {})
            l1_teleop = teleop_reef.get("tba_botRowCount", 0)
            l2_teleop = teleop_reef.get("tba_midRowCount", 0)
            l3_teleop = teleop_reef.get("tba_topRowCount", 0)
            l4_teleop = teleop_reef.get("trough", 0)
            # Points: auto (l1:3, l2:4, l3:6, l4:7), teleop (l1:2, l2:3, l3:4, l4:5)
            l1_points_sum += l1_auto * 3 + l1_teleop * 2
            l2_points_sum += l2_auto * 4 + l2_teleop * 3
            l3_points_sum += l3_auto * 6 + l3_teleop * 4
            l4_points_sum += l4_auto * 7 + l4_teleop * 5
            l1_count += 1
            l2_count += 1
            l3_count += 1
            l4_count += 1
            # net: netAlgaeCount (4 pts, teleop only)
            net = alliance_breakdown.get("netAlgaeCount", 0)
            net_points_sum += net * 4
            net_count += 1
            # processor: wallAlgaeCount (2.5 pts, teleop only)
            processor = alliance_breakdown.get("wallAlgaeCount", 0)
            processor_points_sum += processor * 2.5
            processor_count += 1
        # ---

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
            dominance_scores.append(min(1.0, max(0.0, norm_margin)))
            match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
            decay = 1.0 
            if overall_epa is None:
                overall_epa = actual_overall
                auto_epa = actual_auto
                endgame_epa = actual_endgame
                teleop_epa = actual_teleop
                continue
            K = 0.4
            K *= match_importance * decay
            delta_auto = K * (actual_auto - auto_epa)
            delta_teleop = K * (actual_teleop - teleop_epa)
            delta_endgame = K * (actual_endgame - endgame_epa)
            auto_epa += delta_auto
            teleop_epa += delta_teleop
            endgame_epa += delta_endgame
            overall_epa = auto_epa + teleop_epa + endgame_epa
            contributions.append(actual_overall)
        except Exception as e:
            print(f"Warning: Error processing match {match.get('key', 'unknown')}: {str(e)}")

    if not match_count:
        base = {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "match_count": 0, "raw_confidence": 0.0,
            "consistency": 0.0, "dominance": 0.0,
            "event_boost": 0.0, "veteran_boost": 0.0,
            "years_experience": 0, "weights": CONFIDENCE_WEIGHTS,
            "record_alignment": 0.0, "wins": event_wins,
            "losses": event_losses, "ties": event_ties
        }
        if year == "2025":
            base.update({
                "l1_epa": 0.0, "l2_epa": 0.0, "l3_epa": 0.0, "l4_epa": 0.0,
                "net_epa": 0.0, "processor_epa": 0.0
            })
        return base

    if len(contributions) >= 2:
        peak = max(contributions)
        stdev = statistics.stdev(contributions)
        consistency = max(0.0, 1.0 - stdev / (peak + 1e-6))
    else:
        consistency = 1.0

    dominance = min(1., statistics.mean(dominance_scores)) if dominance_scores else 0.0

    event_keys = get_team_events(team_number, int(year))
    total_events = len(event_keys)
    event_boost = EVENT_BOOSTS.get(min(total_events, 3), EVENT_BOOSTS[3])
    raw_confidence, confidence, record_alignment = calculate_confidence(consistency, dominance, event_boost, team_number, event_wins, event_losses, int(year))
    actual_epa = (overall_epa * confidence) if overall_epa is not None else 0.0
    years = get_team_experience(team_number, int(year))
    veteran_boost = get_veteran_boost(years)

    result = {
        "overall": round(overall_epa, 2) if overall_epa is not None else 0.0,
        "auto": round(auto_epa, 2) if auto_epa is not None else 0.0,
        "teleop": round(teleop_epa, 2) if teleop_epa is not None else 0.0,
        "endgame": round(endgame_epa, 2) if endgame_epa is not None else 0.0,
        "confidence": round(confidence, 2),
        "actual_epa": round(actual_epa, 2),
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
    if year == "2025":
        # Compute per-element EPA as average points per match
        result.update({
            "l1_epa": round(l1_points_sum / l1_count, 2) if l1_count else 0.0,
            "l2_epa": round(l2_points_sum / l2_count, 2) if l2_count else 0.0,
            "l3_epa": round(l3_points_sum / l3_count, 2) if l3_count else 0.0,
            "l4_epa": round(l4_points_sum / l4_count, 2) if l4_count else 0.0,
            "net_epa": round(net_points_sum / net_count, 2) if net_count else 0.0,
            "processor_epa": round(processor_points_sum / processor_count, 2) if processor_count else 0.0
        })
    return result

def aggregate_overall_epa(event_epas: List[Dict]) -> Dict:
    if not event_epas:
        base = {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0, "ties": 0
        }
        # Add per-element EPA for 2025
        base.update({
            "l1_epa": 0.0, "l2_epa": 0.0, "l3_epa": 0.0, "l4_epa": 0.0,
            "net_epa": 0.0, "processor_epa": 0.0
        })
        return base

    # Filter out events with no valid matches or zero EPAs
    valid_events = [
        epa_data for epa_data in event_epas 
        if epa_data.get("match_count", 0) > 0 and epa_data["overall"] > 0
    ]

    if not valid_events:
        base = {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0, "ties": 0
        }
        base.update({
            "l1_epa": 0.0, "l2_epa": 0.0, "l3_epa": 0.0, "l4_epa": 0.0,
            "net_epa": 0.0, "processor_epa": 0.0
        })
        return base

    total_overall = 0.0
    total_auto = 0.0
    total_teleop = 0.0
    total_endgame = 0.0
    total_actual_epa = 0.0
    total_match_count = 0
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
    # Per-element EPA sums for 2025
    l1_sum = l2_sum = l3_sum = l4_sum = 0.0
    net_sum = processor_sum = 0.0
    l1_count = l2_count = l3_count = l4_count = 0
    net_count = processor_count = 0

    # Use a weighted average based on match count per event
    for epa_data in valid_events:
        match_count = epa_data.get("match_count", 0)
        if match_count == 0: # Skip events with no matches
            continue
        total_overall += epa_data["overall"] * match_count
        total_auto += epa_data["auto"] * match_count
        total_teleop += epa_data["teleop"] * match_count
        total_endgame += epa_data["endgame"] * match_count
        total_actual_epa += epa_data["actual_epa"] * match_count
        total_match_count += match_count
        total_confidence += epa_data["confidence"] * match_count
        total_consistency += epa_data["consistency"] * match_count
        total_dominance += epa_data["dominance"] * match_count
        total_veteran_boost += epa_data["veteran_boost"] * match_count
        total_event_boost += epa_data["event_boost"] * match_count
        total_record_alignment += epa_data["record_alignment"] * match_count
        total_wins += epa_data["wins"]
        total_losses += epa_data["losses"]
        total_ties += epa_data.get("ties", 0)
        total_events += 1
        # Per-element EPA for 2025
        if "l1_epa" in epa_data:
            l1_sum += epa_data["l1_epa"] * match_count
            l1_count += match_count
        if "l2_epa" in epa_data:
            l2_sum += epa_data["l2_epa"] * match_count
            l2_count += match_count
        if "l3_epa" in epa_data:
            l3_sum += epa_data["l3_epa"] * match_count
            l3_count += match_count
        if "l4_epa" in epa_data:
            l4_sum += epa_data["l4_epa"] * match_count
            l4_count += match_count
        if "net_epa" in epa_data:
            net_sum += epa_data["net_epa"] * match_count
            net_count += match_count
        if "processor_epa" in epa_data:
            processor_sum += epa_data["processor_epa"] * match_count
            processor_count += match_count
    if total_match_count == 0:
        base = {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0, "ties": 0
        }
        base.update({
            "l1_epa": 0.0, "l2_epa": 0.0, "l3_epa": 0.0, "l4_epa": 0.0,
            "net_epa": 0.0, "processor_epa": 0.0
        })
        return base

    avg_confidence = total_confidence / total_match_count
    avg_consistency = total_consistency / total_match_count
    avg_dominance = total_dominance / total_match_count
    avg_veteran_boost = total_veteran_boost / total_match_count
    avg_event_boost = total_event_boost / total_match_count
    avg_record_alignment = total_record_alignment / total_match_count
    weights = valid_events[0]["weights"]  # Weights are constant across events
    consistency_component = weights["consistency"] * avg_consistency
    record_component = weights["record_alignment"] * avg_record_alignment
    veteran_component = weights["veteran"] * avg_veteran_boost
    dominance_component = weights["dominance"] * avg_dominance
    event_component = weights["events"] * avg_event_boost
    raw_confidence = (
        consistency_component +
        record_component +
        veteran_component +
        dominance_component +
        event_component
    )
    if raw_confidence > CONFIDENCE_THRESHOLDS["high"]:
        raw_confidence = CONFIDENCE_THRESHOLDS["high"] + (raw_confidence - CONFIDENCE_THRESHOLDS["high"]) * CONFIDENCE_MULTIPLIERS["high_boost"]
    elif raw_confidence < CONFIDENCE_THRESHOLDS["low"]:
        raw_confidence = raw_confidence * CONFIDENCE_MULTIPLIERS["low_reduction"]
    final_confidence = max(0.0, min(1.0, raw_confidence))
    result = {
        "overall": round(total_overall / total_match_count, 2),
        "auto": round(total_auto / total_match_count, 2),
        "teleop": round(total_teleop / total_match_count, 2),
        "endgame": round(total_endgame / total_match_count, 2),
        "confidence": round(final_confidence, 2),
        "actual_epa": round((total_overall / total_match_count) * final_confidence, 2),
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
    # Only add per-element EPA if any event has it (2025)
    if l1_count or l2_count or l3_count or l4_count or net_count or processor_count:
        result.update({
            "l1_epa": round(l1_sum / l1_count, 2) if l1_count else 0.0,
            "l2_epa": round(l2_sum / l2_count, 2) if l2_count else 0.0,
            "l3_epa": round(l3_sum / l3_count, 2) if l3_count else 0.0,
            "l4_epa": round(l4_sum / l4_count, 2) if l4_count else 0.0,
            "net_epa": round(net_sum / net_count, 2) if net_count else 0.0,
            "processor_epa": round(processor_sum / processor_count, 2) if processor_count else 0.0
        })
    return result

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

    tba_team = tba_get(f"team/{team_key}")
    website = tba_team.get("website", "N/A") if tba_team else "N/A"

    # Get team events from PostgreSQL
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    event_epa_full = []  # Keep full data for aggregation
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for event_key in event_keys:
        try:
            matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            if matches:
                # Calculate overall wins/losses/ties from matches
                for match in matches:
                    if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                        continue
                    alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
                    winning_alliance = match.get("winning_alliance", "")
                    if winning_alliance == alliance:
                        total_wins += 1
                    elif winning_alliance and winning_alliance != alliance:
                        total_losses += 1
                    elif not winning_alliance:
                        total_ties += 1

                # Calculate EPA after processing all matches
                event_epa = calculate_event_epa(matches, team_key, team_number)
                event_epa["event_key"] = event_key  # Ensure event_key is included
                
                # Keep full data for aggregation
                event_epa_full.append(event_epa)
                
                # Only keep essential fields for final event_epas
                simplified_event_epa = {
                    "event_key": event_key,
                    "overall": event_epa["overall"],
                    "auto": event_epa["auto"],
                    "teleop": event_epa["teleop"],
                    "endgame": event_epa["endgame"],
                    "confidence": event_epa["confidence"],
                    "actual_epa": event_epa["actual_epa"]
                }
                event_epa_results.append(simplified_event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")
            continue

    # Aggregate overall EPA from full event-specific EPAs
    overall_epa_data = aggregate_overall_epa(event_epa_full)
    overall_epa_data["wins"] = total_wins
    overall_epa_data["losses"] = total_losses
    overall_epa_data["ties"] = total_ties

    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": website,
        "normal_epa": overall_epa_data.get("overall", 0),
        "confidence": overall_epa_data.get("confidence", 0),
        "epa": overall_epa_data.get("actual_epa", 0),
        "auto_epa": overall_epa_data.get("auto", 0),
        "teleop_epa": overall_epa_data.get("teleop", 0),
        "endgame_epa": overall_epa_data.get("endgame", 0),
        "wins": overall_epa_data.get("wins", 0),
        "losses": overall_epa_data.get("losses", 0),
        "ties": overall_epa_data.get("ties", 0),
        "event_epas": event_epa_results, # List of event-specific EPA results
    }

def analyze_single_team(team_key: str, year: int):
    # Get team events from PostgreSQL
    team_number = int(team_key[3:])
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for event_key in event_keys:
        try:
            matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            if matches:
                # Calculate overall wins/losses/ties from matches
                for match in matches:
                    if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                        continue
                    
                    alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
                    winning_alliance = match.get("winning_alliance", "")
                    if winning_alliance == alliance:
                        total_wins += 1
                    elif winning_alliance and winning_alliance != alliance:
                        total_losses += 1
                    elif not winning_alliance:
                        total_ties += 1

                event_epa = calculate_event_epa(matches, team_key, team_number)
                event_epa["event_key"] = event_key  # Ensure event_key is included
                event_epa_results.append(event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")

    overall_epa_data = aggregate_overall_epa(event_epa_results)
    overall_epa_data["wins"] = total_wins
    overall_epa_data["losses"] = total_losses
    overall_epa_data["ties"] = total_ties

    print(f"\n{'='*50}")
    print(f"EPA Analysis for Team {team_key} ({year})")
    print(f"{'='*50}")
    print(f"\nOverall EPA: {overall_epa_data['overall']}")
    print(f"Overall Confidence: {overall_epa_data['confidence']}")
    print(f"Actual Overall EPA: {overall_epa_data['actual_epa']}")
    print(f"Overall Record: {overall_epa_data['wins']}-{overall_epa_data['losses']}-{overall_epa_data['ties']}")

    if event_epa_results:
        print(f"\n{'='*50}")
        print("Event-Specific EPA Breakdowns")
        print(f"{'='*50}")
        for event_epa in event_epa_results:
            print(f"\nEvent: {event_epa['event_key']}")
            print(f"  Overall: {event_epa['overall']}")
            print(f"  Auto: {event_epa['auto']}")
            print(f"  Teleop: {event_epa['teleop']}")
            print(f"  Endgame: {event_epa['endgame']}")
            print(f"  Confidence: {event_epa['confidence']}")
            print(f"  Actual EPA: {event_epa['actual_epa']}")
            print(f"  Record: {event_epa['wins']}-{event_epa['losses']}-{event_epa['ties']}")
            print("  Confidence Breakdown:")
            weights = event_epa["weights"]
            print(f"    → Consistency:     {round(event_epa['consistency'], 3)} × {weights['consistency']} = {round(weights['consistency'] * event_epa['consistency'], 4)}")
            print(f"    → Record Align:    {round(event_epa['record_alignment'], 3)} × {weights['record_alignment']} = {round(weights['record_alignment'] * event_epa['record_alignment'], 4)}")
            print(f"    → Veteran Boost:   {round(event_epa['veteran_boost'], 3)} ({event_epa['years_experience']} years) × {weights['veteran']} = {round(weights['veteran'] * event_epa['veteran_boost'], 4)}")
            print(f"    → Dominance:       {round(event_epa['dominance'], 3)} × {weights['dominance']} = {round(weights['dominance'] * event_epa['dominance'], 4)}")
            print(f"    → Event Boost:     {round(event_epa['event_boost'], 3)} × {weights['events']} = {round(weights['events'] * event_epa['event_boost'], 4)}")
            print(f"    → Confidence Total: {round(event_epa['raw_confidence'], 4)} → Capped: {round(event_epa['confidence'], 3)}")
    else:
        print("\nNo event-specific EPA data found for this team.")

    # Calculate and print overall confidence breakdown
    if event_epa_results:
        weights = event_epa_results[0]["weights"]  # Weights are constant across events
        components = overall_epa_data["confidence_components"]
        
        print(f"\n{'='*50}")
        print("Overall Confidence Breakdown (Weighted Average)")
        print(f"{'='*50}")
        print(f"→ Consistency:     {round(overall_epa_data['avg_consistency'], 3)} × {weights['consistency']} = {round(components['consistency'], 4)}")
        print(f"→ Record Align:    {round(overall_epa_data['avg_record_alignment'], 3)} × {weights['record_alignment']} = {round(components['record'], 4)}")
        print(f"→ Veteran Boost:   {round(overall_epa_data['avg_veteran_boost'], 3)} × {weights['veteran']} = {round(components['veteran'], 4)}")
        print(f"→ Dominance:       {round(overall_epa_data['avg_dominance'], 3)} × {weights['dominance']} = {round(components['dominance'], 4)}")
        print(f"→ Event Boost:     {round(overall_epa_data['avg_event_boost'], 3)} × {weights['events']} = {round(components['event'], 4)}")
        print(f"→ Confidence Total: {round(components['raw'], 4)} → Capped: {round(overall_epa_data['confidence'], 3)}")

def restart_heroku_app():
    """Restart the Heroku app to reload updated data."""
    
    app_name = os.environ.get("HEROKU_APP_NAME")
    api_key = os.environ.get("HEROKU_API_KEY")
    
    if not app_name or not api_key:
        print("⚠️  HEROKU_APP_NAME or HEROKU_API_KEY not set, skipping app restart")
        return
    
    try:
        url = f"https://api.heroku.com/apps/{app_name}/dynos"
        headers = {
            "Accept": "application/vnd.heroku+json; version=3",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Restart all dynos
        response = requests.delete(url, headers=headers)
        if response.status_code == 202:
            print(f"✅ Successfully restarted Heroku app: {app_name}")
        else:
            print(f"❌ Failed to restart app: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error restarting app: {e}")

def main():
    print("\nEPA Calculator")
    print("="*20)
    
    try:
        mode = input("\nSelect mode:\n1. Single Team Analysis\n2. Process Entire JSON\nEnter choice (1 or 2): ").strip()
        
        if mode not in ['1', '2']:
            print("Invalid choice. Please enter 1 or 2.")
            return
            
        year = input("Enter year (e.g., 2025): ").strip()
        try:
            year = int(year)
        except ValueError:
            print("Invalid year. Please enter a valid year.")
            return
            
        if mode == '1':
            team_key = input("Enter team key (e.g., frc254): ").strip().lower()
            if not team_key.startswith('frc'):
                team_key = f"frc{team_key}"
            
            analyze_single_team(team_key, year)
            
        else:
            fetch_and_store_team_data(year)
            # Restart the app after successful data update
            restart_heroku_app()
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Final cleanup
        print("\n🧹 Performing final cleanup...")
        for executor in active_executors:
            cleanup_executor(executor)
        for conn in active_connections:
            cleanup_connection(conn)
        print("✅ Cleanup complete.")
        elapsed = time.time() - start_time
        print(f"\n⏱️ Script runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            # Command-line mode
            mode = sys.argv[1]
            if mode == '1':
                # Single team analysis: python epa.py 1 2025 frc254
                if len(sys.argv) < 4:
                    print("Usage: python epa.py 1 <year> <team_key>")
                    sys.exit(1)
                try:
                    year = int(sys.argv[2])
                except ValueError:
                    print("Year must be an integer.")
                    sys.exit(1)
                team_key = sys.argv[3].strip().lower()
                if not team_key.startswith('frc'):
                    team_key = f"frc{team_key}"
                analyze_single_team(team_key, year)
            elif mode == '2':
                # Process all teams: python epa.py 2 2025
                if len(sys.argv) < 3:
                    print("Usage: python epa.py 2 <year>")
                    sys.exit(1)
                try:
                    year = int(sys.argv[2])
                except ValueError:
                    print("Year must be an integer.")
                    sys.exit(1)
                fetch_and_store_team_data(year)
                # Restart the app after successful data update
                restart_heroku_app()
            else:
                print("Unknown mode. Use '1' for single team or '2' for all teams.")
                sys.exit(1)
        else:
            main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Final cleanup
        print("\n🧹 Performing final cleanup...")
        for executor in active_executors:
            cleanup_executor(executor)
        for conn in active_connections:
            cleanup_connection(conn)
        print("✅ Cleanup complete.")
        elapsed = time.time() - start_time
        print(f"\n⏱️ Script runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")