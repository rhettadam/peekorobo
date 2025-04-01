import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go

import folium
from folium.plugins import MarkerCluster

import requests
import urllib.parse 
import os
from dotenv import load_dotenv
import json
import numpy as np
import datetime

from frcgames import frc_games
from locations import COUNTRIES, STATES

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

app = dash.Dash(
    __name__,
    meta_tags=[
        {'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'},
        {'name': 'description', 'content': 'A scouting and statistics platform for FRC teams that provides detailed insights and resources'},
        {'name': 'keywords', 'content': 'FRC, Robotics, Scouting, FIRST, FIRST Robotics Competition, Statbotics, TBA, The Blue Alliance, Competition, Statistics'},
    ],
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Peekorobo",
)

server = app.server

# -------------- LAYOUTS --------------
topbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                [
                    # LOGO on the left
                    dbc.Col(
                        dbc.NavbarBrand(
                            html.Img(
                                src="/assets/logo.png",
                                style={"height": "40px","width": "auto","marginRight": "10px"},
                            ),
                            href="/",
                            className="navbar-brand-custom",
                        ),
                        width="auto",
                        align="center",
                    ),

                    # MOBILE SEARCH in the middle (only visible on sm)
                    dbc.Col(
                        [
                            dbc.InputGroup(
                                [
                                    dbc.Input(
                                        id="mobile-search-input",
                                        placeholder="Search",
                                        type="text",
                                    ),
                                    dbc.Button(
                                        "🔎",
                                        id="mobile-search-button",
                                        color="primary",
                                        style={
                                            "backgroundColor": "#FFDD00",
                                            "border": "none",
                                            "color": "black",
                                        },
                                    ),
                                ],
                                style={"width": "180px"},  # or any desired width
                            ),
                            html.Div(
                                id="mobile-search-preview",
                                style={
                                    "backgroundColor": "white",
                                    "border": "1px solid #ddd",
                                    "borderRadius": "8px",
                                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                    "marginTop": "5px",
                                    "padding": "5px",
                                    "maxHeight": "200px",
                                    "overflowY": "auto",
                                    "overflowX": "hidden",
                                    "width": "180px",
                                    "zIndex": "9999",
                                    "position": "absolute",
                                    "left": "0",
                                    "top": "100%",
                                    "display": "none",
                                },
                            ),
                        ],
                        width="auto",
                        align="center",
                        className="d-md-none",  # hide on md+
                        style={"position": "relative","textAlign": "center"},
                    ),

                    # NAV TOGGLER on the right
                    dbc.Col(
                        dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                        width="auto",
                        align="center",
                        className="d-md-none",  # toggler on mobile only
                    ),
                ],
                className="g-2",  # small horizontal gutter
                align="center",
                justify="between",  # pushes left col to start, right col to end
            ),

            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("Teams", href="/teams", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Map", href="/map", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Insights", href="/insights", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Challenges", href="/challenges", className="custom-navlink")),
                        # Example dropdown
                        dbc.DropdownMenu(
                            label="Resources",
                            nav=True,
                            in_navbar=True,
                            children=[
                                dbc.DropdownMenuItem("Communication", header=True),
                                # ...
                            ],
                        ),
                    ],
                    navbar=True,
                ),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),

            # Desktop Search
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.InputGroup(
                                [
                                    dbc.Input(
                                        id="desktop-search-input",
                                        placeholder="Search Teams or Events",
                                        type="text",
                                    ),
                                    dbc.Button(
                                        "🔎",
                                        id="desktop-search-button",
                                        color="primary",
                                        style={
                                            "backgroundColor": "#FFDD00",
                                            "border": "none",
                                            "color": "black",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                id="desktop-search-preview",
                                style={
                                    "backgroundColor": "white",
                                    "border": "1px solid #ddd",
                                    "borderRadius": "8px",
                                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                    "marginTop": "5px",
                                    "padding": "5px",
                                    "maxHeight": "200px",
                                    "overflowY": "auto",
                                    "overflowX": "hidden",
                                    "width": "100%",
                                    "zIndex": "9999",
                                    "position": "absolute",
                                    "left": "0",
                                    "top": "100%",
                                    "display": "none",
                                },
                            )
                        ],
                        width="auto",
                        className="desktop-search d-none d-md-block",
                        style={"position": "relative"},
                    ),
                ],
                align="center",
            ),
        ],
        fluid=True,
    ),
    color="#353535",
    dark=True,
    className="mb-4",
    style={
        "padding": "5px 0px",
        "position": "sticky",
        "top": "0",
        "zIndex": "1020",
        "boxShadow": "0px 2px 2px rgba(0,0,0,0.1)",
    },
)

app.layout = html.Div([topbar])

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

def flatten_events(data):
    flat = []
    if isinstance(data, dict):
        if "event_code" in data:
            flat.append(data)
        else:
            for value in data.values():
                flat.extend(flatten_events(value))
    elif isinstance(data, list):
        for item in data:
            flat.extend(flatten_events(item))
    return flat

# ----- MASTER CALLBACK: 2 inputs -> 4 outputs -----
@app.callback(
    [Output("desktop-search-preview", "children"), Output("desktop-search-preview", "style"),
     Output("mobile-search-preview", "children"),  Output("mobile-search-preview", "style")],
    [Input("desktop-search-input", "value"), Input("mobile-search-input", "value")],
)
def update_search_preview(desktop_value, mobile_value):
    desktop_value = (desktop_value or "").strip().lower()
    mobile_value  = (mobile_value  or "").strip().lower()

    # Load your data
    folder_path = "team_data"
    teams_file = os.path.join(folder_path, "teams_2025.json")
    events_file = os.path.join(folder_path, "events.json")

    if os.path.exists(teams_file):
        with open(teams_file, "r") as f:
            teams_data = json.load(f)
    else:
        teams_data = []

    if os.path.exists(events_file):
        with open(events_file, "r") as f:
            raw_events_data = json.load(f)
        if isinstance(raw_events_data, dict) and "events" in raw_events_data:
            raw_events_data = raw_events_data["events"]
        events_data = flatten_events(raw_events_data)
    else:
        events_data = []

    def get_children_and_style(val):
        if not val:
            return [], {"display": "none"}

        # --- Filter Teams ---
        filtered_teams = [
            t for t in teams_data
            if val in str(t.get("team_number", "")).lower()
               or val in (t.get("nickname", "")).lower()
        ][:20]

        # Determine closest team number or nickname
        closest_team_number = None
        closest_team_nickname = None
        if val.isdigit() and filtered_teams:
            input_number = int(val)
            closest_team_number = min(
                filtered_teams,
                key=lambda t: abs(input_number - int(t["team_number"])),
                default=None,
            )
        elif filtered_teams:
            closest_team_nickname = min(
                filtered_teams,
                key=lambda t: len(set(val) & set(t["nickname"].lower())),
                default=None,
            )

        # --- Filter Events ---
        filtered_events = []
        for e in events_data:
            event_code = (e.get("event_code") or "").lower()
            event_name = (e.get("name") or "").lower()
            start_date = e.get("start_date", "")
            event_year = start_date[:4] if len(start_date) >= 4 else ""
            year_name_combo = f"{event_year} {event_name}".lower()

            if (val in event_code) or (val in event_name) or (val in year_name_combo):
                filtered_events.append(e)
        filtered_events = filtered_events[:20]

        # Determine closest event
        closest_event = None
        if filtered_events:
            closest_event = max(
                filtered_events,
                key=lambda e: (
                    len(set(val) & set((e.get("event_code") or "").lower()))
                    + len(set(val) & set((e.get("name") or "").lower()))
                )
            )

        children = []

        # Teams section
        if filtered_teams:
            children.append(
                dbc.Row(
                    dbc.Col(
                        html.Div("Teams", style={"fontWeight": "bold", "padding": "5px"}),
                    ),
                    style={"backgroundColor": "#f1f1f1"}
                )
            )
            for team in filtered_teams:
                tn = team.get("team_number", "???")
                nm = team.get("nickname", "")
                background_color = "white"

                # highlight if it's the closest match
                if (closest_team_number and tn == closest_team_number["team_number"]) or \
                   (closest_team_nickname and nm == closest_team_nickname["nickname"]):
                    background_color = "#FFDD00"

                row_el = dbc.Row(
                    dbc.Col(
                        html.A(
                            f"{tn} | {nm}",
                            href=f"/team/{tn}",
                            style={"lineHeight": "20px", "textDecoration": "none", "color": "black"},
                        ),
                        width=True,
                    ),
                    style={"padding": "5px", "backgroundColor": background_color},
                )
                children.append(row_el)

        # Events section
        if filtered_events:
            children.append(
                dbc.Row(
                    dbc.Col(
                        html.Div("Events", style={"fontWeight": "bold", "padding": "5px"}),
                    ),
                    style={"backgroundColor": "#f1f1f1","marginTop": "5px"}
                )
            )
            for evt in filtered_events:
                e_code = evt.get("event_code", "???")
                e_name = evt.get("name", "")
                start_date = evt.get("start_date", "")
                e_year = start_date[:4] if len(start_date) >= 4 else ""
                background_color = "white"

                if closest_event and (
                    e_code.lower() == (closest_event.get("event_code") or "").lower()
                    and e_name == closest_event.get("name")
                ):
                    background_color = "#FFDD00"

                display_text = f"{e_code} | {e_year} {e_name}"
                row_el = dbc.Row(
                    dbc.Col(
                        html.A(
                            display_text,
                            href=f"/event/{e_year}{e_code}",
                            style={"lineHeight": "20px", "textDecoration": "none", "color": "black"},
                        ),
                        width=True,
                    ),
                    style={"padding": "5px", "backgroundColor": background_color},
                )
                children.append(row_el)

        if not filtered_teams and not filtered_events:
            children.append(html.Div("No results found.", style={"padding": "5px","color": "#555"}))

        style_dict = {
            "display": "block",
            "backgroundColor": "white",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
            "marginTop": "5px",
            "padding": "5px",
            "maxHeight": "200px",
            "overflowY": "auto",
            "overflowX": "hidden",
            "width": "100%",
            "zIndex": "9999",
            "position": "absolute",
            "left": "0",
            "top": "100%",
        }
        return children, style_dict

    # Build the preview for each input
    desktop_children, desktop_style = get_children_and_style(desktop_value)
    mobile_children, mobile_style   = get_children_and_style(mobile_value)

    return (desktop_children, desktop_style,
            mobile_children, mobile_style)

