import folium
from folium.plugins import MarkerCluster, Search, HeatMap, AntPath
import json
import os
import numpy as np
import sqlite3
from dotenv import load_dotenv
from folium.features import GeoJson, CustomIcon
from folium import IFrame
import requests
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the pooled connection getter from datagather.py
from datagather import get_pg_connection, get_connection_pool

# Define database paths relative to the data directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
EVENTS_DB_PATH = os.path.join(DATA_DIR, "events.sqlite")
EPA_TEAMS_DB_PATH = os.path.join(DATA_DIR, "epa_teams.sqlite")

load_dotenv()

# FRC District definitions
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
    "CA": ["California"],  # California district added
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
    "CA": "#00bfff",   # Deep Sky Blue for California
}

def load_team_data(locations_file="2025_geo_teams.json", epa_db=None):
    if not os.path.exists(locations_file):
        return []
    
    with open(locations_file, "r") as f:
        locations = json.load(f)
    
    # Load EPA data from PostgreSQL using connection pool
    conn = get_pg_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT team_number, nickname, city, state_prov, country,
               normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
               wins, losses
        FROM team_epas
        WHERE year = 2025
        ORDER BY team_number
    """)
    
    epa_data = {}
    for row in cursor.fetchall():
        team_number, nickname, city, state_prov, country, \
        normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa, \
        wins, losses = row
        epa_data[team_number] = {
            'nickname': nickname,
            'city': city,
            'state_prov': state_prov,
            'country': country,
            'normal_epa': normal_epa,
            'epa': epa,
            'confidence': confidence,
            'auto_epa': auto_epa,
            'teleop_epa': teleop_epa,
            'endgame_epa': endgame_epa,
            'wins': wins,
            'losses': losses
        }
    
    cursor.close()
    # Return connection to pool
    pool_obj = get_connection_pool()
    pool_obj.putconn(conn)
    
    # Combine location and EPA data
    teams = []
    for team in locations:
        team_number = team.get('team_number')
        if team_number in epa_data:
            team.update(epa_data[team_number])
            teams.append(team)
    
    return teams

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
            # Add district information to properties
            for district, states in DISTRICT_STATES.items():
                if state_name in states:
                    feature['properties']['district'] = district
                    break
            filtered_features.append(feature)
        # Include features that are countries but not in district_states, like Israel
        # Note: This might require more sophisticated logic if you have other non-state/province districts
        # For now, we'll focus on getting district states working correctly.

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

def get_event_teams(event_key):
    """Get list of teams that attended a specific event"""
    conn = sqlite3.connect(EVENTS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tk, nn 
        FROM et 
        WHERE ek = ?
        ORDER BY tk
    """, (event_key,))
    teams = cursor.fetchall()
    conn.close()
    return teams

def get_team_location(team_number, teams_data):
    """Get the location of a team from the teams data"""
    for team in teams_data:
        if str(team.get('team_number')) == str(team_number):
            return team.get('lat'), team.get('lng')
    return None, None

