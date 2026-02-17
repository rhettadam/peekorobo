import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from datagather import load_year_data,get_team_avatar,get_team_years_participated,TEAM_COLORS
from flask import session
from datetime import datetime, date, timedelta, timezone
from utils import get_team_data_with_fallback,format_human_date,calculate_single_rank,sort_key,get_user_avatar,user_team_card,get_contrast_text_color,get_available_avatars,DatabaseConnection,get_epa_styling,predict_win_probability, compute_percentiles, pill, get_event_week_label_from_number
import json
import os
import re
import plotly.graph_objs as go
import dash_mantine_components as dmc
from flask import request as _flask_request
import colorsys
import numpy as np
import time
import pytz

current_year = 2026
DEFAULT_TIMEZONE = 'America/Chicago'  # Central Time

def get_team_district_options():
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT district
                FROM teams
                WHERE district IS NOT NULL
                ORDER BY district
                """
            )
            districts = [row[0] for row in cur.fetchall()]
            cur.close()
        return [{"label": d, "value": d} for d in districts if d]
    except Exception:
        return []

def get_team_card_colors_with_text(team_number):
    """Get team colors and appropriate text color for card with cleaner, more subtle styling."""
    try:
        colors = TEAM_COLORS.get(str(team_number), {})
        primary = colors.get("primary", "#3b82f6")  # Default to a medium blue
        secondary = colors.get("secondary", "#1e40af")  # Default to a darker blue
        
        # Create a more subtle gradient with softer colors
        # Use the primary color as base but make it lighter and more muted
        
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(*rgb)
        
        def adjust_color_brightness(hex_color, factor):
            rgb = hex_to_rgb(hex_color)
            h, s, v = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)
            # Increase brightness and reduce saturation for a cleaner look
            v = min(1.0, v * factor)
            s = max(0.1, s * 0.7)  # Reduce saturation for softer look
            new_rgb = colorsys.hsv_to_rgb(h, s, v)
            return rgb_to_hex(tuple(int(c * 255) for c in new_rgb))
        
        # Create softer versions of the team colors
        soft_primary = adjust_color_brightness(primary, 1.3)  # Lighter version
        soft_secondary = adjust_color_brightness(secondary, 0.8)  # Darker, more muted version
        
        # Create a subtle gradient at an angle (diagonal)
        gradient = f"linear-gradient(135deg, {soft_primary} 0%, {soft_secondary} 100%)"
        
        # Use white text for better contrast on the softer background
        text_color = "#FFFFFF"
        
        return gradient, text_color
    except Exception:
        # Fallback to a clean, modern gradient at an angle
        return "linear-gradient(135deg, #4f7cac 0%, #2d3748 100%)", "#FFFFFF"

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
            "color": "#ffffff",  # golden star
            "zIndex": "10",
            "textDecoration": "none",
            "cursor": "pointer",
            "textShadow": "2px 2px 2px rgba(0, 0, 0, 0.6)"
        }
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
    is_history = year is None or (isinstance(year, str) and year.lower() == "history")

    if is_history:
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


    raw_values = [data.get("normal_epa", 0) for data in year_data.values()]
    auto_values = [data.get("auto_epa", 0) for data in year_data.values()]
    teleop_values = [data.get("teleop_epa", 0) for data in year_data.values()]
    endgame_values = [data.get("endgame_epa", 0) for data in year_data.values()]
    ace_values = [data.get("epa", 0) for data in year_data.values()]

    percentiles_dict = {
        "epa": compute_percentiles(raw_values),
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
                "color": "white",
                "textDecoration": "none",
            },
        )
        for yr in years_participated
    ] if years_participated else ["N/A"]
    
    # Add "History" button (same as before)
    years_links.append(
        html.A(
            "History",
            href=f"/team/{team_number}/history",
            style={
                "marginLeft": "0px",
                "color": "white",
                "fontWeight": "bold",
                "textDecoration": "none",
            },
        )
    )
    
    INCLUDED_CATEGORIES = {
        "notables_hall_of_fame": "Hall of Fame",
        "notables_world_champions": "World Champions",
    }
    
    def get_team_notables_grouped(team_number):
        team_key = f"frc{team_number}"
        category_data = {}
    
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT year, category, video
                    FROM notables
                    WHERE team_key = %s AND category = ANY(%s)
                    """,
                    (team_key, list(INCLUDED_CATEGORIES.keys())),
                )
                rows = cur.fetchall()
        except Exception:
            rows = []

        for year, category, video in rows:
            if category not in INCLUDED_CATEGORIES:
                continue
            if category not in category_data:
                category_data[category] = {"years": [], "video": None}
            category_data[category]["years"].append(int(year))
            if category == "notables_hall_of_fame" and video:
                category_data[category]["video"] = video
        return category_data
    
    def generate_notable_badges(team_number):
        grouped = get_team_notables_grouped(team_number)
        badge_elements = []
    
        for category, info in sorted(grouped.items()):
            display_name = INCLUDED_CATEGORIES[category]
            year_list = ", ".join(str(y) for y in sorted(set(info["years"])))
            children = [
                html.Img(src="/assets/trophy.png", style={"height": "1.0em", "verticalAlign": "middle", "marginRight": "5px"}),
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
                        "color": "#fff",
                        "fontWeight": "normal"
                    })
                )
    
            badge_elements.append(
                html.Div(children, style={"display": "flex", "alignItems": "center", "marginBottom": "8px"})
            )
    
        return badge_elements

    badges = generate_notable_badges(team_number)
    
    # Get team card colors with appropriate text color
    background_gradient, text_color = get_team_card_colors_with_text(team_number)
    
        # Team Info Card
    team_card = dbc.Card(
        html.Div([
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H2(f"Team {team_number}: {nickname}", style={"color": "white", "fontWeight": "bold"}),
                                    *badges,
                                    html.P([html.Img(src="/assets/pin.png", style={"height": "1em", "verticalAlign": "middle", "marginRight": "5px"}), f" {city}, {state}, {country}"], style={"color": "white"}),
                                    html.P([html.I(className="bi bi-link-45deg"), "Website: ", 
                                            html.A(website, href=website, target="_blank", style={"color": "white", "textDecoration": "underline"})], style={"color": "white"}),
                                    html.Div(
                                        [
                                            html.I(className="bi bi-calendar", style={"color": "white"}),
                                            html.Span(" Years Participated: ", style={"color": "white"}),
                                            html.Div(
                                                years_links,
                                                style={"display": "flex", "flexWrap": "wrap", "gap": "8px", "textDecoration": "underline","color": "white"},
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
                                                        html.I(className="bi bi-star-fill", style={"color": "#ffffff"}),
                                                        f" {favorites_count} Favorites ▼"
                                                    ],
                                                    style={
                                                        "marginBottom": "0px", # Remove bottom margin on paragraph
                                                        "cursor": "pointer", # Keep cursor on text
                                                        "color": "white"
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
                                            "borderRadius": "10px",
                                            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                                            "marginLeft": "auto",
                                            "marginRight": "auto",
                                            "display": "block",
                                            "backgroundColor": "#00000030",
                                            "padding": "10px",
                                        },
                                    ) if avatar_url else html.Div("No avatar available.", style={"color": "white"}),
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
            "background": background_gradient,
            "color": text_color
        },
    )
    def build_rank_cards(performance_year, global_rank, country_rank, state_rank, country, state, year_data, selected_team):
        # Calculate total counts for each category
        total_teams = len(year_data)
        country_teams = len([team for team in year_data.values() if team.get("country", "").lower() == country.lower()])
        state_teams = len([team for team in year_data.values() if team.get("state_prov", "").lower() == state.lower()])
        
        # Use stored district data for district ranking
        district_rank = None
        district_name = None
        district_teams = 0
        
        try:  
            district_name = selected_team.get("district")
            if district_name:
                district_team_list = [
                    team for team in year_data.values()
                    if team.get("district") == district_name
                ]
                district_teams = len(district_team_list)
                if district_teams > 0:
                    valid_epas = [team.get("epa") for team in district_team_list if team.get("epa") not in (None, 0)]
                    if not valid_epas:
                        district_rank = "N/A"
                    else:
                        district_team_list.sort(key=lambda x: x.get("epa", 0), reverse=True)
                        for i, team in enumerate(district_team_list):
                            if team.get("team_number") == selected_team.get("team_number"):
                                district_rank = i + 1
                                break
        except Exception as e:
            print(f"Error loading district data: {e}")
        
        def rank_card(top, rank, total, href):
            return html.Div(
                dbc.Card(
                    dbc.CardBody([
                        html.P(top, className="rank-card-label", style={"fontWeight": "bold"}),
                        html.A([
                            html.Span(str(rank), style={"display": "block", "fontSize": "1.5rem", "fontWeight": "bold", "color": "#007bff"}),
                            html.Span(f"out of {total}", style={"display": "block", "fontSize": "0.8rem", "opacity": "0.4", "fontweight": "normal"})
                        ], href=href, className="rank-card-value", style={"textDecoration": "none"})
                    ]),
                    className="rank-card"
                )
            )

        # Build rank cards list
        rank_cards = [
            rank_card("Global", global_rank, total_teams, f"/teams?year={performance_year}&sort_by=epa"),
            rank_card(country, country_rank, country_teams, f"/teams?year={performance_year}&country={country}&sort_by=epa"),
        ]
        
        # Add district rank card if district data exists
        if district_name and district_teams > 0:
            rank_cards.append(
                rank_card(district_name, district_rank, district_teams, f"/teams?year={performance_year}&sort_by=epa")
            )
        
        # Add state rank card (always show state rank)
        rank_cards.append(
            rank_card(state, state_rank, state_teams, f"/teams?year={performance_year}&country={country}&state={state}&sort_by=epa")
        )

        return html.Div([
            html.Div(rank_cards, className="rank-card-container")
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
        total_color = "#673ab7"     # Deep Purple for ACE
    
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
                pill("RAW", f"{normal_epa:.1f}", norm_color),
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
        state,
        year_data,
        selected_team
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
                    # --- Trends Chart (moved above recent events) ---
                    build_trends_chart(team_number, year, performance_year, team_database, event_database, years_participated),
                    html.Div([
                        html.Div([
                            html.H3("Recent Events", style={"margin": "0", "color": "var(--text-secondary)", "fontWeight": "bold"}),
                            html.Div([
                                html.Label("Table Style:", style={"fontWeight": "bold", "color": "var(--text-primary)", "marginRight": "12px"}),
                                dcc.RadioItems(
                                    id="recent-events-table-style-toggle",
                                    options=[
                                        {"label": "Both Alliances", "value": "both"},
                                        {"label": "Team Focus", "value": "team"}
                                    ],
                                    value="team",
                                    inline=True,
                                    labelStyle={"marginRight": "15px", "color": "var(--text-primary)"}
                                )
                            ], style={"display": "flex", "alignItems": "center"})
                        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginTop": "2rem", "marginBottom": "1rem"}),
                        html.Div(
                            id="recent-events-section",
                            children=build_recent_events_section(
                                team_key,
                                team_number,
                                epa_data,
                                performance_year,
                                event_database,
                                event_teams,
                                event_matches,
                                event_awards,
                                event_rankings,
                                table_style="team",
                                include_header=False,
                            )
                        )
                    ]),
                ])
            ]
        ),
        dbc.Tab(
            label="Events",
            tab_id="events-tab",
            children=[
                html.Div(id="team-events-content", children="Loading events...")
            ]
        ),
        dbc.Tab(
            label="Awards",
            tab_id="awards-tab",
            children=[
                html.Div(id="team-awards-content", children="Loading awards...")
            ]
        ),
        # Removed Insights tab
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

def blog_index_layout():
    """Blog index page listing all blog posts"""
    blog_posts = [
        {
            "title": "RAW vs ACE: Understanding Peekorobo's Metrics",
            "description": "Learn the difference between RAW (unadjusted performance) and ACE (adjusted contribution estimate), and how confidence scores work.",
            "url": "/blog/raw-vs-ace",
            "date": "2025-11-10"
        },
        {
            "title": "Peekorobo's Features",
            "description": "Complete overview of all features available on Peekorobo, from team analysis to match predictions and event insights.",
            "url": "/blog/features",
            "date": "2025-11-10"
        },
        {
            "title": "Match Prediction System",
            "description": "How Peekorobo predicts match outcomes using ACE values and confidence scores.",
            "url": "/blog/predictions",
            "date": "2025-11-10"
        }
    ]
    
    return html.Div([
        topbar(),
        dbc.Container([
            html.Div([
                html.H1("Blog", 
                    style={"fontSize": "2.5em", "marginBottom": "15px", "color": "var(--text-primary)"}),
                html.P("Technical documentation and insights about Peekorobo's metrics",
                    style={"fontSize": "1.2em", "color": "var(--text-secondary)", "marginBottom": "40px"}),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3([
                                    html.A(post["title"], href=post["url"], 
                                        style={"color": "var(--text-primary)", "textDecoration": "none"})
                                ], style={"marginTop": "0", "marginBottom": "6px"}),
                                html.P(post["description"], style={"color": "var(--text-secondary)", "marginBottom": "2px"}),
                                html.Small(post["date"], style={"color": "var(--text-muted)", "marginBottom": "0"})
                            ], style={"padding": "15px", "paddingBottom": "5px"})
                        ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "20px", "height": "100%"})
                    ], width=12, md=6, style={"marginBottom": "20px"}) 
                    for post in blog_posts
                ], style={"marginBottom": "60px"})
            ], style={"maxWidth": "1000px", "margin": "0 auto", "padding": "40px 20px"})
        ], fluid=True, style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}),
        footer
    ], style={"minHeight": "100vh", "display": "flex", "flexDirection": "column"})

def raw_vs_ace_blog_layout():
    """Blog layout explaining RAW vs ACE metrics"""
    return html.Div([
        topbar(),
        dbc.Container([
            html.Div([
                html.H1("RAW vs ACE: Understanding Peekorobo's Metrics", 
                    style={"fontSize": "2.5em", "marginBottom": "15px", "color": "var(--text-primary)"}),
                
                html.P([
                    "We use two metrics: ", html.Strong("RAW"), " and ", html.Strong("ACE"), " (Adjusted Contribution Estimate). ",
                    "RAW is unadjusted performance. ACE is RAW multiplied by a confidence score."
                ], style={"fontSize": "1.1em", "marginBottom": "40px", "color": "var(--text-primary)"}),
                
                html.H2("What is RAW?", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H3("RAW (Raw Expected Points Added)", style={"color": "var(--text-primary)", "marginTop": "0"}),
                        html.P([
                            html.Strong("RAW"), " is the unadjusted measure of a team's expected contribution. ",
                            "It's calculated using an exponential moving average of match contributions over time."
                        ], style={"color": "var(--text-primary)"}),
                        
                        html.H4("Calculation", style={"color": "var(--text-primary)", "marginTop": "25px"}),
                        html.P("Using an Exponential Moving Average (EMA):", style={"color": "var(--text-primary)"}),
                        html.Ul([
                            html.Li("Calculate actual contribution per match (auto + teleop + endgame)"),
                            html.Li(["Update RAW: ", html.Code("RAW_new = RAW_old + K × (actual_contribution - RAW_old)", style={"color": "#ffdd00"})]),
                        ], style={"color": "var(--text-primary)"}),
                        
                        html.Div([
                            html.Code("RAW = Auto RAW + Teleop RAW + Endgame RAW", 
                                style={"fontSize": "1.2em", "fontWeight": "bold", "color": "#ffdd00"})
                        ], style={
                            "backgroundColor": "var(--bg-secondary)",
                            "border": "2px solid var(--border-color)",
                            "borderRadius": "6px",
                            "padding": "20px",
                            "margin": "20px 0",
                            "textAlign": "center",
                            "fontFamily": "monospace",
                            "color": "var(--text-primary)"
                        }),
                    ])
                ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "30px"}),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H3("Exponential Moving Average (EMA) Algorithm", style={"color": "var(--text-primary)", "marginTop": "0"}),
                        html.P(["RAW is calculated using an EMA with learning rate ", html.Code("K = 0.4", style={"color": "#ffdd00"}), ":"], style={"color": "var(--text-primary)"}),
                        html.Div([
                            html.Code("RAW_new = RAW_old + K × (actual_contribution - RAW_old)", 
                                style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#ffdd00"})
                        ], style={
                            "backgroundColor": "var(--bg-secondary)",
                            "border": "2px solid var(--border-color)",
                            "borderRadius": "6px",
                            "padding": "15px",
                            "margin": "15px 0",
                            "textAlign": "center",
                            "fontFamily": "monospace",
                            "color": "var(--text-primary)"
                        }),
                        html.P(["Where ", html.Code("K", style={"color": "#ffdd00"}), " is adjusted by:"], style={"color": "var(--text-primary)"}),
                        html.Ul([
                            html.Li([html.Strong("Chronological Weight:"), " Later-season events weighted more heavily"]),
                        ], style={"color": "var(--text-primary)"})
                    ])
                ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "20px"}),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H3("Multi-Event Aggregation", style={"color": "var(--text-primary)", "marginTop": "0"}),
                        html.P("For teams with multiple events, RAW and confidence are aggregated with chronological weighting:", style={"color": "var(--text-primary)"}),
                        html.Ul([
                            html.Li(["Each event's RAW is weighted by: ", html.Code("chronological_weight × match_count", style={"color": "#ffdd00"})]),
                            html.Li("Chronological weights range from 0.2 (early season) to 1.0 (late season)"),
                            html.Li("Confidence components are averaged across events using the same weights"),
                            html.Li("Final ACE = Weighted Average RAW × Final Confidence")
                        ], style={"color": "var(--text-primary)"})
                    ])
                ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "30px"}),
                
                html.H2("What is ACE?", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H3("ACE (Adjusted Contribution Estimate)", style={"color": "var(--text-primary)", "marginTop": "0"}),
                        html.P([
                            html.Strong("ACE"), " is RAW multiplied by a confidence score (0.0 to 1.0). ",
                            "Teams with high RAW but low confidence get a lower ACE. Consistent teams have ACE closer to RAW."
                        ], style={"color": "var(--text-primary)"}),
                        
                        html.Div([
                            html.Code("ACE = RAW × Confidence Score", 
                                style={"fontSize": "1.2em", "fontWeight": "bold", "color": "#ffdd00"})
                        ], style={
                            "backgroundColor": "var(--bg-secondary)",
                            "border": "2px solid var(--border-color)",
                            "borderRadius": "6px",
                            "padding": "20px",
                            "margin": "20px 0",
                            "textAlign": "center",
                            "fontFamily": "monospace",
                            "color": "var(--text-primary)"
                        }),
                    ])
                ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "30px"}),
                
                html.H2("Confidence Score", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Confidence is a weighted combination of five factors:", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Div([
                    html.Code("Raw Confidence = (0.35 × Consistency) + (0.35 × Dominance) + (0.10 × Record Alignment) + (0.10 × Veteran) + (0.10 × Events)", 
                        style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#ffdd00"})
                ], style={
                    "backgroundColor": "var(--bg-secondary)",
                    "border": "2px solid var(--border-color)",
                    "borderRadius": "6px",
                    "padding": "20px",
                    "margin": "20px 0",
                    "textAlign": "center",
                    "fontFamily": "monospace",
                    "color": "var(--text-primary)"
                }),
                
                html.H3("Non-Linear Scaling", style={"color": "var(--text-primary)", "marginTop": "30px"}),
                html.P("After calculating raw confidence:", style={"color": "var(--text-primary)"}),
                html.Ul([
                    html.Li([html.Strong(">0.85:"), " 1.1× multiplier"]),
                    html.Li([html.Strong("<0.65:"), " 0.9× multiplier"]),
                    html.Li([html.Strong("Final:"), " Capped 0.0-1.0"])
                ], style={"color": "var(--text-primary)", "marginBottom": "30px"}),
                
                html.H2("Confidence Components", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H3("Confidence Components", style={"color": "var(--text-primary)", "marginTop": "0"}),
                        
                        html.Div([
                            html.Div([
                                html.Strong("Consistency", style={"color": "var(--text-primary)"}),
                                html.Span("35%", style={"float": "right", "color": "var(--navbar-hover)", "fontWeight": "bold"})
                            ], style={"padding": "12px", "backgroundColor": "var(--bg-secondary)", "borderRadius": "6px", "marginBottom": "10px"}),
                            html.P([
                                "Performance consistency across matches. Lower variance = higher consistency."
                            ], style={"marginLeft": "15px", "color": "var(--text-primary)"}),
                            html.H4("Consistency Calculation", style={"color": "var(--text-primary)", "marginTop": "15px", "marginBottom": "10px"}),
                            html.P("Formula:", style={"color": "var(--text-primary)"}),
                            html.Div([
                                html.Code("Consistency = max(0.0, 1.0 - (stdev / (peak + ε)))", 
                                    style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#ffdd00"})
                            ], style={
                                "backgroundColor": "var(--bg-secondary)",
                                "border": "2px solid var(--border-color)",
                                "borderRadius": "6px",
                                "padding": "15px",
                                "margin": "15px 0",
                                "textAlign": "center",
                                "fontFamily": "monospace",
                                "color": "var(--text-primary)"
                            }),
                            html.P("Where:", style={"color": "var(--text-primary)"}),
                            html.Ul([
                                html.Li([html.Code("stdev", style={"color": "#ffdd00"}), " = Standard deviation of all match contributions"]),
                                html.Li([html.Code("peak", style={"color": "#ffdd00"}), " = Maximum contribution in any match"]),
                                html.Li([html.Code("ε", style={"color": "#ffdd00"}), " = Small epsilon (1e-6) to prevent division by zero"])
                            ], style={"color": "var(--text-primary)"})
                        ], style={"marginBottom": "20px"}),
                        
                        html.Div([
                            html.Div([
                                html.Strong("Dominance", style={"color": "var(--text-primary)"}),
                                html.Span("35%", style={"float": "right", "color": "var(--navbar-hover)", "fontWeight": "bold"})
                            ], style={"padding": "12px", "backgroundColor": "var(--bg-secondary)", "borderRadius": "6px", "marginBottom": "10px"}),
                            html.P([
                                "How much a team outscores opponents. Larger margins = higher dominance."
                            ], style={"marginLeft": "15px", "color": "var(--text-primary)"}),
                            html.H4("Dominance Calculation", style={"color": "var(--text-primary)", "marginTop": "15px", "marginBottom": "10px"}),
                            html.P("Calculation:", style={"color": "var(--text-primary)"}),
                            html.Div([
                                html.Code([
                                    "margin = team_contribution - (opponent_score / team_count)", html.Br(),
                                    "scaled_margin = margin / (opponent_score + ε)", html.Br(),
                                    "norm_margin = (scaled_margin + 1) / 1.3", html.Br(),
                                    "dominance = mean(norm_margin) capped at [0.0, 1.0]"
                                ], style={"fontSize": "1.0em", "fontWeight": "bold", "whiteSpace": "pre-wrap", "wordBreak": "break-word","color": "#ffdd00"})
                            ], style={
                                "backgroundColor": "var(--bg-secondary)",
                                "border": "2px solid var(--border-color)",
                                "borderRadius": "6px",
                                "padding": "15px",
                                "margin": "15px 0",
                                "textAlign": "left",
                                "fontFamily": "monospace",
                                "color": "var(--text-primary)"
                            })
                        ], style={"marginBottom": "20px"}),
                        
                        html.Div([
                            html.Div([
                                html.Strong("Record Alignment", style={"color": "var(--text-primary)"}),
                                html.Span("10%", style={"float": "right", "color": "var(--navbar-hover)", "fontWeight": "bold"})
                            ], style={"padding": "12px", "backgroundColor": "var(--bg-secondary)", "borderRadius": "6px", "marginBottom": "10px"}),
                            html.P([
                                "Whether win-loss record matches performance. High RAW + high win rate = boost. ",
                                "Scaled 0.7 (0% wins) to 1.0 (100% wins)."
                            ], style={"marginLeft": "15px", "color": "var(--text-primary)"})
                        ], style={"marginBottom": "20px"}),
                        
                        html.Div([
                            html.Div([
                                html.Strong("Veteran Boost", style={"color": "var(--text-primary)"}),
                                html.Span("10%", style={"float": "right", "color": "var(--navbar-hover)", "fontWeight": "bold"})
                            ], style={"padding": "12px", "backgroundColor": "var(--bg-secondary)", "borderRadius": "6px", "marginBottom": "10px"}),
                            html.P("Based on years of competition:", style={"marginLeft": "15px", "color": "var(--text-primary)"}),
                            html.Ul([
                                html.Li("1 year: 0.2 boost"),
                                html.Li("2 years: 0.4 boost"),
                                html.Li("3 years: 0.6 boost"),
                                html.Li("4+ years: 1.0 boost")
                            ], style={"marginLeft": "30px", "color": "var(--text-primary)"})
                        ], style={"marginBottom": "20px"}),
                        
                        html.Div([
                            html.Div([
                                html.Strong("Event Boost", style={"color": "var(--text-primary)"}),
                                html.Span("10%", style={"float": "right", "color": "var(--navbar-hover)", "fontWeight": "bold"})
                            ], style={"padding": "12px", "backgroundColor": "var(--bg-secondary)", "borderRadius": "6px", "marginBottom": "10px"}),
                            html.P("Based on number of events:", style={"marginLeft": "15px", "color": "var(--text-primary)"}),
                            html.Ul([
                                html.Li("1 event: 0.5 boost"),
                                html.Li("2 events: 0.9 boost"),
                                html.Li("3+ events: 1.0 boost")
                            ], style={"marginLeft": "30px", "color": "var(--text-primary)"})
                        ])
                    ])
                ], style={"backgroundColor": "var(--card-bg)", "border": "1px solid var(--border-color)", "marginBottom": "30px"}),
                
                html.H2("Why Both?", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                dbc.Table([
                    html.Thead([
                        html.Tr([
                            html.Th("Aspect", style={"backgroundColor": "var(--navbar-bg)", "color": "var(--navbar-text)"}),
                            html.Th("RAW", style={"backgroundColor": "var(--navbar-bg)", "color": "var(--navbar-text)"}),
                            html.Th("ACE", style={"backgroundColor": "var(--navbar-bg)", "color": "var(--navbar-text)"})
                        ])
                    ]),
                    html.Tbody([
                        html.Tr([
                            html.Td(html.Strong("What it measures"), style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Raw performance potential", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Realistic expected contribution", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"})
                        ]),
                        html.Tr([
                            html.Td(html.Strong("Adjustments"), style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("None - pure performance", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Adjusted for reliability", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"})
                        ]),
                        html.Tr([
                            html.Td(html.Strong("Best for"), style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Understanding peak capability", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Match predictions and rankings", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"})
                        ]),
                        html.Tr([
                            html.Td(html.Strong("Example"), style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Team scores 50 points in best match", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"}),
                            html.Td("Team averages 35 points reliably", style={"backgroundColor": "var(--table-bg)", "color": "var(--text-primary)"})
                        ])
                    ])
                ], bordered=True, hover=True, responsive=True, style={"marginBottom": "30px", "backgroundColor": "var(--table-bg)", "color": "var(--text-primary)", "borderColor": "var(--table-border)"}),
                
                dbc.Alert([
                    html.H4("Example", style={"marginTop": "0", "color": "var(--text-primary)"}),
                    html.P([
                        html.Strong("Team A: "), "RAW = 45, Confidence = 0.6 → ACE = 27", html.Br(),
                        html.Strong("Team B: "), "RAW = 35, Confidence = 0.9 → ACE = 31.5"
                    ], style={"color": "var(--text-primary)"}),
                    html.P("Team A has higher RAW, but Team B has higher ACE due to consistency. We favor Team B in predictions.", style={"color": "var(--text-primary)"})
                ], color="info", style={"marginBottom": "30px", "backgroundColor": "var(--card-bg)", "borderColor": "#ffdd00", "color": "var(--text-primary)"}),
            ], style={"maxWidth": "900px", "margin": "0 auto", "padding": "40px 20px"})
        ], fluid=True, style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}),
        footer
    ], style={"minHeight": "100vh", "display": "flex", "flexDirection": "column"})

