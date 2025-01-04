import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import requests
import urllib.parse 
import os
from dotenv import load_dotenv
import plotly.express as px
import json

from frcgames import frc_games

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
                        dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Leaderboard", href="/leaderboard", className="custom-navlink")),
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
                                        placeholder="Team # (e.g., 1912)",
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
                                    "width": "calc(100% - 20px)",  # Matches width to input box
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

    teams_data = tba_get("teams/all")  # Fetch all teams
    if not teams_data:
        # If no teams data is available, show no results
        return [html.Div("No results found.", style={"color": "#555"})], {"display": "none"}

    # Filter teams based on input and limit to top 10 results
    filtered_teams = [
        team for team in teams_data if str(input_value).lower() in str(team.get("team_number", "")).lower()
    ][:10]

    # Generate dropdown content
    children = []
    for team in filtered_teams:
        team_key = team.get("key")
        team_number = team.get("team_number", "Unknown")
        team_nickname = team.get("nickname", "Unknown")

        children.append(
            dbc.Row(
                [
                    dbc.Col(
                        html.A(
                            f"{team_number} - {team_nickname}",
                            href=f"/data?team={team_number}",
                            style={
                                "lineHeight": "40px",
                                "textDecoration": "none",
                                "color": "black",
                                "cursor": "pointer",
                            },
                        ),
                        width=True,
                    ),
                ],
                style={"padding": "5px", "borderBottom": "1px solid #ddd"},
                key=team_key,
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
        "padding": "5px",
        "maxHeight": "200px",
        "overflowY": "auto",
        "overflowX": "hidden",
        "width": "calc(100% - 20px)",
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
                    "margin": "2px"
                }
            ),
        ])
    ]),
    fluid=True,
    style={
        "backgroundColor": "white",  
        "padding": "10px 0px",
        "boxShadow": "0px -1px 2px rgba(0, 0, 0, 0.1)", 
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
                                        "width": "35%",
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
    rookie_year = team_info.get("rookie_year", "N/A")
    
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
                                html.P([html.I(className="bi bi-geo-alt-fill"), f" Location: {city}, {state}, {country}"]),
                                html.P([html.I(className="bi bi-link-45deg"), " Website: ", 
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
                                        html.P("EPA", style={"color": "#666", "marginBottom": "2px", "fontSize": "0.9rem"}),
                                        html.P(
                                            epa_display,

                                            style={
                                                "fontSize": "1rem",
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
                                        html.P("Win/Loss Ratio", style={"color": "#666", "marginBottom": "2px", "fontSize": "0.9rem"}),
                                        html.P(
                                            win_loss_ratio,
                                            style={
                                                "fontSize": "1rem",
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
                                        html.P("Avg Match Score", style={"color": "#666", "marginBottom": "2px", "fontSize": "0.9rem"}),
                                        html.P(
                                            f"{avg_score:.2f}",
                                            style={
                                                "fontSize": "1rem",
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
            {"if": {"column_id": "event_name"}, "textAlign": "left"}
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
            dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
            dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
            
            footer
        ]
    )

def clean_category_label(raw_label):
    label = raw_label.replace("typed_", "").replace("_", " ").replace("leaderboard","").title()
    return label

def leaderboard_layout(year=2024, category="typed_leaderboard_blue_banners"):
    
    # Fetch leaderboard data
    leaderboard_data = tba_get(f"insights/leaderboards/{year}")
    if not leaderboard_data:
        return html.Div("Error fetching leaderboard data.")

    # Extract leaderboard categories and clean labels
    leaderboard_categories = [
        {"label": clean_category_label(item["name"]), "value": item["name"]}
        for item in leaderboard_data
    ]

    # Default to the first category if not provided
    if category not in [item["value"] for item in leaderboard_categories]:
        category = leaderboard_categories[0]["value"]

    # Filter data for the selected category
    leaderboard_table_data = []
    for item in leaderboard_data:
        if item["name"] == category:
            rankings = item.get("data", {}).get("rankings", [])
            for rank in rankings:
                for team_key in rank.get("keys", []):
                    team_number = team_key.replace("frc", "")
                    leaderboard_table_data.append({
                        "Team": team_number,
                        "Value": rank.get("value", 0),
                    })

    # Sort data by value 
    leaderboard_table_data = sorted(leaderboard_table_data, key=lambda x: x["Value"], reverse=True)

    # Create a DataTable
    leaderboard_table = dash_table.DataTable(
        id="leaderboard-table",
        columns=[
            {"name": "Team", "id": "Team", "presentation": "markdown"}, 
            {"name": "Value", "id": "Value"},
            {"name": "Rank", "id": "Rank"},
        ],
        data=leaderboard_table_data,
        sort_action="native",
        style_table={"overflowX": "auto",
                    "borderRadius": "10px",
                    "border": "1px solid #ddd"},
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "fontFamily": "Arial, sans-serif",
            "fontSize": "14px",
        },
        style_header={
            "backgroundColor": "#FFCC00",
            "color": "#333",
            "fontWeight": "bold",
            "border": "1px solid #ddd",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": '{Rank} contains "🥇"'},
                "fontWeight": "bold",
            },
            {
                "if": {"filter_query": '{Rank} contains "🥈"'},
                "fontWeight": "bold",
            },
            {
                "if": {"filter_query": '{Rank} contains "🥉"'},
                "fontWeight": "bold",
            },
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "1px solid #FFCC00",
            },
        ],
    )

    return html.Div([
        topbar,
        dbc.Container(
            [
                html.H2("Leaderboard", className="text-center mb-4"),
                dbc.Row([
                    dbc.Col(dcc.Dropdown(
                        id="year-selector",
                        options=[
                            {"label": f"{year}", "value": year} for year in range(2000, 2025)
                        ],
                        value=year,
                        placeholder="Select Year",
                        className="mb-4"
                    ), width=6),
                    dbc.Col(dcc.Dropdown(
                        id="category-selector",
                        options=leaderboard_categories,
                        value=category,
                        placeholder="Select Category",
                        className="mb-4"
                    ), width=6),
                ]),
                leaderboard_table,
            ]),
        
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
        dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
        
        footer
    ])
@app.callback(
    Output("leaderboard-table", "data"),
    Input("year-selector", "value"),
    Input("category-selector", "value"),
)
def update_leaderboard(year, category):
    if not year:
        year = 2024
    leaderboard_data = tba_get(f"insights/leaderboards/{year}")
    if not leaderboard_data:
        return []

    leaderboard_table_data = []
    rankings = []
    for item in leaderboard_data:
        if item["name"] == category:
            rankings = item.get("data", {}).get("rankings", [])
            break

    # Sort rankings by value & compute ranks
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
            if current_rank == 1:
                rank_display = "🥇 1"
            elif current_rank == 2:
                rank_display = "🥈 2"
            elif current_rank == 3:
                rank_display = "🥉 3"
            else:
                rank_display = f"{current_rank}"

            leaderboard_table_data.append({
                "Team": team_link,
                "Value": rank.get("value", 0),
                "Rank": rank_display,
            })

    return leaderboard_table_data

def events_layout(year=2025):
    # Dropdowns
    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": f"{yr}", "value": yr} for yr in range(2000, 2026)],
        value=year,
        placeholder="Select a year",
    )
    event_type_dropdown = dcc.Dropdown(
        id="event-type-dropdown",
        options=[
            {"label": "All", "value": "all"},
            {"label": "Season Events", "value": "season"},
            {"label": "Off-season Events", "value": "offseason"},
            {"label": "Regional Events", "value": "regional"},
            {"label": "District Events", "value": "district"},
            {"label": "Championship Events", "value": "championship"},
        ],
        value=["all"],
        multi=True,
        placeholder="Filter by Event Type",
    )
    week_dropdown = dcc.Dropdown(
        id="week-dropdown",
        options=[
            {"label": "All Weeks", "value": "all"}
        ] + [{"label": f"Week {i}", "value": i} for i in range(0, 9)],
        value="all",
        placeholder="Select Week",
        clearable=False,
    )
    sort_dropdown = dcc.Dropdown(
        id="sort-dropdown",
        options=[
            {"label": "Date (New -> Old)", "value": "newdate"},
            {"label": "Date (Old -> New)", "value": "olddate"},
            {"label": "Name", "value": "name"},
        ],
        placeholder="Sort by",
    )
    search_input = dbc.Input(
        id="search-input",
        placeholder="Search by Name...",
        type="text",
        debounce=True,
    )

    filters_row = dbc.Row(
        [
            dbc.Col(year_dropdown, width=2),
            dbc.Col(event_type_dropdown, width=3),
            dbc.Col(week_dropdown, width=2),
            dbc.Col(sort_dropdown, width=2),
            dbc.Col(search_input, width=3),
        ],
        className="mb-4",
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
        Input("sort-dropdown", "value"),
        Input("search-input", "value"),
    ],
)
def update_events_table_and_map(selected_year, selected_event_types, selected_week, sort_option, search_query):
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
            "Event Name": f"[{ev['name']}]({ev.get('website', '#')})",
            "Location": f"{ev['city']}, {ev['state_prov']}, {ev['country']}",
            "Start Date": ev["start_date"],
            "End Date": ev["end_date"],
            "Event Type": ev["event_type_string"],
        }
        for ev in events_data
    ]

    # Sort
    if sort_option == "olddate":
        formatted_events = sorted(formatted_events, key=lambda x: x["Start Date"])
    elif sort_option == "newdate":
        formatted_events = sorted(formatted_events, key=lambda x: x["Start Date"], reverse=True)
    elif sort_option == "name":
        formatted_events = sorted(formatted_events, key=lambda x: x["Event Name"].lower())

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
                        "FIRST Robotics Competition is made up of seasons in which the challenge (game), along with the required set of tasks, changes annually. "
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
            dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
            dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
            
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
            dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
            dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),
            
            footer,
        ]
    )

