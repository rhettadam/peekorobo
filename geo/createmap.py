import folium
from folium.plugins import MarkerCluster, Search, HeatMap
import json
import os
import numpy as np
import sqlite3
from dotenv import load_dotenv
from folium.features import GeoJson  
from folium import IFrame
import requests

load_dotenv()

# District to state/province mapping
DISTRICT_STATES = {
    "ONT": ["Ontario"],
    "FMA": ["Delaware", "New Jersey", "Pennsylvania"],
    "ISR": ["Israel"],
    "CHS": ["Maryland", "Virginia", "District of Columbia"],
    "FIT": ["Texas", "New Mexico"],
    "PCH": ["Georgia"],
    "PNW": ["Washington", "Oregon"],
    "FIM": ["Michigan"],
    "FSC": ["South Carolina"],
    "FNC": ["North Carolina"],
    "FIN": ["Indiana"],
    "NE": ["Connecticut", "Massachusetts", "Maine", "New Hampshire", "Vermont"],
}

# District colors
DISTRICT_COLORS = {
    "ONT": "#1f77b4",  # blue
    "FMA": "#ff7f0e",  # orange
    "ISR": "#2ca02c",  # green
    "CHS": "#d62728",  # red
    "FIT": "#9467bd",  # purple
    "PCH": "#8c564b",  # brown
    "PNW": "#e377c2",  # pink
    "FIM": "#7f7f7f",  # gray
    "FSC": "#bcbd22",  # yellow-green
    "FNC": "#17becf",  # cyan
    "FIN": "#ff9896",  # light red
    "NE": "#98df8a",   # light green
}

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

def get_event_marker_color(event):
    etype = event.get("event_type_string", "").lower()
    if "regional" in etype:
        return "blue"
    elif "district" in etype:
        return "green"
    elif "championship" in etype:
        return "orange"  # folium doesn't have 'gold', so use orange
    elif "offseason" in etype or "off-season" in etype:
        return "gray"
    else:
        return "red"

def get_state_geojson():
    """Get GeoJSON data for US states and Canadian provinces"""
    # Try to load from cache first
    cache_file = "state_boundaries.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            data = json.load(f)
    else:
        # If not cached, fetch from Natural Earth Data
        url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Cache the data
            with open(cache_file, "w") as f:
                json.dump(data, f)
        else:
            return None
    
    # Get list of all states/provinces in FRC districts
    district_states = []
    for states in DISTRICT_STATES.values():
        district_states.extend(states)
    
    # Filter features to only include states/provinces in FRC districts
    filtered_features = []
    for feature in data['features']:
        state_name = feature['properties']['name']
        if state_name in district_states:
            filtered_features.append(feature)
    
    # Create new GeoJSON with only the filtered features
    filtered_geojson = {
        'type': 'FeatureCollection',
        'features': filtered_features
    }
    
    return filtered_geojson

def style_district(feature):
    """Style function for district boundaries"""
    state_name = feature['properties']['name']
    district = None
    
    # Find which district this state belongs to
    for d, states in DISTRICT_STATES.items():
        if state_name in states:
            district = d
            break
    
    if district:
        return {
            'fillColor': DISTRICT_COLORS.get(district, '#808080'),
            'color': '#000000',
            'weight': 2,
            'fillOpacity': 0.3
        }
    return {
        'fillColor': '#808080',
        'color': '#000000',
        'weight': 1,
        'fillOpacity': 0.1
    }

def highlight_district(feature):
    """Highlight function for district boundaries"""
    return {
        'fillOpacity': 0.5,
        'weight': 2
    }

