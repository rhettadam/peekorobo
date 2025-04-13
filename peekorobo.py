import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc
from dash.dependencies import Input, Output, State
import os

import callbacks.navcb
import callbacks.eventcb
import callbacks.teamscb

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
    app.run(host="0.0.0.0", port=port, debug=False)