footer = dbc.Container(
    dbc.Row([
        dbc.Col([
            html.P(
                [
                    "Built With:  ",
                    html.A("The Blue Alliance ", href="https://www.thebluealliance.com/", target="_blank", style={"color": "#3366CC", "textDecoration": "line"}),
                    " | ",
                    html.A(" GitHub", href="https://github.com/rhettadam/peekorobo", target="_blank", style={"color": "#3366CC", "textDecoration": "line"})
                ],
                style={
                    "textAlign": "center",
                    "color": "#353535",
                    "fontSize": "12px",
                    "margin": "0",  # Minimized margin
                    "padding": "0",  # Minimized padding
                }
            ),
        ], style={"padding": "0"})  # Ensure no padding in columns
    ], style={"margin": "0"}),  # Ensure no margin in rows
    fluid=True,
    style={
        "backgroundColor": "white",
        "padding": "10px 0px",
        "boxShadow": "0px -1px 2px rgba(0, 0, 0, 0.1)",
        "margin": "0",  # Eliminate default container margin
    }
)

home_layout = html.Div([
    topbar,
    dbc.Container(fluid=True, children=[
        dbc.Row(
            [
                # Left Section: Logo, Text, Search
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Img(
                                    src="/assets/logo.png",
                                    className='homelogo',
                                    style={
                                        "width": "400px",
                                        "marginBottom": "15px",
                                    },
                                ),
                                html.P(
                                    "Search for any FRC Team",
                                    style={
                                        "fontSize": "1.5rem",
                                        "color": "#555",
                                        "textAlign": "center",
                                        "marginBottom": "20px"
                                    },
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Input(
                                                id="input-team-home",
                                                type="text",
                                                placeholder="Team name or # (e.g., 1912)",
                                                className="custom-input-box",
                                                style={"width": "100%", "marginBottom": ".4rem"}
                                            ),
                                            width=12
                                        ),
                                        dbc.Col(
                                            dbc.Input(
                                                id="input-year-home",
                                                type="text",
                                                placeholder="Year (e.g., 2025) optional",
                                                className="custom-input-box",
                                                style={"width": "100%"}
                                            ),
                                            width=12
                                        ),
                                    ],
                                    justify="center",
                                    style={"marginBottom": "1rem"}
                                ),
                                dbc.Button(
                                    "Search",
                                    id="btn-search-home",
                                    color="primary",
                                    size="lg",
                                    style={
                                        "backgroundColor": "#ffdd00ff",
                                        "border": "2px solid #555",
                                        "color": "black",
                                        "marginTop": "10px",
                                        "width": "50%",
                                    },
                                ),
                            ],
                            className="logo-search-container",
                            style={
                                "textAlign": "center",
                                "display": "flex",
                                "flexDirection": "column",
                                "alignItems": "center"
                            }
                        )
                    ],
                    width=6,
                    className="desktop-left-section"
                ),
                # Right Section: Bulldozer GIF
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.A(
                                    html.Img(
                                        src="/assets/dozer.gif",
                                        style={
                                            "width": "100%",  
                                            "maxWidth": "600px",
                                            "display": "block",
                                            "margin": "auto"
                                        },
                                        className="dozer-image"
                                    ),
                                    href="https://github.com/rhettadam/peekorobo",
                                    target="_blank",
                                ),
                            ],
                            style={"textAlign": "center"}
                        )
                    ],
                    width=6,
                    className="desktop-right-section"
                )
            ],
            justify="center",
            align="center",
            style={"height": "78vh"}
        ),
    ], class_name="py-5", style={"backgroundColor": "white"}),

    dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
    dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
    
    footer
])

def calculate_ranks(team_data, selected_team):
    global_rank = 1
    country_rank = 1
    state_rank = 1

    # Extract selected team's information
    selected_epa = selected_team.get("epa", 0) or 0  # Ensure selected_epa is a number
    selected_country = (selected_team.get("country") or "").lower()
    selected_state = (selected_team.get("state_prov") or "").lower()

    for team in team_data:
        if team.get("team_number") == selected_team.get("team_number"):
            continue

        team_epa = team.get("epa", 0) or 0  # Default to 0 if EPA is None
        team_country = (team.get("country") or "").lower()
        team_state = (team.get("state_prov") or "").lower()

        # Global Rank
        if team_epa > selected_epa:
            global_rank += 1

        # Country Rank
        if team_country == selected_country and team_epa > selected_epa:
            country_rank += 1

        # State Rank
        if team_state == selected_state and team_epa > selected_epa:
            state_rank += 1

    return global_rank, country_rank, state_rank

