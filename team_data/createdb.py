import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv
import sqlite3
import math
import random

def create_year_table(cur, year):
    """Create a table for a specific year if it doesn't exist"""
    cur.execute(f"DROP TABLE IF EXISTS epa_{year}")
    cur.execute(f"""
    CREATE TABLE epa_{year} (
        team_number INTEGER PRIMARY KEY,
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
        event_epas TEXT
    )
    """)

def migrate_existing_data():
    """Migrate data from epa_history to year-specific tables"""
    conn = sqlite3.connect("epa_teams.sqlite")
    cur = conn.cursor()
    
    try:
        # Get all years from epa_history
        cur.execute("SELECT DISTINCT year FROM epa_history")
        years = [row[0] for row in cur.fetchall()]
        
        # Create tables for each year
        for year in years:
            create_year_table(cur, year)
            
            # Copy data from epa_history to year-specific table
            cur.execute(f"""
            INSERT OR REPLACE INTO epa_{year}
            SELECT team_number, nickname, city, state_prov, country, website,
                   normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                   wins, losses, event_epas
            FROM epa_history
            WHERE year = ?
            """, (year,))
        
        conn.commit()
        print("✅ Successfully migrated existing data to year-specific tables")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during data migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def update_epa_from_json(year):
    """Update the specified year's table with data from the JSON file"""
    json_file = f"teams_{year}.json"
    db_file = "epa_teams.sqlite"

    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        return

    try:
        with open(json_file, "r") as f:
            teams = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ Error decoding JSON from {json_file}. File might be empty or corrupt.")
        return

    print(f"📥 Loaded {len(teams)} teams from {json_file}")

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Create table for the specific year
    create_year_table(cur, year)

    try:
        cur.execute("BEGIN TRANSACTION;")
        # Delete existing entries for the specific year
        cur.execute(f"DELETE FROM epa_{year}")

        for team in teams:
            # Convert event_epas to JSON string
            event_epas_json = json.dumps(team.get("event_epas", []))

            cur.execute(f"""
            INSERT OR REPLACE INTO epa_{year} (
                team_number, nickname, city, state_prov, country, website,
                normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                wins, losses, event_epas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team.get("team_number"),
                team.get("nickname"),
                team.get("city"),
                team.get("state_prov"),
                team.get("country"),
                team.get("website"),
                team.get("normal_epa"),
                team.get("epa"),
                team.get("confidence"),
                team.get("auto_epa"),
                team.get("teleop_epa"),
                team.get("endgame_epa"),
                team.get("wins"),
                team.get("losses"),
                event_epas_json
            ))

        conn.commit()
        print(f"✅ Successfully updated {len(teams)} entries for {year} in {db_file}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during database update for year {year}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    # Get year from user input
    year = input("Enter year to update (e.g., 2024): ").strip()
    try:
        year = int(year)
    except ValueError:
        print("❌ Invalid year. Please enter a valid year number.")
        exit(1)
    
    # Update data for the specified year
    update_epa_from_json(year)
