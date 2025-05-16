import dash_bootstrap_components as dbc
from dash import html, dcc
from datagather import frc_games

def team_link_with_avatar(team):
    team_number = team.get("team_number", "???")
    nickname = team.get("nickname", "")
    avatar_url = f"/assets/avatars/{team_number}.png"

    return html.A(
        html.Div([
            html.Img(src=avatar_url, style={
                "height": "20px",
                "width": "20px",
                "marginRight": "8px",
                "objectFit": "contain",
                "verticalAlign": "middle"
            }),
            f"{team_number} | {nickname}"
        ], style={"display": "flex", "alignItems": "center"}),
        href=f"/team/{team_number}",
        style={"textDecoration": "none", "color": "var(--text-primary)"}
    )

def topbar():
    return dbc.Navbar(
        dbc.Container(
            [
                dcc.Store(id="login-state-ready", data=False),
                dcc.Store(id="theme-store", data="light"),  # Store for theme preference

                dbc.Row(
                    [
                        dbc.Col(
                            dbc.NavbarBrand(
                                html.Img(
                                    src="/assets/logo.png",
                                    style={"height": "40px", "width": "auto", "marginRight": "10px"},
                                ),
                                href="/",
                                className="navbar-brand-custom",
                            ),
                            width="auto",
                            className="align-self-center",
                        ),
                        dbc.Col(
                            [
                                dbc.InputGroup(
                                    [
                                        dbc.Input(id="mobile-search-input", placeholder="Search", type="text"),
                                        dbc.Button("🔎", id="mobile-search-button", color="primary", style={
                                            "backgroundColor": "#FFDD00", "border": "none", "color": "#222",
                                        }),
                                    ],
                                    style={"width": "180px"},
                                ),
                                html.Div(id="mobile-search-preview", style={
                                    "backgroundColor": "var(--card-bg)",
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
                                }),
                            ],
                            width="auto",
                            className="d-md-none align-self-center",
                            style={"position": "relative", "textAlign": "center"},
                        ),
                        dbc.Col(
                            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                            width="auto",
                            className="d-md-none align-self-center",
                        ),
                    ],
                    className="g-2",
                    align="center",
                    justify="between",
                ),

                dbc.Collapse(
                    dbc.Container([
                        dbc.Row(
                            dbc.Nav(
                                [
                                    dbc.NavItem(dbc.NavLink("Teams", href="/teams", className="custom-navlink")),
                                    dbc.NavItem(dbc.NavLink("Map", href="/map", className="custom-navlink")),
                                    dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink")),
                                    dbc.NavItem(dbc.NavLink("Challenges", href="/challenges", className="custom-navlink")),
                                    dbc.NavItem(dbc.NavLink("Blog", href="/blog", className="custom-navlink")),
                                    dbc.DropdownMenu(
                                        label="Resources",
                                        nav=True,
                                        in_navbar=True,
                                        className="custom-navlink",
                                        children=[
                                            dbc.DropdownMenuItem("Chief Delphi", href="https://www.chiefdelphi.com/", target="_blank"),
                                            dbc.DropdownMenuItem("The Blue Alliance", href="https://www.thebluealliance.com/", target="_blank"),
                                            dbc.DropdownMenuItem("FRC Subreddit", href="https://www.reddit.com/r/FRC/", target="_blank"),
                                            dbc.DropdownMenuItem("FRC Discord", href="https://discord.com/invite/frc", target="_blank"),
                                            dbc.DropdownMenuItem(divider=True),
                                            dbc.DropdownMenuItem("FIRST Technical Resources", href="https://www.firstinspires.org/resource-library/frc/technical-resources", target="_blank"),
                                            dbc.DropdownMenuItem("FRCDesign", href="https://www.frcdesign.org/learning-course/", target="_blank"),
                                            dbc.DropdownMenuItem("OnShape4FRC", href="https://onshape4frc.com/", target="_blank"),
                                            dbc.DropdownMenuItem(divider=True),
                                            dbc.DropdownMenuItem("Statbotics", href="https://www.statbotics.io/", target="_blank"),
                                            dbc.DropdownMenuItem("ScoutRadioz", href="https://scoutradioz.com/", target="_blank"),
                                            dbc.DropdownMenuItem("Peekorobo", href="https://www.peekorobo.com/", target="_blank"),
                                        ]
                                    ),
                                    dbc.NavItem(
                                        dbc.Button(
                                            html.I(className="fas fa-moon"),
                                            id="theme-toggle",
                                            className="custom-navlink",
                                            style={"background": "none", "border": "none", "padding": "0.5rem 1rem"},
                                        )
                                    ),
                                ],
                                navbar=True,
                                className="justify-content-center",
                            ),
                            justify="center",
                        ),
                    ]),
                    id="navbar-collapse",
                    is_open=False,
                    navbar=True,
                ),

                dbc.Col(
                    [
                        dbc.InputGroup(
                            [
                                dbc.Input(id="desktop-search-input", placeholder="Search Teams or Events", type="text", className="custom-input-box"),
                                dbc.Button("🔎", id="desktop-search-button", color="primary", style={
                                    "backgroundColor": "#FFDD00", "border": "none", "color": "#222",
                                }),
                            ]
                        ),
                        html.Div(id="desktop-search-preview", style={
                            "backgroundColor": "var(--card-bg)",
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
                        }),
                    ],
                    width="auto",
                    className="desktop-search d-none d-md-block",
                    style={"position": "relative"},
                ),
            ],
            fluid=True
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
        }
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
                    "color": "var(--text-primary)",
                    "fontSize": "12px",
                    "margin": "0",  # Minimized margin
                    "padding": "0",  # Minimized padding
                }
            ),
        ], style={"padding": "0"})  # Ensure no padding in columns
    ], style={"margin": "0"}),  # Ensure no margin in rows
    fluid=True,
    style={
        "backgroundColor": "var(--card-bg)",
        "padding": "10px 0px",
        "boxShadow": "0px -1px 2px rgba(0, 0, 0, 0.1)",
        "margin": "0",  # Eliminate default container margin
    }
)

