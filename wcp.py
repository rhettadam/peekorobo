#!/usr/bin/env python3
"""
fetch_world_champions_unified.py

Similar to your 'insights_layout' logic, but in a stand-alone script.
Fetches the 'notables_world_champions' category from TBA across multiple years,
collects all teams into a single combined list (no duplicates), 
and prints them out in a simple list.
"""

import os
import requests
from dotenv import load_dotenv

def configure():
    """Load environment variables from .env (where TBA_API_KEY should be stored)."""
    load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

def tba_get(endpoint: str):
    """A minimal GET helper for The Blue Alliance."""
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        print(f"Warning: {url} returned status {r.status_code}")
        return None

def main():
    configure()  # ensure we load the TBA_API_KEY
    TARGET_CATEGORY = "notables_world_champions"

    all_champ_teams = []
    
    # Loop over the years you care about. E.g. 1992 - 2030
    for year in range(1992, 2031):
        # GET the "notables" data for this year
        notables_data = tba_get(f"insights/notables/{year}")
        if not notables_data:
            # No data, or an error from TBA
            continue
        
        # Among the returned categories, find the item named "notables_world_champions"
        champs_item = next(
            (item for item in notables_data if item.get("name") == TARGET_CATEGORY),
            None
        )
        if not champs_item:
            # This year doesn't have that category
            continue
        
        # Extract 'entries' from the item and get each "team_key" (like "frc254")
        entries = champs_item.get("data", {}).get("entries", [])
        for entry in entries:
            team_key = entry.get("team_key", "")
            team_number = team_key.replace("frc", "")
            # Avoid duplicates
            if team_number and team_number not in all_champ_teams:
                all_champ_teams.append(team_number)
    
    # Finally, print them out
    if not all_champ_teams:
        print("No world champion teams found in the given years.")
    else:
        print("Teams that have appeared as 'world champions' at any time:")
        for team in all_champ_teams:
            print(team)

if __name__ == "__main__":
    main()
