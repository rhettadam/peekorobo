import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from datagather import load_year_data,get_team_avatar,get_team_years_participated, load_data_2025, load_search_data
from flask import session
from datetime import datetime, date
from utils import calculate_single_rank,sort_key,get_user_avatar,user_team_card,get_contrast_text_color,get_available_avatars,DatabaseConnection,get_epa_styling,predict_win_probability,predict_win_probability_adaptive, learn_from_match_outcome, get_event_prediction_confidence, get_event_learning_stats, get_prediction_difference, compute_percentiles, pill, get_event_week_label, format_human_date
import json
import os

from utils import WEEK_RANGES_BY_YEAR

current_year = 2025

with open('data/district_states.json', 'r', encoding='utf-8') as f:
    DISTRICT_STATES_COMBINED = json.load(f)

def team_layout(team_number, year, team_database, event_database, event_matches, event_awards, event_rankings, event_teams):

    user_id = session.get("user_id")
    is_logged_in = bool(user_id)
    
    # Check if team is already favorited
    is_favorited = False
    if is_logged_in:
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM saved_items
                    WHERE user_id = %s AND item_type = 'team' AND item_key = %s
                """, (user_id, str(team_number)))
                is_favorited = bool(cursor.fetchone())
        except Exception as e:
            print(f"Error checking favorite status: {e}")
    
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

    # Get total favorites count for this team
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM saved_items WHERE item_type = 'team' AND item_key = %s",
                (str(team_number),)
            )
            favorites_count = cursor.fetchone()[0]
    except Exception as e:
        print(f"Error getting favorites count: {e}")
        favorites_count = 0


    # Separate handling for performance year (used for ACE/stats) vs. awards/events year
    is_history = not year or str(year).lower() == "history"

    if is_history:
        year = None
        # fallback year to use for metrics (default to current year or latest available)
        performance_year = current_year
    else:
        try:
            year = int(year)
            performance_year = year
        except ValueError:
            return dbc.Alert("Invalid year provided.", color="danger")

    # Now safely use performance_year for stats lookups
    year_data = team_database.get(performance_year)
    if not year_data:
        return dbc.Alert(f"Data for year {performance_year} not found.", color="danger")

    selected_team = year_data.get(team_number)
    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data for {performance_year}.", color="danger")

    # DEBUG: Print selected_team data
    #print(f"DEBUG (team_layout): selected_team for {team_number}: {selected_team}")

    # Calculate Rankings
    global_rank, country_rank, state_rank = calculate_single_rank(list(year_data.values()), selected_team)

    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
            "event_epas": json.loads(data["event_epas"]) if isinstance(data.get("event_epas"), str) else data.get("event_epas", [])
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
    years_participated = get_team_years_participated(team_number)
    
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
    
    with open("data/notables.json", "r") as f:
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
                html.Img(src="/assets/trophy.png", style={"height": "1.2em", "verticalAlign": "middle", "marginRight": "5px"}),
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
        html.Div([
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H2(f"Team {team_number}: {nickname}", style={"color": "var(--text-primary)", "fontWeight": "bold"}),
                                    *badges,
                                    html.P([html.Img(src="/assets/pin.png", style={"height": "1.5em", "verticalAlign": "middle", "marginRight": "5px"}), f" {city}, {state}, {country}"]),
                                    html.P([html.I(className="bi bi-link-45deg"), "Website: ", 
                                            html.A(website, href=website, target="_blank", style={"color": "#007BFF", "textDecoration": "underline"})]),
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
                                    html.Div( # Wrapper div for positioning
                                        id=f"team-{team_number}-favorites-popover-target", # Move ID to wrapper
                                        style={
                                            "position": "relative", # Establish positioning context
                                            "display": "inline-block" # Prevent div from taking full width
                                        },
                                        children=[
                                            html.P(
                                                [
                                                    html.I(className="bi bi-star-fill", style={"color": "#ffc107"}),
                                                    f" {favorites_count} Favorites ▼"
                                                ],
                                                style={
                                                    "marginBottom": "0px", # Remove bottom margin on paragraph
                                                    "cursor": "pointer" # Keep cursor on text
                                                }),
                                        ]
                                    ),
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
                                            "borderRadius": "0px",
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
            # External website buttons positioned in bottom right corner
            html.Div([
                html.A(
                    html.Img(src="/assets/tba.png", style={"height": "35px", "width": "auto"}),
                    href=f"https://www.thebluealliance.com/team/{team_number}",
                    target="_blank",
                    style={"marginRight": "6px", "display": "inline-block"}
                ),
                html.A(
                    html.Img(src="/assets/statbotics.png", style={"height": "30px", "width": "auto"}),
                    href=f"https://www.statbotics.io/team/{team_number}",
                    target="_blank",
                    style={"marginRight": "6px", "display": "inline-block"}
                ),
                html.A(
                    html.Img(src="/assets/frc.png", style={"height": "30px", "width": "auto"}),
                    href=f"https://frc-events.firstinspires.org/team/{team_number}",
                    target="_blank",
                    style={"display": "inline-block"}
                )
            ], style={
                "position": "absolute",
                "bottom": "10px",
                "right": "15px",
                "zIndex": "5"
            }),
            # Favorite button positioned in top right corner
            favorite_button,
        ], style={"position": "relative"}),
        style={
            "marginBottom": "20px",
            "borderRadius": "10px",
            "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)",
            "backgroundColor": "var(--card-bg)"
        },
    )
    def build_rank_cards(performance_year, global_rank, country_rank, state_rank, country, state):
        def rank_card(top, bottom, rank, href):
            return html.Div(
                dbc.Card(
                    dbc.CardBody([
                        html.P([
                            html.Span(top, style={"display": "block"}),
                            html.Span(bottom, style={"display": "block"})
                        ], className="rank-card-label"),
                        html.A(str(rank), href=href, className="rank-card-value")
                    ]),
                    className="rank-card"
                )
            )

        return html.Div([
            html.Div([
                rank_card("Global", "Rank", global_rank, f"/teams?year={performance_year}&sort_by=epa"),
                rank_card(country, "Rank", country_rank, f"/teams?year={performance_year}&country={country}&sort_by=epa"),
                rank_card(state, "Rank", state_rank, f"/teams?year={performance_year}&country={country}&state={state}&sort_by=epa"),
            ], className="rank-card-container")
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
                "marginBottom": "6px",   # 👈 add vertical spacing
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
                html.Span("-", style={"color": "var(--text-primary)"}),
                html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
                html.Span("-", style={"color": "var(--text-primary)"}),
                html.Span(str(ties), style={"color": "#777", "fontWeight": "bold"}),
                html.Span(f" in {performance_year}.")
            ], style={"marginBottom": "6px", "fontWeight": "bold"}),
            html.Div([
                pill("Auto", f"{auto:.1f}", auto_color),
                pill("Teleop", f"{teleop:.1f}", teleop_color),
                pill("Endgame", f"{endgame:.1f}", endgame_color),
                pill("EPA", f"{normal_epa:.1f}", norm_color),
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

    # Create tabs for the team page
    team_tabs = dbc.Tabs([
        dbc.Tab(
            label="Overview",
            tab_id="overview-tab",
            children=[
                html.Div([
                    rank_card,
                    performance_metrics_card,
                    html.Hr(),
                    build_recent_events_section(team_key, team_number, epa_data, performance_year, event_database, event_teams, event_matches, event_awards, event_rankings),
                ])
            ]
        ),
        dbc.Tab(
            label="Insights",
            tab_id="insights-tab",
            children=[
                html.Div(id="team-insights-content", children="Loading insights...")
            ]
        ),
        dbc.Tab(
            label="Events",
            tab_id="events-tab",
            children=[
                html.Div(id="team-events-content")
            ]
        ),
        dbc.Tab(
            label="Awards",
            tab_id="awards-tab",
            children=[
                html.Div(id="team-awards-content")
            ]
        ),
    ], id="team-tabs", active_tab="overview-tab")

    # Add Popover for team favorites
    favorites_popover = dbc.Popover(
        [
            dbc.PopoverHeader("Favorited By"),
            dbc.PopoverBody(id={"type": "team-favorites-popover-body", "team_number": str(team_number)}, children="Loading..."), # Body to be updated by callback
        ],
        id={"type": "team-favorites-popover", "team_number": str(team_number)}, # Popover ID
        target=f"team-{team_number}-favorites-popover-target", # Target the favorites count element
        trigger="hover", # Trigger on hover
        placement="right", # Position the popover
    )

    return html.Div(
        [
            topbar(),
            dcc.Store(id="user-session", data={"user_id": user_id} if user_id else None),
            dcc.Store(id="team-insights-store", data={"team_number": team_number, "year": year, "performance_year": performance_year}),
            dbc.Alert(id="favorite-alert", is_open=False, duration=3000, color="warning"),
            dbc.Container(
                [
                    team_card,
                    team_tabs,
                    html.Br(),
                ],
                style={
                    "padding": "20px",
                    "maxWidth": "1200px",
                    "margin": "0 auto",
                    "flexGrow": "1"
                },
            ),
            favorites_popover,
            footer,
        ]
    )

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
                        # Last Updated indicator - visible on desktop
                        dbc.Col(
                            html.Span(
                                id="last-updated-text",
                                style={
                                    "color": "var(--text-secondary)",
                                    "fontSize": "0.75rem",
                                    "fontStyle": "italic"
                                }
                            ),
                            width="auto",
                            className="d-none d-md-block align-self-center",
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
                                    style={"width": "100%"}
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
                                    "width": "100%",
                                    "zIndex": "9999",
                                    "position": "absolute",
                                    "left": "0",
                                    "right": "0",
                                    "top": "100%",
                                    "display": "none",
                                }),
                            ],
                            width=True,
                            className="d-md-none align-self-center mobile-search-group",
                            style={"position": "relative", "textAlign": "center", "flexGrow": "1"},
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
                                    dbc.NavItem(dbc.NavLink("Teams", href="/teams", className="custom-navlink", id="nav-teams")),
                                    dbc.NavItem(dbc.NavLink("Map", href="/map", className="custom-navlink", id="nav-map")),
                                    dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink", id="nav-events")),
                                    dbc.NavItem(dbc.NavLink("Insights", href="/insights", className="custom-navlink", id="nav-insights")),
                                    dbc.DropdownMenu(
                                        label="Misc",
                                        nav=True,
                                        in_navbar=True,
                                        className="custom-navlink",
                                        children=[
                                            dbc.DropdownMenuItem("Blog", href="/blog"),
                                            dbc.DropdownMenuItem("Compare", href="/compare"),
                                            dbc.DropdownMenuItem("Account", href="/login", id="account-link"),
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
                                    # Last Updated indicator - mobile version (only visible on mobile)
                                    dbc.NavItem(
                                        html.Span(
                                            "Loading...",
                                            id="last-updated-text-mobile",
                                            style={
                                                "color": "var(--text-secondary)",
                                                "fontSize": "0.75rem",
                                                "fontStyle": "italic",
                                                "display": "block",
                                                "textAlign": "center",
                                                "padding": "0.5rem 1rem"
                                            }
                                        ),
                                        className="d-md-none"  # Only show on mobile
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
                            ],
                            style={"width": "100%"}
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
        className="",  # Removed mb-4
        style={
            "padding": "4px 0 4px 0",  # 4px top and bottom padding only
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
                    html.A(
                        html.Img(src="/assets/tba.png", style={"height": "16px", "width": "auto", "verticalAlign": "middle", "marginRight": "4px"}),
                        href="https://www.thebluealliance.com/", 
                        target="_blank", 
                        style={"textDecoration": "none"}
                    ),
                    html.A("The Blue Alliance ", href="https://www.thebluealliance.com/", target="_blank", style={"color": "#3366CC", "textDecoration": "line"}),
                    "| ",
                    html.A("GitHub", href="https://github.com/rhettadam/peekorobo", target="_blank", style={"color": "#3366CC", "textDecoration": "line"}),
                ],
                style={
                    "textAlign": "center",
                    "color": "var(--text-primary)",
                    "fontSize": "15px",
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
                                        className='homelogo d-none d-md-block',
                                        style={
                                            "width": "100%",
                                            "maxWidth": "700px",
                                            "height": "auto",
                                        },
                                    ),
                                ),
                                html.A(
                                    html.Img(
                                        src="/assets/mobilehome.png",
                                        className='homelogo d-block d-md-none',
                                        style={
                                            "width": "100%",
                                            "maxWidth": "350px",
                                            "height": "auto",
                                            "marginTop": "0",
                                            "marginBottom": "2rem"
                                        },
                                    ),
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
                                "height": "100%",
                                "marginTop": "2.5rem"
                            }
                        )
                    ],
                    width=6,
                    className="desktop-right-section"
                )
            ],
            justify="center",
            align="center",
            className="align-items-center h-100",
            style={"flex": "1 0 auto"}
        ),
    ], class_name="py-5", style={
        "backgroundColor": "var(--bg-primary)",
        "flexGrow": "1",
        "display": "flex",
        "flexDirection": "column"
    }),
    footer
], style={
    "display": "flex",
    "flexDirection": "column",
    "minHeight": "100vh",
    "backgroundColor": "var(--bg-primary)"
})

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

def insights_layout():

    with open('data/frc_games.json', 'r', encoding='utf-8') as f:
        frc_games = json.load(f)

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
                                            href=f"/insights/{year}",
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
                    html.H2("Insights", className="text-center mb-4"),
                    html.P(
                        "The FIRST Robotics Competition is made up of seasons in which the challenge (game), along with the required set of tasks, changes annually. "
                        "Please click on a season to view more insights",
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

def insights_details_layout(year):

    with open('data/frc_games.json', 'r', encoding='utf-8') as f:
        frc_games = json.load(f)
        
    game = frc_games.get(
        str(year),
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
    team_db = None
    event_db = None
    try:
        if year == current_year:
            from peekorobo import EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, TEAM_DATABASE
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
            team_db = TEAM_DATABASE.get(year, {})
            event_db = EVENT_DATABASE.get(year, {})
        else:
            _, event_data, event_teams, _, _, event_matches = load_year_data(year)
            num_events = len(event_data)
            team_set = set()
            for ek, teams in event_teams.items():
                for t in teams:
                    if isinstance(t, dict) and 'tk' in t:
                        team_set.add(t['tk'])
            num_teams = len(team_set)
            num_matches = len(event_matches)
            team_db, event_db, *_ = load_year_data(year)
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

    # --- Insights Section ---
    # Load insights for the year
    try:
        with open('data/insights.json', 'r', encoding='utf-8') as f:
            all_insights = json.load(f)
        year_insights = all_insights.get(str(year), [])
    except Exception:
        year_insights = []

    insight_options = [
        {
            "label": i.get("name", f"Option {ix+1}")
                .replace("typed_leaderboard_", "")
                .replace("_", " ")
                .title() if i.get("name") else f"Option {ix+1}",
            "value": i.get("name", f"Option {ix+1}")
        }
        for ix, i in enumerate(year_insights)
    ]

    # Default to first option if available
    default_insight = insight_options[0]["value"] if insight_options else None

    insights_section = html.Div([
        html.Hr(),
        html.H4("Yearly Insights", className="mb-3 mt-4 text-center"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Select Insight Type:"),
                dcc.Dropdown(
                    id="insights-dropdown",
                    options=insight_options,
                    value=default_insight,
                    clearable=False,
                    style={"marginBottom": "1.5rem"}
                ),
            ], md=6, xs=12, style={"margin": "0 auto"}),
        ], className="justify-content-center"),
        html.Div(id="insights-table-container", style={"marginTop": "1.5rem"}),
    ]) if insight_options else None

    return html.Div(
        [
            topbar(),
            dbc.Container(
                [
                    banner_img if banner_img else None,
                    hero_row,
                    collage_row,
                    insights_section,
                    dcc.Store(id='challenge-team-db', data=team_db),
                    dcc.Store(id='challenge-event-db', data=event_db),
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
                        "display": "block",
                        "marginTop": 0,
                        "paddingTop": 0,
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
                "flexDirection": "column",
                "paddingTop": 0,
                "marginTop": 0,
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
                    html.P(f"{location}", className="card-text", style={
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

def teams_layout(default_year=current_year):
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

    with open('data/countries.json', 'r', encoding='utf-8') as f:
        COUNTRIES = json.load(f)

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
                for acronym in DISTRICT_STATES_COMBINED.keys()
            ]
        ],
        value="All",
        clearable=False,
        placeholder="Select District",
        style={"width": "100%"},
        className="custom-input-box"
    )
    percentile_toggle = dbc.Checklist(
        options=[{"label": "Filter Percentiles", "value": "filtered"}],
        value=[],
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
            html.Div(country_dropdown, style={"flex": "1 1 100px", "minWidth": "100px"}),
            html.Div(state_dropdown, style={"flex": "1 1 120px", "minWidth": "120px"}),
            html.Div(district_dropdown, style={"flex": "1 1 80px", "minWidth": "80px"}),
            html.Div(percentile_toggle, style={"flex": "1 1 100px", "display": "flex", "alignItems": "center"}),
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
            {"name": "ACE Rank", "id": "epa_rank", "type": "numeric"},
            {"name": "Team", "id": "team_display", "presentation": "markdown"},
            {"name": "EPA", "id": "epa", "type": "numeric"},
            {"name": "Confidence", "id": "confidence", "type": "numeric"},
            {"name": "ACE", "id": "ace", "type": "numeric"},
            {"name": "Auto ACE", "id": "auto_epa", "type": "numeric"},
            {"name": "Teleop ACE", "id": "teleop_epa", "type": "numeric"},
            {"name": "Endgame ACE", "id": "endgame_epa", "type": "numeric"},
            {"name": "Record", "id": "record"},
        ],
        data=[],
        # Enhanced features
        sort_action="native",
        sort_mode="multi",
        page_action="native",
        page_current=0,
        page_size=50,
        
        # Copy to clipboard functionality
        include_headers_on_copy_paste=True,
        
        # Export functionality
        #export_format='csv',
        #export_headers='display',
        #export_columns='visible',
        
        # Column and row selection
        column_selectable='multi',
        row_selectable='multi',
        selected_columns=[],
        selected_rows=[],
        
        # Cell selection (disabled)
        cell_selectable=False,
        
        # Column filtering
        filter_action="native",
        filter_options={"case": "insensitive"},
        
        # Styling
        style_table={
            "overflowX": "auto", 
            "borderRadius": "10px", 
            "border": "none", 
            "backgroundColor": "var(--card-bg)",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
            "minHeight": "400px"
        },
        style_header={
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text)",
            "fontWeight": "bold",
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",
            "padding": "8px",
            "fontSize": "13px",
            "position": "sticky",
            "top": 0,
            "zIndex": 1
        },
        style_cell={
            "textAlign": "center",
            "padding": "8px",
            "border": "none",
            "fontSize": "14px",
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text)",
            "minWidth": "80px",
            "maxWidth": "120px",
            "overflow": "hidden",
            "textOverflow": "ellipsis"
        },
        style_data_conditional=[
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(255, 221, 0, 0.5)",
                "border": "none",
            },
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgba(0, 0, 0, 0.05)",
            },
        ],
        style_filter={
            "backgroundColor": "var(--input-bg)",
            "color": "var(--text-primary)",
            "borderColor": "var(--input-border)",
        },
        style_data={
            "border": "none",
        },
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

    # Export dropdown button
    export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)" "black", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    export_selected_dropdown = dbc.DropdownMenu(
        label="Export Selected",
        color="warning",
        size="sm",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export Selected as CSV", id="export-selected-csv-dropdown"),
            dbc.DropdownMenuItem("Export Selected as TSV", id="export-selected-tsv-dropdown"),
            dbc.DropdownMenuItem("Export Selected as Excel", id="export-selected-excel-dropdown"),
            dbc.DropdownMenuItem("Export Selected as JSON", id="export-selected-json-dropdown"),
            dbc.DropdownMenuItem("Export Selected as HTML", id="export-selected-html-dropdown"),
            dbc.DropdownMenuItem("Export Selected as LaTeX", id="export-selected-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    # Search and export container
    search_export_container = html.Div([
        # Collapsible search container
        html.Div([
            # Search icon button
            html.Button(
                html.I(className="fas fa-search"),
                id="search-toggle",
                style={
                    "background": "none",
                    "border": "none",
                    "color": "var(--text-primary)",
                    "fontSize": "16px",
                    "cursor": "pointer",
                    "padding": "8px",
                    "borderRadius": "4px",
                    "transition": "all 0.2s ease"
                }
            ),
            # Expandable search input
            html.Div(
                search_input,
                id="search-container",
                style={
                    "display": "none",
                    "flex": "1",
                    "maxWidth": "300px",
                    "transition": "all 0.3s ease"
                }
            )
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
        html.Div([
            export_dropdown,
            export_selected_dropdown,
            dcc.Download(id="download-dataframe-csv"),
            dcc.Download(id="download-dataframe-excel"),
            dcc.Download(id="download-dataframe-tsv"),
            dcc.Download(id="download-dataframe-json"),
            dcc.Download(id="download-dataframe-html"),
            dcc.Download(id="download-dataframe-latex"),
        ], style={"textAlign": "right"}),
    ], style={
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
        "marginBottom": "5px",
        "gap": "10px"
    })
    
    content = html.Div(id="teams-tab-content", children=[
        html.Div(id="teams-table-container", children=[
            search_export_container,
            teams_table
        ]),
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

def events_layout(year=current_year):
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
    # Dynamically generate week options based on year
    week_ranges = WEEK_RANGES_BY_YEAR.get(str(year), [])
    week_options = [{"label": "All Wks", "value": "all"}]
    if len(week_ranges) > 1:
        for i in range(len(week_ranges) - 1):
            week_options.append({"label": f"Wk {i+1}", "value": i})
        week_options.append({"label": "Champs", "value": len(week_ranges) - 1})
    elif len(week_ranges) == 1:
        week_options.append({"label": "Champs", "value": 0})
    week_dropdown = dcc.Dropdown(
        id="week-dropdown",
        options=week_options,
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
    )
    
    sort_direction_toggle = dbc.Button(
        "▼",
        id="sort-direction-toggle",
        size="sm",
        color="secondary",
        outline=False,
        style={
            "marginLeft": "5px",
            "padding": "2px 6px",
            "fontSize": "10px",
            "borderRadius": "4px",
            "border": "none",
            "backgroundColor": "transparent",
            "color": "var(--text-primary)",
            "minWidth": "20px",
            "height": "20px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "fontWeight": "bold"
        }
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
            html.Div([
                html.Div(sort_toggle, style={"flex": "1"}),
                sort_direction_toggle
            ], style={
                "flex": "1 1 200px", 
                "minWidth": "200px", 
                "display": "flex", 
                "alignItems": "center",
                "backgroundColor": "var(--input-bg)",
                "borderRadius": "6px",
                "padding": "4px 8px",
                "border": "1px solid var(--input-border)"
            }),
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
                sort_action="native",
                sort_mode="multi",
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
        value=current_year,
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

def match_layout(event_key, match_key):
    # Parse year from event_key
    try:
        year = int(event_key[:4])
    except Exception:
        return dbc.Alert("Invalid event key.", color="danger")
    
     # Get EPA data for teams (prefer event-specific EPA)
    if year == current_year:
        from peekorobo import TEAM_DATABASE, EVENT_MATCHES, EVENT_DATABASE
        team_db = TEAM_DATABASE.get(year, {})
        event_matches = EVENT_MATCHES
        event_db = EVENT_DATABASE
    else:
        try:
            team_db, event_db, _, _, _, event_matches = load_year_data(year)
        except Exception:
            team_db = {}

    if isinstance(event_matches, dict):
        matches = [m for m in event_matches.get(year, []) if m.get("ek") == event_key]
    else:
        matches = [m for m in event_matches if m.get("ek") == event_key]

    # Use the same normalization as build_match_rows in layouts.py
    def normalized_label(match):
        label = match.get("k", "").split("_", 1)[-1]
        if label.lower().startswith("sf") and "m" in label.lower():
            label = label.lower().split("m")[0].upper()
        else:
            label = label.upper()
        return label

    match_labels = [normalized_label(m) for m in matches]
    # Try to find the first match whose normalized label matches match_key (case-insensitive)
    match_idx = next((i for i, k in enumerate(match_labels) if k == match_key.upper()), None)
    match = matches[match_idx] if match_idx is not None else None
    if match is None:
        return dbc.Alert("Match not found.", color="danger")

    # Navigation arrows
    prev_match = match_labels[match_idx - 1] if match_idx > 0 else None
    next_match = match_labels[match_idx + 1] if match_idx < len(match_labels) - 1 else None

    # Get teams
    red_teams = [t for t in match.get("rt", "").split(",") if t.strip().isdigit()]
    blue_teams = [t for t in match.get("bt", "").split(",") if t.strip().isdigit()]
    red_score = match.get("rs", "N/A")
    blue_score = match.get("bs", "N/A")
    winner = match.get("wa", "Tie").title()
    match_label = match.get("k", "").split("_", 1)[-1].upper()
    yid = match.get("yt")
    video_embed = html.Iframe(
        src=f"https://www.youtube.com/embed/{yid}" if yid else None,
        style={"width": "100%", "height": "360px", "border": "none"},
    ) if yid else html.Div("No video available.", style={"color": "#888"})

    def get_team_epa_breakdown(t):
        t_data = team_db.get(int(t), {})
        event_epas = t_data.get("event_epas", [])
        if isinstance(event_epas, str):
            try:
                event_epas = json.loads(event_epas)
            except Exception:
                event_epas = []
        event_epa = next((e for e in event_epas if e.get("event_key") == event_key), None)
        if event_epa and event_epa.get("actual_epa", 0) != 0:
            return {
                "auto_epa": event_epa.get("auto", 0),
                "teleop_epa": event_epa.get("teleop", 0),
                "endgame_epa": event_epa.get("endgame", 0),
                "confidence": event_epa.get("confidence", 0.7),
                "epa": event_epa.get("actual_epa", 0),
                "normal_epa": event_epa.get("overall", 0),
                "nickname": t_data.get("nickname", ""),
                "team_number": t_data.get("team_number", t),
            }
        return {
            "auto_epa": t_data.get("auto_epa", 0),
            "teleop_epa": t_data.get("teleop_epa", 0),
            "endgame_epa": t_data.get("endgame_epa", 0),
            "confidence": t_data.get("confidence", 0.7),
            "epa": t_data.get("epa", 0),
            "normal_epa": t_data.get("normal_epa", 0),
            "nickname": t_data.get("nickname", ""),
            "team_number": t_data.get("team_number", t),
        }

    red_epas = [get_team_epa_breakdown(t) for t in red_teams]
    blue_epas = [get_team_epa_breakdown(t) for t in blue_teams]

    p_red, p_blue = predict_win_probability(red_epas, blue_epas)

    # Projected/actual scores
    pred_red_score = sum(t["epa"] for t in red_epas)
    pred_blue_score = sum(t["epa"] for t in blue_epas)

    # Percentile coloring for EPA/ACE using app-wide logic
    all_epas = [t.get("epa", 0) for t in team_db.values() if t.get("epa") is not None]
    percentiles_dict = {"epa": compute_percentiles(all_epas)}

    # Build breakdown data for DataTable
    phases = [
        ("Auto", "auto_epa"),
        ("Teleop", "teleop_epa"),
        ("Endgame", "endgame_epa"),
        ("EPA", "normal_epa"),
        ("Confidence", "confidence"),
    ]
    # Build columns for red and blue tables
    red_columns = [
        {"name": "Phase", "id": "Phase"},
    ] + [
        {"name": str(t["team_number"]), "id": f"red_{t['team_number']}"} for t in red_epas
    ] + [
        {"name": "Pred", "id": "Red Predicted"},
        {"name": "Actual", "id": "Red Actual"},
    ]
    blue_columns = [
        {"name": "Phase", "id": "Phase"},
    ] + [
        {"name": str(t["team_number"]), "id": f"blue_{t['team_number']}"} for t in blue_epas
    ] + [
        {"name": "Pred", "id": "Blue Predicted"},
        {"name": "Actual", "id": "Blue Actual"},
    ]

    # Build data for red and blue tables
    red_data = []
    blue_data = []
    for label, key in phases:
        red_row = {"Phase": label}
        for t in red_epas:
            red_row[f"red_{t['team_number']}"] = round(t[key], 2)
        if key == "confidence":
            red_row["Red Predicted"] = round(sum(t[key] for t in red_epas) / len(red_epas), 2) if red_epas else 0
        else:
            red_row["Red Predicted"] = round(sum(t[key] for t in red_epas), 2)
        red_row["Red Actual"] = ""  # Placeholder for actuals
        red_data.append(red_row)

        blue_row = {"Phase": label}
        for t in blue_epas:
            blue_row[f"blue_{t['team_number']}"] = round(t[key], 2)
        if key == "confidence":
            blue_row["Blue Predicted"] = round(sum(t[key] for t in blue_epas) / len(blue_epas), 2) if blue_epas else 0
        else:
            blue_row["Blue Predicted"] = round(sum(t[key] for t in blue_epas), 2)
        blue_row["Blue Actual"] = ""  # Placeholder for actuals
        blue_data.append(blue_row)

    # Add Total row (ACE)
    red_total_row = {"Phase": "ACE"}
    for t in red_epas:
        red_total_row[f"red_{t['team_number']}"] = round(t["epa"], 2)
    red_total_row["Red Predicted"] = round(pred_red_score, 2)
    red_total_row["Red Actual"] = red_score
    red_data.append(red_total_row)

    blue_total_row = {"Phase": "ACE"}
    for t in blue_epas:
        blue_total_row[f"blue_{t['team_number']}"] = round(t["epa"], 2)
    blue_total_row["Blue Predicted"] = round(pred_blue_score, 2)
    blue_total_row["Blue Actual"] = blue_score
    blue_data.append(blue_total_row)

    # Percentile coloring for all stats
    all_stats = {
        k: [t.get(k if k != "normal_epa" else "epa", 0) for t in team_db.values() if t.get(k if k != "normal_epa" else "epa") is not None]
        for k in ["auto_epa", "teleop_epa", "endgame_epa", "confidence", "epa", "normal_epa"]
    }
    percentiles_dict = {k: compute_percentiles(v) for k, v in all_stats.items()}

    # Build style_data_conditional for red table
    red_style_data_conditional = []
    for row_idx, (label, stat_key) in enumerate(phases):
        percentiles = percentiles_dict[stat_key]
        stat_rules = get_epa_styling({stat_key: percentiles})
        # Red alliance teams
        for t in red_epas:
            col_id = f"red_{t['team_number']}"
            for rule in stat_rules:
                filter_query = rule["if"]["filter_query"].replace(f"{{{stat_key}}}", f"{{{col_id}}}")
                red_style_data_conditional.append({
                    **rule,
                    "if": {
                        **rule["if"],
                        "column_id": col_id,
                        "row_index": row_idx,
                        "filter_query": filter_query
                    }
                })
    # ACE row for red table
    ace_percentiles = percentiles_dict["epa"]
    ace_rules = get_epa_styling({"epa": ace_percentiles})
    for t in red_epas:
        col_id = f"red_{t['team_number']}"
        for rule in ace_rules:
            filter_query = rule["if"]["filter_query"].replace("{epa}", f"{{{col_id}}}")
            red_style_data_conditional.append({
                **rule,
                "if": {
                    **rule["if"],
                    "column_id": col_id,
                    "row_index": len(phases),
                    "filter_query": filter_query
                }
            })

    # Build style_data_conditional for blue table
    blue_style_data_conditional = []
    for row_idx, (label, stat_key) in enumerate(phases):
        percentiles = percentiles_dict[stat_key]
        stat_rules = get_epa_styling({stat_key: percentiles})
        # Blue alliance teams
        for t in blue_epas:
            col_id = f"blue_{t['team_number']}"
            for rule in stat_rules:
                filter_query = rule["if"]["filter_query"].replace(f"{{{stat_key}}}", f"{{{col_id}}}")
                blue_style_data_conditional.append({
                    **rule,
                    "if": {
                        **rule["if"],
                        "column_id": col_id,
                        "row_index": row_idx,
                        "filter_query": filter_query
                    }
                })
    # ACE row for blue table
    for t in blue_epas:
        col_id = f"blue_{t['team_number']}"
        for rule in ace_rules:
            filter_query = rule["if"]["filter_query"].replace("{epa}", f"{{{col_id}}}")
            blue_style_data_conditional.append({
                **rule,
                "if": {
                    **rule["if"],
                    "column_id": col_id,
                    "row_index": len(phases),
                    "filter_query": filter_query
                }
            })

    # Style for red and blue headers
    red_header_style = {
        "backgroundColor": "#d32f2f",
        "color": "#fff",
        "fontWeight": "bold",
        "textAlign": "center",
        "borderBottom": "1px solid var(--border-color)",
        "padding": "6px",
        "fontSize": "13px",
    }
    blue_header_style = {
        "backgroundColor": "#1976d2",
        "color": "#fff",
        "fontWeight": "bold",
        "textAlign": "center",
        "borderBottom": "1px solid var(--border-color)",
        "padding": "6px",
        "fontSize": "13px",
    }
    cell_style = {
        "backgroundColor": "#181a1b",
        "color": "var(--text-primary)",
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }

    # Red and Blue DataTables
    red_table = dash_table.DataTable(
        columns=red_columns,
        data=red_data,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
        style_header=red_header_style,
        style_cell=cell_style,
        style_data_conditional=red_style_data_conditional,
        style_as_list_view=True,
    )
    blue_table = dash_table.DataTable(
        columns=blue_columns,
        data=blue_data,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
        style_header=blue_header_style,
        style_cell=cell_style,
        style_data_conditional=blue_style_data_conditional,
        style_as_list_view=True,
    )

    # Layout
    if year == current_year:
        event_name = next((ev.get("n", event_key) for ev in event_db.get(year, {}).values() if ev.get("k") == event_key), event_key)
    else:
        event_name = event_db.get(event_key, {}).get("n", event_key)
    event_name = f"{year} {event_name}"
    header = html.Div([
        dbc.Row([
            dbc.Col([
                html.A("\u2190", href=f"/match/{event_key}/{prev_match}", style={"fontSize": "2rem", "textDecoration": "none", "color": "#888"}) if prev_match else None
            ], width=1, style={"textAlign": "right", "verticalAlign": "middle"}),
            dbc.Col([
                html.H2([
                    match_label,
                    html.Span(" "),
                    html.A(event_name, href=f"/event/{event_key}", style={"fontSize": "1.2rem", "textDecoration": "underline", "color": "#1976d2"})
                ], style={"textAlign": "center", "marginBottom": "0"})
            ], width=10),
            dbc.Col([
                html.A("\u2192", href=f"/match/{event_key}/{next_match}", style={"fontSize": "2rem", "textDecoration": "none", "color": "#888"}) if next_match else None
            ], width=1, style={"textAlign": "left", "verticalAlign": "middle"}),
        ], align="center", style={"marginBottom": "1rem"})
    ])
    summary = html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div(f"{int(round(pred_red_score))} - {int(round(pred_blue_score))}", style={"fontSize": "2rem", "fontWeight": "bold", "color": "#d32f2f" if pred_red_score > pred_blue_score else "#1976d2"}),
                    html.Div(f"Projected Winner: {'RED' if pred_red_score > pred_blue_score else 'BLUE'}", style={"fontWeight": "bold", "color": "#d32f2f" if pred_red_score > pred_blue_score else "#1976d2"}),
                ], style={"textAlign": "center"})
            ], width=4),
            dbc.Col([
                html.Div([
                    html.Div(f"{int(red_score)} - {int(blue_score)}", style={"fontSize": "2rem", "fontWeight": "bold", "color": "#d32f2f" if red_score > blue_score else "#1976d2"}),
                    html.Div(f"Actual Winner: {winner}", style={"fontWeight": "bold", "color": "#d32f2f" if winner == 'Red' else '#1976d2' if winner == 'Blue' else '#888'}),
                ], style={"textAlign": "center"})
            ], width=4),
            dbc.Col([
                html.Div([
                    html.Div(f"{int(round(100 * max(p_red, p_blue)))}%", style={"fontSize": "2rem", "fontWeight": "bold", "color": "#d32f2f" if p_red > p_blue else "#1976d2"}),
                    html.Div("Win Probability", style={"fontWeight": "bold"}),
                ], style={"textAlign": "center"})
            ], width=4),
        ], style={"marginBottom": "2rem"})
    ])
    breakdown_tables = dbc.Row([
        dbc.Col([red_table], width=6),
        dbc.Col([blue_table], width=6),
    ], style={"marginBottom": "2rem"})
    return html.Div([
        topbar(),
        dbc.Container([
            html.Div(header, style={"marginBottom": "2rem"}),
            html.Div(summary, style={"marginBottom": "2rem"}),
            html.Div(epa_legend_layout(), style={"marginBottom": "1rem", "marginTop": "1rem"}),
            html.Div(breakdown_tables),
            html.Div(video_embed, style={"textAlign": "center", "marginBottom": "2rem"}),
        ], style={"padding": "30px", "maxWidth": "1000px"}),
        footer
    ])

def user_layout(_user_id=None, deleted_items=None):

    from peekorobo import EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, TEAM_DATABASE, EVENT_RANKINGS

    user_id = _user_id or session.get("user_id")

    if not user_id:
        return html.Div([
            dcc.Store(id="user-session", data={}),
            dcc.Location(href="/login", id="force-login-redirect")
        ])

    dcc.Store(id="user-session", data={"user_id": user_id}),

    username = f"USER {user_id}"
    avatar_key = "stock"
    role = "No role"
    team_affil = "####"
    bio = "No bio"
    followers_count = 0
    following_count = 0
    color = "#f9f9f9"
    team_keys = []
    event_keys = []

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT username, avatar_key, role, team, bio, followers, following, color
                FROM users WHERE id = %s
            """, (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                username = user_row[0] or username
                avatar_key = user_row[1] or "stock"
                role = user_row[2] or "No role"
                team_affil = user_row[3] or "####"
                bio = user_row[4] or "No bio"
                followers_ids = user_row[5] or []
                following_ids = user_row[6] or []
                # Get usernames and avatars for followers
                followers_user_objs = []
                if followers_ids:
                    cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (followers_ids,))
                    followers_user_objs = cursor.fetchall()
            
                # Get usernames and avatars for following
                following_user_objs = []
                if following_ids:
                    cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (following_ids,))
                    following_user_objs = cursor.fetchall()
                
                # Count values
                followers_count = len(followers_ids)
                following_count = len(following_ids)
                
                # Fetch usernames for follower IDs
                followers_usernames = []
                if followers_ids:
                    cursor.execute("SELECT username FROM users WHERE id = ANY(%s)", (followers_ids,))
                    followers_usernames = [row[0] for row in cursor.fetchall()]
                
                # Fetch usernames for following IDs
                following_usernames = []
                if following_ids:
                    cursor.execute("SELECT username FROM users WHERE id = ANY(%s)", (following_ids,))
                    following_usernames = [row[0] for row in cursor.fetchall()]

                color = user_row[7] or "#f9f9f9"

            cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'team'", (user_id,))
            team_keys = [r[0] for r in cursor.fetchall()]

            cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'event'", (user_id,))
            event_keys = [r[0] for r in cursor.fetchall()]
            
    except Exception as e:
        print(f"Error retrieving user info: {e}")

    available_avatars = get_available_avatars()

    text_color = get_contrast_text_color(color)

    profile_display = html.Div(
        id="profile-display",
        hidden=False,
        children=[
            html.Div([
                html.Span(f"Role: {role}", id="profile-role", style={
                    "fontWeight": "500",
                    "color": text_color
                }),
                html.Span(" | ", style={"margin": "0 8px", "color": "#999"}),
                html.Span([
                    html.Span("Team: ", style={"color": text_color, "fontWeight": "500"}),
                    html.A(team_affil, href=f"/team/{team_affil}/{current_year}", style={
                        "color": text_color,
                        "textDecoration": "underline",
                        "fontWeight": "500"
                    })
                ], id="profile-team"),
            ], style={
                "fontSize": "0.85rem",
                "color": text_color,
                "marginTop": "6px",
                "display": "flex",
                "flexWrap": "wrap"
            }),
            
            html.Div([
                html.Span([
                    f"Followers: {followers_count} ",
                    html.Span("▼", id="followers-arrow", style={"cursor": "pointer", "fontSize": "0.75rem"})
                ], id="profile-followers", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
    
                html.Span(" | ", style={"margin": "0 8px", "color": "#999"}),
    
                html.Span([
                    f"Following: {following_count} ",
                    html.Span("▼", id="following-arrow", style={"cursor": "pointer", "fontSize": "0.75rem"})
                ], id="profile-following", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
            ], style={
                "fontSize": "0.85rem",
                "color": text_color,
                "marginTop": "4px",
                "display": "flex",
                "flexWrap": "wrap"
            }),
    
            html.Div(bio, id="profile-bio", style={
                "fontSize": "0.9rem",
                "color": text_color,
                "marginTop": "8px",
                "whiteSpace": "pre-wrap",
                "lineHeight": "1.4"
            })
        ]
    )

    profile_edit_form = html.Div(
        id="profile-edit-form",
        hidden=True,
        children=[
            dbc.Input(id="edit-username", value=username, placeholder="Username", className="mb-2", size="sm"),
            dbc.Input(id="edit-role", value=role, placeholder="Role", className="mb-2", size="sm"),
            dbc.Input(id="edit-team", value=team_affil, placeholder="Team", className="mb-2", size="sm"),
            dbc.Textarea(id="edit-bio", value=bio, placeholder="Bio", className="mb-2", style={"height": "60px", "fontSize": "0.85rem"}),
            html.Label("Select Avatar", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#444"}),
            dcc.Dropdown(
                id="edit-avatar-key",
                options=[
                    {"label": html.Div([
                        html.Img(src=f"/assets/avatars/{f}", height="20px", style={"marginRight": "8px"}), f
                    ], style={"display": "flex", "alignItems": "center"}), "value": f}
                    for f in sorted(available_avatars, key=sort_key)
                ],
                value=avatar_key,
                clearable=False,
                style={"width": "200px", "fontSize": "0.75rem"}
            ),
            html.Label("Change Card Background Color", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#444"}),
            dcc.Dropdown(
                id="edit-bg-color",
                options=[
                    {
                        "label": html.Span([
                            html.Div(style={
                                "display": "inline-block",
                                "width": "12px",
                                "height": "12px",
                                "backgroundColor": color,
                                "color": "333",
                                "marginRight": "8px",
                                "border": "1px solid #ccc",
                                "verticalAlign": "middle"
                            }),
                            name
                        ]),
                        "value": color
                    }
                    for name, color in [
                        # Very light pastels and whites
                        ("White", "#ffffff"),
                        ("Floral White", "#fffaf0"),
                        ("Ivory", "#fffff0"),
                        ("Old Lace", "#fdf5e6"),
                        ("Seashell", "#fff5ee"),
                        ("Lemon Chiffon", "#fffacd"),
                        ("Cornsilk", "#fff8dc"),
                        ("Papaya Whip", "#ffefd5"),
                        ("Peach Puff", "#ffdab9"),
                        ("Misty Rose", "#ffe4e1"),
                        ("Beige", "#f5f5dc"),
                        ("Antique White", "#faebd7"),
                        ("Light Goldenrod", "#fafad2"),
                        ("Wheat", "#f5deb3"),
                    
                        # Light cool tones
                        ("Honeydew", "#f0fff0"),
                        ("Mint Cream", "#f5fffa"),
                        ("Azure", "#f0ffff"),
                        ("Alice Blue", "#f0f8ff"),
                        ("Ghost White", "#f8f8ff"),
                        ("Lavender", "#e6e6fa"),
                        ("Light Cyan", "#e0ffff"),
                        ("Powder Blue", "#b0e0e6"),
                        ("Light Steel Blue", "#b0c4de"),
                        ("Thistle", "#d8bfd8"),
                        ("Plum", "#dda0dd"),
                        ("Gainsboro", "#dcdcdc"),
                        ("Light Gray", "#f5f5f5"),
                    
                        # Saturated / mid tones
                        ("Sky Blue", "#87ceeb"),
                        ("Light Pink", "#ffb6c1"),
                        ("Orchid", "#da70d6"),
                        ("Medium Slate Blue", "#7b68ee"),
                        ("Slate Blue", "#6a5acd"),
                        ("Steel Blue", "#4682b4"),
                        ("Medium Violet Red", "#c71585"),
                        ("Tomato", "#ff6347"),
                        ("Goldenrod", "#daa520"),
                        ("Dark Orange", "#ff8c00"),
                        ("Crimson", "#dc143c"),
                    
                        # Cool / bold
                        ("Royal Blue", "#4169e1"),
                        ("Dodger Blue", "#1e90ff"),
                        ("Deep Sky Blue", "#00bfff"),
                        ("Teal", "#008080"),
                        ("Dark Cyan", "#008b8b"),
                        ("Sea Green", "#2e8b57"),
                        ("Forest Green", "#228b22"),
                    
                        # Deep earth tones
                        ("Olive", "#808000"),
                        ("Saddle Brown", "#8b4513"),
                        ("Dark Slate Gray", "#2f4f4f"),
                        ("Navy", "#001f3f"),
                        ("Midnight Blue", "#191970"),
                        ("Black", "#000000"),
                    ]
                ],
                value=color,
                clearable=False,
                style={"width": "200px", "fontSize": "0.75rem"}
            ),
        ])
            

    store_data = {"deleted": []}  # default state, actual deletion handled via callback
    deleted_items = set(tuple(i) for i in store_data.get("deleted", []))


    team_keys = [k for k in team_keys if ("team", k) not in deleted_items]
    event_keys = [k for k in event_keys if ("event", k) not in deleted_items]

    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "normal_epa": data.get("normal_epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
            "confidence": data.get("confidence", 0),
        }
        for team_num, data in TEAM_DATABASE.get(current_year, {}).items()
    }
    
    team_cards = []
    for team_key in team_keys:
        try:
            team_number = int(team_key)
        except:
            continue

        team_data = TEAM_DATABASE.get(current_year, {}).get(team_number)
        year_data = TEAM_DATABASE.get(current_year, {})

        delete_team_btn = html.Button(
            html.Img(
                src="/assets/trash.png",
                style={
                    "width": "20px",
                    "height": "20px",
                    "verticalAlign": "middle"
                }
            ),
            id={"type": "delete-favorite", "item_type": "team", "key": team_key},
            style={
                "backgroundColor": "transparent",
                "border": "none",
                "cursor": "pointer",
                "padding": "4px"
            }
        )
        if team_data:
            epa = team_data.get("epa", 0)
            teleop = team_data.get("teleop_epa", 0)
            auto = team_data.get("auto_epa", 0)
            endgame = team_data.get("endgame_epa", 0)
            confidence = team_data.get("confidence", 0)
            normal_epa = team_data.get("normal_epa", 0)
            wins = team_data.get("wins", 0)
            losses = team_data.get("losses", 0)
            ties = team_data.get("ties", 0)
            
            auto_color = "#1976d2"     # Blue
            teleop_color = "#fb8c00"   # Orange
            endgame_color = "#388e3c"  # Green
            norm_color = "#d32f2f"    # Red (for overall EPA)
            conf_color = "#555"   
            total_color = "#673ab7" 

            metrics = html.Div([
                html.P([
                    html.Span(f"Team {team_number} ({team_data.get('nickname', '')}) had a record of ", style={"fontWeight": "bold"}),
                    html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
                    html.Span("-", style={"color": "var(--text-primary)"}),
                    html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
                    html.Span("-", style={"color": "var(--text-primary)"}),
                    html.Span(str(ties), style={"color": "#777", "fontWeight": "bold"}),
                    html.Span(f" in {current_year}.")
                ], style={"marginBottom": "6px", "fontWeight": "bold"}),
                html.Div([
                    pill("Auto", f"{auto:.1f}", auto_color),
                    pill("Teleop", f"{teleop:.1f}", teleop_color),
                    pill("Endgame", f"{endgame:.1f}", endgame_color),
                    pill("EPA", f"{normal_epa:.1f}", norm_color),
                    pill("Confidence", f"{confidence:.2f}", conf_color),
                    pill("ACE", f"{epa:.1f}", total_color),
                ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"})
            ])

        team_cards.append(user_team_card(
            html.A(
                f"{team_number} | {team_data.get('nickname', '')}",
                href=f"/team/{team_key}/{current_year}",
                style={"textDecoration": "none", "color": "inherit"}
            ),

            [
                html.Img(src=get_team_avatar(team_key), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, current_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
            ],
            delete_button=delete_team_btn
        ))

    return html.Div([
        dcc.Store(id="favorites-store", data={"deleted": []}),
        dcc.Store(id="user-session", data={"user_id": user_id}),
        topbar(),
        dcc.Location(id="login-redirect", refresh=True),
        dbc.Container([
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Img(
                                id="user-avatar-img",
                                src=get_user_avatar(avatar_key),
                                style={"height": "60px", "borderRadius": "50%", "marginRight": "15px"}
                            ),
                            html.Div([
                                html.H2(
                                    f"Welcome, {username.title()}!",
                                    id="profile-header",
                                    style={"margin": 0, "fontSize": "1.5rem", "color": text_color}
                                ),
                                html.Div(
                                    f"{len(team_keys)} favorite teams",
                                    id="profile-subheader",
                                    style={"fontSize": "0.85rem", "color": text_color}
                                ),
                                profile_display,
                                dbc.Popover(
                                    [
                                        dbc.PopoverHeader("Followers"),
                                        dbc.PopoverBody([
                                            html.Ul([
                                                html.Li([
                                                    html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                                                    html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                                                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                                                for user in followers_user_objs[:5]
                                            ], style={
                                                "listStyleType": "none",
                                                "paddingLeft": "0",
                                                "marginBottom": "0"
                                            }),
                                            html.Div("See all", id="followers-see-more", style={
                                                "color": "#007bff", "cursor": "pointer", "fontSize": "0.75rem", "marginTop": "5px"
                                            }) if len(followers_user_objs) > 5 else None,
                                            html.Ul([
                                                html.Li([
                                                    html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                                                    html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                                                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                                                for user in followers_user_objs[5:]
                                            ], id="followers-hidden", style={
                                                "display": "none",
                                                "marginTop": "5px",
                                                "paddingLeft": "0",
                                                "listStyleType": "none",
                                                "marginBottom": "0"
                                            })
                                        ])
                                    ],
                                    id="popover-followers",
                                    target="followers-arrow",
                                    trigger="hover",
                                    placement="bottom"
                                ),
                                
                                dbc.Popover(
                                    [
                                        dbc.PopoverHeader("Following"),
                                        dbc.PopoverBody([
                                            html.Ul([
                                                html.Li([
                                                    html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                                                    html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                                                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                                                for user in following_user_objs[:5]
                                            ], style={
                                                "listStyleType": "none",
                                                "paddingLeft": "0",
                                                "marginBottom": "0"
                                            }),
                                            html.Div("See all", id="following-see-more", style={
                                                "color": "#007bff", "cursor": "pointer", "fontSize": "0.75rem", "marginTop": "5px"
                                            }) if len(following_user_objs) > 5 else None,
                                            html.Ul([
                                                html.Li([
                                                    html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                                                    html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                                                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                                                for user in following_user_objs[5:]
                                            ], id="following-hidden", style={
                                                "display": "none",
                                                "marginTop": "5px",
                                                "paddingLeft": "0",
                                                "listStyleType": "none",
                                                "marginBottom": "0"
                                            })
                                        ])
                                    ],
                                    id="popover-following",
                                    target="following-arrow",
                                    trigger="hover",
                                    placement="bottom"
                                ),

                                profile_edit_form
                            ]),
                        ], style={"display": "flex", "alignItems": "center"}),
                        html.Div([
                            html.A("Log Out", href="/logout", style={"marginTop": "8px", "fontSize": "0.75rem", "color": text_color, "textDecoration": "none", "fontWeight": "600"}),
                            html.Div([
                                html.H5(
                                    id="profile-search-header",
                                    style={"marginTop": "10px", "fontSize": "0.95rem", "color": text_color}
                                ),
                                dbc.Input(id="user-search-input", placeholder="Search Users", type="text", size="sm", className="custom-input-box mb-2"),
                                html.Div(id="user-search-results")
                            ], style={"marginTop": "10px", "width": "100%"}),
                            html.Button(
                                "Edit Profile",
                                id="edit-profile-btn",
                                style={
                                    "background": "none",
                                    "border": "none",
                                    "padding": "0",
                                    "marginTop": "8px",
                                    "color": text_color,
                                    "fontWeight": "bold",
                                    "fontSize": "0.85rem",
                                    "textDecoration": "none"
                                }
                            ),
                            html.Button("Save", id="save-profile-btn", className="btn btn-warning btn-sm mt-2", style={"display": "none"})
                        ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end", "justifyContent": "center"})
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "15px"})
                ]),
                id="profile-card",
                style={"borderRadius": "10px", "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)", "marginBottom": "20px", "backgroundColor": color or "var(--card-bg)"}

            ),
            html.H3("Favorite Teams", className="mb-3"),
            *team_cards,
            html.Hr(),

        ], style={"padding": "20px", "maxWidth": "1000px"}),
        footer
    ])

def other_user_layout(username):
    from peekorobo import TEAM_DATABASE, EVENT_TEAMS, EVENT_DATABASE, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES
    session_user_id = session.get("user_id")
    if not session_user_id:
        return dcc.Location(href="/login", id="force-login-redirect")

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, avatar_key, role, team, bio, followers, following, color
                FROM users WHERE username = %s
            """, (username,))
            row = cur.fetchone()

            if not row:
                return html.Div("User not found.", style={"padding": "2rem", "fontSize": "1.2rem"})

            uid, avatar_key, role, team, bio, followers_json, following_json, color = row
            is_following = session_user_id in (followers_json or [])

            cur.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'team'", (uid,))
            team_keys = [r[0] for r in cur.fetchall()]

            cur.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'event'", (uid,))
            event_keys = [r[0] for r in cur.fetchall()]

    except Exception as e:
        print(f"Error loading user data: {e}")
        return html.Div("Error loading user data.", style={"padding": "2rem", "fontSize": "1.2rem"})

    if color:
        color = color
    else:
        color = "#ffffff"
        
    text_color = get_contrast_text_color(color)

    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "normal_epa": data.get("normal_epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
            "confidence": data.get("confidence", 0),
        }
        for team_num, data in TEAM_DATABASE.get(current_year, {}).items()
    }

    team_cards = []
    for team_key in team_keys:
        try:
            team_number = int(team_key)
        except:
            continue

        team_data = TEAM_DATABASE.get(current_year, {}).get(team_number)
        if not team_data:
            continue

        epa = team_data.get("epa", 0)
        normal_epa = team_data.get("normal_epa", 0)
        confidence = team_data.get("confidence", 0)
        teleop = team_data.get("teleop_epa", 0)
        auto = team_data.get("auto_epa", 0)
        endgame = team_data.get("endgame_epa", 0)
        wins = team_data.get("wins", 0)
        losses = team_data.get("losses", 0)
        ties = team_data.get("ties", 0)
        country = (team_data.get("country") or "").lower()
        state = (team_data.get("state_prov") or "").lower()

        global_rank = 1
        country_rank = 1
        state_rank = 1
        for other in TEAM_DATABASE.get(current_year, {}).values():
            if (other.get("epa", 0) or 0) > epa:
                global_rank += 1
                if (other.get("country") or "").lower() == country:
                    country_rank += 1
                if (other.get("state_prov") or "").lower() == state:
                    state_rank += 1

        year_data = list(TEAM_DATABASE.get(current_year, {}).values())

        auto_color = "#1976d2"     # Blue
        teleop_color = "#fb8c00"   # Orange
        endgame_color = "#388e3c"  # Green
        norm_color = "#d32f2f"    # Red (for overall EPA)
        conf_color = "#555"   
        total_color = "#673ab7" 

        metrics = html.Div([
            html.P([
                html.Span(f"Team {team_number} ({team_data.get('nickname', '')}) had a record of ", style={"fontWeight": "bold"}),
                html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
                html.Span("-", style={"color": "var(--text-primary)"}),
                html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
                html.Span("-", style={"color": "var(--text-primary)"}),
                html.Span(str(ties), style={"color": "#777", "fontWeight": "bold"}),
                html.Span(f" in {year_data[0].get('year', current_year) if year_data else current_year}.")
            ], style={"marginBottom": "6px", "fontWeight": "bold"}),
            html.Div([
                pill("Auto", f"{auto:.1f}", auto_color),
                pill("Teleop", f"{teleop:.1f}", teleop_color),
                pill("Endgame", f"{endgame:.1f}", endgame_color),
                pill("EPA", f"{normal_epa:.2f}", norm_color),
                pill("Confidence", f"{confidence:.2f}", conf_color),
                pill("ACE", f"{epa:.1f}", total_color),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"})
        ])

        team_cards.append(user_team_card(
            html.A(
                f"{team_number} | {team_data.get('nickname', '')}",
                href=f"/team/{team_key}/{current_year}",
                style={"textDecoration": "none", "color": "inherit"}
            ),
            [
                html.Img(src=get_team_avatar(team_key), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, current_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
            ]
        ))

    follow_button = html.Button(
        "Unfollow" if is_following else "Follow",
        id={"type": "follow-user", "user_id": uid},
        className="btn btn-outline-primary btn-sm"
    ) if uid != session_user_id else None

    profile_display = html.Div(
        id="profile-display",
        hidden=False,
        children=[
            html.Div([
                html.Span(f"Role: {role}", id="profile-role", style={
                    "fontWeight": "500",
                    "color": text_color,
                }),
                html.Span(" | ", style={"margin": "0 8px", "color": text_color}),
                html.Span([
                    html.Span("Team: ", style={"color": text_color, "fontWeight": "500"}),
                    html.A(team, href=f"/team/{team}/{current_year}", style={
                        "color": text_color,
                        "textDecoration": "none",
                        "fontWeight": "500"
                    })
                ], id="profile-team"),
                html.Span(" | ", style={"margin": "0 8px", "color": text_color}),
                html.Span(f"Followers: {len(followers_json)}", style={
                    "color": text_color,
                    "fontWeight": "500",
                }),
                html.Span(" | ", style={"margin": "0 8px", "color": text_color}),
                html.Span(f"Following: {len(following_json)}", style={
                    "color": text_color,
                    "fontWeight": "500",
                })
            ], style={
                "fontSize": "0.85rem",
                "color": text_color,
                "marginTop": "6px",
                "display": "flex",
                "flexWrap": "wrap"
            }),
            html.Div(bio, id="profile-bio", style={
                "fontSize": "0.9rem",
                "color": text_color,
                "marginTop": "8px",
                "whiteSpace": "pre-wrap",
                "lineHeight": "1.4"
            })
        ]
    )

    return html.Div([
        dcc.Store(id="user-session", data={"user_id": session_user_id}),
        topbar(),
        dcc.Location(id="login-redirect", refresh=True),
        dbc.Container([
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Img(
                                src=get_user_avatar(avatar_key),
                                style={"height": "60px", "borderRadius": "50%", "marginRight": "15px"}
                            ),
                            html.Div([
                                html.H2(f"{username.title()}", style={"margin": 0, "fontSize": "1.5rem", "color": text_color}),
                                html.Div(f"{len(team_keys)} favorite teams", style={"fontSize": "0.85rem", "color": text_color}),
                                profile_display,
                            ]),
                        ], style={"display": "flex", "alignItems": "center"}),
                        html.Div([
                            html.Button(
                                "Unfollow" if is_following else "Follow",
                                id={"type": "follow-user", "user_id": uid},
                                style={
                                    "backgroundColor": "white" if is_following else "#ffdd00",
                                    "border": "1px solid #ccc",
                                    "borderRadius": "12px",
                                    "padding": "4px 10px",
                                    "fontSize": "0.85rem",
                                    "fontWeight": "500",
                                    "color": "#000",
                                    "cursor": "pointer",
                                    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
                                    "marginTop": "8px"
                                }
                            ) if uid != session_user_id else None
                        ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end", "justifyContent": "center"})
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "15px"})
                ]),
                id="profile-card",
                style={
                    "borderRadius": "10px",
                    "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                    "marginBottom": "20px",
                    "backgroundColor": color or "var(--card-bg)"
                }
            ),
            html.H3("Favorite Teams", className="mb-3"),
            *team_cards,
            html.Hr(),
        ], style={"padding": "20px", "maxWidth": "1000px"}),
        footer,
    ])

def event_layout(event_key):

    def parse_event_key(event_key):
        if len(event_key) >= 5 and event_key[:4].isdigit():
            return int(event_key[:4]), event_key[4:]
        return None, event_key

    parsed_year, _ = parse_event_key(event_key)
    
    # Load data for the specific year
    if parsed_year == current_year:
        from peekorobo import EVENT_DATABASE, EVENT_TEAMS, TEAM_DATABASE, EVENT_RANKINGS, EVENT_MATCHES
        # Use global data for current year
        event = EVENT_DATABASE.get(parsed_year, {}).get(event_key)
        event_teams = EVENT_TEAMS.get(parsed_year, {}).get(event_key, [])
        event_epa_data = {}
        for team in event_teams:
            team_num = team.get("tk")
            team_data = TEAM_DATABASE.get(parsed_year, {}).get(team_num, {})
            if team_data:
                # Handle event_epas whether it's a string or list
                event_epas = team_data.get("event_epas", [])
                if isinstance(event_epas, str):
                    try:
                        event_epas = json.loads(event_epas)
                    except json.JSONDecodeError:
                        event_epas = []
                # Find event-specific EPA data for this team at this event
                event_specific_epa = next(
                    (e for e in event_epas if e.get("event_key") == event_key),
                    None
                )
                # Fallback to overall EPA/confidence/consistency if event-specific is missing
                if event_specific_epa and event_specific_epa.get("actual_epa", 0) != 0:
                    event_epa_data[str(team_num)] = {
                        "normal_epa": event_specific_epa.get("overall", 0),
                        "epa": event_specific_epa.get("actual_epa", 0),
                        "auto_epa": event_specific_epa.get("auto", 0),
                        "teleop_epa": event_specific_epa.get("teleop", 0),
                        "endgame_epa": event_specific_epa.get("endgame", 0),
                        "confidence": event_specific_epa.get("confidence", 0.7),  # Use 0.7 as fallback instead of 0
                    }
                else:
                    # Use overall EPA/confidence/consistency from TEAM_DATABASE
                    event_epa_data[str(team_num)] = {
                        "epa": team_data.get("epa", 0),
                        "normal_epa": team_data.get("normal_epa"),
                        "auto_epa": team_data.get("auto_epa", 0),
                        "teleop_epa": team_data.get("teleop_epa", 0),
                        "endgame_epa": team_data.get("endgame_epa", 0),
                        "confidence": team_data.get("confidence", 0.7),
                    }
        
        # Calculate rankings based on event-specific EPA
        rankings = EVENT_RANKINGS.get(parsed_year, {}).get(event_key, {})
        
        # Get event matches
        event_matches = [m for m in EVENT_MATCHES.get(parsed_year, []) if m.get("ek") == event_key]
        
    else:
        # Load data for other years on-demand
        try:
            year_team_data, year_event_data, year_event_teams, year_event_rankings, _, year_event_matches = load_year_data(parsed_year)
            event = year_event_data.get(event_key)
            event_teams = year_event_teams.get(event_key, [])
            event_epa_data = {}
            for team in event_teams:
                team_num = team.get("tk")
                team_data = year_team_data.get(team_num, {})
                if team_data:
                    # Handle event_epas whether it's a string or list
                    event_epas = team_data.get("event_epas", [])
                    if isinstance(event_epas, str):
                        try:
                            event_epas = json.loads(event_epas)
                        except json.JSONDecodeError:
                            event_epas = []
                    # Find event-specific EPA data for this team at this event
                    event_specific_epa = next(
                        (e for e in event_epas if e.get("event_key") == event_key),
                        None
                    )
                    # Fallback to overall EPA/confidence/consistency if event-specific is missing
                    if event_specific_epa and event_specific_epa.get("actual_epa", 0) != 0:
                        event_epa_data[str(team_num)] = {
                            "normal_epa": event_specific_epa.get("overall", 0),
                            "epa": event_specific_epa.get("actual_epa", 0),
                            "auto_epa": event_specific_epa.get("auto", 0),
                            "teleop_epa": event_specific_epa.get("teleop", 0),
                            "endgame_epa": event_specific_epa.get("endgame", 0),
                            "confidence": event_specific_epa.get("confidence", 0.7),
                        }
                    else:
                        # Use overall EPA/confidence/consistency from year_team_data
                        event_epa_data[str(team_num)] = {
                            "epa": team_data.get("epa", 0),
                            "normal_epa": team_data.get("normal_epa"),
                            "auto_epa": team_data.get("auto_epa", 0),
                            "teleop_epa": team_data.get("teleop_epa", 0),
                            "endgame_epa": team_data.get("endgame_epa", 0),
                            "confidence": team_data.get("confidence", 0.7),
                        }
            
            # Calculate rankings based on event-specific EPA
            rankings = year_event_rankings.get(event_key, {})
            
            # Get event matches
            event_matches = [m for m in year_event_matches if m.get("ek") == event_key]
            
        except Exception as e:
            return dbc.Alert(f"Error loading data for year {parsed_year}: {str(e)}", color="danger")
    
    if not event:
        return dbc.Alert("Event details could not be found.", color="danger")

    event_name = event.get("n", "Unknown Event")
    # Remove ' presented by' and everything after it
    if " presented by" in event_name:
        event_name = event_name.split(" presented by")[0]
    event_location = f"{event.get('c', '')}, {event.get('s', '')}, {event.get('co', '')}"
    start_date = event.get("sd", "N/A")
    end_date = event.get("ed", "N/A")
    event_type = event.get("et", "N/A")

    # Calculate week label
    week_label = None
    if start_date and start_date != "N/A":
        try:
            week_label = get_event_week_label(datetime.strptime(start_date, "%Y-%m-%d").date())
        except Exception:
            week_label = None

    # Format dates for display
    from utils import format_human_date
    start_display = format_human_date(start_date) if start_date and start_date != "N/A" else start_date
    end_display = format_human_date(end_date) if end_date and end_date != "N/A" else end_date

    # Header card
    header_card = dbc.Card(
        html.Div([
            dbc.CardBody([
                html.H2(f"{event_name} ({parsed_year})", className="card-title mb-3", style={"fontWeight": "bold"}),
                html.P(f"{event_location}", className="card-text"),
                html.P(f"{start_display} - {end_display}", className="card-text"),
                html.P(f"{week_label} {event_type}" if week_label else "", className="card-text"),
                dbc.Row([
                    dbc.Col([
                        html.A(
                            html.Img(src="/assets/tba.png", style={"height": "40px", "width": "auto"}),
                            href=f"https://www.thebluealliance.com/event/{event_key}",
                            target="_blank",
                            style={"marginLeft": "0px", "marginTop": "20px", "display": "inline-block"}
                        ),
                        html.A(
                            html.Img(src="/assets/statbotics.png", style={"height": "35px", "width": "auto"}),
                            href=f"https://www.statbotics.io/event/{event_key}",
                            target="_blank",
                            style={"marginLeft": "10px", "marginTop": "20px", "display": "inline-block"}
                        ),
                        html.A(
                            html.Img(src="/assets/frc.png", style={"height": "35px", "width": "auto"}),
                            href=f"https://frc-events.firstinspires.org/{parsed_year}/{event_key[4:]}",
                            target="_blank",
                            style={"marginLeft": "12px", "marginTop": "20px", "display": "inline-block"}
                        )
                    ], width="auto")
                ], className="mt-3")
            ])
        ], style={"position": "relative"}),
        className="mb-4 shadow-sm flex-fill",
        style={"borderRadius": "10px"}
    )

    # Determine last match and thumbnail
    last_match = None
    if event_matches:
        final_matches = [m for m in event_matches if m.get("cl") == "f"]
        last_match = final_matches[-1] if final_matches else event_matches[-1]

    last_match_thumbnail = None
    if last_match and last_match.get("yt"):
        video_key = last_match.get("yt")
        thumbnail_url = f"https://img.youtube.com/vi/{video_key}/hqdefault.jpg"
        last_match_thumbnail = dbc.Card(
            dbc.CardBody(
                html.A(
                    html.Img(src=thumbnail_url, style={"width": "100%", "borderRadius": "5px"}),
                    href=f"https://www.youtube.com/watch?v={video_key}",
                    target="_blank"
                )
            ),
            className="mb-4 shadow-sm flex-fill",
            style={"borderRadius": "10px"}
        )

    header_layout = dbc.Row(
        [
            dbc.Col(header_card, md=8, className="d-flex align-items-stretch"),
            dbc.Col(last_match_thumbnail, md=4, className="d-flex align-items-stretch") if last_match_thumbnail else dbc.Col()
        ],
        className="mb-4"
    )

    tab_style = {"color": "var(--text-primary)", "backgroundColor": "transparent"}
    # Use dcc.Store to set initial tab from URL
    data_tabs = dbc.Tabs(
        [
            dbc.Tab(label="Teams", tab_id="teams", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Rankings", tab_id="rankings", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Metrics", tab_id="metrics", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Matches", tab_id="matches", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Alliances", tab_id="alliances", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="SoS", tab_id="sos", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Compare", tab_id="compare", label_style=tab_style, active_label_style=tab_style),
        ],
        id="event-data-tabs",
        active_tab=None,  # Will be set by callback
        className="mb-4",
    )

    # --- Insights Section ---
    # Load insights for the year
    try:
        with open('data/insights.json', 'r', encoding='utf-8') as f:
            all_insights = json.load(f)
        year_insights = all_insights.get(str(year), [])
    except Exception:
        year_insights = []

    insight_options = [
        {
            "label": i.get("name", f"Option {ix+1}")
                .replace("typed_leaderboard_", "")
                .replace("_", " ")
                .title() if i.get("name") else f"Option {ix+1}",
            "value": i.get("name", f"Option {ix+1}")
        }
        for ix, i in enumerate(year_insights)
    ]

    # Default to first option if available
    default_insight = insight_options[0]["value"] if insight_options else None

    insights_section = html.Div([
        html.Hr(),
        html.H4("Yearly Insights", className="mb-3 mt-4 text-center"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Select Insight Type:"),
                dcc.Dropdown(
                    id="insights-dropdown",
                    options=insight_options,
                    value=default_insight,
                    clearable=False,
                    style={"marginBottom": "1.5rem"}
                ),
            ], md=6, xs=12, style={"margin": "0 auto"}),
        ], className="justify-content-center"),
        html.Div(id="insights-table-container", style={"marginTop": "1.5rem"}),
    ]) if insight_options else None

    return html.Div(
        [
            dcc.Location(id="event-url", refresh=False),
            dcc.Store(id="event-tab-store"),  # Store for initial tab
            dcc.Store(id="user-session"),  # Holds user_id from session
            topbar(),
            dbc.Container(
                [
                    header_layout,
                    data_tabs,
                    dcc.Store(id="store-event-epa", data=event_epa_data),
                    dcc.Store(id="store-event-teams", data=event_teams),
                    dcc.Store(id="store-rankings", data=rankings),
                    dcc.Store(id="store-event-matches", data=event_matches),
                    dcc.Store(id="store-event-year", data=parsed_year),
                    html.Div(id="data-display-container"),
                    html.Div(id="event-alliances-content"),
                    html.Div(id="event-metrics-content"),
                    insights_section,
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            footer,
        ]
    )