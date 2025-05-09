import folium
from folium.plugins import MarkerCluster, Search
import json
import os
import numpy as np
import sqlite3
from dotenv import load_dotenv
from folium.features import GeoJson  
from folium import IFrame

load_dotenv()

def load_team_data(locations_file="2025_geo_teams.json", epa_db="epa_teams.sqlite"):
    if not os.path.exists(locations_file) or not os.path.exists(epa_db):
        return []
    with open(locations_file, "r", encoding="utf-8") as f:
        location_data = json.load(f)
    conn = sqlite3.connect(epa_db)
    cursor = conn.cursor()
    cursor.execute("SELECT team_number, epa FROM epa_history WHERE year = 2025")
    epa_rows = cursor.fetchall()
    conn.close()
    epa_dict = {team_num: epa for team_num, epa in epa_rows}
    for team in location_data:
        team_number = team.get("team_number")
        team["epa"] = epa_dict.get(team_number)
    return location_data

def calculate_global_rankings(teams_data):
    sorted_teams = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)
    epa_values = [team["epa"] for team in sorted_teams if team.get("epa") is not None]
    percentiles = {
        "99": np.percentile(epa_values, 99) if epa_values else 0,
        "95": np.percentile(epa_values, 95) if epa_values else 0,  # ADD THIS
        "90": np.percentile(epa_values, 90) if epa_values else 0,
        "75": np.percentile(epa_values, 75) if epa_values else 0,
        "50": np.percentile(epa_values, 50) if epa_values else 0,  # AND THIS
        "25": np.percentile(epa_values, 25) if epa_values else 0,
    }
    for idx, team in enumerate(sorted_teams):
        team["global_rank"] = idx + 1
        team["epa_display"] = get_epa_display(team.get("epa"), percentiles)
    return sorted_teams

def get_epa_display(epa, percentiles):
    if epa is None:
        return "N/A"
    if epa >= percentiles["99"]:
        color = "🟣"  # Purple
    elif epa >= percentiles["95"]:
        color = "🔵"  # Blue
    elif epa >= percentiles["90"]:
        color = "🟢"  # Green
    elif epa >= percentiles["75"]:
        color = "🟠"  # Orange
    elif epa >= percentiles["50"]:
        color = "🔴"  # Red
    elif epa <= percentiles["25"]:
        color = "🟤"  # Brown
    else:
        color = "⚪"
    return f"{color} {epa:.2f}"

def get_marker_color(epa, percentiles):
    if epa is None:
        return "gray"
    if epa >= percentiles["99"]:
        return "purple"
    elif epa >= percentiles["95"]:
        return "blue"
    elif epa >= percentiles["90"]:
        return "green"
    elif epa >= percentiles["75"]:
        return "orange"
    elif epa >= percentiles["50"]:
        return "red"
    elif epa <= percentiles["25"]:
        return "darkred"
    else:
        return "darkred"


def generate_team_map(output_file="teams_map.html"):
    teams_data = load_team_data()
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]
    map_teams = calculate_global_rankings(map_teams)

    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
    cluster = MarkerCluster(name="FRC Teams").add_to(m)
    search_layer = folium.FeatureGroup(name="Search Layer (invisible)", show=False).add_to(m)

    epa_values = [t["epa"] for t in map_teams if t.get("epa") is not None]
    percentiles = {
        "99": np.percentile(epa_values, 99) if epa_values else 0,
        "95": np.percentile(epa_values, 95) if epa_values else 0,
        "90": np.percentile(epa_values, 90) if epa_values else 0,
        "75": np.percentile(epa_values, 75) if epa_values else 0,
        "50": np.percentile(epa_values, 50) if epa_values else 0,
        "25": np.percentile(epa_values, 25) if epa_values else 0,
    }

    for team in map_teams:
        lat, lng = team["lat"], team["lng"]
        label = f"{team['team_number']} {team.get('nickname', '')} ({team.get('city', '')}, {team.get('state_prov', '')}, {team.get('country', '')})".strip()

        popup_html = f"""
            <b>Team {team['team_number']}:</b> {team.get('nickname', '')}<br>
            <b>Location:</b> {team.get('city', '')}, {team.get('state_prov', '')}, {team.get('country', '')}<br>
            <b>Global Rank:</b> #{team.get('global_rank', 'N/A')}<br>
            <b>EPA:</b> {team.get('epa_display', 'N/A')}<br>
            <a href='/team/{team['team_number']}' target='_top'>View Team Page</a>
        """
        iframe = IFrame(popup_html, width=350, height=150)
        popup = folium.Popup(iframe, max_width=500)

        color = get_marker_color(team.get("epa"), percentiles)

        folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=label,
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(cluster)

        # Invisible searchable marker
        marker = folium.CircleMarker(
            location=[lat, lng],
            radius=0.0001,
            fill=True,
            fill_opacity=0,
            opacity=0,
            popup=popup_html
        )
        marker.add_to(search_layer)
        marker.options.update({"name": label})

    Search(
        layer=search_layer,
        search_label="name",
        placeholder="Search team number, name, city...",
        collapsed=False
    ).add_to(m)

    # Shrink the search box
    m.get_root().html.add_child(folium.Element("""
    <style>
    .leaflet-control-search input {
        width: 180px !important;
        font-size: 12px;
        padding: 3px;
    }
    </style>
    """))

    folium.LayerControl().add_to(m)

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    m.save(output_file)
    print(f"✅ Map saved with EPA-colored markers, search, and compact legend: {output_file}")


if __name__ == "__main__":
    generate_team_map()