def teams_layout(default_year=2024):
    teams_year_dropdown = dcc.Dropdown(
        id="teams-year-dropdown",
        options=[{"label": "All", "value": "All"}]
                 + [{"label": str(y), "value": y} for y in range(1992, 2026)],
        value=default_year,
        clearable=False,
        placeholder="Select Year",
    )

    country_dropdown = dcc.Dropdown(
        id="country-dropdown",
        options=[
            {"label": "All", "value": "All"},
            {"label": "USA", "value": "USA"},
            {"label": "Canada", "value": "Canada"},
            {"label": "Türkiye", "value": "Türkiye"},
            {"label": "Mexico", "value": "Mexico"},
            {"label": "Israel", "value": "Israel"},
            {"label": "Chinese Taipei", "value": "Chinese Taipei"},
            {"label": "China", "value": "China"},
            {"label": "Australia", "value": "Australia"},
            {"label": "Brazil", "value": "Brazil"},
            {"label": "India", "value": "India"},
        ],
        value="All",
        clearable=False,
        placeholder="Select Country",
    )

    # State Dropdown (static example; feel free to expand or make dynamic)
    state_dropdown = dcc.Dropdown(
        id="state-dropdown",
        options=[
            {"label": "All", "value": "All"},
            {"label": "Alabama", "value": "Alabama"},
            {"label": "Alaska", "value": "Alaska"},
            {"label": "Arizona", "value": "Arizona"},
            {"label": "Arkansas", "value": "Arkansas"},
            {"label": "California", "value": "California"},
            {"label": "Colorado", "value": "Colorado"},
            {"label": "Connecticut", "value": "Connecticut"},
            {"label": "Delaware", "value": "Delaware"},
            {"label": "Florida", "value": "Florida"},
            {"label": "Georgia", "value": "Georgia"},
            {"label": "Hawaii", "value": "Hawaii"},
            {"label": "Idaho", "value": "Idaho"},
            {"label": "Illinois", "value": "Illinois"},
            {"label": "Indiana", "value": "Indiana"},
            {"label": "Iowa", "value": "Iowa"},
            {"label": "Kansas", "value": "Kansas"},
            {"label": "Kentucky", "value": "Kentucky"},
            {"label": "Louisiana", "value": "Louisiana"},
            {"label": "Maine", "value": "Maine"},
            {"label": "Maryland", "value": "Maryland"},
            {"label": "Massachusetts", "value": "Massachusetts"},
            {"label": "Michigan", "value": "Michigan"},
            {"label": "Minnesota", "value": "Minnesota"},
            {"label": "Mississippi", "value": "Mississippi"},
            {"label": "Missouri", "value": "Missouri"},
            {"label": "Montana", "value": "Montana"},
            {"label": "Nebraska", "value": "Nebraska"},
            {"label": "Nevada", "value": "Nevada"},
            {"label": "New Hampshire", "value": "New Hampshire"},
            {"label": "New Jersey", "value": "New Jersey"},
            {"label": "New Mexico", "value": "New Mexico"},
            {"label": "New York", "value": "New York"},
            {"label": "North Carolina", "value": "North Carolina"},
            {"label": "North Dakota", "value": "North Dakota"},
            {"label": "Ohio", "value": "Ohio"},
            {"label": "Oklahoma", "value": "Oklahoma"},
            {"label": "Oregon", "value": "Oregon"},
            {"label": "Pennsylvania", "value": "Pennsylvania"},
            {"label": "Rhode Island", "value": "Rhode Island"},
            {"label": "South Carolina", "value": "South Carolina"},
            {"label": "South Dakota", "value": "South Dakota"},
            {"label": "Tennessee", "value": "Tennessee"},
            {"label": "Texas", "value": "Texas"},
            {"label": "Utah", "value": "Utah"},
            {"label": "Vermont", "value": "Vermont"},
            {"label": "Virginia", "value": "Virginia"},
            {"label": "Washington", "value": "Washington"},
            {"label": "West Virginia", "value": "West Virginia"},
            {"label": "Wisconsin", "value": "Wisconsin"},
            {"label": "Wyoming", "value": "Wyoming"},
        ],
        value="All",
        clearable=False,
        placeholder="Select State/Province",
    )

    view_map_button = dbc.Button(
        "View Map",
        id="teams-view-map",
        color="info",
        style={"backgroundColor": "#ffdd00ff",
               "color": "black",
               "border": "2px solid #555",
               "marginLeft": "10px"},
    )

    search_input = dbc.Input(
        id="search-bar",
        placeholder="Search teams by name or number...",
        type="text",
        debounce=True,
        className="mb-3",
    )

    teams_table = dash_table.DataTable(
        id="teams-table",
        columns=[
            {"name": "EPA Rank", "id": "epa_rank"},
            {"name": "Team", "id": "team_display","presentation": "markdown"},
            {"name": "Location", "id": "location_display"}
        ],
        data=[],
        page_size=50,
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
            "fontSize": "14px",
        },
    )


    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H2("Teams", className="text-center mb-4"),
                    dbc.Row(
                        [
                            dbc.Col(teams_year_dropdown, width=1),
                            dbc.Col(country_dropdown, width=2),
                            dbc.Col(state_dropdown, width=2),
                            dbc.Col(view_map_button, width="auto"),
                            dbc.Col(search_input, width=4),
                        ],
                        className="mb-4 justify-content-center",
                    ),
                    
                    # Table
                    dbc.Row(
                        dbc.Col(teams_table, width=12),
                        className="mb-4",
                    ),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),

            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            dbc.Button("Invisible5", id="teams-map", style={"display": "none"}),

            footer,
        ]
    )