home_layout = html.Div([
    topbar(),
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
                                        "color": "var(--text-primary)",
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
                                        "color": "#222",
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
    ], class_name="py-5", style={"backgroundColor": "var(--bg-primary)"}),
    footer
])

blog_layout = html.Div([
    topbar(),
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
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
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
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("EPA Component Breakdown"),
        html.P("Each team's total EPA is the sum of their estimated Auto, Teleop, and Endgame contributions. These are computed separately and updated using the same delta mechanism."),

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
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Statistical Notes on Auto EPA"),
        html.P("The trimming method approximates a robust mean, reducing influence from occasional hot autos. It's a simplified Winsorized mean. The cap of 30 points is based on expected maximum scoring in auto under typical match constraints."),

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
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Consistency"),
        html.P("This measures how stable a team's match-to-match performance is. Statistically, it's computed as 1 minus the coefficient of variation (CV):"),

        dbc.Card([
            dbc.CardHeader("Consistency"),
            dbc.CardBody([
                html.Pre("""
consistency = 1 - (statistics.stdev(scores) / statistics.mean(scores))
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Rookie Bonus"),
        html.P("Veteran teams start with a higher confidence (1.0 vs 0.6) because they've historically performed more predictably."),

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
                                            style={"textDecoration": "none", "color": "var(--text-primary)"},
                                        ),
                                        className="mb-1",
                                    ),
                                    html.P(
                                        game.get("summary", "No summary available."),
                                        style={"color": "var(--text-primary)", "marginBottom": "5px", "fontSize": "0.9rem"},
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
            topbar(),
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
            topbar(),
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
                        style={"fontSize": "1rem", "lineHeight": "1.5", "color": "var(--text-primary)"},
                    ),
                    # Game Manual Button
                    html.Div(
                        dbc.Button(
                            "View Game Manual",
                            href=game["manual"],
                            target="_blank",
                            style={"marginBottom": "20px",
                                  "backgroundColor": "#ffdd00ff",
                                  "color": "#222",
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