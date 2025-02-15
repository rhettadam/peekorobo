import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px

import folium
from folium.plugins import MarkerCluster

import requests
import urllib.parse 
import os
from dotenv import load_dotenv
import json
import numpy as np

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
        {'name': 'viewport', 'content': 'width=device-width,initial-scale=1.0,'}
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
            # Left: Logo
            dbc.NavbarBrand(
                html.Img(
                    src="/assets/logo.png",
                    style={
                        "height": "40px",
                        "width": "auto",
                        "marginRight": "10px",
                    },
                ),
                href="/",
                className="navbar-brand-custom",
            ),
            # Toggler for Mobile
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            # Collapsible Section
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("Teams", href="/teams", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Map", href="/teamsmap", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Insights", href="/insights", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Challenges", href="/challenges", className="custom-navlink")),
                        # Resources Dropdown
                        dbc.DropdownMenu(
                            label="Resources",
                            nav=True,
                            in_navbar=True,
                            children=[
                                dbc.DropdownMenuItem("Communication", header=True),
                                dbc.DropdownMenuItem("Chief Delphi", href="https://www.chiefdelphi.com/", target="_blank"),
                                dbc.DropdownMenuItem("The Blue Alliance", href="https://www.thebluealliance.com/", target="_blank"),
                                dbc.DropdownMenuItem("FRC Subreddit", href="https://www.reddit.com/r/FRC/", target="_blank"),
                                dbc.DropdownMenuItem("FRC Discord", href="https://discord.com/invite/frc", target="_blank"),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem("Technical Resources", header=True),
                                dbc.DropdownMenuItem("FIRST Technical Resources", href="https://www.firstinspires.org/resource-library/frc/technical-resources", target="_blank"),
                                dbc.DropdownMenuItem("FRCDesign", href="https://www.frcdesign.org/learning-course/", target="_blank"),
                                dbc.DropdownMenuItem("OnShape4FRC", href="https://onshape4frc.com/", target="_blank"),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem("Scouting/Statistics", header=True),
                                dbc.DropdownMenuItem("Statbotics", href="https://www.statbotics.io/", target="_blank"),
                                dbc.DropdownMenuItem("ScoutRadioz", href="https://scoutradioz.com/", target="_blank"),
                                dbc.DropdownMenuItem("Peekorobo", href="https://peekorobo-6ec491b9fec0.herokuapp.com/", target="_blank"),
                            ],
                        ),
                        # Mobile Search Bar (inside collapsible menu)
                        dbc.InputGroup(
                            [
                                dbc.Input(
                                    id="mobile-search-input",
                                    placeholder="Team # (e.g., 1912)",
                                    type="text",
                                ),
                                dbc.Button(
                                    "Search",
                                    id="mobile-search-button",
                                    color="primary",
                                    style={
                                        "backgroundColor": "#FFDD00",
                                        "border": "none",
                                        "color": "black",
                                    },
                                ),
                            ],
                            className="mt-3",
                        ),
                    ],
                    navbar=True,
                ),
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.InputGroup(
                                [
                                    dbc.Input(
                                        id="desktop-search-input",
                                        placeholder="Team name or # (eg., 1912)",
                                        type="text",
                                    ),
                                    dbc.Button(
                                        "Search",
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
                                id="search-preview",
                                style={
                                    "backgroundColor": "white",  # Solid white background
                                    "border": "1px solid #ddd",  # Light gray border
                                    "borderRadius": "8px",  # Rounded corners
                                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",  # Subtle shadow for a floating effect
                                    "marginTop": "5px",
                                    "padding": "5px",
                                    "maxHeight": "200px",
                                    "overflowY": "auto",
                                    "overflowX": "hidden",
                                    "width": "100%",  # Matches width to input box
                                    "zIndex": "1050",  # Ensures it's above other elements
                                    "position": "absolute",
                                    "left": "0",  # Aligns with input
                                    "top": "100%",  # Positions below input
                                    "display": "none",  # Hidden by default
                                },
                            )

                        ],
                        width="auto",
                        className="desktop-search",
                        style={"position": "relative"},  # Needed for the preview dropdown
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

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@app.callback(
    [Output("search-preview", "children"), Output("search-preview", "style")],
    Input("desktop-search-input", "value"),
)
def update_search_preview(input_value):
    if not input_value:
        # Hide dropdown when input is empty
        return [], {"display": "none"}

    # Load team data from the 2024 JSON file
    folder_path = "team_data"  # Replace with the path where your JSON files are stored
    file_path = os.path.join(folder_path, "teams_2024.json")
    
    if not os.path.exists(file_path):
        return [html.Div("Data not found.", style={"color": "#555"})], {"display": "none"}

    with open(file_path, "r") as f:
        teams_data = json.load(f)

    input_value = input_value.lower()
    
    # Search for both team numbers and nicknames
    filtered_teams = [
        team for team in teams_data 
        if input_value in str(team.get("team_number", "")).lower()
        or input_value in team.get("nickname", "").lower()
    ][:20]  # Limit results to the top 20

    # Find closest numeric match if input is a number
    closest_team_number = None
    closest_team_nickname = None

    if input_value.isdigit():
        input_number = int(input_value)
        closest_team_number = min(
            filtered_teams,
            key=lambda team: abs(input_number - int(team["team_number"])),
            default=None,
        )
    else:
        # Find the closest nickname match using a simple string similarity comparison
        closest_team_nickname = min(
            filtered_teams,
            key=lambda team: len(set(input_value) & set(team["nickname"].lower())),
            default=None,
        )

    # Generate dropdown content
    children = []
    for team in filtered_teams:
        team_number = team.get("team_number", "Unknown")
        team_nickname = team.get("nickname", "Unknown")

        # Highlight the closest matching team number or nickname
        background_color = "white"
        if (closest_team_number and team_number == closest_team_number["team_number"]) or \
           (closest_team_nickname and team_nickname == closest_team_nickname["nickname"]):
            background_color = "#FFDD00"  # Yellow highlight

        children.append(
            dbc.Row(
                [
                    dbc.Col(
                        html.A(
                            f"{team_number} | {team_nickname}",
                            href=f"/data?team={team_number}",
                            style={
                                "lineHeight": "20px",
                                "textDecoration": "none",
                                "color": "black",
                                "cursor": "pointer",
                            },
                        ),
                        width=True,
                    ),
                ],
                style={"padding": "5px", "backgroundColor": background_color},
                key=f"team-{team_number}",
            )
        )

    # Show dropdown with results
    return children, {
        "display": "block",
        "backgroundColor": "white",
        "border": "1px solid #ddd",
        "borderRadius": "8px",
        "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
        "marginTop": "5px",
        "marginLeft": "10px",
        "padding": "5px",
        "maxHeight": "200px",
        "overflowY": "auto",
        "overflowX": "hidden",
        "width": "93%",
        "zIndex": "1050",
        "position": "absolute",
        "left": "0",
        "top": "100%",
    }

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
                                                placeholder="Team # (e.g., 1912)",
                                                className="custom-input-box",
                                                style={"width": "100%", "marginBottom": ".4rem"}
                                            ),
                                            width=12
                                        ),
                                        dbc.Col(
                                            dbc.Input(
                                                id="input-year-home",
                                                type="text",
                                                placeholder="Year (e.g., 2024) optional",
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
    file_path = os.path.join(folder_path, f"teams_{year or 2024}.json")
    if not os.path.exists(file_path):
        return dbc.Alert(f"Data for year {year or 2024} not found.", color="danger")

    with open(file_path, "r") as f:
        team_data = json.load(f)

    # Find the selected team
    selected_team = next((team for team in team_data if team["team_number"] == int(team_number)), None)
    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data.", color="danger")

    # Calculate Rankings
    global_rank, country_rank, state_rank = calculate_ranks(team_data, selected_team)

    # Fetch Basic Team Info
    team_info = tba_get(f"team/{team_key}")
    if not team_info:
        return dbc.Alert(
            f"Error: Could not fetch info for team {team_number}. "
            "Double-check your input or TBA key.",
            color="danger"
        )

    epa_value = selected_team.get("epa", None)
    epa_display = f"{epa_value:.2f}" if epa_value is not None else "N/A"


    nickname = selected_team.get("nickname", "Unknown")
    city = selected_team.get("city", "")
    state = selected_team.get("state_prov", "")
    country = selected_team.get("country", "")
    website = team_info.get("website", "N/A")
    
    avatar_data = tba_get(f"team/{team_key}/media/2024")
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
            str(year),
            href=f"/data?team={team_number}&year={year}",
            style={
                "marginRight": "0px",
                "color": "#007BFF",
                "textDecoration": "none",
            },
        )
        for year in years_participated
    ] if years_participated else ["N/A"]

        # Add "ALL" button linking to team profile without year
    years_links.append(
        html.A(
            "History",
            href=f"/data?team={team_number}",  # No year specified
            style={
                "marginLeft": "0px",
                "color": "#007BFF",  # Orange to differentiate it
                "fontWeight": "bold",
                "textDecoration": "none",
            },
        )
    )

    rookie_year = years_participated[0]

    hof = [2486, 321, 1629, 503, 4613, 1816, 1902, 1311, 2834, 2614, 3132, 987, 597, 27, 1538, 1114, 359, 341, 236, 842, 365, 111, 67, 254, 103, 175, 22, 16, 120, 23, 47, 51, 144, 151, 191, 7]
                
        # Check if the team is in the Hall of Fame
    is_hof_team = int(team_number) in hof
    
    hof_badge = (
        html.Div(
            [
                html.Span("🏆", style={"fontSize": "1.5rem"}),
                html.Span(" Hall of Fame", style={"color": "gold", "fontSize": "1.2rem", "fontWeight": "bold", "marginLeft": "5px"})
            ],
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}  # Adds spacing below
        )
        if is_hof_team else None
    )
    
    # Team Info Card
    team_card = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        # Left Column: Team Info
                        dbc.Col(
                            [
                                html.H2(f"Team {team_number}: {nickname}", style={"color": "#333", "fontWeight": "bold"}),
                                hof_badge if is_hof_team else None,  # Hall of Fame badge here
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
                                            style={
                                                "display": "flex",
                                                "flexWrap": "wrap",  
                                                "gap": "8px",      
                                            },
                                        ),
                                    ],
                                    style={"marginBottom": "10px"},
                                ),
                            ],
                            width=9,  
                        ),
                        # Right Column: Avatar
                        dbc.Col(
                            [
                                html.Img(
                                    src=avatar_url,
                                    alt=f"Team {team_number} Avatar",
                                    style={
                                        "width": "150px",  
                                        "height": "150px", 
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
                        ),
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
    if year:
        matches = tba_get(f"team/{team_key}/matches/{year}")
    else:
        matches = tba_get(f"team/{team_key}/matches/2024")

    total_matches = len(matches) if matches else 0
    wins = sum(
        1
        for match in matches
        if match["winning_alliance"] == "red" and team_key in match["alliances"]["red"]["team_keys"]
        or match["winning_alliance"] == "blue" and team_key in match["alliances"]["blue"]["team_keys"]
    ) if matches else 0
    losses = total_matches - wins
    win_loss_ratio = f"{wins}/{losses}" if total_matches > 0 else "N/A"

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

    if year:
        perf = html.H5(
                    f"{year} Performance Metrics",
                    style={
                        "textAlign": "center",
                        "color": "#444",
                        "fontSize": "1.3rem",
                        "fontWeight": "bold",
                        "marginBottom": "10px",
                    },
                )
    else:
        perf = html.H5(
                    "2024 Performance Metrics",
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
                # Title
                perf,
                # Ranks and EPA
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{country} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(
                                            f"{country_rank}",
                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                                "color": "#FFC107",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Global Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(
                                            f"{global_rank}",
                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                                "color": "#007BFF",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{state} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.1rem"}),
                                        html.P(
                                            f"{state_rank}",
                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                                "color": "#FFC107",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                        style={"marginBottom": "10px"},
                    ),
                ),
                # Match Performance
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(
                                            epa_display,

                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                                "color": "#17A2B8",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Win/Loss Ratio", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(
                                            win_loss_ratio,
                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Avg Match Score", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(
                                            f"{avg_score:.2f}",
                                            style={
                                                "fontSize": "1.1rem",
                                                "fontWeight": "bold",
                                                "color": "#17A2B8",
                                            },
                                        ),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                    ),
                ),
            ],
        ),
        style={
            "marginBottom": "15px",
            "borderRadius": "8px",
            "boxShadow": "0px 2px 4px rgba(0,0,0,0.1)",
            "backgroundColor": "#f9f9f9",
            "padding": "10px",
        },
    )
        
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
        event_url = f"https://www.thebluealliance.com/event/{event_key}"
        location = f"{ev.get('city', '')}, {ev.get('state_prov', '')}"
        start_date = ev.get("start_date", "")
        end_date = ev.get("end_date", "")
        
        event_name_with_rank = event_name

        if year:
            rankings = tba_get(f"event/{event_key}/rankings")
            rank = None
            if rankings and "rankings" in rankings:
                for entry in rankings["rankings"]:
                    if entry["team_key"] == team_key:
                        rank = entry["rank"]
                    avg_rank = sum(r["rank"] for r in rankings["rankings"]) / len(rankings["rankings"])

            if rank:
                event_name = f"{event_name} (Rank: {rank})"

        events_data.append({
            "event_name": f"[{event_name}]({event_url})",
            "event_location": location,
            "start_date": start_date,
            "end_date": end_date,
        })

    # DataTable for Events
    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name", "presentation": "markdown"},
            {"name": "Location", "id": "event_location"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        data=events_data,
        page_size=5,
        style_table={"overflowX": "auto",
                    "borderRadius": "10px",
                    "border": "1px solid #ddd"},
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
        },
        style_cell_conditional=[
            {"if": {"column_id": "event_name"}, "textAlign": "center"}
        ],
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "1px solid #FFCC00",
            },
        ],
    )

    
    # --- Team Awards ---
    if year:
        awards = tba_get(f"team/{team_key}/awards/{year}")
    else:
        awards = sorted(
            tba_get(f"team/{team_key}/awards") or [],
            key=lambda aw: aw.get("year", 0),
            reverse=True
        )
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
        style_table={"overflowX": "auto",
                    "borderRadius": "10px",
                    "border": "1px solid #ddd"},
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
        },
        style_cell_conditional=[
            {"if": {"column_id": "award_name"}, "textAlign": "left"}
        ],
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "1px solid #FFCC00",
            },
        ],
    )
    
    blue_banner_awards = ["Chairman's", "Impact", "Woodie Flowers", "Winner"]
    blue_banners = []
    if awards:
        for award in awards:
            award_name = award.get("name", "")
            event_key = award.get
            event_name = event_key_to_name.get(award.get("event_key"), "Unknown Event")
    
            # Check if this award is a "blue banner" award
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
                                                style={
                                                    "fontSize": "0.8rem",
                                                    "color": "white",
                                                    "fontWeight": "bold",
                                                    "textAlign": "center",
                                                    "marginBottom": "3px",
                                                },
                                            ),
                                            html.P(
                                                banner.get("event_name", "Unknown Event"),
                                                style={
                                                    "fontSize": "0.6rem",
                                                    "color": "white",
                                                    "textAlign": "center",
                                                },
                                            ),
                                        ],
                                        style={
                                            "position": "absolute",
                                            "top": "50%",
                                            "left": "50%",
                                            "transform": "translate(-50%, -50%)",
                                        },
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
    


    # Final Layout
    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    team_card,
                    performance_card,
                    html.H3("Team Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Team Awards", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    awards_table,
                    blue_banner_section,
                    html.Br(),
                    dbc.Button(
                        "Go Back",
                        id="btn-go-back",
                        color="secondary",
                        href="/",
                        external_link=True,
                        style={"borderRadius": "5px", "padding": "10px 20px", "marginTop": "20px"},
                    ),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}),
            
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer
        ]
    )

