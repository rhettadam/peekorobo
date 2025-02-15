import folium
from folium.plugins import MarkerCluster
import json
import os
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
    return None

def generate_team_map(data_file="geo/mapteams_2025.json", output_file="assets/teams_map.html"):
    """
    Generates an interactive map of FRC teams and saves it as an HTML file.

    :param data_file: Path to the JSON file containing team locations.
    :param output_file: Path to save the generated HTML map.
    """
    # Ensure the data file exists
    if not os.path.exists(data_file):
        print(f"Error: Data file {data_file} not found.")
        return

    # Load team data
    with open(data_file, "r", encoding="utf-8") as f:
        teams_data = json.load(f)

    # Filter only teams with valid lat/lng
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]

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

    # Add team locations to the map with clickable links
    for team in map_teams:
        team_id = team["team_number"]
        popup_html = (
            f"<b>Team {team_id}:</b> {team['nickname']}<br>"
            f"<b>Location:</b> {team['city']}, {team['state_prov']}, {team['country']}<br>"
            f"<a href='/data?team={team_id}' target='_top'>View Team Page</a>"
        )

        folium.Marker(
            location=[team["lat"], team["lng"]],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(marker_cluster)

    # Save the map to an HTML file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    m.save(output_file)
    print(f"Map successfully saved to {output_file}")

# Run the script
if __name__ == "__main__":
    generate_team_map()
