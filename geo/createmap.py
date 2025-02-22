import folium
from folium.plugins import MarkerCluster
import json
import os
import numpy as np
from dotenv import load_dotenv

# Load environment variables
def configure():
    load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

def tba_get(endpoint: str):
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def load_team_data(locations_file="geo/mapteams_2025.json", epa_file="team_data/teams_2024.json"):
    """
    Loads location data from 2025 and EPA rankings from 2024.teams_
    Matches teams by team_number.
    """
    if not os.path.exists(locations_file):
        print(f"Error: Locations file {locations_file} not found.")
        return []
    if not os.path.exists(epa_file):
        print(f"Error: EPA data file {epa_file} not found.")
        return []

    # Load team locations
    with open(locations_file, "r", encoding="utf-8") as f:
        location_data = json.load(f)

    # Load EPA data
    with open(epa_file, "r", encoding="utf-8") as f:
        epa_data = json.load(f)

    # Convert EPA data into a dictionary for quick lookup
    epa_dict = {team["team_number"]: team for team in epa_data}

    # Merge location data with EPA data
    merged_teams = []
    for team in location_data:
        team_number = team.get("team_number")
        if team_number in epa_dict:
            team["epa"] = epa_dict[team_number].get("epa", None)
        else:
            team["epa"] = None  # If no EPA data, assign None
        merged_teams.append(team)

    return merged_teams

def calculate_global_rankings(teams_data):
    """Assign global rankings based on EPA."""
    # Sort teams by EPA descending (higher EPA = better ranking)
    sorted_teams = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)

    # Compute percentiles for ranking
    epa_values = [team["epa"] for team in sorted_teams if team.get("epa") is not None]
    percentiles = {
        "99": np.percentile(epa_values, 99) if epa_values else 0,
        "90": np.percentile(epa_values, 90) if epa_values else 0,
        "75": np.percentile(epa_values, 75) if epa_values else 0,
        "25": np.percentile(epa_values, 25) if epa_values else 0,
    }

    # Assign rankings to teams
    for idx, team in enumerate(sorted_teams):
        team["global_rank"] = idx + 1  # Rank starts at 1
        team["epa_display"] = get_epa_display(team.get("epa", None), percentiles)

    return sorted_teams

def get_epa_display(epa, percentiles):
    """Returns a formatted string with a colored circle based on EPA percentile."""
    if epa is None:
        return "N/A"
    
    if epa >= percentiles["99"]:
        color = "🔵"  # Blue circle
    elif epa >= percentiles["90"]:
        color = "🟢"  # Green circle
    elif epa >= percentiles["75"]:
        color = "🟡"  # Yellow circle
    elif epa >= percentiles["25"]:
        color = "🟠"  # Orange circle
    else:
        color = "🔴"  # Red circle

    return f"{color} {epa:.2f}"

def generate_team_map(output_file="assets/teams_map.html"):
    """
    Generates an interactive map of FRC teams with Global Rank & EPA.
    Saves it as an HTML file.
    """
    # Load team data from 2025 locations and 2024 EPA
    teams_data = load_team_data()

    # Filter only teams with valid lat/lng
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]

    # Calculate Global Rankings & EPA display
    map_teams = calculate_global_rankings(map_teams)

    # Create a Folium map centered on the USA
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles="OpenStreetMap")

    # Add state boundaries (GeoJSON)
    folium.GeoJson(
        "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json",
        name="State Boundaries",
        style_function=lambda x: {
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.1,
        },
    ).add_to(m)

    # Use MarkerCluster for better performance with large datasets
    marker_cluster = MarkerCluster().add_to(m)

    # Add team locations to the map with clickable links & rankings
    for team in map_teams:
        team_id = team["team_number"]
        epa_value = team.get("epa", "N/A")
        global_rank = team.get("global_rank", "N/A")
        epa_display = team.get("epa_display", "N/A")

        popup_html = (
            f"<b>Team {team_id}:</b> {team['nickname']}<br>"
            f"<b>Location:</b> {team['city']}, {team['state_prov']}, {team['country']}<br>"
            f"<b>Global Rank:</b> #{global_rank}<br>"
            f"<b>EPA:</b> {epa_display}<br>"
            f"<a href='/team/{team_id}' target='_top'>View Team Page</a>"
        )

        folium.Marker(
            location=[team["lat"], team["lng"]],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(marker_cluster)

    # Save the map to an HTML file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    m.save(output_file)
    print(f"✅ Map successfully saved to {output_file}")

# Run the script
if __name__ == "__main__":
    generate_team_map()
