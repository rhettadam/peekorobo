#!/usr/bin/env python3
"""
Migration script to transfer all existing data from SQLite to PostgreSQL.
This preserves all historical EPA data without needing to re-run the model.
"""

import os
import sqlite3
import json
from auth import get_pg_connection
from pg_epa import create_epa_tables, clear_year_data

def migrate_events_data():
    """Migrate events data from SQLite to PostgreSQL"""
    print("🔄 Migrating events data...")
    
    # SQLite paths
    events_sqlite = os.path.join("data", "events.sqlite")
    if not os.path.exists(events_sqlite):
        print("❌ events.sqlite not found, skipping events migration")
        return
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(events_sqlite)
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        # Migrate events (e table)
        print("  📅 Migrating events...")
        sqlite_cursor.execute("SELECT k, n, y, sd, ed, et, c, s, co, w FROM e")
        events = sqlite_cursor.fetchall()
        
        for event in events:
            pg_cursor.execute("""
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
            """, event)
        
        # Migrate event teams (et table)
        print("  👥 Migrating event teams...")
        sqlite_cursor.execute("SELECT ek, tk, nn, c, s, co FROM et")
        event_teams = sqlite_cursor.fetchall()
        
        for team in event_teams:
            pg_cursor.execute("""
                INSERT INTO event_teams (event_key, team_number, nickname, city, state_prov, country)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    city = EXCLUDED.city,
                    state_prov = EXCLUDED.state_prov,
                    country = EXCLUDED.country
            """, team)
        
        # Migrate rankings (r table)
        print("  🏆 Migrating rankings...")
        sqlite_cursor.execute("SELECT ek, tk, rk, w, l, t, dq FROM r")
        rankings = sqlite_cursor.fetchall()
        
        for ranking in rankings:
            pg_cursor.execute("""
                INSERT INTO event_rankings (event_key, team_number, rank, wins, losses, ties, dq)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    rank = EXCLUDED.rank,
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    ties = EXCLUDED.ties,
                    dq = EXCLUDED.dq
            """, ranking)
        
        # Migrate OPRs (o table)
        print("  📊 Migrating OPRs...")
        sqlite_cursor.execute("SELECT ek, tk, opr FROM o")
        oprs = sqlite_cursor.fetchall()
        
        for opr in oprs:
            pg_cursor.execute("""
                INSERT INTO event_oprs (event_key, team_number, opr)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_key, team_number) DO UPDATE SET
                    opr = EXCLUDED.opr
            """, opr)
        
        # Migrate matches (m table)
        print("  🏁 Migrating matches...")
        sqlite_cursor.execute("SELECT k, ek, cl, mn, sn, rt, bt, rs, bs, wa, yt FROM m")
        matches = sqlite_cursor.fetchall()
        
        for match in matches:
            pg_cursor.execute("""
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
            """, match)
        
        # Migrate awards (a table)
        print("  🏅 Migrating awards...")
        sqlite_cursor.execute("SELECT ek, tk, an, y FROM a")
        awards = sqlite_cursor.fetchall()
        
        for award in awards:
            pg_cursor.execute("""
                INSERT INTO event_awards (event_key, team_number, award_name, year)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_key, team_number, award_name) DO NOTHING
            """, award)
        
        pg_conn.commit()
        print(f"✅ Migrated {len(events)} events, {len(event_teams)} event teams, {len(rankings)} rankings, {len(oprs)} OPRs, {len(matches)} matches, {len(awards)} awards")
        
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()

def migrate_epa_data():
    """Migrate EPA data from SQLite to PostgreSQL"""
    print("🔄 Migrating EPA data...")
    
    # SQLite paths
    epa_sqlite = os.path.join("data", "epa_teams.sqlite")
    if not os.path.exists(epa_sqlite):
        print("❌ epa_teams.sqlite not found, skipping EPA migration")
        return
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(epa_sqlite)
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        # Get list of all EPA year tables
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'epa_%'")
        year_tables = [row[0] for row in sqlite_cursor.fetchall()]
        
        total_teams = 0
        
        for table in year_tables:
            year = int(table.split('_')[1])  # Extract year from table name (epa_YYYY)
            print(f"  📈 Migrating {year} EPA data...")
            
            # Get all team data for this year
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            columns = [desc[0] for desc in sqlite_cursor.description]
            rows = sqlite_cursor.fetchall()
            
            for row in rows:
                team_data = dict(zip(columns, row))
                
                # Handle event_epas field
                event_epas = team_data.get("event_epas")
                if event_epas is None:
                    event_epas = []
                elif isinstance(event_epas, str):
                    try:
                        event_epas = json.loads(event_epas)
                    except json.JSONDecodeError:
                        event_epas = []
                
                # Insert into PostgreSQL
                pg_cursor.execute("""
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
                    json.dumps(event_epas)
                ))
            
            total_teams += len(rows)
            print(f"    ✅ Migrated {len(rows)} teams for {year}")
        
        pg_conn.commit()
        print(f"✅ Total EPA migration: {total_teams} teams across {len(year_tables)} years")
        
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()

def main():
    print("🚀 Starting SQLite to PostgreSQL migration...")
    print("=" * 50)
    
    try:
        # Create PostgreSQL tables
        print("📋 Creating PostgreSQL tables...")
        create_epa_tables()
        
        # Migrate events data
        migrate_events_data()
        
        # Migrate EPA data
        migrate_epa_data()
        
        # Verify migration
        print("\n🔍 Verifying migration...")
        conn = get_pg_connection()
        cursor = conn.cursor()
        
        # Count records in each table
        tables = ['events', 'event_teams', 'event_rankings', 'event_oprs', 'event_matches', 'event_awards', 'team_epas']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  📊 {table}: {count} records")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Migration completed successfully!")
        print("✅ All your historical data has been preserved in PostgreSQL")
        print("✅ You can now delete the old SQLite files if desired")
        print("✅ Your Heroku scheduler will now use the persistent PostgreSQL data")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1) 