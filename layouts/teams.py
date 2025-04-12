from layouts.topbar import topbar, footer
from layouts.epalegend import epa_legend_layout, get_epa_display
from dash import dcc, dash_table, html
import dash_bootstrap_components as dbc
from datagather import load_data, COUNTRIES, STATES

from data_store import TEAM_DATABASE

team_cache = {}

def load_team_data(year):
    if year not in team_cache:
        team_cache[year] = list(TEAM_DATABASE.get(year, {}).values())
    return team_cache[year]

def create_team_card(team, selected_year, avatar_url=None):
    team_number = team.get("team_number", "N/A")

    nickname = team.get("nickname", "Unknown")
    city = team.get("city", "")
    state = team.get("state_prov", "")
    country = team.get("country", "")

    location_pieces = [p for p in [city, state, country] if p]
    location_str = ", ".join(location_pieces) if location_pieces else "Unknown"

    # ACE and rank from database
    epa = team.get("epa")
    rank = team.get("global_rank", "N/A")

    rank_display = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, rank)

    
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
                html.P(f"ACE: {epa_str} (Global Rank: {rank_display})", className="card-text"),
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

    sort_dropdown = dcc.Dropdown(
    id="sort-by-dropdown",
    options=[
        {"label": "Total ACE", "value": "epa"},
        {"label": "Auto ACE", "value": "auto_epa"},
        {"label": "Teleop ACE", "value": "teleop_epa"},
        {"label": "Endgame ACE", "value": "endgame_epa"},
    ],
    value="epa",
    clearable=False,
    placeholder="ACE",
    style={"width": "180px"}
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
            dbc.Col(sort_dropdown, xs=6, sm=4, md=2),
        ],
        className="mb-4 justify-content-center",
    )

    teams_table = dash_table.DataTable(
        id="teams-table",
        columns=[
            {"name": "ACE Rank", "id": "epa_rank"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "Trend", "id": "trend"},
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