def team_layout(team_number, year):
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_key = f"frc{team_number}"
    folder_path = "team_data"  # Replace with the correct folder path
    file_path = os.path.join(folder_path, f"teams_{year or 2025}.json")
    if not os.path.exists(file_path):
        return dbc.Alert(f"Data for year {year or 2025} not found.", color="danger")

    with open(file_path, "r") as f:
        team_data = json.load(f)

    # Find the selected team
    selected_team = next((team for team in team_data if team["team_number"] == int(team_number)), None)
    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data.", color="danger")

    # Calculate Rankings using your existing function
    global_rank, country_rank, state_rank = calculate_ranks(team_data, selected_team)

    # Overall EPA from stored team data (retained from your original layout)
    epa_value = selected_team.get("epa", None)
    epa_display = f"{epa_value:.2f}" if epa_value is not None else "N/A"

    # Get additional EPA components
    auto_epa = selected_team.get("auto_epa", None)
    teleop_epa = selected_team.get("teleop_epa", None)
    endgame_epa = selected_team.get("endgame_epa", None)
    auto_epa_display = f"{auto_epa:.2f}" if auto_epa is not None else "N/A"
    teleop_epa_display = f"{teleop_epa:.2f}" if teleop_epa is not None else "N/A"
    endgame_epa_display = f"{endgame_epa:.2f}" if endgame_epa is not None else "N/A"

    nickname = selected_team.get("nickname", "Unknown")
    city = selected_team.get("city", "")
    state = selected_team.get("state_prov", "")
    country = selected_team.get("country", "")
    website = selected_team.get("website", "N/A")
    if website and website.startswith("http://"):
        website = "https://" + website[len("http://"):]
    
    avatar_data = tba_get(f"team/{team_key}/media/2025")
    avatar_url = None
    if avatar_data:
        for media in avatar_data:
            if media.get("type") == "avatar" and media.get("details", {}).get("base64Image"):
                avatar_url = f"data:image/png;base64,{media['details']['base64Image']}"
                break
            elif media.get("preferred") and media.get("direct_url"):
                avatar_url = media["direct_url"]
                break
    
    years_participated = tba_get(f"team/{team_key}/years_participated")
    years_links = [
        html.A(
            str(yr),
            href=f"/team/{team_number}/{yr}",
            style={
                "marginRight": "0px",
                "color": "#007BFF",
                "textDecoration": "none",
            },
        )
        for yr in years_participated
    ] if years_participated else ["N/A"]

    # Add "ALL" button linking to team profile without year
    years_links.append(
        html.A(
            "History",
            href=f"/team/{team_number}",  # No year specified
            style={
                "marginLeft": "0px",
                "color": "#007BFF",
                "fontWeight": "bold",
                "textDecoration": "none",
            },
        )
    )

    rookie_year = years_participated[0] if years_participated else year or 2025

    hof = [2486, 321, 1629, 503, 4613, 1816, 1902, 1311, 2834, 2614, 3132, 987, 597, 27, 1538, 1114, 359, 341, 236, 842, 365, 111, 67, 254, 103, 175, 22, 16, 120, 23, 47, 51, 144, 151, 191, 7]
    wcp = [126,148,144,100,73,71,45,1,48,176,25,232,255,125,279,294,365,66,173,65,111,469,435,494,67,330,503,217,296,522,190,987,177,1114,971,254,973,180,16,1241,1477,610,2848,74,118,1678,1671,5012,2481,120,1086,2767,862,1676,1011,2928,5499,27,2708,4027,2976,3075,3707,4481,1218,1323,5026,4201,1619,3175,6672,4414,4096,609,1690,4522,9432,321]

    is_hof_team = int(team_number) in hof
    is_wcp_team = int(team_number) in wcp
    
    hof_badge = (
        html.Div(
            [
                html.Span("🏆", style={"fontSize": "1.5rem"}),
                html.Span(" Hall of Fame", style={"color": "gold", "fontSize": "1.2rem", "fontWeight": "bold", "marginLeft": "5px"})
            ],
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}
        )
        if is_hof_team else None
    )
    wcp_badge = (
        html.Div(
            [
                html.Span("🌎", style={"fontSize": "1.5rem"}),
                html.Span(" World Champions", style={"color": "blue", "fontSize": "1.2rem", "fontWeight": "bold", "marginLeft": "5px"})
            ],
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}
        )
        if is_wcp_team else None
    )
    
    # Team Info Card
    team_card = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H2(f"Team {team_number}: {nickname}", style={"color": "#333", "fontWeight": "bold"}),
                                hof_badge if is_hof_team else None,
                                wcp_badge if is_wcp_team else None,
                                html.P([html.I(className="bi bi-geo-alt-fill"), f"📍 {city}, {state}, {country}"]),
                                html.P([html.I(className="bi bi-link-45deg"), "Website: ", 
                                        html.A(website, href=website, target="_blank", style={"color": "#007BFF", "textDecoration": "none"})]),
                                html.P([html.I(className="bi bi-award"), f" Rookie Year: {rookie_year}"]),
                                html.Div(
                                    [
                                        html.I(className="bi bi-calendar"),
                                        " Years Participated: ",
                                        html.Div(
                                            years_links,
                                            style={"display": "flex", "flexWrap": "wrap", "gap": "8px"},
                                        ),
                                    ],
                                    style={"marginBottom": "10px"},
                                ),
                            ],
                            width=9,
                        ),
                        dbc.Col(
                            [
                                html.Img(
                                    src=avatar_url,
                                    alt=f"Team {team_number} Avatar",
                                    style={
                                        "maxWidth": "150px",
                                        "width": "100%",
                                        "height": "auto",
                                        "objectFit": "contain",
                                        "borderRadius": "10px",
                                        "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                        "marginLeft": "auto",
                                        "marginRight": "auto",
                                        "display": "block",
                                    },
                                ) if avatar_url else html.Div("No avatar available.", style={"color": "#777"}),
                            ],
                            width=3,
                            style={"textAlign": "center"},
                        )
                    ],
                    align="center",
                ),
            ],
            style={"fontSize": "1.1rem"}
        ),
        style={
            "marginBottom": "20px",
            "borderRadius": "10px",
            "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)",
            "backgroundColor": "#f9f9f9",
        },
    )
    
     # --- Performance Metrics ---
    if year in {2023, 2024, 2025}:
        wins = selected_team.get("wins", 0)
        losses = selected_team.get("losses", 0)
        total_matches = wins + losses
        avg_score = selected_team.get("average_match_score", 0)
    else:
        matches = tba_get(f"team/{team_key}/matches/{year or 2025}")
        total_matches = len(matches) if matches else 0

        wins = sum(
            1
            for match in matches
            if (match["winning_alliance"] == "red" and team_key in match["alliances"]["red"]["team_keys"]) or 
               (match["winning_alliance"] == "blue" and team_key in match["alliances"]["blue"]["team_keys"])
        ) if matches else 0
        losses = total_matches - wins

        total_score = sum(
            match["alliances"]["red"]["score"] if team_key in match["alliances"]["red"]["team_keys"]
            else match["alliances"]["blue"]["score"]
            for match in matches
        ) if matches else 0
        avg_score = total_score / total_matches if total_matches > 0 else 0

    win_loss_ratio = html.Span([
        html.Span(f"{wins}", style={"color": "green", "fontWeight": "bold"}),
        html.Span("/", style={"color": "#333", "fontWeight": "bold"}),
        html.Span(f"{losses}", style={"color": "red", "fontWeight": "bold"})
    ])

    perf = html.H5(
        f"{year or 2025} Performance Metrics",
        style={
            "textAlign": "center",
            "color": "#444",
            "fontSize": "1.3rem",
            "fontWeight": "bold",
            "marginBottom": "10px",
        },
    )

    performance_card = dbc.Card(
        dbc.CardBody(
            [
                perf,
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{country} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(f"{country_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#FFC107"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Global Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(f"{global_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#007BFF"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{state} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.1rem"}),
                                        html.P(f"{state_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#FFC107"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                        style={"marginBottom": "10px"},
                    ),
                ),
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Win/Loss Ratio", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(win_loss_ratio, style={"fontSize": "1.1rem", "fontWeight": "bold"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Avg Match Score", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(f"{avg_score:.2f}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                    ),
                ),
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Auto EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(auto_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Teleop EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(teleop_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Endgame EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(endgame_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ]
                    )
                ),
            ],
        ),
        style={"marginBottom": "15px", "borderRadius": "8px", "boxShadow": "0px 2px 4px rgba(0,0,0,0.1)", "backgroundColor": "#f9f9f9", "padding": "10px"},
    )
    
    # --- Rank Over Time Tabs ---
    # Use years_participated as the range (fallback to current year if not available)
    if years_participated and isinstance(years_participated, list):
        team_years = sorted([int(yr) for yr in years_participated])
    else:
        team_years = [year or 2025]

    # Helper function: Compute rank history for the team across years.
    def get_rank_history(team_number, years):
        history = []
        for yr in years:
            file_path = os.path.join("team_data", f"teams_{yr}.json")
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r") as f:
                yearly_data = json.load(f)
            selected = next((team for team in yearly_data if team["team_number"] == int(team_number)), None)
            if not selected:
                continue
            grank, crank, srank = calculate_ranks(yearly_data, selected)
            history.append({
                "year": yr,
                "global_rank": grank,
                "country_rank": crank,
                "state_rank": srank
            })
        return sorted(history, key=lambda x: x["year"])

    rank_history = get_rank_history(team_number, team_years)

    def create_rank_figure(history, title, key):
        """
        history: a list of dicts with keys ["year", "global_rank", "country_rank", "state_rank", ...]
        title: the chart title (e.g., "Global Rank Over Time")
        key: which rank to plot (e.g., "global_rank", "country_rank", or "state_rank")
        """
        years_list = [item["year"] for item in history]
        ranks = [item[key] for item in history]
        if not ranks:
            # If no data, return an empty figure
            return go.Figure()
    
        # 1) Pick a baseline that is numerically bigger than all ranks
        baseline = max(ranks) + 10
    
        # Create the figure
        fig = go.Figure()
    
        # 2) Build up a gradient in multiple layers
        num_layers = 10  # The number of semi-transparent layers
        for i in range(num_layers):
            # factor goes from 0 to 1 across the layers
            factor = (i + 1) / num_layers
            # Interpolate each point from baseline down to the actual rank
            # factor=0 => y=baseline, factor=1 => y=ranks
            layer_y = [
                baseline - factor * (baseline - r) 
                for r in ranks
            ]
            # Adjust opacity so it’s strongest near the line
            alpha = 0.3 * (factor)
            fillcolor = f"rgba(255,255,0,{alpha})"  # Yellow with varying opacity
    
            # For the first layer, use fill='tozeroy' so it starts from baseline.
            # For subsequent layers, fill='tonexty' to stack each layer on top of the previous one.
            fillmode = "tozeroy" if i == 0 else "tonexty"
    
            fig.add_trace(
                go.Scatter(
                    x=years_list,
                    y=layer_y,
                    mode="lines",
                    line=dict(width=0),
                    fill=fillmode,
                    fillcolor=fillcolor,
                    showlegend=False,
                    hoverinfo="skip"
                )
            )
    
        # 3) Finally, add the actual rank line on top
        fig.add_trace(
            go.Scatter(
                x=years_list,
                y=ranks,
                mode="lines+markers",
                line=dict(width=2, color="yellow"),
                marker=dict(size=6),
                name="Rank",
                showlegend=False 
            )
        )
    
        # Because lower rank is better, we reverse the y‐axis
        fig.update_layout(
            title=title,
            xaxis_title="Year",
            yaxis_title="Rank",
            yaxis_autorange="reversed",  # So smaller ranks appear at the top
            template="plotly_white",
            margin=dict(l=40, r=40, t=40, b=40),
        )
    
        return fig


    global_rank_fig = create_rank_figure(rank_history, "Global Rank Over Time", "global_rank")
    country_rank_fig = create_rank_figure(rank_history, "Country Rank Over Time", "country_rank")
    state_rank_fig = create_rank_figure(rank_history, "State Rank Over Time", "state_rank")

    rank_tabs = dcc.Tabs([
        dcc.Tab(label="Global Rank", children=[dcc.Graph(figure=global_rank_fig)]),
        dcc.Tab(label="Country Rank", children=[dcc.Graph(figure=country_rank_fig)]),
        dcc.Tab(label="State Rank", children=[dcc.Graph(figure=state_rank_fig)]),
    ])
    
    # --- Team Events ---
    if year:
        events = tba_get(f"team/{team_key}/events/{year}")
    else:
        events = tba_get(f"team/{team_key}/events")
    events = sorted(events, key=lambda ev: ev.get("start_date", ""), reverse=True)
    event_key_to_name = {ev["key"]: ev["name"] for ev in events}
    events_data = []
    for ev in events:
        event_key = ev.get("key")
        event_name = ev.get("name", "")
        event_url = f"https://www.peekorobo.com/event/{event_key}"
        location = f"{ev.get('city', '')}, {ev.get('state_prov', '')}"
        start_date = ev.get("start_date", "")
        end_date = ev.get("end_date", "")
        if year:
            rankings = tba_get(f"event/{event_key}/rankings")
            rank = None
            if rankings and "rankings" in rankings:
                for entry in rankings["rankings"]:
                    if entry["team_key"] == team_key:
                        rank = entry["rank"]
                if rank:
                    event_name = f"{event_name} (Rank: {rank})"
        events_data.append({
            "event_name": f"[{event_name}]({event_url})",
            "event_location": location,
            "start_date": start_date,
            "end_date": end_date,
        })

    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name", "presentation": "markdown"},
            {"name": "Location", "id": "event_location"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        data=events_data,
        page_size=5,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"},
        style_cell={"textAlign": "center", "padding": "10px", "border": "1px solid #ddd"},
        style_cell_conditional=[{"if": {"column_id": "event_name"}, "textAlign": "center"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    if year:
        awards = tba_get(f"team/{team_key}/awards/{year}")
    else:
        awards = sorted(tba_get(f"team/{team_key}/awards") or [], key=lambda aw: aw.get("year", 0), reverse=True)
    awards_data = [
        {
            "award_name": aw.get("name", "Unknown Award"),
            "event_name": event_key_to_name.get(aw.get("event_key"), "Unknown Event"),
            "award_year": aw.get("year", "N/A"),
        }
        for aw in (awards or [])
    ]
    awards_table = dash_table.DataTable(
        columns=[
            {"name": "Award Name", "id": "award_name"},
            {"name": "Event Name", "id": "event_name"},
            {"name": "Year", "id": "award_year"},
        ],
        data=awards_data,
        page_size=5,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"},
        style_cell={"textAlign": "center", "padding": "10px", "border": "1px solid #ddd"},
        style_cell_conditional=[{"if": {"column_id": "award_name"}, "textAlign": "left"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    blue_banner_awards = ["Chairman's", "Impact", "Woodie Flowers", "Winner"]
    blue_banners = []
    if awards:
        for award in awards:
            award_name = award.get("name", "")
            event_name = event_key_to_name.get(award.get("event_key"), "Unknown Event")
            if any(keyword in award_name.lower() for keyword in ["chairman's", "impact", "winner", "woodie flowers"]):
                blue_banners.append({"award_name": award_name, "event_name": event_name})
    blue_banner_section = html.Div(
        [
            html.Div(
                [
                    html.A(
                        href=f"https://www.thebluealliance.com/event/{banner.get('event_key', '#')}" if banner.get("event_key") else "#",
                        target="_blank" if banner.get("event_key") else "",
                        children=[
                            html.Div(
                                [
                                    html.Img(
                                        src="/assets/banner.png",
                                        style={"width": "120px", "height": "auto", "position": "relative"},
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                banner.get("award_name", "Unknown Award"),
                                                style={"fontSize": "0.8rem", "color": "white", "fontWeight": "bold", "textAlign": "center", "marginBottom": "3px"},
                                            ),
                                            html.P(
                                                banner.get("event_name", "Unknown Event"),
                                                style={"fontSize": "0.6rem", "color": "white", "textAlign": "center"},
                                            ),
                                        ],
                                        style={"position": "absolute", "top": "50%", "left": "50%", "transform": "translate(-50%, -50%)"},
                                    ),
                                ],
                                style={"position": "relative", "marginBottom": "15px"},
                            ),
                        ],
                        style={"textDecoration": "none"} if banner.get("event_key") else {},
                    )
                    for banner in blue_banners
                ],
                style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center", "gap": "10px"},
            ),
        ],
        style={"marginBottom": "15px", "borderRadius": "8px", "backgroundColor": "white", "padding": "10px"},
    )
    
    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    team_card,
                    performance_card,
                    rank_tabs,  # Rank Over Time tabs inserted here
                    html.H3("Team Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Team Awards", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    awards_table,
                    blue_banner_section,
                    html.Br(),
                    dbc.Button("Go Back", id="btn-go-back", color="secondary", href="/", external_link=True, 
                               style={"borderRadius": "5px", "padding": "10px 20px", "marginTop": "20px"}),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )


def clean_category_label(raw_label):
    label = raw_label.replace("typed_", "").replace("_", " ").replace("insights","").title()
    return label

def insights_layout(year=2025, category="typed_leaderboard_blue_banners", notable_category="notables_division_finals_appearances"):
    # Fetch leaderboard data
    insights_data = tba_get(f"insights/leaderboards/{year}")
    notables_data = tba_get(f"insights/notables/{year}")
    
    if not insights_data or not notables_data:
        return html.Div("Error fetching insights or notables data.")

    # Extract leaderboard and notable categories
    insights_categories = [
        {"label": clean_category_label(item["name"]), "value": item["name"]}
        for item in insights_data
    ]
    notable_categories = [
        {"label": clean_category_label(item["name"]), "value": item["name"]}
        for item in notables_data
    ]
    
    if not notable_categories:
        print("Error: No notable categories found")


    # Default to the first category if not provided
    if category not in [item["value"] for item in insights_categories]:
        category = insights_categories[0]["value"]

    if not notable_categories:
        notable_category = None
    elif notable_category not in [item["value"] for item in notable_categories]:
        notable_category = notable_categories[0]["value"]

    # Filter data for the selected categories
    insights_table_data = []
    notable_entries = []
    for item in insights_data:
        if item["name"] == category:
            rankings = item.get("data", {}).get("rankings", [])
            for rank in rankings:
                for team_key in rank.get("keys", []):
                    team_number = team_key.replace("frc", "")
                    insights_table_data.append({
                        "Team": team_number,
                        "Value": rank.get("value", 0),
                    })

    notable_entries = []
    for item in notables_data:
        if item["name"] == notable_category:
            entries = item.get("data", {}).get("entries", [])
            print(f"Entries for category {notable_category}:", entries)  # Debugging
            notable_entries.extend([
                {
                    "Context": entry["context"][0] if entry.get("context") else "N/A",
                    "Team": entry["team_key"].replace("frc", ""),
                }
                for entry in entries
            ])
    
    if not notable_entries:
        print("Error: Notable entries not found for the selected category")

    # Sort insights data by value
    insights_table_data = sorted(insights_table_data, key=lambda x: x["Value"], reverse=True)

    # Create DataTables
    insights_table = dash_table.DataTable(
        id="insights-table",
        columns=[
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Value", "id": "Value"},
            {"name": "Rank", "id": "Rank"},
        ],
        data=insights_table_data,
        page_size=10,
        sort_action="native",
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_cell={"textAlign": "left", "padding": "10px", "fontFamily": "Arial, sans-serif", "fontSize": "14px"},
        style_header={"backgroundColor": "#FFCC00", "color": "#333", "fontWeight": "bold", "border": "1px solid #ddd"},
    )

    notables_table = dash_table.DataTable(
        id="notables-table",
        columns=[
            {"name": "Context", "id": "Context"},
            {"name": "Team", "id": "Team"},
        ],
        data=notable_entries,
        page_size=10,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "color": "#333", "fontWeight": "bold", "border": "1px solid #ddd"},
        style_cell={"textAlign": "left", "padding": "10px", "fontFamily": "Arial, sans-serif", "fontSize": "14px"},
    )

    return html.Div([
        topbar,
        dbc.Container(
            [
                html.H2("Insights", className="text-center mb-4"),
                dbc.Row([
                    dbc.Col(dcc.Dropdown(
                        id="year-selector",
                        options=[{"label": f"{year}", "value": year} for year in range(2000, 2026)],
                        value=year,
                        placeholder="Select Year",
                        className="mb-4"
                    ), width=4),
                    dbc.Col(dcc.Dropdown(
                        id="category-selector",
                        options=insights_categories,
                        value=category,
                        placeholder="Select Insights Category",
                        className="mb-4"
                    ), width=4),
                    dbc.Col(dcc.Dropdown(
                        id="notable-category-selector",
                        options=notable_categories,
                        value=notable_category,
                        placeholder="Select Notables Category",
                        className="mb-4",
                        disabled=notable_category is None  # Disable dropdown if no notable categories
                    ), width=4),
                ]),
                html.H3("Insights", className="mt-4"),
                insights_table,
                html.H3("Notables", className="mt-4"),
                notables_table,
            ],
            style={"maxWidth": "1200px", "margin": "0 auto"},
        ),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer,
    ])

@app.callback(
    [Output("insights-table", "data"), Output("notables-table", "data")],
    [Input("year-selector", "value"), Input("category-selector", "value"), Input("notable-category-selector", "value")],
)
def update_insights(year, category, notable_category):
    if not year:
        year = 2025
    
    # Fetch leaderboard and notables data
    insights_data = tba_get(f"insights/leaderboards/{year}")
    notables_data = tba_get(f"insights/notables/{year}")
    if not insights_data or not notables_data:
        return [], []

    # Insights data processing
    insights_table_data = []
    rankings = []
    for item in insights_data:
        if item["name"] == category:
            rankings = item.get("data", {}).get("rankings", [])

    # Sort rankings by value and compute ranks
    sorted_rankings = sorted(rankings, key=lambda x: x["value"], reverse=True)
    current_rank = 0
    last_value = None
    for i, rank in enumerate(sorted_rankings):
        team_keys = rank.get("keys", [])
        for team_key in team_keys:
            team_number = team_key.replace("frc", "")
            team_link = f"[{team_number}](/team/{team_number}/{year})"

            # Assign rank
            if rank["value"] != last_value:
                current_rank = i + 1
                last_value = rank["value"]

            # Style rank based on position
            rank_display = f"{current_rank}" if current_rank > 3 else ["🥇", "🥈", "🥉"][current_rank - 1] + f" {current_rank}"
            insights_table_data.append({
                "Team": team_link,
                "Value": rank.get("value", 0),
                "Rank": rank_display,
            })

    # Notables data processing
    notables_data_processed = []
    for item in notables_data:
        if item["name"] == notable_category:
            entries = item.get("data", {}).get("entries", [])
            notables_data_processed.extend([
                {
                    "Context": entry["context"][0] if entry.get("context") else "N/A",
                    "Team": entry["team_key"].replace("frc", ""),
                }
                for entry in entries
            ])

    return insights_table_data, notables_data_processed

def events_layout(year=2025):
    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": str(yr), "value": yr} for yr in range(2000, 2026)],
        value=year,
        placeholder="Year",
        clearable=False
    )
    event_type_dropdown = dcc.Dropdown(
        id="event-type-dropdown",
        options=[
            {"label": "All", "value": "all"},
            {"label": "Season", "value": "season"},
            {"label": "Off-season", "value": "offseason"},
            {"label": "Regional", "value": "regional"},
            {"label": "District", "value": "district"},
            {"label": "Championship", "value": "championship"},
        ],
        value=["all"],
        multi=True,
        placeholder="Filter by Event Type",
    )
    week_dropdown = dcc.Dropdown(
        id="week-dropdown",
        options=(
            [{"label": "All", "value": "all"}] +
            [{"label": f"Week {i+1}", "value": i} for i in range(0, 9)]
        ),
        value="all",
        placeholder="Week",
        clearable=False,
    )
    search_input = dbc.Input(
        id="search-input",
        placeholder="Search",
        type="text",
    )

    filters_row = dbc.Row(
        [
            dbc.Col(year_dropdown, xs=6, sm=3, md=2),
            dbc.Col(event_type_dropdown, xs=6, sm=3, md=2),
            dbc.Col(week_dropdown, xs=6, sm=3, md=2),
            dbc.Col(search_input, xs=6, sm=3, md=2),
        ],
        className="mb-4 justify-content-center",
        style={"gap": "10px"},
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    # Upcoming Events
                    html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="upcoming-events-container", className="justify-content-center"),

                    # Ongoing Events
                    html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="ongoing-events-container", className="justify-content-center"),

                    # All Events
                    html.H3("All Events", className="mb-4 mt-4 text-center"),
                    filters_row,
                    html.Div(
                        id="all-events-container",
                        className="d-flex flex-wrap justify-content-center"
                    ),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer
        ]
    )

