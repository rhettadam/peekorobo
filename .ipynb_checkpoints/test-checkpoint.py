import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
import requests
import urllib.parse  # for URL query string parsing

# -------------- CONFIG --------------
TBA_API_KEY = "lsSSM1GgCjbFqObJKWADdAzE4DNoO7gEu2nO4cyATZnLJTWEaIKrHfItkfYaM25M"  # <--- Replace with your real TBA Read Key
TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

# -------------- SETUP --------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],  # Use Darkly theme
    suppress_callback_exceptions=True
)
server = app.server

# -------------- HELPER --------------
def tba_get(endpoint: str):
    """Fetch data from TBA with the Read API key."""
    headers = {"X-TBA-Auth-Key": TBA_API_KEY}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

# -------------- LAYOUTS --------------

# ---- HOME PAGE LAYOUT ----
home_layout = dbc.Container(fluid=True, children=[
    dbc.Row(
        dbc.Col([
            html.Div(className="home-hero", children=[
                html.H1("Welcome to FRC Team Lookup"),
                html.H4("Powered by The Blue Alliance"),
                html.P(
                    "Search for any FRC Team and optionally a specific year to see "
                    "their location, events, and awards."
                ),
                # Big input form
                dbc.Row([
                    dbc.Col(
                        dbc.Input(
                            id="input-team-home",
                            type="text",
                            placeholder="Team # (e.g., 254)",
                            style={"marginBottom": "1rem"}
                        ), width=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id="input-year-home",
                            type="text",
                            placeholder="Year (optional, e.g. 2023)",
                            style={"marginBottom": "1rem"}
                        ), width=3
                    ),
                ], class_name="justify-content-center"),
                dbc.Button("Search", id="btn-search-home", color="primary", size="lg"),
            ])
        ], width=12),
    )
], class_name="py-5")

# ---- DATA PAGE LAYOUT ----
def data_layout(team_number, year):
    """Returns a layout with TBA data for the given team/year."""
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_key = f"frc{team_number}"

    # --- (1) Basic Team Info ---
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
    website = team_info.get("website", "")
    rookie_year = team_info.get("rookie_year", "N/A")

    # --- (2) Fetch an Image/Logo (if available) from TBA Media ---
    media_list = tba_get(f"team/{team_key}/media")  # Fetch all years
    team_img_src = None
    if media_list:
        for m in media_list:
            # Some media might be YouTube or other types, so only look for direct images
            direct_url = m.get("direct_url") or m.get("details", {}).get("image_direct_url")
            # We'll pick the first valid image link we find
            if direct_url and direct_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                team_img_src = direct_url
                break

    # If we found an image link, display it; otherwise, skip the image
    if team_img_src:
        img_element = html.Img(src=team_img_src, className="team-image")
    else:
        img_element = html.Div()  # or some placeholder

    # Layout: Image on the left, info on the right
    team_card = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                # Column 1: The image (if found)
                dbc.Col(img_element, width=4, md=3),
                # Column 2: The textual info
                dbc.Col([
                    html.H2(f"Team {team_number} - {nickname}"),
                    html.P(f"Location: {city}, {state}, {country}"),
                    html.P(f"Website: ", href=website, children=[
                        html.A(website, href=website, target="_blank")
                    ]),
                    html.P(f"Rookie Year: {rookie_year}")
                ], width=8, md=9),
            ])
        ])
    ], className="mb-4")

    # --- (3) Team Events ---
    if year:
        events = tba_get(f"team/{team_key}/events/{year}")
    else:
        events = tba_get(f"team/{team_key}/events")

    events_data = []
    event_name_lookup = {}
    if events:
        for ev in events:
            e_name = ev.get("name", "")
            e_city = ev.get("city", "")
            e_state = ev.get("state_prov", "")
            e_start = ev.get("start_date", "")
            e_end = ev.get("end_date", "")
            events_data.append({
                "event_name": e_name,
                "event_location": f"{e_city}, {e_state}",
                "start_date": e_start,
                "end_date": e_end,
            })
            event_name_lookup[ev.get("key", "")] = e_name

    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name"},
            {"name": "Location", "id": "event_location"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        data=events_data,
        page_size=10,
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "backgroundColor": "#343a40",
            "color": "#f8f9fa",
            "border": "1px solid #495057"
        },
        style_header={
            "backgroundColor": "#495057",
            "color": "#f8f9fa",
            "fontWeight": "bold"
        }
    )

    # --- (4) Team Awards ---
    if year:
        awards = tba_get(f"team/{team_key}/awards/{year}")
    else:
        awards = tba_get(f"team/{team_key}/awards")

    awards_data = []
    if awards:
        for aw in awards:
            a_name = aw.get("name", "Unknown Award")
            a_event_key = aw.get("event_key", "")
            a_year = aw.get("year", "N/A")
            a_event_name = event_name_lookup.get(a_event_key, "Unknown Event")
            awards_data.append({
                "award_name": a_name,
                "event_name": a_event_name,
                "award_year": a_year,
            })

    awards_table = dash_table.DataTable(
        columns=[
            {"name": "Award Name", "id": "award_name"},
            {"name": "Event Name", "id": "event_name"},
            {"name": "Year", "id": "award_year"},
        ],
        data=awards_data,
        page_size=10,
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "backgroundColor": "#343a40",
            "color": "#f8f9fa",
            "border": "1px solid #495057"
        },
        style_header={
            "backgroundColor": "#495057",
            "color": "#f8f9fa",
            "fontWeight": "bold"
        }
    )

    return dbc.Container([
        # Top card with team info and image
        team_card,

        # Events
        html.H3("Team Events", style={"marginTop": "2rem", "color": "#ffc107"}),
        events_table,

        # Awards
        html.H3("Team Awards", style={"marginTop": "2rem", "color": "#17a2b8"}),
        awards_table,

        # Back button
        html.Br(),
        dbc.Button("Go Back", id="btn-go-back", color="secondary", href="/", external_link=True)
    ], fluid=True)

# -------------- TOP-LEVEL APP LAYOUT --------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

# -------------- CALLBACKS --------------

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("url", "search")
)
def display_page(pathname, search):
    """
    Renders either the home page (if path == "/") or the data page (if path == "/data").
    On the data page, we parse the query string ?team=XYZ&year=ABC
    """
    if pathname == "/data":
        # E.g. search might be "?team=254&year=2023"
        query_params = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
        team_number = query_params.get("team", [None])[0]
        year = query_params.get("year", [None])[0]
        return data_layout(team_number, year)
    else:
        # Home page
        return home_layout

# The fix is here: we multi-output (pathname, search) instead of a single "href".
@app.callback(
    Output("url", "pathname"),
    Output("url", "search"),
    Input("btn-search-home", "n_clicks"),
    State("input-team-home", "value"),
    State("input-year-home", "value"),
    prevent_initial_call=True
)
def go_to_data_page(n_clicks, team_value, year_value):
    """
    When the user clicks "Search" on the home page, we update the URL to /data,
    plus the query string ?team=XXX&year=YYY
    """
    if not team_value:
        return dash.no_update, dash.no_update

    # We'll always navigate to /data
    new_path = "/data"

    # Build query string
    qs = f"?team={team_value}"
    if year_value:
        qs += f"&year={year_value}"

    return new_path, qs

if __name__ == "__main__":
    app.run_server(debug=True)
