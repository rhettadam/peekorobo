#!/usr/bin/env python3
import os
import time
import json
import requests
from tqdm import tqdm
from dotenv import load_dotenv
import random

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = [k.strip() for k in os.getenv("TBA_API_KEYS", "").split(",") if k.strip()]
LOCATIONIQ_KEY = os.getenv("LOCATIONIQ_API_KEY") or "pk.62a48aee2f1255204a72a9934eb15b47"
YEAR = 2026
GEO_URL = "https://us1.locationiq.com/v1/search.php"

geo_cache = {}
cache_path = os.path.join(os.path.dirname(__file__), "geo_cache.json")

def tba_get(endpoint: str):
    if not API_KEYS:
        raise Exception("TBA_API_KEYS not set in environment.")
    for _ in range(5):
        try:
            key = random.choice(API_KEYS)
            headers = {"X-TBA-Auth-Key": key}
            url = f"{TBA_BASE_URL}/{endpoint}"

            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"[{r.status_code}] Error fetching {endpoint}")

        except Exception as e:
            print(f"Exception fetching {endpoint}: {e}")

        time.sleep(1 + random.random())

    return []


# -------------------------------
#   SIMPLE REWRITTEN ADDRESS BUILDER
#   USES ONLY CITY + STATE + ZIP
# -------------------------------
def build_location(team):
    city = team.get("city")
    state = team.get("state_prov")
    country = team.get("country")

    parts = [city, state, country]
    return ", ".join([p for p in parts if p])


def load_cache():
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache():
    try:
        with open(cache_path, "w") as f:
            json.dump(geo_cache, f)
    except Exception:
        pass


def safe_geocode(query):
    if not query:
        return None, None
    if query in geo_cache:
        return geo_cache[query]

    params = {
        "key": LOCATIONIQ_KEY,
        "q": query,
        "format": "json",
        "limit": 1,
    }

    for attempt in range(3):
        try:
            # Stay under rate limits
            time.sleep(0.6 + random.uniform(0.1, 0.3))
            r = requests.get(GEO_URL, params=params, timeout=10)

            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    geo_cache[query] = [lat, lon]
                    return lat, lon
                break

            elif r.status_code in (400, 404):
                break
            elif r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue

            elif attempt == 2:
                print(f"Error {r.status_code} geocoding '{query}'")

        except Exception as e:
            if attempt == 2:
                print(f"Exception geocoding '{query}': {e}")

        time.sleep(1)

    geo_cache[query] = [None, None]
    return None, None


def main():
    global geo_cache
    geo_cache = load_cache()

    all_teams = []
    page = 0

    # Fetch all teams from TBA
    while True:
        page_data = tba_get(f"teams/{YEAR}/{page}")
        if not page_data:
            break
        all_teams.extend(page_data)
        page += 1

    print(f"Fetched {len(all_teams)} teams from TBA.")

    # Geocode each team
    for team in tqdm(all_teams, desc="Geocoding", unit="team"):
        location_query = build_location(team)
        if not location_query:
            team["lat"] = None
            team["lng"] = None
            continue
        lat, lng = safe_geocode(location_query)

        team["lat"] = lat
        team["lng"] = lng

    save_cache()

    # Save
    output_path = os.path.join(os.path.dirname(__file__), f"{YEAR}_geo_teams.json")
    with open(output_path, "w") as f:
        json.dump(all_teams, f, indent=2)

    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
