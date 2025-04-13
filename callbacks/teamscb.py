from dash import callback, Output, Input, State
from dash import dash_table
from layouts.teams import get_epa_display
from layouts.teams import create_team_card
from datagather import get_team_avatar, load_data, COUNTRIES, STATES
import numpy as np
import dash_bootstrap_components as dbc
from dash import html
import os

from layouts.teams import load_team_data

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
        Input("sort-by-dropdown", "value"),
    ],
)
def load_teams(selected_year, selected_country, selected_state, search_query, active_tab, sort_by):
    teams_data = load_team_data(selected_year)

    if not teams_data:
        return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}

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

    if sort_by == "auto_epa":
        teams_data.sort(key=lambda t: t.get("auto_epa") or 0, reverse=True)
    elif sort_by == "teleop_epa":
        teams_data.sort(key=lambda t: t.get("teleop_epa") or 0, reverse=True)
    elif sort_by == "endgame_epa":
        teams_data.sort(key=lambda t: t.get("endgame_epa") or 0, reverse=True)
    else:
        def weighted_epa(t):
            auto = t.get("auto_epa") or 0
            teleop = t.get("teleop_epa") or 0
            endgame = t.get("endgame_epa") or 0
            return 0.4 * auto + 0.5 * teleop + 0.1 * endgame  # tweak weights as desired

        teams_data.sort(key=weighted_epa, reverse=True)

    def compute_percentiles(values):
        return {p: np.percentile(values, int(p)) for p in ["99", "95", "90", "75", "50", "25"]} if values else {p: 0 for p in ["99", "95", "90", "75", "50", "25"]}

    extract_valid = lambda key: [t[key] for t in teams_data if t.get(key) is not None]
    overall_percentiles = compute_percentiles(extract_valid("epa"))
    auto_percentiles = compute_percentiles(extract_valid("auto_epa"))
    teleop_percentiles = compute_percentiles(extract_valid("teleop_epa"))
    endgame_percentiles = compute_percentiles(extract_valid("endgame_epa"))

    for idx, t in enumerate(teams_data):
        t["global_rank"] = idx + 1

    state_options = [{"label": "All States", "value": "All"}]
    if selected_country and selected_country in STATES:
        state_options += [
            {"label": s["label"], "value": s["value"]}
            for s in STATES[selected_country] if isinstance(s, dict)
        ]

    table_rows = []
    for t in teams_data:
        raw_rank = t.get("global_rank")
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            rank = "N/A"

        epa_rank_display = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, rank)
        team_num = t.get("team_number")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        table_rows.append({
            "epa_rank": epa_rank_display,
            "team_display": f"[{team_num} | {t.get('nickname', 'Unknown')}](/team/{team_num}/{selected_year})",
            "confidence": t.get("confidence", 0),
            "trend": t.get("trend", 0),
            "epar": get_epa_display(t.get("epa"), overall_percentiles),
            "auto_epa": get_epa_display(t.get("auto_epa"), auto_percentiles),
            "teleop_epa": get_epa_display(t.get("teleop_epa"), teleop_percentiles),
            "endgame_epa": get_epa_display(t.get("endgame_epa"), endgame_percentiles),
            "location_display": ", ".join(filter(None, [t.get("city", ""), t.get("state_prov", ""), t.get("country", "")])),
            "record": record,
        })

    top_teams_layout = dbc.Row([
        dbc.Col(create_team_card(t, selected_year, get_team_avatar(t.get("team_number"), selected_year)), width="auto")
        for t in teams_data[:3] if t.get("team_number")
    ], className="justify-content-center")

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
