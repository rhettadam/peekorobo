import os
import sqlite3
import requests
import random
from tqdm import tqdm
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS").split(",")

def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

# Create SQLite DB and schema (main thread)
conn = sqlite3.connect("events.sqlite")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS events (
    key TEXT PRIMARY KEY,
    name TEXT,
    year INTEGER,
    start_date TEXT,
    end_date TEXT,
    event_type TEXT,
    city TEXT,
    state_prov TEXT,
    country TEXT,
    website TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS event_teams (
    event_key TEXT,
    team_key TEXT,
    team_number INTEGER,
    nickname TEXT,
    city TEXT,
    state_prov TEXT,
    country TEXT,
    PRIMARY KEY (event_key, team_key)
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS event_rankings (
    event_key TEXT,
    team_key TEXT,
    rank INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    dq INTEGER
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS event_oprs (
    event_key TEXT,
    team_key TEXT,
    opr REAL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS event_matches (
    key TEXT PRIMARY KEY,
    event_key TEXT,
    comp_level TEXT,
    match_number INTEGER,
    set_number INTEGER,
    red_teams TEXT,
    blue_teams TEXT,
    red_score INTEGER,
    blue_score INTEGER,
    winning_alliance TEXT,
    youtube_video TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS event_awards (
    event_key TEXT,
    team_key TEXT,
    award_name TEXT,
    year INTEGER
)
""")
conn.commit()

# ================================
# Process events by year
# ================================
for year in range(1992, 2026):
    try:
        events = tba_get(f"events/{year}")
    except Exception as e:
        print(f"❌ Failed to load events for {year}: {e}")
        continue

    print(f"\n📅 {year} - {len(events)} events")

    def fetch_event_data(event):
        key = event["key"]
        event_data = {
            "event_row": (
                key,
                event.get("name"),
                year,
                event.get("start_date"),
                event.get("end_date"),
                event.get("event_type_string"),
                event.get("city"),
                event.get("state_prov"),
                event.get("country"),
                event.get("website")
            ),
            "teams": [],
            "rankings": [],
            "oprs": [],
            "matches": [],
            "awards": []
        }

        # Teams
        try:
            teams = tba_get(f"event/{key}/teams")
            for t in teams:
                event_data["teams"].append((
                    key, t["key"], t.get("team_number"), t.get("nickname"),
                    t.get("city"), t.get("state_prov"), t.get("country")
                ))
        except:
            pass

        # Rankings
        try:
            rankings_data = tba_get(f"event/{key}/rankings")
            for entry in rankings_data.get("rankings", []):
                record = entry.get("record", {})
                event_data["rankings"].append((
                    key, entry.get("team_key"),
                    entry.get("rank"), record.get("wins"),
                    record.get("losses"), record.get("ties"),
                    entry.get("dq"),
                ))
        except:
            pass

        # OPRs
        try:
            opr_data = tba_get(f"event/{key}/oprs")
            for team_key, opr in opr_data.get("oprs", {}).items():
                event_data["oprs"].append((key, team_key, opr))
        except:
            pass

        # Matches
        try:
            matches = tba_get(f"event/{key}/matches")
            for match in matches:
                red_teams = ",".join(match["alliances"]["red"]["team_keys"])
                blue_teams = ",".join(match["alliances"]["blue"]["team_keys"])
                red_score = match["alliances"]["red"]["score"]
                blue_score = match["alliances"]["blue"]["score"]
                youtube = next((v["key"] for v in match.get("videos", []) if v["type"] == "youtube"), None)

                event_data["matches"].append((
                    match["key"], key, match["comp_level"],
                    match["match_number"], match["set_number"],
                    red_teams, blue_teams,
                    red_score, blue_score,
                    match.get("winning_alliance"), youtube
                ))
        except:
            pass

        # 🆕 Awards
        try:
            awards = tba_get(f"event/{key}/awards")
            if not awards:
                print(f"🔇 No awards for {key}")
            for award in awards:
                name = award.get("name", "")
                for recipient in award.get("recipient_list", []):
                    team_key = recipient.get("team_key")
                    if team_key:  # Only store awards with associated teams
                        event_data["awards"].append((key, team_key, name, year))
        except Exception as e:
            print(f"❌ Error fetching awards for {key}: {e}")

        return event_data

    all_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_event_data, ev) for ev in events]
        for future in tqdm(as_completed(futures), total=len(events), desc=f"Processing {year}"):
            try:
                result = future.result()
                all_data.append(result)
            except Exception as e:
                print(f"❌ Error processing event: {e}")

    # ✅ Back to main thread: Write to DB
    for data in all_data:
        c.execute("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data["event_row"])
        c.executemany("INSERT OR REPLACE INTO event_teams VALUES (?, ?, ?, ?, ?, ?, ?)", data["teams"])
        c.executemany("INSERT INTO event_rankings VALUES (?, ?, ?, ?, ?, ?, ?)", data["rankings"])
        c.executemany("INSERT INTO event_oprs VALUES (?, ?, ?)", data["oprs"])
        c.executemany("INSERT OR REPLACE INTO event_matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data["matches"])
        c.executemany("INSERT INTO event_awards VALUES (?, ?, ?, ?)", data["awards"])

    conn.commit()

conn.close()
print("\n✅ Done! SQLite DB created: frc_events_1992_2025.db")
