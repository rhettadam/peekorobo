import sqlite3
import json
import os
import random

# Database setup
db_filename = "epa_teams.sqlite"
conn = sqlite3.connect(db_filename)
cur = conn.cursor()

# Create table (only creates if it doesn't exist)
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
    trend REAL,
    average_match_score REAL,
    wins INTEGER,
    losses INTEGER,
    PRIMARY KEY (year, team_number)
)
""")
conn.commit()

# === Load ONLY 2025 data ===
file_path = "teams_2025.json"

if not os.path.exists(file_path):
    print(f"File {file_path} not found. Exiting.")
else:
    print(f"Updating data from {file_path}...")

    with open(file_path, "r") as f:
        teams = json.load(f)

    year = 2025
    for team in teams:
        cur.execute("""
        INSERT OR REPLACE INTO epa_history (
            year, team_number, nickname, city, state_prov, country, website,
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
            consistency, trend, average_match_score, wins, losses
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            team.get("trend"),
            team.get("average_match_score"),
            team.get("wins"),
            team.get("losses")
        ))

    conn.commit()
    print("2025 data updated successfully.")

conn.close()
