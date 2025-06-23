#!/usr/bin/env python3
"""
Clear existing data and migrate all data from SQLite to PostgreSQL
"""

import os
import sqlite3
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
from tqdm import tqdm
import time
import json

load_dotenv()

def get_pg_connection():
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
        # Add connection timeout settings
        connect_timeout=30,
        options='-c statement_timeout=300000'  # 5 minutes
    )
    return conn

def clear_existing_data():
    """Clear all existing data from PostgreSQL tables"""
    print("🧹 Clearing existing data from PostgreSQL...")
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        # Clear all tables in the correct order (respecting foreign keys)
        tables_to_clear = [
            "event_awards",
            "event_oprs", 
            "event_rankings",
            "event_teams",
            "event_matches",
            "team_epas"
        ]
        
        for table in tables_to_clear:
            print(f"   Clearing {table}...")
            pg_cursor.execute(f"DELETE FROM {table}")
            count = pg_cursor.rowcount
            print(f"   ✅ Deleted {count} records from {table}")
        
        pg_conn.commit()
        print("✅ All existing data cleared successfully!")
        
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
    finally:
        pg_cursor.close()
        pg_conn.close()

def migrate_table_robust(sqlite_cursor, sqlite_table_name, pg_table_name, select_sql, insert_sql, chunk_size=1000, resume_offset=0):
    """Migrate a table using robust processing with infinite retries"""
    print(f"\n🔄 Migrating {pg_table_name}...")
    
    # Get total count
    print(f"   Counting records in {sqlite_table_name}...")
    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {sqlite_table_name}")
    total_count = sqlite_cursor.fetchone()[0]
    print(f"   Found {total_count} records")
    
    if total_count == 0:
        print(f"   No data to migrate for {pg_table_name}")
        return 0
    
    if resume_offset > 0:
        print(f"   Resuming from offset {resume_offset}")
    
    print(f"   Using chunk size: {chunk_size}")
    
    migrated_count = resume_offset
    max_retries_per_chunk = 5
    retry_delay = 10  # Start with 10 seconds
    
    with tqdm(total=total_count, initial=resume_offset, desc=f"   {pg_table_name}", unit="records") as pbar:
        for i in range(resume_offset, total_count, chunk_size):
            retry_count = 0
            success = False
            
            while not success:  # Infinite retries
                try:
                    # Create fresh connection for each chunk to avoid timeouts
                    pg_conn = get_pg_connection()
                    pg_cursor = pg_conn.cursor()
                    
                    # Get chunk from SQLite
                    sqlite_cursor.execute(f"{select_sql} LIMIT ? OFFSET ?", (chunk_size, i))
                    chunk = sqlite_cursor.fetchall()
                    
                    if chunk:
                        # Insert chunk into PostgreSQL
                        pg_cursor.executemany(insert_sql, chunk)
                        pg_conn.commit()
                        migrated_count += len(chunk)
                        pbar.update(len(chunk))
                        
                        # Progress update every 5 chunks
                        if (i // chunk_size) % 5 == 0:
                            print(f"   ✅ Committed at {migrated_count} records (offset {i})")
                    
                    pg_cursor.close()
                    pg_conn.close()
                    success = True
                    
                    # Reset retry delay on success
                    retry_delay = 10
                    
                except Exception as e:
                    retry_count += 1
                    print(f"   ⚠️  Error at offset {i} (attempt {retry_count}): {e}")
                    
                    try:
                        pg_cursor.close()
                        pg_conn.close()
                    except:
                        pass
                    
                    # Exponential backoff with max delay of 5 minutes
                    wait_time = min(retry_delay * (2 ** (retry_count - 1)), 300)
                    print(f"   🔄 Retrying in {wait_time} seconds... (will retry indefinitely)")
                    time.sleep(wait_time)
    
    print(f"   ✅ Migrated {migrated_count} records for {pg_table_name}")
    return migrated_count

def migrate_epa_data_robust(epa_sqlite_cursor):
    """Migrate EPA data using robust processing with infinite retries"""
    print("\n📈 Migrating EPA data...")
    
    epa_sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'epa_%'")
    year_tables = [row[0] for row in epa_sqlite_cursor.fetchall()]
    print(f"   Found EPA tables for years: {[t.split('_')[1] for t in year_tables]}")
    
    total_teams = 0
    max_retries_per_batch = 5
    retry_delay = 10
    
    for table in year_tables:
        year = int(table.split('_')[1])
        print(f"\n     📈 Migrating {year} EPA data...")
        
        # Get all team data for this year
        epa_sqlite_cursor.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in epa_sqlite_cursor.description]
        rows = epa_sqlite_cursor.fetchall()
        
        print(f"       Found {len(rows)} teams for {year}")
        
        # Process in small batches
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            retry_count = 0
            success = False
            
            while not success:  # Infinite retries
                try:
                    # Create fresh connection for each batch
                    pg_conn = get_pg_connection()
                    pg_cursor = pg_conn.cursor()
                    
                    # Prepare batch data
                    batch_data = []
                    for row in batch:
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
                        
                        batch_data.append((
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
                            json.dumps(event_epas) if event_epas else None
                        ))
                    
                    # Insert batch
                    pg_cursor.executemany("""
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
                    """, batch_data)
                    
                    pg_conn.commit()
                    total_teams += len(batch_data)
                    
                    pg_cursor.close()
                    pg_conn.close()
                    success = True
                    
                    # Reset retry delay on success
                    retry_delay = 10
                    
                    # Progress update every 10 batches
                    if (i // batch_size) % 10 == 0:
                        print(f"       Processed {total_teams} teams so far...")
                        
                except Exception as e:
                    retry_count += 1
                    print(f"       ⚠️  Error processing batch {i//batch_size + 1} for {year} (attempt {retry_count}): {e}")
                    
                    try:
                        pg_cursor.close()
                        pg_conn.close()
                    except:
                        pass
                    
                    # Exponential backoff with max delay of 5 minutes
                    wait_time = min(retry_delay * (2 ** (retry_count - 1)), 300)
                    print(f"       🔄 Retrying in {wait_time} seconds... (will retry indefinitely)")
                    time.sleep(wait_time)
    
    print(f"   ✅ Total teams migrated: {total_teams}")
    return total_teams

def main():
    """Clear data and run migration with infinite retries"""
    print("🚀 Starting fresh migration from SQLite to PostgreSQL...")
    print("=" * 60)
    print("🔄 This script will retry indefinitely if it encounters errors")
    print("🔄 You can stop it with Ctrl+C and it will show you where to resume")
    
    # Check SQLite files
    events_sqlite = os.path.join("data", "events.sqlite")
    epa_sqlite = os.path.join("data", "epa_teams.sqlite")
    
    if not os.path.exists(events_sqlite):
        print(f"❌ {events_sqlite} not found")
        return
    
    if not os.path.exists(epa_sqlite):
        print(f"❌ {epa_sqlite} not found")
        return
    
    print(f"✅ Found SQLite files:")
    print(f"   Events: {events_sqlite}")
    print(f"   EPA: {epa_sqlite}")
    
    # Clear existing data first
    clear_existing_data()
    
    # Connect to SQLite databases
    events_sqlite_conn = sqlite3.connect(events_sqlite)
    events_sqlite_cursor = events_sqlite_conn.cursor()
    
    epa_sqlite_conn = sqlite3.connect(epa_sqlite)
    epa_sqlite_cursor = epa_sqlite_conn.cursor()
    
    start_time = time.time()
    
    try:
        # === MIGRATE EVENT TEAMS ===
        event_teams_sql = "SELECT ek, tk, nn, c, s, co FROM et"
        event_teams_insert = """
            INSERT INTO event_teams (event_key, team_number, nickname, city, state_prov, country)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key, team_number) DO UPDATE SET
                nickname = EXCLUDED.nickname,
                city = EXCLUDED.city,
                state_prov = EXCLUDED.state_prov,
                country = EXCLUDED.country
        """
        migrate_table_robust(events_sqlite_cursor, "et", "event_teams", event_teams_sql, event_teams_insert, chunk_size=1000)
        
        # === MIGRATE RANKINGS ===
        rankings_sql = "SELECT ek, tk, rk, w, l, t, dq FROM r"
        rankings_insert = """
            INSERT INTO event_rankings (event_key, team_number, rank, wins, losses, ties, dq)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key, team_number) DO UPDATE SET
                rank = EXCLUDED.rank,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                ties = EXCLUDED.ties,
                dq = EXCLUDED.dq
        """
        migrate_table_robust(events_sqlite_cursor, "r", "event_rankings", rankings_sql, rankings_insert, chunk_size=1000)
        
        # === MIGRATE OPRS ===
        oprs_sql = "SELECT ek, tk, opr FROM o"
        oprs_insert = """
            INSERT INTO event_oprs (event_key, team_number, opr)
            VALUES (%s, %s, %s)
            ON CONFLICT (event_key, team_number) DO UPDATE SET
                opr = EXCLUDED.opr
        """
        migrate_table_robust(events_sqlite_cursor, "o", "event_oprs", oprs_sql, oprs_insert, chunk_size=1000)
        
        # === MIGRATE MATCHES ===
        matches_sql = "SELECT k, ek, cl, mn, sn, rt, bt, rs, bs, wa, yt FROM m"
        matches_insert = """
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
        """
        migrate_table_robust(events_sqlite_cursor, "m", "event_matches", matches_sql, matches_insert, chunk_size=1000)
        
        # === MIGRATE AWARDS ===
        awards_sql = "SELECT ek, tk, an, y FROM a"
        awards_insert = """
            INSERT INTO event_awards (event_key, team_number, award_name, year)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (event_key, team_number, award_name) DO NOTHING
        """
        migrate_table_robust(events_sqlite_cursor, "a", "event_awards", awards_sql, awards_insert, chunk_size=1000)
        
        # === MIGRATE EPA DATA ===
        total_teams = migrate_epa_data_robust(epa_sqlite_cursor)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ Fresh migration completed successfully!")
        print(f"📊 Total teams migrated: {total_teams}")
        print(f"⏱️  Total time: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        
        # Verify migration
        print(f"\n🔍 Verifying migration...")
        pg_conn = get_pg_connection()
        pg_cursor = pg_conn.cursor()
        
        pg_cursor.execute("SELECT COUNT(*) FROM events")
        events_count = pg_cursor.fetchone()[0]
        pg_cursor.execute("SELECT COUNT(*) FROM event_teams")
        event_teams_count = pg_cursor.fetchone()[0]
        pg_cursor.execute("SELECT COUNT(*) FROM team_epas")
        team_epas_count = pg_cursor.fetchone()[0]
        
        print(f"   Events: {events_count}")
        print(f"   Event Teams: {event_teams_count}")
        print(f"   Team EPAs: {team_epas_count}")
        
        pg_cursor.close()
        pg_conn.close()
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Migration interrupted by user (Ctrl+C)")
        print(f"💡 The script was resilient and will retry automatically")
        print(f"💡 You can stop it again if needed")
        return
    except Exception as e:
        print(f"❌ Unexpected error during migration: {e}")
        import traceback
        traceback.print_exc()
        print(f"💡 The script will retry automatically due to the robust retry logic")
    finally:
        events_sqlite_cursor.close()
        events_sqlite_conn.close()
        epa_sqlite_cursor.close()
        epa_sqlite_conn.close()

if __name__ == "__main__":
    main() 