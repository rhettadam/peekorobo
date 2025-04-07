import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc, dash_table
from dash.dependencies import Input, Output, State
import folium
from folium.plugins import MarkerCluster

import requests
import urllib.parse 
import os
import random
from dotenv import load_dotenv
import numpy as np
import datetime
import sqlite3

from frcgames import frc_games
from locations import COUNTRIES, STATES

load_dotenv()

def load_all_team_data():

    def compress_dict(d):
        """Remove any None or empty string values."""
        return {k: v for k, v in d.items() if v not in (None, "", [], {}, ())}

    # === Load team ACE data ===
    team_conn = sqlite3.connect(os.path.join("team_data", "epa_teams.sqlite"))
    team_cursor = team_conn.cursor()
    team_cursor.execute("SELECT * FROM epa_history")
    team_columns = [desc[0] for desc in team_cursor.description]
    team_data = {}

    for row in team_cursor.fetchall():
        team = compress_dict(dict(zip(team_columns, row)))
        year = team["year"]
        number = team["team_number"]
        team_data.setdefault(year, {})[number] = team

    team_conn.close()

    # === Load compressed event data ===
    event_conn = sqlite3.connect(os.path.join("team_data", "events.sqlite"))
    event_cursor = event_conn.cursor()

    def fetch_all(query):
        event_cursor.execute(query)
        cols = [d[0] for d in event_cursor.description]
        return [compress_dict(dict(zip(cols, r))) for r in event_cursor.fetchall()]

    # Events
    events = fetch_all("SELECT * FROM e")
    event_data = {}
    flat_event_list = []
    for ev in events:
        year = ev["y"]
        ek = ev["k"]
        event_data.setdefault(year, {})[ek] = ev
        flat_event_list.append(ev)

    # Event Teams
    team_entries = fetch_all("SELECT * FROM et")
    EVENT_TEAMS = {}
    for t in team_entries:
        year = int(t["ek"][:4])
        ek = t["ek"]
        EVENT_TEAMS.setdefault(year, {}).setdefault(ek, []).append(t)

    # Rankings
    rank_entries = fetch_all("SELECT * FROM r")
    EVENT_RANKINGS = {}
    for r in rank_entries:
        year = int(r["ek"][:4])
        ek = r["ek"]
        tk = r["tk"]
        EVENT_RANKINGS.setdefault(year, {}).setdefault(ek, {})[tk] = r

    # Awards
    EVENTS_AWARDS = fetch_all("SELECT * FROM a")

    # Matches
    match_entries = fetch_all("SELECT * FROM m")
    EVENT_MATCHES = {}
    for m in match_entries:
        year = int(m["ek"][:4])
        EVENT_MATCHES.setdefault(year, []).append(m)

    # OPRs
    opr_entries = fetch_all("SELECT * FROM o")
    EVENT_OPRS = {}
    for o in opr_entries:
        year = int(o["ek"][:4])
        ek = o["ek"]
        tk = o["tk"]
        EVENT_OPRS.setdefault(year, {}).setdefault(ek, {})[tk] = o["opr"]

    event_conn.close()

    return team_data, event_data, flat_event_list, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES, EVENT_OPRS

TEAM_DATABASE, EVENT_DATABASE, EVENTS_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES, EVENT_OPRS = load_all_team_data()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

def tba_get(endpoint: str):
    # Cycle through keys by selecting one randomly or using a round-robin approach.
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
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
                        dbc.NavItem(dbc.NavLink("Challenges", href="/challenges", className="custom-navlink")),
                        dbc.NavItem(dbc.NavLink("Blog", href="/blog", className="custom-navlink")),
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

@app.callback(
    [Output("desktop-search-preview", "children"), Output("desktop-search-preview", "style"),
     Output("mobile-search-preview", "children"), Output("mobile-search-preview", "style")],
    [Input("desktop-search-input", "value"), Input("mobile-search-input", "value")],
)
def update_search_preview(desktop_value, mobile_value):
    desktop_value = (desktop_value or "").strip().lower()
    mobile_value = (mobile_value or "").strip().lower()

    # Collapse TEAM_DATABASE to a flat dict keeping only the most recent year for each team
    latest_teams = {}
    for year in sorted(TEAM_DATABASE.keys(), reverse=True):
        for team_number, team_data in TEAM_DATABASE[year].items():
            if team_number not in latest_teams:
                latest_teams[team_number] = team_data
    teams_data = list(latest_teams.values())

    events_data = EVENTS_DATABASE  # flat list of compressed event dicts

    def get_children_and_style(val):
        if not val:
            return [], {"display": "none"}

        # --- Filter Teams ---
        filtered_teams = [
            t for t in teams_data
            if val in str(t.get("team_number", "")).lower()
            or val in (t.get("nickname", "")).lower()
        ][:20]

        # Closest team
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

        # --- Filter Events (using compressed keys) ---
        filtered_events = []
        for e in events_data:
            event_code = (e.get("cd") or "").lower()
            event_name = (e.get("n") or "").lower()
            start_date = e.get("sd", "")
            event_year = start_date[:4] if len(start_date) >= 4 else ""
            year_name_combo = f"{event_year} {event_name}".lower()

            if (val in event_code) or (val in event_name) or (val in year_name_combo):
                filtered_events.append(e)
        filtered_events = filtered_events[:20]

        closest_event = None
        if filtered_events:
            closest_event = max(
                filtered_events,
                key=lambda e: (
                    len(set(val) & set((e.get("cd") or "").lower()))
                    + len(set(val) & set((e.get("n") or "").lower()))
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
                    style={"backgroundColor": "#f1f1f1", "marginTop": "5px"}
                )
            )
            for evt in filtered_events:
                event_key = evt.get("k", "???")
                e_name = evt.get("n", "")
                start_date = evt.get("sd", "")
                e_year = start_date[:4] if len(start_date) >= 4 else ""
                background_color = "white"

                if closest_event and event_key == closest_event.get("k"):
                    background_color = "#FFDD00"

                display_text = f"{event_key} | {e_year} {e_name}"
                row_el = dbc.Row(
                    dbc.Col(
                        html.A(
                            display_text,
                            href=f"/event/{event_key}",
                            style={"lineHeight": "20px", "textDecoration": "none", "color": "black"},
                        ),
                        width=True,
                    ),
                    style={"padding": "5px", "backgroundColor": background_color},
                )
                children.append(row_el)

        if not filtered_teams and not filtered_events:
            children.append(html.Div("No results found.", style={"padding": "5px", "color": "#555"}))

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

    desktop_children, desktop_style = get_children_and_style(desktop_value)
    mobile_children, mobile_style = get_children_and_style(mobile_value)

    return desktop_children, desktop_style, mobile_children, mobile_style

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

        team_epa = team.get("epa", 0) or 0  # Default to 0 if ACE is None
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

