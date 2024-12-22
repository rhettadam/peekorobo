import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import requests
import urllib.parse  # for URL query string parsing
import os
from dotenv import load_dotenv

# -------------- CONFIG --------------
TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

def configure():
    load_dotenv()
# -------------- SETUP --------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
server = app.server

# -------------- HELPER --------------
def tba_get(endpoint: str):
    """Fetch data from TBA with the Read API key."""
    headers = {"X-TBA-Auth-Key": os.getenv("TBA_API_KEY")}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None
# -------------- LAYOUTS --------------

topbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand(
                html.Img(
                    src="/assets/logo.png",
                    height="40px",
                    alt="FRC Logo",
                ),
                href="/",
                className="ms-2",
            ),
            dbc.Nav(
                [
                    dbc.NavItem(dbc.NavLink("Home", href="/")),
                    dbc.NavItem(dbc.NavLink("Leaderboard", href="/leaderboard")),
                ],
                navbar=True,
            ),
            # Search Button and Input in Topbar
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="topbar-search-input",
                        placeholder="Search teams...",
                        type="text",
                        style={"width": "200px"},
                    ),
                    dbc.Button(
                        "Search",
                        id="topbar-search-button",
                        color="primary",
                        style={
                            "backgroundColor": "#ffdd00ff",
                            "border": "none",
                            "color": "#333",
                        },
                    ),
                ],
                className="ms-auto",
                style={"width": "300px"},
            ),
        ]
    ),
    color="light",
    dark=False,
    className="mb-4",
    style={
        "position": "sticky",  # Makes the navbar sticky
        "top": "0",           # Sticks to the top of the viewport
        "zIndex": "1020",     # Ensures it stays on top of other content
        "boxShadow": "0px 2px 2px rgba(0,0,0,0.1)",  # Optional shadow for better visibility
    },
)

footer = dbc.Container(
    dbc.Row([
        dbc.Col([
            html.P("Powered by "),
            html.A("The Blue Alliance", href="https://www.thebluealliance.com/", target="_blank", style={"color": "#007BFF"}),
            " | ",
            html.A("GitHub", href="https://github.com/rhettadam/peekorobo", target="_blank", style={"color": "#007BFF"}),
        ], style={"textAlign": "center", "color": "#AAA", "fontSize": "14px"})
    ]),
    fluid=True,
    style={"marginTop": "0px", "padding": "5px 0","boxShadow": "0px -2px 2px rgba(0,0,0,0.1)"}
)

# ---- HOME PAGE LAYOUT ----
home_layout = html.Div([
    topbar,
    dbc.Container(fluid=True, children=[
    # Main Content Row
    dbc.Row([
        # Left Section: Logo, Text, Search
        dbc.Col([
            html.Div([
                html.Img(src="/assets/logo.png", 
                         className='homelogo',
                         style={
                    "width": "450px", 
                    "marginBottom": "15px"
                }),
                html.P("Search for any FRC Team", style={
                    "fontSize": "1.5rem", 
                    "color": "#555", 
                    "textAlign": "center", 
                    "marginBottom": "20px"
                }),
                dbc.Row([
                    dbc.Col(dbc.Input(id="input-team-home", type="text", placeholder="Team # (e.g., 254)",
                                      className="custom-input-box",
                                      style={"padding": "10px", "borderRadius": "5px", "marginBottom": "1rem", "width": "100%"}), width=6),
                    dbc.Col(dbc.Input(id="input-year-home", type="text", placeholder="Year (e.g., 2023) optional)",
                                      className="custom-input-box",
                                      style={"padding": "10px", "borderRadius": "5px", "marginBottom": "1rem", "width": "100%"}), width=6),
                ], justify="center"),
                dbc.Button("Search", id="btn-search-home", color="primary", size="lg",
                           style={"backgroundColor": "#ffdd00ff", "border": "none", "color": "black", "marginTop": "10px"}),
            ], style={"textAlign": "center", "display": "flex", "flexDirection": "column", "alignItems": "center"})
        ], width=6),
        
        # Right Section: Bulldozer GIF
        dbc.Col([
            html.Div([
                html.A(
                    html.Img(
                        src="/assets/dozer.gif",
                        style={"width": "600px", "display": "block", "margin": "auto"}
                    ),
                    href="https://github.com/rhettadam/peekrobo",
                    target="_blank"  # Opens in a new tab
                ),
            ], style={"textAlign": "center"}),
        ], width=6)
    ], justify="center", align="center", style={"height": "75vh"}),
], class_name="py-5", style={"backgroundColor": "white"}),
    footer
])