def clean_category_label(raw_label):
    label = raw_label.replace("typed_", "").replace("_", " ").replace("insights","").title()
    return label

def insights_layout(year=2024, category="typed_leaderboard_blue_banners", notable_category="notables_division_finals_appearances"):
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
    else:
        print("Notable Categories:", notable_categories)


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
    else:
        print("Notable Entries:", notable_entries)

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
                        options=[{"label": f"{year}", "value": year} for year in range(2000, 2025)],
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
        year = 2024
    
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
            team_link = f"[{team_number}](/data?team={team_number}&year={year})"

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
    # Dropdowns
    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": f"{yr}", "value": yr} for yr in range(2000, 2026)],
        value=year,
        placeholder="Year",
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
        options=[
            {"label": "All", "value": "all"}
        ] + [{"label": f"Week {i+1}", "value": i} for i in range(0, 9)],
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
            dbc.Col(year_dropdown, xs=3, sm=4, md=2),
            dbc.Col(event_type_dropdown, xs=3, sm=3, md=2),
            dbc.Col(week_dropdown, xs=3, sm=4, md=2),
            dbc.Col(search_input, xs=3, sm=4, md=2),
        ],
        className="mb-4",
        style={"display": "flex", "justifyContent": "center", "gap": "10px"},
    )

    # Events Table
    events_table = dash_table.DataTable(
        id="events-table",
        columns=[
            {"name": "Event Name", "id": "Event Name", "presentation": "markdown"},
            {"name": "Location", "id": "Location"},
            {"name": "Start Date", "id": "Start Date"},
            {"name": "End Date", "id": "End Date"},
            {"name": "Event Type", "id": "Event Type"},
        ],
        data=[],  # will be updated by callback
        page_size=10,
        style_table={"overflowX": "auto",
                    "borderRadius": "10px",
                    "border": "1px solid #ddd"},
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
        },
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "1px solid #FFCC00",
            },
        ],
    )

    events_map_graph = dcc.Graph(
        id="events-map",
        figure={},    
        style={"height": "700px"}  
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H2("Events", className="text-center mb-4"),
                    filters_row,
                    events_table,
                    events_map_graph,  
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
            dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
            footer,
        ]
    )

