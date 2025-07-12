import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from datagather import frc_games,COUNTRIES,STATES,DISTRICT_STATES,get_team_avatar,get_team_years_participated
from flask import session
from datetime import datetime, date
from utils import predict_win_probability, predict_win_probability_adaptive, learn_from_match_outcome, get_event_prediction_confidence, get_event_learning_stats, get_prediction_difference, compute_percentiles, pill
import json
import os

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
                                    style={"height": "40px", "width": "auto", "marginRight": "0px"},
                                ),
                                href="/",
                                className="navbar-brand-custom mobile-navbar-col",
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
                                    style={"width": "160px"},
                                    className="mobile-search-group",
                                ),
                                html.Div(id="mobile-search-preview", style={
                                    "backgroundColor": "var(--card-bg)",
                                    #"border": "1px solid var(--card-bg)",
                                    "borderRadius": "8px",
                                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                    "marginTop": "5px",
                                    "padding": "0px",
                                    "maxHeight": "200px",
                                    "overflowY": "auto",
                                    "overflowX": "hidden",
                                    "width": "180px",
                                    "zIndex": "9999",
                                    "position": "absolute",
                                    "left": "0",
                                    "right": "0",
                                    "top": "100%",
                                    "display": "none",
                                }),
                            ],
                            width="auto",
                            className="d-md-none align-self-center",
                            style={"position": "relative", "textAlign": "center"},
                        ),
                        dbc.Col(
                            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0, className="navbar-toggler-custom",style={"padding": "0px"}),
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
                                                    dbc.DropdownMenuItem("FRCManual", href="https://www.frcmanual.com/", target="_blank"),
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
                    "| View Peekorobo on ",
                    html.A("GitHub", href="https://github.com/rhettadam/peekorobo", target="_blank", style={"color": "#3366CC", "textDecoration": "line"}),
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
                # Left Section: Logo
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.A(
                                    html.Img(
                                        src="/assets/home.png",
                                        className='homelogo',
                                        style={
                                            "width": "100%",
                                            "maxWidth": "700px",
                                            "height": "auto",
                                        },
                                    ),
                                    href="https://github.com/rhettadam/peekorobo",
                                    target="_blank",
                                    rel="noopener noreferrer"
                                ),
                            ],
                            className="logo-container",
                            style={
                                "textAlign": "center",
                                "display": "flex",
                                "alignItems": "center",
                                "justifyContent": "center",
                                "height": "100%"
                            }
                        )
                    ],
                    width=6,
                    className="desktop-left-section"
                ),
                # Right Section: Navigation
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.H1(
                                    [
                                        "Data-Driven ",
                                        html.Span("FRC", className="gradient-hover"),
                                        " Insights"
                                    ],
                                    style={
                                        "fontSize": "3.5rem",
                                        "fontWeight": "bold",
                                        "color": "var(--text-primary)",
                                        "marginBottom": "1rem",
                                        "textAlign": "center"
                                    },
                                ),
                                html.P(
                                    [
                                        "Explore teams, events, and matches from the ",
                                        html.A(
                                            "FIRST Robotics Competition",
                                            href="https://www.firstinspires.org/robotics/frc",
                                            target="_blank",
                                            rel="noopener noreferrer",
                                            className="frc-link"
                                        )
                                    ],
                                    style={
                                        "fontSize": "1.3rem",
                                        "color": "var(--text-secondary)",
                                        "marginBottom": "1.2rem",
                                        "textAlign": "center",
                                        "lineHeight": "1.4"
                                    },
                                ),
                                html.Div(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-users me-2"),
                                                "Teams"
                                            ],
                                            href="/teams",
                                            color="warning",
                                            outline=True,
                                            size="lg",
                                            className="custom-view-btn",
                                            style={
                                                "fontSize": "1.2rem",
                                                "fontWeight": "bold",
                                                "padding": "1rem 2rem",
                                                "width": "240px"
                                            },
                                        ),
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-calendar-alt me-2"),
                                                "Events"
                                            ],
                                            href="/events",
                                            color="warning",
                                            outline=True,
                                            size="lg",
                                            className="custom-view-btn",
                                            style={
                                                "fontSize": "1.2rem",
                                                "fontWeight": "bold",
                                                "padding": "1rem 2rem",
                                                "width": "240px"
                                            },
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "justifyContent": "center",
                                        "gap": "2rem",
                                        "marginTop": "0.5rem"
                                    }
                                ),
                            ],
                            className="navigation-container",
                            style={
                                "display": "flex",
                                "flexDirection": "column",
                                "justifyContent": "center",
                                "height": "100%"
                            }
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
        "flexGrow": "1"
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
            footer,
        ]
    )