def data_layout(team_number, year):
    """Returns a layout with TBA data for the given team/year."""
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_key = f"frc{team_number}"

    # Fetch Basic Team Info
    team_info = tba_get(f"team/{team_key}")
    if not team_info:
        return dbc.Alert(
            f"Error: Could not fetch info for team {team_number}. "
            "Double-check your input or TBA key.",
            color="danger"
        )

    nickname = team_info.get("nickname", "Unknown")
    city = team_info.get("city", "")
    state = team_info.get("state_prov", "")
    country = team_info.get("country", "")
    website = team_info.get("website", "N/A")
    rookie_year = team_info.get("rookie_year", "N/A")

    # Fetch Years Participated
    years_participated = tba_get(f"team/{team_key}/years_participated")
    years_text = ", ".join(map(str, years_participated)) if years_participated else "N/A"

    # Team Info Card
    team_card = dbc.Card(
        dbc.CardBody(
            [
                html.H2(f"Team {team_number}: {nickname}", style={"color": "#333", "fontWeight": "bold"}),
                html.P([html.I(className="bi bi-geo-alt-fill"), f" Location: {city}, {state}, {country}"]),
                html.P([html.I(className="bi bi-link-45deg"), " Website: ", 
                        html.A(website, href=website, target="_blank", style={"color": "#007BFF", "textDecoration": "none"})]),
                html.P([html.I(className="bi bi-award"), f" Rookie Year: {rookie_year}"]),
                html.P([html.I(className="bi bi-calendar"), f" Years Participated: {years_text}"]),
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
        matches = tba_get(f"team/{team_key}/matches")

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
        html.Span(f"{wins}", style={"color": "green", "fontWeight": "bold"}),  # Green for wins
        html.Span("/", style={"color": "#333", "fontWeight": "bold"}),  # Separator
        html.Span(f"{losses}", style={"color": "red", "fontWeight": "bold"})  # Red for losses
    ])

    if year:
        performance_card = dbc.Card(
            dbc.CardBody(
                [
                    html.H3(f"{year if year else 'All Years'} Performance Metrics", style={"color": "#333", "fontWeight": "bold"}),
                    html.P([html.I(className="bi bi-trophy-fill"), f" Total Matches Played: {total_matches}"]),
                    html.P([
                        html.I(className="bi bi-bar-chart-fill"), 
                        " Win/Loss Ratio: ", 
                        win_loss_ratio  # Use the styled win/loss ratio here
                    ]),
                    html.P([html.I(className="bi bi-graph-up"), f" Average Match Score: {avg_score:.2f}"]),
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

    else:
        performance_card = None
        
    # --- Team Events ---
    if year:
        events = tba_get(f"team/{team_key}/events/{year}")
    else:
        # Fetch events from the past 3 years
        from datetime import datetime

        current_year = datetime.now().year
        events = []
        for past_year in range(current_year - 2, current_year + 2):
            events.extend(tba_get(f"team/{team_key}/events/{past_year}") or [])
        # Sort events by start date in reverse order
        events = sorted(events, key=lambda ev: ev.get("start_date", ""), reverse=True)
        
    event_key_to_name = {ev["key"]: ev["name"] for ev in events}

    events_data = []
    for ev in events:
        event_key = ev.get("key")
        event_name = ev.get("name", "")
        location = f"{ev.get('city', '')}, {ev.get('state_prov', '')}"
        start_date = ev.get("start_date", "")
        end_date = ev.get("end_date", "")

        # Fetch rankings for the event
        rankings = tba_get(f"event/{event_key}/rankings")
        rank = None
        if rankings and "rankings" in rankings:
            for entry in rankings["rankings"]:
                if entry["team_key"] == team_key:
                    rank = entry["rank"]
                avg_rank = sum(r["rank"] for r in rankings["rankings"]) / len(rankings["rankings"])

        # Format rank with the event name
        if rank:
            event_name_with_rank = f"{event_name} (Rank: {rank})"
        else:
            event_name_with_rank = event_name

        events_data.append({
            "event_name": event_name_with_rank,
            "event_location": location,
            "start_date": start_date,
            "end_date": end_date,
        })

    # DataTable for Events
    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name"},
            {"name": "Location", "id": "event_location"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        data=events_data,
        page_size=5,
        style_table={"overflowX": "auto"},
        style_data={"border": "1px solid #ddd"},
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
        style_table={"overflowX": "auto"},
        style_data={"border": "1px solid #ddd"},
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
            footer
        ]
    )

def clean_category_label(raw_label):
    """Cleans up the raw category label for better display."""
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
                    # Remove 'frc' prefix to display just the team number
                    team_number = team_key.replace("frc", "")
                    leaderboard_table_data.append({
                        "Team": team_number,
                        "Value": rank.get("value", 0),
                    })

    # Sort data by value (descending)
    leaderboard_table_data = sorted(leaderboard_table_data, key=lambda x: x["Value"], reverse=True)

    # Create a DataTable
    leaderboard_table = dash_table.DataTable(
        id="leaderboard-table",
        columns=[
            {"name": "Team", "id": "Team", "presentation": "markdown"},  # Enable markdown for links
            {"name": "Value", "id": "Value"},
            {"name": "Rank", "id": "Rank"},
        ],
        data=leaderboard_table_data,
        sort_action="native",
        style_table={"overflowX": "auto"},
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
        footer
    ])
@app.callback(
    Output("leaderboard-table", "data"),
    Input("year-selector", "value"),
    Input("category-selector", "value"),
)
def update_leaderboard(year, category):
    if not year:
        year = 2024  # Default year
    leaderboard_data = tba_get(f"insights/leaderboards/{year}")
    if not leaderboard_data:
        return []

    leaderboard_table_data = []
    rankings = []
    for item in leaderboard_data:
        if item["name"] == category:
            rankings = item.get("data", {}).get("rankings", [])
            break

    # Sort rankings by value (descending) and compute ranks
    sorted_rankings = sorted(rankings, key=lambda x: x["value"], reverse=True)
    current_rank = 0
    last_value = None
    for i, rank in enumerate(sorted_rankings):
        team_keys = rank.get("keys", [])
        for team_key in team_keys:
            team_number = team_key.replace("frc", "")
            team_link = f"[{team_number}](/data?team={team_number}&year={year})"

            # Assign rank (same rank for teams with the same value)
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

# -------------- TOP-LEVEL APP LAYOUT --------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

# -------------- CALLBACKS --------------

@app.callback(
    [Output("url", "pathname"), Output("url", "search")],
    [
        Input("btn-search-home", "n_clicks"),
        Input("topbar-search-button", "n_clicks"),
    ],
    [
        State("input-team-home", "value"),
        State("input-year-home", "value"),  # Include the year input field
        State("topbar-search-input", "value"),
    ],
    prevent_initial_call=True,
)
def handle_navigation(home_click, topbar_click, home_team_value, home_year_value, topbar_search_value):
    """
    Handles navigation triggered by either the home search button or the topbar search button,
    ensuring the search leads to the team's historical data page with optional year.
    """
    ctx = dash.callback_context

    # Identify which button triggered the callback
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Handle the Home Search button
    if trigger_id == "btn-search-home" and home_team_value:
        query_params = {"team": home_team_value}
        if home_year_value:  # Include year if provided
            query_params["year"] = home_year_value
        search = "?" + urllib.parse.urlencode(query_params)
        return "/data", search

    # Handle the Topbar Search button
    elif trigger_id == "topbar-search-button" and topbar_search_value:
        return "/data", f"?team={topbar_search_value}"

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
        return data_layout(team_number, year)
    elif pathname == "/leaderboard":
        return leaderboard_layout()
    else:
        return home_layout
    
if __name__ == "__main__":
    app.run_server(debug=False)
    

