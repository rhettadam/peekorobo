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
API_KEYS = os.getenv("TBA_API_KEYS").split(',')
LOCATIONIQ_KEY = os.getenv("LOCATIONIQ_API_KEY") or "pk.62a48aee2f1255204a72a9934eb15b47"
YEAR = 2025
GEO_URL = "https://us1.locationiq.com/v1/search.php"

geo_cache = {}

def tba_get(endpoint: str):
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
    postal = team.get("postal_code")

    # Best option: ZIP + City + State
    if postal:
        return ", ".join([postal, city, state] if city and state else [postal])

    # Fallback: City + State
    parts = [city, state]
    return ", ".join([p for p in parts if p])


def safe_geocode(query):
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
                    geo_cache[query] = (lat, lon)
                    return lat, lon
                break

            elif r.status_code in (400, 404):
                break

            elif attempt == 2:
                print(f"Error {r.status_code} geocoding '{query}'")

        except Exception as e:
            if attempt == 2:
                print(f"Exception geocoding '{query}': {e}")

        time.sleep(1)

    geo_cache[query] = (None, None)
    return None, None


def main():
    all_teams = []
    page = 0

    # Fetch all teams
    while True:
        page_data = tba_get(f"teams/{YEAR}/{page}")
        if not page_data:
            break
        all_teams.extend(page_data)
        page += 1

    print(f"Fetched {len(all_teams)} teams.")

    # Geocode each team
    for team in tqdm(all_teams, desc="Geocoding", unit="team"):
        location_query = build_location(team)
        lat, lng = safe_geocode(location_query)

        team["lat"] = lat
        team["lng"] = lng

    # Save
    with open(f"{YEAR}_geo_teams.json", "w") as f:
        json.dump(all_teams, f, indent=2)

    print(f"Saved {YEAR}_geo_teams.json")


if __name__ == "__main__":
    main()