def generate_team_event_map(output_file="teams_map.html"):
    teams_data = load_team_data()
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]
    map_teams = calculate_global_rankings(map_teams)

    # Load events
    with open("2025_geo_events.json", "r", encoding="utf-8") as f:
        events_data = json.load(f)
    map_events = [e for e in events_data if e.get("lat") and e.get("lng")]

    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

    # --- Districts Layer ---
    districts_layer = folium.FeatureGroup(name="FRC Districts", show=False)
    state_geojson = get_state_geojson()
    if state_geojson:
        GeoJson(
            state_geojson,
            name='District Boundaries',
            style_function=style_district,
            highlight_function=highlight_district,
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['State/Province:'],
                style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
            )
        ).add_to(districts_layer)

    # --- Teams Layer ---
    teams_layer = folium.FeatureGroup(name="FRC Teams", show=True)
    cluster = MarkerCluster(name="Team Clusters").add_to(teams_layer)
    search_layer = folium.FeatureGroup(name="Search Layer", show=False)

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
<b>ACE:</b> {team.get('epa_display', 'N/A')}<br>
<a href='https://www.peekorobo.com/team/{team['team_number']}' target='_blank' rel='noopener noreferrer'>View Team</a>
""".strip()
        iframe = IFrame(popup_html, width=350, height=150)
        popup = folium.Popup(iframe, max_width=500)

        color = get_marker_color(team.get("epa"), percentiles)

        folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=label,
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(cluster)

        # Invisible searchable marker for teams
        search_label = f"Team {team['team_number']}: {team.get('nickname', '')} - {team.get('city', '')}, {team.get('state_prov', '')}"
        marker = folium.CircleMarker(
            location=[lat, lng],
            radius=0.0001,
            fill=True,
            fill_opacity=0,
            opacity=0,
            popup=popup_html
        )
        marker.add_to(search_layer)
        marker.options.update({"name": search_label})

    # --- Events Layer ---
    events_layer = folium.FeatureGroup(name="FRC Events", show=True)
    
    for event in map_events:
        lat, lng = event["lat"], event["lng"]
        etype = event.get("event_type_string", "Unknown")
        color = get_event_marker_color(event)
        popup_html = f"""
<b>{event['name']}</b><br>
{event.get('city', '')}, {event.get('state_prov', '')}, {event.get('country', '')}<br>
<b>Type:</b> {etype}<br>
<b>Dates:</b> {event.get('start_date', '')} - {event.get('end_date', '')}<br>
<a href='https://www.peekorobo.com/event/{event['key']}' target='_blank'>View Event</a>
""".strip()
        iframe = IFrame(popup_html, width=350, height=150)
        popup = folium.Popup(iframe, max_width=500)
        folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=event['name'],
            icon=folium.Icon(color=color, icon="star")
        ).add_to(events_layer)

        # Add invisible searchable marker for events
        search_label = f"Event {event.get('event_code', '')}: {event['name']} - {event.get('city', '')}, {event.get('state_prov', '')}"
        marker = folium.CircleMarker(
            location=[lat, lng],
            radius=0.0001,
            fill=True,
            fill_opacity=0,
            opacity=0,
            popup=popup_html
        )
        marker.add_to(search_layer)
        marker.options.update({"name": search_label})

    # --- Heatmap Layer ---
    heatmap_layer = folium.FeatureGroup(name="Team Density Heatmap", show=False)
    heat_data = [[t["lat"], t["lng"]] for t in map_teams if t.get("lat") and t.get("lng")]
    HeatMap(heat_data, radius=16, blur=12, min_opacity=0.3, max_zoom=12).add_to(heatmap_layer)

    # Add all layers to map
    teams_layer.add_to(m)
    search_layer.add_to(m)
    events_layer.add_to(m)
    heatmap_layer.add_to(m)
    districts_layer.add_to(m)

    # Add combined search bar
    Search(
        layer=search_layer,
        search_label="name",
        placeholder="Search teams & events by name, number, code, city...",
        collapsed=False
    ).add_to(m)

    # Add LayerControl
    folium.LayerControl(collapsed=False).add_to(m)

    # Shrink the search box
    m.get_root().html.add_child(folium.Element("""
    <style>
    .leaflet-control-search input {
        width: 250px !important;
        font-size: 12px;
        padding: 3px;
    }
    </style>
    """))

    # Add legend for event marker colors
    legend_html = '''
     <div style="position: fixed; bottom: 40px; left: 40px; z-index:9999; background: white; border:2px solid #444; padding: 10px; border-radius: 8px; font-size: 14px;">
     <b>Event Marker Colors</b><br>
     <i class="fa fa-star" style="color: blue"></i> Regional<br>
     <i class="fa fa-star" style="color: green"></i> District<br>
     <i class="fa fa-star" style="color: orange"></i> Championship<br>
     <i class="fa fa-star" style="color: gray"></i> Offseason<br>
     <i class="fa fa-star" style="color: red"></i> Preseason<br>
     </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    m.save(output_file)
    print(f"✅ Map saved with teams, events, heatmap, and legend: {output_file}")

if __name__ == "__main__":
    generate_team_event_map()
