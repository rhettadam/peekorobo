import os
import time
import json
import requests
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from tqdm import tqdm  

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
TBA_KEY = os.getenv("TBA_API_KEY")
if not TBA_KEY:
    raise ValueError("No TBA_API_KEY found in environment/.env")

def tba_get(endpoint: str):
    headers = {"X-TBA-Auth-Key": TBA_KEY}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        print(f"Warning: TBA returned {r.status_code} for {url}")
        return None

geo_cache = {}
geolocator = Nominatim(user_agent="precompute_teams_2025_app")

def geocode_city_state_postal(team):

    if team.get("lat") is not None and team.get("lng") is not None:
        return team["lat"], team["lng"]

    city = team.get("city", "")
    state = team.get("state_prov", "")
    postal = team.get("postal_code", "")
    country = team.get("country", "")

    parts = [p for p in [city, state, postal, country] if p]
    if not parts:
        return None, None

    address_str = ", ".join(parts)

    if address_str in geo_cache:
        return geo_cache[address_str]

    try:
        time.sleep(1)  
        loc = geolocator.geocode(address_str)
        if loc:
            lat, lng = loc.latitude, loc.longitude
            geo_cache[address_str] = (lat, lng)
            return lat, lng
        else:
            geo_cache[address_str] = (None, None)
            return None, None
    except Exception as e:
        print(f"Geocode error for '{address_str}': {e}")
        geo_cache[address_str] = (None, None)
        return None, None

def main():

    year = 2025
    out_file = "teams_2025.json"

    print(f"Precomputing data for year={year}...")

    all_teams = []
    page_num = 0
    while True:
        endpoint = f"teams/{year}/{page_num}"

        page_data = tba_get(endpoint)
        if not page_data:
            break

        all_teams.extend(page_data)
        page_num += 1

    print(f"\nFetched {len(all_teams)} teams total for {year}.")

    print("Geocoding each team's city/state/postal/country...")
    for team in tqdm(all_teams, desc="Geocoding", unit="team"):
        lat, lng = geocode_city_state_postal(team)
        team["lat"] = lat
        team["lng"] = lng

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_teams, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(all_teams)} teams to '{out_file}'.")
    print("Done!")

if __name__ == "__main__":
    main()