def features_blog_layout():
    """Blog post explaining all Peekorobo features"""
    return html.Div([
        topbar(),
        dbc.Container([
            html.Div([
                html.H1("Peekorobo's Features", 
                    style={"fontSize": "2.5em", "marginBottom": "15px", "color": "var(--text-primary)"}),
                
                html.P([
                    "Peekorobo is a comprehensive web application for analyzing FRC team performance, leveraging data from The Blue Alliance (TBA) and a contribution estimation model called the ACE algorithm. ",
                    "It offers rich insights into team rankings, match performance and predictions, strength of schedule, historical trends, and event dynamics."
                ], style={"fontSize": "1.1em", "marginBottom": "40px", "color": "var(--text-primary)"}),
                
                html.H2("Home Page", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.Img(src="/assets/readme/homepage.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Team Profiles", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Each team has a dedicated profile page displaying detailed information for a selected year (or historical overview).", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("General Info: "), "Team number, nickname, location (city, state, country), rookie year, and website. Notable achievements like Hall of Fame or World Championships are highlighted."]),
                    html.Li([html.Strong("Years Participated: "), "Links to view the team's profile for specific past seasons."]),
                    html.Li([html.Strong("Performance Metrics: "), "Detailed breakdown of the team's performance based on the ACE model, including:"]),
                    html.Ul([
                        html.Li("Overall ACE and RAW"),
                        html.Li("Component breakdown: Auto ACE, Teleop ACE, Endgame ACE"),
                        html.Li("Global, Country, and State/Province ranks (clickable links to the Teams insights filtered view)"),
                        html.Li("Season win/loss/tie record"),
                        html.Li("ACE component pills with color coding based on percentile rank relative to all teams in the selected year")
                    ], style={"marginLeft": "20px", "marginTop": "10px", "marginBottom": "10px"}),
                    html.Li([html.Strong("Recent Events: "), "A section showcasing the team's most recent event performances with key stats and match outcomes."]),
                    html.Li([html.Strong("Event History Table: "), "A searchable and filterable table listing all events the team participated in during the selected year (or across history), including event name, location, and dates."]),
                    html.Li([html.Strong("Awards Table: "), "A table listing all awards the team received in the selected year (or across history), including award name, event name, and year."]),
                    html.Li([html.Strong("Blue Banners: "), "A visual display of blue banners won by the team, with links to the corresponding events."]),
                    html.Li([html.Strong("Favorite Button: "), "Authenticated users can favorite teams to easily access them from their user profile."])
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/team.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Teams", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Explore and compare all teams within a given year.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("Filtering: "), "Filter teams by year, country, state/province, and district."]),
                    html.Li([html.Strong("Search: "), "Interactive search bar to filter teams by number, name, or location."]),
                    html.Li([html.Strong("Top 3 Spotlight: "), "Highlights the top 3 teams based on ACE with dedicated cards."]),
                    html.Li([html.Strong("Main Table: "), "A detailed table displaying teams with columns for ACE Rank, ACE, RAW (unweighted), Confidence, and the component breakdowns (Auto ACE, Teleop ACE, Endgame ACE), Location, and Record. Favorite counts are also shown with subtle highlighting at configurable thresholds."]),
                    html.Li([html.Strong("Exports: "), "Download the current or selected rows as CSV, TSV, Excel, JSON, HTML, or LaTeX."]),
                    html.Li([html.Strong("ACE Color Key: "), "A legend explaining the color coding used for ACE and its components, based on percentiles. Users can toggle between global percentiles (all teams) and filtered percentiles (teams matching current filters)."]),
                    html.Li([html.Strong("Avatars Gallery: "), "A separate tab displaying all team avatars for the filtered set of teams."]),
                    html.Li([html.Strong("Bubble Chart: "), "A visual representation of team performance plotting two chosen ACE components against each other, with bubble size potentially representing overall ACE. Useful for identifying specialists (high on one axis) or well-rounded teams (balanced on both axes). Users can select which components to plot on the X and Y axes."])
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/teams.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/teams_avatars.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/teams_bubble.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Events", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Browse and filter FRC events across different years.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("Filtering: "), "Filter events by year, event type (Season, Off-season, Regional, District, Championship), week number, and district."]),
                    html.Li([html.Strong("Search: "), "Interactive search bar to filter events by name or code."]),
                    html.Li([html.Strong("Sorting: "), "Toggle between sorting events by time (start date) or alphabetically by name."]),
                    html.Li([html.Strong("Card View: "), "Displays events as interactive cards showing key details and a favorite button for logged-in users. Includes separate sections for Upcoming and Ongoing events."]),
                    html.Li([html.Strong("Event Insights Table: "), "A tabular view providing insights into the competitive strength of events, showing Max ACE, Top 8 ACE, and Top 24 ACE for teams participating in each event. Color-coded based on percentiles for comparison."])
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/events.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_insights.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Event Details", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("A dedicated page for each FRC event providing in-depth information.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("Header: "), "Event name, year, location, dates, type, website link, and a favorite button. Includes a thumbnail link to the event's YouTube match video if available."]),
                    html.Li([html.Strong("Data Tabs: "), "Switch between different views of event data:"]),
                    html.Ul([
                        html.Li([html.Strong("Teams: "), "Lists all teams participating in the event, sorted by ACE Rank, with ACE and component breakdowns. Includes a spotlight of the top teams at the event. A Stats Type selector lets you switch between Overall season metrics and Event-specific metrics; event stats include SoS and ACE Δ versus season baselines."]),
                        html.Li([html.Strong("Rankings: "), "Displays the official event rankings (Rank, Wins, Losses, Ties, DQ) alongside ACE Rank and ACE for comparison."]),
                        html.Li([html.Strong("Matches: "), "Lists all matches played at the event, including Red/Blue alliances, scores, winner, and win predictions based on ACE and confidence. Toggle between Both Alliances and Team Focus views, filter by team, and create a YouTube playlist of selected matches with one click. Inline accuracy badges summarize prediction performance, and an Event Insights card surfaces high/low scores, win margins, and handy match links."]),
                        html.Li([html.Strong("SoS: "), "Strength of Schedule table per team using average opponent ACE and per-match win probabilities."]),
                        html.Li([html.Strong("Compare: "), "Select multiple teams and compare event stats side-by-side, plus a radar chart normalized to the event field."]),
                        html.Li([html.Strong("Metrics: "), "Explore TBA metrics via a dropdown (OPRs, DPRs, CCWMs, COPRs variants). Results are sortable and link back to team pages."]),
                        html.Li([html.Strong("Alliances: "), "Visual bracket-style cards that show alliance captains/picks and playoff progression/status pulled from TBA."])
                    ], style={"marginLeft": "20px", "marginTop": "10px", "marginBottom": "10px"})
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/event_teams.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_ranks.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_matches.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_sos.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_compare.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_metrics.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/event_alliances.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Challenges", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Explore the history of FRC games year by year.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("Challenge Dictionary: "), "Lists all FRC challenges from 1992 to the present, with names, years, and logos."]),
                    html.Li([html.Strong("Challenge Details: "), "Clicking on a challenge leads to a page with a summary of the game, links to the official game manual, and the game reveal video."])
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/challenges.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/challenge_details.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Team Map", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Visualize the geographic distribution of FRC teams for a given year on an interactive map.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/map.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("User Profiles", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Authenticated users have a profile page.", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Ul([
                    html.Li([html.Strong("My Profile: "), "Displays user information (username, role, team affiliation, bio, avatar, card background color), favorite team and event counts, and lists of followers and following. Edit your profile (including picking an avatar from a gallery and a background color with automatic contrast adjustment)."]),
                    html.Li([html.Strong("Favorite Teams/Events: "), "Lists the teams and events the user has favorited, with direct links and an option to remove them."]),
                    html.Li([html.Strong("Other User Profiles: "), "View profiles of other users, see their favorited teams/events, and follow/unfollow them with one click."]),
                    html.Li([html.Strong("User Search: "), "Search for other users by username. Results appear in a compact overlay with follow/unfollow actions and quick links."])
                ], style={"color": "var(--text-primary)", "marginBottom": "20px"}),
                
                html.Img(src="/assets/readme/user_profile.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "20px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                html.Img(src="/assets/readme/other_user_profile.png", style={"width": "100%", "maxWidth": "1200px", "marginBottom": "30px", "borderRadius": "8px", "border": "1px solid var(--border-color)"}),
                
                html.H2("Theme Toggle", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Switch between light and dark mode for a personalized viewing experience.", style={"color": "var(--text-primary)", "marginBottom": "30px"}),
                
                html.H2("Universal Profile Icon/Toast", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("A small icon is shown in the bottom right for logged-in users, linking to their profile. For logged-out users, a dismissible toast encourages registration/login to use favorite features.", style={"color": "var(--text-primary)", "marginBottom": "30px"})
            ], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "40px 20px"})
        ], fluid=True, style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"}),
        footer
    ], style={"minHeight": "100vh", "display": "flex", "flexDirection": "column"})

def predictions_blog_layout():
    """Blog post explaining the match prediction system"""
    return html.Div([
        topbar(),
        dbc.Container([
            html.Div([
                html.H1("Match Prediction System", 
                    style={"fontSize": "2.5em", "marginBottom": "15px", "color": "var(--text-primary)"}),
                
                html.P([
                    "Peekorobo uses ACE values to predict match outcomes. ",
                    "The system calculates win probabilities based on team ACE and confidence scores."
                ], style={"fontSize": "1.1em", "marginBottom": "40px", "color": "var(--text-primary)"}),
                
                html.H2("Basic Prediction Formula", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Predictions start with ACE values:", style={"color": "var(--text-primary)"}),
                html.Div([
                    html.Code([
                        "red_ace = sum(team.ace for team in red_alliance)", html.Br(),
                        "blue_ace = sum(team.ace for team in blue_alliance)", html.Br(),
                        "diff = red_ace - blue_ace"
                    ], style={"fontSize": "1.1em", "fontWeight": "bold", "whiteSpace": "pre", "color": "#ffdd00"})
                ], style={
                    "backgroundColor": "var(--bg-secondary)",
                    "border": "2px solid var(--border-color)",
                    "borderRadius": "6px",
                    "padding": "20px",
                    "margin": "20px 0",
                    "textAlign": "left",
                    "fontFamily": "monospace",
                    "color": "var(--text-primary)"
                }),
                
                html.H2("Win Probability Calculation", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Win probability uses logistic regression:", style={"color": "var(--text-primary)"}),
                html.Div([
                    html.Code([
                        "scale = boost × (0.06 + 0.3 × (1 - avg_confidence))", html.Br(),
                        "p_red = 1 / (1 + exp(-scale × diff))", html.Br(),
                        "p_red = max(0.15, min(0.90, p_red))"
                    ], style={"fontSize": "1.1em", "fontWeight": "bold", "whiteSpace": "pre", "color": "#ffdd00"})
                ], style={
                    "backgroundColor": "var(--bg-secondary)",
                    "border": "2px solid var(--border-color)",
                    "borderRadius": "6px",
                    "padding": "20px",
                    "margin": "20px 0",
                    "textAlign": "left",
                    "fontFamily": "monospace",
                    "color": "var(--text-primary)"
                }),
                
                html.P("The scale factor adjusts based on average confidence. Lower confidence = wider probability distribution.", style={"color": "var(--text-primary)"}),
                
                html.H2("Prediction Confidence", style={"color": "var(--text-primary)", "marginTop": "40px", "marginBottom": "20px", "borderBottom": "2px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.P("Prediction confidence depends on:", style={"color": "var(--text-primary)"}),
                html.Ul([
                    html.Li("Average confidence of teams in the match"),
                    html.Li("ACE difference between alliances"),
                    html.Li("Number of matches played by teams")
                ], style={"color": "var(--text-primary)"}),
                
                html.P("Higher team confidence = more reliable predictions. Large ACE differences = more confident predictions.", style={"color": "var(--text-primary)", "marginTop": "20px"}),
                
            ], style={"maxWidth": "900px", "margin": "0 auto", "padding": "40px 20px"})
        ], fluid=True, style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}),
        footer
    ], style={"minHeight": "100vh", "display": "flex", "flexDirection": "column"})

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
                                    dbc.NavItem(dbc.NavLink("Events", href="/events", className="custom-navlink", id="nav-events")),
                                    dbc.NavItem(dbc.NavLink("Map", href="/map", className="custom-navlink", id="nav-map")),
                                    dbc.NavItem(dbc.NavLink("Insights", href="/insights", className="custom-navlink", id="nav-insights")),
                                    dbc.DropdownMenu(
                                        label="Misc",
                                        nav=True,
                                        in_navbar=True,
                                        className="custom-navlink",
                                        children=[
                                            dbc.DropdownMenuItem("Blog", href="/blog"),
                                            dbc.DropdownMenuItem("Higher or Lower", href="/higher-lower"),
                                            dbc.DropdownMenuItem("Duel", href="/duel"),
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
                                            html.I(className="fas fa-sun"),
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
                                    # Peekolive link - mobile version
                                    dbc.NavItem(
                                        html.A(
                                            [
                                                html.Span("Try", style={
                                                    "fontWeight": "600",
                                                    "fontSize": "0.9rem",
                                                    "letterSpacing": "0.5px",
                                                    "color": "white"
                                                }),
                                                " ",
                                                html.Img(
                                                    src="/assets/peekolive.png",
                                                    style={"height": "20px", "width": "auto", "marginLeft": "4px", "marginRight": "4px"}
                                                )
                                            ],
                                            href="/events/peekolive",
                                            style={
                                                "color": "var(--navbar-text)",
                                                "textDecoration": "none",
                                                "display": "flex",
                                                "alignItems": "center",
                                                "justifyContent": "center",
                                                "padding": "0.5rem 1rem",
                                                "transition": "color 0.2s ease"
                                            },
                                            className="peekolive-nav-link"
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

                # Peekolive link - desktop version
                dbc.Col(
                    html.A(
                        [
                            html.Span("Try", style={
                                "fontWeight": "600",
                                "fontSize": "0.95rem",
                                "letterSpacing": "0.5px",
                                "color": "white"
                            }),
                            " ",
                            html.Img(
                                src="/assets/peekolive.png",
                                style={"height": "24px", "width": "auto", "marginLeft": "6px", "marginRight": "6px"}
                            )
                        ],
                        href="/events/peekolive",
                        style={
                            "color": "var(--navbar-text)",
                            "textDecoration": "none",
                            "display": "flex",
                            "alignItems": "center",
                            "padding": "0.5rem 1rem",
                            "transition": "color 0.2s ease",
                            "whiteSpace": "nowrap"
                        },
                        className="peekolive-nav-link"
                    ),
                    width="auto",
                    className="d-none d-md-block align-self-center",
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
                                            style={"textDecoration": "none", "color": "var(--text-primary)", "transition": "all 0.3s ease"},
                                            className="insights-game-link"
                                        ),
                                        className="mb-1",
                                    ),
                                    html.P(
                                        (lambda s: s[:250] + "..." if len(s) > 250 else s)(game.get("summary", "No summary available.")),
                                        style={"color": "var(--text-primary)", "marginBottom": "5px", "fontSize": "0.9rem"},
                                    ),
                                ],
                                width=True,
                            ),
                        ],
                        className="align-items-center",
                    )
                ),
                className="mb-3 insights-card",
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
    event_db = None
    try:
        if year == current_year:
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
            # Only store event_teams (event_key: list of team dicts)
            event_teams = EVENT_TEAMS.get(year, {})
            event_db = {k: v.get("n", "") for k, v in EVENT_DATABASE.get(year, {}).items()}
        else:
            _, ly_event_db, ly_event_teams, _, _, ly_event_matches = load_year_data(year)
            num_events = len(ly_event_db)
            team_set = set()
            for ek, teams in ly_event_teams.items():
                for t in teams:
                    if isinstance(t, dict) and 'tk' in t:
                        team_set.add(t['tk'])
            num_teams = len(team_set)
            num_matches = len(ly_event_matches)
            # Only store event_teams (event_key: list of team dicts)
            event_teams = ly_event_teams
            event_db = {k: v.get("n", "") for k, v in ly_event_db.items()}
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
    # Load insights for the year from DB
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT name, key_type
                FROM insights_rankings
                WHERE year = %s
                GROUP BY name, key_type
                ORDER BY name
                """,
                (year,),
            )
            year_insights = [{"name": row[0], "key_type": row[1]} for row in cur.fetchall()]
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

    if insight_options:
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
        ])
    else:
        insights_section = dbc.Alert(
            "No insights found for this year.",
            color="warning",
            className="mt-4"
        )

    return html.Div(
        [
            topbar(),
            dbc.Container(
                [
                    banner_img if banner_img else None,
                    hero_row,
                    collage_row,
                    insights_section,
                    dcc.Store(id='challenge-event-teams-db', data=event_teams),
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

def map_layout():
    # Generate and get the map file path
    map_path = "assets/teams_map_compressed.html.gz"

    return html.Div([
        topbar(),
        dbc.Container(
            [
                html.Iframe(
                    src=f"/{map_path}",  # Reference the compressed HTML file
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
                        html.H3("Login", style={"textAlign": "center", "marginBottom": "20px", "color": "var(--text-primary)"}),
                        dbc.Input(id="login-username", type="text", placeholder="Username or Email", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1rem"}),
                        dbc.Input(id="login-password", type="password", placeholder="Password", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1.5rem"}),
                        dbc.Button("Login", id="login-btn", style={
                            "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%", "maxWidth": "500px"
                        }),
                        html.Div([
                            html.Span("Don't have an account? ", style={"color": "var(--text-primary)"}),
                            html.A("Register", href="/register", style={"color": "#ffdd00ff", "textDecoration": "underline"})
                        ], style={"textAlign": "center", "marginTop": "1rem"}),
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

def register_layout():
    # Optional redirect if logged in
    if "user_id" in session:
        return dcc.Location(href="/user", id="redirect-to-profile")

    return html.Div([
        topbar(),
        dcc.Location(id="register-redirect", refresh=True),
        dbc.Container(fluid=True, children=[
            dbc.Row(
                dbc.Col(
                    html.Div([
                        html.Img(
                            src="/assets/home.png",
                            style={"width": "100%", "maxWidth": "500px", "marginBottom": "30px"},
                            className="home-image"
                        ),
                        html.H3("Register", style={"textAlign": "center", "marginBottom": "20px", "color": "var(--text-primary)"}),
                        dbc.Input(id="register-username", type="text", placeholder="Username", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1rem"}),
                        dbc.Input(id="register-email", type="email", placeholder="Email (optional)", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1rem"}),
                        dbc.Input(id="register-password", type="password", placeholder="Password", className="custom-input-box", style={"width": "100%", "maxWidth": "500px", "margin": "auto", "marginBottom": "1.5rem"}),
                        dbc.Button("Register", id="register-btn", style={
                            "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%", "maxWidth": "500px"
                        }),
                        html.Div([
                            html.Span("Already have an account? ", style={"color": "var(--text-primary)"}),
                            html.A("Login", href="/login", style={"color": "#ffdd00ff", "textDecoration": "underline"})
                        ], style={"textAlign": "center", "marginTop": "1rem"}),
                        html.Div(id="register-message", style={"textAlign": "center", "marginTop": "1rem", "color": "#333", "fontWeight": "bold"}),
                    ], style={"textAlign": "center", "paddingTop": "50px"})
                , width=12),
            )
        ], class_name="py-5", style={
            "backgroundColor": "var(--bg-primary)",
            "flexGrow": "1" # Added flex-grow
            }),
        footer
    ])

def ace_legend_layout():
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
    
    # Get team colors for background and text color
    background_gradient, text_color = get_team_card_colors_with_text(team_number)

    return dbc.Card(
        [
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "objectFit": "contain",
                    "height": "140px",
                    "padding": "1rem",
                    "backgroundColor": "transparent",
                    "borderRadius": "12px 12px 0 0"
                }
            ),
            dbc.CardBody(
                [
                    html.H5(f"#{team_number} | {nickname}", className="card-title", style={
                        "fontSize": "1.2rem",
                        "fontWeight": "600",
                        "textAlign": "center",
                        "marginBottom": "0.75rem",
                        "color": text_color,
                        "lineHeight": "1.3"
                    }),
                    html.P(f"{location}", className="card-text", style={
                        "fontSize": "0.95rem",
                        "textAlign": "center",
                        "marginBottom": "0.75rem",
                        "color": text_color,
                        "opacity": "0.9",
                        "fontWeight": "400"
                    }),
                    html.P(f"ACE: {epa_display}", className="card-text", style={
                        "fontSize": "0.9rem",
                        "textAlign": "center",
                        "marginBottom": "1rem",
                        "color": text_color,
                        "opacity": "0.85",
                        "fontWeight": "500"
                    }),
                    dbc.Button(
                        f"Peek",
                        href=f"/team/{team_number}/{year}",
                        color="warning",
                        outline=False,
                        className="mt-auto view-team-btn-hover",
                        style={
                            "color": text_color,
                            "border": f"2px solid {text_color}",
                            "borderRadius": "8px",
                            "padding": "8px 16px",
                            "fontSize": "0.9rem",
                            "fontWeight": "500",
                            "backgroundColor": "rgba(255, 255, 255, 0.1)",
                            "transition": "all 0.3s ease-in-out",
                            "backdropFilter": "blur(10px)"
                        }
                    ),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "flexGrow": "1",
                    "justifyContent": "space-between",
                    "padding": "1.25rem",
                    "minHeight": "140px"
                }
            )
        ],
        className="m-2",
        style={
            "width": "18rem",
            "height": "22rem",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "space-between",
            "alignItems": "stretch",
            "borderRadius": "16px",
            "background": background_gradient,
            "border": "none",
            "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.15)",
            "transition": "all 0.3s ease-in-out",
            "overflow": "hidden"
        }
    )

def create_team_card_spotlight(team, year_team_database, event_year):
        t_num = team.get("tk")  # from compressed team list
        
        # Use the passed year_team_database
        team_data = year_team_database.get(event_year, {}).get(t_num, {})
        all_teams = year_team_database.get(event_year, {})

        nickname = team_data.get("nickname", "Unknown")
        city = team_data.get("city", "")
        state = team_data.get("state_prov", "")
        country = team_data.get("country", "")
        location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

        # === Rank Calculation (use global ranking) ===
        # Get global rank from the team data if available, otherwise calculate it
        epa_rank = team_data.get("global_rank", "N/A")
        if epa_rank == "N/A":
            # Fallback: calculate rank from current year data
            team_epas = [
                (tnum, data.get("epa", 0))
                for tnum, data in all_teams.items()
                if isinstance(data, dict)
            ]
            team_epas.sort(key=lambda x: x[1], reverse=True)
            rank_map = {tnum: i + 1 for i, (tnum, _) in enumerate(team_epas)}
            epa_rank = rank_map.get(t_num, "N/A")

        team_epa = team_data.get("epa", 0)
        epa_display = f"{team_epa:.1f}"

        # === Avatar and link ===
        avatar_url = get_team_avatar(t_num, event_year)
        team_url = f"/team/{t_num}/{event_year}"
        
        # Get team colors for background and text color
        background_gradient, text_color = get_team_card_colors_with_text(t_num)

        # === Card Layout ===
        card_body = dbc.CardBody(
            [
                html.H5(f"#{t_num} | {nickname}", className="card-title", style={
                    "fontSize": "1.2rem",
                    "fontWeight": "600",
                    "textAlign": "center",
                    "marginBottom": "0.75rem",
                    "color": text_color,
                    "lineHeight": "1.3"
                }),
                html.P(f"{location_str}", className="card-text", style={
                    "fontSize": "0.95rem",
                    "textAlign": "center",
                    "marginBottom": "0.75rem",
                    "color": text_color,
                    "opacity": "0.9",
                    "fontWeight": "400"
                }),
                html.P(f"ACE: {epa_display}", className="card-text", style={
                    "fontSize": "0.9rem",
                    "textAlign": "center",
                    "marginBottom": "1rem",
                    "color": text_color,
                    "opacity": "0.85",
                    "fontWeight": "500"
                }),
                dbc.Button(
                    "Peek",
                    href=team_url,
                    color="warning",
                    outline=False,
                    className="mt-auto view-team-btn-hover",
                    style={
                        "color": text_color,
                        "border": f"2px solid {text_color}",
                        "borderRadius": "8px",
                        "padding": "8px 16px",
                        "fontSize": "0.9rem",
                        "fontWeight": "500",
                        "backgroundColor": "rgba(255, 255, 255, 0.1)",
                        "transition": "all 0.3s ease-in-out",
                        "backdropFilter": "blur(10px)"
                    }
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "flexGrow": "1",
                "justifyContent": "space-between",
                "padding": "1.25rem",
                "minHeight": "140px"
            }
        )

        card_elements = []
        if avatar_url:
            card_elements.append(
                dbc.CardImg(
                    src=avatar_url,
                    top=True,
                    style={
                        "width": "100%",
                        "height": "140px",
                        "objectFit": "contain",
                        "backgroundColor": "transparent",
                        "padding": "1rem",
                        "borderRadius": "16px 16px 0 0"
                    }
                )
            )

        card_elements.append(card_body)

        return dbc.Card(
            card_elements,
            className="m-2",
            style={
                "width": "18rem",
                "height": "22rem",
                "display": "flex",
                "flexDirection": "column",
                "justifyContent": "space-between",
                "alignItems": "stretch",
                "borderRadius": "16px",
                "background": background_gradient,
                "border": "none",
                "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.15)",
                "transition": "all 0.3s ease-in-out",
                "overflow": "hidden"
            },
        )

def create_team_card_spotlight_event(team, event_team_data, event_year, event_rank_map):
    """Create a spotlight card for event-specific stats with team gradients."""
    t_num = team.get("tk")  # from compressed team list
    
    # Get team info from event_teams
    nickname = team.get('nn', 'Unknown')
    city = team.get("c", "")
    state = team.get("s", "")
    country = team.get("co", "")
    location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"
    
    # Calculate event-specific rank
    team_event_epa = event_team_data.get("epa", 0)
    event_rank = event_rank_map.get(team_event_epa, "N/A")
    
    # === Avatar and link ===
    avatar_url = get_team_avatar(t_num, event_year)
    team_url = f"/team/{t_num}/{event_year}"
    
    # Get team colors for background and text color
    background_gradient, text_color = get_team_card_colors_with_text(t_num)

    # === Card Layout ===
    card_body = dbc.CardBody(
        [
            html.H5(f"#{t_num} | {nickname}", className="card-title", style={
                "fontSize": "1.2rem",
                "fontWeight": "600",
                "textAlign": "center",
                "marginBottom": "0.75rem",
                "color": text_color,
                "lineHeight": "1.3"
            }),
            html.P(f"{location_str}", className="card-text", style={
                "fontSize": "0.95rem",
                "textAlign": "center",
                "marginBottom": "0.75rem",
                "color": text_color,
                "opacity": "0.9",
                "fontWeight": "400"
            }),
            html.P(f"Event ACE: {team_event_epa:.1f} (Event Rank: {event_rank})", className="card-text", style={
                "fontSize": "0.9rem",
                "textAlign": "center",
                "marginBottom": "1rem",
                "color": text_color,
                "opacity": "0.85",
                "fontWeight": "500"
            }),
            dbc.Button(
                "Peek",
                href=team_url,
                color="warning",
                outline=False,
                className="mt-auto view-team-btn-hover",
                style={
                    "color": text_color,
                    "border": f"2px solid {text_color}",
                    "borderRadius": "8px",
                    "padding": "8px 16px",
                    "fontSize": "0.9rem",
                    "fontWeight": "500",
                    "backgroundColor": "rgba(255, 255, 255, 0.1)",
                    "transition": "all 0.3s ease-in-out",
                    "backdropFilter": "blur(10px)"
                }
            ),
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "flexGrow": "1",
            "justifyContent": "space-between",
            "padding": "1.25rem",
            "minHeight": "140px"
        }
    )

    card_elements = []
    if avatar_url:
        card_elements.append(
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "width": "100%",
                    "height": "140px",
                    "objectFit": "contain",
                    "backgroundColor": "transparent",
                    "padding": "1rem",
                    "borderRadius": "16px 16px 0 0"
                }
            )
        )

    card_elements.append(card_body)

    return dbc.Card(
        card_elements,
        className="m-2",
        style={
            "width": "18rem",
            "height": "22rem",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "space-between",
            "alignItems": "stretch",
            "borderRadius": "16px",
            "background": background_gradient,
            "border": "none",
            "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.15)",
            "transition": "all 0.3s ease-in-out",
            "overflow": "hidden"
        },
    )

def teams_layout(default_year=current_year):
    teams_year_dropdown = dcc.Dropdown(
        id="teams-year-dropdown",
        options=[{"label": str(y), "value": y} for y in reversed(range(1992, 2027))],
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
            *get_team_district_options()
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
        style={
            "marginTop": "0px",
            "--bs-primary": "#ffdd00",  # Yellow color when on
            "--bs-secondary": "#6c757d",  # Dark gray when off
            "--bs-body-bg": "#2d2d2d",  # Dark background
            "--bs-body-color": "#ffffff",  # White text
        }
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
            {"label": "RAW", "value": "raw"},
            {"label": "ACE", "value": "ace"},
            {"label": "Auto % of ACE", "value": "auto_share"},
            {"label": "Teleop % of ACE", "value": "teleop_share"},
            {"label": "Endgame % of ACE", "value": "endgame_share"},
            {"label": "Win Rate", "value": "win_rate"},
            {"label": "Team Number", "value": "team_number"},
            {"label": "Confidence", "value": "confidence"},
            {"label": "Wins", "value": "wins"},
            {"label": "Losses", "value": "losses"},
            {"label": "Ties", "value": "ties"},
            {"label": "Favorites", "value": "favorites"},
        ],
        value="teleop_epa",
        clearable=False,
        style={"width": "160px"},
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
            {"label": "RAW", "value": "raw"},
            {"label": "ACE", "value": "ace"},
            {"label": "Auto % of ACE", "value": "auto_share"},
            {"label": "Teleop % of ACE", "value": "teleop_share"},
            {"label": "Endgame % of ACE", "value": "endgame_share"},
            {"label": "Win Rate", "value": "win_rate"},
            {"label": "Team Number", "value": "team_number"},
            {"label": "Confidence", "value": "confidence"},
            {"label": "Wins", "value": "wins"},
            {"label": "Losses", "value": "losses"},
            {"label": "Ties", "value": "ties"},
            {"label": "Favorites", "value": "favorites"},
        ],
        value="auto+endgame",
        clearable=False,
        style={"width": "160px"},
        className="custom-input-box"
    )

    z_axis_dropdown = dcc.Dropdown(
        id="z-axis-dropdown",
        options=[
            {"label": "Teleop", "value": "teleop_epa"},
            {"label": "Auto", "value": "auto_epa"},
            {"label": "Endgame", "value": "endgame_epa"},
            {"label": "Auto+Teleop", "value": "auto+teleop"},
            {"label": "Auto+Endgame", "value": "auto+endgame"},
            {"label": "Teleop+Endgame", "value": "teleop+endgame"},
            {"label": "RAW", "value": "raw"},
            {"label": "ACE", "value": "ace"},
            {"label": "Auto % of ACE", "value": "auto_share"},
            {"label": "Teleop % of ACE", "value": "teleop_share"},
            {"label": "Endgame % of ACE", "value": "endgame_share"},
            {"label": "Win Rate", "value": "win_rate"},
            {"label": "Team Number", "value": "team_number"},
            {"label": "Confidence", "value": "confidence"},
            {"label": "Wins", "value": "wins"},
            {"label": "Losses", "value": "losses"},
            {"label": "Ties", "value": "ties"},
            {"label": "Favorites", "value": "favorites"},
        ],
        value="ace",
        clearable=False,
        style={"width": "160px"},
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
                dbc.Col(html.Label("Color:", style={"color": "var(--text-primary)"}), width="auto"),
                dbc.Col(z_axis_dropdown, width=3),
            ], className="align-items-center axis-dropdown-row")
        ],
        style={"display": "none", "marginBottom": "5px", "marginTop": "0px"}
    )

    search_input = dcc.Input(
        id="search-bar",
        type="text",
        debounce=True,
        placeholder="Search teams..",
        className="custom-input-box",
        style={
            "width": "100%",
            "padding": "10px 14px",
            "borderRadius": "12px",         # Rounded corners
            "border": "1px solid #ccc",     # Light flat border
            "outline": "none",              # Remove focus border glow
            "boxShadow": "none",            # Remove any shadows
            "fontSize": "16px",
            "backgroundColor": "#f8f9fa",   # Light gray background (flat)
        },
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
            {"name": "ACE Rank", "id": "ace_rank", "type": "numeric"},
            {"name": "Team #", "id": "team_number", "type": "numeric"},
            {"name": "Nickname", "id": "nickname", "presentation": "markdown"},
            {"name": "RAW", "id": "epa", "type": "numeric"},
            {"name": "Confidence", "id": "confidence", "type": "numeric"},
            {"name": "ACE", "id": "ace", "type": "numeric"},
            {"name": "Auto", "id": "auto_epa", "type": "numeric"},
            {"name": "Teleop", "id": "teleop_epa", "type": "numeric"},
            {"name": "Endgame", "id": "endgame_epa", "type": "numeric"},
            {"name": "Favorites", "id": "favorites", "type": "numeric"},
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
        dcc.Graph(
            id="bubble-chart", 
            style={
                "display": "none", 
                "height": "600px",
                "width": "100%",
                "maxWidth": "100%"
            },
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d"],
                "responsive": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": "team_performance_chart",
                    "height": 600,
                    "width": 800,
                    "scale": 2
                }
            }
        )
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
                ace_legend_layout(),
                tabs,
                content,
            ], style={
                "padding": "10px",
                "maxWidth": "1200px",
                "margin": "0 auto",
                "flexGrow": "1"
            }),
            footer,
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "minHeight": "100vh",
            "backgroundColor": "var(--bg-primary)"
        }
    )

def events_layout(year=current_year, active_tab="cards-tab"):
    year_dropdown = dcc.Dropdown(
        id="year-dropdown",
        options=[{"label": str(yr), "value": yr} for yr in reversed(range(1992, 2027))],
        value=year,
        placeholder="Year",
        clearable=False
    )
    event_type_dropdown = dcc.Dropdown(
        id="event-type-dropdown",
        options=[
            {"label": "Pre-Season", "value": "Preseason"},
            {"label": "Regional", "value": "Regional"},
            {"label": "District", "value": "District"},
            {"label": "District Champs", "value": "District Championship"},
            {"label": "District Champs Division", "value": "District Championship Division"},
            {"label": "Champs Division", "value": "Championship Division"},
            {"label": "Champs Finals", "value": "Championship Finals"},
            {"label": "Off-Season", "value": "Offseason"},
        ],
        value=[],
        multi=True,
        placeholder="Event Type",
        clearable=True,
        className="custom-input-box"
    )
    # Dynamically generate week options based on stored weeks for the year
    try:
        from peekorobo import EVENT_DATABASE
        year_events = EVENT_DATABASE.get(year, {})
        weeks = sorted({ev.get("wk") for ev in year_events.values() if ev.get("wk") is not None})
    except Exception:
        weeks = []
    week_options = [{"label": "All Wks", "value": "all"}]
    for wk in weeks:
        week_options.append({"label": f"Wk {wk + 1}", "value": wk})
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
                        active_tab=active_tab,
                        children=[
                            dbc.Tab(label="Cards", tab_id="cards-tab", active_label_style=tab_style),
                            dbc.Tab(label="Event Insights", tab_id="table-tab", active_label_style=tab_style),
                            dbc.Tab(label="Peekolive", tab_id="peekolive-tab", active_label_style=tab_style),
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
            footer,
        ]
    )

def build_recent_events_section(team_key, team_number, team_epa_data, performance_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS, table_style="team", include_header=True):
    epa_data = team_epa_data or {}

    recent_rows = []
    year = performance_year

    def parse_event_year(event_key):
        try:
            return int(str(event_key)[:4])
        except Exception:
            return None
    # Get all events the team attended with start dates
    event_dates = []
    
    year_events = EVENT_DATABASE.get(performance_year, {}) if isinstance(EVENT_DATABASE, dict) else EVENT_DATABASE

    has_year_keys = isinstance(EVENT_TEAMS, dict) and performance_year in EVENT_TEAMS
    
    for ek, ev in year_events.items():
        # Handle both data structures
        if has_year_keys:
            # current yearstructure: EVENT_TEAMS[year][event_key]
            event_teams = EVENT_TEAMS.get(performance_year, {}).get(ek, [])
        else:
            # before current year structure: EVENT_TEAMS[event_key]
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
            # current year structure: EVENT_TEAMS[year][event_key]
            event_teams = EVENT_TEAMS.get(year, {}).get(event_key, [])
        else:
            # before current year structure: EVENT_TEAMS[event_key]
            event_teams = EVENT_TEAMS.get(event_key, []) if isinstance(EVENT_TEAMS, dict) else EVENT_TEAMS
    
        # Skip if team wasn't on the team list
        if not any(int(t["tk"]) == team_number for t in event_teams if "tk" in t):
            continue
    
        # === Special check for Einstein (2025cmptx) ===
        if event_key == "2025cmptx":
            # Handle both data structures for matches
            if has_year_keys:
                # current year structure: EVENT_MATCHES[year]
                year_matches = EVENT_MATCHES.get(year, [])
            else:
                # before current year structure: EVENT_MATCHES is a list
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
                if a["tk"] == team_number
                and a["ek"] == "2025cmptx"
                and parse_event_year(a.get("ek")) == year
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
            # current year structure: EVENT_RANKINGS[year][event_key]
            ranking = EVENT_RANKINGS.get(year, {}).get(event_key, {}).get(team_number, {})
        else:
            # before current year structure: EVENT_RANKINGS[event_key]
            ranking = EVENT_RANKINGS.get(event_key, {}).get(team_number, {}) if isinstance(EVENT_RANKINGS, dict) else {}
        rank_val = ranking.get("rk", "N/A")
        total_teams = len(event_teams)

        # EVENT_AWARDS is always a list
        award_names = [
            a["an"] for a in EVENT_AWARDS
            if a["tk"] == team_number
            and a["ek"] == event_key
            and parse_event_year(a.get("ek")) == year
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

        # Placeholder for record - will be calculated after all_event_matches is defined
        record = None

        # Get event-specific data
        event_epa_pills = None
        if year >= 2015:
            # Access event_epas from the specific team's data within the epa_data dictionary
            team_specific_event_epas = epa_data.get(str(team_number), {}).get("event_epas", [])
            # Handle both event key formats (with and without "frc" prefix)
            event_key_clean = event_key.replace("frc", "") if event_key.startswith("frc") else event_key
            event_epa = next((e for e in team_specific_event_epas if str(e.get("event_key")) == str(event_key_clean)), None)
            if event_epa:
                # Fixed colors to match screenshot styling for consistency
                auto_color = "#1976d2"     # Blue
                teleop_color = "#fb8c00"   # Orange
                endgame_color = "#388e3c"  # Green
                norm_color = "#d32f2f"    # Red 
                conf_color = "#555"   # Gray
                total_color = "#673ab7" # Purple
                event_epa_pills = html.Div([
                    html.Div([
                        pill("Auto", f"{event_epa['auto']:.1f}", auto_color),
                        pill("Teleop", f"{event_epa['teleop']:.1f}", teleop_color),
                        pill("Endgame", f"{event_epa['endgame']:.1f}", endgame_color),
                        pill("RAW", f"{event_epa['overall']:.1f}", norm_color),
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
                print(f"No event stats found for {event_key}")
        else:
            event_epa_pills = html.Div() # Ensure it's an empty div if no data, not None

        # Get week label for the event (stored week is 0-based)
        week_label = get_event_week_label_from_number(event.get("wk"))

        # Handle both data structures for matches
        if has_year_keys:
            # 2025 structure: EVENT_MATCHES[year]
            year_matches = EVENT_MATCHES.get(year, [])
        else:
            # 2024 structure: EVENT_MATCHES is a list
            year_matches = EVENT_MATCHES
        
        # Get ALL matches for this event
        all_event_matches = [m for m in year_matches if m.get("ek") == event_key]
        
        # Calculate record from match data instead of rankings
        wins = 0
        losses = 0
        ties = 0
        
        # Get matches for this team in this event
        team_matches = [
            m for m in all_event_matches
            if str(team_number) in m.get("rt", "").split(",") or str(team_number) in m.get("bt", "").split(",")
        ]
        
        for match in team_matches:
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            winner = match.get("wa") or "Tie"
            winner = winner.lower() if winner else "tie"
            
            # Handle disqualifications (score of 0) as ties
            if red_score == 0 or blue_score == 0:
                ties += 1
                continue
                
            # Determine team's alliance
            team_alliance = None
            if str(team_number) in match.get("rt", "").split(","):
                team_alliance = "red"
            elif str(team_number) in match.get("bt", "").split(","):
                team_alliance = "blue"
            else:
                continue  # Team not in this match
            
            # Count wins, losses, ties
            if winner == "tie" or winner == "" or red_score == blue_score:
                ties += 1
            elif winner == team_alliance:
                wins += 1
            else:
                losses += 1
        
        record = html.Span([
            html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#777"}),
            html.Span(str(losses), style={"color": "red", "fontWeight": "bold"}),
            html.Span("-", style={"color": "#777"}),
            html.Span(str(ties), style={"color": "gray", "fontWeight": "bold"})
        ])
        
        def get_team_epa_info(t_key):
            # First try to get event-specific stats for this team
            t_data = epa_data.get(t_key.strip(), {})
            # Handle both event key formats (with and without "frc" prefix)
            event_key_clean = event_key.replace("frc", "") if event_key.startswith("frc") else event_key
            event_epa = next((e for e in t_data.get("event_epas", []) if e.get("event_key") == event_key_clean), None)
            if event_epa and event_epa.get("overall", 0) != 0:
                return {
                    "team_number": int(t_key.strip()),
                    "epa": event_epa.get("overall", 0),
                    "confidence": event_epa.get("confidence", 0.7),
                    "consistency": event_epa.get("consistency", 0)
                }
            
            # If no event-specific stats, try to get team's overall stats
            if t_data.get("epa") not in (None, ""):
                epa_val = t_data.get("epa", 0)
                conf_val = t_data.get("confidence", 0.7)
                return {
                    "team_number": int(t_key.strip()),
                    "epa": epa_val,
                    "confidence": conf_val,
                    "consistency": t_data.get("consistency", 0)
                }
            
            # If still no data, try to get from team database for the year
            try:
                if year == current_year:
                    from peekorobo import TEAM_DATABASE
                    team_data = TEAM_DATABASE.get(year, {}).get(int(t_key.strip()), {})
                else:
                    from datagather import load_year_data
                    year_team_data, _, _, _, _, _ = load_year_data(year)
                    team_data = year_team_data.get(int(t_key.strip()), {})
                
                return {
                    "team_number": int(t_key.strip()),
                    "epa": team_data.get("epa", 0),
                    "confidence": team_data.get("confidence", 0.7),
                    "consistency": team_data.get("consistency", 0)
                }
            except Exception:
                # Final fallback
                return {"team_number": int(t_key.strip()), "epa": 0, "confidence": 0.7, "consistency": 0}

        # Filter to only show matches the team played in
        matches = [
            m for m in all_event_matches
            if str(team_number) in m.get("rt", "").split(",") or str(team_number) in m.get("bt", "").split(",")
        ]

        # Calculate prediction accuracy for this team in this event
        def compute_team_event_accuracy(team_matches):
            total = 0
            correct = 0
            excluded_ties = 0
            
            for match in team_matches:
                red_score = match.get("rs", 0)
                blue_score = match.get("bs", 0)
                winner = match.get("wa") or "Tie"
                winner = winner.lower() if winner else "tie"
                
                # Only count completed matches
                if red_score <= 0 or blue_score <= 0:
                    continue
                
                # Determine team's alliance
                team_alliance = None
                if str(team_number) in match.get("rt", "").split(","):
                    team_alliance = "red"
                elif str(team_number) in match.get("bt", "").split(","):
                    team_alliance = "blue"
                else:
                    continue  # Team not in this match
                
                # Get prediction for this match
                red_str = match.get("rt", "")
                blue_str = match.get("bt", "")
                red_team_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
                blue_team_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]
                
                if red_team_info and blue_team_info:
                    p_red, p_blue = predict_win_probability(red_team_info, blue_team_info)
                    
                    if winner == "tie" or winner == "":
                        # Only count as correct if prediction is 50%
                        team_prediction = p_red if team_alliance == "red" else p_blue
                        if abs(team_prediction - 0.5) < 0.01:  # Within 1% of 50%
                            total += 1
                            correct += 1
                        else:
                            excluded_ties += 1
                    elif winner in ["red", "blue"]:
                        total += 1
                        team_prediction = p_red if team_alliance == "red" else p_blue
                        
                        # Check if prediction was correct
                        if (team_alliance == winner and team_prediction > 0.5) or (team_alliance != winner and team_prediction < 0.5):
                            correct += 1
            
            acc = (correct / total * 100) if total > 0 else 0
            return correct, total, acc, excluded_ties

        # Calculate accuracy for this event
        correct, total, accuracy, excluded_ties = compute_team_event_accuracy(matches)
        
        # Create accuracy badge
        def accuracy_badge(correct, total, acc, excluded_ties):
            if excluded_ties:
                note = f" (excluding {excluded_ties} ties)" if excluded_ties > 1 else f" (excluding {excluded_ties} tie)"
            else:
                note = ""
            return html.Span(
                f"Prediction Accuracy: {correct}/{total} ({acc:.0f}%)" + note,
                style={
                    "color": "var(--text-secondary)",
                    "fontSize": "0.9rem",
                    "fontWeight": "normal"
                }
            )

        header = html.Div([
            html.Div([
                html.Div([
                    html.A(str(year) + " " + event_name, href=event_url, style={"fontWeight": "bold", "fontSize": "1.1rem"}),
                    html.Span(f" ({week_label})", style={"color": "var(--text-muted)", "fontSize": "0.9rem", "marginLeft": "8px"}) if week_label else None,
                ], style={"flex": "1"}),
                accuracy_badge(correct, total, accuracy, excluded_ties) if total > 0 else None,
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
            html.Div(loc),
            html.Div(rank_str),
            html.Div([
                html.Span("Record: ", style={"marginRight": "5px"}),
                record,
                html.Div(awards_line),
                event_epa_pills if event_epa_pills else None,
            ]),
        ], style={"marginBottom": "20px"})

        def build_match_rows(matches, table_style="team"):
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
                return "  ".join(f"[{t}](/team/{t}/{current_year})" for t in team_str.split(",") if t.strip().isdigit())
        
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
                red_team_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
                blue_team_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]
                if red_team_info and blue_team_info:
                    # Use simple prediction
                    p_red, p_blue = predict_win_probability(red_team_info, blue_team_info)
                    if p_red == 0.5 and p_blue == 0.5:
                        pred_red = "50%"
                        pred_blue = "50%"
                        pred_winner = "Tie"
                    else:
                        pred_red = f"{p_red:.0%}"
                        pred_blue = f"{p_blue:.0%}"
                        pred_winner = "Red" if p_red > p_blue else "Blue"
                else:
                    p_red = p_blue = None
                    pred_red = pred_blue = "N/A"
                    pred_winner = "Tie"
        
                winner = match.get("wa") or "Tie"
                winner = winner.title() if winner else "Tie"
                youtube_id = match.get("yt")
                video_link = f"[▶](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
                
                team_alliance = None
                if str(team_number) in red_str:
                    team_alliance = "Red"
                elif str(team_number) in blue_str:
                    team_alliance = "Blue"

                if table_style == "both":
                    row = {
                        "Video": video_link,
                        "Match": match_label_md,
                        "Red Alliance": format_team_list(red_str),
                        "Blue Alliance": format_team_list(blue_str),
                        "Red Score": red_score,
                        "Blue Score": blue_score,
                        "Winner": winner,
                        "Pred Winner": pred_winner,
                        "Red Pred": pred_red,
                        "Blue Pred": pred_blue,
                        "Red Prediction %": p_red * 100 if p_red is not None else None,
                        "Blue Prediction %": p_blue * 100 if p_blue is not None else None,
                        "rowColor": "#ffe6e6" if winner == "Red" else "#e6f0ff" if winner == "Blue" else "white",
                    }
                else:
                    team_prediction = "N/A"
                    team_prediction_percent = None
                    if team_alliance == "Red" and p_red is not None:
                        team_prediction = pred_red
                        team_prediction_percent = p_red * 100
                    elif team_alliance == "Blue" and p_blue is not None:
                        team_prediction = pred_blue
                        team_prediction_percent = p_blue * 100
                    
                    row = {
                        "Video": video_link,
                        "Match": match_label_md,
                        "Alliance": team_alliance or "N/A",
                        "Red Alliance": format_team_list(red_str),
                        "Blue Alliance": format_team_list(blue_str),
                        "Score": red_score if team_alliance == "Red" else blue_score if team_alliance == "Blue" else "N/A",
                        "Opponent Score": blue_score if team_alliance == "Red" else red_score if team_alliance == "Blue" else "N/A",
                        "Winner": winner,
                        "Prediction": f"{team_prediction}".strip(),
                        "Prediction %": team_prediction_percent,
                        "Outcome": "",
                        "rowColor": "#ffe6e6" if winner == "Red" else "#e6f0ff" if winner == "Blue" else "white",
                    }

                row["team_alliance"] = team_alliance

                rows.append(row)

            return rows

        match_rows = build_match_rows(matches, table_style)

        if table_style == "both":
            match_columns = [
                {"name": "Video", "id": "Video", "presentation": "markdown"},
                {"name": "Match", "id": "Match", "presentation": "markdown"},
                {"name": "Red Alliance", "id": "Red Alliance", "presentation": "markdown"},
                {"name": "Blue Alliance", "id": "Blue Alliance", "presentation": "markdown"},
                {"name": "Red Score", "id": "Red Score"},
                {"name": "Blue Score", "id": "Blue Score"},
                {"name": "Winner", "id": "Winner"},
                {"name": "Pred Winner", "id": "Pred Winner"},
                {"name": "Red Pred", "id": "Red Pred"},
                {"name": "Blue Pred", "id": "Blue Pred"},
            ]
            row_style = [
                {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
                {"if": {"column_id": "Red Alliance"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Blue Alliance"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Red Score"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Blue Score"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"filter_query": "{Red Prediction %} >= 45 && {Red Prediction %} < 50", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lowneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} >= 50 && {Red Prediction %} < 55", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-highneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} >= 55 && {Red Prediction %} <= 65", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} > 65 && {Red Prediction %} <= 75", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} > 75 && {Red Prediction %} <= 85", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} > 85 && {Red Prediction %} <= 95", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} > 95", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} < 45 && {Red Prediction %} >= 35", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} < 35 && {Red Prediction %} >= 25", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} < 25 && {Red Prediction %} >= 15", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} < 15 && {Red Prediction %} >= 5", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-darkred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Red Prediction %} < 5", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-deepred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} >= 45 && {Blue Prediction %} < 50", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lowneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} >= 50 && {Blue Prediction %} < 55", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-highneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} >= 55 && {Blue Prediction %} <= 65", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} > 65 && {Blue Prediction %} <= 75", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} > 75 && {Blue Prediction %} <= 85", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} > 85 && {Blue Prediction %} <= 95", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} > 95", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} < 45 && {Blue Prediction %} >= 35", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} < 35 && {Blue Prediction %} >= 25", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} < 25 && {Blue Prediction %} >= 15", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} < 15 && {Blue Prediction %} >= 5", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-darkred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Blue Prediction %} < 5", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-deepred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Pred Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Pred Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Pred Winner} = "Tie"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-yellow)", "color": "var(--text-primary)"},
                {"if": {"column_id": "Video"}, "textDecoration": "none"},
                {"if": {"column_id": "Match"}, "textDecoration": "none"},
                {"if": {"column_id": "Red Alliance"}, "textDecoration": "none"},
                {"if": {"column_id": "Blue Alliance"}, "textDecoration": "none"},
            ]
        else:
            match_columns = [
                {"name": "Video", "id": "Video", "presentation": "markdown"},
                {"name": "Match", "id": "Match", "presentation": "markdown"},
                {"name": "Alliance", "id": "Alliance"},
                {"name": "Red Alliance", "id": "Red Alliance", "presentation": "markdown"},
                {"name": "Blue Alliance", "id": "Blue Alliance", "presentation": "markdown"},
                {"name": "Score", "id": "Score"},
                {"name": "Opponent Score", "id": "Opponent Score"},
                {"name": "Winner", "id": "Winner"},
                {"name": "Prediction", "id": "Prediction"},
                {"name": "Outcome", "id": "Outcome"},
            ]
            row_style = [
                {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} >= 45 && {Prediction %} < 50", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lowneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} >= 50 && {Prediction %} < 55", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-highneutral)", "fontWeight": "bold", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} >= 55 && {Prediction %} <= 65", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} > 65 && {Prediction %} <= 75", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} > 75 && {Prediction %} <= 85", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} > 85 && {Prediction %} <= 95", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} > 95", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} < 45 && {Prediction %} >= 35", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} < 35 && {Prediction %} >= 25", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} < 25 && {Prediction %} >= 15", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-lightred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} < 15 && {Prediction %} >= 5", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-darkred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": "{Prediction %} < 5", "column_id": "Prediction"}, "backgroundColor": "var(--table-row-prediction-deepred)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Red" && {Alliance} = "Red"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-green)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Red" && {Alliance} != "Red"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Blue" && {Alliance} = "Blue"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-green)", "color": "var(--text-primary)"},
                {"if": {"filter_query": '{Winner} = "Blue" && {Alliance} != "Blue"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
                {"if": {"column_id": "Red Alliance"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Blue Alliance"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Score"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Opponent Score"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"filter_query": '{team_alliance} = "Red"', "column_id": "Red Alliance"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"filter_query": '{team_alliance} = "Blue"', "column_id": "Blue Alliance"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
                {"if": {"column_id": "Video"}, "textDecoration": "none"},
                {"if": {"column_id": "Match"}, "textDecoration": "none"},
                {"if": {"column_id": "Red Alliance"}, "textDecoration": "none"},
                {"if": {"column_id": "Blue Alliance"}, "textDecoration": "none"},
            ]

        table = html.Div(
            dash_table.DataTable(
                columns=match_columns,
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
                    "backgroundColor": "transparent",
                    "color": "var(--text-primary)",
                    "textAlign": "center",
                    "padding": "10px",
                    "border": "none",
                    "fontSize": "14px",
                    "fontWeight": "bold",
                },
                style_data_conditional=[
                    {
                        "if": {"state": "active"},
                        "backgroundColor": "inherit",
                        "border": "inherit",
                        "color": "inherit",
                    },
                    *row_style
                ]
            ),
            className="recent-events-table"
        )

        recent_rows.append(
            html.Div([
                header,
                table,
            ], style={"marginBottom": "30px"})
        )
    
    content = html.Div(recent_rows)
    if include_header:
        return html.Div([
            html.H3("Recent Events", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
            content
        ])
    return content

def get_peekolive_events_categorized(include_all: bool = False):
    """Get peekolive events categorized into completed, ongoing, and upcoming."""
    today = date.today()
    completed_events = []
    ongoing_events = []
    upcoming_events = []
    
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT event_key, name, start_date, end_date, webcast_type, webcast_channel, city, state_prov, country, week
                FROM events
                WHERE webcast_type IS NOT NULL AND webcast_channel IS NOT NULL
                ORDER BY start_date NULLS LAST
                """
            )
            rows = cur.fetchall()
            for row in rows:
                ek, name, sd, ed, wtype, wchan, city, state, country, week = row
                try:
                    year = int(str(ek)[:4])
                except Exception:
                    year = None
                try:
                    sd_d = datetime.strptime(sd, "%Y-%m-%d").date() if sd else None
                    ed_d = datetime.strptime(ed, "%Y-%m-%d").date() if ed else None
                except Exception:
                    sd_d, ed_d = None, None
                
                event_data = {
                    "event_key": ek,
                    "name": name,
                    "webcast_type": (wtype or "").lower(),
                    "webcast_channel": wchan,
                    "start_date": sd,
                    "end_date": ed,
                    "year": year,
                    "location": ", ".join([v for v in [city, state, country] if v]),
                    "week": week
                }
                
                # Categorize events
                if sd_d and ed_d:
                    if ed_d < today:
                        completed_events.append(event_data)
                    elif sd_d <= today <= ed_d:
                        ongoing_events.append(event_data)
                    elif sd_d > today:
                        upcoming_events.append(event_data)
                elif sd_d and not ed_d:
                    if sd_d < today:
                        completed_events.append(event_data)
                    elif sd_d == today:
                        ongoing_events.append(event_data)
                    elif sd_d > today:
                        upcoming_events.append(event_data)
                elif not sd_d and ed_d:
                    if ed_d < today:
                        completed_events.append(event_data)
                    elif ed_d == today:
                        ongoing_events.append(event_data)
                else:
                    # No date info, treat as upcoming
                    upcoming_events.append(event_data)
            cur.close()
    except Exception:
        pass

    # Limit events per category when not showing all
    if not include_all:
        def sort_key(ev):
            try:
                return datetime.strptime(ev.get("start_date") or "0001-01-01", "%Y-%m-%d")
            except Exception:
                return datetime.min
        
        # Sort and limit each category
        completed_events = sorted(completed_events, key=sort_key, reverse=True)[:9]  # Most recent completed
        ongoing_events = sorted(ongoing_events, key=sort_key)[:9]  # Current ongoing
        upcoming_events = sorted(upcoming_events, key=sort_key)[:9]  # Nearest upcoming
    
    return {
        "completed": completed_events,
        "ongoing": ongoing_events,
        "upcoming": upcoming_events
    }

def get_peekolive_events(include_all: bool = False):
    """Get peekolive events as a flat list (for search callback compatibility)."""
    categorized = get_peekolive_events_categorized(include_all)
    # Return all events as a flat list for search functionality
    return categorized["completed"] + categorized["ongoing"] + categorized["upcoming"]

def peekolive_embed_for(ev):
    wtype = ev.get("webcast_type", "").lower()
    channel = (ev.get("webcast_channel") or "").strip()
    title = f"{ev.get('event_key')} | {ev.get('name', '')}"
    if not channel:
        return html.Div(title)
    if wtype == "youtube":
        src = f"https://www.youtube.com/embed/{channel}?autoplay=1&mute=1&rel=0"
        return html.Iframe(
            src=src,
            style={
                "width": "100%",
                "height": "100%",
                "border": "0",
                "maxHeight": "500px",
                "objectFit": "cover"
            },
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen",
            title=title,
        )
    if wtype == "twitch":
        # Build Twitch parent list: current request host + defaults
        try:
            req_host = (_flask_request.host or "").split(":")[0]
        except Exception:
            req_host = ""
        parent_list = []
        if req_host:
            parent_list.append(req_host)
        # Sensible defaults for dev/prod
        parent_list += [
            "www.peekorobo.com",
            "localhost",
            "127.0.0.1",
        ]
        # De-duplicate and drop empties
        uniq_parents = []
        for p in parent_list:
            if p and p not in uniq_parents:
                uniq_parents.append(p)
        parent_qs = "".join([f"&parent={p}" for p in uniq_parents])
        src = f"https://player.twitch.tv/?channel={channel}{parent_qs}&muted=true&autoplay=true"
        return html.Iframe(
            src=src,
            style={
                "width": "100%",
                "height": "100%",
                "border": "0",
                "maxHeight": "500px",
                "objectFit": "cover"
            },
            allow="autoplay; fullscreen",
            title=title,
        )
    # Fallback: show link
    return html.A(f"{wtype}: {channel}", href=f"/event/{ev.get('event_key')}")

def build_peekolive_layout_with_events(events_data, detected_team=None):
    """Build PeekoLive layout with pre-filtered events data."""
    # Check if any events exist
    total_events = len(events_data["completed"]) + len(events_data["ongoing"]) + len(events_data["upcoming"])
    if total_events == 0:
        return html.Div([
            dbc.Container([
                # Enhanced logo section
                html.Div([
                    html.Img(src="/assets/peekolive.png", style={
                        "height": "100px", 
                        "margin": "0 auto 20px", 
                        "display": "block"
                    })
                ], className="mb-4"),
                
                # Enhanced empty state
                html.Div([
                    html.Div([
                        html.I(className="fas fa-video-slash", style={
                            "fontSize": "4rem",
                            "color": "var(--text-secondary)",
                            "marginBottom": "20px",
                            "opacity": "0.6"
                        }),
                        html.H3("No Live Events", style={
                            "color": "var(--text-primary)",
                            "fontWeight": "600",
                            "fontSize": "1.8rem",
                            "marginBottom": "15px"
                        }),
                        html.P("There are currently no live FRC events streaming. Check back later for upcoming competitions!", style={
                            "color": "var(--text-secondary)",
                            "fontSize": "1.1rem",
                            "lineHeight": "1.6",
                            "marginBottom": "25px",
                            "maxWidth": "500px",
                            "margin": "0 auto 25px"
                        }),
                        html.Div([
                            html.I(className="fas fa-clock", style={"marginRight": "8px", "color": "var(--text-secondary)"}),
                            html.Span("Events typically stream during competition weekends", style={
                                "color": "var(--text-secondary)",
                                "fontSize": "0.95rem",
                                "fontStyle": "italic"
                            })
                        ], style={"textAlign": "center"})
                    ], style={
                        "textAlign": "center",
                        "padding": "60px 20px",
                        "background": "var(--card-bg)",
                        "borderRadius": "16px",
                        "border": "1px solid var(--border-color)",
                        "boxShadow": "0 4px 20px rgba(0,0,0,0.08)"
                    })
                ], style={"maxWidth": "600px", "margin": "0 auto"})
            ], style={"maxWidth": "1400px", "padding": "20px"}),
        ])

    def build_event_card(ev, event_status="ongoing"):
        # Create the card with relative positioning for the indicator and fixed height
        card_style = {
            "backgroundColor": "var(--card-bg)", 
            "position": "relative",
            "height": "350px",
            "display": "flex",
            "flexDirection": "column",
            "borderRadius": "16px",
            "boxShadow": "0 4px 20px rgba(0,0,0,0.08)",
            "border": "1px solid var(--border-color)",
            "transition": "all 0.3s ease",
            "overflow": "hidden"
        }
        
        # Add appropriate indicator based on event status
        indicator = None
        if event_status == "ongoing":
            indicator = html.Div(className="ongoing-indicator")
        elif event_status == "upcoming":
            indicator = html.Div(className="upcoming-indicator")
        elif event_status == "completed":
            indicator = html.Div(className="completed-indicator")
        
        # Truncate event name if too long
        event_name = ev.get("name", "")
        if len(event_name) > 35:
            event_name = event_name[:32] + "..."
        
        return dbc.Card([
            indicator,
            dbc.CardHeader([
                html.Div([
                    html.Div([
                        html.A(ev.get("event_key"), href=f"/event/{ev.get('event_key')}", style={
                            "fontWeight": "700", 
                            "color": "var(--primary-color)", 
                            "textDecoration": "none",
                            "fontSize": "1.1rem",
                            "transition": "color 0.2s ease"
                        }),
                        html.Span(" · ", style={"color": "var(--text-secondary)", "fontWeight": "500"}),
                        html.Span(event_name, title=ev.get("name", ""), style={
                            "fontWeight": "600",
                            "color": "var(--text-primary)"
                        }),  # Show full name on hover
                    ], style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": 1})
                ], style={"display": "flex", "justifyContent": "flex-start", "alignItems": "flex-start", "gap": "12px", "marginBottom": "8px"}),
                html.Div([
                    html.I(className="fas fa-map-marker-alt", style={"marginRight": "6px", "color": "var(--text-secondary)"}),
                    html.Span(ev.get("location", ""), style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}),
                html.Div([
                    html.Div([
                        html.I(className="fas fa-calendar-alt", style={"marginRight": "6px", "color": "var(--text-secondary)"}),
                        html.Span(ev.get("start_date", "TBD"), style={"fontSize": "0.9rem", "color": "var(--text-secondary)"}),
                        html.Span(" - ", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"}),
                        html.Span(ev.get("end_date", "TBD"), style={"fontSize": "0.9rem", "color": "var(--text-secondary)"}),
                    ], style={"display": "flex", "alignItems": "center", "flex": 1}),
                    dbc.Button(
                        "Peek",
                        id={"type": "focus-button", "event_key": ev.get("event_key")},
                        size="sm",
                        color="light",
                        outline=False,
                        style={
                            "fontSize": "0.8rem",
                            "padding": "4px 12px",
                            "borderRadius": "6px",
                            "fontWeight": "500",
                            "backgroundColor": "#ffffff",
                            "borderColor": "#dee2e6",
                            "color": "#212529"
                        }
                    )
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
            ], style={
                "backgroundColor": "var(--bg-secondary)", 
                "flexShrink": 0,
                "borderBottom": "1px solid var(--border-color)",
                "padding": "16px"
            }),
            dbc.CardBody([
                peekolive_embed_for(ev)
            ], style={"padding": 0, "flex": 1, "display": "flex", "flexDirection": "column"})
        ], style=card_style, className="peekolive-card event-card")

    def build_section(title, events_list, section_id, event_status="ongoing"):
        if not events_list:
            return html.Div()
        
        # Determine icon and color based on status
        status_config = {
            "ongoing": {"icon": "fas fa-play-circle", "color": "#28a745", "bg": "rgba(40, 167, 69, 0.1)"},
            "upcoming": {"icon": "fas fa-clock", "color": "#ffc107", "bg": "rgba(255, 193, 7, 0.1)"},
            "completed": {"icon": "fas fa-check-circle", "color": "#dc3545", "bg": "rgba(220, 53, 69, 0.1)"}
        }
        config = status_config.get(event_status, status_config["ongoing"])
        
        cards = [build_event_card(ev, event_status=event_status) for ev in events_list]
        return html.Div([
            html.Div([
                html.Div([
                    html.I(className=config["icon"], style={
                        "color": config["color"],
                        "fontSize": "1.5rem",
                        "marginRight": "12px"
                    }),
                    html.H4(title, style={
                        "color": "var(--text-primary)",
                        "fontWeight": "700",
                        "fontSize": "1.8rem",
                        "margin": "0",
                        "display": "inline-block"
                    })
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginBottom": "25px"
                })
            ], style={
                "background": f"linear-gradient(135deg, {config['bg']} 0%, transparent 100%)",
                "borderRadius": "12px",
                "padding": "20px 20px 10px 20px",
                "marginBottom": "25px",
                "border": f"1px solid {config['color']}20"
            }),
            dbc.Row([
                dbc.Col(card, md=6, xl=4, className="mb-4") for card in cards
            ], className="justify-content-center", id=section_id)
        ], className="mb-3")

    # Build sections
    ongoing_section = build_section("Ongoing Events", events_data["ongoing"], "ongoing-events", event_status="ongoing") 
    upcoming_section = build_section("Upcoming Events", events_data["upcoming"], "upcoming-events", event_status="upcoming")
    completed_section = build_section("Completed Events", events_data["completed"], "completed-events", event_status="completed")
    
    return html.Div([
        dbc.Container([
            # Enhanced logo section
            html.Div([
                html.Img(src="/assets/peekolive.png", style={
                    "height": "100px", 
                    "margin": "0 auto 20px", 
                    "display": "block"
                })
            ], className="mb-4"),
            
            dcc.Interval(id='peekolive-refresh', interval=120000, n_intervals=0),
            ongoing_section,
            upcoming_section,
            completed_section
        ], style={"maxWidth": "1400px", "padding": "20px"}),
    ])

def peekolive_layout():
    events_data = get_peekolive_events_categorized()
    return build_peekolive_layout_with_events(events_data)

def build_peekolive_grid(team_value=None, prefiltered_events=None):
    """Helper to build PeekoLive grid children filtered by optional team string.

    If prefiltered_events is provided, uses that list directly; otherwise fetches
    events via get_peekolive_events (respecting include_all when team filter is set).
    """
    # Get events data
    if prefiltered_events is not None:
        # prefiltered_events is a flat list from search callback
        events_to_display = prefiltered_events
    else:
        # Get categorized events for normal display
        events_data = get_peekolive_events_categorized(include_all=bool(team_value))
        if not team_value or team_value is None:
            # Combine all events for display
            events_to_display = events_data["completed"] + events_data["ongoing"] + events_data["upcoming"]
        else:
            # Team filtering logic for categorized events
            try:
                from peekorobo import EVENT_TEAMS
                t_str = str(team_value)
                filtered_events = []
                
                # Filter each category
                for category in ["completed", "ongoing", "upcoming"]:
                    for ev in events_data[category]:
                        evk = ev.get("event_key")
                        found = False
                        # Search across all years for the event key
                        for y, year_map in (EVENT_TEAMS or {}).items():
                            teams = (year_map or {}).get(evk, [])
                            if any(str(t.get("tk")) == t_str for t in teams):
                                found = True
                                break
                        if found:
                            filtered_events.append(ev)
                events_to_display = filtered_events
            except Exception:
                # Fallback to all events if filtering fails
                events_to_display = events_data["completed"] + events_data["ongoing"] + events_data["upcoming"]
    
    # Build grid rows for events
    cards = []
    for ev in events_to_display:
        # Truncate event name if too long
        event_name = ev.get("name", "")
        if len(event_name) > 30:
            event_name = event_name[:27] + "..."
        
        cards.append(
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.Div([
                            html.A(ev.get("event_key"), href=f"/event/{ev.get('event_key')}", style={"fontWeight": "bold", "color": "var(--primary-color)", "textDecoration": "none"}),
                            html.Span(" · "),
                            html.Span(event_name, title=ev.get("name", "")),  # Show full name on hover
                        ], style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "flex": 1}),
                        dbc.Button(
                            "Peek",
                            id={"type": "focus-button", "event_key": ev.get("event_key")},
                            size="sm",
                            color="warning",
                            outline=False,
                            style={
                                "fontSize": "0.7rem",
                                "padding": "3px 10px",
                                "borderRadius": "5px",
                                "fontWeight": "500",
                                "backgroundColor": "#ffc107",
                                "borderColor": "#ffc107",
                                "color": "#000"
                            }
                        )
                    ], style={"display": "flex", "justifyContent": "flex-start", "alignItems": "flex-start", "gap": "12px", "marginBottom": "6px"}),
                    html.Div(ev.get("location", ""), style={"fontSize": "0.85rem", "color": "var(--text-secondary)"}),
                    html.Div([
                        html.Span(ev.get("start_date", "TBD")),
                        html.Span(" - "),
                        html.Span(ev.get("end_date", "TBD")),
                    ], style={"fontSize": "0.85rem", "color": "var(--text-secondary)", "marginTop": "4px"}),
                ], style={"backgroundColor": "var(--card-bg)", "flexShrink": 0}),
                dbc.CardBody([
                    peekolive_embed_for(ev)
                ], style={"padding": 0, "flex": 1, "display": "flex", "flexDirection": "column"})
            ], style={
                "backgroundColor": "var(--card-bg)",
                "height": "300px",
                "display": "flex",
                "flexDirection": "column"
            })
        )
    return dbc.Row([
        dbc.Col(c, md=6, xl=4, className="mb-3") for c in cards
    ], className="justify-content-center")

def match_layout(event_key, match_key):
    # Parse year from event_key
    try:
        year = int(event_key[:4])
    except Exception:
        return dbc.Alert("Invalid event key.", color="danger")
    
     # Get data for teams (prefer event-specific)
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
    winner = match.get("wa") or "Tie"
    winner = winner.title() if winner else "Tie"
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

    # Percentile coloring for ACE using app-wide logic
    all_epas = [t.get("epa", 0) for t in team_db.values() if t.get("epa") is not None]
    percentiles_dict = {"epa": compute_percentiles(all_epas)}

    # Build breakdown data for DataTable
    phases = [
        ("Auto", "auto_epa"),
        ("Teleop", "teleop_epa"),
        ("Endgame", "endgame_epa"),
        ("RAW", "normal_epa"),
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
            html.Div(ace_legend_layout(), style={"marginBottom": "1rem", "marginTop": "1rem"}),
            html.Div(breakdown_tables),
            html.Div(video_embed, style={"textAlign": "center", "marginBottom": "2rem"}),
        ], style={"padding": "30px", "maxWidth": "1000px"}),
        footer
    ])

