import psycopg2
import json
import os
from typing import Dict, List, Optional
from auth import get_pg_connection

def get_pg_epa_connection():
    """Get a connection to the PostgreSQL database for EPA data"""
    return get_pg_connection()

def create_epa_tables():
    """Create the EPA tables in PostgreSQL if they don't exist"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    # Read and execute the schema
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ EPA tables created/verified in PostgreSQL")

def clear_year_data(year: int):
    """Clear all data for a specific year from all EPA tables"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    # Clear data for the specified year
    cur.execute("DELETE FROM events WHERE year = %s", (year,))
    cur.execute("DELETE FROM event_teams WHERE event_key LIKE %s", (f"{year}%",))
    cur.execute("DELETE FROM event_rankings WHERE event_key LIKE %s", (f"{year}%",))
    cur.execute("DELETE FROM event_oprs WHERE event_key LIKE %s", (f"{year}%",))
    cur.execute("DELETE FROM event_matches WHERE event_key LIKE %s", (f"{year}%",))
    cur.execute("DELETE FROM event_awards WHERE year = %s", (year,))
    cur.execute("DELETE FROM team_epas WHERE year = %s", (year,))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"🧹 Cleared all {year} data from PostgreSQL")

def insert_event_data(events_data: List[Dict], year: int):
    """Insert event data into PostgreSQL"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    for data in events_data:
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
        
        # Insert OPRs
        if data["oprs"]:
            cur.executemany("""
                INSERT INTO event_oprs (event_key, team_number, opr)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    opr = EXCLUDED.opr
            """, data["oprs"])
        
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
    print(f"✅ Inserted {len(events_data)} events into PostgreSQL")

def get_teams_for_year(year: int) -> List[Dict]:
    """Get all unique teams that participated in events for a specific year"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT team_number, nickname, city, state_prov, country
        FROM event_teams
        WHERE event_key LIKE %s
        ORDER BY team_number
    """, (f"{year}%",))
    
    teams = []
    for row in cur.fetchall():
        team_number, nickname, city, state_prov, country = row
        teams.append({
            "key": f"frc{team_number}",
            "team_number": team_number,
            "nickname": nickname,
            "city": city,
            "state_prov": state_prov,
            "country": country,
        })
    
    cur.close()
    conn.close()
    return teams

def get_team_events(team_number: int, year: int) -> List[str]:
    """Get all event keys for a team in a specific year"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT event_key
        FROM event_teams
        WHERE team_number = %s AND event_key LIKE %s
        ORDER BY event_key
    """, (team_number, f"{year}%"))
    
    event_keys = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    return event_keys

def insert_team_epa(team_data: Dict, year: int):
    """Insert or update team EPA data"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    # Filter event_epas to only allowed keys
    allowed_keys = ["overall", "auto", "teleop", "endgame", "confidence", "actual_epa", "wins", "losses"]
    filtered_event_epas = []
    for event_epa in team_data.get("event_epas", []):
        filtered_event_epas.append({k: event_epa[k] for k in allowed_keys if k in event_epa})
    
    cur.execute("""
        INSERT INTO team_epas (
            team_number, year, nickname, city, state_prov, country, website,
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
            wins, losses, event_epas
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        team_data.get("team_number"),
        year,
        team_data.get("nickname"),
        team_data.get("city"),
        team_data.get("state_prov"),
        team_data.get("country"),
        team_data.get("website"),
        team_data.get("normal_epa"),
        team_data.get("epa"),
        team_data.get("confidence"),
        team_data.get("auto_epa"),
        team_data.get("teleop_epa"),
        team_data.get("endgame_epa"),
        team_data.get("wins"),
        team_data.get("losses"),
        json.dumps(filtered_event_epas)
    ))
    
    conn.commit()
    cur.close()
    conn.close()

def get_team_experience_pg(team_number: int, up_to_year: int) -> int:
    """Get team experience from PostgreSQL"""
    conn = get_pg_epa_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(DISTINCT year)
        FROM team_epas
        WHERE team_number = %s AND year <= %s
    """, (team_number, up_to_year))
    
    years = cur.fetchone()[0] or 0
    
    cur.close()
    conn.close()
    return years 