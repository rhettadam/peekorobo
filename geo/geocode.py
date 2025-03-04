import os
import json
import requests
import time
from dotenv import load_dotenv
from tqdm import tqdm
import concurrent.futures
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type

# Load environment variables from .env
def configure():
    load_dotenv()

TBA_API_BASE_URL = "https://www.thebluealliance.com/api/v3"

# Retry indefinitely on any exception.
@retry(stop=stop_never, wait=wait_exponential(multiplier=1, min=0.5, max=5),
       retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_API_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

# Set up caching for geocoding.
geo_cache = {}
from geopy.geocoders import Nominatim
geolocator = Nominatim(user_agent="precompute_teams_2025_app")

@retry(stop=stop_never, wait=wait_exponential(multiplier=1, min=0.5, max=5),
       retry=retry_if_exception_type(Exception))
def geocode_location_retry(address_str):
    return geolocator.geocode(address_str)

def geocode_location(item):
    """
    Geocode an item (team or event) based on its 'city', 'state_prov',
    'postal_code', and 'country' fields. Returns (lat, lng) or (None, None).
    Uses a cache to avoid redundant lookups.
    """
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
        # Minimal delay to be fast but still polite
        time.sleep(0.2)
        loc = geocode_location_retry(address_str)
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

def process_team(team, year):
    """
    Process a single team:
      - Geocode the team's location.
      - Fetch the events (competitions) for the team in the given year.
      - Geocode each event's location.
      - Return the updated team dictionary.
    """
    # Geocode team location.
    lat, lng = geocode_location(team)
    team["lat"] = lat
    team["lng"] = lng

    # Fetch team events.
    team_key = team.get("key")
    if team_key:
        events = tba_get(f"team/{team_key}/events/{year}") or []
        # Process each event concurrently.
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_event = {executor.submit(geocode_location, event): event for event in events}
            for future in concurrent.futures.as_completed(future_to_event):
                event = future_to_event[future]
                try:
                    event_lat, event_lng = future.result()
                except Exception as e:
                    print(f"Error geocoding event for team {team_key}: {e}")
                    event_lat, event_lng = None, None
                event["lat"] = event_lat
                event["lng"] = event_lng
        team["events"] = events
    else:
        team["events"] = []
    return team

def main():
    configure()
    year = 2025
    out_file = f"teams_{year}.json"

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

    total_teams = len(all_teams)
    print(f"\nFetched {total_teams} teams total for {year}.")

    print("Processing each team's geocoding and event registration...")
    processed_teams = []
    # Process teams concurrently using a ThreadPoolExecutor.
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_team, team, year) for team in all_teams]
        pbar = tqdm(total=len(futures), desc="Processing teams")
        for future in concurrent.futures.as_completed(futures):
            try:
                processed_teams.append(future.result())
            except Exception as e:
                print(f"Error processing a team: {e}")
            pbar.update(1)
        pbar.close()

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(processed_teams, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(processed_teams)} teams to '{out_file}'.")
    print("Done!")

if __name__ == "__main__":
    main()