# Helper to build a Bootstrap Card for one event
def create_event_card(event):
    event_url = f"https://www.peekorobo.com/event/{event['key']}"
    location = f"{event.get('city','')}, {event.get('state_prov','')}, {event.get('country','')}"
    start = event.get('start_date', 'N/A')
    end = event.get('end_date', 'N/A')
    event_type = event.get('event_type_string', 'N/A')

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H5(event["name"], className="card-title mb-3"),
                    html.P(location, className="card-text"),
                    html.P(f"Dates: {start} - {end}", className="card-text"),
                    html.P(f"Type: {event_type}", className="card-text"),
                    dbc.Button("View Details", href=event_url, target="_blank",
                               color="warning", className="mt-2"),
                ]
            )
        ],
        className="mb-4 shadow",
        style={
            "width": "18rem",
            "height": "20rem",  # force uniform height
            "margin": "10px"
        }
    )

@app.callback(
    [
        Output("upcoming-events-container", "children"),
        Output("ongoing-events-container", "children"),  # new
        Output("all-events-container", "children"),
    ],
    [
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("week-dropdown", "value"),
        Input("search-input", "value"),
    ],
)
def update_events_table(selected_year, selected_event_types, selected_week, search_query):
    # 1. Fetch event data
    events_data = tba_get(f"events/{selected_year}")
    if not events_data:
        return [], [], []

    # make selected_event_types a list
    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    # 2. Filter by event type
    if "all" not in selected_event_types:
        filtered = []
        for et in selected_event_types:
            if et == "season":
                filtered.extend([ev for ev in events_data if ev["event_type"] not in [99, 100]])
            elif et == "offseason":
                filtered.extend([ev for ev in events_data if ev["event_type"] in [99, 100]])
            elif et == "regional":
                filtered.extend([ev for ev in events_data if "Regional" in ev.get("event_type_string","")])
            elif et == "district":
                filtered.extend([ev for ev in events_data if "District" in ev.get("event_type_string","")])
            elif et == "championship":
                filtered.extend([ev for ev in events_data if "Championship" in ev.get("event_type_string","")])
        events_data = list({ev["key"]: ev for ev in filtered}.values())

    # 3. Filter by week
    if selected_week != "all":
        events_data = [ev for ev in events_data if ev.get("week") == selected_week]

    # 4. Filter by search
    if search_query:
        q = search_query.lower()
        events_data = [
            ev for ev in events_data
            if q in ev.get("name","").lower() or q in ev.get("city","").lower()
        ]

    # 5. Parse and sort by start_date
    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)
    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("start_date","1900-01-01"))
        ev["_end_date_obj"]   = parse_date(ev.get("end_date","1900-01-01"))
    events_data.sort(key=lambda x: x["_start_date_obj"])

    today = datetime.date.today()

    # 6. Identify upcoming, ongoing
    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    # "All events" is the entire filtered list
    all_events = events_data

    # 7. Build card layouts
    # upcoming
    up_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in upcoming[:5]]  # top 5 upcoming
    upcoming_layout = dbc.Row(up_cards, className="justify-content-center")

    # ongoing
    ongoing_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in ongoing]
    ongoing_layout = dbc.Row(ongoing_cards, className="justify-content-center")

    # all
    all_event_cards = [create_event_card(ev) for ev in all_events]

    return upcoming_layout, ongoing_layout, all_event_cards

