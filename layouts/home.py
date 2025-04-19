from dash import html
import dash_bootstrap_components as dbc
from layouts.topbar import topbar, footer

home_layout = html.Div([
    dbc.Container(
        dbc.Row(
            dbc.Col(
                html.H2(
                    "Sorry, Peekorobo has been discontinued",
                    style={"textAlign": "center", "color": "#333", "marginTop": "20vh"}
                ),
                width=12
            ),
            justify="center",
            align="center",
            style={"height": "78vh"}
        ),
        fluid=True,
        class_name="py-5",
        style={"backgroundColor": "white"}
    ),
])