@app.callback(
    Output("teams-table", "data"),
    [
        Input("teams-year-dropdown", "value"),
        Input("country-dropdown", "value"),
        Input("state-dropdown", "value"),
        Input("search-bar", "value"),
    ],
)
def load_teams(selected_year, selected_country, selected_state, search_query):
    folder_path = "team_data"  # Replace with the folder containing your JSON files
    teams_data = []

    if selected_year != "All":
        file_path = os.path.join(folder_path, f"teams_{selected_year}.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                teams_data = json.load(f)
    else:
        # Load data from all years if "All" is selected
        for filename in os.listdir(folder_path):
            if filename.endswith(".json"):
                with open(os.path.join(folder_path, filename), "r") as f:
                    teams_data.extend(json.load(f))

    # Filter by country
    if selected_country and selected_country != "All":
        teams_data = [team for team in teams_data if team.get("country") == selected_country]

    # Filter by state
    if selected_state and selected_state != "All":
        teams_data = [team for team in teams_data if team.get("state_prov") == selected_state]

    teams_data = sorted(teams_data, key=lambda x: x.get("epa", 0) if x.get("epa") is not None else 0, reverse=True)
    for idx, team in enumerate(teams_data):
        team["rank"] = idx + 1

    if search_query:
        search_query = search_query.lower()
        teams_data = [
            team for team in teams_data if
            search_query in str(team.get("team_number", "")).lower() or
            search_query in team.get("nickname", "").lower()
        ]

    # Assign EPA ranks and emojis
    table_data = []
    for idx, team in enumerate(teams_data):
        team_number = team.get("team_number", "")
        nickname = team.get("nickname", "")
        city = team.get("city", "")
        state = team.get("state_prov", "")
        country = team.get("country", "")
        epa = team.get("epa", 0)
        rank = team.get("rank", "N/A")

        rank_emoji = ""
        if rank == 1:
            rank_emoji = "🥇"
        elif rank == 2:
            rank_emoji = "🥈"
        elif rank == 3:
            rank_emoji = "🥉"

        epa_formatted = f"{epa:.2f}" if epa is not None else "N/A"
        epa_rank_display = f"{rank_emoji} {rank} \n Mean EPA: {epa_formatted}"

        team_display = f"[Team {team_number} - {nickname}](/data?team={team_number})" if nickname else f"[Team {team_number}](/data?team={team_number})"
        location_display = ", ".join(filter(None, [city, state, country]))

        table_data.append({
            "epa_rank": epa_rank_display,
            "team_display": team_display,
            "location_display": location_display or "Unknown",
        })

    return table_data

def teams_map_layout():
    folder_path = "geo"
    file_path = os.path.join(folder_path, "mapteams_2025.json")
    with open(file_path, "r", encoding="utf-8") as f:
        map_teams_2025 = json.load(f)

    # 2) Filter only teams with lat & lng
    map_teams = [t for t in map_teams_2025 if t.get("lat") and t.get("lng")]

    if not map_teams:
        # No lat/lng data?
        fig = px.scatter_geo(title="No teams found with lat/lng")
    else:
        fig = px.scatter_geo(
            map_teams,
            lat="lat",
            lon="lng",
            hover_name="nickname",
            hover_data=["team_number", "city", "state_prov", "country"],
            custom_data=["team_number"],
            projection="natural earth",
            template="plotly_white",
        )

        fig.update_traces(
            marker=dict(
                symbol='circle',
                color="yellow",
                size=5,                 # optional size
                line=dict(width=.5)  # optional border
            )
        )
        fig.update_geos(
            showcountries=True,
            countrycolor="grey",
            showsubunits=True,
            subunitcolor="gray",
            showland=True,
            landcolor="lightgreen",
            showocean=True,
            oceancolor="lightblue",
        )
        fig.update_layout(margin={"r":0, "t":0,"l":0,"b":0})

    # Return a layout
    return html.Div([
        topbar,
        dbc.Container([
            html.H3("Interactive Map: All 2025 Teams", className="text-center mb-4"),
            dcc.Graph(
                id="teams-map",
                figure=fig,
                style={"height": "80vh", "width": "100%"}
            ),
        ], fluid=True),

        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        dbc.Button("Invisible4", id="teams-view-map", style={"display": "none"}),
        
        footer
    ])


app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

@app.callback(
    [Output("url", "pathname"), Output("url", "search")],
    [
        Input("btn-search-home", "n_clicks"), 
        Input("desktop-search-button", "n_clicks"),  
        Input("mobile-search-button", "n_clicks"),  
        Input("teams-view-map", "n_clicks"),  
        Input("teams-map", "clickData"),
    ],
    [
        State("input-team-home", "value"), 
        State("input-year-home", "value"), 
        State("desktop-search-input", "value"), 
        State("mobile-search-input", "value"), 
    ],
    prevent_initial_call=True,
)
def handle_navigation(home_click, desktop_click, mobile_click, view_map_click, map_clickdata, home_team_value, home_year_value, desktop_search_value, mobile_search_value):
    
    ctx = dash.callback_context

    if not ctx.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Handle the Home Search button
    if trigger_id == "btn-search-home" and home_team_value:
        query_params = {"team": home_team_value}
        if home_year_value:  
            query_params["year"] = home_year_value
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    # Handle the Topbar Search button
    elif trigger_id == "desktop-search-button" and desktop_search_value:
        query_params = {"team": desktop_search_value}
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    elif trigger_id == "mobile-search-button" and mobile_search_value:
        query_params = {"team": mobile_search_value}
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    elif trigger_id == "teams-view-map":

        return "/teamsmap", ""  # pathname="/teamsmap", no search

    elif trigger_id == "teams-map":
        if not map_clickdata:
            raise dash.exceptions.PreventUpdate
        
        point = map_clickdata["points"][0]
        custom = point.get("customdata", [])
        if not custom:
            raise dash.exceptions.PreventUpdate

        team_number = custom[0] 
        query_params = {"team": team_number}
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    return dash.no_update, dash.no_update

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
    elif pathname == "/teams":
        return teams_layout()
    elif pathname == "/teamsmap":
        return teams_map_layout()  
    elif pathname == "/leaderboard":
        return leaderboard_layout()
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
