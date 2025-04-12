import dash_bootstrap_components as dbc
from dash import html

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
                                dbc.DropdownMenuItem("Peekorobo", href="https://www.peekorobo.com/", target="_blank"),
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