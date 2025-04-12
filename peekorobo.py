import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc
from dash.dependencies import Input, Output, State
import os

from callbacks.navcb import toggle_navbar, update_search_preview
from callbacks.eventcb import update_display
from callbacks.teamscb import load_teams

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
        from layouts.team import team_layout
        team_number = path_parts[1]
        year = path_parts[2] if len(path_parts) > 2 else None
        return team_layout(team_number, year)
    
    if pathname.startswith("/event/"):
        from layouts.event import event_layout
        event_key = pathname.split("/")[-1]
        return event_layout(event_key)
    
    if pathname == "/teams":
        from layouts.teams import teams_layout
        return teams_layout()
    
    if pathname == "/map":
        from layouts.mapp import teams_map_layout
        return teams_map_layout()
    
    if pathname == "/events":
        from layouts.events import events_layout
        return events_layout()
    
    if pathname == "/challenges":
        from layouts.challenge import challenges_layout
        return challenges_layout()

    if pathname == "/blog":
        from layouts.blog import blog_layout
        return blog_layout
    
    if pathname.startswith("/challenge/"):
        from layouts.challenge import challenge_details_layout
        year = pathname.split("/")[-1]
        try:
            year = int(year)
        except ValueError:
            year = None
        return challenge_details_layout(year)

    from layouts.home import home_layout
    return home_layout

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=True)

