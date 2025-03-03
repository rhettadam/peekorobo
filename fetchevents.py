import os
import json
import requests

# Replace this with your TBA API key or fetch it from an environment variable
TBA_API_KEY = "lsSSM1GgCjbFqObJKWADdAzE4DNoO7gEu2nO4cyATZnLJTWEaIKrHfItkfYaM25M"

# Adjust as needed
YEAR_RANGE = range(2016, 2026)  # E.g., from 2016 to 2024

# Optionally define or import this if you have a routine to compute EPA data
def load_teams_and_compute_epa_ranks(event_year):
    """
    Stubbed function. Replace with your actual logic to compute EPA data for teams.
    Must return a dictionary keyed by team number (string), with 'rank' and 'epa_display' fields, e.g.:
    {
        "123": {"rank": 10, "epa_display": "42.1 ⭐"},
        "456": {"rank": 15, "epa_display": "38.7 🌟"},
        ...
    }
    """
    # For demonstration, just return an empty dict
    return {}

# Helper function to handle TBA GET requests
def tba_get(endpoint):
    """
    Fetch data from TBA API v3 endpoint.
    Example: tba_get("event/2023miket") -> JSON
    """
    base_url = "https://www.thebluealliance.com/api/v3/"
    headers = {"X-TBA-Auth-Key": TBA_API_KEY}
    url = f"{base_url}{endpoint}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    # Make sure 'events' directory exists
    os.makedirs("events", exist_ok=True)

    for year in YEAR_RANGE:
        print(f"Fetching events for {year}...")
        # Get all events for the given year
        events_list = tba_get(f"events/{year}")
        if not events_list:
            print(f"No events found for {year}. Skipping...")
            continue

        # Pre-load the relevant EPA data (only if you need it)
        epa_data_for_year = load_teams_and_compute_epa_ranks(year)

        # Dictionary to hold all data for this year
        year_data = {}

        # Loop over all events of that year
        for event in events_list:
            event_key = event["key"]
            print(f"  Processing event: {event_key}")

            # Fetch the specific data sets
            event_details = tba_get(f"event/{event_key}") or {}
            rankings = tba_get(f"event/{event_key}/rankings") or {}
            oprs = tba_get(f"event/{event_key}/oprs") or {}
            coprs = tba_get(f"event/{event_key}/coprs") or {}
            insights = tba_get(f"event/{event_key}/insights") or {}

            # Save to the dictionary
            year_data[event_key] = {
                "event_details": event_details,
                "rankings": rankings,
                "oprs": oprs,
                "coprs": coprs,
                "insights": insights,
                # Optionally attach epa_data_for_year if you want to integrate
                # that with your event data
                "epa_data": epa_data_for_year,
            }

        # Write out the entire year's data to events/{year}.json
        output_path = f"events/{year}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(year_data, f, indent=4, ensure_ascii=False)

        print(f"Finished writing {year} data to {output_path}.\n")

if __name__ == "__main__":
    main()