def generate_team_event_map(output_file="teams_map.html"):
    teams_data = load_team_data()
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]
    map_teams = calculate_global_rankings(map_teams)

    # Load week ranges
    with open(os.path.join(os.path.dirname(__file__), '../data/week_ranges.json'), 'r', encoding='utf-8') as f:
        week_ranges = json.load(f)

    # Load events
    with open("2025_geo_events.json", "r", encoding="utf-8") as f:
        events_data = json.load(f)
    
    # Add week number to each event
    for event in events_data:
        start_date = event.get('start_date')
        year = str(event.get('year', '2025'))
        if not start_date or year not in week_ranges:
            event['week'] = None
            continue
        try:
            event_date = datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            event['week'] = None
            continue
        week_found = False
        for i, (range_start, range_end) in enumerate(week_ranges[year], 1):
            try:
                range_start_dt = datetime.strptime(range_start, "%Y-%m-%d")
                range_end_dt = datetime.strptime(range_end, "%Y-%m-%d")
            except Exception:
                continue
            if range_start_dt <= event_date <= range_end_dt:
                event['week'] = i
                week_found = True
                break
        if not week_found:
            event['week'] = None

    map_events = [e for e in events_data if e.get("lat") and e.get("lng")]

    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

    from folium.plugins import MeasureControl
    m.add_child(MeasureControl(primary_length_unit='kilometers'))

    # --- Districts Layer ---
    districts_layer = folium.FeatureGroup(name="Districts", show=False)
    state_geojson = get_state_geojson()
    if state_geojson:
        GeoJson(
            state_geojson,
            name='District Boundaries',
            style_function=style_district,
            highlight_function=highlight_district,
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'district'],
                aliases=['State/Province:', 'District:'],
                style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
            )
        ).add_to(districts_layer)

    # Add a special circle for Israel if needed (this was removed, adding back simplified)
    israel_teams = [t for t in map_teams if t.get('country') == 'Israel']
    if israel_teams:
        # Calculate center of Israel teams
        israel_lats = [t['lat'] for t in israel_teams]
        israel_lngs = [t['lng'] for t in israel_teams]
        if israel_lats and israel_lngs:
             israel_center = [sum(israel_lats)/len(israel_lats), sum(israel_lngs)/len(israel_lngs)]
             folium.Circle(
                 location=israel_center,
                 radius=50000,  # 50km radius
                 color=DISTRICT_COLORS.get('ISR', '#2ca02c'),
                 fill=True,
                 fill_color=DISTRICT_COLORS.get('ISR', '#2ca02c'),
                 fill_opacity=0.3,
                 popup="Israel (ISR)",
                 tooltip="Israel (ISR)"
             ).add_to(districts_layer)

    # --- Teams Layer ---
    teams_layer = folium.FeatureGroup(name="Teams", show=True)
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

        avatar_path = f"../assets/avatars/{team['team_number']}.png"
        if not os.path.exists(avatar_path):
            avatar_path = "../assets/avatars/stock.png"
        icon = CustomIcon(
            avatar_path,
            icon_size=(40, 40),  # Adjust size as needed
            icon_anchor=(20, 20)
        )
        popup_html = f"""
<b>Team {team['team_number']}:</b> {team.get('nickname', '')}<br>
<b>Location:</b> {team.get('city', '')}, {team.get('state_prov', '')}, {team.get('country', '')}<br>
<b>Global Rank:</b> #{team.get('global_rank', 'N/A')}<br>
<b>ACE:</b> {team.get('epa_display', 'N/A')}<br>
<a href='https://www.peekorobo.com/team/{team['team_number']}' target='_blank' rel='noopener noreferrer'>View Team</a>
""".strip()
        iframe = IFrame(popup_html, width=350, height=150)
        popup = folium.Popup(iframe, max_width=500)
        folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=label,
            icon=icon
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
    events_layer = folium.FeatureGroup(name="Events", show=True)
    event_cluster = MarkerCluster(name="Event Clusters").add_to(events_layer)
    
    for event in map_events:
        lat, lng = event["lat"], event["lng"]
        etype = event.get("event_type_string", "Unknown")
        color = get_event_marker_color(event)
        
        popup_html = f"""
<b>{event['name']}</b><br>
{event.get('city', '')}, {event.get('state_prov', '')}, {event.get('country', '')}<br>
<b>Type:</b> {etype}<br>
<b>Dates:</b> {event.get('start_date', '')} - {event.get('end_date', '')}<br>
<b>Week:</b> {event.get('week', 'N/A')}<br>
<a href='https://www.peekorobo.com/event/{event['key']}' target='_blank'>View Event</a>
""".strip()
        iframe = IFrame(popup_html, width=350, height=150)
        popup = folium.Popup(iframe, max_width=500)
        
        # Create marker
        marker = folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=event['name'],
            icon=folium.Icon(color=color, icon="star")
        )
        
        marker.add_to(event_cluster)

        # Add invisible searchable marker for events
        search_label = f"Event {event.get('event_code', '')}: {event['name']} - {event.get('city', '')}, {event.get('state_prov', '')}"
        search_marker = folium.CircleMarker(
            location=[lat, lng],
            radius=0.0001,
            fill=True,
            fill_opacity=0,
            opacity=0,
            popup=popup_html # Using raw html string for search marker consistency
        )
        search_marker.add_to(search_layer)
        search_marker.options.update({"name": search_label})

    # --- Heatmap Layer ---
    heatmap_layer = folium.FeatureGroup(name="Team Density Heatmap", show=False)
    heat_data = [[t["lat"], t["lng"]] for t in map_teams if t.get("lat") and t.get("lng")]
    HeatMap(heat_data, radius=16, blur=12, min_opacity=0.3, max_zoom=12).add_to(heatmap_layer)

    # --- Event Density Heatmap Layer ---
    event_heatmap_layer = folium.FeatureGroup(name="Event Density Heatmap", show=False)
    event_heat_data = [[e["lat"], e["lng"]] for e in map_events if e.get("lat") and e.get("lng")]
    HeatMap(event_heat_data, radius=16, blur=12, min_opacity=0.3, max_zoom=12).add_to(event_heatmap_layer)

    # --- EPA Strength Heatmap ---
    epa_weighted_heat = [[t["lat"], t["lng"], t["epa"]] for t in map_teams if t.get("epa") and t.get("lat") and t.get("lng")]
    epa_heat_layer = folium.FeatureGroup(name="ACE Heatmap", show=False)
    HeatMap(epa_weighted_heat, radius=20, blur=15, min_opacity=0.4).add_to(epa_heat_layer)

    # Add all layers to map
    teams_layer.add_to(m)
    search_layer.add_to(m)
    events_layer.add_to(m)
    heatmap_layer.add_to(m)
    event_heatmap_layer.add_to(m)
    epa_heat_layer.add_to(m)
    districts_layer.add_to(m)

    # Add combined search bar
    Search(
        layer=search_layer,
        search_label="name",
        placeholder="Search teams & events",
        collapsed=False
    ).add_to(m)

    # Add LayerControl
    folium.LayerControl(collapsed=False).add_to(m)

    # Shrink the search box
    m.get_root().html.add_child(folium.Element("""
    <style>
    .leaflet-control-search input {
        width: 150px !important;
        font-size: 12px;
        padding: 3px;
    }
    </style>
    """))

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    m.save(output_file)
    print(f"✅ Map saved with teams, events, heatmap, and legend: {output_file}")

if __name__ == "__main__":
    generate_team_event_map()