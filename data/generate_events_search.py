#!/usr/bin/env python3
"""
Generate a simple JSON file containing all event keys and names.
This creates a mapping of event_key -> event_name, similar to the existing events.json format.
"""

import json
import os
from dotenv import load_dotenv
from datagather import DatabaseConnection

load_dotenv()

def generate_events_simple():
    """Generate a simple JSON file with event keys and names."""
    
    print("🚀 Starting simple events data extraction...")
    
    events_dict = {}
    
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            
            # Get all events with just key and name
            print("📅 Extracting event keys and names...")
            cur.execute("""
                SELECT event_key, name
                FROM events
                ORDER BY year, event_key
            """)
            
            for row in cur.fetchall():
                event_key, name = row
                events_dict[event_key] = name
            
            print(f"✅ Found {len(events_dict)} events")
            
    except Exception as e:
        print(f"❌ Error extracting data: {e}")
        raise
    
    # Save to JSON file
    print("💾 Saving to events.json...")
    output_file = "data/events.json"
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(events_dict, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully saved {len(events_dict)} events to {output_file}")
    
    # Show year distribution
    year_counts = {}
    for event_key in events_dict.keys():
        year = event_key[:4] if len(event_key) >= 4 else 'Unknown'
        year_counts[year] = year_counts.get(year, 0) + 1
    
    print(f"\n📅 Events by Year:")
    for year in sorted(year_counts.keys()):
        print(f"   {year}: {year_counts[year]} events")
    
    return events_dict

if __name__ == "__main__":
    generate_events_simple()
