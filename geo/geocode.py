import os
import time
import json
import requests
from geopy.geocoders import Nominatim
from tqdm import tqdm  
from dotenv import load_dotenv

def configure():
    load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

def tba_get(endpoint: str):
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    print(f"Error {r.status_code}: {r.text}")
    return None

# Cache for geocoding results to avoid repeated lookups
geo_cache = {}
geolocator = Nominatim(user_agent="precompute_teams_2025_app")

def geocode_location(item):
    """
    Geocode the location for a given item (team or event) based on its
    'city', 'state_prov', 'postal_code', and 'country' fields.
    Returns a tuple (lat, lng) or (None, None) if geocoding fails.
    """
    # Return early if already geocoded
    if item.get("lat") is not None and item.get("lng") is not None:
        return item["lat"], item["lng"]

    city = item.get("city", "")
    state = item.get("state_prov", "")
    postal = item.get("postal_code", "")
    country = item.get("country", "")

    parts = [p for p in [city, state, postal, country] if p]
    if not parts:
        return None, None

    address_str = ", ".join(parts)
    if address_str in geo_cache:
        return geo_cache[address_str]

    try:
        time.sleep(1)  # Delay to be kind to the geocoding service
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
    # Load environment variables, including TBA_API_KEY
    configure()

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

    print("Processing each team's geocoding and event registration...")
    for team in tqdm(all_teams, desc="Processing teams", unit="team"):
        # Geocode the team's location
        lat, lng = geocode_location(team)
        team["lat"] = lat
        team["lng"] = lng

        # Fetch the competitions (events) the team is registered for this year
        team_key = team.get("key")
        if team_key:
            events = tba_get(f"team/{team_key}/events/{year}")
            if events is None:
                events = []
            # Geocode each event's location if necessary
            for event in events:
                event_lat, event_lng = geocode_location(event)
                event["lat"] = event_lat
                event["lng"] = event_lng
                time.sleep(0.5)  # Small delay between event geocoding requests
            team["events"] = events
            time.sleep(0.5)  # Small delay between team event requests
        else:
            team["events"] = []

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_teams, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(all_teams)} teams to '{out_file}'.")
    print("Done!")

if __name__ == "__main__":
    main()