def load_teams_and_compute_epa_ranks(year):
    """
    Loads teams data from teams_<year>.json, computes EPA percentiles and global ranks.
    Returns a dict { team_number: {"epa": float or None, "rank": int, "epa_display": str } } for easy lookups.
    """
    folder_path = "team_data"
    epa_info = {}

    # Attempt to load the file
    file_path = os.path.join(folder_path, f"teams_{year}.json")
    if not os.path.exists(file_path):
        return epa_info  # Return empty if no file for that year

    with open(file_path, "r") as f:
        teams_data = json.load(f)

    # Sort by EPA descending
    teams_data = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)

    # Collect all EPA values to compute percentiles
    epa_values = [t["epa"] for t in teams_data if t.get("epa") is not None]
    if not epa_values:
        return epa_info

    epa_values = [t["epa"] for t in teams_data if t.get("epa") is not None]
    if epa_values:
        percentiles = {
            "99": np.percentile(epa_values, 99),
            "95": np.percentile(epa_values, 95),
            "90": np.percentile(epa_values, 90),
            "75": np.percentile(epa_values, 75),
            "50": np.percentile(epa_values, 50),
            "25": np.percentile(epa_values, 25),
        }
    else:
        # fallback zeros
        percentiles = {"99":0, "95":0, "90":0, "75":0, "50":0, "25":0}


    # Assign global rank and build a quick lookup
    for idx, t in enumerate(teams_data):
        team_number = t["team_number"]
        epa_val = t.get("epa", None)
        rank = idx + 1
        epa_info[team_number] = {
            "epa": epa_val,
            "rank": rank,
            "epa_display": get_epa_display(epa_val, percentiles),
        }

    return epa_info

def event_layout(event_key):
    # Fetch event details

    parsed_year, event_code = parse_event_key(event_key)
    
    event_details = tba_get(f"event/{event_key}")
    if not event_details:
        return dbc.Alert("Event details could not be fetched.", color="danger")

    event_year = parsed_year if parsed_year else event_details.get("year", 2025)
    epa_data = load_teams_and_compute_epa_ranks(event_year)

    # TBA calls
    rankings = tba_get(f"event/{event_key}/rankings") or {"rankings": []}
    oprs = tba_get(f"event/{event_key}/oprs") or {"oprs": {}}
    event_teams = tba_get(f"event/{event_key}/teams") or []
    event_matches = tba_get(f"event/{event_key}/matches") or []

    # Basic info
    event_name = event_details.get("name", "Unknown Event")
    event_location = f"{event_details.get('city', '')}, {event_details.get('state_prov', '')}, {event_details.get('country', '')}"
    start_date = event_details.get("start_date", "N/A")
    end_date = event_details.get("end_date", "N/A")
    event_type = event_details.get("event_type_string", "N/A")
    website = event_details.get("website", "#")

    # Build the header card (left side), ensuring it can stretch
    header_card = dbc.Card(
        dbc.CardBody([
            html.H2(f"{event_name} ({event_year})", className="card-title mb-3", style={"fontWeight": "bold"}),
            html.P(f"Location: {event_location}", className="card-text"),
            html.P(f"Dates: {start_date} - {end_date}", className="card-text"),
            html.P(f"Type: {event_type}", className="card-text"),
            dbc.Button(
                "Visit Event Website",
                href=website,
                external_link=True,
                className="mt-3",
                style={
                    "backgroundColor": "#FFCC00",
                    "borderColor": "#FFCC00",
                    "color": "black",
                },
            )
        ]),
        className="mb-4 shadow-sm flex-fill",  # flex-fill ensures the card occupies full height
        style={"borderRadius": "10px"}
    )

    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": str(y), "value": y} for y in range(1992, 2031)],
        value=event_year,
        clearable=False,
        style={"width": "150px"}
    )

    dropdown_card = dbc.Card(
        dbc.CardBody([
            html.Label("Year:", style={"fontWeight": "bold"}),
            year_dropdown
        ]),
        className="mb-4 shadow-sm flex-fill",
        style={"borderRadius": "10px", "padding": "10px"}
    )

    # ------------------ Last Match Thumbnail (Right side) ------------------
    last_match = None
    if event_matches:
        # Prefer finals if available
        final_matches = [m for m in event_matches if m.get("comp_level") == "f"]
        if final_matches:
            final_matches.sort(key=lambda m: m.get("match_number", 0))
            last_match = final_matches[-1]
        else:
            event_matches.sort(key=lambda m: m.get("match_number", 0))
            last_match = event_matches[-1]

    last_match_thumbnail = None
    if last_match:
        video_key = None
        for vid in last_match.get("videos", []):
            if vid.get("type") == "youtube":
                video_key = vid.get("key")
                break
        if video_key:
            thumbnail_url = f"https://img.youtube.com/vi/{video_key}/hqdefault.jpg"
            last_match_thumbnail = dbc.Card(
                dbc.CardBody(
                    html.A(
                        html.Img(
                            src=thumbnail_url,
                            style={"width": "100%", "borderRadius": "5px"},
                        ),
                        href=f"https://www.youtube.com/watch?v={video_key}",
                        target="_blank"
                    )
                ),
                className="mb-4 shadow-sm flex-fill",  # Make this card also fill its parent column
                style={"borderRadius": "10px"}
            )

    # ------------------ Combine header card & thumbnail in one row ------------------
    # Use .d-flex and .align-items-stretch to ensure both columns match height
    header_layout = dbc.Row(
        [
            dbc.Col(header_card, md=8, className="d-flex align-items-stretch"),
            dbc.Col(last_match_thumbnail, md=4, className="d-flex align-items-stretch") if last_match_thumbnail else dbc.Col()
        ],
        className="mb-4"
    )

    tab_style = {"color": "#3b3b3b"}
    data_tabs = dbc.Tabs(
        [
            dbc.Tab(label="Teams", tab_id="teams", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Rankings", tab_id="rankings", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="OPRs", tab_id="oprs", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Matches", tab_id="matches", label_style=tab_style, active_label_style=tab_style),
        ],
        id="event-data-tabs",
        active_tab="teams",
        className="mb-4",
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    header_layout,   # Row with event card (left) and last match thumbnail (right)
                    data_tabs,
                    # Hidden data storage
                    dcc.Store(id="store-rankings", data=rankings),
                    dcc.Store(id="store-oprs", data=oprs),
                    dcc.Store(id="store-event-epa", data=epa_data),
                    dcc.Store(id="store-event-teams", data=event_teams),
                    dcc.Store(id="store-event-matches", data=event_matches),
                    dcc.Store(id="store-event-year", data=event_year),
                    # The tab content
                    html.Div(id="data-display-container"),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def create_team_card_spotlight(team, epa_data, event_year):
    """
    Similar to your 'teams page' approach: fetch avatar, display EPA & rank.
    """
    from urllib.parse import quote

    t_num = team.get("team_number", None)
    nickname = team.get("nickname", "Unknown")
    city = team.get("city", "")
    state = team.get("state_prov", "")
    country = team.get("country", "")
    location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

    # Pull from epa_data (string keys)
    epa_rank = "N/A"
    epa_display = "N/A"
    if t_num and str(t_num) in epa_data:
        info = epa_data[str(t_num)]
        epa_rank = info.get("rank", "N/A")
        epa_display = info.get("epa_display", "N/A")

    # Avatars
    avatar_url = get_team_avatar(t_num, event_year)

    # Build the link to /team/<num>/<year>
    team_url = f"/team/{t_num}/{event_year}"

    card_elems = []
    if avatar_url:
        card_elems.append(
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "width": "100%",
                    "height": "150px",
                    "objectFit": "contain",
                    "backgroundColor": "#fff",
                    "padding": "5px"
                }
            )
        )
    card_elems.append(
        dbc.CardBody(
            [
                html.H5(f"#{t_num} | {nickname}", className="card-title mb-3"),
                html.P(f"Location: {location_str}", className="card-text"),
                html.P(f"EPA: {epa_display} (Global Rank: {epa_rank})", className="card-text"),
                dbc.Button("View Team", href=team_url, color="warning", className="mt-2"),
            ]
        )
    )

    return dbc.Card(
        card_elems,
        className="m-2 shadow",
        style={
            "width": "18rem",
            "height": "26rem",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "start",
            "alignItems": "stretch",
        },
    )

