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

def update_epa_from_json(year):
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

    # Ensure epa_history table exists with all possible columns
    cur.execute("""
    CREATE TABLE IF NOT EXISTS epa_history (
        year INTEGER,
        team_number INTEGER,
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
        consistency REAL,
        average_match_score REAL,
        wins INTEGER,
        losses INTEGER,
        avg_l4 REAL,
        avg_l3 REAL,
        avg_l2 REAL,
        avg_l1 REAL,
        avg_net REAL,
        avg_processor REAL,
        algae_epa REAL,
        most_common_endgame TEXT,
        PRIMARY KEY (year, team_number)
    )
    """)

    try:
        cur.execute("BEGIN TRANSACTION;")
        # Delete existing entries for the specific year
        cur.execute("DELETE FROM epa_history WHERE year = ?", (year,))

        for team in teams:
            # Use .get() with default to handle potential missing keys gracefully
            cur.execute("""
            INSERT OR REPLACE INTO epa_history (
                year, team_number, nickname, city, state_prov, country, website,
                normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
                consistency, average_match_score, wins, losses,
                avg_l4, avg_l3, avg_l2, avg_trough, avg_net, avg_processor, avg_algae_epa, most_common_endgame
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                year,
                team.get("team_number"),
                team.get("nickname"),
                team.get("city"),
                team.get("state_prov"),
                team.get("country"),
                team.get("website"),
                team.get("normal_epa"),
                team.get("ace"), # Use 'ace' from JSON for 'epa' column
                team.get("confidence"),
                team.get("auto_ace"), # Use 'auto_ace' for 'auto_epa' column
                team.get("teleop_ace"), # Use 'teleop_ace' for 'teleop_epa' column
                team.get("endgame_ace"), # Use 'endgame_ace' for 'endgame_epa' column
                team.get("consistency"),
                team.get("average_match_score"),
                team.get("wins"),
                team.get("losses"),
                # New columns for 2025
                team.get("avg_l4"),
                team.get("avg_l3"),
                team.get("avg_l2"),
                team.get("avg_trough"),
                team.get("avg_net"),
                team.get("avg_processor"),
                team.get("avg_algae_epa"),
                team.get("most_common_endgame"),
            ))

        conn.commit()
        print(f"✅ Successfully updated {len(teams)} entries for {year} in {db_file}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during database update for year {year}: {e}")
        import traceback
        traceback.print_exc() # Print traceback for better debugging
    finally:
        conn.close()

if __name__ == "__main__":
    # Call the function specifically for 2025
    update_epa_from_json(2025)
    # If you need to process 2022 again with the old data, you would call:
    # update_epa_from_json(2022)
    # Note that the 2022 entries will have NULL for the new 2025-specific columns.


if __name__ == "__main__":
    update_2022_epa_from_json()