def generate_team_recommendations(team_database, favorite_teams, user_team_affil, text_color):
    """Generate personalized team recommendations based on user preferences and data."""
    recommendations = []
    
    if not team_database:
        return [html.Div("No team data available", style={"color": text_color})]
    
    # Get current year data
    current_year_data = team_database.get(current_year, {})
    if not current_year_data:
        return [html.Div("No team data available for the current year", style={"color": text_color})]
    
    # Get user's team location info
    user_team_location = None
    if user_team_affil and user_team_affil != "####":
        try:
            user_team_num = int(user_team_affil)
            user_team_data = current_year_data.get(user_team_num, {})
            if user_team_data:
                user_team_location = {
                    "state": user_team_data.get("state_prov", ""),
                    "country": user_team_data.get("country", ""),
                    "city": user_team_data.get("city", "")
                }
        except ValueError:
            pass
    
    # Get favorite teams' characteristics
    favorite_team_epas = []
    favorite_team_locations = []
    favorite_team_states = set()
    favorite_team_countries = set()
    favorite_team_cities = set()
    
    for team_key in favorite_teams:
        try:
            team_num = int(team_key)
            team_data = current_year_data.get(team_num, {})
            if team_data:
                epa = team_data.get("epa", 0)
                state = team_data.get("state_prov", "")
                country = team_data.get("country", "")
                city = team_data.get("city", "")
                
                favorite_team_epas.append(epa)
                favorite_team_locations.append({
                    "state": state,
                    "country": country,
                    "city": city
                })
                
                if state:
                    favorite_team_states.add(state)
                if country:
                    favorite_team_countries.add(country)
                if city:
                    favorite_team_cities.add(city)
        except ValueError:
            continue
    
    # Calculate statistics of favorite teams
    avg_favorite_epa = sum(favorite_team_epas) / len(favorite_team_epas) if favorite_team_epas else 0
    min_favorite_epa = min(favorite_team_epas) if favorite_team_epas else 0
    max_favorite_epa = max(favorite_team_epas) if favorite_team_epas else 0
    epa_range = max_favorite_epa - min_favorite_epa
    
    # Generate recommendations
    candidate_teams = []
    
    for team_num, team_data in current_year_data.items():
        # Skip if already a favorite
        if str(team_num) in favorite_teams:
            continue
            
        team_epa = team_data.get("epa", 0)
        team_state = team_data.get("state_prov", "")
        team_country = team_data.get("country", "")
        team_city = team_data.get("city", "")
        team_nickname = team_data.get("nickname", "")
        
        # Calculate recommendation score
        score = 0
        
        # Location-based scoring (considering ALL favorite teams)
        if user_team_location:
            if team_state == user_team_location["state"]:
                score += 50
            if team_country == user_team_location["country"]:
                score += 30
        
        # Performance-based scoring (considering ALL favorite teams)
        if favorite_team_epas:
            # Check if team fits within the range of favorite teams
            if min_favorite_epa <= team_epa <= max_favorite_epa:
                score += 50  # High score for teams within favorite range
            else:
                # Calculate distance from favorite range
                if team_epa < min_favorite_epa:
                    epa_distance = min_favorite_epa - team_epa
                else:
                    epa_distance = team_epa - max_favorite_epa
                
                if epa_distance < 10:
                    score += 30
                elif epa_distance < 20:
                    score += 15
        
        # Regional bonus for ALL favorite team locations
        if team_state in favorite_team_states:
            score += 40  # Higher score for exact state matches
        if team_country in favorite_team_countries:
            score += 25  # Good score for same country
        
        # City-level matching (bonus for exact city matches)
        if team_city in favorite_team_cities:
            score += 60  # Very high score for same city
        
        # High performer bonus (if user likes high performers)
        if team_epa > 100 and max_favorite_epa > 80:  # Top tier teams, if user likes good teams
            score += 35
        elif team_epa > 80 and avg_favorite_epa > 60:  # Good teams, if user likes decent teams
            score += 20
        
        # Diversity bonus (if user has diverse favorites, suggest diverse teams)
        if len(favorite_team_states) > 2:  # User likes teams from multiple states
            if team_state not in favorite_team_states:
                score += 15  # Bonus for new states
        elif len(favorite_team_states) == 1:  # User likes teams from one state
            if team_state in favorite_team_states:
                score += 25  # Higher bonus for same state
        
        if score > 0:
            candidate_teams.append({
                "team_num": team_num,
                "team_data": team_data,
                "score": score
            })
    
    # Sort by score and take top 6
    candidate_teams.sort(key=lambda x: x["score"], reverse=True)
    top_teams = candidate_teams[:6]
    
    # Create recommendation cards
    for team_info in top_teams:
        team_num = team_info["team_num"]
        team_data = team_info["team_data"]
        score = team_info["score"]
        
        # Get team colors
        background_gradient, card_text_color = get_team_card_colors_with_text(str(team_num))
        
        # Get avatar
        avatar_url = get_team_avatar(team_num, 2025)
        
        reason_text = "Recommended for you"
        
        card = html.Div([
            # Header with avatar and team info
            html.Div([
                html.Div([
                    html.Img(
                        src=avatar_url,
                        style={
                            "width": "50px",
                            "height": "50px",
                            "objectFit": "contain",
                            "borderRadius": "10px",
                            "backgroundColor": "rgba(255, 255, 255, 0.1)",
                            "padding": "4px"
                        }
                    ),
                    html.Div([
                        html.H4(f"#{team_num}", style={
                            "margin": "0 0 2px 0",
                            "fontSize": "1.2rem",
                            "fontWeight": "700",
                            "color": card_text_color,
                            "lineHeight": "1.2"
                        }),
                        html.P(team_data.get("nickname", ""), style={
                            "margin": "0",
                            "fontSize": "0.85rem",
                            "color": card_text_color,
                            "opacity": "0.9",
                            "fontWeight": "400",
                            "lineHeight": "1.3"
                        })
                    ], style={"marginLeft": "12px", "flex": "1"})
                ], style={"display": "flex", "alignItems": "center"}),
                
                # ACE score badge
                html.Div([
                    html.Span("ACE", style={
                        "fontSize": "0.7rem",
                        "fontWeight": "600",
                        "color": card_text_color,
                        "opacity": "0.8",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.5px"
                    }),
                    html.Br(),
                    html.Span(f"{team_data.get('epa', 0):.1f}", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "700",
                        "color": card_text_color,
                        "lineHeight": "1.2"
                    })
                ], style={
                    "textAlign": "center",
                    "backgroundColor": "rgba(255, 255, 255, 0.1)",
                    "padding": "8px 12px",
                    "borderRadius": "8px",
                    "minWidth": "60px"
                })
            ], style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "16px 16px 12px 16px"
            }),
            
            # Recommendation reason
            html.Div([
                html.Span(reason_text, style={
                    "fontSize": "0.75rem",
                    "color": card_text_color,
                    "opacity": "0.8",
                    "fontWeight": "400",
                    "lineHeight": "1.4"
                })
            ], style={
                "padding": "0 16px 12px 16px"
            }),
            
            # Modern button
            html.A(
                "Peek",
                href=f"/team/{team_num}/{current_year}",
                style={
                    "display": "block",
                    "textAlign": "center",
                    "padding": "10px 16px",
                    "backgroundColor": "rgba(255, 255, 255, 0.15)",
                    "color": card_text_color,
                    "textDecoration": "none",
                    "borderRadius": "8px",
                    "fontSize": "0.85rem",
                    "fontWeight": "600",
                    "transition": "all 0.2s ease",
                    "margin": "0 16px 16px 16px",
                    "border": "1px solid rgba(255, 255, 255, 0.2)",
                    "backdropFilter": "blur(10px)"
                }
            )
        ], style={
            "background": background_gradient,
            "borderRadius": "16px",
            "overflow": "hidden",
            "boxShadow": "0 8px 25px rgba(0, 0, 0, 0.15)",
            "transition": "all 0.3s ease",
            "cursor": "pointer",
            "position": "relative"
        })
        
        recommendations.append(card)
    
    return recommendations if recommendations else [html.Div("No recommendations available", style={"color": text_color})]