@app.callback(
    [
        Output("events-table", "data"),
        Output("events-map", "figure")
    ],
    [
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("week-dropdown", "value"),
        Input("search-input", "value"),
    ],
)
def update_events_table_and_map(selected_year, selected_event_types, selected_week, search_query):
    # --- 1. Fetch & Filter Event Data for Table ---
    events_data = tba_get(f"events/{selected_year}")
    if not events_data:
        return [], {}

    # Ensure selected_event_types is list
    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    # Filter by Event Type
    if "all" not in selected_event_types:
        filtered_events = []
        for et in selected_event_types:
            if et == "season":
                # Exclude off-season type=99 or 100
                filtered_events.extend([ev for ev in events_data if ev["event_type"] not in [99, 100]])
            elif et == "offseason":
                filtered_events.extend([ev for ev in events_data if ev["event_type"] in [99, 100]])
            elif et == "regional":
                filtered_events.extend([ev for ev in events_data if "Regional" in ev.get("event_type_string", "")])
            elif et == "district":
                filtered_events.extend([ev for ev in events_data if "District" in ev.get("event_type_string", "")])
            elif et == "championship":
                filtered_events.extend([ev for ev in events_data if "Championship" in ev.get("event_type_string", "")])
        events_data = filtered_events

    # Remove duplicates if multiple filters
    events_data = list({ev["key"]: ev for ev in events_data}.values())

    # Filter by Week
    if selected_week != "all":
        events_data = [ev for ev in events_data if ev.get("week") == selected_week]

    # Filter by Search
    if search_query:
        search_query = search_query.lower()
        events_data = [
            ev for ev in events_data
            if search_query in ev["name"].lower() or search_query in ev["city"].lower()
        ]

    # --- 2. Prepare Table Data ---
    formatted_events = [
        {
            "Event Name": f"[{ev['name']}]({'https://www.thebluealliance.com/event/' + ev['key']})",
            "Location": f"{ev['city']}, {ev['state_prov']}, {ev['country']}",
            "Start Date": ev["start_date"],
            "End Date": ev["end_date"],
            "Event Type": ev["event_type_string"],
        }
        for ev in events_data
    ]

    map_events = [ev for ev in events_data if ev.get("lat") is not None and ev.get("lng") is not None]

    fig = {}
    if map_events:
        fig = px.scatter_geo(
            map_events,
            lat="lat",
            lon="lng",
            hover_name="name",
            hover_data=["city", "start_date", "end_date"],
            projection="natural earth",
        )
        fig.update_traces(
            marker=dict(
                symbol='circle',
                color="yellow",
                size=10,                 # optional size
                line=dict(width=1)  # optional border
            )
        )
        fig.update_geos(
            showcountries=True,
            countrycolor="gray",
            showsubunits=True,
            subunitcolor="gray",
            showland=True,
            landcolor="lightgreen",
            showocean=True,
            oceancolor="lightblue",
        )
        fig.update_layout(
            margin={"r": 0, "t": 30, "l": 0, "b": 0},
        )

    return formatted_events, fig