def build_recent_events_section(team_key, team_number, epa_data):
    epa_data = epa_data or {}
    recent_rows = []
    year = 2025

    for event_key, event in EVENT_DATABASE.get(year, {}).items():
        event_teams = EVENT_TEAMS.get(year, {}).get(event_key, [])
        if not any(t["tk"] == team_number for t in event_teams):
            continue

        event_name = event.get("n", "Unknown")
        loc = ", ".join(filter(None, [event.get("c", ""), event.get("s", ""), event.get("co", "")]))
        start_date = event.get("sd", "")
        event_url = f"/event/{event_key}"

        # Ranking
        ranking = EVENT_RANKINGS.get(year, {}).get(event_key, {}).get(team_number, {})
        rank_val = ranking.get("rk", "N/A")
        total_teams = len(event_teams)

        # Awards
        award_names = [
            a["an"] for a in EVENTS_AWARDS
            if a["tk"] == team_number and a["ek"] == event_key and a["y"] == year
        ]
        awards_line = html.Div([
            html.Span("Awards: ", style={"fontWeight": "bold"}),
            html.Span(", ".join(award_names))
        ]) if award_names else None

        rank_percent = rank_val / total_teams if isinstance(rank_val, int) and total_teams > 0 else None
        if rank_percent is not None:
            if rank_percent <= 0.25:
                rank_color = "green"
            elif rank_percent <= 0.5:
                rank_color = "orange"
            else:
                rank_color = "red"
            rank_str = html.Span([
                "Rank: ",
                html.Span(f"{rank_val}", style={"color": rank_color, "fontWeight": "bold"}),
                html.Span(f"/{total_teams}", style={"color": "black", "fontWeight": "normal"})
            ])
        else:
            rank_str = f"Rank: {rank_val}/{total_teams}"

        wins = ranking.get("w", "N/A")
        losses = ranking.get("l", "N/A")
        ties = ranking.get("t", "N/A")
        record = html.Span([
            html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#333"}),
            html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#333"}),
            html.Span(str(ties), style={"color": "gray", "fontWeight": "bold"})
        ])

        header = html.Div([
            html.A("2025 " + event_name, href=event_url, style={"fontWeight": "bold", "fontSize": "1.1rem"}),
            html.Div(loc),
            html.Div(rank_str),
            html.Div([
                html.Span("Record: ", style={"marginRight": "5px"}),
                record,
                html.Div(awards_line),
            ]),
        ], style={"marginBottom": "10px"})

        matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
        matches = [m for m in matches if str(team_number) in (m.get("rt") or "") or str(team_number) in (m.get("bt") or "")]

        def build_match_rows(matches):
            rows = []
            comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}
            matches.sort(key=lambda m: (comp_level_order.get(m.get("cl", ""), 99), m.get("mn", 9999)))
        
            def format_team_list(team_str):
                return ", ".join(f"[{t}](/team/{t})" for t in team_str.split(",") if t.strip().isdigit())

            def sum_epa(team_str):
                return sum(epa_data.get(t.strip(), {}).get("epa", 0) for t in team_str.split(",") if t.strip().isdigit())

        
            for match in matches:
                red_str = match.get("rt", "")
                blue_str = match.get("bt", "")
                red_score = match.get("rs", 0)
                blue_score = match.get("bs", 0)
                label = match.get("cl", "").upper() + " " + str(match.get("mn", ""))
        
                red_epa = sum_epa(red_str)
                blue_epa = sum_epa(blue_str)
        
                if red_epa + blue_epa > 0:
                    p_red = red_epa / (red_epa + blue_epa)
                    p_blue = 1 - p_red
                    prediction = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"
                else:
                    prediction = "N/A"
        
                winner = match.get("wa", "N/A").title()
                youtube_id = match.get("yt")
                video_link = f"[Watch](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
        
                rows.append({
                    "Video": video_link,
                    "Match": label,
                    "Red Teams": format_team_list(red_str),
                    "Blue Teams": format_team_list(blue_str),
                    "Red Score": red_score,
                    "Blue Score": blue_score,
                    "Winner": winner,
                    "Prediction": prediction,
                    "rowColor": "#ffe6e6" if winner == "Red" else "#e6f0ff" if winner == "Blue" else "white"
                })
        
            return rows


        match_rows = build_match_rows(matches)

        table = dash_table.DataTable(
            columns=[
                {"name": "Video", "id": "Video", "presentation": "markdown"},
                {"name": "Match", "id": "Match"},
                {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
                {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
                {"name": "Red Score", "id": "Red Score"},
                {"name": "Blue Score", "id": "Blue Score"},
                {"name": "Winner", "id": "Winner"},
                {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
            ],
            data=match_rows,
            page_size=10,
            style_table={"overflowX": "auto", "border": "1px solid #ddd", "borderRadius": "5px"},
            style_header={"backgroundColor": "#F2F2F2", "fontWeight": "bold", "border": "1px solid #ddd", "textAlign": "center"},
            style_cell={"textAlign": "center", "border": "1px solid #ddd", "padding": "8px"},
            style_data_conditional=[
                {
                    "if": {"filter_query": '{Winner} = "Red"'},
                    "backgroundColor": "#ffe6e6"
                },
                {
                    "if": {"filter_query": '{Winner} = "Blue"'},
                    "backgroundColor": "#e6f0ff"
                }
            ]
        )

        recent_rows.append(
            html.Div([
                header,
                table
            ])
        )

    return html.Div([
        html.H3("Recent Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
        html.Div(recent_rows)
    ])

def team_layout(team_number, year):
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_number = int(team_number)
    team_key = f"frc{team_number}"

    # Separate handling for performance year (used for ACE/stats) vs. awards/events year
    is_history = not year or str(year).lower() == "history"

    if is_history:
        year = None
        # fallback year to use for metrics (default to 2025 or latest available)
        performance_year = 2025
        available_years = sorted(TEAM_DATABASE.keys(), reverse=True)
        for y in available_years:
            if team_number in TEAM_DATABASE[y]:
                performance_year = y
                break
    else:
        try:
            year = int(year)
            performance_year = year
        except ValueError:
            return dbc.Alert("Invalid year provided.", color="danger")

    # Now safely use performance_year for stats lookups
    year_data = TEAM_DATABASE.get(performance_year)
    if not year_data:
        return dbc.Alert(f"Data for year {performance_year} not found.", color="danger")

    selected_team = year_data.get(team_number)
    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data for {performance_year}.", color="danger")

    # Calculate Rankings
    global_rank, country_rank, state_rank = calculate_ranks(list(year_data.values()), selected_team)

    # ACE Display
    epa_value = selected_team.get("epa", None)
    epa_display = f"{epa_value:.2f}" if epa_value is not None else "N/A"

    auto_epa = selected_team.get("auto_epa", None)
    teleop_epa = selected_team.get("teleop_epa", None)
    endgame_epa = selected_team.get("endgame_epa", None)
    auto_epa_display = f"{auto_epa:.2f}" if auto_epa is not None else "N/A"
    teleop_epa_display = f"{teleop_epa:.2f}" if teleop_epa is not None else "N/A"
    endgame_epa_display = f"{endgame_epa:.2f}" if endgame_epa is not None else "N/A"

    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
        }
        for team_num, data in year_data.items()
    }

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

    wins = selected_team.get("wins")
    losses = selected_team.get("losses")
    avg_score = selected_team.get("average_match_score")
    
    wins_str = str(wins) if wins is not None else "N/A"
    losses_str = str(losses) if losses is not None else "N/A"
    avg_score_str = f"{avg_score:.2f}" if avg_score is not None else "N/A"
    
    win_loss_ratio = html.Span([
        html.Span(wins_str, style={"color": "green", "fontWeight": "bold"}),
        html.Span(" / ", style={"color": "#333", "fontWeight": "bold"}),
        html.Span(losses_str, style={"color": "red", "fontWeight": "bold"})
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
                                        html.P("ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
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
                                        html.P(avg_score_str, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
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
                                        html.P("Auto ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(auto_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Teleop ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(teleop_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Endgame ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
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
    
        # --- Team Events from local database ---
    events_data = []
    
    year_keys = [year] if year else list(EVENT_DATABASE.keys())
    participated_events = []
    
    for year_key in year_keys:
        for event_key, event in EVENT_DATABASE.get(year_key, {}).items():
            team_list = EVENT_TEAMS.get(year_key, {}).get(event_key, [])
            if any(t["tk"] == team_number for t in team_list):  # using team_number now
                participated_events.append((year_key, event_key, event))
    
    # Sort events by start date
    participated_events.sort(key=lambda tup: tup[2].get("sd", ""), reverse=True)
    
    # Map event keys to names
    event_key_to_name = {ek: e.get("n", "Unknown") for _, ek, e in participated_events}
    
    # Build event rows
    for year_key, event_key, event in participated_events:
        event_name = event.get("n", "")
        location = f"{event.get('c', '')}, {event.get('s', '')}".strip(", ")
        start_date = event.get("sd", "")
        end_date = event.get("ed", "")
        event_url = f"https://www.peekorobo.com/event/{event_key}"
    
        # Rank
        rank = None
        rankings = EVENT_RANKINGS.get(year_key, {}).get(event_key, {})
        if team_number in rankings:
            rank = rankings[team_number].get("rk")
            if rank:
                event_name += f" (Rank: {rank})"
    
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
    
    # --- Awards Section ---
    team_awards = [
        row for row in EVENTS_AWARDS
        if row["tk"] == team_number and (not year or row["y"] == year)
    ]
    
    team_awards.sort(key=lambda aw: aw["y"], reverse=True)
    
    awards_data = [
        {
            "award_name": aw["an"],
            "event_name": event_key_to_name.get(aw["ek"], "Unknown Event"),
            "award_year": aw["y"]
        }
        for aw in team_awards
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
    
    # --- Blue Banners Section ---
    blue_banner_keywords = ["chairman's", "impact", "woodie flowers", "winner"]
    blue_banners = []
    
    for award in team_awards:
        name_lower = award["an"].lower()
        if any(keyword in name_lower for keyword in blue_banner_keywords):
            event_key = award["ek"]
            year_str = str(award["y"])
            event = EVENT_DATABASE.get(int(year_str), {}).get(event_key, {})
            event_name = event.get("n", "Unknown Event")
            full_event_name = f"{year_str} {event_name}"
    
            blue_banners.append({
                "award_name": award["an"],
                "event_name": full_event_name,
                "event_key": event_key
            })
    
    blue_banner_section = html.Div(
        [
            html.Div(
                [
                    html.A(
                        href=f"/event/{banner['event_key']}",
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
                                                banner["award_name"],
                                                style={"fontSize": "0.8rem", "color": "white", "fontWeight": "bold", "textAlign": "center", "marginBottom": "3px"},
                                            ),
                                            html.P(
                                                banner["event_name"],
                                                style={"fontSize": "0.6rem", "color": "white", "textAlign": "center"},
                                            ),
                                        ],
                                        style={"position": "absolute", "top": "50%", "left": "50%", "transform": "translate(-50%, -50%)"},
                                    ),
                                ],
                                style={"position": "relative", "marginBottom": "15px"},
                            ),
                        ],
                        style={"textDecoration": "none"},
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
                    html.Hr(),
                    build_recent_events_section(team_key, team_number, epa_data),
                    html.H3("Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Awards", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    awards_table,
                    #rank_tabs,  # Rank Over Time tabs inserted here
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
                    html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="upcoming-events-container", className="justify-content-center"),

                    html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="ongoing-events-container", className="justify-content-center"),

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


def create_event_card(event):
    event_url = f"https://www.peekorobo.com/event/{event['k']}"
    location = f"{event.get('c','')}, {event.get('s','')}, {event.get('co','')}"
    start = event.get('sd', 'N/A')
    end = event.get('ed', 'N/A')
    event_type = event.get('et', 'N/A')

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H5(event.get("n", "Unknown Event"), className="card-title mb-3"),
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
            "height": "20rem",
            "margin": "10px"
        }
    )

@app.callback(
    [
        Output("upcoming-events-container", "children"),
        Output("ongoing-events-container", "children"),
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
    events_data = list(EVENT_DATABASE.get(selected_year, {}).values())
    if not events_data:
        return [], [], []

    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    if "all" not in selected_event_types:
        filtered = []
        for et in selected_event_types:
            if et == "season":
                filtered.extend([ev for ev in events_data if ev.get("et") not in [99, 100]])
            elif et == "offseason":
                filtered.extend([ev for ev in events_data if ev.get("et") in [99, 100]])
            elif et == "regional":
                filtered.extend([ev for ev in events_data if "regional" in (ev.get("et") or "").lower()])
            elif et == "district":
                filtered.extend([ev for ev in events_data if "district" in (ev.get("et") or "").lower()])
            elif et == "championship":
                filtered.extend([ev for ev in events_data if "championship" in (ev.get("et") or "").lower()])
        events_data = list({ev["k"]: ev for ev in filtered}.values())

    if selected_week != "all":
        events_data = [ev for ev in events_data if ev.get("w") == selected_week]  # Optional: include week in compressed schema

    if search_query:
        q = search_query.lower()
        events_data = [
            ev for ev in events_data
            if q in ev.get("n", "").lower() or q in ev.get("c", "").lower()
        ]

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("sd", "1900-01-01"))
        ev["_end_date_obj"] = parse_date(ev.get("ed", "1900-01-01"))
    events_data.sort(key=lambda x: x["_start_date_obj"])

    today = datetime.date.today()
    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    up_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in upcoming[:5]]
    upcoming_layout = dbc.Row(up_cards, className="justify-content-center")

    ongoing_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in ongoing]
    ongoing_layout = dbc.Row(ongoing_cards, className="justify-content-center")

    all_event_cards = [create_event_card(ev) for ev in events_data]

    return upcoming_layout, ongoing_layout, all_event_cards

def load_teams_and_compute_epa_ranks(year):
    epa_info = {}

    year_data = TEAM_DATABASE.get(year)
    if not year_data:
        return epa_info  # Return empty if no data

    teams_data = list(year_data.values())

    teams_data = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)

    epa_values = [team["epa"] for team in teams_data if team.get("epa") is not None]
    if not epa_values:
        return epa_info  # No ACE values to rank

    percentiles = {
        "99": np.percentile(epa_values, 99),
        "95": np.percentile(epa_values, 95),
        "90": np.percentile(epa_values, 90),
        "75": np.percentile(epa_values, 75),
        "50": np.percentile(epa_values, 50),
        "25": np.percentile(epa_values, 25),
    }

    for idx, team in enumerate(teams_data):
        team_number = team["team_number"]
        epa_val = team.get("epa")
        rank = idx + 1
        epa_info[str(team_number)] = {
            "epa": epa_val,
            "rank": rank,
            "epa_display": get_epa_display(epa_val, percentiles),
        }

    return epa_info

def event_layout(event_key):
    parsed_year, _ = parse_event_key(event_key)
    event = EVENT_DATABASE.get(parsed_year, {}).get(event_key)
    if not event:
        return dbc.Alert("Event details could not be found.", color="danger")

    epa_data = load_teams_and_compute_epa_ranks(parsed_year)
    event_year = parsed_year
    event_teams = EVENT_TEAMS.get(event_year, {}).get(event_key, [])
    rankings = EVENT_RANKINGS.get(event_year, {}).get(event_key, {})

    # Compressed match keys
    event_matches = [m for m in EVENT_MATCHES.get(event_year, []) if m.get("ek") == event_key]

    event_name = event.get("n", "Unknown Event")
    event_location = f"{event.get('c', '')}, {event.get('s', '')}, {event.get('co', '')}"
    start_date = event.get("sd", "N/A")
    end_date = event.get("ed", "N/A")
    event_type = event.get("et", "N/A")
    website = event.get("w", "#")

    # Header card
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
        className="mb-4 shadow-sm flex-fill",
        style={"borderRadius": "10px"}
    )

    # Determine last match and thumbnail
    last_match = None
    if event_matches:
        final_matches = [m for m in event_matches if m.get("cl") == "f"]
        last_match = final_matches[-1] if final_matches else event_matches[-1]

    last_match_thumbnail = None
    if last_match and last_match.get("yt"):
        video_key = last_match.get("yt")
        thumbnail_url = f"https://img.youtube.com/vi/{video_key}/hqdefault.jpg"
        last_match_thumbnail = dbc.Card(
            dbc.CardBody(
                html.A(
                    html.Img(src=thumbnail_url, style={"width": "100%", "borderRadius": "5px"}),
                    href=f"https://www.youtube.com/watch?v={video_key}",
                    target="_blank"
                )
            ),
            className="mb-4 shadow-sm flex-fill",
            style={"borderRadius": "10px"}
        )

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
                    header_layout,
                    data_tabs,
                    dcc.Store(id="store-event-epa", data=epa_data),
                    dcc.Store(id="store-event-teams", data=event_teams),
                    dcc.Store(id="store-rankings", data=rankings),
                    dcc.Store(id="store-event-matches", data=event_matches),
                    dcc.Store(id="store-event-year", data=event_year),
                    dcc.Store(
                        id="store-oprs",
                        data={"oprs": EVENT_OPRS.get(event_year, {}).get(event_key, {})}
                    ),
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
    Build a team spotlight card using compressed event team data
    and full-schema TEAM_DATABASE.
    """
    from urllib.parse import quote

    t_num = team.get("tk")  # from compressed team list
    team_data = TEAM_DATABASE.get(event_year, {}).get(t_num, {})

    nickname = team_data.get("nickname", "Unknown")
    city = team_data.get("city", "")
    state = team_data.get("state_prov", "")
    country = team_data.get("country", "")
    location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

    # ACE info
    t_key_str = str(t_num)
    epa_rank = epa_data.get(t_key_str, {}).get("rank", "N/A")
    epa_display = epa_data.get(t_key_str, {}).get("epa_display", "N/A")

    # Avatar and team link
    avatar_url = get_team_avatar(t_num, event_year)
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
                html.P(f"ACE: {epa_display} (Global Rank: {epa_rank})", className="card-text"),
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

    # === Shared styles ===
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

    def safe_int(val):
        try: return int(val)
        except: return 999999

    # === Rankings Tab ===
    if active_tab == "rankings":
        data_rows = []
        for team_num, rank_info in (rankings or {}).items():
            tnum_str = str(team_num)

            epa_rank = epa_data.get(tnum_str, {}).get("rank", "N/A")
            epa_display = epa_data.get(tnum_str, {}).get("epa_display", "N/A")

            data_rows.append({
                "Rank": rank_info.get("rk", "N/A"),
                "Team": f"[{tnum_str}](/team/{tnum_str})",
                "Wins": rank_info.get("w", "N/A"),
                "Losses": rank_info.get("l", "N/A"),
                "Ties": rank_info.get("t", "N/A"),
                "DQ": rank_info.get("dq", "N/A"),
                "ACE Rank": epa_rank,
                "ACE": epa_display,
            })

        data_rows.sort(key=lambda r: safe_int(r["Rank"]))

        columns = [
            {"name": "Rank", "id": "Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins"},
            {"name": "Losses", "id": "Losses"},
            {"name": "Ties", "id": "Ties"},
            {"name": "DQ", "id": "DQ"},
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
        ]

        return html.Div([
            epa_legend_layout(),
            dash_table.DataTable(
                columns=columns,
                data=data_rows,
                page_size=10,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
            )
        ])

    # === OPRs Tab ===
    elif active_tab == "oprs":
        data = []
        for team_num, opr_val in (oprs.get("oprs") or {}).items():
            tnum_str = str(team_num)
            epa_rank = epa_data.get(tnum_str, {}).get("rank", "N/A")
            epa_display = epa_data.get(tnum_str, {}).get("epa_display", "N/A")

            data.append({
                "Team": f"[{tnum_str}](/team/{tnum_str})",
                "OPR": opr_val,
                "ACE Rank": epa_rank,
                "ACE": epa_display,
            })

        data.sort(key=lambda x: x["OPR"], reverse=True)
        for i, row in enumerate(data):
            row["OPR Rank"] = i + 1

        columns = [
            {"name": "OPR Rank", "id": "OPR Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "OPR", "id": "OPR"},
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
        ]

        return dash_table.DataTable(
            columns=columns,
            data=data,
            page_size=10,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
        )

    # === Teams Tab ===
    elif active_tab == "teams":
        sorted_teams = sorted(
            event_teams,
            key=lambda t: safe_int(epa_data.get(str(t.get("tk")), {}).get("rank", 999999))
        )
        top_3 = sorted_teams[:3]

        spotlight_cards = [
            dbc.Col(create_team_card_spotlight(t, epa_data, event_year), width="auto")
            for t in top_3
        ]
        spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")

        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            epa_rank = epa_data.get(tstr, {}).get("rank", "N/A")
            epa_disp = epa_data.get(tstr, {}).get("epa_display", "N/A")

            loc = ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown"

            rows.append({
                "ACE Rank": epa_rank,
                "ACE": epa_disp,
                "Team Number": f"[{tstr}](/team/{tstr})",
                "Nickname": t.get("nn", "Unknown"),
                "Location": loc,
            })

        rows.sort(key=lambda r: safe_int(r["ACE Rank"]))

        columns = [
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
            {"name": "Team Number", "id": "Team Number", "presentation": "markdown"},
            {"name": "Nickname", "id": "Nickname"},
            {"name": "Location", "id": "Location"},
        ]

        return html.Div([
            html.H4("Spotlight Teams", className="text-center mb-4", style={"fontWeight": "bold"}),
            spotlight_layout,
            epa_legend_layout(),
            dash_table.DataTable(
                columns=columns,
                data=rows,
                page_size=10,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
            )
        ])

    # === Matches Tab ===
    elif active_tab == "matches":
        team_filter_options = [
            {"label": f"{t['tk']} - {t.get('nn', '')}", "value": str(t["tk"])}
            for t in event_teams
        ]

        return html.Div([
            html.Div(
                [
                    html.Label("Filter by Team:", style={"fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="team-filter",
                        options=[{"label": "All Teams", "value": "ALL"}] + team_filter_options,
                        value="ALL",
                        clearable=False
                    )
                ],
                style={"marginBottom": "20px"}
            ),
            html.Div(id="matches-container")
        ])

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
    event_matches = event_matches or []
    epa_data = epa_data or {}

    # 1) Filter by team number
    if selected_team and selected_team != "ALL":
        event_matches = [
            m for m in event_matches
            if selected_team in (m.get("rt", "") + "," + m.get("bt", ""))
        ]

    # 2) Sort and separate by comp level
    comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}

    def match_sort_key(m):
        lvl = comp_level_order.get(m.get("cl", ""), 99)
        num = m.get("mn", 9999)
        return (lvl, num)

    event_matches.sort(key=match_sort_key)
    qual_matches = [m for m in event_matches if m.get("cl") == "qm"]
    playoff_matches = [m for m in event_matches if m.get("cl") != "qm"]

    # 3) Utility functions
    def format_teams_markdown(team_list_str):
        return ", ".join(f"[{t}](/team/{t})" for t in team_list_str.split(",") if t.strip().isdigit())

    def sum_epa(team_list_str):
        return sum(
            epa_data.get(t.strip(), {}).get("epa", 0)
            for t in team_list_str.split(",") if t.strip().isdigit()
        )

    def build_match_rows(matches):
        rows = []
        for match in matches:
            red_str = match.get("rt", "")
            blue_str = match.get("bt", "")
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            winner = match.get("wa", "")
            label = match.get("cl", "").upper() + str(match.get("mn", ""))

            r_sum = sum_epa(red_str)
            b_sum = sum_epa(blue_str)
            if (r_sum + b_sum) > 0:
                p_red = r_sum / (r_sum + b_sum)
                p_blue = 1.0 - p_red
                pred_str = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"
            else:
                pred_str = "N/A"

            yid = match.get("yt")
            video_link = f"[Watch](https://www.youtube.com/watch?v={yid})" if yid else "N/A"

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Teams": format_teams_markdown(red_str),
                "Blue Teams": format_teams_markdown(blue_str),
                "Red Score": red_score,
                "Blue Score": blue_score,
                "Winner": winner.title() if winner else "N/A",
                "Prediction": pred_str,
            })
        return rows

    qual_data = build_match_rows(qual_matches)
    playoff_data = build_match_rows(playoff_matches)

    match_columns = [
        {"name": "Video", "id": "Video", "presentation": "markdown"},
        {"name": "Match", "id": "Match"},
        {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
        {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
        {"name": "Red Score", "id": "Red Score"},
        {"name": "Blue Score", "id": "Blue Score"},
        {"name": "Winner", "id": "Winner"},
        {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
    ]

    row_style = [
        {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "#ffe6e6"},
        {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "#e6f0ff"},
    ]

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

blog_layout = html.Div([
    topbar,
    dbc.Container([
        html.H2("ACE (Adjusted Contribution Estimate) Algorithm", className="text-center my-4"),

        html.P("The EPA (Estimated Points Added) model attempts to estimate a team's contribution to a match based on detailed scoring breakdowns and long-term trends. ACE (Adjusted Contribution Estimate) extends this by incorporating consistency, alliance context, and statistical reliability.", style={"fontSize": "1.1rem"}),

        html.H4("Core Model", className="mt-4"),
        html.P("EPA updates are done incrementally after each match. Auto, Teleop, and Endgame contributions are calculated, then EPA is updated using a weighted delta."),

        dbc.Card([
            dbc.CardHeader("EPA Update"),
            dbc.CardBody([
                html.Pre("""
# Delta calculation with decay and match importance:
delta = decay * (K / (1 + M)) * ((actual - epa) - M * (opponent_score - epa))

# Update EPA:
epa += delta
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Decay and Match Weighting"),
        html.P("EPA uses exponential decay so newer matches matter more. Quals are weighted more than playoffs to reduce alliance bias."),

        dbc.Card([
            dbc.CardHeader("Decay Formula"),
            dbc.CardBody([
                html.Pre("""
decay = 0.95 ** match_index
importance = {"qm": 1.2, "qf": 1.0, "sf": 1.0, "f": 1.0}
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("EPA Component Breakdown"),
        html.P("Each team’s total EPA is the sum of their estimated Auto, Teleop, and Endgame contributions. These are computed separately and updated using the same delta mechanism."),

        html.H4("Auto EPA Estimation"),
        html.P("Auto EPA estimates scoring using reef row counts. To reduce inflation, the algorithm trims the top 25% of scores and caps the result."),

        dbc.Card([
            dbc.CardHeader("Auto Scoring Logic"),
            dbc.CardBody([
                html.Pre("""
def estimate_consistent_auto(breakdowns, team_count):
    scores = sorted(score_per_breakdown(b) for b in breakdowns)
    cutoff = int(len(scores) * 0.75)
    trimmed = scores[:cutoff]
    return round(min(statistics.mean(trimmed), 30), 2)
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Statistical Notes on Auto EPA"),
        html.P("The trimming method approximates a robust mean, reducing influence from occasional hot autos. It’s a simplified Winsorized mean. The cap of 30 points is based on expected maximum scoring in auto under typical match constraints."),

        html.H4("Confidence Weighting (ACE)"),
        html.P("ACE = EPA × Confidence. Confidence is computed from three components: consistency, rookie bonus, and carry factor."),

        dbc.Card([
            dbc.CardHeader("ACE Confidence Formula"),
            dbc.CardBody([
                html.Pre("""
consistency = 1 - (stdev / mean)
rookie_bonus = 1.0 if veteran else 0.6
carry = min(1.0, team_epa / (avg_teammate_epa + ε))
confidence = (consistency + rookie_bonus + carry) / 3
ACE = EPA × confidence
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Consistency"),
        html.P("This measures how stable a team's match-to-match performance is. Statistically, it's computed as 1 minus the coefficient of variation (CV):"),

        dbc.Card([
            dbc.CardHeader("Consistency"),
            dbc.CardBody([
                html.Pre("""
consistency = 1 - (statistics.stdev(scores) / statistics.mean(scores))
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "#f8f9fa", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Rookie Bonus"),
        html.P("Veteran teams start with a higher confidence (1.0 vs 0.6) because they’ve historically performed more predictably."),

        html.H4("Carry Factor"),
        html.P("This measures whether a team is likely benefiting from stronger alliance partners. A team well below its average teammates gets a lower confidence score."),

        html.Hr(),
        html.P("The full model is continuously evolving and improving. To contribute, test ideas, or file issues, visit the GitHub repository:", className="mt-4"),
        html.A("https://github.com/rhettadam/peekorobo", href="https://github.com/rhettadam/peekorobo", target="_blank")
    ], style={"maxWidth": "900px"}, className="py-4 mx-auto"),
    dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
    dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
    dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
    footer
])

def get_team_avatar(team_number, year=2025):
    """
    Returns the relative URL path to a team's avatar image if it exists,
    otherwise returns the path to a stock avatar.
    """
    avatar_path = f"assets/avatars/{team_number}.png"
    if os.path.exists(avatar_path):
        return f"/assets/avatars/{team_number}.png?v=1"
    return "/assets/avatars/stock.png"


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
            html.H5("ACE Color Key (Percentile):", className="mb-3", style={"fontWeight": "bold"}),
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

    # Pull team data from database
    team_data = TEAM_DATABASE.get(selected_year, {}).get(team_number, {})

    nickname = team_data.get("nickname", "Unknown")
    city = team_data.get("city", "")
    state = team_data.get("state_prov", "")
    country = team_data.get("country", "")

    location_pieces = [p for p in [city, state, country] if p]
    location_str = ", ".join(location_pieces) if location_pieces else "Unknown"

    # ACE and rank from database
    epa = team_data.get("epa")
    rank = team_data.get("global_rank", "N/A")
    epa_str = f"{epa:.2f}" if isinstance(epa, (int, float)) else "N/A"

    # URL to team details
    team_url = f"/team/{team_number}/{selected_year}"

    card_body = []

    # Add avatar if available
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
                html.P(f"ACE: {epa_str} (Global Rank: {rank})", className="card-text"),
                dbc.Button("View Team", href=team_url, color="warning", className="mt-2"),
            ]
        )
    )

    return dbc.Card(
        card_body,
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
        options=COUNTRIES,
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
            {"name": "ACE Rank", "id": "epa_rank"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "Confidence", "id": "confidence"},
            {"name": "ACE", "id": "epar"},
            {"name": "Auto ACE", "id": "auto_epa"},
            {"name": "Teleop ACE", "id": "teleop_epa"},
            {"name": "Endgame ACE", "id": "endgame_epa"},
            {"name": "Record", "id": "record"},
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

    avatar_gallery = html.Div(
        id="avatar-gallery",
        className="d-flex flex-wrap justify-content-center",
        style={"gap": "5px", "padding": "1rem"}
    )

    tabs = dbc.Tabs([
        dbc.Tab(label="Teams Table", tab_id="table-tab"),
        dbc.Tab(label="Avatars", tab_id="avatars-tab"),
    ], id="teams-tabs", active_tab="table-tab", className="mb-3")

    content = html.Div(id="teams-tab-content", children=[
        html.Div(id="teams-table-container", children=[teams_table]),
        html.Div(id="avatar-gallery", className="d-flex flex-wrap justify-content-center", style={"gap": "5px", "padding": "1rem", "display": "none"})
    ])


    return html.Div(
        [
            topbar,
            dbc.Container([
                html.H4("Top 3 Teams", className="text-center mb-4"),
                dbc.Row(id="top-teams-container", className="justify-content-center mb-5"),
                filters_row,
                epa_legend_layout(),
                tabs,
                content,
            ], style={"padding": "10px", "maxWidth": "1200px", "margin": "0 auto"}),
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
        Output("top-teams-container", "children"),
        Output("teams-table-container", "style"),
        Output("avatar-gallery", "children"),
        Output("avatar-gallery", "style"),
    ],
    [
        Input("teams-year-dropdown", "value"),
        Input("country-dropdown", "value"),
        Input("state-dropdown", "value"),
        Input("search-bar", "value"),
        Input("teams-tabs", "active_tab"),
    ],
)
def load_teams(selected_year, selected_country, selected_state, search_query, active_tab):
    from functools import lru_cache

    @lru_cache(maxsize=1)
    def get_cached_team_data(year):
        return list(TEAM_DATABASE.get(year, {}).values())

    teams_data = get_cached_team_data(selected_year)

    if not teams_data:
        return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}

    # Apply filters early to reduce work
    if selected_country and selected_country != "All":
        teams_data = [t for t in teams_data if t.get("country", "").lower() == selected_country.lower()]
    if selected_state and selected_state != "All":
        teams_data = [t for t in teams_data if t.get("state_prov", "").lower() == selected_state.lower()]
    if search_query:
        q = search_query.lower()
        teams_data = [
            t for t in teams_data
            if q in str(t.get("team_number", "")).lower()
            or q in t.get("nickname", "").lower()
            or q in t.get("city", "").lower()
        ]

    # Sort by EPA after filtering
    teams_data.sort(key=lambda t: t.get("epa") or 0, reverse=True)

    # Pre-compute percentile cutoffs
    def compute_percentiles(values):
        return {p: np.percentile(values, int(p)) for p in ["99", "95", "90", "75", "50", "25"]} if values else {p: 0 for p in ["99", "95", "90", "75", "50", "25"]}

    extract_valid = lambda key: [t[key] for t in teams_data if t.get(key) is not None]
    overall_percentiles = compute_percentiles(extract_valid("epa"))
    auto_percentiles = compute_percentiles(extract_valid("auto_epa"))
    teleop_percentiles = compute_percentiles(extract_valid("teleop_epa"))
    endgame_percentiles = compute_percentiles(extract_valid("endgame_epa"))

    # Assign global ranks
    for idx, t in enumerate(teams_data):
        t["global_rank"] = idx + 1

    # State dropdown options
    state_options = [{"label": "All States", "value": "All"}]
    if selected_country and selected_country in STATES:
        state_options += [
            {"label": s["label"], "value": s["value"]}
            for s in STATES[selected_country] if isinstance(s, dict)
        ]

    # Table rows
    table_rows = []
    for t in teams_data:
        rank = t.get("global_rank", "N/A")
        team_num = t.get("team_number")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        table_rows.append({
            "epa_rank": {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, rank),
            "team_display": f"[{team_num} | {t.get('nickname', 'Unknown')}](/team/{team_num}/{selected_year})",
            "confidence": t.get("confidence", 0),
            "epar": get_epa_display(t.get("epa"), overall_percentiles),
            "auto_epa": get_epa_display(t.get("auto_epa"), auto_percentiles),
            "teleop_epa": get_epa_display(t.get("teleop_epa"), teleop_percentiles),
            "endgame_epa": get_epa_display(t.get("endgame_epa"), endgame_percentiles),
            "location_display": ", ".join(filter(None, [t.get("city", ""), t.get("state_prov", ""), t.get("country", "")])),
            "record": record,
        })

    # Top cards
    top_teams_layout = dbc.Row([
        dbc.Col(create_team_card(t, selected_year, get_team_avatar(t.get("team_number"), selected_year)), width="auto")
        for t in teams_data[:3] if t.get("team_number")
    ], className="justify-content-center")

    # Tabs
    if active_tab == "avatars-tab":
        table_style, avatar_style = {"display": "none"}, {"display": "flex"}
        avatars = []
        for t in teams_data:
            team_number = t.get("team_number")
            if isinstance(team_number, int):
                path = f"assets/avatars/{team_number}.png"
                avatars.append(html.A(
                    html.Img(
                        src=f"/assets/avatars/{team_number}.png?v=1" if os.path.exists(path) else "/assets/avatars/stock.png",
                        title=str(team_number),
                        style={"width": "64px", "height": "64px", "objectFit": "contain", "imageRendering": "pixelated", "border": "1px solid #ccc"},
                    ),
                    href=f"/team/{team_number}/{selected_year}",
                    style={"display": "inline-block"}
                ))
        return table_rows, state_options, top_teams_layout, table_style, avatars, avatar_style

    return table_rows, state_options, top_teams_layout, {"display": "block"}, [], {"display": "none"}

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

    selected_year = int(year_value) if year_value and year_value.isdigit() else 2025
    year_data = TEAM_DATABASE.get(selected_year)

    if not year_data:
        return "/"

    # Search for the team by number or name
    search_value_lower = search_value.lower()
    matching_team = next(
        (
            team for team in year_data.values()
            if str(team.get("team_number", "")).lower() == search_value_lower
            or search_value_lower in team.get("nickname", "").lower()
        ),
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
    
    if pathname == "/events":
        return events_layout()
    
    if pathname == "/challenges":
        return challenges_layout()

    if pathname == "/blog":
        return blog_layout
    
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
    app.run(host="0.0.0.0", port=port, debug=False)

