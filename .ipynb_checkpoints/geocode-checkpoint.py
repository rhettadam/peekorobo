#!/usr/bin/env python3

import os
import time
import json
import requests
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from tqdm import tqdm  # <-- for progress bars

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

# Simple cache for geocoding results: address_string -> (lat, lon)
geo_cache = {}
geolocator = Nominatim(user_agent="precompute_teams_2025_app")

def geocode_city_state_postal(team):
    """
    Attempt to get (lat, lng) from city, state_prov, postal_code, country.
    Return (lat, lng) or (None, None).
    We do a 1s delay per call to be polite to Nominatim, and cache results to avoid duplicates.
    """
    # If TBA already provided lat/lng (rare, but check anyway)
    if team.get("lat") is not None and team.get("lng") is not None:
        return team["lat"], team["lng"]

    city = team.get("city", "")
    state = team.get("state_prov", "")
    postal = team.get("postal_code", "")
    country = team.get("country", "")

    # Build an address string, e.g. "Pontiac, Michigan, 48340, USA"
    parts = [p for p in [city, state, postal, country] if p]
    if not parts:
        return None, None

    address_str = ", ".join(parts)

    # Check cache first
    if address_str in geo_cache:
        return geo_cache[address_str]

    # Otherwise, geocode via Nominatim
    try:
        time.sleep(1)  # be courteous with Nominatim usage
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
    """
    1) Fetch all teams for year=2025 with a progress bar for each 500-team page.
    2) Geocode each team with a second progress bar.
    3) Write final data to teams_2025.json
    """
    year = 2025
    out_file = "teams_2025.json"

    print(f"Precomputing data for year={year}...")

    # 1) Fetch all pages for 2025
    all_teams = []
    page_num = 0
    while True:
        endpoint = f"teams/{year}/{page_num}"
        # We'll fetch each page in a loop; it's not trivial to guess how many pages upfront.
        # So let's just fetch until we get <500 or None.

        page_data = tba_get(endpoint)
        if not page_data:
            break

        all_teams.extend(page_data)
        page_num += 1

    print(f"\nFetched {len(all_teams)} teams total for {year}.")

    # 2) Now geocode each team. We'll add a progress bar:
    print("Geocoding each team's city/state/postal/country...")
    for team in tqdm(all_teams, desc="Geocoding", unit="team"):
        lat, lng = geocode_city_state_postal(team)
        team["lat"] = lat
        team["lng"] = lng

    # 3) Write to a JSON file
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_teams, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(all_teams)} teams to '{out_file}'.")
    print("Done!")

if __name__ == "__main__":
    main()
