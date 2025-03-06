import os
import json
import requests
from dotenv import load_dotenv

def configure():
    load_dotenv()

# Load environment variables from .env file
configure()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
# Endpoint template for simple event info for a given year
endpoint_template = "events/{year}/simple"

def tba_get(endpoint: str):
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

all_events = {}

# Loop from 1992 to 2025 (inclusive)
for year in range(1992, 2026):
    endpoint = endpoint_template.format(year=year)
    events = tba_get(endpoint)
    
    if events is not None:
        event_list = []
        for event in events:
            # Build a location string from city, state/province, and country
            city = event.get("city", "")
            state_prov = event.get("state_prov", "")
            country = event.get("country", "")
            location_parts = [part for part in [city, state_prov, country] if part]
            location = ", ".join(location_parts) if location_parts else None

            # Create a dictionary with the desired event details
            event_data = {
                "event_code": event.get("event_code"),
                "name": event.get("name"),
                "start_date": event.get("start_date"),
                "end_date": event.get("end_date"),
                "event_type": event.get("event_type"),  # Alternatively, event.get("event_type_string")
                "location": location,
                "website": event.get("website")
            }
            event_list.append(event_data)
        all_events[year] = event_list
        print(f"Year {year}: Retrieved {len(event_list)} events.")
    else:
        print(f"Failed to fetch events for {year}.")

output_filename = "tba_events_1992_2025.json"
with open(output_filename, "w") as f:
    json.dump(all_events, f, indent=4)

print(f"\nSaved all event data to {output_filename}")
