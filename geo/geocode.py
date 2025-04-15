import os
import json
import requests
import time
import random
import concurrent.futures
from tqdm import tqdm
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load environment variables
load_dotenv()
TBA_KEYS = os.getenv("TBA_API_KEYS")
if not TBA_KEYS:
    raise ValueError("TBA_API_KEYS not found in .env")
API_KEYS = TBA_KEYS.split(",")

TBA_URL = "https://www.thebluealliance.com/api/v3"
geolocator = Nominatim(user_agent="peekorobo_2025_geocoder")
geo_cache = {}

@retry(stop=stop_after_attempt(10), wait=wait_exponential(min=0.2, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_URL}/{endpoint}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=0.2, max=5), retry=retry_if_exception_type(Exception))
def geocode_location_retry(address_str):
    return geolocator.geocode(address_str, timeout=10)

def geocode_location(item):
    if item.get("lat") is not None and item.get("lng") is not None:
        return item["lat"], item["lng"]

    address = ", ".join(filter(None, [item.get("city"), item.get("state_prov"), item.get("postal_code"), item.get("country")]))
    if not address:
        return None, None

    if address in geo_cache:
        return geo_cache[address]

    try:
        time.sleep(0.1)
        loc = geocode_location_retry(address)
        coords = (loc.latitude, loc.longitude) if loc else (None, None)
    except Exception:
        coords = (None, None)

    geo_cache[address] = coords
    return coords

def process_team(team, year):
    team["lat"], team["lng"] = geocode_location(team)
    team_key = team.get("key", "")
    if not team_key:
        team["events"] = []
        return team

    try:
        events = tba_get(f"team/{team_key}/events/{year}")
    except Exception as e:
        print(f"Error fetching events for {team_key}: {e}")
        team["events"] = []
        return team

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(geocode_location, evt): evt for evt in events}
        for future in concurrent.futures.as_completed(futures):
            evt = futures[future]
            try:
                evt["lat"], evt["lng"] = future.result()
            except Exception:
                evt["lat"], evt["lng"] = None, None

    team["events"] = events
    return team

def main():
    year = 2025
    all_teams = []
    page = 0
    print("Fetching teams from TBA...")
    while True:
        data = tba_get(f"teams/{year}/{page}")
        if not data:
            break
        all_teams.extend(data)
        page += 1

    print(f"Total teams fetched: {len(all_teams)}")

    processed_teams = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(process_team, team, year) for team in all_teams]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Geocoding & Processing"):
            try:
                processed_teams.append(future.result())
            except Exception as e:
                print(f"Failed to process team: {e}")

    out_file = f"teams_{year}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(processed_teams, f, indent=2)
    print(f"Saved {len(processed_teams)} teams to {out_file}")

if __name__ == "__main__":
    main()
