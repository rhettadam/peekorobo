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

def build_address(event):
    # Prefer event['address'] if present, else build from city/state/country
    if event.get("address"):
        return event["address"]
    parts = [event.get("location_name"), event.get("city"), event.get("state_prov"), event.get("postal_code"), event.get("country")]
    return ", ".join([p for p in parts if p])

def safe_geocode(address):
    if address in geo_cache:
        return geo_cache[address]

    params = {
        "key": LOCATIONIQ_KEY,
        "q": address,
        "format": "json",
        "limit": 1,
    }

    for _ in range(5):
        try:
            time.sleep(0.6 + random.uniform(0.1, 0.3))  # stay under 2 req/sec
            r = requests.get(GEO_URL, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    geo_cache[address] = (lat, lon)
                    return lat, lon
                break
            else:
                print(f"Error {r.status_code} geocoding '{address}'")
        except Exception as e:
            print(f"Retrying geocode for '{address}': {e}")
            time.sleep(3)
    geo_cache[address] = (None, None)
    return None, None

def main():
    events = tba_get(f"events/{YEAR}")
    print(f"Fetched {len(events)} events.")

    for event in tqdm(events, desc="Geocoding Events", unit="event"):
        # Only geocode if lat/lng missing or null
        lat = event.get("lat")
        lng = event.get("lng")
        if lat is None or lng is None:
            address = build_address(event)
            lat, lng = safe_geocode(address)
            event["lat"] = lat
            event["lng"] = lng

    with open(f"{YEAR}_geo_events.json", "w") as f:
        json.dump(events, f, indent=2)

    print(f"Saved {YEAR}_geo_events.json")

if __name__ == "__main__":
    main() 