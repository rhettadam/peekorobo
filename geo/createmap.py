import folium
from folium.plugins import (
    MarkerCluster, Search, HeatMap, AntPath, MiniMap, MousePosition, 
    LocateControl, FloatImage,
    BeautifyIcon, MeasureControl
)
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
import gzip
import pickle
from functools import lru_cache

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the pooled connection getter from datagather.py
from datagather import get_pg_connection, get_connection_pool

# Define database paths relative to the data directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
EVENTS_DB_PATH = os.path.join(DATA_DIR, "events.sqlite")
EPA_TEAMS_DB_PATH = os.path.join(DATA_DIR, "epa_teams.sqlite")

# Cache directories
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

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

def load_cached_data(cache_file, load_func, *args, **kwargs):
    """Load data from cache or generate and cache it"""
    cache_path = os.path.join(CACHE_DIR, cache_file)
    
    # Check if cache exists and is recent (less than 24 hours old)
    if os.path.exists(cache_path):
        cache_age = datetime.now().timestamp() - os.path.getmtime(cache_path)
        if cache_age < 86400:  # 24 hours
            try:
                with gzip.open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
    
    # Generate data and cache it
    data = load_func(*args, **kwargs)
    try:
        with gzip.open(cache_path, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except:
        pass
    
    return data

@lru_cache(maxsize=128)
def get_team_colors(team_number):
    """Get team colors from the JSON file, with fallback to default colors"""
    try:
        with open('../data/team_colors.json', 'r') as f:
            team_colors_data = json.load(f)
        
        team_str = str(team_number)
        if team_str in team_colors_data:
            return team_colors_data[team_str]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    
    # Default colors if team not found or file doesn't exist
    return {
        "primary": "#1566ac",
        "secondary": "#c0b8bb"
    }

def load_team_data_optimized(locations_file="2025_geo_teams.json", epa_db=None):
    """Optimized team data loading with caching"""
    def _load_team_data():
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
    
    return load_cached_data("team_data.pkl.gz", _load_team_data)

def load_team_data(locations_file="2025_geo_teams.json", epa_db=None):
    """Backward compatibility wrapper"""
    return load_team_data_optimized(locations_file, epa_db)

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
    """Get GeoJSON data for US states, Canadian provinces, and Israel"""
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

    # Add Israel boundary
    israel_geojson = get_israel_boundary()
    if israel_geojson:
        filtered_features.append(israel_geojson)

    # Create new GeoJSON with only the filtered features
    filtered_geojson = {
        'type': 'FeatureCollection',
        'features': filtered_features
    }
    
    return filtered_geojson

def get_israel_boundary():
    """Get Israel boundary GeoJSON data"""
    # Try to load from cache first
    cache_file = "israel_boundary.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
    
    # If not cached, fetch from Natural Earth Data (countries)
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        
        # Find Israel in the countries data
        for feature in data['features']:
            country_name = feature['properties'].get('name', '').lower()
            if 'israel' in country_name:
                # Modify the feature to match our district format
                feature['properties']['name'] = 'Israel'
                feature['properties']['district'] = 'ISR'
                
                # Cache the Israel boundary
                with open(cache_file, "w") as f:
                    json.dump(feature, f)
                
                return feature
    
    return None

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
    # Load data with caching
    teams_data = load_team_data()
    map_teams = [t for t in teams_data if t.get("lat") and t.get("lng")]
    map_teams = calculate_global_rankings(map_teams)

    # Load week ranges with caching
    def _load_week_ranges():
        with open(os.path.join(os.path.dirname(__file__), '../data/week_ranges.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    week_ranges = load_cached_data("week_ranges.pkl.gz", _load_week_ranges)

    # Load events with caching
    def _load_events():
        with open("2025_geo_events.json", "r", encoding="utf-8") as f:
            return json.load(f)
    events_data = load_cached_data("events_data.pkl.gz", _load_events)
    
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

    # Create map with dark theme
    m = folium.Map(
        location=[39.8283, -98.5795], 
        zoom_start=4, 
        zoom_control=False,
        min_zoom=3,  # Prevent excessive zoom out
        max_zoom=18,  # Maximum zoom level
        tiles=None  # Don't add default tiles
    )
    
    # Add dark tile layer
    folium.TileLayer(
        tiles='CartoDB dark_matter',
        name='Dark Theme',
        min_zoom=3,  # Match map min zoom
        max_zoom=18,  # Match map max zoom
        control=False  # Don't show in layer control since it's the only option
    ).add_to(m)

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

    # --- Teams Layer ---
    teams_layer = folium.FeatureGroup(name="Teams", show=True)
    cluster = MarkerCluster(
        name="Team Clusters",
        options={
            'maxClusterRadius': 80,  # Increased to create larger clusters
            'spiderfyOnMaxZoom': True,
            'showCoverageOnHover': True,
            'zoomToBoundsOnClick': True,
            'disableClusteringAtZoom': 8,  # Stop clustering much earlier (zoom level 8)
            'chunkedLoading': True,
            'minClusterSize': 3,  # Only cluster when 3 or more markers are close
            'spiderfyDistanceMultiplier': 1.5,  # Spread out overlapping markers more
            'spiderfyShapePositions': 'circle'  # Arrange overlapping markers in a circle
        }
    ).add_to(teams_layer)
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

    # Track coordinates to prevent exact overlap
    used_coordinates = {}
    
    for team in map_teams:
        lat, lng = team["lat"], team["lng"]
        
        # Check if this exact coordinate is already used
        coord_key = f"{lat:.6f},{lng:.6f}"
        if coord_key in used_coordinates:
            # Add a larger offset to prevent exact overlap
            offset_count = used_coordinates[coord_key]
            lat_offset = (offset_count * 0.001)  # About 110 meters
            lng_offset = (offset_count * 0.001)
            lat += lat_offset
            lng += lng_offset
            used_coordinates[coord_key] += 1
        else:
            used_coordinates[coord_key] = 1
        
        label = f"{team['team_number']} {team.get('nickname', '')} ({team.get('city', '')}, {team.get('state_prov', '')}, {team.get('country', '')})".strip()

        avatar_path = f"../assets/avatars/{team['team_number']}.png"
        if not os.path.exists(avatar_path):
            avatar_path = "../assets/avatars/stock.png"
        icon = CustomIcon(
            avatar_path,
            icon_size=(40, 40),  # Adjust size as needed
            icon_anchor=(20, 20)
        )
        # Get team colors
        team_colors = get_team_colors(team['team_number'])
        
        popup_html = f"""
<div style="background: linear-gradient(135deg, {team_colors['primary']}, {team_colors['secondary']}); padding: 15px; border-radius: 8px; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.7);">
<b>Team {team['team_number']}:</b> {team.get('nickname', '')}<br>
<b>Location:</b> {team.get('city', '')}, {team.get('state_prov', '')}, {team.get('country', '')}<br>
<b>Global Rank:</b> #{team.get('global_rank', 'N/A')}<br>
<b>ACE:</b> {team.get('epa_display', 'N/A')}<br>
<a href='https://www.peekorobo.com/team/{team['team_number']}' target='_blank' rel='noopener noreferrer' style="color: white; text-decoration: underline;">View Team</a>
</div>
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
    event_cluster = MarkerCluster(
        name="Event Clusters",
        options={
            'maxClusterRadius': 60,  # Increased for larger event clusters
            'spiderfyOnMaxZoom': True,
            'showCoverageOnHover': True,
            'zoomToBoundsOnClick': True,
            'disableClusteringAtZoom': 7,  # Stop clustering even earlier for events (zoom level 7)
            'chunkedLoading': True,
            'minClusterSize': 3,  # Only cluster when 3 or more markers are close
            'spiderfyDistanceMultiplier': 1.5,  # Spread out overlapping markers more
            'spiderfyShapePositions': 'circle'  # Arrange overlapping markers in a circle
        }
    ).add_to(events_layer)
    
    # Track coordinates for events to prevent exact overlap
    used_event_coordinates = {}
    
    for event in map_events:
        lat, lng = event["lat"], event["lng"]
        
        # Check if this exact coordinate is already used
        coord_key = f"{lat:.6f},{lng:.6f}"
        if coord_key in used_event_coordinates:
            # Add a larger offset to prevent exact overlap
            offset_count = used_event_coordinates[coord_key]
            lat_offset = (offset_count * 0.001)  # About 110 meters
            lng_offset = (offset_count * 0.001)
            lat += lat_offset
            lng += lng_offset
            used_event_coordinates[coord_key] += 1
        else:
            used_event_coordinates[coord_key] = 1
            
        etype = event.get("event_type_string", "Unknown")
        color = get_event_marker_color(event)
        
        popup_html = f"""
<div style="background: #2A2A2A; padding: 15px; border-radius: 8px; color: white; border: 1px solid #444;">
<b>{event['name']}</b><br>
{event.get('city', '')}, {event.get('state_prov', '')}, {event.get('country', '')}<br>
<b>Type:</b> {etype}<br>
<b>Dates:</b> {event.get('start_date', '')} - {event.get('end_date', '')}<br>
<b>Week:</b> {event.get('week', 'N/A')}<br>
<a href='https://www.peekorobo.com/event/{event['key']}' target='_blank' style="color: white; text-decoration: underline;">View Event</a>
</div>
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

    # Create custom sidebar with all controls
    sidebar_html = '''
    <div id="sidebar" class="sidebar">
        <div class="sidebar-header">
            <h3>Map Controls</h3>
            <button id="sidebar-toggle" class="sidebar-toggle">×</button>
        </div>
        <div class="sidebar-content">
            <div class="control-section">
                <div id="search-container"></div>
            </div>
            <div class="control-section">
                <div id="layer-control-container"></div>
            </div>
            <div class="control-section">
                <div id="measure-control-container"></div>
            </div>

            <div class="control-section">
                <div id="locate-control-container"></div>
            </div>

        </div>
    </div>
    '''

    # Add sidebar HTML to map
    m.get_root().html.add_child(folium.Element(sidebar_html))

    # Add CSS for sidebar styling
    sidebar_css = '''
    <style>
    /* Prevent white flash during loading */
    html, body {
        background: #1A1A1A !important;
        margin: 0;
        padding: 0;
    }
    
    /* Hide ALL controls initially to prevent flash */
    .leaflet-control-search,
    .leaflet-control-layers,
    .leaflet-control-measure,
    .leaflet-control-locate,
    .leaflet-control-minimap,
    .leaflet-control-mouseposition {
        opacity: 0 !important;
        visibility: hidden !important;
        transition: opacity 0.3s ease, visibility 0.3s ease;
        pointer-events: none !important;
    }
    
    /* Show controls once they're moved to sidebar */
    .sidebar .leaflet-control-search,
    .sidebar .leaflet-control-layers,
    .sidebar .leaflet-control-measure,
    .sidebar .leaflet-control-locate {
        opacity: 1 !important;
        visibility: visible !important;
        pointer-events: auto !important;
    }
    
    /* Keep minimap and mouse position visible on map (not in sidebar) */
    .leaflet-control-minimap,
    .leaflet-control-mouseposition {
        opacity: 1 !important;
        visibility: visible !important;
        pointer-events: auto !important;
    }
    
    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        height: 100vh;
        width: 280px;
        background: #1A1A1A;
        box-shadow: 2px 0 8px rgba(0,0,0,0.3);
        z-index: 1000;
        transform: translateX(-100%);
        transition: transform 0.3s ease;
        overflow-y: auto;
        border-right: 1px solid #333;
    }
    
    .sidebar.open {
        transform: translateX(0);
    }
    
    /* Hide sidebar content when closed to prevent layout issues */
    .sidebar:not(.open) .sidebar-content {
        opacity: 0;
        pointer-events: none;
    }
    
    .sidebar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 15px;
        border-bottom: 1px solid #333;
        background: #2A2A2A;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    .sidebar-header h3 {
        margin: 0;
        font-size: 16px;
        color: #fff;
        font-weight: 600;
    }
    
    .sidebar-toggle {
        background: #FFDD00;
        border: none;
        font-size: 18px;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background-color 0.2s;
        color: #000;
        font-weight: bold;
    }
    
    .sidebar-toggle:hover {
        background-color: #E6C700;
        color: #000;
    }
    
    .sidebar-content {
        padding: 20px;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    .control-section {
        margin-bottom: 50px;
        position: relative;
        width: 100% !important;
        display: block !important;
        clear: both !important;
    }
    
    .control-section:last-child {
        margin-bottom: 0;
    }
    
    /* Add extra spacing between layers and measure control */
    #layer-control-container {
        margin-bottom: 20px;
    }
    
    .control-section h4 {
        margin: 20px 0 15px 0;
        font-size: 12px;
        color: #ccc;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #444;
        padding-bottom: 8px;
        width: 100% !important;
        display: block !important;
        clear: both !important;
    }
    
    /* Remove top margin from first section header */
    .control-section:first-child h4 {
        margin-top: 0;
    }
    
    /* Style the search control */
    #search-container .leaflet-control-search {
        box-shadow: none !important;
        border: none !important;
        border-radius: 0 !important;
        background: transparent !important;
        width: 100% !important;
        position: relative !important;
    }
    
    #search-container .leaflet-control-search input {
        width: 100% !important;
        font-size: 13px;
        padding: 10px 12px;
        border: 1px solid #444;
        border-radius: 6px;
        background: #2A2A2A;
        color: #fff;
        box-sizing: border-box;
        margin-right: 0 !important;
    }
    
    #search-container .leaflet-control-search input:focus {
        background: #333;
        outline: none;
        border-color: #007bff;
        box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
    }
    
    #search-container .leaflet-control-search input::placeholder {
        color: #999;
    }
    
    /* Hide ALL search icons and buttons */
    #search-container .leaflet-control-search .search-icon,
    #search-container .leaflet-control-search .search-button,
    #search-container .leaflet-control-search .search-cancel,
    #search-container .leaflet-control-search a,
    #search-container .leaflet-control-search img,
    #search-container .leaflet-control-search svg,
    #search-container .leaflet-control-search button {
        display: none !important;
    }
    
    /* Ensure search results appear above everything */
    #search-container .leaflet-control-search .search-tooltip,
    #search-container .leaflet-control-search .search-tip,
    #search-container .leaflet-control-search .search-list,
    #search-container .leaflet-control-search .search-result {
        z-index: 9999 !important;
        position: relative !important;
        background: #2A2A2A !important;
        border: 1px solid #444 !important;
        color: #fff !important;
        max-height: 200px !important;
        overflow-y: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        left: 0 !important;
        right: 0 !important;
        box-sizing: border-box !important;
    }
    
    /* Style search result items */
    #search-container .leaflet-control-search .search-result-item {
        background: #333 !important;
        border-bottom: 1px solid #444 !important;
        color: #fff !important;
        padding: 8px 12px !important;
        cursor: pointer !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    /* Make search result tooltips wider to match map click tooltips */
    .leaflet-popup-content-wrapper {
        min-width: 280px !important;
        max-width: 320px !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    .leaflet-popup-content {
        min-width: 280px !important;
        max-width: 320px !important;
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
    }
    
    /* Ensure search result popups have the same width as map click popups */
    .leaflet-popup {
        min-width: 280px !important;
    }
    
    /* Remove default popup styling to show custom gradients */
    .leaflet-popup-tip {
        background: transparent !important;
    }
    
    /* Ensure map background stays dark during tile loading */
    .leaflet-container {
        background: #1a1a1a !important;
    }
    
    .leaflet-tile-pane {
        background: #1a1a1a !important;
    }
    
    /* Dark background for loading tiles */
    .leaflet-tile {
        background: #1a1a1a !important;
    }
    
    /* Ensure map container background is dark */
    .leaflet-map-pane {
        background: #1a1a1a !important;
    }
    
    #search-container .leaflet-control-search .search-result-item:hover {
        background: #444 !important;
    }
    
    #search-container .leaflet-control-search .search-result-item.selected {
        background: #007bff !important;
        color: #fff !important;
    }
    
    /* Style the layer control */
    #layer-control-container .leaflet-control-layers {
        box-shadow: none !important;
        border: 1px solid #444;
        border-radius: 6px;
        background: #2A2A2A;
        padding: 12px;
        margin: 0;
        width: 100% !important;
        display: block !important;
    }
    
    #layer-control-container .leaflet-control-layers-toggle {
        width: 100%;
        height: 32px;
        background: #333;
        border: 1px solid #444;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 12px;
        color: #ccc;
    }
    
    #layer-control-container .leaflet-control-layers-toggle:hover {
        background: #444;
    }
    
    /* Style layer checkboxes and radio buttons */
    #layer-control-container .leaflet-control-layers label {
        font-size: 12px;
        margin: 6px 0;
        color: #fff;
        display: flex;
        align-items: center;
        cursor: pointer;
    }
    
    #layer-control-container .leaflet-control-layers input[type="checkbox"],
    #layer-control-container .leaflet-control-layers input[type="radio"] {
        margin-right: 8px;
        margin-left: 0;
    }
    
    /* Ensure proper spacing between sections */
    #layer-control-container .leaflet-control-layers > div {
        margin-bottom: 8px;
    }
    
    #layer-control-container .leaflet-control-layers > div:last-child {
        margin-bottom: 0;
    }
    
    /* Style the measure control */
    #measure-control-container .leaflet-control-measure {
        box-shadow: none !important;
        border: 1px solid #444 !important;
        border-radius: 6px !important;
        background: #2A2A2A !important;
        width: 100% !important;
        padding: 12px !important;
    }
    
    #measure-control-container .leaflet-control-measure a {
        background: #333 !important;
        border: 1px solid #444 !important;
        border-radius: 4px !important;
        color: #fff !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        margin: 2px 0 !important;
        text-align: center !important;
        display: block !important;
        text-decoration: none !important;
        box-sizing: border-box !important;
    }
    
    #measure-control-container .leaflet-control-measure a:hover {
        background: #444 !important;
        color: #fff !important;
        text-decoration: none !important;
    }
    
    /* Style measure control labels and text */
    #measure-control-container .leaflet-control-measure .measure-label,
    #measure-control-container .leaflet-control-measure .measure-text,
    #measure-control-container .leaflet-control-measure span,
    #measure-control-container .leaflet-control-measure div {
        color: #fff !important;
    }
    
    /* Force measure control to always be expanded */
    #measure-control-container .leaflet-control-measure .leaflet-control-measure-toggle {
        display: none !important;
    }
    
    #measure-control-container .leaflet-control-measure .leaflet-control-measure-interaction {
        display: block !important;
    }
    

    

    
    /* Style the locate control */
    #locate-control-container .leaflet-control-locate {
        box-shadow: none !important;
        border: 1px solid #444 !important;
        border-radius: 6px !important;
        background: #2A2A2A !important;
        width: 100% !important;
        padding: 12px !important;
    }
    
    #locate-control-container .leaflet-control-locate a {
        background: #333 !important;
        border: 1px solid #444 !important;
        border-radius: 4px !important;
        color: #fff !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        margin: 2px 0 !important;
        text-align: center !important;
        display: block !important;
        text-decoration: none !important;
        box-sizing: border-box !important;
    }
    
    #locate-control-container .leaflet-control-locate a:hover {
        background: #444 !important;
        color: #fff !important;
        text-decoration: none !important;
    }
    

    
    /* Floating toggle button when sidebar is closed */
    .sidebar-toggle-float {
        position: fixed;
        top: 20px;
        left: 20px;
        z-index: 999;
        background: #FFDD00;
        border: 1px solid #E6C700;
        border-radius: 6px;
        padding: 8px 12px;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        font-size: 16px;
        display: block;
        color: #000;
        font-weight: bold;
        transition: all 0.2s ease;
    }
    
    .sidebar-toggle-float:hover {
        background: #E6C700;
        color: #000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    
    .sidebar-toggle-float.hide {
        display: none;
    }
    
    /* Adjust map container to account for sidebar */
    .leaflet-container {
        transition: margin-left 0.3s ease;
    }
    
    .sidebar.open + .leaflet-container {
        margin-left: 280px;
    }
    
    /* Ensure map controls don't interfere with sidebar */
    .leaflet-control-zoom {
        top: 20px !important;
        left: 20px !important;
    }
    
    .sidebar.open ~ .leaflet-control-zoom {
        left: 300px !important;
    }
    
    /* Style minimap */
    .leaflet-control-minimap {
        border: 2px solid #444 !important;
        border-radius: 6px !important;
        background: #2A2A2A !important;
    }
    
    .leaflet-control-minimap .leaflet-control-minimap-toggle-display {
        background: #333 !important;
        border: 1px solid #444 !important;
        color: #fff !important;
    }
    
    .leaflet-control-minimap .leaflet-control-minimap-toggle-display:hover {
        background: #444 !important;
    }
    
    /* Change minimap viewport box color to yellow */
    .leaflet-control-minimap .leaflet-control-minimap-viewport {
        border: 2px solid #FFDD00 !important;
        background: rgba(255, 221, 0, 0.1) !important;
    }
    
    /* Style mouse position control */
    .leaflet-control-mouseposition {
        background: rgba(42, 42, 42, 0.9) !important;
        border: 1px solid #444 !important;
        border-radius: 4px !important;
        color: #fff !important;
        font-size: 11px !important;
        padding: 4px 8px !important;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .sidebar {
            width: 260px;
        }
        .sidebar.open + .leaflet-container {
            margin-left: 260px;
        }
        .sidebar.open ~ .leaflet-control-zoom {
            left: 280px !important;
        }
    }
    </style>
    '''
    
    m.get_root().html.add_child(folium.Element(sidebar_css))

    # Add JavaScript for sidebar functionality
    sidebar_js = '''
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const sidebar = document.getElementById('sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const mapContainer = document.querySelector('.leaflet-container');
        
        // Create floating toggle button
        const floatingToggle = document.createElement('button');
        floatingToggle.className = 'sidebar-toggle-float';
        floatingToggle.innerHTML = '☰';
        floatingToggle.title = 'Open Map Controls';
        document.body.appendChild(floatingToggle);
        
        // Toggle sidebar function
        function toggleSidebar() {
            sidebar.classList.toggle('open');
            floatingToggle.classList.toggle('hide');
            
            // Trigger map resize to ensure proper rendering
            if (window.map) {
                setTimeout(() => {
                    window.map.invalidateSize();
                }, 300);
            }
        }
        
        // Event listeners
        sidebarToggle.addEventListener('click', toggleSidebar);
        floatingToggle.addEventListener('click', toggleSidebar);
        
        // Close sidebar when clicking outside (on mobile)
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                if (!sidebar.contains(e.target) && !floatingToggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                    floatingToggle.classList.remove('hide');
                }
            }
        });
        
        // Move controls to sidebar with better timing
        function moveControlsToSidebar() {
            // Move search control
            const searchControl = document.querySelector('.leaflet-control-search');
            if (searchControl && !document.getElementById('search-container').contains(searchControl)) {
                document.getElementById('search-container').appendChild(searchControl);
                // Force search input to be single line
                const searchInput = searchControl.querySelector('input');
                if (searchInput) {
                    searchInput.style.width = '100%';
                    searchInput.style.marginRight = '0';
                }
                // Show the control smoothly
                setTimeout(() => {
                    searchControl.style.opacity = '1';
                    searchControl.style.visibility = 'visible';
                    searchControl.style.pointerEvents = 'auto';
                }, 50);
            }
            

            
            // Move layer control
            const layerControl = document.querySelector('.leaflet-control-layers');
            if (layerControl && !document.getElementById('layer-control-container').contains(layerControl)) {
                document.getElementById('layer-control-container').appendChild(layerControl);
                // Force layer control to be full width
                layerControl.style.width = '100%';
                layerControl.style.display = 'block';
                // Show the control smoothly
                setTimeout(() => {
                    layerControl.style.opacity = '1';
                    layerControl.style.visibility = 'visible';
                    layerControl.style.pointerEvents = 'auto';
                }, 100);
            }
            
            // Move measure control
            const measureControl = document.querySelector('.leaflet-control-measure');
            if (measureControl && !document.getElementById('measure-control-container').contains(measureControl)) {
                document.getElementById('measure-control-container').appendChild(measureControl);
                // Show the control smoothly
                setTimeout(() => {
                    measureControl.style.opacity = '1';
                    measureControl.style.visibility = 'visible';
                    measureControl.style.pointerEvents = 'auto';
                }, 125);
            }
            

            
            // Move locate control
            const locateControl = document.querySelector('.leaflet-control-locate');
            if (locateControl && !document.getElementById('locate-control-container').contains(locateControl)) {
                document.getElementById('locate-control-container').appendChild(locateControl);
                // Show the control smoothly
                setTimeout(() => {
                    locateControl.style.opacity = '1';
                    locateControl.style.visibility = 'visible';
                    locateControl.style.pointerEvents = 'auto';
                }, 175);
            }
            

            
            // Hide any remaining controls that should be in sidebar
            const allControls = document.querySelectorAll('.leaflet-control-search, .leaflet-control-layers, .leaflet-control-measure, .leaflet-control-locate');
            allControls.forEach(control => {
                if (!control.closest('.sidebar')) {
                    control.style.opacity = '0';
                    control.style.visibility = 'hidden';
                    control.style.pointerEvents = 'none';
                }
            });
        }
        
        // Try to move controls multiple times to ensure they're moved
        setTimeout(moveControlsToSidebar, 100);
        setTimeout(moveControlsToSidebar, 500);
        setTimeout(moveControlsToSidebar, 1000);
        setTimeout(moveControlsToSidebar, 2000);
        setTimeout(moveControlsToSidebar, 3000);
        
        // Ensure zoom controls are properly positioned initially
        setTimeout(() => {
            const zoomControls = document.querySelector('.leaflet-control-zoom');
            if (zoomControls) {
                zoomControls.style.top = '20px';
                zoomControls.style.left = '20px';
            }
        }, 100);
        
        // Handle overlapping markers by adding click handlers
        function handleOverlappingMarkers() {
            // Find all marker icons
            const markers = document.querySelectorAll('.leaflet-marker-icon');
            
            markers.forEach((marker, index) => {
                // Add a small random offset to prevent exact overlap
                const randomOffset = (index % 4) * 2; // 0, 2, 4, 6 pixels
                if (randomOffset > 0) {
                    marker.style.transform += ` translate(${randomOffset}px, ${randomOffset}px)`;
                }
                
                // Add click handler to bring marker to front
                marker.addEventListener('click', function(e) {
                    // Bring this marker to the front
                    this.style.zIndex = '1000';
                    
                    // Reset other markers z-index after a short delay
                    setTimeout(() => {
                        markers.forEach(m => {
                            if (m !== this) {
                                m.style.zIndex = '';
                            }
                        });
                    }, 1000);
                });
            });
        }
        
        // Run overlapping marker handler after map loads
        setTimeout(handleOverlappingMarkers, 2000);
        setTimeout(handleOverlappingMarkers, 5000);
    });
    </script>
    '''
    
    m.get_root().html.add_child(folium.Element(sidebar_js))

    # Add the controls to the map (they will be moved to sidebar by JavaScript)
    Search(
        layer=search_layer,
        search_label="name",
        placeholder="Search teams & events",
        collapsed=False
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    MeasureControl(primary_length_unit='kilometers').add_to(m)
    
    # Add comprehensive Folium tools and plugins
    # MiniMap for overview navigation
    MiniMap(
        tile_layer="CartoDB dark_matter",
        position="bottomright",
        width=150,
        height=150,
        collapsed_width=25,
        collapsed_height=25,
        zoom_level_offset=-5,
        toggle_display=True
    ).add_to(m)
    
    # Mouse position coordinates display
    MousePosition(
        position="bottomleft",
        separator=" | ",
        prefix="Coordinates:",
        lat_formatter="function(num) {return L.Util.formatNum(num, 4) + '°';}",
        lng_formatter="function(num) {return L.Util.formatNum(num, 4) + '°';}"
    ).add_to(m)
    
    # Locate user position
    LocateControl(
        position="topleft",
        strings={"title": "Show my location"},
        flyTo=True,
        keepCurrentZoomLevel=True
    ).add_to(m)
    

    

    


    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Optimize the HTML output
    html_content = m.get_root().render()
    
    # Add dark background to prevent white flash
    html_content = html_content.replace(
        '<head>',
        '<head>\n<style>html, body { background: #1A1A1A !important; margin: 0; padding: 0; }</style>'
    )
    
    # Compress the HTML content
    compressed_html = gzip.compress(html_content.encode('utf-8'))
    
    # Save both compressed and uncompressed versions
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    compressed_file = output_file.replace('.html', '_compressed.html.gz')
    with open(compressed_file, 'wb') as f:
        f.write(compressed_html)
    
    # Calculate file sizes
    original_size = len(html_content.encode('utf-8'))
    compressed_size = len(compressed_html)
    compression_ratio = (1 - compressed_size / original_size) * 100
    
    print(f"✅ Map saved with optimizations:")
    print(f"   📁 Original: {original_size:,} bytes")
    print(f"   📦 Compressed: {compressed_size:,} bytes")
    print(f"   📊 Compression: {compression_ratio:.1f}% smaller")
    print(f"   🗂️ Files: {output_file}, {compressed_file}")
    
    # Performance tips
    print(f"💡 Performance tips:")
    print(f"   • Use the compressed file for faster loading")
    print(f"   • Cache is stored in {CACHE_DIR}")
    print(f"   • Data is cached for 24 hours")
    print(f"   • New features added:")
    print(f"     🗺️ MiniMap for navigation overview")
    print(f"     📍 Mouse position coordinates")
    print(f"     🔍 Geocoder for address search")
    print(f"     ✏️ Drawing tools for annotations")
    print(f"     📏 Enhanced measurement tools")
    print(f"     🎮 Fullscreen and scroll zoom controls")
    print(f"     📍 Location finder")

if __name__ == "__main__":
    generate_team_event_map()