import re

def parse_event_key(event_key):
    m = re.match(r'^(\d{4})(.+)$', event_key)
    if m:
        return int(m.group(1)), m.group(2)
    return None, event_key

@app.callback(
    Output("data-display-container", "children"),
    Input("event-data-tabs", "active_tab"),
    State("store-rankings", "data"),
    State("store-oprs", "data"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-event-matches", "data"),
    State("store-event-year", "data"), 
)
def update_display(active_tab, rankings, oprs, epa_data, event_teams, event_matches, event_year):
    if not active_tab:
        return dbc.Alert("Select a data category above.", color="info")

    # Common DataTable styling
    common_style_table = {
        "overflowX": "auto",
        "border": "1px solid #ddd",
        "borderRadius": "5px",
    }
    common_style_header = {
        "backgroundColor": "#F2F2F2",
        "fontWeight": "bold",
        "border": "1px solid #ddd",
        "textAlign": "center",
    }
    common_style_cell = {
        "textAlign": "center",
        "border": "1px solid #ddd",
        "padding": "8px",
    }

    # ------------------ RANKINGS TAB ------------------
    if active_tab == "rankings":
        columns = [
            {"name": "Rank", "id": "Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins"},
            {"name": "Losses", "id": "Losses"},
            {"name": "Ties", "id": "Ties"},
            {"name": "DQ", "id": "DQ"},
            {"name": "EPA Rank", "id": "EPA_Rank"},
            {"name": "EPA", "id": "EPA"},
        ]

        data_rows = []
        for rank_info in (rankings.get("rankings", []) or []):
            team_key = rank_info.get("team_key", "")
            tnum_str = team_key.replace("frc", "")
            try:
                tnum = int(tnum_str)
            except ValueError:
                tnum = None

            epa_rank = "N/A"
            epa_display = "N/A"
            if tnum and str(tnum) in epa_data:
                epa_info = epa_data[str(tnum)]
                epa_rank = epa_info["rank"]
                epa_display = epa_info["epa_display"]

            data_rows.append(
                {
                    "Rank": rank_info.get("rank", "N/A"),
                    "Team": f"[{tnum_str}](/team/{tnum_str})",
                    "Wins": rank_info.get("record", {}).get("wins", "N/A"),
                    "Losses": rank_info.get("record", {}).get("losses", "N/A"),
                    "Ties": rank_info.get("record", {}).get("ties", "N/A"),
                    "DQ": rank_info.get("dq", "N/A"),
                    "EPA_Rank": epa_rank,
                    "EPA": epa_display,
                }
            )

        # Sort by "Rank" ascending
        def safe_int(val):
            try:
                return int(val)
            except:
                return 999999
        data_rows.sort(key=lambda r: safe_int(r["Rank"]))

        rankings_table = dash_table.DataTable(
            columns=columns,
            data=data_rows,
            page_size=10,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
        )
        
        return html.Div([
            epa_legend_layout(),
            rankings_table
        ])

    # ------------------ OPRS TAB ------------------
    elif active_tab == "oprs":
        data = []
        # Convert each frcXXXX to a clickable link
        for team_key, opr_val in (oprs.get("oprs") or {}).items():
            tnum_str = team_key.replace("frc", "")
    
            # Retrieve EPA & Rank from epa_data if available
            epa_rank = "N/A"
            epa_display = "N/A"
            if tnum_str in epa_data:
                epa_info = epa_data[tnum_str]
                epa_rank = epa_info.get("rank", "N/A")
                epa_display = epa_info.get("epa_display", "N/A")
    
            data.append({
                "Team": f"[{tnum_str}](/team/{tnum_str})",  # clickable link
                "OPR": opr_val,
                "EPA Rank": epa_rank,
                "EPA": epa_display,
            })
    
        # Sort by OPR descending
        data.sort(key=lambda x: x["OPR"], reverse=True)
    
        # Assign a simple "OPR Rank" (just for display)
        for i, row in enumerate(data):
            row["OPR Rank"] = i + 1
    
        # Define the columns, marking "Team" as Markdown
        columns = [
            {"name": "OPR Rank", "id": "OPR Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "OPR", "id": "OPR"},
            {"name": "EPA Rank", "id": "EPA Rank"},
            {"name": "EPA", "id": "EPA"},
        ]
    
        return dash_table.DataTable(
            columns=columns,
            data=data,
            page_size=10,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
        )


    # ------------------ TEAMS TAB ------------------
    elif active_tab == "teams":
        # 1) Identify top 3 by ascending epa rank:
        def safe_int(val):
            try: return int(val)
            except: return 999999

        sorted_teams = sorted(
            event_teams,
            key=lambda t: safe_int(epa_data.get(str(t.get("team_number")), {}).get("rank", 999999))
        )
        top_3 = sorted_teams[:3]

        # 2) Build spotlight cards for top_3
        spotlight_cards = []
        for top_team in top_3:
            card = create_team_card_spotlight(top_team, epa_data, event_year)
            spotlight_cards.append(dbc.Col(card, width="auto"))

        spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")

        # 3) Build the standard table (like before)
        rows = []
        for t in event_teams:
            t_num = t.get("team_number")
            t_str = str(t_num) if t_num else "N/A"
            epa_rank = "N/A"
            epa_disp = "N/A"
            if t_num and str(t_num) in epa_data:
                e_info = epa_data[str(t_num)]
                epa_rank = e_info["rank"]
                epa_disp = e_info["epa_display"]

            city = t.get("city", "")
            st = t.get("state_prov", "")
            ctry = t.get("country", "")
            loc = ", ".join(filter(None, [city, st, ctry])) or "Unknown"

            rows.append({
                "EPA Rank": epa_rank,
                "EPA": epa_disp,
                "Team Number": f"[{t_str}](/team/{t_str})",
                "Nickname": t.get("nickname", "Unknown"),
                "Location": loc,
            })

        rows.sort(key=lambda r: safe_int(r["EPA Rank"]))

        columns = [
            {"name": "EPA Rank", "id": "EPA Rank"},
            {"name": "EPA", "id": "EPA"},
            {"name": "Team Number", "id": "Team Number", "presentation": "markdown"},
            {"name": "Nickname", "id": "Nickname"},
            {"name": "Location", "id": "Location"},
        ]

        teams_table = dash_table.DataTable(
            columns=columns,
            data=rows,
            page_size=10,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
        )

        return html.Div([
            html.H4(
                "Spotlight Teams", 
                className="text-center mb-4",
                style={"fontWeight": "bold"}
            ),
            spotlight_layout,
            epa_legend_layout(),
            teams_table
        ])



    # ------------------ MATCHES TAB ------------------
    elif active_tab == "matches":
        # 1) Build the dropdown
        team_filter_options = []
        if event_teams:
            for t in event_teams:
                tnum = t.get("team_number")
                nickname = t.get("nickname","")
                label = f"{tnum} - {nickname}" if nickname else str(tnum)
                team_filter_options.append({"label": label, "value": str(tnum)})

        # 2) Return the layout: a Div with the dropdown + an empty container
        return html.Div([
            html.Div(
                [
                    html.Label("Filter by Team:", style={"fontWeight":"bold"}),
                    dcc.Dropdown(
                        id="team-filter",
                        options=team_filter_options,
                        value=None,
                        placeholder="Select a team...",
                        clearable=True
                    )
                ],
                style={"marginBottom":"20px"}
            ),
            # An empty container for the final table(s)
            html.Div(id="matches-container")
        ])

    # If none of the above, fallback
    return dbc.Alert("No data available.", color="warning")

@app.callback(
    Output("matches-container", "children"),
    Input("team-filter", "value"),
    [
        State("store-event-matches", "data"),
        State("store-event-epa", "data"),
    ],
)
def update_matches_table(selected_team, event_matches, epa_data):
    """
    Called whenever user picks a team in the dropdown.
    Returns the final Matches tables into 'matches-container'.
    """
    event_matches = event_matches or []
    epa_data = epa_data or {}

    # 1) If user selected a team, filter
    if selected_team:
        frc_key = f"frc{selected_team}"
        event_matches = [
            m for m in event_matches
            if frc_key in m["alliances"]["red"]["team_keys"]
               or frc_key in m["alliances"]["blue"]["team_keys"]
        ]

    # 2) Sort & separate
    comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}
    def match_sort_key(m):
        lvl = comp_level_order.get(m.get("comp_level",""),99)
        num = m.get("match_number",9999)
        return (lvl, num)

    event_matches.sort(key=match_sort_key)
    qual_matches = [m for m in event_matches if m.get("comp_level")=="qm"]
    playoff_matches = [m for m in event_matches if m.get("comp_level")!="qm"]

    # 3) Utility
    def format_teams_markdown(team_list):
        links = []
        for t in team_list:
            short = t.replace("frc","")
            links.append(f"[{short}](/team/{short})")
        return ", ".join(links)

    def sum_epa(team_list):
        total = 0.0
        for x in team_list:
            s = x.replace("frc","")
            if s in epa_data:
                val = epa_data[s].get("epa", 0) or 0
                total += val
        return total

    def build_match_rows(matches):
        rows = []
        for match in matches:
            red = match["alliances"]["red"]
            blu = match["alliances"]["blue"]
            winner = match.get("winning_alliance","")
            label = match.get("comp_level","").upper()+str(match.get("match_number",""))

            r_sum = sum_epa(red["team_keys"])
            b_sum = sum_epa(blu["team_keys"])
            if (r_sum+b_sum)>0:
                p_red = r_sum/(r_sum+b_sum)
                p_blue = 1.0 - p_red
                pred_str = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"
            else:
                pred_str = "N/A"

            video_link = "N/A"
            for vid in match.get("videos",[]):
                if vid.get("type")=="youtube":
                    yid = vid["key"]
                    video_link = f"[Watch](https://www.youtube.com/watch?v={yid})"
                    break

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Teams": format_teams_markdown(red["team_keys"]),
                "Blue Teams": format_teams_markdown(blu["team_keys"]),
                "Red Score": red.get("score",0),
                "Blue Score": blu.get("score",0),
                "Winner": winner.title() if winner else "N/A",
                "Prediction": pred_str,
            })
        return rows

    qual_data = build_match_rows(qual_matches)
    playoff_data = build_match_rows(playoff_matches)

    match_columns = [
        {"name":"Video","id":"Video","presentation":"markdown"},
        {"name":"Match","id":"Match"},
        {"name":"Red Teams","id":"Red Teams","presentation":"markdown"},
        {"name":"Blue Teams","id":"Blue Teams","presentation":"markdown"},
        {"name":"Red Score","id":"Red Score"},
        {"name":"Blue Score","id":"Blue Score"},
        {"name":"Winner","id":"Winner"},
        {"name":"Prediction","id":"Prediction","presentation":"markdown"},
    ]
    row_style = [
        {"if": {"filter_query": '{Winner} = \"Red\"'},  "backgroundColor": "#ffe6e6"},
        {"if": {"filter_query": '{Winner} = \"Blue\"'}, "backgroundColor": "#e6f0ff"},
    ]

    # For brevity, define your styling for tables:
    style_table = {
        "overflowX": "auto",
        "border": "1px solid #ddd",
        "borderRadius": "5px",
    }
    style_header = {
        "backgroundColor": "#F2F2F2",
        "fontWeight": "bold",
        "border": "1px solid #ddd",
        "textAlign": "center",
    }
    style_cell = {
        "textAlign": "center",
        "border": "1px solid #ddd",
        "padding": "8px",
    }

    qual_table = [
        html.H5("Qualification Matches", className="mb-3 mt-3"),
        dash_table.DataTable(
            columns=match_columns,
            data=qual_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if qual_data else [
        html.H5("Qualification Matches", className="mb-3 mt-3"),
        dbc.Alert("No qualification matches found.", color="info"),
    ]

    playoff_table = [
        html.H5("Playoff Matches", className="mb-3 mt-5"),
        dash_table.DataTable(
            columns=match_columns,
            data=playoff_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if playoff_data else [
        html.H5("Playoff Matches", className="mb-3 mt-5"),
        dbc.Alert("No playoff matches found.", color="info"),
    ]

    return html.Div(qual_table + playoff_table)
    
def challenges_layout():
    challenges = []
    for year, game in sorted(frc_games.items(), reverse=True):
        challenges.append(
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            # Game Logo
                            dbc.Col(
                                html.Img(
                                    src=game["logo"],
                                    style={"width": "150px", "height": "auto", "marginRight": "10px"},
                                    alt=game["name"],
                                ),
                                width="auto",
                            ),
                            # Game Info
                            dbc.Col(
                                [
                                    html.H5(
                                        html.A(
                                            f"{game['name']} ({year})",
                                            href=f"/challenge/{year}",
                                            style={"textDecoration": "none", "color": "#007BFF"},
                                        ),
                                        className="mb-1",
                                    ),
                                    html.P(
                                        game.get("summary", "No summary available."),
                                        style={"color": "#555", "marginBottom": "5px", "fontSize": "0.9rem"},
                                    ),
                                ],
                                width=True,
                            ),
                        ],
                        className="align-items-center",
                    )
                ),
                className="mb-3",
            )
        )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H2("Challenges", className="text-center mb-4"),
                    html.P(
                        "The FIRST Robotics Competition is made up of seasons in which the challenge (game), along with the required set of tasks, changes annually. "
                        "Please click on a season to view more information and results.",
                        className="text-center mb-4",
                    ),
                    *challenges,
                ],
                style={"maxWidth": "900px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def challenge_details_layout(year):
    game = frc_games.get(
        year,
        {"name": "Unknown Game", "video": "#", "logo": "/assets/placeholder.png", "manual": "#", "summary": "No summary available."}
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    # Title and Logo
                    html.H2(f"{game['name']} ({year})", className="text-center mb-4"),
                    html.Img(
                        src=game["logo"],
                        style={"display": "block", "margin": "0 auto", "maxWidth": "400px", "borderRadius": "10px"},
                        alt=game["name"],
                        className="mb-4",
                    ),
                    # Summary
                    html.P(
                        game.get("summary", "No summary available."),
                        className="text-center mb-4",
                        style={"fontSize": "1rem", "lineHeight": "1.5", "color": "#555"},
                    ),
                    # Game Manual Button
                    html.Div(
                        dbc.Button(
                            "View Game Manual",
                            href=game["manual"],
                            target="_blank",
                            style={"marginBottom": "20px",
                                  "backgroundColor": "#ffdd00ff",
                                  "color": "black",
                                  "border": "2px solid #555"},
                        ),
                        className="text-center",
                    ),
                    # Video Thumbnail
                    html.P(
                        "Watch the official game reveal:",
                        className="text-center mt-4",
                    ),
                    html.Div(
                        html.A(
                            html.Img(
                                src=f"https://img.youtube.com/vi/{game['video'].split('=')[-1]}/0.jpg",
                                style={
                                    "maxWidth": "400px",
                                    "borderRadius": "8px",
                                    "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)",
                                },
                            ),
                            href=game["video"],
                            target="_blank",
                            style={"display": "block", "margin": "0 auto"},
                        ),
                        className="text-center",
                    ),
                ],
                style={"maxWidth": "800px", "margin": "0 auto", "padding": "20px"},
            ),
            
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def get_team_avatar(team_number, year=2025):
    team_key = f"frc{team_number}"
    avatar_data = tba_get(f"team/{team_key}/media/{year}")
    if not avatar_data:
        return None
    
    # Try to find a base64 Avatar first
    for media in avatar_data:
        if media.get("type") == "avatar" and media.get("details", {}).get("base64Image"):
            return f"data:image/png;base64,{media['details']['base64Image']}"
    
    # Otherwise, fallback to direct_url if preferred or "avatar" isn't found
    for media in avatar_data:
        if media.get("preferred") and media.get("direct_url"):
            return media["direct_url"]

    return None

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
        color = "🟡"  # Yellow
    elif epa >= percentiles["50"]:
        color = "🟠"  # Orange
    elif epa >= percentiles["25"]:
        color = "🔴"  # Brown
    else:
        color = "🟤"  # Red

    return f"{color} {epa:.2f}"

