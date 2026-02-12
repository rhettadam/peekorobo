#!/usr/bin/env python3
"""
Generate a simple JSON file containing all team numbers, nicknames, and last year participated.
This creates a mapping of team_number -> {nickname, last_year}, matching the existing teams.json format.
"""

import json
import os
from dotenv import load_dotenv
from datagather import DatabaseConnection

load_dotenv()

def generate_teams_simple():
    """Generate a simple JSON file with team numbers, nicknames, and last year."""
    
    print("🚀 Starting simple teams data extraction...")
    
    teams_dict = {}
    
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            
            # Get all teams with their nicknames from the most recent year and last year participated
            print("👥 Extracting team numbers, nicknames, and last year...")
            cur.execute("""
                WITH team_last_year AS (
                    SELECT team_number, MAX(year) as last_year
                    FROM team_epas
                    GROUP BY team_number
                )
                SELECT t.team_number, t.nickname, tly.last_year
                FROM teams t
                LEFT JOIN team_last_year tly ON t.team_number = tly.team_number
                ORDER BY t.team_number
            """)
            
            for row in cur.fetchall():
                team_number, nickname, last_year = row
                teams_dict[str(team_number)] = {
                    "nickname": nickname or "",
                    "last_year": int(last_year) if last_year else None
                }
            
            print(f"✅ Found {len(teams_dict)} teams")
            
    except Exception as e:
        print(f"❌ Error extracting data: {e}")
        raise
    
    # Save to JSON file
    print("💾 Saving to teams.json...")
    output_file = "data/teams.json"
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(teams_dict, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully saved {len(teams_dict)} teams to {output_file}")
    
    # Show year distribution
    year_counts = {}
    for team_info in teams_dict.values():
        last_year = team_info.get("last_year")
        if last_year:
            year_counts[last_year] = year_counts.get(last_year, 0) + 1
    
    print(f"\n📅 Teams by Last Year:")
    for year in sorted(year_counts.keys(), reverse=True):
        print(f"   {year}: {year_counts[year]} teams")
    
    return teams_dict

if __name__ == "__main__":
    generate_teams_simple()