def event_layout(event_key):
    # Fetch event details
    event_details = tba_get(f"event/{event_key}")
    if not event_details:
        return dbc.Alert("Event details could not be fetched.", color="danger")

    # Fetch additional data endpoints
    rankings = tba_get(f"event/{event_key}/rankings") or {"rankings": []}
    oprs = tba_get(f"event/{event_key}/oprs") or {"oprs": {}}
    coprs = tba_get(f"event/{event_key}/coprs") or {"coprs": {}}
    insights = tba_get(f"event/{event_key}/insights") or {}

    # Event information
    event_name = event_details.get("name", "Unknown Event")
    event_location = f"{event_details.get('city', '')}, {event_details.get('state_prov', '')}, {event_details.get('country', '')}"
    start_date = event_details.get("start_date", "N/A")
    end_date = event_details.get("end_date", "N/A")
    event_type = event_details.get("event_type_string", "N/A")
    website = event_details.get("website", "#")

    # Layout for event details
    header_layout = html.Div(
        [
            html.H2(event_name, className="text-center mb-4"),
            html.P(f"Location: {event_location}", className="text-center"),
            html.P(f"Dates: {start_date} - {end_date}", className="text-center"),
            html.P(f"Type: {event_type}", className="text-center"),
            html.A("Visit Event Website", href=website, target="_blank", className="d-block text-center mb-4"),
        ]
    )

    # Dropdown to select data
    dropdown = dbc.DropdownMenu(
        label="Select Data to Display",
        children=[
            dbc.DropdownMenuItem("Rankings", id="dropdown-rankings"),
            dbc.DropdownMenuItem("OPRs", id="dropdown-oprs"),
            dbc.DropdownMenuItem("COPRs", id="dropdown-coprs"),
            dbc.DropdownMenuItem("Insights", id="dropdown-insights"),
        ],
        color="primary",
        className="mb-4",
    )

    # Data containers
    rankings_table = dash_table.DataTable(
        id="rankings-table",
        columns=[
            {"name": "Rank", "id": "Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins"},
            {"name": "Losses", "id": "Losses"},
            {"name": "Ties", "id": "Ties"},
            {"name": "DQ", "id": "DQ"},
        ],
        data=[
            {
                "Rank": rank.get("rank", "N/A"),
                "Team": f"[{rank.get('team_key', 'N/A').replace('frc', '')}](/data?team={rank.get('team_key', '').replace('frc', '')})",
                "Wins": rank.get("record", {}).get("wins", "N/A"),
                "Losses": rank.get("record", {}).get("losses", "N/A"),
                "Ties": rank.get("record", {}).get("ties", "N/A"),
                "DQ": rank.get("dq", "N/A"),
            }
            for rank in (rankings.get("rankings", []) if rankings else [])
        ],
        page_size=10,
    )

    oprs_table = dash_table.DataTable(
        id="oprs-table",
        columns=[
            {"name": "Team", "id": "Team"},
            {"name": "OPR", "id": "OPR"},
        ],
        data=[
            {"Team": team.replace("frc", ""), "OPR": value}
            for team, value in (oprs.get("oprs", {}) if oprs else {}).items()
        ],
        page_size=10,
    )

    coprs_table = dash_table.DataTable(
        id="coprs-table",
        columns=[
            {"name": "Team", "id": "Team"},
            {"name": "COPR", "id": "COPR"},
        ],
        data=[
            {"Team": team.replace("frc", ""), "COPR": value}
            for team, value in (coprs.get("coprs", {}) if coprs else {}).items()
        ],
        page_size=10,
    )

    insights_table = dash_table.DataTable(
        id="insights-table",
        columns=[
            {"name": "Metric", "id": "Metric"},
            {"name": "Value", "id": "Value"},
        ],
        data=[
            {"Metric": metric.replace("_", " ").title(), "Value": value}
            for metric, value in (insights.items() if insights else {})
        ],
        page_size=5,
    )

    # Layout with Dropdown and dynamic table
    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    header_layout,
                    dropdown,
                    html.Div(id="data-display-container", children=[rankings_table]),  # Default to rankings
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

