from dash import callback, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from datagather import load_data

data = load_data(
    load_teams=True,
    load_events=True,
    load_event_teams=False,
    load_rankings=False,
    load_awards=False,
    load_matches=False,
    load_oprs=False,
)

# Mimic legacy unpacking
TEAM_DATABASE = data.get("team_data", {})
EVENTS_DATABASE = data.get("flat_event_list", [])

team_data = TEAM_DATABASE

@callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@callback(
    [Output("desktop-search-preview", "children"), Output("desktop-search-preview", "style"),
     Output("mobile-search-preview", "children"), Output("mobile-search-preview", "style")],
    [Input("desktop-search-input", "value"), Input("mobile-search-input", "value")],
)
def update_search_preview(desktop_value, mobile_value):
    desktop_value = (desktop_value or "").strip().lower()
    mobile_value = (mobile_value or "").strip().lower()

    # Collapse TEAM_DATABASE to a flat dict keeping only the most recent year for each team
    # === Build flat_team_list: most recent year per team ===
    latest_teams = {}
    for year in sorted(team_data.keys(), reverse=True):  # latest years first
        for team_number, team_info in team_data[year].items():
            if team_number not in latest_teams:
                latest_teams[team_number] = team_info
    teams_data = list(latest_teams.values())


    events_data = EVENTS_DATABASE

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