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

def update_2025_epa_from_json():
    json_file = "teams_2025.json"
    db_file = "epa_teams.sqlite"
    year = 2025

    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        return

    with open(json_file, "r") as f:
        teams = json.load(f)

    print(f"📥 Loaded {len(teams)} teams from {json_file}")

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Ensure epa_history table exists
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
        PRIMARY KEY (year, team_number)
    )
    """)

    # Delete existing 2025 entries to avoid duplication
    cur.execute("DELETE FROM epa_history WHERE year = ?", (year,))

    for team in teams:
        cur.execute("""
        INSERT OR REPLACE INTO epa_history (
            year, team_number, nickname, city, state_prov, country, website,
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
            consistency, average_match_score, wins, losses
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            year,
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
            team.get("consistency"),
            team.get("average_match_score"),
            team.get("wins"),
            team.get("losses"),
        ))

    conn.commit()
    conn.close()
    print(f"✅ Successfully updated {len(teams)} entries for 2025 in {db_file}")

if __name__ == "__main__":
    update_2025_epa_from_json()

