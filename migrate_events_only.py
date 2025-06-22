#!/usr/bin/env python3
"""
Migrate just events data to test the migration process
"""

import os
import sqlite3
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
from tqdm import tqdm

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
        port=result.port
    )
    return conn

def migrate_events_only():
    """Migrate just events data to test the process"""
    print("🔄 Migrating events data only...")
    
    # SQLite paths
    events_sqlite = os.path.join("data", "events.sqlite")
    if not os.path.exists(events_sqlite):
        print(f"❌ {events_sqlite} not found")
        return
    
    print(f"✅ Found SQLite file: {events_sqlite}")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(events_sqlite)
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        # Check what's in SQLite
        sqlite_cursor.execute("SELECT COUNT(*) FROM e")
        sqlite_count = sqlite_cursor.fetchone()[0]
        print(f"📊 SQLite has {sqlite_count} events")
        
        if sqlite_count == 0:
            print("❌ No events in SQLite to migrate")
            return
        
        # Migrate events (e table)
        print("  📅 Migrating events...")
        sqlite_cursor.execute("SELECT k, n, y, sd, ed, et, c, s, co, w FROM e LIMIT 10")
        events = sqlite_cursor.fetchall()
        
        print(f"  📋 Sample events from SQLite:")
        for event in events[:3]:
            print(f"    {event[0]}: {event[1]} ({event[2]})")
        
        # Clear existing events first
        pg_cursor.execute("DELETE FROM events")
        print("  🧹 Cleared existing events from PostgreSQL")
        
        # Insert events in small batches
        chunk_size = 100
        with tqdm(total=sqlite_count, desc="    Events", unit="events") as pbar:
            for i in range(0, sqlite_count, chunk_size):
                sqlite_cursor.execute("SELECT k, n, y, sd, ed, et, c, s, co, w FROM e LIMIT ? OFFSET ?", (chunk_size, i))
                chunk = sqlite_cursor.fetchall()
                
                if chunk:
                    pg_cursor.executemany("""
                        INSERT INTO events (event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, chunk)
                    pbar.update(len(chunk))
        
        # Commit the transaction
        pg_conn.commit()
        print("✅ Events migration completed and committed!")
        
        # Verify the migration
        pg_cursor.execute("SELECT COUNT(*) FROM events")
        pg_count = pg_cursor.fetchone()[0]
        print(f"📊 PostgreSQL now has {pg_count} events")
        
        if pg_count > 0:
            pg_cursor.execute("SELECT event_key, name, year FROM events LIMIT 3")
            sample_pg_events = pg_cursor.fetchall()
            print(f"📋 Sample events in PostgreSQL:")
            for event in sample_pg_events:
                print(f"    {event[0]}: {event[1]} ({event[2]})")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate_events_only() 