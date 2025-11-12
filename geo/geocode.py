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

def build_address(team):
    """
    Build the most specific address possible for geocoding.
    Priority order:
    1. School name + city + state + postal code (most specific - geocoders can find schools by name)
    2. City + state + postal code (fallback if no school name)
    
    Note: Geocoding services like LocationIQ can successfully geocode school names
    when combined with location context (city, state, postal code).
    """
    # Try school name + location (geocoders are good at finding schools by name)
    school_name = team.get("school_name")
    if school_name:
        # Clean up school name - if it has multiple schools (separated by &), use just the first one
        # Also limit length to avoid 400 errors from overly long queries
        cleaned_school_name = school_name.split(" & ")[0].split(",")[0].strip()
        # Limit to 100 characters to avoid query length issues
        if len(cleaned_school_name) > 100:
            cleaned_school_name = cleaned_school_name[:100].rsplit(" ", 1)[0]  # Cut at word boundary
        
        parts = [cleaned_school_name]
        city = team.get("city")
        state = team.get("state_prov")
        postal_code = team.get("postal_code")
        country = team.get("country")
        
        # Add location context to help geocoder
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if postal_code:
            parts.append(postal_code)
        elif country:  # Only add country if no postal code
            parts.append(country)
        return ", ".join([p for p in parts if p])
    
    # Fallback to basic location info (city + state + postal code)
    parts = [team.get("city"), team.get("state_prov"), team.get("postal_code"), team.get("country")]
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

    for attempt in range(3):  # Reduced retries since we have fallback strategies
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
                # Empty result means not found, don't retry
                break
            elif r.status_code in (400, 404):
                # 400/404 mean bad request or not found - don't retry, just return None
                # 400 often means query too long or malformed
                break
            else:
                # Only print error on last attempt to reduce noise
                if attempt == 2:
                    print(f"Error {r.status_code} geocoding '{address}'")
        except Exception as e:
            # Only print error on last attempt
            if attempt == 2:
                print(f"Exception geocoding '{address}': {e}")
            time.sleep(1)
    
    # Cache the failure so we don't retry the same address
    geo_cache[address] = (None, None)
    return None, None

def main():
    all_teams = []
    page = 0
    while True:
        page_data = tba_get(f"teams/{YEAR}/{page}")
        if not page_data:
            break
        all_teams.extend(page_data)
        page += 1

    print(f"Fetched {len(all_teams)} teams.")

    for team in tqdm(all_teams, desc="Geocoding", unit="team"):
        # Try multiple address strategies for better accuracy
        addresses_to_try = []
        
        # Strategy 1: Most specific (school name + location)
        primary_address = build_address(team)
        addresses_to_try.append(primary_address)
        
        # Strategy 2: If we used school name, also try without it as fallback
        # Sometimes geocoders struggle with school names, so try postal code + city + state
        if team.get("school_name") and primary_address.startswith(team.get("school_name", "")):
            # Try with postal code + city + state (very specific)
            fallback_parts = []
            postal_code = team.get("postal_code")
            city = team.get("city")
            state = team.get("state_prov")
            
            if postal_code:
                fallback_parts.append(postal_code)
            if city:
                fallback_parts.append(city)
            if state:
                fallback_parts.append(state)
            
            fallback_address = ", ".join([p for p in fallback_parts if p])
            if fallback_address and fallback_address != primary_address:
                addresses_to_try.append(fallback_address)
            
            # Strategy 3: Just city + state (last resort)
            simple_parts = [city, state]
            simple_address = ", ".join([p for p in simple_parts if p])
            if simple_address and simple_address not in addresses_to_try:
                addresses_to_try.append(simple_address)
        
        # Try each address strategy until one works
        lat, lng = None, None
        for address in addresses_to_try:
            lat, lng = safe_geocode(address)
            if lat is not None and lng is not None:
                break
        
        team["lat"] = lat
        team["lng"] = lng

    with open(f"{YEAR}_geo_teams.json", "w") as f:
        json.dump(all_teams, f, indent=2)

    print(f"Saved {YEAR}_geo_teams.json")

if __name__ == "__main__":
    main()