# Callback to update the displayed table based on the dropdown selection
@app.callback(
    Output("data-display-container", "children"),
    [Input("dropdown-rankings", "n_clicks"),
     Input("dropdown-oprs", "n_clicks"),
     Input("dropdown-coprs", "n_clicks"),
     Input("dropdown-insights", "n_clicks")],
)
def update_display(show_rankings, show_oprs, show_coprs, show_insights):
    ctx = dash.callback_context
    if not ctx.triggered:
        return 

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "dropdown-rankings":
        return rankings_table
    elif button_id == "dropdown-oprs":
        return oprs_table
    elif button_id == "dropdown-coprs":
        return coprs_table
    elif button_id == "dropdown-insights":
        return insights_table

    return rankings_table  # Fallback

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

def teams_layout(default_year=2024):
    teams_year_dropdown = dcc.Dropdown(
        id="teams-year-dropdown",
        options=[{"label": str(y), "value": y} for y in range(1992, 2026)],
        value=default_year,
        clearable=False,
        placeholder="Select Year",
    )

    country_dropdown = dcc.Dropdown(
        id="country-dropdown",
        options=COUNTRIES,
        value="All",
        clearable=False,
        placeholder="Select Country",
    )

    # Initialize state dropdown with properly formatted options
    state_dropdown = dcc.Dropdown(
        id="state-dropdown",
        options=[{"label": "All States", "value": "All"}] + [
            {"label": state["label"], "value": state["value"]}
            for state in STATES.get("USA", []) if isinstance(state, dict)
        ],
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

    teams_table = dash_table.DataTable(
        id="teams-table",
        columns=[
            {"name": "EPA Rank", "id": "epa_rank"},
            {"name": "EPA", "id": "epar", "presentation": "markdown"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "Location", "id": "location_display"}
        ],
        data=[],
        page_size=50,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"},
        style_cell={"textAlign": "center", "padding": "10px", "border": "1px solid #ddd", "fontSize": "14px"},
        style_data_conditional=[{
            "if": {"state": "selected"},
            "backgroundColor": "rgba(255, 221, 0, 0.5)",
            "border": "1px solid #FFCC00",
        }],
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H2("Teams", className="text-center mb-4"),
                    dbc.Row(
                        [
                            dbc.Col(teams_year_dropdown, xs=3, sm=4, md=2),  # Adjust widths for mobile
                            dbc.Col(country_dropdown, xs=3, sm=6, md=3),
                            dbc.Col(state_dropdown, xs=3, sm=4, md=3),
                            dbc.Col(search_input, xs=3, sm=6, md=4),  # Full-width on mobile
                        ],
                        className="mb-4 justify-content-center",
                    ),
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

@app.callback(
    [
        Output("teams-table", "data"),
        Output("state-dropdown", "options"),  # Dynamically update states based on selected country
    ],
    [
        Input("teams-year-dropdown", "value"),
        Input("country-dropdown", "value"),
        Input("state-dropdown", "value"),
        Input("search-bar", "value"),
    ],
)
def load_teams(selected_year, selected_country, selected_state, search_query):
    folder_path = "team_data"  # Update this path if necessary
    teams_data = []

    # Load team data for the selected year
    file_path = os.path.join(folder_path, f"teams_{selected_year}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            teams_data = json.load(f)
    else:
        return [], [{"label": "All States", "value": "All"}]  # Return empty if no data for the selected year

    # Ensure EPA values exist and sort teams by EPA descending
    teams_data = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)

    # Compute EPA percentiles for ranking
    epa_values = [team["epa"] for team in teams_data if team.get("epa") is not None]
    percentiles = {
        "99": np.percentile(epa_values, 99) if epa_values else 0,
        "90": np.percentile(epa_values, 90) if epa_values else 0,
        "75": np.percentile(epa_values, 75) if epa_values else 0,
        "25": np.percentile(epa_values, 25) if epa_values else 0,
    }

    # Assign global ranks
    for idx, team in enumerate(teams_data):
        team["global_rank"] = idx + 1

    # **Fix state options (remove nested dicts)**
    if selected_country and selected_country in STATES:
        state_options = [{"label": "All States", "value": "All"}] + [
            {"label": state["label"], "value": state["value"]}
            for state in STATES[selected_country] if isinstance(state, dict)
        ]
    else:
        state_options = [{"label": "All States", "value": "All"}]

    # Apply filters
    if selected_country and selected_country != "All":
        teams_data = [team for team in teams_data if team.get("country", "").lower() == selected_country.lower()]

    if selected_state and selected_state != "All":
        teams_data = [team for team in teams_data if team.get("state_prov", "").lower() == selected_state.lower()]

    # Apply search query (matches team number, nickname, and city)
    if search_query:
        search_query = search_query.lower()
        teams_data = [
            team for team in teams_data
            if search_query in str(team.get("team_number", "")).lower()
            or search_query in team.get("nickname", "").lower()
            or search_query in team.get("city", "").lower()
        ]

    # Generate table data
    table_data = []
    for team in teams_data:
        team_number = team.get("team_number", "")
        nickname = team.get("nickname", "Unknown")
        city = team.get("city", "Unknown")
        state = team.get("state_prov", "")
        country = team.get("country", "")
        epa = team.get("epa", None)
        global_rank = team.get("global_rank", "N/A")

        team_display = f"[{team_number} | {nickname}](/data?team={team_number}&year={selected_year})"
        location_display = ", ".join(filter(None, [city, state, country]))
        epa_display = get_epa_display(epa, percentiles)

        table_data.append(
            {
                "epa_rank": f"🥇" if global_rank == 1 else f"🥈" if global_rank == 2 else f"🥉" if global_rank == 3 else global_rank,
                "epar": epa_display,
                "team_display": team_display,
                "location_display": location_display or "Unknown",
            }
        )

    return table_data, state_options  # Returning both table data and state dropdown options

def teams_map_layout():
    # Generate and get the map file path
    map_path = "assets/teams_map.html"

    return html.Div([
        topbar,
        dbc.Container(
            [
                html.Iframe(
                    src=f"/{map_path}",  # Reference the generated HTML file
                    style={"width": "100%", "height": "840px", "border": "none"},
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
    [Output("url", "pathname"), Output("url", "search")],
    [
        Input("btn-search-home", "n_clicks"),
        Input("input-team-home", "n_submit"),
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
    home_click, home_submit, desktop_click, desktop_submit, 
    mobile_click, mobile_submit, home_team_value, home_year_value, 
    desktop_search_value, mobile_search_value
):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Get input value from the triggered element
    if trigger_id in ["btn-search-home", "input-team-home"]:
        search_value = home_team_value
        year_value = home_year_value
    elif trigger_id in ["desktop-search-button", "desktop-search-input"]:
        search_value = desktop_search_value
        year_value = None
    elif trigger_id in ["mobile-search-button", "mobile-search-input"]:
        search_value = mobile_search_value
        year_value = None
    else:
        return dash.no_update, dash.no_update

    if not search_value:
        return dash.no_update, dash.no_update

    search_value = search_value.strip().lower()

    # Load the team data
    folder_path = "team_data"
    selected_year = year_value if year_value else "2024"
    file_path = os.path.join(folder_path, f"teams_{selected_year}.json")

    if not os.path.exists(file_path):
        return "/", ""  # Redirect to home if no data

    with open(file_path, "r") as f:
        teams_data = json.load(f)

    # Search by number or name
    matching_team = next(
        (team for team in teams_data if 
         str(team.get("team_number", "")).lower() == search_value or 
         search_value in team.get("nickname", "").lower()), 
        None
    )

    if matching_team:
        team_number = matching_team.get("team_number", "")
        query_params = {"team": team_number}
        if year_value and year_value.isdigit():
            query_params["year"] = year_value
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    return "/", ""  # Redirect to home if no match

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("url", "search")
)
def display_page(pathname, search):
    if pathname == "/data":
        query_params = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
        team_number = query_params.get("team", [None])[0]
        year = query_params.get("year", [None])[0]
        return team_layout(team_number, year)
    elif pathname.startswith("/event/"):
        event_key = pathname.split("/")[-1]  # Extract event_key from URL
        return event_layout(event_key)
    elif pathname == "/teams":
        return teams_layout()
    elif pathname == "/teamsmap":
        return teams_map_layout()  
    elif pathname == "/insights":
        return insights_layout()
    elif pathname == "/events":
        return events_layout()
    elif pathname == "/challenges":
        return challenges_layout()
    elif pathname.startswith("/challenge/"):
        year = pathname.split("/")[-1]
        try:
            year = int(year)
        except ValueError:
            year = None
        return challenge_details_layout(year)
    else:
        return home_layout
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run_server(host="0.0.0.0", port=port, debug=False)
