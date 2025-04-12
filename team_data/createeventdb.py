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
    headers = {"X-TBA-Auth-Key": random.choice(API_KEYS)}
    r = requests.get(f"{BASE_URL}/{endpoint}", headers=headers)
    r.raise_for_status()
    return r.json()

# Connect to SQLite and enable compression features
conn = sqlite3.connect("events.sqlite")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("PRAGMA temp_store=MEMORY")
conn.execute("PRAGMA page_size=4096")
c = conn.cursor()

# Create optimized schema if not exists
c.executescript("""
CREATE TABLE IF NOT EXISTS e (
    k TEXT PRIMARY KEY,
    n TEXT, y INT, sd TEXT, ed TEXT,
    et TEXT, c TEXT, s TEXT, co TEXT, w TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS et (
    ek TEXT, tk INT,
    nn TEXT, c TEXT, s TEXT, co TEXT,
    PRIMARY KEY (ek, tk)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS r (
    ek TEXT, tk INT, rk INT,
    w INT, l INT, t INT, dq INT
);

CREATE TABLE IF NOT EXISTS o (
    ek TEXT, tk INT, opr REAL
);

CREATE TABLE IF NOT EXISTS m (
    k TEXT PRIMARY KEY,
    ek TEXT, cl TEXT, mn INT, sn INT,
    rt TEXT, bt TEXT,
    rs INT, bs INT, wa TEXT, yt TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS a (
    ek TEXT, tk INT, an TEXT, y INT
);
""")
conn.commit()

year = 2025

# Delete all 2025 data before rebuilding
print("🧹 Deleting existing 2025 data...")
c.execute("DELETE FROM e WHERE y = ?", (year,))
c.execute("DELETE FROM et WHERE ek IN (SELECT k FROM e WHERE y = ?)", (year,))
c.execute("DELETE FROM r WHERE ek IN (SELECT k FROM e WHERE y = ?)", (year,))
c.execute("DELETE FROM o WHERE ek IN (SELECT k FROM e WHERE y = ?)", (year,))
c.execute("DELETE FROM m WHERE ek IN (SELECT k FROM e WHERE y = ?)", (year,))
c.execute("DELETE FROM a WHERE y = ?", (year,))
conn.commit()

try:
    events = tba_get(f"events/{year}")
except Exception as e:
    print(f"❌ Failed to load events for {year}: {e}")
    conn.close()
    exit()

def fetch(event):
    key = event["key"]
    data = {
        "event": (
            key, event.get("name"), year,
            event.get("start_date"), event.get("end_date"),
            event.get("event_type_string"), event.get("city"),
            event.get("state_prov"), event.get("country"),
            event.get("website")
        ),
        "teams": [], "rankings": [], "oprs": [], "matches": [], "awards": []
    }

    try:
        teams = tba_get(f"event/{key}/teams")
        for t in teams:
            t_num = t.get("team_number")
            data["teams"].append((key, t_num, t.get("nickname"),
                                  t.get("city"), t.get("state_prov"), t.get("country")))
    except:
        pass

    try:
        ranks = tba_get(f"event/{key}/rankings")
        for r in ranks.get("rankings", []):
            record = r.get("record", {})
            t_num = int(r.get("team_key", "frc0")[3:])
            data["rankings"].append((key, t_num, r.get("rank"),
                                     record.get("wins"), record.get("losses"),
                                     record.get("ties"), r.get("dq")))
    except:
        pass

    try:
        oprs = tba_get(f"event/{key}/oprs").get("oprs", {})
        for t_key, opr in oprs.items():
            t_num = int(t_key[3:])
            data["oprs"].append((key, t_num, opr))
    except:
        pass

    try:
        matches = tba_get(f"event/{key}/matches")
        for m in matches:
            data["matches"].append((
                m["key"], key, m["comp_level"], m["match_number"],
                m["set_number"],
                ",".join(str(int(t[3:])) for t in m["alliances"]["red"]["team_keys"]),
                ",".join(str(int(t[3:])) for t in m["alliances"]["blue"]["team_keys"]),
                m["alliances"]["red"]["score"], m["alliances"]["blue"]["score"],
                m.get("winning_alliance"),
                next((v["key"] for v in m.get("videos", []) if v["type"] == "youtube"), None)
            ))
    except:
        pass

    try:
        awards = tba_get(f"event/{key}/awards")
        for aw in awards:
            for r in aw.get("recipient_list", []):
                if r.get("team_key"):
                    t_num = int(r["team_key"][3:])
                    data["awards"].append((key, t_num, aw.get("name"), year))
    except:
        pass

    return data

all_data = []
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch, ev) for ev in events]
    for f in tqdm(as_completed(futures), total=len(events), desc=f"Updating {year}"):
        try:
            all_data.append(f.result())
        except Exception as e:
            print(f"❌ Error processing: {e}")

for d in all_data:
    c.execute("INSERT OR REPLACE INTO e VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", d["event"])
    c.executemany("INSERT OR REPLACE INTO et VALUES (?, ?, ?, ?, ?, ?)", d["teams"])
    c.executemany("INSERT INTO r VALUES (?, ?, ?, ?, ?, ?, ?)", d["rankings"])
    c.executemany("INSERT INTO o VALUES (?, ?, ?)", d["oprs"])
    c.executemany("INSERT OR REPLACE INTO m VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", d["matches"])
    c.executemany("INSERT INTO a VALUES (?, ?, ?, ?)", d["awards"])
conn.commit()

conn.close()
print("\n✅ 2025 events rebuilt and database saved: events.sqlite")