def challenge_details_layout(year):
    game = frc_games.get(
        year,
        {"name": "Unknown Game", "video": "#", "logo": "/assets/placeholder.png", "manual": "#", "summary": "No summary available."}
    )

    # Check for year-specific banner
    banner_path = f"/assets/logos/banner.png"
    has_banner = os.path.exists(banner_path)
    banner_img = html.Img(
        src=f"/{banner_path}",
        style={
            "width": "100%",
            "height": "auto",
            "objectFit": "cover",
            "marginBottom": "20px",
            "borderRadius": "10px" # Optional: match card corners
        },
        alt=f"{year} Challenge Banner",
    ) if has_banner else None

    # --- Stats Section ---
    # Count number of events, teams, and matches for the year
    num_events = num_teams = num_matches = 'N/A'
    try:
        if year == 2025:
            from peekorobo import EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES
            year_events = EVENT_DATABASE.get(year, {})
            year_event_keys = list(year_events.keys())
            num_events = len(year_event_keys)
            team_set = set()
            for ek in year_event_keys:
                teams = EVENT_TEAMS.get(year, {}).get(ek, [])
                for t in teams:
                    if isinstance(t, dict) and 'tk' in t:
                        team_set.add(t['tk'])
            num_teams = len(team_set)
            year_matches = EVENT_MATCHES.get(year, [])
            num_matches = len(year_matches)
        else:
            from datagather import load_year_data
            _, event_data, event_teams, _, _, event_matches = load_year_data(year)
            num_events = len(event_data)
            team_set = set()
            for ek, teams in event_teams.items():
                for t in teams:
                    if isinstance(t, dict) and 'tk' in t:
                        team_set.add(t['tk'])
            num_teams = len(team_set)
            num_matches = len(event_matches)
    except Exception:
        pass

    stats_row = dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.Div(str(num_teams), style={
                    "fontSize": "2.5rem",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "marginBottom": "0.25rem",
                    "whiteSpace": "nowrap"
                }),
                html.Div("Teams", style={
                    "fontSize": "1.1rem",
                    "color": "var(--text-secondary)",
                    "textAlign": "center",
                    "whiteSpace": "nowrap"
                })
            ])
        ], className="shadow-sm stat-card", style={
            "borderRadius": "12px",
            "padding": "1.2rem 0.5rem",
            "minWidth": "100px",
            "background": "rgba(255,255,255,0.02)",
            "border": "1.5px solid #444"
        }), xs=12, md=4, style={"marginBottom": "1rem"}),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.Div(str(num_events), style={
                    "fontSize": "2.5rem",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "marginBottom": "0.25rem",
                    "whiteSpace": "nowrap"
                }),
                html.Div("Events", style={
                    "fontSize": "1.1rem",
                    "color": "var(--text-secondary)",
                    "textAlign": "center",
                    "whiteSpace": "nowrap"
                })
            ])
        ], className="shadow-sm stat-card", style={
            "borderRadius": "12px",
            "padding": "1.2rem 0.5rem",
            "minWidth": "100px",
            "background": "rgba(255,255,255,0.02)",
            "border": "1.5px solid #444"
        }), xs=12, md=4, style={"marginBottom": "1rem"}),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.Div(str(num_matches), style={
                    "fontSize": "2.5rem",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "marginBottom": "0.25rem",
                    "whiteSpace": "nowrap"
                }),
                html.Div("Matches", style={
                    "fontSize": "1.1rem",
                    "color": "var(--text-secondary)",
                    "textAlign": "center",
                    "whiteSpace": "nowrap"
                })
            ])
        ], className="shadow-sm stat-card", style={
            "borderRadius": "12px",
            "padding": "1.2rem 0.5rem",
            "minWidth": "160px",
            "background": "rgba(255,255,255,0.02)",
            "border": "1.5px solid #444"
        }), xs=12, md=4),
    ], className="mb-4 justify-content-center", style={"maxWidth": "600px", "margin": "0 auto"})

    # --- Field Diagram Section ---
    field_img_path = f"/assets/logos/{year}field.png"
    field_img_exists = os.path.exists(f"assets/logos/{year}field.png")
    field_diagram = (
        html.Div([
            html.H5("Field Diagram", className="text-center mt-4 mb-2"),
            html.Img(
                src=field_img_path,
                style={
                    "display": "block",
                    "margin": "0 auto",
                    "maxWidth": "100%",
                    "maxHeight": "350px",
                    "borderRadius": "10px",
                    "boxShadow": "0px 2px 8px rgba(0,0,0,0.12)"
                },
                alt=f"{year} FRC Field"
            ),
            html.Div(
                className="text-center mt-2"
            )
        ]) if field_img_exists else None
    )

    # Manual Button (now to be placed below the logo)
    manual_button = html.Div(
        dbc.Button(
            "View Game Manual",
            href=game["manual"],
            target="_blank",
            color="warning",
            outline=True,
            className="custom-view-btn custom-view-btn-large",
            style={
                "marginTop": "1rem"
            },
        ),
        className="text-center mb-4",
        style={"marginTop": "1rem"}
    )

    # --- Collage Layout ---
    # Hero Section: Logo + Summary/Stats side by side
    hero_row = dbc.Row([
        dbc.Col([
            html.Img(
                src=game["logo"],
                style={
                    "display": "block",
                    "margin": "0 auto 1.5rem auto",
                    "maxWidth": "260px",
                    "borderRadius": "16px",
                    "boxShadow": "0px 2px 12px rgba(0,0,0,0.13)"
                },
                alt=game["name"],
            ),
            manual_button,
        ], md=5, xs=12, style={"textAlign": "center", "marginBottom": "2rem", "display": "flex", "flexDirection": "column", "justifyContent": "center"}),
        dbc.Col([
            html.H2(f"{game['name']} ({year})", className="card-title text-center mb-3", style={"fontWeight": "bold"}),
            html.P(
                game.get("summary", "No summary available."),
                className="card-text text-center mb-4",
                style={
                    "fontSize": "1.1rem",
                    "lineHeight": "1.6",
                    "color": "var(--text-primary)",
                    "marginBottom": "2rem",
                    "maxWidth": "600px",
                    "marginLeft": "auto",
                    "marginRight": "auto"
                },
            ),
            stats_row,
        ], md=7, xs=12, style={"display": "flex", "flexDirection": "column", "justifyContent": "center", "marginBottom": "2rem"}),
    ], align="center", className="mb-4", style={"minHeight": "340px"})

    # Collage Section: Field Diagram + Reveal Video side by side
    collage_row = dbc.Row([
        dbc.Col([
            field_diagram,
        ], md=6, xs=12, style={"marginBottom": "2rem"}),
        dbc.Col([
            html.H5("Watch the official game reveal:", className="text-center mb-3 mt-2"),
            html.Div(
                html.A(
                    html.Img(
                        src=f"https://img.youtube.com/vi/{game['video'].split('=')[-1]}/0.jpg",
                        style={
                            "maxWidth": "100%",
                            "borderRadius": "8px",
                            "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)",
                            "margin": "0 auto",
                            "display": "block"
                        },
                    ),
                    href=game["video"],
                    target="_blank",
                    style={
                        "display": "block",
                        "margin": "0 auto"
                    },
                ),
                className="text-center",
            ),
        ], md=6, xs=12, style={"marginBottom": "2rem"}),
    ], className="mb-4", style={"background": "var(--card-bg)", "borderRadius": "12px", "padding": "2rem 1rem"})

    return html.Div(
        [
            topbar(),
            dbc.Container(
                [
                    banner_img if banner_img else None,
                    hero_row,
                    collage_row,
                ],
                style={
                    "maxWidth": "1000px",
                    "margin": "0 auto",
                    "padding": "32px 10px 20px 10px",
                    "flexGrow": "1",
                },
            ),
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
                    style={
                        "width": "100%",
                        "height": "100%",
                        "border": "none",
                        "minHeight": "0",
                        "flexGrow": 1,
                        "display": "block"
                    },
                ),
            ],
            fluid=True,
            style={
                "flexGrow": "1",
                "padding": "0",
                "margin": "0",
                "height": "100%",
                "minHeight": "0",
                "display": "flex",
                "flexDirection": "column"
            }
        ),
        footer,
    ], style={
        "minHeight": "100vh",
        "display": "flex",
        "flexDirection": "column",
        "padding": "0",
        "margin": "0",
        "overflow": "hidden"
    })

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
                            src="/assets/home.png",
                            style={"width": "100%", "maxWidth": "500px", "marginBottom": "30px"},
                            className="home-image"
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
                    # Learning progress indicator
                    dbc.Alert(
                        id="learning-progress-alert",
                        is_open=False,
                        color="info",
                        className="mb-3",
                        children=[
                            html.H6("🤖 Adaptive Learning Active", className="mb-2"),
                            html.P(id="learning-stats-text", className="mb-0", style={"fontSize": "0.9rem"})
                        ]
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
            footer,
        ]
    )

