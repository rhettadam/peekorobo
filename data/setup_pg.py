#!/usr/bin/env python3
"""
Setup script to initialize PostgreSQL tables for EPA data.
Run this once to create the necessary tables.
"""

import os
import sys
from auth import get_pg_connection
from pg_epa import create_epa_tables

def main():
    print("Setting up PostgreSQL tables for EPA data...")
    
    try:
        # Create the EPA tables
        create_epa_tables()
        print("✅ PostgreSQL tables created successfully!")
        
        # Test the connection
        conn = get_pg_connection()
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('events', 'event_teams', 'event_rankings', 'event_oprs', 'event_matches', 'event_awards', 'team_epas')
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ Found {len(tables)} EPA tables: {', '.join(tables)}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Setup complete! You can now run the EPA script with PostgreSQL.")
        
    except Exception as e:
        print(f"❌ Error setting up PostgreSQL tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 