def epa_legend_layout():
    return dbc.Alert(
        [
            html.H5("EPA Color Key (Percentile):", className="mb-3", style={"fontWeight": "bold"}),
            html.Div("🟣  ≥ 99% | 🔵  ≥ 95% | 🟢  ≥ 90% | 🟡  ≥ 75% | 🟠  ≥ 50% | 🔴  ≥ 25% | 🟤  < 25%"),
        ],
        color="light",
        style={
            "border": "1px solid #ccc",
            "borderRadius": "10px",
            "padding": "10px",
            "fontSize": "0.9rem",
        },
    )

def create_team_card(team, selected_year, avatar_url=None):
    team_number = team.get("team_number", "N/A")
    nickname = team.get("nickname", "Unknown")
    epa = team.get("epa", None)
    rank = team.get("global_rank", "N/A")

    location_pieces = []
    if city := team.get("city"): 
        location_pieces.append(city)
    if state := team.get("state_prov"):
        location_pieces.append(state)
    if country := team.get("country"):
        location_pieces.append(country)
    location_str = ", ".join(location_pieces) if location_pieces else "Unknown"

    # If epa is None, display "N/A"; otherwise format
    epa_str = f"{epa:.2f}" if isinstance(epa, (int, float)) else "N/A"
    # Build team URL for more details
    team_url = f"/team/{team_number}/{selected_year}"

    card_body = []
    # Avatar at top if we have one
    if avatar_url:
        card_body.append(
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "width": "100%",
                    "height": "150px",
                    "objectFit": "contain",
                    "backgroundColor": "#fff",
                    "padding": "5px"
                }
            )
        )

    card_body.append(
        dbc.CardBody(
            [
                html.H5(f"#{team_number} | {nickname}", className="card-title mb-3"),
                html.P(f"Location: {location_str}", className="card-text"),
                html.P(f"EPA: {epa_str} (Global Rank: {rank})", className="card-text"),
                dbc.Button("View Team", href=team_url, color="warning", className="mt-2"),
            ]
        )
    )

    return dbc.Card(
        card_body,
        className="m-2 shadow",
        style={
            # fix width/height so each card is the same size
            "width": "18rem",
            "height": "26rem",     # tweak as needed
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "start",
            "alignItems": "stretch",
        },
    )