def build_recent_events_section(team_key, team_number, team_epa_data, performance_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS):
    epa_data = team_epa_data or {}

    recent_rows = []
    year = performance_year 
    # Get all events the team attended with start dates
    event_dates = []
    
    year_events = EVENT_DATABASE.get(performance_year, {}) if isinstance(EVENT_DATABASE, dict) else EVENT_DATABASE

    # Detect data structure: 2025 has year keys, 2024 doesn't
    has_year_keys = isinstance(EVENT_TEAMS, dict) and performance_year in EVENT_TEAMS
    
    for ek, ev in year_events.items():
        # Handle both data structures
        if has_year_keys:
            # 2025 structure: EVENT_TEAMS[year][event_key]
            event_teams = EVENT_TEAMS.get(performance_year, {}).get(ek, [])
        else:
            # 2024 structure: EVENT_TEAMS[event_key]
            event_teams = EVENT_TEAMS.get(ek, []) if isinstance(EVENT_TEAMS, dict) else EVENT_TEAMS
        
        if not any(int(t.get("tk", -1)) == team_number for t in event_teams):
            continue
        
        start_str = ev.get("sd")
        if start_str:
            try:
                dt = datetime.strptime(start_str, "%Y-%m-%d")
                event_dates.append((dt, ek, ev)) # Store event data as well
            except ValueError:
                print(f"  Failed to parse date {start_str} for event {ek}")
                continue
        else:
            print(f"  No start date for event {ek}")
    
    # Sort all attended events by most recent first (no slicing)
    recent_events_sorted = sorted(event_dates, key=lambda x: x[0], reverse=True)
    
    # Iterate through sorted events to build the section
    for dt, event_key, event in recent_events_sorted:

        # Handle both data structures
        if has_year_keys:
            # 2025 structure: EVENT_TEAMS[year][event_key]
            event_teams = EVENT_TEAMS.get(year, {}).get(event_key, [])
        else:
            # 2024 structure: EVENT_TEAMS[event_key]
            event_teams = EVENT_TEAMS.get(event_key, []) if isinstance(EVENT_TEAMS, dict) else EVENT_TEAMS
    
        # Skip if team wasn't on the team list
        if not any(int(t["tk"]) == team_number for t in event_teams if "tk" in t):
            continue
    
        # === Special check for Einstein (2025cmptx) ===
        if event_key == "2025cmptx":
            # Handle both data structures for matches
            if has_year_keys:
                # 2025 structure: EVENT_MATCHES[year]
                year_matches = EVENT_MATCHES.get(year, [])
            else:
                # 2024 structure: EVENT_MATCHES is a list
                year_matches = EVENT_MATCHES
            einstein_matches = [
                m for m in year_matches
                if m.get("ek") == "2025cmptx" and (
                    str(team_number) in m.get("rt", "").split(",") or
                    str(team_number) in m.get("bt", "").split(",")
                )
            ]

            # EVENT_AWARDS is always a list
            einstein_awards = [
                a for a in EVENT_AWARDS
                if a["tk"] == team_number and a["ek"] == "2025cmptx" and a["y"] == year
            ]
    
            # If neither, skip
            if not einstein_matches and not einstein_awards:
                continue

        event_name = event.get("n", "Unknown")
        loc = ", ".join(filter(None, [event.get("c", ""), event.get("s", ""), event.get("co", "")]))
        start_date = event.get("sd", "")
        event_url = f"/event/{event_key}"

        # Handle both data structures for rankings
        if has_year_keys:
            # 2025 structure: EVENT_RANKINGS[year][event_key]
            ranking = EVENT_RANKINGS.get(year, {}).get(event_key, {}).get(team_number, {})
        else:
            # 2024 structure: EVENT_RANKINGS[event_key]
            ranking = EVENT_RANKINGS.get(event_key, {}).get(team_number, {}) if isinstance(EVENT_RANKINGS, dict) else {}
        rank_val = ranking.get("rk", "N/A")
        total_teams = len(event_teams)

        # EVENT_AWARDS is always a list
        award_names = [
            a["an"] for a in EVENT_AWARDS
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
            html.Span("-", style={"color": "#777"}),
            html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#777"}),
            html.Span(str(ties), style={"color": "gray", "fontWeight": "bold"})
        ])

        # Get event-specific EPA data for 2025 events
        event_epa_pills = None
        if year >= 2015:
            # Access event_epas from the specific team's data within the epa_data dictionary
            team_specific_event_epas = epa_data.get(str(team_number), {}).get("event_epas", [])
            event_epa = next((e for e in team_specific_event_epas if str(e.get("event_key")) == str(event_key)), None)
            if event_epa:
                # Fixed colors to match screenshot styling for consistency
                auto_color = "#1976d2"     # Blue
                teleop_color = "#fb8c00"   # Orange
                endgame_color = "#388e3c"  # Green
                norm_color = "#d32f2f"    # Red (for overall EPA)
                conf_color = "#555"   
                total_color = "#673ab7"  
                     # Gray for confidence
                event_epa_pills = html.Div([
                    html.Div([
                        pill("Auto", f"{event_epa['auto']:.1f}", auto_color),
                        pill("Teleop", f"{event_epa['teleop']:.1f}", teleop_color),
                        pill("Endgame", f"{event_epa['endgame']:.1f}", endgame_color),
                        pill("EPA", f"{event_epa['overall']:.1f}", norm_color),
                        pill("Conf", f"{event_epa['confidence']:.2f}", conf_color),
                        pill("ACE", f"{event_epa['actual_epa']:.1f}", total_color),
                        
                    ], style={
                        "display": "flex", 
                        "alignItems": "center", 
                        "flexWrap": "wrap", 
                        "marginBottom": "5px"
                    }),
                ], style={"marginBottom": "10px"})
            else:
                print(f"No event EPA found for {event_key}")
        else:
            event_epa_pills = html.Div() # Ensure it's an empty div if no data, not None

        header = html.Div([
            html.Div([
                html.A(str(year) + " " + event_name, href=event_url, style={"fontWeight": "bold", "fontSize": "1.1rem"}),
                dbc.Button(
                    "Playlist",
                    id={"type": "recent-event-playlist", "event_key": event_key, "team_number": team_number},
                    color="warning",
                    outline=True,
                    size="sm",
                    className="custom-view-btn",
                    style={
                        "fontSize": "1.2rem",
                        "fontWeight": "bold",
                        "padding": "1rem 2rem",
                        "width": "100px",
                        "marginLeft": "10px"
                    }
                )
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(loc),
            html.Div(rank_str),
            html.Div([
                html.Span("Record: ", style={"marginRight": "5px"}),
                record,
                html.Div(awards_line),
                event_epa_pills if event_epa_pills else None,
            ]),
        ], style={"marginBottom": "10px"})

        # Handle both data structures for matches
        if has_year_keys:
            # 2025 structure: EVENT_MATCHES[year]
            year_matches = EVENT_MATCHES.get(year, [])
        else:
            # 2024 structure: EVENT_MATCHES is a list
            year_matches = EVENT_MATCHES
        matches = [m for m in year_matches if m.get("ek") == event_key]
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
        
            for match in matches:
                red_str = match.get("rt", "")
                blue_str = match.get("bt", "")
                red_score = match.get("rs", 0)
                blue_score = match.get("bs", 0)
                if red_score <= 0 or blue_score <= 0:
                    red_score = 0
                    blue_score = 0
                label = match.get("k", "").split("_", 1)[-1]

                if label.lower().startswith("sf") and "m" in label.lower():
                    label = label.lower().split("m")[0].upper()
                else:
                    label = label.upper()

                # Add match link
                match_url = f"/match/{event_key}/{label}"
                match_label_md = f"[{label}]({match_url})"
                
                def get_team_epa_info(t_key):
                    t_data = epa_data.get(t_key.strip(), {})
                    event_epa = next((e for e in t_data.get("event_epas", []) if e.get("event_key") == event_key), None)
                    if event_epa and event_epa.get("overall", 0) != 0:
                        return {
                            "team_number": int(t_key.strip()),
                            "epa": event_epa.get("overall", 0),
                            "confidence": event_epa.get("confidence", 0.7),
                            "consistency": event_epa.get("consistency", 0)
                        }
                    if t_data.get("epa") not in (None, ""):
                        epa_val = t_data.get("epa", 0)
                        conf_val = t_data.get("confidence", 0.7)
                        return {
                            "team_number": int(t_key.strip()),
                            "epa": epa_val,
                            "confidence": conf_val,
                            "consistency": t_data.get("consistency", 0)
                        }
                    return {"team_number": int(t_key.strip()), "epa": 0, "confidence": 0, "consistency": 0}
                red_team_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
                blue_team_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]
                if red_team_info and blue_team_info:
                    # Use adaptive prediction that learns from previous matches
                    p_red, p_blue = predict_win_probability_adaptive(red_team_info, blue_team_info, event_key, match.get("k", ""))
                    # Learn from completed matches
                    winner = match.get("wa", "Tie").lower()
                    if winner in ["red", "blue"]:
                        learn_from_match_outcome(event_key, match.get("k", ""), winner, red_score, blue_score)
                    
                    prediction = f"{p_red:.0%}" if str(team_number) in red_str else f"{p_blue:.0%}"
                    prediction_percent = round((p_red if str(team_number) in red_str else p_blue) * 100)
                else:
                    prediction = "N/A"
                    prediction_percent = None
        
                winner = match.get("wa", "Tie").title()
                youtube_id = match.get("yt")
                video_link = f"[Watch](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
        
                # Get prediction confidence for this event
                prediction_confidence = get_event_prediction_confidence(event_key)
                confidence_indicator = f"({prediction_confidence:.1%} conf)" if prediction_confidence > 0.5 else ""
                
                row = {
                    "Video": video_link,
                    "Match": match_label_md,
                    "Red Alliance": format_team_list(red_str),
                    "Blue Alliance": format_team_list(blue_str),
                    "Red Score": red_score,
                    "Blue Score": blue_score,
                    "Winner": winner,
                    "Outcome": "",
                    "Prediction": f"{prediction}".strip(),
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
                    {"name": "Match", "id": "Match", "presentation": "markdown"},
                    {"name": "Red Alliance", "id": "Red Alliance", "presentation": "markdown"},
                    {"name": "Blue Alliance", "id": "Blue Alliance", "presentation": "markdown"},
                    {"name": "Red Score", "id": "Red Score"},
                    {"name": "Blue Score", "id": "Blue Score"},
                    {"name": "Outcome", "id": "Outcome"},
                    {"name": "Prediction", "id": "Prediction"},
                ],
                data=match_rows,
                page_size=10,
                style_table={
                    "overflowX": "auto", 
                    "borderRadius": "10px", 
                    "border": "none", 
                    "backgroundColor": "transparent",
                    "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)" # Added shadow
                },
                style_header={
                    "backgroundColor": "var(--card-bg)",
                    "color": "var(--text-primary)",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "borderBottom": "1px solid var(--border-color)",
                    "padding": "6px",
                    "fontSize": "13px",
                },
                style_cell={
                    "backgroundColor": "#181a1b",
                    "color": "var(--text-primary)",
                    "textAlign": "center",
                    "padding": "10px",
                    "border": "none",
                    "fontSize": "14px",
                    "fontWeight": "bold",
                },
                style_data_conditional=[
                    {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
                    {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
                    {"if": {"filter_query": '{Winner} = "Red" && {team_alliance} = "Red"',"column_id": "Outcome"},"backgroundColor": "var(--table-row-green)","color": "var(--text-primary)"},
                    {"if": {"filter_query": '{Winner} = "Red" && {team_alliance} != "Red"',"column_id": "Outcome"},"backgroundColor": "var(--table-row-red)","color": "var(--text-primary)"},
                    {"if": {"filter_query": '{Winner} = "Blue" && {team_alliance} = "Blue"',"column_id": "Outcome"},"backgroundColor": "var(--table-row-green)","color": "var(--table-row-prediction-green)"},
                    {"if": {"filter_query": '{Winner} = "Blue" && {team_alliance} != "Blue"',"column_id": "Outcome"},"backgroundColor": "var(--table-row-red)","color": "var(--table-row-prediction-red)"},
                    {"if": {"filter_query": "{Prediction %} >= 45 && {Prediction %} < 50", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lowneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} >= 50 && {Prediction %} <= 55", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-highneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} > 55 && {Prediction %} <= 65", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} > 65 && {Prediction %} <= 75", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} > 75 && {Prediction %} <= 85", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} > 85 && {Prediction %} <= 95", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} > 95", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} < 45 && {Prediction %} >= 35", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} < 35 && {Prediction %} >= 25", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} < 25 && {Prediction %} >= 15", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightred)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} < 15 && {Prediction %} >= 5", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-darkred)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": "{Prediction %} < 5", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-deepred)", "fontWeight": "bold", "color": "var(--text-primary)"},
                    {"if": {"filter_query": '{team_alliance} = "Red"', "column_id": "Red Score"}, "borderBottom": "1px solid var(--text-primary)"},
                    {"if": {"filter_query": '{team_alliance} = "Blue"', "column_id": "Blue Score"}, "borderBottom": "1px solid var(--text-primary)"},


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
        footer
    ])