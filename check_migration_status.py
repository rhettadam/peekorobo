#!/usr/bin/env python3
"""
Check migration status and database contents
"""

import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

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

def check_migration_status():
    print("🔍 Checking migration status...")
    
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()
        
        # Check what tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"📋 Tables in database: {[t[0] for t in tables]}")
        
        # Check each table's row count
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  {table_name}: {count} rows")
            except Exception as e:
                print(f"  {table_name}: Error - {e}")
        
        # Check if events table exists and has structure
        if ('events',) in tables:
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'events' 
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            print(f"\n📊 Events table structure:")
            for col_name, data_type in columns:
                print(f"  {col_name}: {data_type}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_migration_status() 