import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from datagather import frc_games,COUNTRIES,STATES,DISTRICT_STATES,get_team_avatar,get_pg_connection
from flask import session
from datetime import datetime, date
from utils import predict_win_probability, calculate_single_rank, compute_percentiles
import json

def topbar():
    return dbc.Navbar(
        dbc.Container(
            [
                dcc.Store(id="login-state-ready", data=False),
                dcc.Store(id="theme-store", data="dark"),  # Store for theme preference

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
                                        dbc.Input(id="mobile-search-input", placeholder="Search", type="text", className="custom-input-box"),
                                        dbc.Button(
                                            html.Img(src="/assets/magnifier.svg", style={
                                                "width": "20px",
                                                "height": "20px",
                                                "transform": "scaleX(-1)"
                                            }),
                                            id="mobile-search-button",
                                            color="primary",
                                            style={
                                                "backgroundColor": "#FFDD00",
                                                "border": "none",
                                                "color": "#222",
                                                "display": "flex",
                                                "alignItems": "center",
                                                "justifyContent": "center",
                                                "padding": "0.375rem 0.75rem"
                                            }
                                        ),
                                    ],
                                    style={"width": "180px"},
                                ),
                                html.Div(id="mobile-search-preview", style={
                                    "backgroundColor": "var(--card-bg)",
                                    #"border": "1px solid var(--card-bg)",
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
                                    dbc.DropdownMenu(
                                        label="Misc",
                                        nav=True,
                                        in_navbar=True,
                                        className="custom-navlink",
                                        children=[
                                            dbc.DropdownMenuItem("Blog", href="/blog"),
                                            dbc.DropdownMenuItem("Compare", href="/compare"),
                                            dbc.DropdownMenuItem(divider=True),
                                            dbc.DropdownMenu(
                                                label="Resources",
                                                nav=False,  # This is a nested dropdown, not a main nav item
                                                in_navbar=False, # Not a main nav item
                                                direction="end", # Open to the right
                                                toggleClassName='nested-dropdown-toggle', # Added custom class
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
                                dbc.Button(
                                    html.Img(src="/assets/magnifier.svg", style={
                                        "width": "20px",
                                        "height": "20px",
                                        "transform": "scaleX(-1)"
                                    }),
                                    id="desktop-search-button",
                                    color="primary",
                                    style={
                                        "backgroundColor": "#FFDD00",
                                        "border": "none",
                                        "color": "#222",
                                        "display": "flex",
                                        "alignItems": "center",
                                        "justifyContent": "center",
                                        "padding": "0.375rem 0.75rem"
                                    }
                                ),
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
        color="var(--text-primary)",
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
                                        src="/assets/dozer.png",
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
    ], class_name="py-5", style={
        "backgroundColor": "var(--bg-primary)",
        "flexGrow": "1" # Added flex-grow
        }),
    footer
])

blog_layout = html.Div([
    topbar(),
    dbc.Container([
        html.H2("ACE (Adjusted Contribution Estimate) Algorithm", className="text-center my-4"),

        html.P("The EPA (Estimated Points Added) model estimates a team's contribution to a match based on scoring breakdowns and trends. ACE (Adjusted Contribution Estimate) extends this by incorporating consistency, dominance, and statistical reliability.", style={"fontSize": "1.1rem"}),

        html.H4("Core Model", className="mt-4"),
        html.P("EPA updates are done incrementally after each match. Auto, Teleop, and Endgame contributions are calculated separately, then EPA is updated using a weighted delta with decay."),

        dbc.Card([
            dbc.CardHeader("EPA Update Formula"),
            dbc.CardBody([
                html.Pre("""
# For each component (auto, teleop, endgame):
delta = decay * K * (actual - epa)

# Where:
decay = world_champ_penalty * (match_count / total_matches)²
K = 0.4 * match_importance * world_champ_penalty

# World Championship penalties:
Einstein: 0.95
Division: 0.85
Regular: 1.0

# Match importance weights:
importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Component Estimation", className="mt-4"),
        html.P("Each component (Auto, Teleop, Endgame) is estimated separately with adaptive trimming based on match count:"),

        dbc.Card([
            dbc.CardHeader("Adaptive Trimming"),
            dbc.CardBody([
                html.Pre("""
# Trimming percentages based on match count:
< 12 matches: 0%
< 25 matches: 3%
< 40 matches: 5%
< 60 matches: 8%
< 100 matches: 10%
≥ 100 matches: 12%

# Trim from low end only:
trimmed_scores = sorted(scores)[k:]  # k = n * trim_pct
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Confidence Calculation", className="mt-4"),
        html.P("ACE = EPA × Confidence. Confidence is computed from multiple weighted components:"),

        dbc.Card([
            dbc.CardHeader("Confidence Formula"),
            dbc.CardBody([
                html.Pre("""
weights = {
    "consistency": 0.4,
    "dominance": 0.25,
    "record_alignment": 0.15,
    "veteran": 0.1,
    "events": 0.05,
    "base": 0.05
}

# Components:
consistency = 1 - (stdev / peak_score)
dominance = mean(normalized_margin_scores)
record_alignment = 1 - |expected_win_rate - actual_win_rate|
veteran_bonus = 1.0 if veteran else 0.6
event_boost = 1.0 if events ≥ 2 else 0.60

confidence = min(1.0, sum(weight * component))
""", style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "backgroundColor": "var(--card-bg)", "padding": "10px"})
            ])
        ], className="my-3"),

        html.H4("Key Components", className="mt-4"),
        html.P("Each confidence component measures a different aspect of team performance:"),

        dbc.Card([
            dbc.CardBody([
                html.H6("Consistency (40%)"),
                html.P("Measures stability of match-to-match performance. Higher when scores are more consistent relative to peak performance."),
                
                html.H6("Dominance (25%)"),
                html.P("Measures how much a team outperforms opponents. Calculated from normalized margin scores across matches."),
                
                html.H6("Record Alignment (15%)"),
                html.P("How well actual win rate matches expected win rate based on dominance scores."),
                
                html.H6("Veteran Status (10%)"),
                html.P("Veteran teams get higher confidence (1.0 vs 0.6) due to historical predictability."),
                
                html.H6("Event Count (5%)"),
                html.P("Teams with multiple events get a confidence boost (1.0 vs 0.6)."),
                
                html.H6("Base Confidence (5%)"),
                html.P("Minimum confidence floor to prevent extreme penalties.")
            ])
        ], className="my-3"),

        html.Hr(),
        html.P("The model is continuously evolving. To contribute, test ideas, or file issues, visit the GitHub repository:", className="mt-4"),
        html.A("https://github.com/rhettadam/peekorobo", href="https://github.com/rhettadam/peekorobo", target="_blank")
    ], style={
        "maxWidth": "900px",
        "flexGrow": "1" # Added flex-grow
        }, className="py-4 mx-auto"),
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
                style={
                    "maxWidth": "900px",
                    "margin": "0 auto",
                    "flexGrow": "1" # Added flex-grow
                },
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
                style={
                    "maxWidth": "800px",
                    "margin": "0 auto",
                    "padding": "20px",
                    "flexGrow": "1" # Added flex-grow
                },
            ),
            
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def teams_map_layout():
    # Generate and get the map file path
    map_path = "assets/teams_map.html"

    return html.Div([
        topbar(),
        dbc.Container(
            [
                html.Iframe(
                    src=f"/{map_path}",  # Reference the generated HTML file
                    style={"width": "100%", "height": "1050px", "border": "none"},
                ),
            ],
            fluid=True,
            style={
                "flexGrow": "1", # Added flex-grow
            }
        ),
        footer,
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
    ])

def login_layout():
    # Optional redirect if logged in
    if "user_id" in session:
        return dcc.Location(href="/user", id="redirect-to-profile")

    return html.Div([
        topbar(),
        dcc.Location(id="login-redirect", refresh=True),
        dbc.Container(fluid=True, children=[
            dbc.Row(
                dbc.Col(
                    html.Div([
                        html.Img(
                            src="/assets/dozer.png",
                            style={"width": "100%", "maxWidth": "500px", "marginBottom": "30px"},
                            className="dozer-image"
                        ),
                        html.H3("Login or Register", style={"textAlign": "center", "marginBottom": "20px", "color": "var(--text-primary)"}),
                        dbc.Input(id="username", type="text", placeholder="Username", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1rem"}),
                        dbc.Input(id="password", type="password", placeholder="Password", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1.5rem"}),
                        dbc.Row([
                            dbc.Col(dbc.Button("Login", id="login-btn", style={
                                "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%"
                            }), width=6),
                            dbc.Col(dbc.Button("Register", id="register-btn", style={
                                "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%"
                            }), width=6),
                        ], justify="center", style={"maxWidth": "500px", "margin": "auto"}),
                        html.Div(id="login-message", style={"textAlign": "center", "marginTop": "1rem", "color": "#333", "fontWeight": "bold"}),
                    ], style={"textAlign": "center", "paddingTop": "50px"})
                , width=12),
            )
        ], class_name="py-5", style={
            "backgroundColor": "var(--bg-primary)",
            "flexGrow": "1" # Added flex-grow
            }),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer
    ])

def epa_legend_layout():
    color_map = [
        ("≥ 99%", "#6a1b9a99"),   # Deep Purple
        ("≥ 97%", "#8e24aa99"),
        ("≥ 95%", "#3949ab99"),
        ("≥ 93%", "#1565c099"),
        ("≥ 91%", "#1e88e599"), 
        ("≥ 89%", "#2e7d3299"),
        ("≥ 85%", "#43a04799"),
        ("≥ 80%", "#c0ca3399"),
        ("≥ 75%", "#ffb30099"),
        ("≥ 65%", "#f9a82599"),
        ("≥ 55%", "#fb8c0099"),
        ("≥ 40%", "#e5393599"),
        ("≥ 25%", "#b71c1c99"),
        ("≥ 10%", "#7b000099"),
        ("< 10%", "#4d000099"),
    ]
    blocks = [
        html.Div(
            label,
            style={
                "backgroundColor": color,
                "color": "#fff",
                "padding": "2px 6px",
                "borderRadius": "4px",
                "fontSize": "0.7rem",
                "fontWeight": "500",
                "textAlign": "center",
                "minWidth": "48px",
            }
        )
        for label, color in color_map
    ]

    return dbc.Alert(
        [
            html.Small("ACE Color Key (Percentiles):", className="d-block mb-2", style={"fontWeight": "bold"}),
            html.Div(blocks, style={"display": "flex", "flexWrap": "wrap", "gap": "4px"})
        ],
        color="light",
        style={
            "border": "1px solid #ccc",
            "borderRadius": "8px",
            "padding": "8px",
            "fontSize": "0.8rem",
            "marginBottom": "1rem",
        },
    )

def create_team_card(team, year, avatar_url, epa_ranks):
    team_number = str(team.get("team_number"))
    epa_data = epa_ranks.get(team_number, {})
    nickname = team.get("nickname", "Unknown")
    location = ", ".join(filter(None, [team.get("city", ""), team.get("state_prov", ""), team.get("country", "")]))
    epa_display = epa_data.get("epa_display", "N/A")
    rank = epa_data.get("rank", "N/A")

    return dbc.Card(
        [
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "objectFit": "contain",
                    "height": "150px",
                    "padding": "0.5rem",
                    "backgroundColor": "transparent"
                }
            ),
            dbc.CardBody(
                [
                    html.H5(f"#{team_number} | {nickname}", className="card-title", style={
                        "fontSize": "1.1rem",
                        "textAlign": "center",
                        "marginBottom": "0.5rem"
                    }),
                    html.P(f"Location: {location}", className="card-text", style={
                        "fontSize": "0.9rem",
                        "textAlign": "center",
                        "marginBottom": "0.5rem"
                    }),
                    html.P(f"ACE: {epa_display} (Global Rank: {rank})", className="card-text", style={
                        "fontSize": "0.9rem",
                        "textAlign": "center",
                        "marginBottom": "auto"
                    }),
                    dbc.Button(
                        "View Team",
                        href=f"/team/{team_number}/{year}",
                        color="warning",
                        outline=True,
                        className="custom-view-btn mt-3",
                    )
                ],
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "flexGrow": "1",
                    "justifyContent": "space-between",
                    "padding": "1rem"
                }
            )
        ],
        className="m-2 shadow-sm",
        style={
            "width": "18rem",
            "height": "22rem",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "space-between",
            "alignItems": "stretch",
            "borderRadius": "12px"
        }
    )

def teams_layout(default_year=2025):
    user_id = session.get("user_id")
    teams_year_dropdown = dcc.Dropdown(
        id="teams-year-dropdown",
        options=[{"label": str(y), "value": y} for y in range(1992, 2026)],
        value=default_year,
        clearable=False,
        placeholder="Select Year",
        style={"width": "100%"},
        className="custom-input-box"
    )

    country_dropdown = dcc.Dropdown(
        id="country-dropdown",
        options=COUNTRIES,
        value="All",
        clearable=False,
        placeholder="Select Country",
        style={"width": "100%"},
        className="custom-input-box"
    )

    state_dropdown = dcc.Dropdown(
        id="state-dropdown",
        options=[{"label": "All States", "value": "All"}],
        value="All",
        clearable=False,
        placeholder="Select State/Province",
        style={"width": "100%"},
        className="custom-input-box"
    )

    district_dropdown = dcc.Dropdown(
        id="district-dropdown",
        options=[
            {"label": "All Districts", "value": "All"},
            *[
                {"label": acronym, "value": acronym}
                for acronym in DISTRICT_STATES.keys()
            ]
        ],
        value="All",
        clearable=False,
        placeholder="Select District",
        style={"width": "100%"},
        className="custom-input-box"
    )
    percentile_toggle = dbc.Checklist(
        options=[{"label": "Filter Colors", "value": "filtered"}],
        value=[],  # Empty means global by default
        id="percentile-toggle",
        switch=True,
        style={"marginTop": "0px"}
    )

    x_axis_dropdown = dcc.Dropdown(
        id="x-axis-dropdown",
        options=[
            {"label": "Teleop", "value": "teleop_epa"},
            {"label": "Auto", "value": "auto_epa"},
            {"label": "Endgame", "value": "endgame_epa"},
            {"label": "Auto+Teleop", "value": "auto+teleop"},
            {"label": "Auto+Endgame", "value": "auto+endgame"},
            {"label": "Teleop+Endgame", "value": "teleop+endgame"},
            {"label": "Total", "value": "epa"},
        ],
        value="teleop_epa",
        clearable=False,
        style={"width": "130px"},
        className="custom-input-box"
    )

    y_axis_dropdown = dcc.Dropdown(
        id="y-axis-dropdown",
        options=[
            {"label": "Teleop", "value": "teleop_epa"},
            {"label": "Auto", "value": "auto_epa"},
            {"label": "Endgame", "value": "endgame_epa"},
            {"label": "Auto+Teleop", "value": "auto+teleop"},
            {"label": "Auto+Endgame", "value": "auto+endgame"},
            {"label": "Teleop+Endgame", "value": "teleop+endgame"},
            {"label": "Total", "value": "epa"},
        ],
        value="auto+endgame",
        clearable=False,
        style={"width": "130px"},
        className="custom-input-box"
    )

    axis_dropdowns = html.Div(
        id="axis-dropdown-container",
        children=[
            dbc.Row([
                dbc.Col(html.Label("X Axis:", style={"color": "var(--text-primary)"}), width="auto"),
                dbc.Col(x_axis_dropdown, width=3),
                dbc.Col(html.Label("Y Axis:", style={"color": "var(--text-primary)"}), width="auto"),
                dbc.Col(y_axis_dropdown, width=3),
            ], className="align-items-center")
        ],
        style={"display": "none", "marginBottom": "5px", "marginTop": "0px"}
    )

    search_input = dbc.Input(
        id="search-bar",
        placeholder="Search",
        type="text",
        className="custom-input-box",
        style={"width": "100%"},
    )

    filters_row = html.Div(
        [
            html.Div(teams_year_dropdown, style={"flex": "0 0 80px", "minWidth": "80px"}),
            html.Div(country_dropdown, style={"flex": "1 1 120px", "minWidth": "120px"}),
            html.Div(state_dropdown, style={"flex": "1 1 120px", "minWidth": "120px"}),
            html.Div(district_dropdown, style={"flex": "1 1 120px", "minWidth": "120px"}),
            html.Div(percentile_toggle, style={"flex": "0 0 120px", "minWidth": "120px", "display": "flex", "alignItems": "center"}),
            html.Div(search_input, style={"flex": "2 1 200px", "minWidth": "150px"}),
        ],
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "justifyContent": "center",
            "gap": "12px", # Add space between items
            "rowGap": "16px", # Add space between rows when wrapped
            "margin": "0 auto",
            "maxWidth": "1200px",
            "top": "60px",
            "zIndex": 10,
            "backgroundColor": "transparent",
            "padding": "10px 0", # Add vertical padding
        }
    )

    teams_table = dash_table.DataTable(
        id="teams-table",
        columns=[
            {"name": "ACE Rank", "id": "epa_rank"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "EPA", "id": "epa"},
            {"name": "×", "id": "mult_symbol"},
            {"name": "Confidence", "id": "confidence"},
            {"name": "=", "id": "equals_symbol"},
            {"name": "ACE", "id": "ace"},
            {"name": "Auto ACE", "id": "auto_epa"},
            {"name": "Teleop ACE", "id": "teleop_epa"},
            {"name": "Endgame ACE", "id": "endgame_epa"},
            {"name": "Record", "id": "record"},
        ],
        data=[],
        page_size=50,
        style_table={
            "overflowX": "auto", 
            "borderRadius": "10px", 
            "border": "none", 
            "backgroundColor": "var(--card-bg)",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)" # Added shadow
        },
        style_header={
            "backgroundColor": "var(--card-bg)",        # Match the table background
            "color": "var(--text)",
            "fontWeight": "bold",              # Keep column labels strong
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",  # Thin line under header only
            "padding": "6px",                  # Reduce banner size
            "fontSize": "13px",                # Optional: shrink text slightly
        },

        style_cell={
            "textAlign": "center",
            "padding": "10px",
            "border": "none",
            "fontSize": "14px",
            "backgroundColor": "var(--card-bg)",
        },
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "none",
            },
        ],
    )

    avatar_gallery = html.Div(
        id="avatar-gallery",
        className="d-flex flex-wrap justify-content-center",
        style={"gap": "5px", "padding": "1rem"}
    )
    tab_style = {"color": "var(--text-primary)", "backgroundColor": "transparent"}
    tabs = dbc.Tabs([
        dbc.Tab(label="Insights", tab_id="table-tab", active_label_style=tab_style),
        dbc.Tab(label="Avatars", tab_id="avatars-tab", active_label_style=tab_style),
        dbc.Tab(label="Bubble Chart", tab_id="bubble-chart-tab", active_label_style=tab_style),
    ], id="teams-tabs", active_tab="table-tab", className="mb-3")

    content = html.Div(id="teams-tab-content", children=[
        html.Div(id="teams-table-container", children=[teams_table]),
        html.Div(id="avatar-gallery", className="d-flex flex-wrap justify-content-center", style={"gap": "5px", "padding": "1rem", "display": "none"}),
        dcc.Graph(id="bubble-chart", style={"display": "none", "height": "700px"})
    ])

    return html.Div(
        [
            dcc.Location(id="teams-url", refresh=False),
            dcc.Store(id="user-session"),
            topbar(),
            dbc.Container([
                dbc.Row(id="top-teams-container", className="gx-4 gy-4 justify-content-center mb-5 d-none d-md-flex", justify="center"),
                filters_row,
                axis_dropdowns,
                epa_legend_layout(),
                tabs,
                content,
            ], style={
                "padding": "10px",
                "maxWidth": "1200px",
                "margin": "0 auto",
                "flexGrow": "1" # Added flex-grow
                }),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def events_layout(year=2025):
    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": str(yr), "value": yr} for yr in range(2000, 2026)],
        value=year,
        placeholder="Year",
        clearable=False
    )
    event_type_dropdown = dcc.Dropdown(
        id="event-type-dropdown",
        options=[
            {"label": "All", "value": "all"},
            {"label": "Season", "value": "season"},
            {"label": "Off-season", "value": "offseason"},
            {"label": "Regional", "value": "regional"},
            {"label": "District", "value": "district"},
            {"label": "Championship", "value": "championship"},
        ],
        value=["all"],
        multi=True,
        placeholder="Filter by Event Type",
        clearable=False,
        className="custom-input-box"
    )
    week_dropdown = dcc.Dropdown(
        id="week-dropdown",
        options=(
            [{"label": "All Wks", "value": "all"}] +
            [{"label": f"Wk {i+1}", "value": i} for i in range(0, 6)]
        ),
        placeholder="Week",
        value="all",
        clearable=False
    )
    district_dropdown = dcc.Dropdown(
        id="district-dropdown",
        options=[],
        placeholder="District",
        value="all",
        clearable=False,
        className="custom-input-box"
    )
    sort_toggle = dcc.RadioItems(
        id="sort-mode-toggle",
        options=[
            {"label": "Sort by Time", "value": "time"},
            {"label": "Sort A–Z", "value": "alpha"},
        ],
        value="time",
        labelStyle={"display": "inline-block", "margin-right": "15px", "color": "var(--text-primary)"},
        style={
            # Apply basic styling here, leave theme to CSS
            "padding": "4px 8px",
            "borderRadius": "6px"
        },
        className="custom-input-box"
    )
    search_input = dbc.Input(
        id="search-input",
        placeholder="Search",
        className="custom-input-box",
        type="text",
        style={
            "backgroundColor": "var(--input-bg)",
            "color": "var(--input-text)",
            "borderColor": "var(--input-border)",
        }
    )

    filters_row = html.Div(
        [
            html.Div(year_dropdown, style={"flex": "0 0 60px", "minWidth": "60px"}),
            html.Div(event_type_dropdown, style={"flex": "1 1 150px", "minWidth": "140px"}),
            html.Div(week_dropdown, style={"flex": "0 0 80px", "minWidth": "80px"}),
            html.Div(district_dropdown, style={"flex": "1 1 80px", "minWidth": "80px"}),
            html.Div(sort_toggle, style={"flex": "1 1 175px", "minWidth": "175px"}),
            html.Div(search_input, style={"flex": "2 1 100px", "minWidth": "100px"}),
        ],
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "justifyContent": "center",
            "gap": "12px",
            "rowGap": "16px",
            "margin": "0 auto",
            "maxWidth": "1000px",
            "top": "60px",
            "zIndex": 10,
            "backgroundColor": "transparent",
            "padding": "10px 0",
        }
    )
    tab_style = {"color": "var(--text-primary)", "backgroundColor": "transparent"}
    return html.Div(
        [
            topbar(),
            dcc.Store(id="event-favorites-store", storage_type="session"),
            dbc.Alert(id="favorite-event-alert", is_open=False, duration=3000, color="warning"),
            dbc.Container(
                [
                    dbc.Row(id="upcoming-events-container", className="justify-content-center"),
    
                    html.Div(id="ongoing-events-wrapper", children=[]),
    
                    filters_row,
                    dbc.Tabs(
                        id="events-tabs",
                        active_tab="cards-tab",
                        children=[
                            dbc.Tab(label="Cards", tab_id="cards-tab", active_label_style=tab_style),
                            dbc.Tab(label="Event Insights", tab_id="table-tab", active_label_style=tab_style),
                        ],
                        className="mb-4",
                    ),
                    html.Div(id="events-tab-content"),
                ],
                style={
                    "padding": "20px",
                    "maxWidth": "1200px",
                    "margin": "0 auto",
                    "flexGrow": "1" # Added flex-grow
                },
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def build_recent_events_section(team_key, team_number, epa_data, performance_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENTS_AWARDS, EVENT_RANKINGS):
    epa_data = epa_data or {}
    recent_rows = []
    year = performance_year 
    # Get the 3 most recent events by start date
    # Get team-attended events with start dates
    event_dates = []
    for ek, ev in EVENT_DATABASE.get(performance_year, {}).items():
        event_teams = EVENT_TEAMS.get(performance_year, {}).get(ek, [])
        if not any(int(t.get("tk", -1)) == team_number for t in event_teams):
            continue
    
        start_str = ev.get("sd")
        if start_str:
            try:
                dt = datetime.strptime(start_str, "%Y-%m-%d")
                event_dates.append((dt, ek))
            except ValueError:
                continue
    
    # Most recent 3 events they attended
    recent_event_keys = {ek for _, ek in sorted(event_dates, reverse=True)[:3]}

    for event_key, event in EVENT_DATABASE.get(year, {}).items():
        if event_key not in recent_event_keys:
            continue
    
        event_teams = EVENT_TEAMS.get(year, {}).get(event_key, [])
    
        # Skip if team wasn't on the team list
        if not any(int(t["tk"]) == team_number for t in event_teams if "tk" in t):
            continue
    
        # === Special check for Einstein (2025cmptx) ===
        if event_key == "2025cmptx":
            # Check if they played matches at Einstein
            einstein_matches = [
                m for m in EVENT_MATCHES.get(year, [])
                if m.get("ek") == "2025cmptx" and (
                    str(team_number) in m.get("rt", "").split(",") or
                    str(team_number) in m.get("bt", "").split(",")
                )
            ]

            # Check if they earned an award at Einstein
            einstein_awards = [
                a for a in EVENTS_AWARDS
                if a["tk"] == team_number and a["ek"] == "2025cmptx" and a["y"] == year
            ]
    
            # If neither, skip
            if not einstein_matches and not einstein_awards:
                continue

        event_name = event.get("n", "Unknown")
        loc = ", ".join(filter(None, [event.get("c", ""), event.get("s", ""), event.get("co", "")]))
        start_date = event.get("sd", "")
        event_url = f"/event/{event_key}"

        # Ranking
        ranking = EVENT_RANKINGS.get(year, {}).get(event_key, {}).get(team_number, {})
        rank_val = ranking.get("rk", "N/A")
        total_teams = len(event_teams)

        # Awards
        award_names = [
            a["an"] for a in EVENTS_AWARDS
            if a["tk"] == team_number and a["ek"] == event_key and a["y"] == year
        ]
        awards_line = html.Div([
            html.Span("Awards: ", style={"fontWeight": "bold"}),
            html.Span(", ".join(award_names))
        ]) if award_names else None

        rank_percent = rank_val / total_teams if isinstance(rank_val, int) and total_teams > 0 else None
        if rank_percent is not None:
            if rank_percent <= 0.25:
                rank_color = "green"
            elif rank_percent <= 0.5:
                rank_color = "orange"
            else:
                rank_color = "red"
            rank_str = html.Span([
                "Rank: ",
                html.Span(f"{rank_val}", style={"color": rank_color, "fontWeight": "bold"}),
                html.Span(f"/{total_teams}", style={"color": "var(text-muted)", "fontWeight": "normal"})
            ])
        else:
            rank_str = f"Rank: {rank_val}/{total_teams}"

        wins = ranking.get("w", "N/A")
        losses = ranking.get("l", "N/A")
        ties = ranking.get("t", "N/A")
        record = html.Span([
            html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#333"}),
            html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#333"}),
            html.Span(str(ties), style={"color": "gray", "fontWeight": "bold"})
        ])

        header = html.Div([
            html.A(str(year) + " " + event_name, href=event_url, style={"fontWeight": "bold", "fontSize": "1.1rem"}),
            html.Div(loc),
            html.Div(rank_str),
            html.Div([
                html.Span("Record: ", style={"marginRight": "5px"}),
                record,
                html.Div(awards_line),
            ]),
        ], style={"marginBottom": "10px"})

        matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
        matches = [
            m for m in matches
            if str(team_number) in m.get("rt", "").split(",") or str(team_number) in m.get("bt", "").split(",")
        ]

        def build_match_rows(matches):
            rows = []
            def parse_match_sort_key(match):
                comp_level_order = {"qm": 0, "sf": 1, "qf": 2, "f": 3}
                key = match.get("k", "").split("_")[-1].lower()
                cl = match.get("cl", "").lower()
            
                # Extract comp level from key or cl
                for level in comp_level_order:
                    if key.startswith(level):
                        # Remove the level prefix and 'm' if present, get the numeric part
                        remainder = key[len(level):].replace("m", "")
                        match_number = int(remainder) if remainder.isdigit() else 0
                        return (comp_level_order[level], match_number)
                
                # fallback to cl and mn if no match
                return (comp_level_order.get(cl, 99), match.get("mn", 9999))
            
            matches.sort(key=parse_match_sort_key)
                    
            def format_team_list(team_str):
                return "  ".join(f"[{t}](/team/{t})" for t in team_str.split(",") if t.strip().isdigit())

            def sum_epa(team_str):
                return sum(epa_data.get(t.strip(), {}).get("epa", 0) for t in team_str.split(",") if t.strip().isdigit())

        
            for match in matches:
                red_str = match.get("rt", "")
                blue_str = match.get("bt", "")
                red_score = match.get("rs", 0)
                blue_score = match.get("bs", 0)
                label = match.get("k", "").split("_", 1)[-1]

                if label.lower().startswith("sf") and "m" in label.lower():
                    # Always work with lower and reconstruct as upper for safety
                    label = label.lower().split("m")[0].upper()
                else:
                    label = label.upper()
                
                def get_team_epa_info(t_key):
                    t_data = epa_data.get(t_key.strip(), {})
                    return {
                        "epa": t_data.get("epa", 0),
                        "confidence": t_data.get("confidence", 0),
                        "consistency": t_data.get("consistency", 0)
                    }
                
                # Gather info for all teams
                red_team_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
                blue_team_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]
                
                if red_team_info and blue_team_info:
                    p_red, p_blue = predict_win_probability(red_team_info, blue_team_info)
                    is_red = str(team_number) in red_str
                    team_prob = p_red if is_red else p_blue
                    prediction = f"{team_prob:.0%}"
                    prediction_percent = round(team_prob * 100)
                else:
                    prediction = "N/A"
                    prediction_percent = None
        
                winner = match.get("wa", "Tie").title()
                youtube_id = match.get("yt")
                video_link = f"[Watch](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
        
                row = {
                    "Video": video_link,
                    "Match": label,
                    "Red Alliance": format_team_list(red_str),
                    "Blue Alliance": format_team_list(blue_str),
                    "Red Score": red_score,
                    "Blue Score": blue_score,
                    "Winner": winner,
                    "Prediction": prediction,
                    "Prediction %": prediction_percent,
                    "rowColor": "#ffe6e6" if winner == "Red" else "#e6f0ff" if winner == "Blue" else "white",
                }

                # Identify alliance and add underline flag
                if str(team_number) in red_str:
                    row["team_alliance"] = "Red"
                elif str(team_number) in blue_str:
                    row["team_alliance"] = "Blue"
                else:
                    row["team_alliance"] = None

                rows.append(row)

            return rows

        match_rows = build_match_rows(matches)

        table = html.Div(
            dash_table.DataTable(
                columns=[
                    {"name": "Video", "id": "Video", "presentation": "markdown"},
                    {"name": "Match", "id": "Match"},
                    {"name": "Red Alliance", "id": "Red Alliance", "presentation": "markdown"},
                    {"name": "Blue Alliance", "id": "Blue Alliance", "presentation": "markdown"},
                    {"name": "Red Score", "id": "Red Score"},
                    {"name": "Blue Score", "id": "Blue Score"},
                    {"name": "Winner", "id": "Winner"},
                    {"name": "Prediction", "id": "Prediction"},
                ],
                data=match_rows,
                page_size=10,
                style_table={
                    "overflowX": "auto", 
                    "borderRadius": "10px", 
                    "border": "none", 
                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)" # Added shadow
                },
                style_header={
                    "backgroundColor": "var(--card-bg)",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "borderBottom": "1px solid #ccc",
                    "padding": "6px",
                    "fontSize": "13px",
                },
                style_cell={
                    "backgroundColor": "white",
                    "textAlign": "center",
                    "padding": "10px",
                    "border": "none",
                    "fontSize": "14px",
                },
                style_data_conditional=[
                    {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "#ffe6e6"},
                    {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "#e6f0ff"},
                    {"if": {"filter_query": "{Prediction %} >= 45 && {Prediction %} <= 55", "column_id": "Prediction"}, "backgroundColor": "#ededd4", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} > 55 && {Prediction %} <= 65", "column_id": "Prediction"}, "backgroundColor": "#d4edda", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} > 65 && {Prediction %} <= 75", "column_id": "Prediction"}, "backgroundColor": "#b6dfc1", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} > 75 && {Prediction %} <= 85", "column_id": "Prediction"}, "backgroundColor": "#8fd4a8", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} > 85 && {Prediction %} <= 95", "column_id": "Prediction"}, "backgroundColor": "#68c990", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} > 95", "column_id": "Prediction"}, "backgroundColor": "#41be77", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} < 45 && {Prediction %} >= 35", "column_id": "Prediction"}, "backgroundColor": "#f8d7da", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} < 35 && {Prediction %} >= 25", "column_id": "Prediction"}, "backgroundColor": "#f1bfc2", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} < 25 && {Prediction %} >= 15", "column_id": "Prediction"}, "backgroundColor": "#eaa7aa", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} < 15 && {Prediction %} >= 5", "column_id": "Prediction"}, "backgroundColor": "#e39091", "fontWeight": "bold"},
                    {"if": {"filter_query": "{Prediction %} < 5", "column_id": "Prediction"}, "backgroundColor": "#dc7878", "fontWeight": "bold"},
                    {"if": {"filter_query": '{team_alliance} = "Red"', "column_id": "Red Score"}, "borderBottom": "1px solid black"},
                    {"if": {"filter_query": '{team_alliance} = "Blue"', "column_id": "Blue Score"}, "borderBottom": "1px solid black"},
                ]
            ),
            className="recent-events-table"
        )

        recent_rows.append(
            html.Div([
                header,
                table
            ])
        )

    return html.Div([
        html.H3("Recent Events", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
        html.Div(recent_rows)
    ])

def build_recent_matches_section(event_key, year, epa_data, EVENT_MATCHES):
    matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
    if not matches:
        return html.P("No matches available for this event.")

    epa_data = epa_data or {}

    # Sort matches by comp level and match number
    comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}

    def match_sort_key(m):
        key = m.get("k", "").split("_", 1)[-1].lower()

        # Initialize defaults
        level = 99
        set_num = 0
        match_num = 9999

        # Try parsing the key manually
        for prefix in ["qm", "qf", "sf", "f"]:
            if key.startswith(prefix):
                level = {"qm": 0, "qf": 1, "sf": 2, "f": 3}[prefix]
                rest = key[len(prefix):]
                if 'm' in rest:
                    set_part, match_part = rest.split('m', 1)
                    if match_part.isdigit():
                        match_num = int(match_part)
                    if set_part.isdigit():
                        set_num = int(set_part)
                break

        return (level, set_num, match_num)

    matches.sort(key=match_sort_key)
    qual_matches = [m for m in matches if m.get("cl") == "qm"]
    playoff_matches = [m for m in matches if m.get("cl") != "qm"]

    # Utilities
    def format_teams_markdown(team_str):
        return ", ".join(f"[{t}](/team/{t})" for t in team_str.split(",") if t.strip().isdigit())

    def get_team_epa_info(t_key):
        info = epa_data.get(t_key.strip(), {})
        return {
            "epa": info.get("epa", 0),
            "confidence": info.get("confidence", 0) / 100,  # normalize
            "consistency": info.get("consistency", 0),
        }


    def build_match_rows(match_list):
        rows = []
        for match in match_list:
            red_str = match.get("rt", "")
            blue_str = match.get("bt", "")
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            winner = match.get("wa", "")
            label = match.get("k", "").split("_", 1)[-1]

            if label.lower().startswith("sf") and "m" in label.lower():
                # Always work with lower and reconstruct as upper for safety
                label = label.lower().split("m")[0].upper()
            else:
                label = label.upper()

            red_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
            blue_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]

            p_red, p_blue = predict_win_probability(red_info, blue_info)
            if p_red == 0.5 and p_blue == 0.5:
                prediction = "N/A"
            else:
                prediction = f"🔴 {p_red:.0%} vs 🔵 {p_blue:.0%}"

            yid = match.get("yt")
            video_link = f"[Watch](https://youtube.com/watch?v={yid})" if yid else "N/A"

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Alliance": format_teams_markdown(red_str),
                "Blue Alliance": format_teams_markdown(blue_str),
                "Red Score": red_score,
                "Blue Score": blue_score,
                "Winner": winner.title() if winner else "N/A",
                "Prediction": prediction,
            })
        return rows

    # Data rows
    qual_data = build_match_rows(qual_matches)
    playoff_data = build_match_rows(playoff_matches)

    # Columns and styling
    match_columns = [
        {"name": "Video", "id": "Video", "presentation": "markdown"},
        {"name": "Match", "id": "Match"},
        {"name": "Red Alliance", "id": "Red Alliance", "presentation": "markdown"},
        {"name": "Blue Alliance", "id": "Blue Alliance", "presentation": "markdown"},
        {"name": "Red Score", "id": "Red Score"},
        {"name": "Blue Score", "id": "Blue Score"},
        {"name": "Winner", "id": "Winner"},
        {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
    ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"}
    style_header={
        "backgroundColor": "var(--card-bg)",        # Match the table background
        "fontWeight": "bold",              # Keep column labels strong
        "textAlign": "center",
        "borderBottom": "1px solid #ccc",  # Thin line under header only
        "padding": "6px",                  # Reduce banner size
        "fontSize": "13px",                # Optional: shrink text slightly
    }

    style_cell={
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }
    row_style = [
        {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "#ffe6e6"},
        {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "#e6f0ff"},
    ]

    qual_table = [
        html.H5("Qualification Matches", className="mb-3 mt-3"),
        dash_table.DataTable(
            columns=match_columns,
            data=qual_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if qual_data else [
        html.H5("Qualification Matches", className="mb-3 mt-3"),
        dbc.Alert("No qualification matches found.", color="info"),
    ]

    playoff_table = [
        html.H5("Playoff Matches", className="mb-3 mt-5"),
        dash_table.DataTable(
            columns=match_columns,
            data=playoff_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if playoff_data else [
        html.H5("Playoff Matches", className="mb-3 mt-5"),
        dbc.Alert("No playoff matches found.", color="info"),
    ]

    return html.Div([
        html.Div(qual_table, className="recent-events-table"),
        html.Div(playoff_table, className="recent-events-table")
    ])

def team_layout(team_number, year, TEAM_DATABASE, EVENT_DATABASE, EVENT_MATCHES, EVENTS_AWARDS, EVENT_RANKINGS, EVENT_TEAMS):

    user_id = session.get("user_id")
    is_logged_in = bool(user_id)
    
    # Check if team is already favorited
    is_favorited = False
    if is_logged_in:
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id FROM saved_items
                WHERE user_id = %s AND item_type = 'team' AND item_key = %s
            """, (user_id, str(team_number)))
            is_favorited = bool(cursor.fetchone())
        except Exception as e:
            print(f"Error checking favorite status: {e}")
        finally:
            conn.close()
    
    favorite_button = dbc.Button(
        "★" if is_favorited else "☆",
        id={"type": "favorite-team-btn", "key": str(team_number)},
        href="/login" if not is_logged_in else None,
        color="link",
        className="p-0",
        style={
            "position": "absolute",
            "top": "12px",
            "right": "16px",
            "fontSize": "2.2rem",
            "lineHeight": "1",
            "border": "none",
            "boxShadow": "none",
            "background": "none",
            "color": "#ffc107",  # golden star
            "zIndex": "10",
            "textDecoration": "none",
            "cursor": "pointer"
        }
    )

    # Add alert component without pattern matching
    favorite_alert = dbc.Alert(
        id="favorite-alert",
        is_open=False,
        duration=3000,
        color="warning"
    )
    
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_number = int(team_number)
    team_key = f"frc{team_number}"

    # Separate handling for performance year (used for ACE/stats) vs. awards/events year
    is_history = not year or str(year).lower() == "history"

    if is_history:
        year = None
        # fallback year to use for metrics (default to 2025 or latest available)
        performance_year = 2025
        available_years = sorted(TEAM_DATABASE.keys(), reverse=True)
        for y in available_years:
            if team_number in TEAM_DATABASE[y]:
                performance_year = y
                break
    else:
        try:
            year = int(year)
            performance_year = year
        except ValueError:
            return dbc.Alert("Invalid year provided.", color="danger")

    # Now safely use performance_year for stats lookups
    year_data = TEAM_DATABASE.get(performance_year)
    if not year_data:
        return dbc.Alert(f"Data for year {performance_year} not found.", color="danger")

    selected_team = year_data.get(team_number)
    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data for {performance_year}.", color="danger")

    # Calculate Rankings
    global_rank, country_rank, state_rank = calculate_single_rank(list(year_data.values()), selected_team)

    # ACE Display
    epa_value = selected_team.get("epa", None)
    epa_display = f"{epa_value:.2f}" if epa_value is not None else "N/A"

    auto_epa = selected_team.get("auto_epa", None)
    teleop_epa = selected_team.get("teleop_epa", None)
    endgame_epa = selected_team.get("endgame_epa", None)
    auto_epa_display = f"{auto_epa:.2f}" if auto_epa is not None else "N/A"
    teleop_epa_display = f"{teleop_epa:.2f}" if teleop_epa is not None else "N/A"
    endgame_epa_display = f"{endgame_epa:.2f}" if endgame_epa is not None else "N/A"

    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
        }
        for team_num, data in year_data.items()
    }

    epa_values = [data.get("normal_epa", 0) for data in year_data.values()]
    auto_values = [data.get("auto_epa", 0) for data in year_data.values()]
    teleop_values = [data.get("teleop_epa", 0) for data in year_data.values()]
    endgame_values = [data.get("endgame_epa", 0) for data in year_data.values()]
    ace_values = [data.get("epa", 0) for data in year_data.values()]

    percentiles_dict = {
        "epa": compute_percentiles(epa_values),
        "auto_epa": compute_percentiles(auto_values),
        "teleop_epa": compute_percentiles(teleop_values),
        "endgame_epa": compute_percentiles(endgame_values),
        "ace": compute_percentiles(ace_values),
    }


    nickname = selected_team.get("nickname", "Unknown")
    city = selected_team.get("city", "")
    state = selected_team.get("state_prov", "")
    country = selected_team.get("country", "")
    website = selected_team.get("website", "N/A")
    if website and website.startswith("http://"):
        website = "https://" + website[len("http://"):]
    
    avatar_url = get_team_avatar(team_number)
    
        # Get all years this team appears in, sorted
    years_participated = sorted([
        y for y in TEAM_DATABASE
        if team_number in TEAM_DATABASE[y]
    ])
    
    # Build clickable year links
    years_links = [
        html.A(
            str(yr),
            href=f"/team/{team_number}/{yr}",
            style={
                "marginRight": "0px",
                "color": "#007BFF",
                "textDecoration": "none",
            },
        )
        for yr in years_participated
    ] if years_participated else ["N/A"]
    
    # Add "History" button (same as before)
    years_links.append(
        html.A(
            "History",
            href=f"/team/{team_number}",
            style={
                "marginLeft": "0px",
                "color": "#007BFF",
                "fontWeight": "bold",
                "textDecoration": "none",
            },
        )
    )
    
    # Estimate rookie year just like before
    rookie_year = years_participated[0] if years_participated else year or 2025
    
    with open("team_data/notables_by_year.json", "r") as f:
        NOTABLES_DB = json.load(f)
    
    INCLUDED_CATEGORIES = {
        "notables_hall_of_fame": "Hall of Fame",
        "notables_world_champions": "World Champions",
    }
    
    def get_team_notables_grouped(team_number):
        team_key = f"frc{team_number}"
        category_data = {}
    
        for year, categories in NOTABLES_DB.items():
            for category, entries in categories.items():
                if category in INCLUDED_CATEGORIES:
                    for entry in entries:
                        if entry["team"] == team_key:
                            if category not in category_data:
                                category_data[category] = {"years": [], "video": None}
                            category_data[category]["years"].append(int(year))
                            if category == "notables_hall_of_fame" and "video" in entry:
                                category_data[category]["video"] = entry["video"]
        return category_data
    
    def generate_notable_badges(team_number):
        grouped = get_team_notables_grouped(team_number)
        badge_elements = []
    
        for category, info in sorted(grouped.items()):
            display_name = INCLUDED_CATEGORIES[category]
            year_list = ", ".join(str(y) for y in sorted(set(info["years"])))
            children = [
                html.Span("🏆", style={"fontSize": "1.2rem"}),
                html.Span(
                    f" {display_name} ({year_list})",
                    style={
                        "color": "var(--text-primary)",
                        "fontSize": "1.2rem",
                        "fontWeight": "bold",
                        "marginLeft": "5px"
                    }
                ),
            ]
    
            # Add video link if available (Hall of Fame only)
            if category == "notables_hall_of_fame" and info.get("video"):
                children.append(
                    html.A("Video", href=info["video"], target="_blank", style={
                        "marginLeft": "8px",
                        "fontSize": "1.1rem",
                        "textDecoration": "underline",
                        "color": "#007BFF",
                        "fontWeight": "normal"
                    })
                )
    
            badge_elements.append(
                html.Div(children, style={"display": "flex", "alignItems": "center", "marginBottom": "8px"})
            )
    
        return badge_elements

    badges = generate_notable_badges(team_number)
    
        # Team Info Card
    team_card = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H2(f"Team {team_number}: {nickname}", style={"color": "var(--text-primary)", "fontWeight": "bold"}),
                                *badges,
                                html.P([html.I(className="bi bi-geo-alt-fill"), f"📍 {city}, {state}, {country}"]),
                                html.P([html.I(className="bi bi-link-45deg"), "Website: ", 
                                        html.A(website, href=website, target="_blank", style={"color": "#007BFF", "textDecoration": "underline"})]),
                                html.P([html.I(className="bi bi-award"), f" Rookie Year: {rookie_year}"]),
                                html.Div(
                                    [
                                        html.I(className="bi bi-calendar"),
                                        " Years Participated: ",
                                        html.Div(
                                            years_links,
                                            style={"display": "flex", "flexWrap": "wrap", "gap": "8px", "textDecoration": "underline","color": "#007BFF"},
                                        ),
                                    ],
                                    style={"marginBottom": "10px"},
                                ),
                                favorite_button  # ⭐ Inserted here
                            ],
                            width=9,
                        ),
                        dbc.Col(
                            [
                                html.Img(
                                    src=avatar_url,
                                    alt=f"Team {team_number} Avatar",
                                    style={
                                        "maxWidth": "150px",
                                        "width": "100%",
                                        "height": "auto",
                                        "objectFit": "contain",
                                        "borderRadius": "10px",
                                        "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                        "marginLeft": "auto",
                                        "marginRight": "auto",
                                        "display": "block",
                                    },
                                ) if avatar_url else html.Div("No avatar available.", style={"color": "#777"}),
                            ],
                            width=3,
                            style={"textAlign": "center"},
                        )
                    ],
                    align="center",
                ),
            ],
            style={"fontSize": "1.1rem"}
        ),
        style={
            "marginBottom": "20px",
            "borderRadius": "10px",
            "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)",
            "backgroundColor": "var(--card-bg)"
        },
    )

    wins = selected_team.get("wins")
    losses = selected_team.get("losses")
    
    wins_str = str(wins) if wins is not None else "N/A"
    losses_str = str(losses) if losses is not None else "N/A"
    
    win_loss_ratio = html.Span([
        html.Span(wins_str, style={"color": "green", "fontWeight": "bold"}),
        html.Span(" / ", style={"color": "#333", "fontWeight": "bold"}),
        html.Span(losses_str, style={"color": "red", "fontWeight": "bold"})
    ])
    def build_rank_cards(performance_year, global_rank, country_rank, state_rank, country, state):
        def rank_card(label, rank, href):
            return dbc.Card(
                dbc.CardBody([
                    html.P(label, style={"fontSize": "1rem", "color": "#888", "marginBottom": "4px"}),
                    html.A(str(rank), href=href, style={
                        "fontSize": "1.6rem",
                        "fontWeight": "bold",
                        "color": "#007BFF",
                        "textDecoration": "none",
                    }),
                ]),
                style={
                    "textAlign": "center",
                    "borderRadius": "10px",
                    "boxShadow": "0px 2px 6px rgba(0,0,0,0.1)",
                    "backgroundColor": "var(--card-bg)",
                    "padding": "15px",
                }
            )
    
        return dbc.Row([
            dbc.Col(rank_card("Global Rank", global_rank, f"/teams?year={performance_year}&sort_by=epa"), width=4),
            dbc.Col(rank_card(f"{country} Rank", country_rank, f"/teams?year={performance_year}&country={country}&sort_by=epa"), width=4),
            dbc.Col(rank_card(f"{state} Rank", state_rank, f"/teams?year={performance_year}&country={country}&state={state}&sort_by=epa"), width=4),
        ], className="mb-4")


    def build_performance_metrics_card(selected_team, performance_year, percentiles_dict):
        def pill(label, value, color):
            return html.Span(f"{label}: {value}", style={
                "backgroundColor": color,
                "borderRadius": "6px",
                "padding": "4px 10px",
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "0.85rem",
                "marginRight": "6px",
                "display": "inline-block"
            })
    
        # Fixed colors to match screenshot styling
        auto_color = "#1976d2"     # Blue
        teleop_color = "#fb8c00"   # Orange
        endgame_color = "#388e3c"  # Green
        norm_color = "#d32f2f"    # Red
        conf_color = "#555"        # Gray for confidence
        total_color = "#673ab7"     # Deep Purple for normal EPA
    
        total = selected_team.get("epa", 0)
        normal_epa = selected_team.get("normal_epa", 0)
        confidence = selected_team.get("confidence", 0)
        auto = selected_team.get("auto_epa", 0)
        teleop = selected_team.get("teleop_epa", 0)
        endgame = selected_team.get("endgame_epa", 0)
        wins = selected_team.get("wins", 0)
        losses = selected_team.get("losses", 0)
        ties = selected_team.get("ties", 0)
        team_number = selected_team.get("team_number", "")
        nickname = selected_team.get("nickname", "")
    
        return html.Div([
            html.P([
                html.Span(f"Team {team_number} ({nickname}) had a record of ", style={"fontWeight": "bold"}),
                html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
                html.Span("-"),
                html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
                html.Span("-"),
                html.Span(str(ties), style={"color": "#777", "fontWeight": "bold"}),
                html.Span(f" in {performance_year}.")
            ], style={"marginBottom": "6px", "fontWeight": "bold"}),
            html.Div([
                pill("Auto", f"{auto:.1f}", auto_color),
                pill("Teleop", f"{teleop:.1f}", teleop_color),
                pill("Endgame", f"{endgame:.1f}", endgame_color),
                pill("EPA", f"{normal_epa:.2f}", norm_color),
                pill("Confidence", f"{confidence:.2f}", conf_color),
                pill("ACE", f"{total:.1f}", total_color),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"})
        ])


    rank_card = build_rank_cards(
        performance_year,
        global_rank,
        country_rank,
        state_rank,
        country,
        state
    )

    performance_metrics_card = build_performance_metrics_card(
        selected_team,
        performance_year,
        percentiles_dict
    )

    events_data = []
    
    year_keys = [year] if year else list(EVENT_DATABASE.keys())
    participated_events = []
    
    for year_key in year_keys:
        for event_key, event in EVENT_DATABASE.get(year_key, {}).items():
            team_list = EVENT_TEAMS.get(year_key, {}).get(event_key, [])
            if any(t["tk"] == team_number for t in team_list):
                # Special case: Einstein (2025cmptx) filter
                if event_key == "2025cmptx":
                    # Check if team played matches on Einstein
                    einstein_matches = [
                        m for m in EVENT_MATCHES.get(year, [])
                        if m.get("ek") == "2025cmptx" and (
                            str(team_number) in m.get("rt", "").split(",") or
                            str(team_number) in m.get("bt", "").split(",")
                        )
                    ]
    
                    # Check if team won an award at Einstein
                    einstein_awards = [
                        aw for aw in EVENTS_AWARDS
                        if aw["tk"] == team_number and aw["ek"] == "2025cmptx" and aw["y"] == year_key
                    ]
    
                    # Skip Einstein if no matches and no awards
                    if not einstein_matches and not einstein_awards:
                        continue
    
                participated_events.append((year_key, event_key, event))
    
    # Sort events by start date
    participated_events.sort(key=lambda tup: tup[2].get("sd", ""), reverse=True)
    
    # Map event keys to names
    event_key_to_name = {ek: e.get("n", "Unknown") for _, ek, e in participated_events}
    
    # Build event rows
    for year_key, event_key, event in participated_events:
        event_name = event.get("n", "")
        location = f"{event.get('c', '')}, {event.get('s', '')}".strip(", ")
        start_date = event.get("sd", "")
        end_date = event.get("ed", "")
        event_url = f"https://www.peekorobo.com/event/{event_key}"
    
        # Rank
        rank = None
        rankings = EVENT_RANKINGS.get(year_key, {}).get(event_key, {})
        if team_number in rankings:
            rank = rankings[team_number].get("rk")
            if rank:
                event_name += f" (Rank: {rank})"
    
        events_data.append({
            "event_name": f"[{event_name}]({event_url})",
            "event_location": location,
            "start_date": start_date,
            "end_date": end_date,
        })
    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name", "presentation": "markdown"},
            {"name": "Location", "id": "event_location"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        data=events_data,
        page_size=5,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)", "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"},
        style_header={
            "backgroundColor": "var(--card-bg)",        # Match the table background
            "fontWeight": "bold",              # Keep column labels strong
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",  # Thin line under header only
            "padding": "6px",                  # Reduce banner size
            "fontSize": "13px",                # Optional: shrink text slightly
        },

        style_cell={
            "backgroundColor": "var(--card-bg)",
            "textAlign": "center",
            "padding": "10px",
            "border": "none",
            "fontSize": "14px",
        },
        style_cell_conditional=[{"if": {"column_id": "event_name"}, "textAlign": "center"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )

    
    # --- Awards Section ---
    team_awards = [
        row for row in EVENTS_AWARDS
        if row["tk"] == team_number and (not year or row["y"] == year)
    ]
    
    team_awards.sort(key=lambda aw: aw["y"], reverse=True)
    
    awards_data = [
        {
            "award_name": aw["an"],
            "event_name": event_key_to_name.get(aw["ek"], "Unknown Event"),
            "award_year": aw["y"]
        }
        for aw in team_awards
    ]
    
    awards_table = dash_table.DataTable(
        columns=[
            {"name": "Award Name", "id": "award_name"},
            {"name": "Event Name", "id": "event_name"},
            {"name": "Year", "id": "award_year"},
        ],
        data=awards_data,
        page_size=5,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)", "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"},
        style_header={
            "backgroundColor": "var(--card-bg)",        # Match the table background
            "fontWeight": "bold",              # Keep column labels strong
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",  # Thin line under header only
            "padding": "6px",                  # Reduce banner size
            "fontSize": "13px",                # Optional: shrink text slightly
        },

        style_cell={
            "backgroundColor": "var(--card-bg)",
            "textAlign": "center",
            "padding": "10px",
            "border": "none",
            "fontSize": "14px",
        },
        style_cell_conditional=[{"if": {"column_id": "award_name"}, "textAlign": "left"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    # --- Blue Banners Section ---
    blue_banner_keywords = ["chairman's", "impact", "woodie flowers", "winner"]
    blue_banners = []
    
    for award in team_awards:
        name_lower = award["an"].lower()
        if any(keyword in name_lower for keyword in blue_banner_keywords):
            event_key = award["ek"]
            year_str = str(award["y"])
            event = EVENT_DATABASE.get(int(year_str), {}).get(event_key, {})
            event_name = event.get("n", "Unknown Event")
            full_event_name = f"{year_str} {event_name}"
    
            blue_banners.append({
                "award_name": award["an"],
                "event_name": full_event_name,
                "event_key": event_key
            })
    
    blue_banner_section = html.Div(
        [
            html.Div(
                [
                    html.A(
                        href=f"/event/{banner['event_key']}",
                        children=[
                            html.Div(
                                [
                                    html.Img(
                                        src="/assets/banner.png",
                                        style={"width": "120px", "height": "auto", "position": "relative"},
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                banner["award_name"],
                                                style={"fontSize": "0.8rem", "color": "white", "fontWeight": "bold", "textAlign": "center", "marginBottom": "3px"},
                                            ),
                                            html.P(
                                                banner["event_name"],
                                                style={"fontSize": "0.6rem", "color": "white", "textAlign": "center"},
                                            ),
                                        ],
                                        style={"position": "absolute", "top": "50%", "left": "50%", "transform": "translate(-50%, -50%)"},
                                    ),
                                ],
                                style={"position": "relative", "marginBottom": "15px"},
                            ),
                        ],
                        style={"textDecoration": "none"},
                    )
                    for banner in blue_banners
                ],
                style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center", "gap": "10px"},
            ),
        ],
        style={"marginBottom": "15px", "borderRadius": "8px", "backgroundColor": "var(--card-bg)", "padding": "10px"},
    )

    
    return html.Div(
        [
            topbar(),
            dcc.Store(id="user-session", data={"user_id": user_id} if user_id else None),  # Add this line
            dbc.Alert(id="favorite-alert", is_open=False, duration=3000, color="warning"),
            dbc.Container(
                [
                    team_card,
                    rank_card,
                    performance_metrics_card,
                    html.Hr(),
                    build_recent_events_section(team_key, team_number, epa_data, performance_year,EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENTS_AWARDS, EVENT_RANKINGS),
                    html.H3("Events", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Awards", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
                    awards_table,
                    blue_banner_section,
                    html.Br(),
                ],
                style={
                    "padding": "20px",
                    "maxWidth": "1200px",
                    "margin": "0 auto",
                    "flexGrow": "1"
                },
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

def compare_layout():
    # Team options will be filled by callback or server-side, so use empty list for now
    team_dropdown = dcc.Dropdown(
        id="compare-teams",
        options=[],
        placeholder="Select teams to compare",
        className="custom-input-box",
        style={"width": "100%"},
        searchable=True,
        multi=True,
        value=[1323, 2056] # Set default teams
    )

    year_dropdown = dcc.Dropdown(
        id="compare-year",
        options=[{"label": str(y), "value": y} for y in range(1992, 2026)],
        value=2025,
        clearable=False,
        placeholder="Select Year",
        className="custom-input-box",
        style={"width": "100%"},
    )

    return html.Div([
        topbar(),
        dbc.Container([
            html.H2("Compare Teams", className="text-center my-4"),
            dbc.Row([
                dbc.Col([
                    html.Label("Teams", style={"color": "var(--text-primary)", "fontWeight": "bold"}),
                    team_dropdown
                ], width=7),
                dbc.Col([
                    html.Label("Year", style={"color": "var(--text-primary)", "fontWeight": "bold"}),
                    year_dropdown
                ], width=3),
            ], className="mb-4 justify-content-center"),
            html.Hr(),
            html.Div(id="compare-output-section", children=[]) # Make this div initially empty
        ], style={"maxWidth": "1000px", "margin": "0 auto", "padding": "20px", "flexGrow": "1"}),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer
    ])