def user_profile_layout(username=None, _user_id=None, deleted_items=None):
    """
    Combined layout for both current user profile and other user profiles.
    
    Args:
        username: If provided, shows profile for this specific user (other user view)
        _user_id: If provided, shows profile for this user ID (current user view)
        deleted_items: Items to exclude from display (for current user view)
    """
    from peekorobo import EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, TEAM_DATABASE, EVENT_RANKINGS

    session_user_id = session.get("user_id")
    if not session_user_id:
        return html.Div([
            dcc.Store(id="user-session", data={}),
            dcc.Location(href="/login", id="force-login-redirect")
        ])

    # Determine if this is current user or other user view
    is_current_user = username is None
    
    if is_current_user:
        # Current user view - use session user_id or provided _user_id
        user_id = _user_id or session_user_id
        target_user_id = user_id
    else:
        # Other user view - look up user by username
        target_user_id = None
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if not row:
                    return html.Div("User not found.", style={"padding": "2rem", "fontSize": "1.2rem"})
                target_user_id = row[0]
        except Exception as e:
            print(f"Error loading user data: {e}")
            return html.Div("Error loading user data.", style={"padding": "2rem", "fontSize": "1.2rem"})

    # Fetch user data
    username_display = f"USER {target_user_id}"
    avatar_key = "stock"
    role = "No role"
    team_affil = "####"
    bio = "No bio"
    email = ""
    followers_count = 0
    following_count = 0
    color = "#f9f9f9"
    higher_lower_highscore = 0
    team_keys = []
    event_keys = []
    followers_user_objs = []
    following_user_objs = []
    is_following = False

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            if is_current_user:
                # Current user - get full profile data
                cursor.execute("""
                    SELECT username, avatar_key, role, team, bio, followers, following, color, email, higher_lower_highscore
                    FROM users WHERE id = %s
                """, (target_user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    username_display = user_row[0] or username_display
                    avatar_key = user_row[1] or "stock"
                    role = user_row[2] or "No role"
                    team_affil = user_row[3] or "####"
                    bio = user_row[4] or "No bio"
                    followers_ids = user_row[5] or []
                    following_ids = user_row[6] or []
                    color = user_row[7] or "#f9f9f9"
                    email = user_row[8] or ""
                    higher_lower_highscore = user_row[9] or 0
                    
                    # Get usernames and avatars for followers
                    if followers_ids:
                        cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (followers_ids,))
                        followers_user_objs = cursor.fetchall()
                    
                    # Get usernames and avatars for following
                    if following_ids:
                        cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (following_ids,))
                        following_user_objs = cursor.fetchall()
                    
                    # Count values
                    followers_count = len(followers_ids)
                    following_count = len(following_ids)
            else:
                # Other user - get profile data and check if current user is following
                cursor.execute("""
                    SELECT username, avatar_key, role, team, bio, followers, following, color, higher_lower_highscore
                    FROM users WHERE id = %s
                """, (target_user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    username_display = user_row[0] or username_display
                    avatar_key = user_row[1] or "stock"
                    role = user_row[2] or "No role"
                    team_affil = user_row[3] or "####"
                    bio = user_row[4] or "No bio"
                    followers_ids = user_row[5] or []
                    following_ids = user_row[6] or []
                    followers_count = len(followers_ids)
                    following_count = len(following_ids)
                    color = user_row[7] or "#ffffff"
                    higher_lower_highscore = user_row[8] or 0
                    
                    # Get usernames and avatars for followers (for other users too)
                    if followers_ids:
                        cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (followers_ids,))
                        followers_user_objs = cursor.fetchall()
                    
                    # Get usernames and avatars for following (for other users too)
                    if following_ids:
                        cursor.execute("SELECT id, username, avatar_key FROM users WHERE id = ANY(%s)", (following_ids,))
                        following_user_objs = cursor.fetchall()
                    
                    # Check if current user is following this user
                    is_following = session_user_id in followers_ids

            # Get favorite teams and events
            cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'team'", (target_user_id,))
            team_keys = [r[0] for r in cursor.fetchall()]

            cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'event'", (target_user_id,))
            event_keys = [r[0] for r in cursor.fetchall()]
            
    except Exception as e:
        print(f"Error retrieving user info: {e}")

    available_avatars = get_available_avatars()
    text_color = get_contrast_text_color(color)

    # Handle deleted items for current user view
    if is_current_user and deleted_items:
        store_data = {"deleted": []}
        deleted_items_set = set(tuple(i) for i in store_data.get("deleted", []))
        team_keys = [k for k in team_keys if ("team", k) not in deleted_items_set]
        event_keys = [k for k in event_keys if ("event", k) not in deleted_items_set]

    # Profile display section
    if is_current_user:
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
                        html.Span("▼", id=f"followers-arrow-{username}" if username else "followers-arrow", style={"cursor": "pointer", "fontSize": "0.75rem", "color": text_color})
                    ], id="profile-followers", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
        
                    html.Span(" | ", style={"margin": "0 8px", "color": "#999"}),
        
                    html.Span([
                        f"Following: {following_count} ",
                        html.Span("▼", id=f"following-arrow-{username}" if username else "following-arrow", style={"cursor": "pointer", "fontSize": "0.75rem", "color": text_color})
                    ], id="profile-following", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
                ], style={
                    "fontSize": "0.85rem",
                    "color": text_color,
                    "marginTop": "4px",
                    "display": "flex",
                    "flexWrap": "wrap"
                }),

                html.Div([
                    html.Span("Higher/Lower High Score: ", style={"fontWeight": "500", "color": text_color}),
                    html.Span(str(higher_lower_highscore), style={"fontWeight": "600", "color": text_color, "marginLeft": "4px"})
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
    else:
        # Other user view - simpler profile display
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
                        html.A(team_affil, href=f"/team/{team_affil}/{current_year}", style={
                            "color": text_color,
                            "textDecoration": "none",
                            "fontWeight": "500"
                        })
                    ], id="profile-team"),
                    html.Span(" | ", style={"margin": "0 8px", "color": text_color}),
                    html.Span([
                        f"Followers: {followers_count} ",
                        html.Span("▼", id=f"followers-arrow-{username}" if username else "followers-arrow", style={"cursor": "pointer", "fontSize": "0.75rem", "color": text_color})
                    ], id="profile-followers", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
                    html.Span(" | ", style={"margin": "0 8px", "color": "#999"}),
                    html.Span([
                        f"Following: {following_count} ",
                        html.Span("▼", id=f"following-arrow-{username}" if username else "following-arrow", style={"cursor": "pointer", "fontSize": "0.75rem", "color": text_color})
                    ], id="profile-following", style={"color": text_color, "fontWeight": "500", "position": "relative"}),
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

    # Profile edit form (only for current user)
    profile_edit_form = None
    if is_current_user:
                profile_edit_form = html.Div(
            id="profile-edit-form",
            hidden=True,
            children=[
                html.Label("Username", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Input(id="edit-username", value=username_display, placeholder="Username", className="mb-2", size="sm"),
                html.Label("Email (optional)", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Input(id="edit-email", value=email, placeholder="Email (optional)", className="mb-2", size="sm"),
                html.Label("New Password (leave blank to keep current)", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Input(id="edit-password", type="password", placeholder="New Password (leave blank to keep current)", className="mb-2", size="sm", value=""),
                html.Label("Role", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Input(id="edit-role", value=role, placeholder="Role", className="mb-2", size="sm"),
                html.Label("Team", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Input(id="edit-team", value=team_affil, placeholder="Team", className="mb-2", size="sm"),
                html.Label("Bio", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                dbc.Textarea(id="edit-bio", value=bio, placeholder="Bio", className="mb-2", style={"height": "60px", "fontSize": "0.85rem"}),
                html.Label("Select Avatar", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
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
                html.Label("Change Card Background Color", style={"fontSize": "0.75rem", "fontWeight": "600", "marginTop": "6px", "color": "#fff"}),
                html.Div([
                    dmc.ColorPicker(
                        id="edit-bg-color",
                        format="hex",
                        value=color,
                        style={"marginBottom": "8px"}
                    ),
                    dmc.Space(h=10),
                    html.Div([
                        html.Span("Current: ", style={"fontSize": "0.7rem", "color": "#ccc"}),
                        html.Span(
                            color,
                            id="current-color-display",
                            style={
                                "fontSize": "0.7rem",
                                "color": "#fff",
                                "fontFamily": "monospace",
                                "backgroundColor": color,
                                "padding": "2px 6px",
                                "borderRadius": "3px",
                                "border": "1px solid #666"
                            }
                        )
                    ], style={"marginTop": "4px"})
                ], style={"width": "200px"}),
            ]
        )

    # Build team cards
    epa_data = {
        str(team_num): {
            "epa": data.get("epa", 0),
            "normal_epa": data.get("normal_epa", 0),
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
            "confidence": data.get("confidence", 0),
            "event_epas": data.get("event_epas", []),
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

        # Add delete button only for current user
        delete_team_btn = None
        if is_current_user:
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
        norm_color = "#d32f2f"    # Red
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
                pill("RAW", f"{normal_epa:.1f}", norm_color),
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
                html.Img(src=get_team_avatar(team_number), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, current_year, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
            ],
            delete_button=delete_team_btn,
            team_number=team_number
        ))

    # Note: All content is now integrated directly into the main layout for better mobile organization

    # Build popovers for followers/following (for all users)
    followers_popover = None
    following_popover = None
    
    if followers_user_objs:
        followers_popover = dbc.Popover(
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
                    html.Div("See all", id={"type": "followers-see-more", "username": username} if username else "followers-see-more", style={
                        "color": "#007bff", "cursor": "pointer", "fontSize": "0.75rem", "marginTop": "5px"
                    }) if len(followers_user_objs) > 5 else None,
                    html.Ul([
                        html.Li([
                            html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                            html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                        for user in followers_user_objs[5:]
                    ], id={"type": "followers-hidden", "username": username} if username else "followers-hidden", style={
                        "display": "none",
                        "marginTop": "5px",
                        "paddingLeft": "0",
                        "listStyleType": "none",
                        "marginBottom": "0"
                    })
                ], style={"maxHeight": "300px", "overflowY": "auto"})
            ],
            id=f"popover-followers-{username}" if username else "popover-followers",
            target=f"followers-arrow-{username}" if username else "followers-arrow",
            trigger="click",
            autohide=False,
            placement="bottom"
        )
    
    if following_user_objs:
        following_popover = dbc.Popover(
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
                    html.Div("See all", id={"type": "following-see-more", "username": username} if username else "following-see-more", style={
                        "color": "#007bff", "cursor": "pointer", "fontSize": "0.75rem", "marginTop": "5px"
                    }) if len(following_user_objs) > 5 else None,
                    html.Ul([
                        html.Li([
                            html.Img(src=get_user_avatar(user[2]), height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                            html.A(user[1], href=f"/user/{user[1]}", style={"textDecoration": "none", "color": "#007bff"})
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"})
                        for user in following_user_objs[5:]
                    ], id={"type": "following-hidden", "username": username} if username else "following-hidden", style={
                        "display": "none",
                        "marginTop": "5px",
                        "paddingLeft": "0",
                        "listStyleType": "none",
                        "marginBottom": "0"
                    })
                ], style={"maxHeight": "300px", "overflowY": "auto"})
            ],
            id=f"popover-following-{username}" if username else "popover-following",
            target=f"following-arrow-{username}" if username else "following-arrow",
            trigger="click",
            autohide=False,
            placement="bottom"
        )

    # Build the main layout
    layout_components = [
        dcc.Store(id="user-session", data={"user_id": session_user_id}),
        topbar(),
        dcc.Location(id="login-redirect", refresh=True),
    ]
    
    # Add favorites store only for current user
    if is_current_user:
        layout_components.append(dcc.Store(id="favorites-store", data={"deleted": []}))
    
    layout_components.extend([
        followers_popover,
        following_popover,
        dbc.Container([
            dbc.Card(
                dbc.CardBody([
                    # Unified responsive layout
                    html.Div([
                        # Simple, clean layout
                        html.Div([
                            # Layout with Log Out top right, Edit Profile bottom right, search flexible
                            html.Div([
                                # Top section with Log Out button
                                html.Div([
                                    # Avatar and name section
                                    html.Div([
                                        html.Img(
                                            **({"id": "user-avatar-img"} if is_current_user else {}),
                                            src=get_user_avatar(avatar_key),
                                            style={
                                                "height": "60px", 
                                                "width": "60px",
                                                "borderRadius": "50%", 
                                                "marginRight": "15px",
                                                "flexShrink": "0"
                                            }
                                        ),
                                        html.Div([
                                            html.H2(
                                                f"Welcome, {username_display.title()}!" if is_current_user else f"{username_display.title()}",
                                                **({"id": "profile-header"} if is_current_user else {}),
                                                style={"margin": 0, "fontSize": "1.5rem", "color": text_color, "lineHeight": "1.2"}
                                            ),
                                            html.Div(
                                                f"{len(team_keys)} favorite teams",
                                                **({"id": "profile-subheader"} if is_current_user else {}),
                                                style={"fontSize": "0.85rem", "color": text_color, "marginTop": "2px"}
                                            ),
                                        ], style={"flex": "1", "minWidth": "0"}),
                                    ], style={"display": "flex", "alignItems": "center"}),
                                    
                                    # Log Out button in top right
                                    html.A(
                                        "Log Out", 
                                        id="logout-btn",
                                        href="/logout", 
                                        style={
                                            "fontSize": "0.8rem", 
                                            "color": "#ffffff", 
                                            "textDecoration": "none", 
                                            "fontWeight": "600",
                                            "alignSelf": "flex-start",
                                            "marginTop": "5px",
                                            "backgroundColor": "#2D2D2D",
                                            "border": "0px solid #ffffff",
                                            "borderRadius": "4px",
                                            "padding": "6px 12px",
                                            "display": "inline-block"
                                        }
                                    ) if is_current_user else None,
                                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "15px"}),
                                
                                # Profile info section
                                html.Div([
                                    profile_display,
                                    followers_popover,
                                    following_popover,
                                    profile_edit_form,
                                ], style={"width": "100%", "marginBottom": "15px"}),
                                
                                # Bottom section with search, Edit Profile, and Follow button
                                html.Div([
                                    # Search bar (flexible) - only for current user
                                    html.Div([
                                        html.H5(
                                            id="profile-search-header",
                                            style={"marginBottom": "8px", "fontSize": "0.95rem", "color": text_color}
                                        ),
                                        dbc.Input(
                                            id="user-search-input", 
                                            placeholder="Search Users", 
                                            type="text", 
                                            size="sm", 
                                            className="custom-input-box mb-2", 
                                            style={"width": "100%", "maxWidth": "300px"}
                                        ),
                                        html.Div(id="user-search-results")
                                    ], style={"flex": "1", "marginRight": "20px", "position": "relative"}) if is_current_user else None,
                                    
                                    # Edit Profile button - only for current user
                                    html.Button(
                                        "Edit Profile",
                                        id="edit-profile-btn",
                                        style={
                                            "backgroundColor": "#2D2D2D",
                                            "border": "0px solid #000000",
                                            "borderRadius": "4px",
                                            "padding": "6px 12px",
                                            "color": "#ffffff",
                                            "fontWeight": "600",
                                            "fontSize": "0.85rem",
                                            "textDecoration": "none",
                                            "cursor": "pointer"
                                        }
                                    ) if is_current_user else None,
                                    html.Button("Save", id="save-profile-btn", className="btn btn-warning btn-sm", style={"display": "none"}) if is_current_user else None,
                                    
                                    # Follow button for other users
                                    html.Button(
                                        "Unfollow" if is_following else "Follow",
                                        id={"type": "follow-user", "user_id": target_user_id},
                                        style={
                                            "backgroundColor": "white" if is_following else "#ffdd00",
                                            "border": "1px solid #ccc",
                                            "borderRadius": "12px",
                                            "padding": "6px 12px",
                                            "fontSize": "0.85rem",
                                            "fontWeight": "500",
                                            "color": "#000",
                                            "cursor": "pointer",
                                            "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
                                            "display": "block"
                                        }
                                    ) if not is_current_user and target_user_id != session_user_id else None,
                                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end", "width": "100%"}),
                            ], style={"display": "flex", "flexDirection": "column", "width": "100%"}),
                        ], style={"display": "flex", "flexDirection": "column", "width": "100%", "gap": "15px"}),
                    ], style={"display": "flex", "flexDirection": "column", "width": "100%", "gap": "15px"})
                ]),
                id="profile-card",
                style={"borderRadius": "10px", "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)", "marginBottom": "20px", "backgroundColor": color or "var(--card-bg)"}
            ),
            
            # Teams You Might Like Section
            html.Div([
                html.Div([
                    html.H3("Teams You Might Like", className="mb-3", style={
                        "color": "var(--text-primary)",
                        "fontSize": "1.5rem",
                        "fontWeight": "600",
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "8px"
                    }),
                    html.P("Based on your location, favorite teams, and performance patterns", style={
                        "color": "var(--text-secondary)",
                        "opacity": "0.8",
                        "fontSize": "0.9rem",
                        "marginBottom": "20px"
                    })
                ]),
                
                # Generate team recommendations
                html.Div([
                    *generate_team_recommendations(TEAM_DATABASE, team_keys, team_affil, text_color)
                ], style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fill, minmax(280px, 1fr))",
                    "gap": "20px",
                    "marginBottom": "30px"
                })
            ], style={
                "marginBottom": "30px",
                "padding": "20px",
                "backgroundColor": "rgba(255, 255, 255, 0.05)",
                "borderRadius": "12px",
                "border": "1px solid rgba(255, 255, 255, 0.1)"
            }),
            
            html.Hr(),
            html.H3("Favorite Teams", className="mb-3"),
            *team_cards,
        ], style={"padding": "20px", "maxWidth": "1000px"}),
        footer
    ])

    return html.Div(layout_components)

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
                # Find event-specific data for this team at this event
                event_specific_epa = next(
                    (e for e in event_epas if e.get("event_key") == event_key),
                    None
                )
                # Fallback to overall data if event-specific is missing
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
                    # Use overall data from TEAM_DATABASE with fallback
                    fallback_team_data, actual_year = get_team_data_with_fallback(team_num, parsed_year, TEAM_DATABASE)
                    if fallback_team_data:
                        event_epa_data[str(team_num)] = {
                            "epa": fallback_team_data.get("epa", 0),
                            "normal_epa": fallback_team_data.get("normal_epa", 0),
                            "auto_epa": fallback_team_data.get("auto_epa", 0),
                            "teleop_epa": fallback_team_data.get("teleop_epa", 0),
                            "endgame_epa": fallback_team_data.get("endgame_epa", 0),
                            "confidence": fallback_team_data.get("confidence", 0.7),
                        }
                    else:
                        # Final fallback to original data
                        event_epa_data[str(team_num)] = {
                            "epa": team_data.get("epa", 0),
                            "normal_epa": team_data.get("normal_epa", 0),
                            "auto_epa": team_data.get("auto_epa", 0),
                            "teleop_epa": team_data.get("teleop_epa", 0),
                            "endgame_epa": team_data.get("endgame_epa", 0),
                            "confidence": team_data.get("confidence", 0.7),
                        }
        
        # Calculate rankings based on event-specific data
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
                    # Find event-specific data for this team at this event
                    event_specific_epa = next(
                        (e for e in event_epas if e.get("event_key") == event_key),
                        None
                    )
                    # Fallback to overall data if event-specific is missing
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
                        # Use overall performance metrics from year_team_data
                        event_epa_data[str(team_num)] = {
                            "epa": team_data.get("epa", 0),
                            "normal_epa": team_data.get("normal_epa"),
                            "auto_epa": team_data.get("auto_epa", 0),
                            "teleop_epa": team_data.get("teleop_epa", 0),
                            "endgame_epa": team_data.get("endgame_epa", 0),
                            "confidence": team_data.get("confidence", 0.7),
                        }
            
            # Calculate rankings based on event-specific ACE
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
    district = (event.get("da") or "").strip().upper()
    if not district:
        district_key = (event.get("dk") or "").strip()
        district = district_key[-2:].upper() if len(district_key) >= 2 else ""

    # Calculate week label (stored week is 0-based)
    week_label = get_event_week_label_from_number(event.get("wk"))

    # Format dates for display
    start_display = format_human_date(start_date) if start_date and start_date != "N/A" else start_date
    end_display = format_human_date(end_date) if end_date and end_date != "N/A" else end_date

    if district and isinstance(event_type, str) and "district" in event_type.lower():
        type_label = f"{district} District Event"
    elif isinstance(event_type, str) and "regional" in event_type.lower():
        region_label = (event.get("s") or "").strip().upper()
        if region_label:
            type_label = f"{region_label} Regional Event"
        else:
            type_label = "Regional Event"
    else:
        type_label = event_type

    # Header card
    header_card = dbc.Card(
        html.Div([
            dbc.CardBody([
                html.H2(f"{event_name} ({parsed_year})", className="card-title mb-2", style={"fontWeight": "bold"}),
                html.P(event_key, className="card-text text-secondary mb-3"),
                html.P(f"{event_location}", className="card-text"),
                html.P(f"{start_display} - {end_display}", className="card-text"),
                html.P(f"{week_label} {type_label}" if week_label else "", className="card-text"),
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
        # Sort matches chronologically by match key to get the actual last match
        def chronological_sort_key(match):
            # Use the match key format like the existing code but reverse priority
            key = match.get("k", "").split("_", 1)[-1].lower()
            
            # Use regex to extract comp level, set number, and match number
   
            match_re = re.match(r"(qm|qf|sf|f)?(\d*)m?(\d+)", key)
            if match_re:
                level_str, set_num_str, match_num_str = match_re.groups()
                # Reverse the level priority so finals come last (highest number)
                level = {"qm": 0, "qf": 1, "sf": 2, "f": 3}.get(level_str, 99)
                set_num = int(set_num_str) if set_num_str.isdigit() else 0
                match_num = int(match_num_str) if match_num_str.isdigit() else 0
                return (level, set_num, match_num)
            else:
                # Fallback if format is weird
                return (99, 99, 9999)
        
        # Sort chronologically and find the last match with a video
        sorted_matches = sorted(event_matches, key=chronological_sort_key)
        matches_with_videos = [m for m in sorted_matches if m.get("yt")]
        last_match = matches_with_videos[-1] if matches_with_videos else sorted_matches[-1]

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
    team_count = len(event_teams) if event_teams else 0
    data_tabs = dbc.Tabs(
        [
            dbc.Tab(label=f"Teams ({team_count})", tab_id="teams", label_style=tab_style, active_label_style=tab_style),
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
                    dcc.Store(id="store-event-key", data=event_key),
                    html.Div(id="data-display-container"),
                    html.Div(id="event-alliances-content"),
                    html.Div(id="event-metrics-content")
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            footer,
        ]
    )

# --- Add the trends chart builder function ---
def build_trends_chart(team_number, year, performance_year, team_database, event_database, years_participated):
    # Try to get the team data for the given year
    if not team_number:
        return None
    try:
        team_number = int(team_number)
    except Exception:
        return None
    # Use the correct team data for the year
    if performance_year == current_year:
        team_data = team_database.get(performance_year, {}).get(team_number, {})
    else:
        try:
            team_data = team_database.get(performance_year, {}).get(team_number, {})
        except Exception:
            return None
    if not team_data:
        return None
    # If a specific year is selected, show event-by-event ACE
    if year:
        event_epas = team_data.get("event_epas", [])
        if isinstance(event_epas, str):
            try:
                event_epas = json.loads(event_epas)
            except Exception:
                event_epas = []
        if not event_epas:
            return html.Div("No event data available for this team in this year.")
        def get_event_date(event_epa):
            event_key = event_epa.get("event_key", "")
            # Try to get start date from event_database
            if event_database and performance_year in event_database and event_key in event_database[performance_year]:
                event_info = event_database[performance_year][event_key]
                start_date = event_info.get("sd")
                if start_date:
                    return start_date
            return event_key  # fallback
        sorted_events = sorted(event_epas, key=get_event_date)
        
        # Filter out events with 0 stats (all components are 0)
        filtered_events = []
        for event in sorted_events:
            ace = max(0.0, event.get("actual_epa", event.get("epa", 0)))
            auto = max(0.0, event.get("auto", 0))
            teleop = max(0.0, event.get("teleop", 0))
            endgame = max(0.0, event.get("endgame", 0))
            raw = max(0.0, event.get("overall", event.get("normal_epa", 0)))
            
            # Only include events that have at least one non-zero stat
            if ace > 0 or auto > 0 or teleop > 0 or endgame > 0 or raw > 0:
                filtered_events.append(event)
        
        if not filtered_events:
            return html.Div("No event data with valid stats available for this team in this year.")
        
        event_codes = [event.get("event_key", "") for event in filtered_events]
        ace_values = [max(0.0, event.get("actual_epa", event.get("epa", 0))) for event in filtered_events]
        auto_values = [max(0.0, event.get("auto", 0)) for event in filtered_events]
        teleop_values = [max(0.0, event.get("teleop", 0)) for event in filtered_events]
        endgame_values = [max(0.0, event.get("endgame", 0)) for event in filtered_events]
        confidence_values = [min(1.0, max(0.0, event.get("confidence", 0))) for event in filtered_events]
        raw_values = [max(0.0, event.get("overall", event.get("normal_epa", 0))) for event in filtered_events]
        if not ace_values:
            return html.Div("No valid event data found.")
        # Linear extrapolation for 2 predicted points using all events
        n_events = len(ace_values)
        # Determine number of predicted points based on number of events
        if n_events <= 1:
            n_pred = 0
        elif n_events == 2:
            n_pred = 1
        else:
            n_pred = 2
        if n_events >= 2:
            x = np.arange(n_events)
            y_ace = np.array(ace_values)
            y_auto = np.array(auto_values)
            y_teleop = np.array(teleop_values)
            y_endgame = np.array(endgame_values)
            y_confidence = np.array(confidence_values)
            y_raw = np.array(raw_values)
            # Fit lines
            ace_fit = np.polyfit(x, y_ace, 1)
            auto_fit = np.polyfit(x, y_auto, 1)
            teleop_fit = np.polyfit(x, y_teleop, 1)
            endgame_fit = np.polyfit(x, y_endgame, 1)
            confidence_fit = np.polyfit(x, y_confidence, 1)
            raw_fit = np.polyfit(x, y_raw, 1)
            
            # Calculate trend strength and apply conservative adjustments
            ace_slope = ace_fit[0]
            auto_slope = auto_fit[0]
            teleop_slope = teleop_fit[0]
            endgame_slope = endgame_fit[0]
            raw_slope = raw_fit[0]
            
            # Apply conservative adjustments based on trend strength
            # Strong positive trends get reduced, but teams maintain some improvement
            def apply_conservative_adjustment(slope, current_value):
                if slope > 0:
                    # Reduce positive slopes by 30-60% depending on strength
                    # This allows teams to maintain some improvement but not continue at full pace
                    if slope > current_value * 0.15:  # Very strong trend
                        reduction_factor = 0.4  # Keep 40% of the improvement
                    elif slope > current_value * 0.08:  # Strong trend
                        reduction_factor = 0.6  # Keep 60% of the improvement
                    else:  # Moderate trend
                        reduction_factor = 0.8  # Keep 80% of the improvement
                    adjusted_slope = slope * reduction_factor
                else:
                    # Keep negative slopes as they are (teams can decline)
                    adjusted_slope = slope
                return adjusted_slope
            
            # Apply adjustments to slopes
            ace_fit[0] = apply_conservative_adjustment(ace_slope, np.mean(y_ace))
            auto_fit[0] = apply_conservative_adjustment(auto_slope, np.mean(y_auto))
            teleop_fit[0] = apply_conservative_adjustment(teleop_slope, np.mean(y_teleop))
            endgame_fit[0] = apply_conservative_adjustment(endgame_slope, np.mean(y_endgame))
            raw_fit[0] = apply_conservative_adjustment(raw_slope, np.mean(y_raw))
            pred_x = np.arange(n_events, n_events + n_pred)
            predicted_ace = np.polyval(ace_fit, pred_x) if n_pred > 0 else []
            predicted_auto = np.polyval(auto_fit, pred_x) if n_pred > 0 else []
            predicted_teleop = np.polyval(teleop_fit, pred_x) if n_pred > 0 else []
            predicted_endgame = np.polyval(endgame_fit, pred_x) if n_pred > 0 else []
            predicted_confidence = np.polyval(confidence_fit, pred_x) if n_pred > 0 else []
            predicted_raw = np.polyval(raw_fit, pred_x) if n_pred > 0 else []
            
            # Apply bounds to predictions
            if n_pred > 0:
                # Apply conservative confidence adjustments
                # Teams typically don't maintain high confidence indefinitely
                for i in range(len(predicted_confidence)):
                    if predicted_confidence[i] > 0.8:
                        # Reduce very high confidence predictions more gently
                        predicted_confidence[i] = 0.8 + (predicted_confidence[i] - 0.8) * 0.7
                    elif predicted_confidence[i] > 0.6:
                        # Slightly reduce moderate-high confidence
                        predicted_confidence[i] = 0.6 + (predicted_confidence[i] - 0.6) * 0.8
                
                # Ensure confidence never exceeds 1.0 or goes below 0.0
                predicted_confidence = np.clip(predicted_confidence, 0.0, 1.0)
                
                # Ensure all other predictions never go below 0.0
                predicted_auto = np.maximum(predicted_auto, 0.0)
                predicted_teleop = np.maximum(predicted_teleop, 0.0)
                predicted_endgame = np.maximum(predicted_endgame, 0.0)
                predicted_raw = np.maximum(predicted_raw, 0.0)
                
                # Calculate ACE correctly: ACE = RAW * confidence
                predicted_ace = predicted_raw * predicted_confidence
        else:
            predicted_ace = []
            predicted_auto = []
            predicted_teleop = []
            predicted_endgame = []
            predicted_confidence = []
            predicted_raw = []
        predicted_event_codes = [f'{year}pred{i+1}' for i in range(n_pred)]
        # Main trace (actual)
        fig = go.Figure()
        
        # Add gradient background effect
        fig.add_trace(go.Scatter(
            x=event_codes,
            y=ace_values,
            mode='lines',
            line=dict(color='rgba(255, 221, 0, 0.3)', width=8, shape='spline'),
            fill='tozeroy',
            fillcolor='rgba(255, 221, 0, 0.1)',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Main actual data trace with enhanced styling
        fig.add_trace(go.Scatter(
            x=event_codes,
            y=ace_values,
            mode='lines+markers',
            line=dict(
                color='#FFDD00', 
                width=4, 
                shape='spline',
                smoothing=1.3
            ),
            marker=dict(
                size=12, 
                color='#FFDD00', 
                symbol='circle',
                line=dict(color='white', width=2),
                opacity=0.9
            ),
            fill='tozeroy',
            fillcolor='rgba(255, 221, 0, 0.15)',
            name='Actual',
            customdata=list(zip(event_codes, auto_values, teleop_values, endgame_values, raw_values, confidence_values, ace_values)),
            hovertemplate=(
                '<b><a href="/event/%{customdata[0]}" target="_blank">%{customdata[0]}</a></b><br><br>'
                'Auto: %{customdata[1]:.2f}<br>'
                'Teleop: %{customdata[2]:.2f}<br>'
                'Endgame: %{customdata[3]:.2f}<br>'
                'RAW: %{customdata[4]:.2f}<br>'
                'Confidence: %{customdata[5]:.2f}<br>'
                'ACE: %{customdata[6]:.2f}<extra></extra>'
            ),
        ))
        # Predicted trace (if any)
        if n_pred > 0:
            # Add gradient background for predictions
            fig.add_trace(go.Scatter(
                x=[event_codes[-1]] + predicted_event_codes,
                y=[ace_values[-1]] + list(predicted_ace),
                mode='lines',
                line=dict(color='rgba(33, 150, 243, 0.3)', width=8, shape='spline'),
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.1)',
                showlegend=False,
                hoverinfo='skip'
            ))
            
            fig.add_trace(go.Scatter(
                x=[event_codes[-1]] + predicted_event_codes,
                y=[ace_values[-1]] + list(predicted_ace),
                mode='lines+markers',
                line=dict(
                    color='#2196F3', 
                    width=4, 
                    dash='dash', 
                    shape='spline',
                    smoothing=1.3
                ),
                marker=dict(
                    size=12, 
                    color='#2196F3', 
                    symbol='diamond',
                    line=dict(color='white', width=2),
                    opacity=0.9
                ),
                fill='tozeroy',
                fillcolor='rgba(33,150,243,0.15)',
                name='Pred',
                customdata=[
                    (event_codes[-1], auto_values[-1], teleop_values[-1], endgame_values[-1], raw_values[-1], confidence_values[-1], ace_values[-1], 'Actual'),
                    *[(predicted_event_codes[i], predicted_auto[i], predicted_teleop[i], predicted_endgame[i], predicted_raw[i], predicted_confidence[i], predicted_ace[i], 'Predicted') for i in range(n_pred)]
                ],
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Auto: %{customdata[1]:.2f}<br>'
                    'Teleop: %{customdata[2]:.2f}<br>'
                    'Endgame: %{customdata[3]:.2f}<br>'
                    'RAW: %{customdata[4]:.2f}<br>'
                    'Confidence: %{customdata[5]:.2f}<br>'
                    'ACE: %{customdata[6]:.2f}<br>'
                    '<i>%{customdata[7]}</i><extra></extra>'
                ),
                showlegend=True
            ))
        event_links = [f'<a href="/event/{code}" target="_blank">{code}</a>' for code in event_codes] + predicted_event_codes
        
        # Enhanced layout with cool styling
        fig.update_layout(
            title=dict(
                text=f"Team {team_number} Performance Trends",
                font=dict(size=24, color='#FFDD00', family='Arial Black'),
                x=0.5,
                y=0.95
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white', family='Arial'),
            xaxis=dict(
                title=dict(text="Events", font=dict(size=16, color='#FFDD00')),
                gridcolor='rgba(255,255,255,0.1)',
                zerolinecolor='rgba(255,255,255,0.2)',
                tickfont=dict(color='white'),
                showgrid=True
            ),
            yaxis=dict(
                title=dict(text="ACE Score", font=dict(size=16, color='#FFDD00')),
                gridcolor='rgba(255,255,255,0.1)',
                zerolinecolor='rgba(255,255,255,0.2)',
                tickfont=dict(color='white'),
                showgrid=True
            ),
            legend=dict(
                font=dict(color='white', size=14),
                x=0.02,
                y=0.98
            ),
            hovermode='closest',
            margin=dict(l=80, r=80, t=100, b=80),
            showlegend=True
        )
        fig.update_layout(
            title=f"Team {team_number} Event Performance in {performance_year}",
            height=400,
            margin=dict(l=50, r=50, t=80, b=60),
            font=dict(color="#999"),
            xaxis_title="Event Code",
            yaxis_title="ACE",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                tickmode='array',
                tickvals=event_codes + predicted_event_codes,
                ticktext=event_links,
                ticklabelmode='instant',
                tickformat='html',
                ticklabelstandoff=10,
            ),
            hoverlabel=dict(
                bgcolor="#1A1A1A",
                font=dict(color="white"),
                bordercolor="rgba(0,0,0,0)",
            ),
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', zeroline=False)
        trends_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    else:
        # Show one point per year with normalized ACE (percentile) as Y axis
        year_stats = []
        for year_key in sorted(years_participated):
            if year_key in (2020, 2021):
                continue  # Skip 2020 and 2021
            # Only extract the team's summary for each year
            if year_key == current_year:
                team_year_data = team_database.get(year_key, {}).get(team_number, {})
                ace_values = [max(0.0, data.get("epa", 0)) for data in team_database.get(year_key, {}).values()]
            else:
                try:
                    year_team_data, *_ = load_year_data(year_key)
                    team_year_data = year_team_data.get(team_number, {})
                    ace_values = [max(0.0, data.get("epa", 0)) for data in year_team_data.values()]
                except Exception:
                    team_year_data = {}
                    ace_values = []
            if team_year_data:
                ace = max(0.0, team_year_data.get("epa", 0))
                auto = max(0.0, team_year_data.get("auto_epa", 0))
                teleop = max(0.0, team_year_data.get("teleop_epa", 0))
                endgame = max(0.0, team_year_data.get("endgame_epa", 0))
                confidence = min(1.0, max(0.0, team_year_data.get("confidence", 0)))
                epa = max(0.0, team_year_data.get("normal_epa", 0))
                # Compute percentile for ACE in this year
                if ace_values:
                    sorted_ace = sorted(ace_values)
                    percentile = 100.0 * sum(val < ace for val in sorted_ace) / len(sorted_ace)
                else:
                    percentile = 0
                year_stats.append({
                    "year": year_key,
                    "ace": ace,
                    "auto": auto,
                    "teleop": teleop,
                    "endgame": endgame,
                    "epa": epa,
                    "confidence": confidence,
                    "percentile": percentile
                })
        if not year_stats:
            return html.Div("No historical year data available for this team.")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[ys["year"] for ys in year_stats],
            y=[ys["percentile"] for ys in year_stats],
            mode='lines+markers',
            line=dict(color='#FFDD00', width=3, shape='spline'),
            marker=dict(size=8, color='#FFDD00'),
            fill='tozeroy',
            name='Normalized ACE Percentile',
            customdata=[
                (
                    ys["year"],
                    ys["auto"],
                    ys["teleop"],
                    ys["endgame"],
                    ys["epa"],
                    ys["confidence"],
                    ys["ace"],
                    ys["percentile"]
                ) for ys in year_stats
            ],
            hovertemplate=(
                '<b>Year: %{customdata[0]}</b><br>'
                'Auto: %{customdata[1]:.2f}<br>'
                'Teleop: %{customdata[2]:.2f}<br>'
                'Endgame: %{customdata[3]:.2f}<br>'
                'RAW: %{customdata[4]:.2f}<br>'
                'Confidence: %{customdata[5]:.2f}<br>'
                'ACE: %{customdata[6]:.2f}<br>'
                '<b>ACE Percentile: %{customdata[7]:.1f}</b><extra></extra>'
            ),
        ))
        fig.update_layout(
            title=f"Team {team_number} Yearly Normalized ACE (Percentile)",
            height=400,
            margin=dict(l=50, r=50, t=80, b=60),
            font=dict(color="#999"),
            xaxis_title="Year",
            yaxis_title="ACE Percentile (0-100)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                tickmode='array',
                tickvals=[ys["year"] for ys in year_stats],
                ticktext=[str(ys["year"]) for ys in year_stats],
                ticklabelmode='instant',
                tickformat='html',
                ticklabelstandoff=10,
            ),
            hoverlabel=dict(
                bgcolor="#2D2D2D",
                font=dict(color="white"),
                bordercolor="rgba(0,0,0,0)",
            ),
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', zeroline=False, range=[0, 100])
        trends_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    return html.Div([
        html.Div(trends_chart, className="trends-chart-container"),
        html.Hr(style={"margin": "30px 0"})
    ])

def focused_peekolive_layout(event_key):
    """Create a focused peekolive layout for a specific event with stream on right and notifications on left"""
    
    # Get event data from database like the main peekolive page does
    event_data = None
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT event_key, name, start_date, end_date, webcast_type, webcast_channel, city, state_prov, country
                FROM events
                WHERE event_key = %s
                """,
                (event_key,)
            )
            row = cur.fetchone()
            if row:
                ek, name, sd, ed, wtype, wchan, city, state, country = row
                try:
                    year = int(str(ek)[:4])
                except Exception:
                    year = None
                event_data = {
                    "event_key": ek,
                    "name": name,
                    "webcast_type": (wtype or "").lower(),
                    "webcast_channel": wchan,
                    "start_date": sd,
                    "end_date": ed,
                    "year": year,
                    "location": ", ".join([v for v in [city, state, country] if v])
                }
    except Exception as e:
        print(f"Error fetching event data: {e}")
    
    if not event_data:
        return html.Div([
            dbc.Alert(f"Event {event_key} not found", color="danger"),
            html.A("← Back to PeekoLive", href="/events/peekolive", className="btn btn-primary")
        ])
    
    event_name = event_data.get("name", "Unknown Event")
    event_location = event_data.get("location", "")
    start_date = event_data.get("start_date", "N/A")
    end_date = event_data.get("end_date", "N/A")
    
    # Format dates
    start_display = format_human_date(start_date) if start_date and start_date != "N/A" else start_date
    end_display = format_human_date(end_date) if end_date and end_date != "N/A" else end_date
    
    return html.Div([
        # Add header and footer
        topbar(),
        # Header
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.A("← Back to PeekoLive", href="/events/peekolive", style={
                        "color": "var(--primary-color)", 
                        "textDecoration": "none",
                        "fontWeight": "500"
                    }),
                    html.H2(f"{event_name}", className="mt-3 mb-2"),
                    html.P(f"{event_location}", className="text-muted mb-1"),
                    html.P(f"{start_display} - {end_display}", className="text-muted mb-0"),
                ], width=12)
            ], className="mb-4")
        ]),
        
        # Main content area
        dbc.Container([
            dbc.Row([
                # Left side - Stream
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.Div([
                                html.Div([
                                    html.H5("Live Stream", className="mb-0"),
                                    html.Small("Event broadcast", className="text-muted")
                                ], style={"flex": "1"}),
                                html.Div(id="stream-status-dot", children=get_stream_status_dot(event_data), style={"marginLeft": "10px"})
                            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"})
                        ]),
                        dbc.CardBody([
                            html.Div(id="event-stream", children=[
                                # This will be populated by the stream component
                                peekolive_embed_for(event_data) if event_data.get("webcast_channel") else html.Div([
                                    html.I(className="fas fa-video text-muted", style={"fontSize": "3rem", "marginBottom": "1rem"}),
                                    html.H5("No Live Stream Available", className="text-muted"),
                                    html.P("This event doesn't have a live stream configured.", className="text-muted")
                                ], style={"textAlign": "center", "padding": "2rem"})
                            ], style={
                                "height": "500px", 
                                "maxHeight": "500px",
                                "overflow": "hidden",
                                "display": "flex", 
                                "alignItems": "center", 
                                "justifyContent": "center"
                            })
                        ], style={"padding": "0", "height": "100%", "overflow": "hidden"})
                    ], style={"height": "600px"})
                ], width={"size": 12, "sm": 6}, style={"marginBottom": "20px"}),
                
                # Right side - Notifications
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("Match Notifications", className="mb-0"),
                            html.Small("Live updates from matches", className="text-muted")
                        ]),
                        dbc.CardBody([
                            # Team filter dropdown
                            html.Div([
                                html.Label("Filter by Team:", style={"fontWeight": "bold", "marginBottom": "8px", "color": "var(--primary-color)"}),
                                dcc.Dropdown(
                                    id={"type": "team-filter", "event_key": event_key},
                                    options=[{"label": "All Teams", "value": "all"}] + get_event_teams(event_key),
                                    value="all",
                                    placeholder="Select a team to filter matches...",
                                    style={"marginBottom": "15px"}
                                )
                            ]),
                            html.Div(id="match-notifications", children=build_match_notifications(event_key), style={
                                "maxHeight": "400px",
                                "overflowY": "auto",
                                "overflowX": "hidden",
                                "paddingRight": "10px",
                                "paddingBottom": "15px",
                                "flex": "1",
                                "minHeight": "0"
                            })
                        ], style={"padding": "1rem", "height": "100%", "display": "flex", "flexDirection": "column"})
                    ], style={"height": "600px", "display": "flex", "flexDirection": "column"}, className="match-notifications-card")
                ], width={"size": 12, "sm": 6}, style={"marginBottom": "20px"})
            ]),
            
            # Team list and matches section
            dbc.Row([
                # Left side - Teams
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("Participating Teams", className="mb-0"),
                            html.Small("Teams competing in this event", className="text-muted")
                        ]),
                        dbc.CardBody([
                            html.Div(id="team-list", children=build_team_list(event_key), style={
                                "maxHeight": "400px",
                                "overflowY": "auto",
                                "paddingRight": "10px"
                            })
                        ], style={"padding": "1rem"})
                    ], style={"marginTop": "20px"})
                ], width={"size": 12, "sm": 6}, style={"marginBottom": "20px"}),
                
                # Right side - All Matches
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("All Matches", className="mb-0"),
                            html.Small("Complete match schedule", className="text-muted")
                        ]),
                        dbc.CardBody([
                            html.Div(id="all-matches", children=build_all_matches(event_key), style={
                                "maxHeight": "400px",
                                "overflowY": "auto",
                                "paddingRight": "10px"
                            })
                        ], style={"padding": "1rem"})
                    ], style={"marginTop": "20px"})
                ], width={"size": 12, "sm": 6}, style={"marginBottom": "20px"})
            ])
        ]),
        footer
    ])

def get_event_teams(event_key):
    """Get list of teams participating in the event"""
    
    teams = []
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT team_number, nickname
                FROM event_teams
                WHERE event_key = %s
                ORDER BY team_number
                """,
                (event_key,)
            )
            rows = cur.fetchall()
            for row in rows:
                team_number, nickname = row
                teams.append({
                    "label": f"{team_number} - {nickname or 'Unknown'}",
                    "value": str(team_number)
                })
    except Exception as e:
        print(f"Error fetching event teams: {e}")
    
    return teams

def build_team_list(event_key):
    """Build team list with avatars for the focused peekolive page"""
    
    teams = []
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT team_number, nickname, city, state_prov, country
                FROM event_teams
                WHERE event_key = %s
                ORDER BY team_number
                """,
                (event_key,)
            )
            rows = cur.fetchall()
            
            for row in rows:
                team_number, nickname, city, state, country = row
                
                # Build location string
                location_parts = [part for part in [city, state, country] if part]
                location = ", ".join(location_parts) if location_parts else "Unknown"
                
                # Get team colors if available
                team_colors = get_team_colors(team_number)
                primary_color = team_colors.get("primary", "#6c757d")
                secondary_color = team_colors.get("secondary", "#ffffff")
                
                # Create team card
                team_card = dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            # Team avatar
                            html.Div([
                                html.Img(
                                    src=f"/assets/avatars/{team_number}.png",
                                    alt=f"Team {team_number}",
                                    style={
                                        "width": "60px",
                                        "height": "60px",
                                        "borderRadius": "50%",
                                        "objectFit": "cover",
                                        "border": f"3px solid {primary_color}",
                                        "boxShadow": f"0 2px 8px rgba(0,0,0,0.1)"
                                    }
                                )
                            ], style={"marginRight": "15px"}),
                            
                            # Team info
                            html.Div([
                                html.Div([
                                    html.H6(f"Team {team_number}", className="mb-1"),
                                    html.P(nickname or "Unknown Team", className="mb-1 text-muted", style={"fontSize": "14px"}),
                                    html.Small(location, className="text-muted", style={"fontSize": "12px"})
                                ], style={"flex": "1"}),
                                
                                # Team links
                                html.Div([
                                    html.A(
                                        html.I(className="fas fa-external-link-alt"),
                                        href=f"/team/{team_number}",
                                        target="_blank",
                                        style={"textDecoration": "none", "marginLeft": "10px", "color": "var(--bs-primary)"}
                                    ) if team_number else None
                                ], style={"textAlign": "right"})
                            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "flex": "1"})
                        ], style={"display": "flex", "alignItems": "center"})
                    ], style={"padding": "12px"})
                ], style={
                    "marginBottom": "10px",
                    "border": f"1px solid {primary_color}60",
                    "borderRadius": "8px",
                    "background": f"linear-gradient(135deg, {primary_color}30, {secondary_color}20)",
                    "transition": "all 0.2s ease"
                }, className="team-card")
                
                teams.append(team_card)
                
    except Exception as e:
        print(f"Error building team list: {e}")
        return html.Div([
            html.I(className="fas fa-exclamation-triangle text-warning", style={"marginRight": "8px"}),
            "Error loading teams"
        ], className="text-muted")
    
    if not teams:
        return html.Div([
            html.I(className="fas fa-users text-muted", style={"fontSize": "2rem", "marginBottom": "1rem"}),
            html.H6("No Teams Found", className="text-muted"),
            html.P("No teams are registered for this event.", className="text-muted")
        ], style={"textAlign": "center", "padding": "2rem"})
    
    return html.Div(teams)

def get_team_colors(team_number):
    """Get team colors from the team_colors.json file"""
    try:
        colors_file = os.path.join(os.path.dirname(__file__), "data", "team_colors.json")
        if os.path.exists(colors_file):
            with open(colors_file, 'r') as f:
                team_colors = json.load(f)
                return team_colors.get(str(team_number), {"primary": "#6c757d", "secondary": "#ffffff"})
    except Exception as e:
        print(f"Error loading team colors: {e}")
    
    return {"primary": "#6c757d", "secondary": "#ffffff"}

def get_sf_bracket_position(match_key, predicted_time, all_sf_matches):
    """Determine the actual bracket position for semifinal matches based on predicted time"""
    if not predicted_time or not all_sf_matches:
        return 1
    
    try:
        # Sort all SF matches by predicted time to get the actual bracket order
        sorted_sf_matches = sorted(all_sf_matches, key=lambda x: x.get('predicted_time', 0) or 0)
        
        # Find this match's position in the sorted list using match_key
        for i, match in enumerate(sorted_sf_matches):
            if match.get('match_key') == match_key:
                return i + 1  # Return actual position (1, 2, 3, 4, etc.)
        
        return 1
    except Exception as e:
        print(f"Error calculating SF bracket position: {e}")
        return 1

def build_all_matches(event_key):
    """Build all matches list for the focused peekolive page"""
    
    matches = []
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT match_key, comp_level, match_number, red_score, blue_score, 
                       predicted_time, red_teams, blue_teams, winning_alliance
                FROM event_matches
                WHERE event_key = %s
                ORDER BY 
                    CASE comp_level 
                        WHEN 'qm' THEN 1 
                        WHEN 'qf' THEN 2 
                        WHEN 'sf' THEN 3 
                        WHEN 'f' THEN 4 
                        ELSE 5 
                    END,
                    match_number
                """,
                (event_key,)
            )
            rows = cur.fetchall()
            
            # Collect all SF matches for bracket position calculation
            sf_matches = []
            for row in rows:
                match_key, comp_level, match_number, red_score, blue_score, predicted_time, red_teams, blue_teams, winning_alliance = row
                if comp_level == 'sf':
                    sf_matches.append({
                        'match_key': match_key,
                        'predicted_time': predicted_time
                    })
            
            # Sort all matches by predicted time for proper display order
            sorted_rows = sorted(rows, key=lambda x: x[5] or 0)  # x[5] is predicted_time
            
            for row in sorted_rows:
                match_key, comp_level, match_number, red_score, blue_score, predicted_time, red_teams, blue_teams, winning_alliance = row
                
                # Determine match status
                is_completed = red_score > 0 or blue_score > 0
                status = "completed" if is_completed else "upcoming"
                
                # Format predicted time
                time_display = format_predicted_time_display(predicted_time) if predicted_time else "TBD"
                
                # Parse alliances from team strings
                red_team_list = red_teams.split(',') if red_teams else []
                blue_team_list = blue_teams.split(',') if blue_teams else []
                
                # Determine background color based on winning alliance
                if is_completed:
                    if winning_alliance == 'red':
                        bg_color = "var(--table-row-red)"  # Light red for red alliance win
                    elif winning_alliance == 'blue':
                        bg_color = "var(--table-row-blue)"  # Light blue for blue alliance win
                    else:
                        bg_color = "var(--bg-secondary)"  # Light gray for no winner/tie
                else:  # upcoming matches
                    if comp_level == 'f':
                        bg_color = "var(--table-row-yellow)"  # Light yellow for finals
                    elif comp_level == 'sf':
                        bg_color = "var(--table-row-green)"  # Light green for semifinals
                    elif comp_level == 'qf':
                        bg_color = "var(--table-row-pink)"  # Light pink for quarterfinals
                    else:  # qm
                        bg_color = "var(--bg-secondary)"  # Light gray for qualifiers
                
                # Create match card
                match_card = dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            # Match header
                            html.Div([
                                html.H6(
                                    f"{comp_level.upper()} {match_number}" if comp_level != 'sf' else 
                                    f"SF {get_sf_bracket_position(match_key, predicted_time, sf_matches)}", 
                                    className="mb-1"
                                ),
                                html.Small(time_display, className="text-muted")
                            ], style={"flex": "1"}),
                            
                            # Match status indicator
                            html.Div([
                                html.Span(
                                    "✓" if is_completed else "⏰",
                                    style={
                                        "color": "#28a745" if is_completed else "#ffc107",
                                        "fontSize": "18px",
                                        "fontWeight": "bold"
                                    }
                                )
                            ], style={"marginLeft": "10px"})
                        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "10px"}),
                        
                        # Alliance info - side by side
                        html.Div([
                            # Red alliance
                            html.Div([
                                html.Small("Red Alliance", className="text-danger", style={"fontWeight": "bold"}),
                                html.Div([
                                    html.Span(f"Team {team}", className="badge bg-danger me-1", style={"fontSize": "10px"})
                                    for team in red_team_list[:3]  # Show first 3 teams
                                ]),
                                html.Small(f"{red_score}", className="text-danger", style={"fontWeight": "bold", "marginLeft": "5px"}) if is_completed else None
                            ], style={"flex": "1", "marginRight": "10px"}),
                            
                            # Blue alliance
                            html.Div([
                                html.Small("Blue Alliance", className="text-primary", style={"fontWeight": "bold"}),
                                html.Div([
                                    html.Span(f"Team {team}", className="badge bg-primary me-1", style={"fontSize": "10px"})
                                    for team in blue_team_list[:3]  # Show first 3 teams
                                ]),
                                html.Small(f"{blue_score}", className="text-primary", style={"fontWeight": "bold", "marginLeft": "5px"}) if is_completed else None
                            ], style={"flex": "1"})
                        ], style={"display": "flex", "gap": "10px"})
                    ], style={"padding": "12px"})
                ], style={
                    "marginBottom": "8px",
                    "border": "1px solid var(--border-color)",
                    "borderRadius": "6px",
                    "backgroundColor": bg_color,
                    "transition": "all 0.2s ease"
                }, className="match-card")
                
                matches.append(match_card)
                
    except Exception as e:
        print(f"Error building all matches: {e}")
        return html.Div([
            html.I(className="fas fa-exclamation-triangle text-warning", style={"marginRight": "8px"}),
            "Error loading matches"
        ], className="text-muted")
    
    if not matches:
        return html.Div([
            html.I(className="fas fa-calendar text-muted", style={"fontSize": "2rem", "marginBottom": "1rem"}),
            html.H6("No Matches Found", className="text-muted"),
            html.P("No matches are scheduled for this event.", className="text-muted")
        ], style={"textAlign": "center", "padding": "2rem"})
    
    return html.Div(matches)

def get_time_until_match(predicted_time):
    """Calculate time until match and return formatted string"""
    if not predicted_time:
        return "Time TBD"
    
    try:
        
        # Handle different types of predicted_time
        if isinstance(predicted_time, int):
            # Unix timestamp - convert to datetime
            match_time = datetime.fromtimestamp(predicted_time, tz=timezone.utc)
        elif isinstance(predicted_time, str):
            # ISO format string
            match_time = datetime.fromisoformat(predicted_time.replace('Z', '+00:00'))
        elif isinstance(predicted_time, datetime):
            # Already a datetime object
            match_time = predicted_time
            # Ensure timezone aware
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
        else:
            return "Time TBD"
        
        # Get user's local timezone - use configured timezone
        try:
            user_tz = pytz.timezone(DEFAULT_TIMEZONE)
        except:
            try:
                # Fallback to system timezone
                offset = time.timezone if (time.daylight == 0) else time.altzone
                user_tz = timezone(timedelta(seconds=-offset))
            except:
                # Final fallback to UTC
                user_tz = timezone.utc
        
        # Convert to user's timezone
        match_time_local = match_time.astimezone(user_tz)
        now_local = datetime.now(user_tz)
        time_diff = match_time_local - now_local
        
        if time_diff.total_seconds() < 0:
            return "Match in progress or completed"
        elif time_diff.total_seconds() < 60:
            return "Match starting now!"
        elif time_diff.total_seconds() < 3600:  # Less than 1 hour
            minutes = int(time_diff.total_seconds() / 60)
            return f"Match in {minutes} minute{'s' if minutes != 1 else ''}"
        else:  # More than 1 hour
            hours = int(time_diff.total_seconds() / 3600)
            minutes = int((time_diff.total_seconds() % 3600) / 60)
            if minutes == 0:
                return f"Match in {hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"Match in {hours}h {minutes}m"
    except Exception as e:
        print(f"Error calculating time until match: {e}")
        return "Time TBD"

def format_predicted_time_display(predicted_time):
    """Format predicted time for display"""
    if not predicted_time:
        return "TBD"
    
    try:
        # Handle different types of predicted_time
        if isinstance(predicted_time, int):
            # Unix timestamp - convert to datetime
            match_time = datetime.fromtimestamp(predicted_time, tz=timezone.utc)
        elif isinstance(predicted_time, str):
            # ISO format string
            match_time = datetime.fromisoformat(predicted_time.replace('Z', '+00:00'))
        elif isinstance(predicted_time, datetime):
            # Already a datetime object
            match_time = predicted_time
            # Ensure timezone aware
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
        else:
            return "TBD"
        
        # Get user's local timezone - use configured timezone
        try:
            user_tz = pytz.timezone(DEFAULT_TIMEZONE)
        except:
            try:
                # Fallback to system timezone
                offset = time.timezone if (time.daylight == 0) else time.altzone
                user_tz = timezone(timedelta(seconds=-offset))
            except:
                # Final fallback to UTC
                user_tz = timezone.utc
        
        # Convert to user's timezone
        match_time_local = match_time.astimezone(user_tz)
        
        # Get timezone abbreviation and map to common names
        offset_str = match_time_local.strftime('%z')
        
        # Try to get timezone name from system first
        try:
            if time.daylight:
                tz_abbr = time.tzname[1]  # Daylight time name
            else:
                tz_abbr = time.tzname[0]  # Standard time name
            
            # If we got a proper timezone name, use it
            if tz_abbr and tz_abbr != 'UTC':
                # Extract abbreviation from full name
                if 'Central' in tz_abbr:
                    tz_abbr = "CDT" if time.daylight else "CST"
                elif 'Eastern' in tz_abbr:
                    tz_abbr = "EDT" if time.daylight else "EST"
                elif 'Mountain' in tz_abbr:
                    tz_abbr = "MDT" if time.daylight else "MST"
                elif 'Pacific' in tz_abbr:
                    tz_abbr = "PDT" if time.daylight else "PST"
        except:
            tz_abbr = None
        
        # Fallback to offset-based mapping if system names didn't work
        if not tz_abbr or tz_abbr == 'UTC':
            if offset_str:
                offset_hours = int(offset_str[1:3])
                offset_mins = int(offset_str[3:5])
                
                # Common US timezone mappings
                if offset_str[0] == '-':  # Negative offset (behind UTC)
                    if offset_hours == 5 and offset_mins == 0:
                        tz_abbr = "CDT"  # Central Daylight Time
                    elif offset_hours == 6 and offset_mins == 0:
                        tz_abbr = "CST"  # Central Standard Time
                    elif offset_hours == 4 and offset_mins == 0:
                        tz_abbr = "EDT"  # Eastern Daylight Time
                    elif offset_hours == 5 and offset_mins == 0:
                        tz_abbr = "EST"  # Eastern Standard Time
                    elif offset_hours == 7 and offset_mins == 0:
                        tz_abbr = "MST"  # Mountain Standard Time
                    elif offset_hours == 6 and offset_mins == 0:
                        tz_abbr = "MDT"  # Mountain Daylight Time
                    elif offset_hours == 8 and offset_mins == 0:
                        tz_abbr = "PST"  # Pacific Standard Time
                    elif offset_hours == 7 and offset_mins == 0:
                        tz_abbr = "PDT"  # Pacific Daylight Time
                    else:
                        tz_abbr = f"UTC{offset_str}"
                else:  # Positive offset (ahead of UTC)
                    tz_abbr = f"UTC+{offset_hours:02d}:{offset_mins:02d}"
            else:
                tz_abbr = "Local"
        
        return match_time_local.strftime(f'%I:%M %p {tz_abbr}')
    except Exception as e:
        print(f"Error formatting predicted time: {e}")
        return "TBD"

def get_stream_status_dot(event_data):
    """Get status indicator dot for the stream based on event timing"""
    try:
        start_date = event_data.get("start_date")
        end_date = event_data.get("end_date")
        
        if not start_date or not end_date:
            return html.Div([
                html.Div(className="status-dot status-unknown", title="Event status unknown")
            ])
        
        # Parse dates
        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = start_date
            
        if isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = end_date
        
        # Make timezone aware
        start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = end_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        
        # Determine status
        if now < start_dt:
            # Event hasn't started yet
            return html.Div([
                html.Div(className="status-dot status-upcoming", title="Event upcoming")
            ])
        elif start_dt <= now <= end_dt:
            # Event is ongoing
            return html.Div([
                html.Div(className="status-dot status-ongoing", title="Event ongoing")
            ])
        else:
            # Event has ended
            return html.Div([
                html.Div(className="status-dot status-completed", title="Event completed")
            ])
            
    except Exception as e:
        print(f"Error determining event status: {e}")
        return html.Div([
            html.Div(className="status-dot status-unknown", title="Event status unknown")
        ])

def build_match_notifications(event_key, selected_team=None):
    """Build match notifications for the focused peekolive page"""
    # Get matches from database
    matches = []
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT match_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, predicted_time
                FROM event_matches
                WHERE event_key = %s
                ORDER BY predicted_time ASC NULLS LAST, comp_level, match_number
                """,
                (event_key,)
            )
            rows = cur.fetchall()
            for row in rows:
                match_key, comp_level, match_number, set_number, red_teams, blue_teams, red_score, blue_score, winning_alliance, predicted_time = row
                matches.append({
                    "k": match_key,
                    "cl": comp_level,
                    "mn": match_number,
                    "sn": set_number,
                    "rt": red_teams or "",
                    "bt": blue_teams or "",
                    "rs": red_score or 0,
                    "bs": blue_score or 0,
                    "wa": winning_alliance or "",
                    "pt": predicted_time
                })
    except Exception as e:
        print(f"Error fetching matches: {e}")
    
    # Filter matches by selected team if provided (and not "all")
    if selected_team and selected_team != "all":
        # Handle case where selected_team might be a list
        if isinstance(selected_team, list):
            selected_team = selected_team[0] if selected_team else None
        
        if selected_team and selected_team != "all":
            print(f"Filtering for team: {selected_team}")
            filtered_matches = []
            for match in matches:
                red_teams = match.get("rt", "").split(",") if match.get("rt") else []
                blue_teams = match.get("bt", "").split(",") if match.get("bt") else []
                # Convert team numbers to strings for comparison
                red_teams = [str(team).strip() for team in red_teams if team.strip()]
                blue_teams = [str(team).strip() for team in blue_teams if team.strip()]
                print(f"Match {match.get('mn', '?')}: Red teams: {red_teams}, Blue teams: {blue_teams}")
                if str(selected_team) in red_teams or str(selected_team) in blue_teams:
                    filtered_matches.append(match)
            matches = filtered_matches
            print(f"Found {len(matches)} matches for team {selected_team}")
    
    if not matches:
        if selected_team and selected_team != "all":
            return html.Div([
                html.Div([
                    html.I(className="fas fa-info-circle text-info me-2"),
                    html.Span(f"No matches starting within the next hour for team {selected_team}", className="text-muted")
                ], className="notification-item")
            ])
        else:
            return html.Div([
                html.Div([
                    html.I(className="fas fa-info-circle text-info me-2"),
                    html.Span("No matches starting within the next hour", className="text-muted")
                ], className="notification-item")
            ])
    # Get user's local timezone - use configured timezone
    try:
        user_tz = pytz.timezone(DEFAULT_TIMEZONE)
    except:
        try:
            # Fallback to system timezone
            offset = time.timezone if (time.daylight == 0) else time.altzone
            user_tz = timezone(timedelta(seconds=-offset))
        except:
            # Final fallback to UTC
            user_tz = timezone.utc
    
    now = datetime.now(user_tz)
    one_hour_from_now = now + timedelta(hours=1)
    
    # Filter matches to only show upcoming matches within the next hour
    upcoming_matches = []
    for match in matches:
        predicted_time = match.get("pt")
        if predicted_time:
            try:
                # Convert predicted_time to datetime
                if isinstance(predicted_time, int):
                    match_time = datetime.fromtimestamp(predicted_time, tz=timezone.utc)
                elif isinstance(predicted_time, str):
                    match_time = datetime.fromisoformat(predicted_time.replace('Z', '+00:00'))
                elif isinstance(predicted_time, datetime):
                    match_time = predicted_time
                    if match_time.tzinfo is None:
                        match_time = match_time.replace(tzinfo=timezone.utc)
                else:
                    continue
                
                # Convert to user's timezone for comparison
                match_time_local = match_time.astimezone(user_tz)
                
                # Only include matches that are:
                # 1. Not yet started (match_time > now)
                # 2. Starting within the next hour (match_time <= one_hour_from_now)
                if now < match_time_local <= one_hour_from_now:
                    upcoming_matches.append(match)
            except Exception as e:
                print(f"Error processing match time: {e}")
                continue
    
    # Use filtered matches
    matches = upcoming_matches
    
    notifications = []
    for match in matches:
        match_key = match.get("k", "")
        match_number = match.get("mn", 0)
        comp_level = match.get("cl", "qm")
        red_teams = match.get("rt", "")
        blue_teams = match.get("bt", "")
        red_score = match.get("rs", 0)
        blue_score = match.get("bs", 0)
        winning_alliance = match.get("wa", "")
        predicted_time = match.get("pt")
        
        # Get time until match
        time_until = get_time_until_match(predicted_time)
        
        # Determine match status
        if red_score > 0 or blue_score > 0:
            status = "completed"
            status_icon = "fas fa-check-circle text-success"
            status_text = "Completed"
        else:
            status = "upcoming"
            status_icon = "fas fa-clock text-warning"
            status_text = time_until
        
        # Format teams
        red_team_list = red_teams.split(",") if red_teams else []
        blue_team_list = blue_teams.split(",") if blue_teams else []
        
        # Format match label
        if comp_level == "qm":
            match_label = f"Q{match_number}"
        elif comp_level == "qf":
            match_label = f"QF{match_number}"
        elif comp_level == "sf":
            match_label = f"SF{match_number}"
        elif comp_level == "f":
            match_label = f"F{match_number}"
        else:
            match_label = f"{comp_level.upper()}{match_number}"
        
        notification = html.Div([
            html.Div([
                html.I(className=status_icon),
                html.Span(f" {match_label}", className="fw-bold ms-2"),
                html.Span(f" - {status_text}", className="text-muted ms-1")
            ], className="notification-header"),
            html.Div([
                html.Div([
                    html.Span("Red: ", className="text-danger fw-bold"),
                    html.Span(", ".join(red_team_list), className="me-3")
                ]),
                html.Div([
                    html.Span("Blue: ", className="text-primary fw-bold"),
                    html.Span(", ".join(blue_team_list))
                ])
            ], className="notification-teams mt-2"),
            html.Div([
                html.Span(f"Score: {red_score} - {blue_score}", className="fw-bold"),
                html.Span(f" | Winner: {winning_alliance.title()}", className="text-success ms-2") if winning_alliance else ""
            ], className="notification-score mt-2") if status == "completed" else html.Div([
                html.Span(f"Predicted time: {format_predicted_time_display(predicted_time)}", className="text-info")
            ], className="notification-score mt-2")
        ], className="notification-item mb-3 p-3 border rounded")
        
        notifications.append(notification)
    
    return html.Div(notifications)

def higher_lower_layout():
    """Higher or Lower game layout comparing team ACE values"""
    is_logged_in = "user_id" in session
    return html.Div([
        topbar(),
        dbc.Container(fluid=True, children=[
            html.Div([
            # Filters and start button
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("Year", style={"color": "var(--text-primary)", "fontWeight": "bold", "marginBottom": "5px", "fontSize": "0.9rem"}),
                        dcc.Dropdown(
                            id="higher-lower-year-dropdown",
                            options=[{"label": str(yr), "value": yr} for yr in reversed(range(1992, 2027))],
                            value=current_year,
                            clearable=False,
                            placeholder="Select Year",
                            className="custom-input-box higher-lower-filter-dropdown"
                        )
                    ], className="higher-lower-filter-item"),
                    html.Div([
                        html.Label("Country", style={"color": "var(--text-primary)", "fontWeight": "bold", "marginBottom": "5px", "fontSize": "0.9rem"}),
                        dcc.Dropdown(
                            id="higher-lower-country-dropdown",
                            options=[{"label": "All", "value": "All"}] + [
                                c for c in (json.load(open('data/countries.json', 'r', encoding='utf-8')) if os.path.exists('data/countries.json') else [])
                                if (c.get("value") or "").lower() != "all"
                            ],
                            value="All",
                            clearable=False,
                            placeholder="Select Country",
                            className="custom-input-box higher-lower-filter-dropdown"
                        )
                    ], className="higher-lower-filter-item"),
                    html.Div([
                        html.Label("State", style={"color": "var(--text-primary)", "fontWeight": "bold", "marginBottom": "5px", "fontSize": "0.9rem"}),
                        dcc.Dropdown(
                            id="higher-lower-state-dropdown",
                            options=[{"label": "All States", "value": "All"}],
                            value="All",
                            clearable=False,
                            placeholder="Select State/Province",
                            className="custom-input-box higher-lower-filter-dropdown"
                        )
                    ], className="higher-lower-filter-item"),
                    html.Div([
                        html.Label("District", style={"color": "var(--text-primary)", "fontWeight": "bold", "marginBottom": "5px", "fontSize": "0.9rem"}),
                        dcc.Dropdown(
                            id="higher-lower-district-dropdown",
                            options=[
                                {"label": "All Districts", "value": "All"},
                                *get_team_district_options()
                            ],
                            value="All",
                            clearable=False,
                            placeholder="Select District",
                            className="custom-input-box higher-lower-filter-dropdown"
                        )
                    ], className="higher-lower-filter-item"),
                    html.Div([
                        dbc.Button("Start", id="higher-lower-start-btn", color="warning", size="lg",
                                  className="higher-lower-start-button")
                    ], className="higher-lower-filter-item higher-lower-start-container")
                ], className="higher-lower-filters-container")
            ], style={"borderBottom": "1px solid rgba(255, 255, 255, 0.1)"}),
            
            # Score and Highscore at top
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("Highscore", style={"fontSize": "0.75rem", "color": "var(--text-secondary)"}),
                        html.Span(
                            " • Log in to save your high score",
                            style={"fontSize": "0.75rem", "color": "var(--text-secondary)", "marginLeft": "6px"},
                        ) if not is_logged_in else None,
                    ]),
                    html.Div(id="highscore-display", children="0", style={"fontSize": "1.5rem", "fontWeight": "bold", "color": "var(--text-primary)"})
                ], style={"textAlign": "center", "flex": 1}),
                html.Div(style={"width": "2px", "backgroundColor": "white", "height": "40px", "margin": "0 20px"}),
                html.Div([
                    html.Div("Score", style={"fontSize": "0.75rem", "color": "var(--text-secondary)"}),
                    html.Div(id="score-display", children="0", style={"fontSize": "1.5rem", "fontWeight": "bold", "color": "var(--text-primary)"})
                ], style={"textAlign": "center", "flex": 1}),
                html.Div([
                    dbc.Popover(
                        [
                            dbc.PopoverHeader("How to Play"),
                            dbc.PopoverBody([
                                html.P("Guess whether the hidden team's ACE is Higher or Lower than the shown team's ACE."),
                                html.P("You get 3 wrong guesses before the game ends."),
                                html.P("Your score increases with each correct guess. Try to beat your highscore!"),
                                html.P([html.Strong("ACE (Adjusted Contribution Estimate)"), " is a team's expected contribution to a match, combining performance metrics with confidence factors."]),
                            ])
                        ],
                        target="higher-lower-info-icon",
                        trigger="click",
                        placement="left",
                    ),
                    html.I(
                        id="higher-lower-info-icon",
                        className="fas fa-info-circle",
                        style={"fontSize": "1.2rem", "color": "var(--text-secondary)", "cursor": "pointer"}
                    )
                ], style={"position": "absolute", "right": "20px", "top": "10px"})
            ], style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "padding": "20px",
                "position": "relative",
                "borderBottom": "1px solid rgba(255, 255, 255, 0.1)"
            }),
            
            # Main game area - two halves
            html.Div([
                # Left team (shows ACE)
                html.Div([
                    html.Div(id="left-team-avatar-container", style={"textAlign": "center", "marginBottom": "20px"}),
                    html.Div(id="left-team-name", className="higher-lower-team-name", style={"fontSize": "1.5rem", "fontWeight": "bold", "textAlign": "center", "marginBottom": "10px", "color": "var(--text-primary)"}),
                    html.Div("has a", style={"fontSize": "1rem", "textAlign": "center", "marginBottom": "10px", "color": "var(--text-secondary)"}),
                    html.Div(id="left-team-ace", className="higher-lower-ace", style={"fontSize": "3rem", "fontWeight": "bold", "textAlign": "center", "marginBottom": "10px", "color": "var(--text-primary)"}),
                    html.Div("ACE", style={"fontSize": "0.875rem", "textAlign": "center", "color": "var(--text-secondary)"})
                ], className="higher-lower-team-panel", style={
                    "flex": 1,
                    "padding": "40px",
                    "display": "flex",
                    "flexDirection": "column",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "borderRight": "2px solid white"
                }),
                
                # VS divider
                html.Div("vs", className="higher-lower-vs", style={
                    "position": "absolute",
                    "left": "50%",
                    "top": "50%",
                    "transform": "translate(-50%, -50%)",
                    "fontSize": "2rem",
                    "fontWeight": "bold",
                    "color": "white",
                    "backgroundColor": "var(--bg-primary)",
                    "padding": "10px 20px",
                    "zIndex": 10
                }),
                
                # Right team (hidden ACE with buttons)
                html.Div([
                    html.Div(id="right-team-avatar-container", style={"textAlign": "center", "marginBottom": "20px"}),
                    html.Div(id="right-team-name", className="higher-lower-team-name", style={"fontSize": "1.5rem", "fontWeight": "bold", "textAlign": "center", "marginBottom": "10px", "color": "var(--text-primary)"}),
                    html.Div("has a", style={"fontSize": "1rem", "textAlign": "center", "marginBottom": "10px", "color": "var(--text-secondary)"}),
                    html.Div(id="right-team-ace-container", className="higher-lower-ace", style={"textAlign": "center", "marginBottom": "10px"}),
                    html.Div([
                        dbc.Button("Higher", id="higher-btn", color="success", size="lg", className="higher-lower-btn", style={"marginRight": "10px", "padding": "15px 40px", "fontSize": "1.2rem"}),
                        dbc.Button("Lower", id="lower-btn", color="danger", size="lg", className="higher-lower-btn", style={"padding": "15px 40px", "fontSize": "1.2rem"})
                    ], id="higher-lower-buttons-container", style={"textAlign": "center", "marginBottom": "10px"}),
                    html.Div("ACE", style={"fontSize": "0.875rem", "textAlign": "center", "color": "var(--text-secondary)"})
                ], className="higher-lower-team-panel", style={
                    "flex": 1,
                    "padding": "40px",
                    "display": "flex",
                    "flexDirection": "column",
                    "justifyContent": "center",
                    "alignItems": "center"
                })
            ], id="higher-lower-game-container", style={
                "display": "flex",
                "position": "relative",
                "minHeight": "60vh",
                "alignItems": "center"
            }),
            
            # Game over message
            html.Div(id="game-over-message", style={"display": "none", "textAlign": "center", "padding": "20px"}),
            
            # Stores for game state
            dcc.Store(id="game-state-store", data={
                "score": 0,
                "highscore": 0,
                "wrong_guesses": 0,
                "left_team": None,
                "right_team": None,
                "left_ace": None,
                "right_ace": None
            }),
            dcc.Store(id="teams-data-store", data=[]),
            dcc.Store(id="selected-year-store", data=current_year),
            dcc.Store(id="selected-country-store", data="All"),
            dcc.Store(id="selected-state-store", data="All"),
            dcc.Store(id="selected-district-store", data="All"),
            dcc.Store(id="game-started-store", data=False),
            dcc.Store(id="teams-cache-store", data={}),  # Cache teams data per year
            dcc.Interval(id="reveal-transition-interval", interval=600, n_intervals=0, disabled=True),  # 600ms to show reveal clearly
            html.Button(id="pick-new-team-trigger", n_clicks=0, style={"display": "none"})  # Hidden trigger for picking new teams
            ], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "20px"})
        ], style={"minHeight": "100vh", "backgroundColor": "var(--bg-primary)"})
    ])

def duel_layout():
    return html.Div([
        topbar(),
        dbc.Container(
            fluid=True,
            children=[
                html.Div([
                    html.Div([
                        html.H2("Duel", className="duel-title"),
                        html.P(
                            "Compare two teams across seasons by head-to-head win rate.",
                            className="duel-subtitle"
                        )
                    ], className="duel-header"),
                    html.Div([
                        html.Div(id="duel-team-1-info", className="duel-team-info"),
                        html.Div(id="duel-team-2-info", className="duel-team-info"),
                    ], className="duel-team-info-row"),
                    html.Div([
                        dbc.Input(
                            id="duel-team-1-input",
                            placeholder="Team 1 (e.g., 1912)",
                            type="text",
                            className="duel-team-input duel-team-input-red"
                        ),
                        dbc.Button(
                            html.I(className="fas fa-exchange-alt"),
                            id="duel-swap-btn",
                            color="secondary",
                            className="duel-swap-btn"
                        ),
                        dbc.Input(
                            id="duel-team-2-input",
                            placeholder="Team 2 (e.g., 7525)",
                            type="text",
                            className="duel-team-input duel-team-input-blue"
                        ),
                        dbc.Button(
                            "Search",
                            id="duel-search-btn",
                            color="info",
                            className="duel-search-btn"
                        )
                    ], className="duel-inputs"),
                    html.Div([
                        dbc.Checklist(
                            id="duel-filter-options",
                            options=[
                                {"label": "Exclude Quals", "value": "exclude_quals"},
                                {"label": "Exclude Elims", "value": "exclude_elims"},
                            ],
                            value=[],
                            inline=True,
                            className="duel-filter-checks"
                        ),
                        dbc.Input(
                            id="duel-year-filter",
                            placeholder="Years (e.g., 2019-2026 or 2022,2024)",
                            type="text",
                            className="duel-year-input"
                        )
                    ], className="duel-filters"),
                    html.Div(id="duel-status-text", className="duel-status"),
                    html.Div([
                        html.Div([
                            html.Div("Matches Together", className="duel-stat-label"),
                            html.Div("0", id="duel-matches-together-value", className="duel-stat-value")
                        ], className="duel-stat-card"),
                        html.Div([
                            html.Div("Win Rate Together", className="duel-stat-label"),
                            html.Div("0%", id="duel-winrate-together-value", className="duel-stat-value"),
                            html.Div([
                                html.Span("W-L-T: ", className="duel-stat-meta-label"),
                                html.Span("0-0-0", id="duel-winrate-together-wlt", className="duel-stat-meta-value"),
                                html.Span(" • ", className="duel-stat-meta-sep"),
                                html.Span("Pts: ", className="duel-stat-meta-label"),
                                html.Span("0.0", id="duel-winrate-together-points", className="duel-stat-meta-value"),
                            ], className="duel-stat-meta")
                        ], className="duel-stat-card"),
                        html.Div([
                            html.Div("Matches Against", className="duel-stat-label"),
                            html.Div("0", id="duel-matches-against-value", className="duel-stat-value")
                        ], className="duel-stat-card"),
                        html.Div([
                            html.Div("Win Rate vs", id="duel-winrate-vs-label", className="duel-stat-label"),
                            html.Div("0%", id="duel-winrate-vs-value", className="duel-stat-value"),
                            html.Div([
                                html.Span("W-L-T: ", className="duel-stat-meta-label"),
                                html.Span("0-0-0", id="duel-winrate-vs-wlt", className="duel-stat-meta-value"),
                                html.Span(" • ", className="duel-stat-meta-sep"),
                                html.Span("Pts: ", className="duel-stat-meta-label"),
                                html.Span("0.0", id="duel-winrate-vs-points", className="duel-stat-meta-value"),
                            ], className="duel-stat-meta"),
                            html.Div(id="duel-winrate-vs-subtext", className="duel-stat-subtext")
                        ], className="duel-stat-card")
                    ], className="duel-stats"),
                    html.Div([
                        html.Div([
                            html.Div("Year", className="duel-table-header-cell duel-year-col"),
                            html.Div("Code", className="duel-table-header-cell duel-code-col"),
                            html.Div("Match", className="duel-table-header-cell duel-match-col"),
                            html.Div("Outcome", className="duel-table-header-cell duel-outcome-col")
                        ], className="duel-table-header"),
                        html.Div(
                            id="duel-match-list",
                            className="duel-match-list"
                        )
                    ], className="duel-table")
                ], className="duel-page")
            ],
            style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}
        ),
        footer
    ], style={"minHeight": "100vh", "display": "flex", "flexDirection": "column"})