def teams_layout(default_year=2025):
    teams_year_dropdown = dcc.Dropdown(
        id="teams-year-dropdown",
        options=[{"label": str(y), "value": y} for y in range(1992, 2026)],
        value=default_year,
        clearable=False,
        placeholder="Select Year",
    )

    country_dropdown = dcc.Dropdown(
        id="country-dropdown",
        options=COUNTRIES,  # e.g. [{"label": "All", "value": "All"}, {"label": "USA", "value": "USA"}, ...]
        value="All",
        clearable=False,
        placeholder="Select Country",
    )

    state_dropdown = dcc.Dropdown(
        id="state-dropdown",
        options=[{"label": "All States", "value": "All"}],
        value="All",
        clearable=False,
        placeholder="Select State/Province",
    )

    search_input = dbc.Input(
        id="search-bar",
        placeholder="Search",
        type="text",
        className="mb-3",
    )

    filters_row = dbc.Row(
        [
            dbc.Col(teams_year_dropdown, xs=6, sm=4, md=2),
            dbc.Col(country_dropdown, xs=6, sm=4, md=2),
            dbc.Col(state_dropdown, xs=6, sm=4, md=2),
            dbc.Col(search_input, xs=6, sm=4, md=3),
        ],
        className="mb-4 justify-content-center",
    )

    teams_table = dash_table.DataTable(
        id="teams-table",
        columns=[
            {"name": "EPA Rank", "id": "epa_rank"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "EPA", "id": "epar"},
            {"name": "Auto EPA", "id": "auto_epa"},
            {"name": "Teleop EPA", "id": "teleop_epa"},
            {"name": "Endgame EPA", "id": "endgame_epa"},
            {"name": "Location", "id": "location_display"},
        ],
        data=[],
        page_size=50,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={
            "backgroundColor": "#FFCC00",
            "fontWeight": "bold",
            "textAlign": "center",
            "border": "1px solid #ddd",
        },
        style_cell={
            "textAlign": "center",
            "padding": "10px",
            "border": "1px solid #ddd",
            "fontSize": "14px",
        },
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "1px solid #FFCC00",
            },
        ],
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H4("Top 3 Teams", className="text-center mb-4"),
                    dbc.Row(id="top-teams-container", className="justify-content-center mb-5"),
                    filters_row,
                    epa_legend_layout(),  # EPA color key
                    dbc.Row(dbc.Col(teams_table, width=12), className="mb-4"),
                ],
                style={"padding": "10px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

@callback(
    [
        Output("teams-table", "data"),
        Output("state-dropdown", "options"),
        Output("top-teams-container", "children"),  # For top-3 featured teams
    ],
    [
        Input("teams-year-dropdown", "value"),
        Input("country-dropdown", "value"),
        Input("state-dropdown", "value"),
        Input("search-bar", "value"),
    ],
)
def load_teams(selected_year, selected_country, selected_state, search_query):
    folder_path = "team_data"
    file_path = os.path.join(folder_path, f"teams_{selected_year}.json")
    if not os.path.exists(file_path):
        # No data for this year
        return [], [{"label": "All States", "value": "All"}], []

    # 1) Load the raw data
    with open(file_path, "r") as f:
        teams_data = json.load(f)

    # 2) Sort teams by descending overall EPA (treating None as 0)
    teams_data.sort(key=lambda t: t["epa"] if t.get("epa") is not None else 0, reverse=True)

    # Build percentile dictionaries for each EPA component
    overall_values = [t["epa"] for t in teams_data if t.get("epa") is not None]
    auto_values = [t["auto_epa"] for t in teams_data if t.get("auto_epa") is not None]
    teleop_values = [t["teleop_epa"] for t in teams_data if t.get("teleop_epa") is not None]
    endgame_values = [t["endgame_epa"] for t in teams_data if t.get("endgame_epa") is not None]

    if overall_values:
        overall_percentiles = {
            "99": np.percentile(overall_values, 99),
            "95": np.percentile(overall_values, 95),
            "90": np.percentile(overall_values, 90),
            "75": np.percentile(overall_values, 75),
            "50": np.percentile(overall_values, 50),
            "25": np.percentile(overall_values, 25),
        }
    else:
        overall_percentiles = {"99": 0, "95": 0, "90": 0, "75": 0, "50": 0, "25": 0}

    if auto_values:
        auto_percentiles = {
            "99": np.percentile(auto_values, 99),
            "95": np.percentile(auto_values, 95),
            "90": np.percentile(auto_values, 90),
            "75": np.percentile(auto_values, 75),
            "50": np.percentile(auto_values, 50),
            "25": np.percentile(auto_values, 25),
        }
    else:
        auto_percentiles = {"99": 0, "95": 0, "90": 0, "75": 0, "50": 0, "25": 0}

    if teleop_values:
        teleop_percentiles = {
            "99": np.percentile(teleop_values, 99),
            "95": np.percentile(teleop_values, 95),
            "90": np.percentile(teleop_values, 90),
            "75": np.percentile(teleop_values, 75),
            "50": np.percentile(teleop_values, 50),
            "25": np.percentile(teleop_values, 25),
        }
    else:
        teleop_percentiles = {"99": 0, "95": 0, "90": 0, "75": 0, "50": 0, "25": 0}

    if endgame_values:
        endgame_percentiles = {
            "99": np.percentile(endgame_values, 99),
            "95": np.percentile(endgame_values, 95),
            "90": np.percentile(endgame_values, 90),
            "75": np.percentile(endgame_values, 75),
            "50": np.percentile(endgame_values, 50),
            "25": np.percentile(endgame_values, 25),
        }
    else:
        endgame_percentiles = {"99": 0, "95": 0, "90": 0, "75": 0, "50": 0, "25": 0}

    # 3) Assign global ranks
    for idx, t in enumerate(teams_data):
        t["global_rank"] = idx + 1

    # 4) Build State dropdown options.
    if selected_country and selected_country in STATES:
        state_options = [{"label": "All States", "value": "All"}] + [
            {"label": s["label"], "value": s["value"]} for s in STATES[selected_country] if isinstance(s, dict)
        ]
    else:
        state_options = [{"label": "All States", "value": "All"}]

    # 5) Apply filters.
    if selected_country and selected_country != "All":
        teams_data = [
            t for t in teams_data
            if t.get("country", "").lower() == selected_country.lower()
        ]
    if selected_state and selected_state != "All":
        teams_data = [
            t for t in teams_data
            if t.get("state_prov", "").lower() == selected_state.lower()
        ]
    if search_query:
        q = search_query.lower()
        teams_data = [
            t for t in teams_data
            if (q in str(t.get("team_number", "")).lower())
               or (q in t.get("nickname", "").lower())
               or (q in t.get("city", "").lower())
        ]

    # 6) Prepare DataTable rows including EPA components with percentage emojis.
    table_rows = []
    for t in teams_data:
        rank = t.get("global_rank", "N/A")
        overall_epa = t.get("epa")
        auto_epa = t.get("auto_epa")
        teleop_epa = t.get("teleop_epa")
        endgame_epa = t.get("endgame_epa")

        overall_display = get_epa_display(overall_epa, overall_percentiles)
        auto_display = get_epa_display(auto_epa, auto_percentiles) if auto_epa is not None else "N/A"
        teleop_display = get_epa_display(teleop_epa, teleop_percentiles) if teleop_epa is not None else "N/A"
        endgame_display = get_epa_display(endgame_epa, endgame_percentiles) if endgame_epa is not None else "N/A"

        team_num = t.get("team_number", "")
        nickname = t.get("nickname", "Unknown")
        city = t.get("city", "Unknown")
        state = t.get("state_prov", "")
        country = t.get("country", "")
        location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

        if rank == 1:
            rank_str = "🥇"
        elif rank == 2:
            rank_str = "🥈"
        elif rank == 3:
            rank_str = "🥉"
        else:
            rank_str = rank

        table_rows.append({
            "epa_rank": rank_str,
            "team_display": f"[{team_num} | {nickname}](/team/{team_num}/{selected_year})",
            "epar": overall_display,
            "auto_epa": auto_display,
            "teleop_epa": teleop_display,
            "endgame_epa": endgame_display,
            "location_display": location_str,
        })

    # 7) Build top-3 “Featured Teams”
    top_3 = teams_data[:3]  # after filters
    featured_cards = []
    for top_team in top_3:
        t_num = top_team.get("team_number")
        if t_num is not None:
            avatar_url = get_team_avatar(t_num, selected_year)
            featured_cards.append(create_team_card(top_team, selected_year, avatar_url=avatar_url))
    top_teams_layout = dbc.Row([dbc.Col(card, width="auto") for card in featured_cards],
                               className="justify-content-center")

    return table_rows, state_options, top_teams_layout

def teams_map_layout():
    # Generate and get the map file path
    map_path = "assets/teams_map.html"

    return html.Div([
        topbar,
        dbc.Container(
            [
                html.Iframe(
                    src=f"/{map_path}",  # Reference the generated HTML file
                    style={"width": "100%", "height": "1050px", "border": "none"},
                ),
            ],
            fluid=True
        ),
        footer,
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
    ])

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

@app.callback(
    Output("url", "pathname"),
    [
        Input("btn-search-home", "n_clicks"),
        Input("input-team-home", "n_submit"),
        Input("input-year-home", "n_submit"),
        Input("desktop-search-button", "n_clicks"),
        Input("desktop-search-input", "n_submit"),
        Input("mobile-search-button", "n_clicks"),
        Input("mobile-search-input", "n_submit"),
    ],
    [
        State("input-team-home", "value"),
        State("input-year-home", "value"),
        State("desktop-search-input", "value"),
        State("mobile-search-input", "value"),
    ],
    prevent_initial_call=True,
)
def handle_navigation(
    home_click, home_submit, home_year_submit, desktop_click, desktop_submit, 
    mobile_click, mobile_submit, home_team_value, home_year_value, 
    desktop_search_value, mobile_search_value
):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Determine which input was triggered
    if trigger_id in ["btn-search-home", "input-team-home", "input-year-home"]:
        search_value = home_team_value
        year_value = home_year_value
    elif trigger_id in ["desktop-search-button", "desktop-search-input"]:
        search_value = desktop_search_value
        year_value = None
    elif trigger_id in ["mobile-search-button", "mobile-search-input"]:
        search_value = mobile_search_value
        year_value = None
    else:
        return dash.no_update

    if not search_value:
        return dash.no_update

    search_value = search_value.strip().lower()

    # Load team data
    folder_path = "team_data"
    selected_year = year_value if year_value else "2025"
    file_path = os.path.join(folder_path, f"teams_{selected_year}.json")

    if not os.path.exists(file_path):
        return "/"

    with open(file_path, "r") as f:
        teams_data = json.load(f)

    # Search for the team by number or name
    matching_team = next(
        (team for team in teams_data if 
         str(team.get("team_number", "")).lower() == search_value or 
         search_value in team.get("nickname", "").lower()), 
        None
    )

    if matching_team:
        team_number = matching_team.get("team_number", "")
        if year_value and year_value.isdigit():
            return f"/team/{team_number}/{year_value}"
        return f"/team/{team_number}"

    return "/"

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    path_parts = pathname.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "team":
        team_number = path_parts[1]
        year = path_parts[2] if len(path_parts) > 2 else None
        return team_layout(team_number, year)
    
    if pathname.startswith("/event/"):
        event_key = pathname.split("/")[-1]
        return event_layout(event_key)
    
    if pathname == "/teams":
        return teams_layout()
    
    if pathname == "/map":
        return teams_map_layout()
    
    if pathname == "/insights":
        return insights_layout()
    
    if pathname == "/events":
        return events_layout()
    
    if pathname == "/challenges":
        return challenges_layout()
    
    if pathname.startswith("/challenge/"):
        year = pathname.split("/")[-1]
        try:
            year = int(year)
        except ValueError:
            year = None
        return challenge_details_layout(year)

    return home_layout

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run_server(host="0.0.0.0", port=port, debug=False)
