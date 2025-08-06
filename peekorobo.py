import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc, dash_table, ctx, ALL, MATCH, no_update, callback_context
from dash.dependencies import Input, Output, State

import flask
from flask import session
from auth import register_user, verify_user

import os
import numpy as np
import datetime
from datetime import datetime, date

import re
import random
import requests
from urllib.parse import parse_qs, urlencode, quote, unquote
import json
import pandas as pd

import plotly.graph_objects as go

from datagather import load_data_2025,load_search_data,load_year_data,get_team_avatar,DatabaseConnection,get_team_years_participated

from layouts import create_team_card_spotlight,create_team_card_spotlight_event,insights_layout,insights_details_layout,team_layout,match_layout,user_profile_layout,home_layout,blog_layout,teams_map_layout,login_layout,create_team_card,teams_layout,event_layout,ace_legend_layout,events_layout,compare_layout

from utils import is_western_pennsylvania_city,format_human_date,predict_win_probability_adaptive,learn_from_match_outcome,calculate_all_ranks,get_user_avatar,get_epa_styling,compute_percentiles,get_contrast_text_color,universal_profile_icon_or_toast,get_week_number,event_card,truncate_name

from dotenv import load_dotenv
load_dotenv()

# Load optimized data: current year data globally + search data with all events
TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES = load_data_2025()
SEARCH_TEAM_DATA, SEARCH_EVENT_DATA = load_search_data()

with open('data/district_states.json', 'r', encoding='utf-8') as f:
    DISTRICT_STATES_COMBINED = json.load(f)

# Store app startup time for "Last Updated" indicator
APP_STARTUP_TIME = datetime.now()

current_year = 2025

app = dash.Dash(
    __name__,
    meta_tags=[
        {'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'},
        {'name': 'description', 'content': 'A scouting and statistics platform for FRC teams that provides detailed insights and resources'},
        {'name': 'keywords', 'content': 'FRC, Robotics, Scouting, FIRST, FIRST Robotics Competition, Statbotics, TBA, The Blue Alliance, Competition, Statistics'},
    ],
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
    ],
    suppress_callback_exceptions=True,
    title="Peekorobo",
)

server = app.server
server.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-placeholder-key")

def serve_layout():
    return dmc.MantineProvider(
        theme={
            "colorScheme": "light",
            "primaryColor": "blue",
            "components": {
                "ColorPicker": {"styles": {"root": {"width": "100%"}}}
            }
        },
        children=html.Div([
            dcc.Location(id='url', refresh=False),
            dcc.Store(id='tab-title', data='Peekorobo'),
            dcc.Store(id='theme-store'),
            html.Div(
                id='page-content-animated-wrapper',
                children=html.Div(id='page-content'),
                className='fade-page',
            ),
            universal_profile_icon_or_toast(),
            html.Div(id='dummy-output', style={'display': 'none'}),
            html.Button(id='page-load-trigger', n_clicks=1, style={'display': 'none'}),
            dcc.Interval(id='last-updated-interval', interval=60000, n_intervals=0)  # Update every minute
        ])
    )

app.layout = serve_layout

# client-side callback for smooth page transitions
app.clientside_callback(
    """
    function(pathname) {
        var wrapper = document.getElementById('page-content-animated-wrapper');
        if (!wrapper) return window.dash_clientside.no_update;

        // Fade out
        wrapper.classList.add('fade-out');
        
        // Fade back in after a short delay
        setTimeout(function() {
            wrapper.classList.remove('fade-out');
        }, 200); // Half the CSS transition duration for smooth effect

        return window.dash_clientside.no_update;
    }
    """,
    Output('dummy-output', 'children', allow_duplicate=True),
    Input('url', 'pathname'),
    prevent_initial_call=True
)

# Set dark mode immediately on first page render
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <script>
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
        </script>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Theme switching callbacks
app.clientside_callback(
    """
    function(n_clicks, current_theme) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }
        
        const new_theme = current_theme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', new_theme);
        
        // Update theme toggle icon
        const themeIcon = document.querySelector('#theme-toggle i');
        if (themeIcon) {
            themeIcon.className = new_theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
        
        return new_theme;
    }
    """,
    Output("theme-store", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True
)

# Initialize theme on page load
app.clientside_callback(
    """
    function() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        // Update theme toggle icon
        const themeIcon = document.querySelector('#theme-toggle i');
        if (themeIcon) {
            themeIcon.className = savedTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
        
        return savedTheme;
    }
    """,
    Output("theme-store", "data", allow_duplicate=True),
    Input("page-load-trigger", "n_clicks"),
    prevent_initial_call=True
)

# Save theme preference
app.clientside_callback(
    """
    function(theme) {
        if (theme) {
            localStorage.setItem('theme', theme);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("theme-store", "data", allow_duplicate=True),
    Input("theme-store", "data"),
    prevent_initial_call=True
)

# Add a callback to update the "Last Updated" text
@app.callback(
    [Output("last-updated-text", "children"),
     Output("last-updated-text-mobile", "children")],
    [Input("page-load-trigger", "n_clicks"),
     Input("last-updated-interval", "n_intervals")]
)
def update_last_updated_text(n_clicks, n_intervals):
    # Calculate time difference
    time_diff = datetime.now() - APP_STARTUP_TIME
    
    if time_diff.total_seconds() < 60:
        text = f"Updated {int(time_diff.total_seconds())}s ago"
    elif time_diff.total_seconds() < 3600:
        text = f"Updated {int(time_diff.total_seconds() // 60)}m ago"
    else:
        text = f"Updated {int(time_diff.total_seconds() // 3600)}h ago"
    
    return text, text

# Add a callback to update navigation link styles based on current page
@app.callback(
    [Output("nav-teams", "className"),
     Output("nav-map", "className"),
     Output("nav-events", "className")],
    [Input("url", "pathname")]
)
def update_nav_active_state(pathname):
    # Default class for all nav links
    default_class = "custom-navlink"
    active_class = "custom-navlink nav-active"
    
    # Determine which page is active based on pathname
    teams_active = active_class if pathname and pathname.startswith("/teams") else default_class
    map_active = active_class if pathname and pathname.startswith("/map") else default_class
    events_active = active_class if pathname and pathname.startswith("/events") else default_class
    
    return teams_active, map_active, events_active

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    path_parts = pathname.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "team":
        team_number = path_parts[1]
        # If the third part is 'history', show history (year=None)
        if len(path_parts) > 2 and path_parts[2].lower() == "history":
            # Use global data for history
            return team_layout(team_number, None, TEAM_DATABASE, EVENT_DATABASE, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS, EVENT_TEAMS)
        # If a year is specified and it's not current_year, load that year's data
        year = path_parts[2] if len(path_parts) > 2 else str(current_year)
        if year and year != str(current_year):
            try:
                year = int(year)
                if year != current_year:
                    # Load data for the specific year
                    year_team_data, year_event_data, year_event_teams, year_event_rankings, year_event_awards, year_event_matches = load_year_data(year)
                    # Create year-specific databases
                    year_team_database = {year: year_team_data}
                    year_event_database = {year: year_event_data}
                    return team_layout(
                        team_number, year, 
                        year_team_database, year_event_database, 
                        year_event_matches, year_event_awards, 
                        year_event_rankings, year_event_teams
                    )
            except (ValueError, TypeError):
                # If year parsing fails, fall back to current year
                pass
        # Default: show current year
        return team_layout(team_number, current_year, TEAM_DATABASE, EVENT_DATABASE, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS, EVENT_TEAMS)
    
    if pathname.startswith("/event/"):
        event_key = pathname.split("/")[-1]
        return event_layout(event_key)
    
    if pathname == "/teams":
        return teams_layout()
    
    if pathname == "/map":
        return teams_map_layout()
    
    if pathname == "/events":
        return events_layout()
    
    if pathname == "/blog":
        return blog_layout

    if pathname == "/login":
        return login_layout()

    if pathname == "/user":
        return html.Div([
                    dcc.Store(id="favorites-store", data={"deleted": []}),
                    dcc.Store(id="user-session", data={"user_id": session.get("user_id")}),
                    html.Div(id="user-layout-wrapper", children=user_profile_layout())
                ])
    
    if pathname == "/insights":
        return insights_layout()
    
    if pathname.startswith("/insights/"):
        year = pathname.split("/")[-1]
        try:
            year = int(year)
        except ValueError:
            year = None
        return insights_details_layout(year)

    if len(path_parts) == 2 and path_parts[0] == "user":
        try:
            username = pathname.split("/user/")[1]
            # URL decode the username to handle spaces and special characters
            username = unquote(username)
            return user_profile_layout(username=username)
        except ValueError:
            pass
    
    if pathname.startswith("/compare"):
        return compare_layout()

    if pathname.startswith("/match/"):
        # /match/<event_key>/<match_key>
        parts = pathname.split("/")
        if len(parts) >= 4:
            event_key = parts[2]
            match_key = parts[3]
            return match_layout(event_key, match_key)
        else:
            return dbc.Alert("Invalid match URL.", color="danger")

    return home_layout

@app.callback(
    Output('tab-title', 'data'),
    Input('url', 'pathname'),
)
def update_tab_title(pathname):
    if pathname.startswith('/team/'):
        team_number = pathname.split('/team/')[1].split('/')[0]
        return f'Team {team_number} - Peekorobo'
    elif pathname.startswith('/teams'):
        return 'Teams - Peekorobo'
    elif pathname.startswith('/event/'):
        event_key = pathname.split('/event/')[-1].split('/')[0]
        return f'{event_key} - Peekorobo'
    elif pathname.startswith('/events'):
        return 'Events - Peekorobo'
    elif pathname.startswith('/map'):
        return 'Map - Peekorobo'
    elif pathname.startswith('/compare'):
        return 'Compare - Peekorobo'
    elif pathname.startswith('/blog'):
        return 'Blog - Peekorobo'
    else:
        return 'Peekorobo'

app.clientside_callback(
    """
    function(title) {
        document.title = title;
        return '';
    }
    """,
    Output('dummy-output', 'children'),
    Input('tab-title', 'data')
)

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

@app.callback(
    [Output("desktop-search-preview", "children"), Output("desktop-search-preview", "style"),
     Output("mobile-search-preview", "children"), Output("mobile-search-preview", "style")],
    [Input("desktop-search-input", "value"), Input("mobile-search-input", "value")],
    [State("theme-store", "data")] # Add theme state
)
def update_search_preview(desktop_value, mobile_value, current_theme):
    desktop_value = (desktop_value or "").strip().lower()
    mobile_value = (mobile_value or "").strip().lower()

    # Use search-specific data: current year teams and all events
    teams_data = list(SEARCH_TEAM_DATA[current_year].values())
    events_data = [ev for year_dict in SEARCH_EVENT_DATA.values() for ev in year_dict.values()]

    def get_children_and_style(val):
        if not val:
            return [], {"display": "none"}

                # --- Filter Users from PostgreSQL ---
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT username, avatar_key FROM users WHERE username ILIKE %s LIMIT 10", (f"%{val}%",))
                user_rows = cur.fetchall()
        except Exception as e:
            user_rows = []

        # --- Filter Teams ---
        filtered_teams = [
            t for t in teams_data
            if val in str(t.get("team_number", "")).lower()
            or val in (t.get("nickname", "") or "").lower()
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
                key=lambda t: len(set(val) & set((t.get("nickname", "") or "").lower())),
                default=None,
            )

        # --- Filter Events (simplified) ---
        filtered_events = []
        search_terms = val.split()
        
        for e in events_data:
            event_key = (e.get("k") or "").lower()
            event_name = (e.get("n") or "").lower()
            
            # Create a combined string for searching
            searchable_text = f"{event_key} {event_name}".lower()

            # Check if all search terms are present in the searchable text
            if all(term in searchable_text for term in search_terms):
                filtered_events.append(e)
        
        # Sort events by key (newest first since keys are chronological)
        filtered_events.sort(key=lambda x: x.get("k", ""), reverse=True)

        closest_event = None
        if filtered_events:
            closest_event = max(
                filtered_events,
                key=lambda e: (
                    len(set(val) & set((e.get("k") or "").lower())) +
                    len(set(val) & set((e.get("n") or "").lower()))
                )
            )

        children = []

        # Determine default text color based on theme
        default_text_color = "white" if current_theme == "dark" else "black"

        # Teams section
        if filtered_teams:
            children.append(
                dbc.Row(
                    dbc.Col(
                        html.Div("Teams", style={"fontWeight": "bold", "padding": "5px"}),
                    ),
                    style={"backgroundColor": "var(--card-bg)"}
                )
            )
            for team in filtered_teams:
                tn = team.get("team_number", "???")
                nm = team.get("nickname", "")
                last_year = team.get("last_year", None)
                background_color = "var(--card-bg)"
                is_highlighted = False
                if (closest_team_number and tn == closest_team_number["team_number"]) or \
                   (closest_team_nickname and nm == closest_team_nickname["nickname"]):
                    background_color = "#FFDD0080"
                    is_highlighted = True

                # Use last_year for the link, fallback to current_year if missing
                year_for_link = last_year if last_year is not None else current_year

                team_link_element = html.A([
                    html.Img(src=get_team_avatar(tn), style={
                        "height": "20px", "width": "20px", "borderRadius": "50%", "marginRight": "8px"
                    }),
                    html.Span(f"{tn} | {nm}")
                ], href=f"/team/{tn}/{year_for_link}", style={
                    "textDecoration": "none",
                    "color": "black" if is_highlighted else default_text_color
                })

                row_el = dbc.Row(
                    dbc.Col(team_link_element),
                    style={
                        "padding": "5px",
                        "backgroundColor": background_color,
                    },
                )

                children.append(row_el)

        # Events section
        if filtered_events:
            children.append(
                dbc.Row(
                    dbc.Col(
                        html.Div("Events", style={"fontWeight": "bold", "padding": "5px"}),
                    ),
                    style={"backgroundColor": "var(--card-bg)", "marginTop": "5px"}
                )
            )
            for evt in filtered_events:
                event_key = evt.get("k", "???")
                e_name = evt.get("n", "")
                e_year = event_key[:4] if len(event_key) >= 4 else ""
                background_color = "var(--card-bg)"

                if closest_event and event_key == closest_event.get("k"):
                    background_color = "#FFDD0080"

                display_text = f"{event_key} | {e_year} {e_name}"
                row_el = dbc.Row(
                    dbc.Col(
                        html.A(
                            display_text,
                            href=f"/event/{event_key}",
                            style={
                                "lineHeight": "20px",
                                "textDecoration": "none",
                                "color": "black" if background_color == "#FFDD00" else default_text_color,
                            },
                        ),
                        width=True,
                    ),
                    style={
                        "padding": "5px",
                        "backgroundColor": background_color
                    },
                )
                children.append(row_el)

        # Users section
        if user_rows:
            children.append(
                dbc.Row(
                    dbc.Col(
                        html.Div("Users", style={"fontWeight": "bold", "padding": "5px"}),
                    ),
                    style={"backgroundColor": "var(--card-bg)", "marginTop": "5px"}
                )
            )
            for username, avatar_key in user_rows:
                avatar_src = f"/assets/avatars/{avatar_key or 'stock'}"
                row_el = dbc.Row(
                    dbc.Col(
                        html.A([
                            html.Img(src=avatar_src, style={"height": "20px", "width": "20px", "borderRadius": "50%", "marginRight": "8px"}),
                            username
                        ], href=f"/user/{username}", style={
                            "textDecoration": "none",
                            "color": default_text_color
                            }),
                    ),
                    style={"padding": "5px", "backgroundColor": "transparent"},
                )
                children.append(row_el)


        if not filtered_teams and not filtered_events:
            children.append(html.Div("No results found.", style={"padding": "5px", "color": "#555"}))

        style_dict = {
            "display": "block",
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text-primary)",
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

# Callback to update account link based on login status
@app.callback(
    Output("account-link", "href"),
    Input("user-session", "data")
)
def update_account_link(session_data):
    if session_data and session_data.get("user_id"):
        return "/user/"
    else:
        return "/login"

@app.callback(
    Output("followers-hidden", "style"),
    Input("followers-see-more", "n_clicks"),
    prevent_initial_call=True
)
def toggle_followers_list(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

@app.callback(
    Output("following-hidden", "style"),
    Input("following-see-more", "n_clicks"),
    prevent_initial_call=True
)
def toggle_following_list(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

# New callbacks for dynamic user-specific IDs
@app.callback(
    Output({"type": "followers-hidden", "username": MATCH}, "style"),
    Input({"type": "followers-see-more", "username": MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def toggle_followers_list_dynamic(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

@app.callback(
    Output({"type": "following-hidden", "username": MATCH}, "style"),
    Input({"type": "following-see-more", "username": MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def toggle_following_list_dynamic(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

@app.server.route("/logout")
def logout():
    flask.session.clear()
    return flask.redirect("/login")

@app.callback(
    Output("current-color-display", "children"),
    Output("current-color-display", "style"),
    Input("edit-bg-color", "value")
)
def update_color_display(color_value):
    if not color_value:
        color_value = "#f9f9f9"
    
    return color_value, {
        "fontSize": "0.7rem",
        "color": "#fff",
        "fontFamily": "monospace",
        "backgroundColor": color_value,
        "padding": "2px 6px",
        "borderRadius": "3px",
        "border": "1px solid #666"
    }

@app.callback(
    Output("profile-display", "hidden"),
    Output("profile-card", "style"),
    Output("profile-edit-form", "hidden"),
    Output("save-profile-btn", "style"),
    Output("edit-profile-btn", "style"),
    Output("logout-btn", "style"),
    Output("user-search-input", "style"),
    Output("edit-profile-btn", "n_clicks"),
    Output("user-avatar-img", "src"),
    Output("profile-role", "children"),
    Output("profile-team", "children"),
    Output("profile-bio", "children"),
    Output("profile-header", "style"),
    Output("profile-subheader", "style"),
    Output("profile-search-header", "style"),
    Output("profile-followers", "style"),
    Output("profile-following", "style"),
    Output("profile-followers", "children"),  # added to dynamically update count text
    Input("edit-profile-btn", "n_clicks"),
    Input("save-profile-btn", "n_clicks"),
    State("profile-edit-form", "hidden"),
    State("edit-username", "value"),
    State("edit-bg-color", "value"),
    State("edit-role", "value"),
    State("edit-team", "value"),
    State("edit-bio", "value"),
    State("edit-avatar-key", "value"),
    State("user-session", "data")
)
def handle_profile_edit(
    edit_clicks, save_clicks, editing_hidden,
    username, color, role, team, bio, avatar_key_selected,
    session_data
):
    triggered_id = ctx.triggered_id
    if not triggered_id:
        return [dash.no_update] * 18

    user_id = session_data if isinstance(session_data, str) else session_data.get("user_id") if session_data else None
    if not user_id:
        return [dash.no_update] * 18

    # Handle color picker format (direct hex string)
    if not color:
        color = "#f9f9f9"

    if triggered_id == "save-profile-btn":
        if not username or len(username.strip()) < 3:
            return [dash.no_update] * 18

        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                cur.execute("SELECT id FROM users WHERE LOWER(username) = %s AND id != %s", (username.lower(), user_id))
                if cur.fetchone():
                    return [dash.no_update] * 18

                cur.execute("""
                    UPDATE users
                    SET username = %s,
                        role = %s,
                        team = %s,
                        bio = %s,
                        avatar_key = %s,
                        color = %s
                    WHERE id = %s
                """, (username, role, team, bio, avatar_key_selected, color, user_id))
                conn.commit()

                cur.execute("SELECT role, team, bio, color, followers FROM users WHERE id = %s", (user_id,))
                new_role, new_team, new_bio, new_color, followers_json = cur.fetchone()
                followers_count = len(followers_json) if followers_json else 0
                text_color = get_contrast_text_color(new_color)

        except Exception as e:
            new_role, new_team, new_bio, new_color = role, team, bio, color
            followers_count = 0
            text_color = get_contrast_text_color(color)

        return (
            False,  # show profile-display
            {
                "backgroundColor": new_color or "transparent",
                "color": text_color,
                "borderRadius": "10px",
                "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                "marginBottom": "20px"
            },
            True,  # hide profile-edit-form
            {"display": "none"},
            {
                "backgroundColor": "#2D2D2D",
                "border": "0px solid #000000",
                "borderRadius": "4px",
                "padding": "6px 12px",
                "color": "#ffffff",
                "fontWeight": "600",
                "fontSize": "0.85rem",
                "textDecoration": "none",
                "cursor": "pointer",
                "display": "inline-block"
            },  # show edit-profile-btn
            {
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
            },  # show logout-btn
            {
                "width": "100%", 
                "maxWidth": "300px",
                "display": "block"
            },  # show search bar
            0,
            get_user_avatar(avatar_key_selected),
            html.Span(f"Role: {new_role}", style={"color": text_color}),
            html.Span([
                html.Span("Team: ", style={"color": text_color, "fontWeight": "500"}),
                html.A(new_team, href=f"/team/{new_team}/{current_year}", style={"color": text_color, "textDecoration": "underline"})
            ]),
            html.Div(new_bio, style={"color": text_color}),
            {"color": text_color},  # profile-header
            {"color": text_color},  # profile-subheader
            {"color": text_color},  # profile-search-header
            {"color": text_color, "fontWeight": "500"},  # profile-followers style
            {"color": text_color, "fontWeight": "500"},  # profile-following style
            f"Followers: {followers_count}",  # profile-followers children
        )

    elif triggered_id == "edit-profile-btn":
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT color, followers FROM users WHERE id = %s", (user_id,))
                result = cur.fetchone()
                saved_color = result[0] if result else "#f9f9f9"
                followers_json = result[1] if result else []
                followers_count = len(followers_json) if followers_json else 0
                text_color = get_contrast_text_color(saved_color)
        except Exception as e:
            saved_color = "#f9f9f9"
            text_color = "#000"
            followers_count = 0

        return (
            True,  # show edit form
            {
                "backgroundColor": saved_color,
                "color": "#333",
                "borderRadius": "10px",
                "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                "marginBottom": "20px"
            },
            False,  # hide profile display
            {"display": "inline-block"},
            {"display": "none"},  # hide edit-profile-btn
            {"display": "none"},  # hide logout-btn
            {"display": "none"},  # hide search bar
            dash.no_update,
            dash.no_update,  # user-avatar-img.src
            html.Span(f"Role: {role}", style={"color": text_color}),
            html.Span([
                "Team: ",
                html.A(team, href=f"/team/{team}/{current_year}", style={"color": text_color, "textDecoration": "underline"})
            ]),
            html.Div(bio, style={"color": text_color}),
            {"color": text_color},  # profile-header
            {"color": text_color},  # profile-subheader
            {"color": text_color},  # profile-search-header
            {"color": text_color, "fontWeight": "500"},  # profile-followers style
            {"color": text_color, "fontWeight": "500"},  # profile-following style
            f"Followers: {followers_count}",  # profile-followers children
        )

    return [dash.no_update] * 18
    
@app.callback(
    Output({"type": "follow-user", "user_id": MATCH}, "children"),
    Input({"type": "follow-user", "user_id": MATCH}, "n_clicks"),
    State("user-session", "data"),
    State({"type": "follow-user", "user_id": MATCH}, "children"),
    prevent_initial_call=True
)
def toggle_follow_user(_, session_data, current_text):
    follower_id = session_data.get("user_id")
    followee_id = ctx.triggered_id["user_id"]

    if follower_id == followee_id:
        return dash.no_update

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()

            # Get followers for followee
            cur.execute("SELECT followers FROM users WHERE id = %s", (followee_id,))
            followers = cur.fetchone()[0] or []
            if isinstance(followers, str):
                followers = json.loads(followers)

            # Get following for follower
            cur.execute("SELECT following FROM users WHERE id = %s", (follower_id,))
            following = cur.fetchone()[0] or []
            if isinstance(following, str):
                following = json.loads(following)

            followers = set(followers)
            following = set(following)

            if current_text == "Follow":
                followers.add(follower_id)
                following.add(followee_id)
                new_label = "Unfollow"
            else:
                followers.discard(follower_id)
                following.discard(followee_id)
                new_label = "Follow"

            # Update both sides
            cur.execute("UPDATE users SET followers = %s WHERE id = %s", (json.dumps(list(followers)), followee_id))
            cur.execute("UPDATE users SET following = %s WHERE id = %s", (json.dumps(list(following)), follower_id))

            conn.commit()
            return new_label

    except Exception as e:
        return current_text

@app.callback(
    Output("user-search-results", "children"),
    Input("user-search-input", "value"),
    State("user-session", "data")
)
def search_users(query, session_data):
    if not query or not session_data:
        print("No query or session data, returning empty")
        return []
    
    return search_users_common(query, session_data)

def search_users_common(query, session_data):

    current_user_id = session_data.get("user_id")
    
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT id, username, avatar_key, followers
                FROM users
                WHERE username ILIKE %s AND id != %s
                LIMIT 10
            """, (f"%{query}%", current_user_id))
            rows = cur.fetchall()
            
        user_blocks = []
        for uid, username, avatar_key, followers in rows:
            # Handle followers field - it might be JSON string, list, or None
            try:
                if isinstance(followers, str):
                    followers_list = json.loads(followers)
                elif isinstance(followers, list):
                    followers_list = followers
                else:
                    followers_list = []
            except (json.JSONDecodeError, TypeError):
                followers_list = []
            
            is_following = current_user_id in followers_list
            avatar_src = get_user_avatar(avatar_key or "stock")

            user_blocks.append(html.Div([
                html.Img(src=avatar_src, style={
                    "height": "32px", "width": "32px", "borderRadius": "50%", "marginRight": "8px"
                }),
                html.A(username, href=f"/user/{quote(username)}", style={
                    "fontWeight": "bold", "textDecoration": "none", "color": "#ffffff", "flexGrow": "1"
                }),
                html.Button(
                    "Unfollow" if is_following else "Follow",
                    id={"type": "follow-user", "user_id": uid},
                    style={
                        "backgroundColor": "white",
                        "border": "1px solid #ccc",
                        "borderRadius": "12px",
                        "padding": "4px 10px",
                        "fontSize": "0.85rem",
                        "fontWeight": "500",
                        "color": "#333",
                        "cursor": "pointer",
                        "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
                        "transition": "all 0.2s ease-in-out"
                    }
                ),
            ], style={
                "display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "8px"
            }))

        # Wrap the user blocks in a container with overlay styling
        result_div = html.Div(user_blocks, style={
            "position": "absolute",
            "top": "100%",
            "left": "0",
            "width": "300px",
            "backgroundColor": "var(--card-bg)",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
            "maxHeight": "300px",
            "overflowY": "auto",
            "zIndex": "9999",
            "marginTop": "5px"
        })
        return result_div

    except Exception as e:
        print(f"Error in user search: {e}")
        return []

@app.callback(
    Output("favorites-store", "data"),
    Output("user-layout-wrapper", "children"),
    Input({"type": "delete-favorite", "item_type": ALL, "key": ALL}, "n_clicks"),
    State("favorites-store", "data"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def remove_favorite(n_clicks, store_data, session_data):
    if not ctx.triggered_id or not session_data:
        return no_update, no_update

    item_type = ctx.triggered_id["item_type"]
    item_key = ctx.triggered_id["key"]
    user_id = session_data.get("user_id")

    # Delete from database
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_items WHERE user_id = %s AND item_type = %s AND item_key = %s",
                (user_id, item_type, item_key)
            )
            conn.commit()

        # Update favorites store
        store_data = store_data or {"deleted": []}
        deleted = set(tuple(i) for i in store_data.get("deleted", []))
        deleted.add((item_type, item_key))
        new_store = {"deleted": list(deleted)}

        # Rerender layout
        return new_store, user_profile_layout(_user_id=user_id, deleted_items=deleted)
    except Exception as e:
        return dash.no_update, dash.no_update

@app.callback(
    Output("login-message", "children"),
    Output("login-redirect", "href"),
    Input("login-btn", "n_clicks"),
    Input("register-btn", "n_clicks"),
    State("username", "value"),
    State("password", "value"),
    prevent_initial_call=True
)
def handle_login(login_clicks, register_clicks, username, password):
    ctx = dash.callback_context

    if not ctx.triggered or not username or not password:
        return "Please enter both username and password.", dash.no_update

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "login-btn":
        valid, user_id = verify_user(username, password)
        if valid:
            session["user_id"] = user_id
            session["username"] = username
            redirect_url = "/user"
            return f"✅ Welcome, {username}!", redirect_url
        else:
            return "❌ Invalid username or password.", dash.no_update

    elif button_id == "register-btn":
        success, message = register_user(username.strip(), password.strip())
        if success:
            # Auto-login after registration
            try:
                with DatabaseConnection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username.strip(),))
                    user_id = cursor.fetchone()[0]
                session["user_id"] = user_id
                session["username"] = username.strip()
                redirect_url = "/user"
                return f"✅ Welcome, {username.strip()}!", redirect_url
            except Exception as e:
                return "Registration successful but login failed. Please try logging in.", dash.no_update
        else:
            return message, dash.no_update

@app.callback(
    Output("favorite-alert", "children"),
    Output("favorite-alert", "is_open"),
    Input("favorite-team-btn", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True
)
def save_favorite_team(n_clicks, pathname):

    if "user_id" not in session:
        return "You must be logged in.", True

    user_id = session["user_id"]

    # Extract team number from URL: e.g. "/team/1912"
    if pathname.startswith("/team/"):
        team_key = pathname.split("/team/")[1].split("/")[0]
    else:
        return "Invalid team path.", True

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()

            # Avoid duplicates
            cursor.execute("""
                SELECT id FROM saved_items
                WHERE user_id = %s AND item_type = 'team' AND item_key = %s
            """, (user_id, team_key))
            if cursor.fetchone():
                return "Team already favorited.", True

            cursor.execute("""
                INSERT INTO saved_items (user_id, item_type, item_key)
                VALUES (%s, 'team', %s)
            """, (user_id, team_key))
            conn.commit()

        return "Team favorited successfully!", True
    except Exception as e:
        return "Error favoriting team.", True

@app.callback(
    [
        Output("events-tab-content", "children"),
        Output("district-dropdown", "options"),
        Output("sort-direction-toggle", "children"),
    ],
    [
        Input("events-tabs", "active_tab"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("week-dropdown", "value"),
        Input("search-input", "value"),
        Input("district-dropdown", "value"),
        Input("sort-mode-toggle", "value"),
        Input("sort-direction-toggle", "n_clicks"),
        Input("event-favorites-store", "data"),
    ],
    suppress_callback_exceptions=True,
)
def update_events_tab_content(
    active_tab,
    selected_year,
    selected_event_types,
    selected_week,
    search_query,
    selected_district,
    sort_mode,
    sort_direction_clicks,
    store_data,
):
    user_favorites = set(store_data or [])
    
    # Load data for the selected year
    if selected_year == current_year:
        # Use global data for the current year
        events_data = list(EVENT_DATABASE.get(selected_year, {}).values())
        year_event_teams = EVENT_TEAMS.get(selected_year, {})
        year_team_database = TEAM_DATABASE
    else:
        # Load data for other years on-demand
        try:
            year_team_data, year_event_data, year_event_teams, _, _, _ = load_year_data(selected_year)
            events_data = list(year_event_data.values())
            year_team_database = {selected_year: year_team_data}
        except Exception as e:
            return html.Div(f"Error loading data for year {selected_year}: {str(e)}"), []
    
    if not events_data:
        return html.Div("No events available."), []

    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    def get_event_district(event):
        """Get district for an event based on its location using DISTRICT_STATES mapping"""
        state = event.get("s", "")  # State/province
        country = event.get("co", "")  # Country
        city = event.get("c", "")  # City
        
        # Special cases for non-US districts
        if country == "Israel":
            return "ISR"
        if country == "Canada":
            return "ONT"
        
        # Check US states against DISTRICT_STATES
        for district_acronym, states in DISTRICT_STATES_COMBINED.items():
            if state in states.get('abbreviations', []):
                # Special handling for FMA district - exclude western Pennsylvania cities
                if district_acronym == "FMA" and is_western_pennsylvania_city(city):
                    return None  # Not in FMA district
                return district_acronym
        
        return None

    # Get all unique districts from events
    district_keys = sorted(set(
        get_event_district(ev) for ev in events_data
        if get_event_district(ev) is not None
    ))

    district_options = [{"label": "All", "value": "all"}] + [
        {"label": dk, "value": dk} for dk in district_keys if dk
    ]

    if selected_district and selected_district != "all":
        events_data = [
            ev for ev in events_data
            if get_event_district(ev) == selected_district
        ]

    # Only filter if user has selected one or more event types
    if selected_event_types:
        events_data = [ev for ev in events_data if ev.get("et") in selected_event_types]

    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    def compute_event_insights_from_data(EVENT_TEAMS, EVENT_DATABASE, TEAM_DATABASE, selected_year, filtered_event_keys=None):
        rows = []
    
        teams_by_event = EVENT_TEAMS
        events = EVENT_DATABASE
    
        for event_key, team_entries in teams_by_event.items():
            if filtered_event_keys and event_key not in filtered_event_keys:
                continue
    
            event = events.get(selected_year, {}).get(event_key)
            if not event:
                continue
    
            full_name = event.get("n", "")
            # Remove ' presented by' and everything after it
            if " presented by" in full_name:
                full_name = full_name.split(" presented by")[0]
            name = full_name.split(" presented by")[0].strip()

            # --- Week Calculation ---
            try:
                start_date = datetime.strptime(event.get("sd", ""), "%Y-%m-%d").date()
                week_idx = get_week_number(start_date)
                if week_idx is not None:
                    week = f"{week_idx+1}"  # FRC weeks are 1-based
                else:
                    week = "N/A"
            except Exception:
                week = "N/A"

            # --- District Calculation ---
            district = get_event_district(event) or ""
            state = event.get("s", "")
            country = event.get("co", "")
            location = ", ".join([v for v in [state, country] if v])
    
            epa_values = []
            for t in team_entries:
                team_number = t["tk"]
                team_data = TEAM_DATABASE.get(selected_year, {}).get(team_number)
                if team_data and team_data.get("epa") is not None:
                    epa_values.append(team_data["epa"])
    
            if not epa_values:
                continue
    
            epa_values.sort(reverse=True)
            max_epa = max(epa_values)
            top_8 = np.mean(epa_values[:8]) if len(epa_values) >= 8 else np.mean(epa_values)
            top_24 = np.mean(epa_values[:24]) if len(epa_values) >= 24 else np.mean(epa_values)
            mean_epa = np.median(epa_values)

            # Tooltip with truncated name and markdown link
            truncated = truncate_name(name)
            # Markdown link with tooltip using title attribute
            markdown_link = f'[{truncated}](/event/{event_key} "{name}")'
    
            rows.append({
                "Name": markdown_link,
                "Week": week,
                "District": district,
                "Location": location,
                "Event Type": event.get("et", "N/A"),
                "Max ACE": round(max_epa, 2),
                "Top 8 ACE": round(top_8, 2),
                "Top 24 ACE": round(top_24, 2),
            })
    
        return pd.DataFrame(rows).sort_values(by="Top 8 ACE", ascending=False)
    

    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("sd", "1900-01-01"))
        ev["_end_date_obj"] = parse_date(ev.get("ed", "1900-01-01"))
        ev["w"] = get_week_number(ev["_start_date_obj"])

    if selected_week != "all":
        events_data = [ev for ev in events_data if ev.get("w") == selected_week]

    if search_query:
        q = search_query.lower()
        events_data = [
            ev for ev in events_data
            if q in ev.get("n", "").lower() or q in ev.get("c", "").lower()
        ]

    # Determine sort direction based on button clicks
    is_reverse = (sort_direction_clicks or 0) % 2 == 1
    
    # Apply sorting with direction
    if sort_mode == "time":
        events_data.sort(key=lambda x: x["_start_date_obj"], reverse=is_reverse)
    elif sort_mode == "alpha":
        events_data.sort(key=lambda x: x.get("n", "").lower(), reverse=is_reverse)

    if active_tab == "table-tab":
        # Create year-specific databases for the compute function
        year_event_database = {selected_year: {ev["k"]: ev for ev in events_data}}
        df = compute_event_insights_from_data(year_event_teams, year_event_database, year_team_database, selected_year)
    
        # Sort by "Top 8 ACE"
        df = df.sort_values(by="Top 8 ACE", ascending=False).reset_index(drop=True)
    
        # Use standard EPA styling for the ACE columns
        ace_values = df["Top 8 ACE"].dropna().values
        percentiles_dict = {
            "Top 8 ACE": compute_percentiles(ace_values),
            "Max ACE": compute_percentiles(df["Max ACE"].dropna().values),
            "Top 24 ACE": compute_percentiles(df["Top 24 ACE"].dropna().values),
        }
        style_data_conditional = get_epa_styling(percentiles_dict)

        # Create export dropdown buttons for event insights table
        event_export_dropdown = dbc.DropdownMenu(
            label="Export",
            color="primary",
            className="me-2",
            children=[
                dbc.DropdownMenuItem("Export as CSV", id="event-export-csv-dropdown"),
                dbc.DropdownMenuItem("Export as TSV", id="event-export-tsv-dropdown"),
                dbc.DropdownMenuItem("Export as Excel", id="event-export-excel-dropdown"),
                dbc.DropdownMenuItem("Export as JSON", id="event-export-json-dropdown"),
                dbc.DropdownMenuItem("Export as HTML", id="event-export-html-dropdown"),
                dbc.DropdownMenuItem("Export as LaTeX", id="event-export-latex-dropdown"),
            ],
            toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
            style={"display": "inline-block"}
        )

        # Export container
        export_container = html.Div([
            event_export_dropdown,
            dcc.Download(id="download-event-insights-csv"),
            dcc.Download(id="download-event-insights-excel"),
            dcc.Download(id="download-event-insights-tsv"),
            dcc.Download(id="download-event-insights-json"),
            dcc.Download(id="download-event-insights-html"),
            dcc.Download(id="download-event-insights-latex"),
        ], style={"textAlign": "right", "marginBottom": "10px"})

        # Update direction button text
        direction_text = "▲" if is_reverse else "▼"
        
        return html.Div([
            ace_legend_layout(),
            export_container,
            dash_table.DataTable(
                id="event-insights-table",
                columns=[
                    {"name": "Name", "id": "Name", "presentation": "markdown"},
                    {"name": "Week", "id": "Week"},
                    {"name": "District", "id": "District"},
                    {"name": "Location", "id": "Location"},
                    {"name": "Event Type", "id": "Event Type"},
                    {"name": "Max ACE", "id": "Max ACE"},
                    {"name": "Top 8 ACE", "id": "Top 8 ACE"},
                    {"name": "Top 24 ACE", "id": "Top 24 ACE"},
                ],
                sort_action="native",
                sort_mode="multi",
                data=df.to_dict("records"),
                style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
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
                style_data_conditional=style_data_conditional,
                style_as_list_view=True,
            )
        ]), district_options, direction_text


    # Default: cards tab
    today = date.today()
    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    up_cards = [dbc.Col(event_card(ev, favorited=(ev["k"] in user_favorites)), width="auto") for ev in upcoming[:5]]

    ongoing_section = html.Div([
        html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
        dbc.Row([dbc.Col(event_card(ev, favorited=(ev["k"] in user_favorites)), width="auto") for ev in ongoing], className="justify-content-center"),
    ]) if ongoing else html.Div()

    all_event_cards = [event_card(ev, favorited=(ev["k"] in user_favorites)) for ev in events_data]

    # Conditionally render Upcoming Events section
    upcoming_section = html.Div([
        html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
        dbc.Row(up_cards, className="justify-content-center"),
    ]) if upcoming else html.Div()
    
    # All Events section
    all_events_section = html.Div([
        html.H3("All Events", className="mb-4 mt-4 text-center"),
        html.Div(all_event_cards, className="d-flex flex-wrap justify-content-center"),
    ]) if events_data else html.Div()
    
    # Update direction button text
    direction_text = "▲" if is_reverse else "▼"
    
    return html.Div([
        upcoming_section,
        html.Br(),
        ongoing_section,
        html.Br(),
        all_events_section,
    ]), district_options, direction_text

# Add a callback to set the event-tab-store from the URL's search string
@app.callback(
    Output("event-tab-store", "data"),
    Input("url", "search"),
)
def set_event_tab_from_url(search):
    if search and search.startswith("?"):
        params = parse_qs(search[1:])
        tab = params.get("tab", [None])[0]
        if tab in ["teams", "rankings", "matches", "sos", "compare", "alliances", "metrics"]:
            return tab
    return "teams"

# Add a callback to set the active_tab of event-data-tabs from event-tab-store
@app.callback(
    Output("event-data-tabs", "active_tab"),
    Input("event-tab-store", "data"),
)
def set_event_tabs_active_tab(tab):
    return tab

@app.callback(
    Output("data-display-container", "children"),
    Output("event-url", "search"),  # NEW: update the event tab URL
    Input("event-data-tabs", "active_tab"),
    State("store-rankings", "data"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-event-matches", "data"),
    State("store-event-year", "data"),
    State("url", "pathname"),  # get the event_key from the URL
    suppress_callback_exceptions=True,
)
def update_event_display(active_tab, rankings, epa_data, event_teams, event_matches, event_year, pathname):

    # --- URL update logic ---
    # Extract event_key from pathname
    event_key = None
    if pathname and "/event/" in pathname:
        event_key = pathname.split("/event/")[-1].split("/")[0]
    query_string = f"?tab={active_tab}" if active_tab and event_key else ""

    if not active_tab:
        return dbc.Alert("Select a data category above.", color="info"), query_string

    # === Shared styles ===
    common_style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none"}
    common_style_header={
        "backgroundColor": "var(--card-bg)",        # Match the table background
        "fontWeight": "bold",              # Keep column labels strong
        "textAlign": "center",
        "borderBottom": "1px solid #ccc",  # Thin line under header only
        "padding": "6px",                  # Reduce banner size
        "fontSize": "13px",                # Optional: shrink text slightly
    }

    common_style_cell={
        "backgroundColor": "var(--card-bg)", 
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }

    def safe_int(val):
        try: return int(val)
        except: return 999999

    # Load team data for the specific year
    if event_year == current_year:
        year_team_data = TEAM_DATABASE # Use global data for current year
        team_epas = []
        for tnum, team_data in TEAM_DATABASE.get(event_year, {}).items():
            if team_data:
                team_epas.append((tnum, team_data.get("epa", 0)))
    else:
        # Load data for other years on-demand
        try:
            year_team_data, _, _, _, _, _ = load_year_data(event_year)
            team_epas = []
            for tnum, team_data in year_team_data.items():
                if team_data:
                    team_epas.append((tnum, team_data.get("epa", 0)))
        except Exception as e:
            return dbc.Alert(f"Error loading team data for year {event_year}: {str(e)}", color="danger"), query_string
        
    # Sort by EPA to calculate ranks
    team_epas.sort(key=lambda x: x[1], reverse=True)
    rank_map = {tnum: i+1 for i, (tnum, _) in enumerate(team_epas)}

    # Get all EPA values for percentile calculations
    epa_values = [data.get("epa", 0) for data in epa_data.values()]
    confidence_values = [data.get("confidence", 0) for data in epa_data.values()]
    auto_values = [data.get("auto_epa", 0) for data in epa_data.values()]
    teleop_values = [data.get("teleop_epa", 0) for data in epa_data.values()]
    endgame_values = [data.get("endgame_epa", 0) for data in epa_data.values()]

    percentiles_dict = {
        "ACE": compute_percentiles(epa_values),
        "Confidence": compute_percentiles(confidence_values),
        "Auto": compute_percentiles(auto_values),
        "Teleop": compute_percentiles(teleop_values),
        "Endgame": compute_percentiles(endgame_values),
    }
        
    style_data_conditional = get_epa_styling(percentiles_dict)

    # === Rankings Tab ===
    if active_tab == "rankings":
        data_rows = []
        for team_num, rank_info in (rankings or {}).items():
            tstr = str(team_num)
            if event_year == current_year:
                team_data = year_team_data.get(current_year, {}).get(int(team_num), {})
            else:
                team_data = year_team_data.get(int(team_num), {})
            nickname = team_data.get("nickname", "Unknown")

            data_rows.append({
                "Rank": rank_info.get("rk", None),
                "Team": f"[{tstr} | {truncate_name(nickname)}](/team/{tstr}/{event_year})",
                "Wins": rank_info.get("w", None),
                "Losses": rank_info.get("l", None),
                "Ties": rank_info.get("t", None),
                "DQ": rank_info.get("dq", None),
                "ACE Rank": rank_map.get(int(tstr), None),
                "ACE": epa_data.get(tstr, {}).get("epa", None),
            })

        data_rows.sort(key=lambda r: safe_int(r["Rank"]))

        columns = [
            {"name": "Rank", "id": "Rank", "type": "numeric"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins", "type": "numeric"},
            {"name": "Losses", "id": "Losses", "type": "numeric"},
            {"name": "Ties", "id": "Ties", "type": "numeric"},
            {"name": "DQ", "id": "DQ", "type": "numeric"},
            {"name": "ACE Rank", "id": "ACE Rank", "type": "numeric"},
            {"name": "ACE", "id": "ACE", "type": "numeric"},
        ]

        return html.Div([
            ace_legend_layout(),
            dash_table.DataTable(
                columns=columns,
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                filter_options={"case": "insensitive"},
                data=data_rows,
                page_size=10,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_data_conditional=style_data_conditional,
                style_filter={
                    "backgroundColor": "var(--input-bg)",
                    "color": "var(--text-primary)",
                    "borderColor": "var(--input-border)",
                }
            )
        ]), query_string

    # === Teams Tab ===
    elif active_tab == "teams":

        if event_year != current_year:
            year_team_data = {event_year: year_team_data}
        
        # Add stats selector
        stats_selector = dbc.Row([
            dbc.Col([
                html.Label("Stats Type:", style={"fontWeight": "bold", "color": "var(--text-primary)", "marginRight": "10px"}),
                dcc.Dropdown(
                    id="event-teams-stats-selector",
                    options=[
                        {"label": "Overall Stats", "value": "overall"},
                        {"label": "Event Stats", "value": "event"}
                    ],
                    value="overall",
                    clearable=False,
                    style={"width": "200px"}
                )
            ], md=3, className="d-flex align-items-center"),
            dbc.Col([
                html.Div(id="event-teams-stats-display")
            ], md=9)
        ], className="mb-4 align-items-center", align="center")

        # Sort teams by overall EPA from year_team_database for spotlight cards
        sorted_teams = sorted(
            event_teams,
            key=lambda t: year_team_data.get(event_year, {}).get(int(t.get("tk")), {}).get("epa", 0),
            reverse=True
        )
        top_3 = sorted_teams[:3]

        spotlight_cards = [
            dbc.Col(create_team_card_spotlight(t, year_team_data, event_year), width="auto")
            for t in top_3
        ]

        return html.Div([
            stats_selector,
            html.Div(id="event-teams-spotlight"),
            ace_legend_layout(),
            html.Div(id="event-teams-stats-display")
        ]), query_string

    # === Matches Tab ===
    elif active_tab == "matches":
        team_filter_options = [
            {"label": f"{t['tk']} - {t.get('nn', '')}", "value": str(t["tk"])}
            for t in event_teams
        ]
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Label("Filter by Team:", style={"fontWeight": "bold", "color": "var(--text-primary)"}),
                    dcc.Dropdown(
                        id="team-filter",
                        options=[{"label": "All Teams", "value": "ALL"}] + team_filter_options,
                        value="ALL",
                        clearable=False
                    )
                ], md=4),
                dbc.Col([
                    html.Div([
                        html.Label("Table Style:", style={"fontWeight": "bold", "color": "var(--text-primary)", "marginRight": "18px"}),
                        dcc.RadioItems(
                            id="table-style-toggle",
                            options=[
                                {"label": "Both Alliances", "value": "both"},
                                {"label": "Team Focus", "value": "team"}
                            ],
                            value="both",
                            inline=True,
                            labelStyle={"marginRight": "15px", "color": "var(--text-primary)"}
                        )
                    ], style={"display": "flex", "alignItems": "center"})
                ], md=4),
                dbc.Col([
                    dbc.Button(
                        "Create Playlist ▶︎",
                        id="create-playlist-btn",
                        color="warning",
                        outline=True,
                        className="custom-view-btn w-100",
                        style={"marginTop": "10px"}
                    )
                ], md=4)
            ], className="mb-4 align-items-center", align="center"),
            html.Div(id="matches-container")
        ]), query_string

    # === Strength of Schedule (SoS) Tab ===
    elif active_tab == "sos":
        # Build a table of SoS metrics for each team
        # For each team, get their matches, compute average predicted opponent EPA, avg win prob, hardest/easiest match
        team_sos_rows = []
        team_numbers = [t["tk"] for t in event_teams]
        matches = [m for m in (event_matches or []) if m.get("cl") == "qm"]  # Only consider qualification matches
        # Build a lookup for team data
        team_lookup = {int(t["tk"]): t for t in event_teams}
        # For each team
        for team_num in team_numbers:
            team_num_int = int(team_num)
            # Find matches this team played
            team_matches = [m for m in matches if str(team_num) in m.get("rt", "").split(",") or str(team_num) in m.get("bt", "").split(",")]
            if not team_matches:
                continue
            opp_aces = []
            win_probs = []
            hardest = None
            easiest = None
            hardest_prob = 1.0
            easiest_prob = 0.0
            for m in team_matches:
                # Determine alliance
                if str(team_num) in m.get("rt", "").split(","):
                    alliance = "red"
                    opp_teams = [int(t) for t in m.get("bt", "").split(",") if t.strip().isdigit()]
                else:
                    alliance = "blue"
                    opp_teams = [int(t) for t in m.get("rt", "").split(",") if t.strip().isdigit()]
                # Opponent EPA
                opp_ace = 0
                opp_count = 0
                for opp in opp_teams:
                    opp_ace += epa_data.get(str(opp), {}).get("epa", 0)
                    opp_count += 1
                avg_opp_ace = opp_ace / opp_count if opp_count else 0
                opp_aces.append(avg_opp_ace)
                # Win probability (use adaptive prediction)
                red_info = [
                    {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                    for t in m.get("rt", "").split(",") if t.strip().isdigit()
                ]
                blue_info = [
                    {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                    for t in m.get("bt", "").split(",") if t.strip().isdigit()
                ]
                p_red, p_blue = predict_win_probability_adaptive(red_info, blue_info, m.get("ek", ""), m.get("k", ""))
                win_prob = p_red if alliance == "red" else p_blue
                win_probs.append(win_prob)
                if win_prob < hardest_prob:
                    hardest_prob = win_prob
                    hardest = m
                if win_prob > easiest_prob:
                    easiest_prob = win_prob
                    easiest = m
            avg_opp_ace = sum(opp_aces) / len(opp_aces) if opp_aces else 0
            avg_win_prob = sum(win_probs) / len(win_probs) if win_probs else 0
            sos_metric = avg_win_prob  # SoS: 0 = lose all, 1 = win all
            # Build row
            team_data = team_lookup.get(team_num_int, {})
            nickname = team_data.get("nn", "Unknown")
            def match_label(m):
                if not m: return None
                label = m.get("k", "").split("_", 1)[-1].upper()
                return f"[{label}](/match/{m.get('ek', '')}/{label})"
            team_sos_rows.append({
                "Team": f"[{team_num} | {truncate_name(nickname)}](/team/{team_num}/{event_year})",
                "SoS": sos_metric,
                "Avg Opponent ACE": avg_opp_ace,
                "Avg Win Prob": avg_win_prob,
                "Hardest Match": match_label(hardest),
                "Hardest Win Prob": hardest_prob,
                "Easiest Match": match_label(easiest),
                "Easiest Win Prob": easiest_prob,
                "# Matches": len(team_matches),
            })
        # Sort by SoS (ascending: hardest at bottom, easiest at top)
        team_sos_rows.sort(key=lambda r: r["SoS"], reverse=True)
        sos_columns = [
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "SoS", "id": "SoS", "type": "numeric"},
            {"name": "Avg Opponent ACE", "id": "Avg Opponent ACE", "type": "numeric"},
            {"name": "Avg Win Prob", "id": "Avg Win Prob", "type": "numeric"},
            {"name": "Hardest Match", "id": "Hardest Match", "presentation": "markdown"},
            {"name": "Hardest Win Prob", "id": "Hardest Win Prob", "type": "numeric"},
            {"name": "Easiest Match", "id": "Easiest Match", "presentation": "markdown"},
            {"name": "Easiest Win Prob", "id": "Easiest Win Prob", "type": "numeric"},
            {"name": "# Matches", "id": "# Matches", "type": "numeric"},
        ]
        return html.Div([
            html.H4("Strength of Schedule (SoS)", className="mb-3 mt-3"),
            dash_table.DataTable(
                columns=sos_columns,
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                filter_options={"case": "insensitive"},
                data=team_sos_rows,
                page_size=15,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_filter={
                    "backgroundColor": "var(--input-bg)",
                    "color": "var(--text-primary)",
                    "borderColor": "var(--input-border)",
                }
            )
        ]), query_string

    # === Compare Teams Tab ===
    elif active_tab == "compare":
        # Multi-select dropdown for teams
        team_options = [
            {"label": f"{t['tk']} - {t.get('nn', '')}", "value": str(t["tk"])}
            for t in event_teams
        ]
        # Default: top 2 teams by EPA
        sorted_teams = sorted(event_teams, key=lambda t: epa_data.get(str(t["tk"]), {}).get("epa", 0), reverse=True)
        default_team_values = [str(t["tk"]) for t in sorted_teams[:2]]
        # Use a Store to keep selection in sync
        compare_layout = html.Div([
            html.Label("Select Teams to Compare:", style={"fontWeight": "bold", "color": "var(--text-primary)", "marginBottom": "8px"}),
            dcc.Dropdown(
                id="compare-teams-dropdown",
                options=team_options,
                value=default_team_values,
                multi=True,
                placeholder="Select teams...",
                style={"marginBottom": "20px"}
            ),
            html.Div(id="compare-teams-table-container")
        ])
        return compare_layout, query_string

    if active_tab == "alliances":
        query_string = f"?tab=alliances"
        return "", query_string
    
    if active_tab == "metrics":
        query_string = f"?tab=metrics"
        return "", query_string

    return dbc.Alert("No data available.", color="warning"), query_string

@app.callback(
    [Output("event-teams-stats-display", "children"),
     Output("event-teams-spotlight", "children")],
    Input("event-teams-stats-selector", "value"),
    [
        State("store-event-epa", "data"),
        State("store-event-teams", "data"),
        State("store-event-matches", "data"),
        State("store-event-year", "data"),
        State("url", "pathname"),
    ],
    suppress_callback_exceptions=True,
)
def update_event_teams_stats_display(stats_type, epa_data, event_teams, event_matches, event_year, pathname):
    """Update the teams table and spotlight cards based on selected stats type (overall vs event-specific)"""
    
    if not stats_type or not event_teams:
        return "", ""
    
    # Extract event_key from pathname
    event_key = None
    if pathname and "/event/" in pathname:
        event_key = pathname.split("/event/")[-1].split("/")[0]
    
    if not event_key:
        return "", ""
    
    # Load team data for the specific year
    if event_year == current_year:
        year_team_data = TEAM_DATABASE
    else:
        try:
            year_team_data, _, _, _, _, _ = load_year_data(event_year)
        except Exception as e:
            error_alert = dbc.Alert(f"Error loading team data for year {event_year}: {str(e)}", color="danger")
            return error_alert, ""
    
    if event_year != current_year:
        year_team_data = {event_year: year_team_data}
    
    # Calculate ranks based on selected stats type
    if stats_type == "overall":
        # Use overall EPA for ranking
        team_epas = []
        for tnum, team_data in year_team_data.get(event_year, {}).items():
            if team_data:
                team_epas.append((tnum, team_data.get("epa", 0)))
        team_epas.sort(key=lambda x: x[1], reverse=True)
        rank_map = {tnum: i+1 for i, (tnum, _) in enumerate(team_epas)}
        
        # Sort teams by overall EPA for spotlight cards
        sorted_teams = sorted(
            event_teams,
            key=lambda t: year_team_data.get(event_year, {}).get(int(t.get("tk")), {}).get("epa", 0),
            reverse=True
        )
        
        # Build rows with overall stats
        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            team_data = year_team_data.get(event_year, {}).get(int(tnum), {})
            
            rows.append({
                "ACE Rank": rank_map.get(int(tnum), None),
                "EPA": team_data.get('normal_epa', 0),
                "Confidence": team_data.get('confidence', 0),
                "ACE": team_data.get('epa', 0),
                "Auto": team_data.get('auto_epa', 0),
                "Teleop": team_data.get('teleop_epa', 0),
                "Endgame": team_data.get('endgame_epa', 0),
                "Team": f"[{tstr} | {truncate_name(t.get('nn', 'Unknown'))}](/team/{tstr}/{event_year})",
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })
        
        # Sort by overall EPA value
        rows.sort(key=lambda r: r["ACE"] if r["ACE"] is not None else 0, reverse=True)
        
        # Use global percentiles for coloring
        if event_year == current_year:
            global_teams = TEAM_DATABASE.get(event_year, {}).values()
        else:
            global_teams = year_team_data.get(event_year, {}).values()
        global_epa_values = [t.get("epa", 0) for t in global_teams]
        global_confidence_values = [t.get("confidence", 0) for t in global_teams]
        global_auto_values = [t.get("auto_epa", 0) for t in global_teams]
        global_teleop_values = [t.get("teleop_epa", 0) for t in global_teams]
        global_endgame_values = [t.get("endgame_epa", 0) for t in global_teams]
        
    else:  # stats_type == "event"
        # Use event-specific EPA for ranking within the event
        event_epa_values = [data.get("epa", 0) for data in epa_data.values()]
        event_epa_values.sort(reverse=True)
        event_rank_map = {epa_val: i+1 for i, epa_val in enumerate(event_epa_values)}
        
        # Calculate overall ACE ranks using the full dataset
        overall_team_epas = []
        for tnum, team_data in year_team_data.get(event_year, {}).items():
            if team_data:
                overall_team_epas.append((tnum, team_data.get("epa", 0)))
        overall_team_epas.sort(key=lambda x: x[1], reverse=True)
        overall_rank_map = {tnum: i+1 for i, (tnum, _) in enumerate(overall_team_epas)}
        
        # Calculate SoS for each team using the same logic as the SoS tab
        team_numbers = [t["tk"] for t in event_teams]
        team_sos = {}
        
        if event_matches:
            # Only consider qualification matches for SoS
            qm_matches = [m for m in event_matches if m.get("cl") == "qm"]
            
            for team_num in team_numbers:
                team_num_str = str(team_num)
                # Find matches this team played
                team_matches = [m for m in qm_matches if team_num_str in m.get("rt", "").split(",") or team_num_str in m.get("bt", "").split(",")]
                if not team_matches:
                    team_sos[team_num] = 0
                    continue
                
                win_probs = []
                for m in team_matches:
                    # Determine alliance
                    if team_num_str in m.get("rt", "").split(","):
                        alliance = "red"
                        opp_teams = [int(t) for t in m.get("bt", "").split(",") if t.strip().isdigit()]
                    else:
                        alliance = "blue"
                        opp_teams = [int(t) for t in m.get("rt", "").split(",") if t.strip().isdigit()]
                    
                    # Win probability (use adaptive prediction)
                    red_info = [
                        {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                        for t in m.get("rt", "").split(",") if t.strip().isdigit()
                    ]
                    blue_info = [
                        {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                        for t in m.get("bt", "").split(",") if t.strip().isdigit()
                    ]
                    p_red, p_blue = predict_win_probability_adaptive(red_info, blue_info, m.get("ek", ""), m.get("k", ""))
                    win_prob = p_red if alliance == "red" else p_blue
                    win_probs.append(win_prob)
                
                avg_win_prob = sum(win_probs) / len(win_probs) if win_probs else 0
                team_sos[team_num] = avg_win_prob  # SoS: 0 = lose all, 1 = win all
        else:
            # Fallback to simplified calculation if no match data
            for team_num in team_numbers:
                team_sos[team_num] = 0.5  # Default to 50% win probability
        
        # Sort teams by event-specific EPA for spotlight cards
        sorted_teams = sorted(
            event_teams,
            key=lambda t: epa_data.get(str(t.get("tk")), {}).get("epa", 0),
            reverse=True
        )
        
        # Build rows with event-specific stats
        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            event_team_data = epa_data.get(tstr, {})
            
            # Find rank for this team's event EPA
            team_event_epa = event_team_data.get("epa", 0)
            event_rank = event_rank_map.get(team_event_epa, None)
            
            # Get overall ACE rank
            overall_ace_rank = overall_rank_map.get(int(tnum), None)
            
            # Get SoS
            sos_value = team_sos.get(tnum, 0)
            
            # Calculate ACE improvement from overall to event
            overall_team_data = year_team_data.get(event_year, {}).get(int(tnum), {})
            overall_ace = overall_team_data.get('epa', 0)
            event_ace = event_team_data.get('epa', 0)
            ace_improvement = event_ace - overall_ace
            
            rows.append({
                "Event Rank": event_rank,
                "ACE Rank": overall_ace_rank,
                "EPA": event_team_data.get('normal_epa', 0),
                "Confidence": event_team_data.get('confidence', 0),
                "ACE": event_team_data.get('epa', 0),
                "Auto": event_team_data.get('auto_epa', 0),
                "Teleop": event_team_data.get('teleop_epa', 0),
                "Endgame": event_team_data.get('endgame_epa', 0),
                "SoS": sos_value,
                "ACE Δ": ace_improvement,
                "Team": f"[{tstr} | {truncate_name(t.get('nn', 'Unknown'))}](/team/{tstr}/{event_year})",
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })
        
        # Sort by event EPA value
        rows.sort(key=lambda r: r["ACE"] if r["ACE"] is not None else 0, reverse=True)
        
        # Use event-specific percentiles for coloring
        event_confidence_values = [data.get("confidence", 0) for data in epa_data.values()]
        event_auto_values = [data.get("auto_epa", 0) for data in epa_data.values()]
        event_teleop_values = [data.get("teleop_epa", 0) for data in epa_data.values()]
        event_endgame_values = [data.get("endgame_epa", 0) for data in epa_data.values()]
        sos_values = list(team_sos.values())
        
        # Calculate ACE improvement values
        ace_improvement_values = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            event_team_data = epa_data.get(tstr, {})
            overall_team_data = year_team_data.get(event_year, {}).get(int(tnum), {})
            overall_ace = overall_team_data.get('epa', 0)
            event_ace = event_team_data.get('epa', 0)
            ace_improvement_values.append(event_ace - overall_ace)
        

        for t in event_teams:
            tnum = t.get("tk")
            sos_value = team_sos.get(tnum, 0)
            event_team_data = epa_data.get(str(tnum), {})

        
        global_epa_values = event_epa_values
        global_confidence_values = event_confidence_values
        global_auto_values = event_auto_values
        global_teleop_values = event_teleop_values
        global_endgame_values = event_endgame_values
    
    # Common styles
    common_style_table = {"overflowX": "auto", "borderRadius": "10px", "border": "none"}
    common_style_header = {
        "backgroundColor": "var(--card-bg)",
        "fontWeight": "bold",
        "textAlign": "center",
        "borderBottom": "1px solid #ccc",
        "padding": "6px",
        "fontSize": "13px",
    }
    common_style_cell = {
        "backgroundColor": "var(--card-bg)",
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }
    
    # Calculate percentiles for styling
    percentiles_dict = {
        "ACE": compute_percentiles(global_epa_values),
        "Auto": compute_percentiles(global_auto_values),
        "Teleop": compute_percentiles(global_teleop_values),
        "Endgame": compute_percentiles(global_endgame_values),
        "Confidence": compute_percentiles(global_confidence_values),
    }
    
    # Add additional percentiles for event stats
    if stats_type == "event":
        percentiles_dict["SoS"] = compute_percentiles(sos_values)
        percentiles_dict["ACE Δ"] = compute_percentiles(ace_improvement_values)
    style_data_conditional = get_epa_styling(percentiles_dict)
    
    # Define columns based on stats type
    if stats_type == "overall":
        columns = [
            {"name": "ACE Rank", "id": "ACE Rank", "type": "numeric"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "EPA", "id": "EPA", "type": "numeric"},
            {"name": "Confidence", "id": "Confidence", "type": "numeric"},
            {"name": "ACE", "id": "ACE", "type": "numeric"},
            {"name": "Auto", "id": "Auto", "type": "numeric"},
            {"name": "Teleop", "id": "Teleop", "type": "numeric"},
            {"name": "Endgame", "id": "Endgame", "type": "numeric"},
            {"name": "Location", "id": "Location"},
        ]
    else:  # event stats
        columns = [
            {"name": "Event Rank", "id": "Event Rank", "type": "numeric"},
            {"name": "ACE Rank", "id": "ACE Rank", "type": "numeric"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "EPA", "id": "EPA", "type": "numeric"},
            {"name": "Confidence", "id": "Confidence", "type": "numeric"},
            {"name": "ACE", "id": "ACE", "type": "numeric"},
            {"name": "Auto", "id": "Auto", "type": "numeric"},
            {"name": "Teleop", "id": "Teleop", "type": "numeric"},
            {"name": "Endgame", "id": "Endgame", "type": "numeric"},
            {"name": "SoS", "id": "SoS", "type": "numeric"},
            {"name": "ACE Δ", "id": "ACE Δ", "type": "numeric"},
            {"name": "Location", "id": "Location"},
        ]
    
    # Create spotlight cards based on selected stats type
    top_3 = sorted_teams[:3]
    
    if stats_type == "overall":
        # Use overall stats for spotlight cards
        spotlight_cards = [
            dbc.Col(create_team_card_spotlight(t, year_team_data, event_year), width="auto")
            for t in top_3
        ]
    else:
        # Use event-specific stats for spotlight cards
        spotlight_cards = []
        for t in top_3:
            tnum = t.get("tk")
            tstr = str(tnum)
            event_team_data = epa_data.get(tstr, {})
            
            spotlight_cards.append(
                dbc.Col(
                    create_team_card_spotlight_event(t, event_team_data, event_year, event_rank_map),
                    width="auto"
                )
            )
    
    spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")
    
    return dash_table.DataTable(
        columns=columns,
        sort_action="native",
        sort_mode="multi",
        filter_action="native",
        filter_options={"case": "insensitive"},
        data=rows,
        page_size=10,
        style_table=common_style_table,
        style_header=common_style_header,
        style_cell=common_style_cell,
        style_data_conditional=style_data_conditional,
        style_filter={
            "backgroundColor": "var(--input-bg)",
            "color": "var(--text-primary)",
            "borderColor": "var(--input-border)",
        }
    ), spotlight_layout

@app.callback(
    Output("matches-container", "children"),
    Input("team-filter", "value"),
    Input("table-style-toggle", "value"),
    [
        State("store-event-matches", "data"),
        State("store-event-epa", "data"),
        State("store-event-year", "data"),  # Add event year state
    ],
)
def update_matches_table(selected_team, table_style, event_matches, epa_data, event_year):
    event_matches = event_matches or []
    epa_data = epa_data or {}
    event_year = event_year or current_year  # Default fallback
    
    # 1) Filter by team number
    if selected_team and selected_team != "ALL":
        event_matches = [
            m for m in event_matches
            if selected_team in m.get("rt", "").split(",") or selected_team in m.get("bt", "").split(",")
        ] 

    def match_sort_key(m):
        # Use the match key (preferred in playoff)
        key = m.get("k", "").split("_", 1)[-1].lower()
    
        # Use regex to extract comp level, set number, and match number
        match_re = re.match(r"(qm|qf|sf|f)?(\d*)m(\d+)", key)
        if match_re:
            level_str, set_num_str, match_num_str = match_re.groups()
            level = {"qm": 0, "qf": 1, "sf": 2, "f": 3}.get(level_str, 99)
            set_num = int(set_num_str) if set_num_str.isdigit() else 0
            match_num = int(match_num_str)
            return (level, set_num, match_num)
        else:
            # Fallback if format is weird
            return (99, 99, 9999)
    

    event_matches.sort(key=match_sort_key)
    qual_matches = [m for m in event_matches if m.get("cl") == "qm"]
    playoff_matches = [m for m in event_matches if m.get("cl") != "qm"]

    # 3) Utility functions
    def format_teams_markdown(team_list_str):
        return ", ".join(f"[{t}](/team/{t}/{event_year})" for t in team_list_str.split(",") if t.strip().isdigit())

    def get_team_epa_info(t_key):
        info = epa_data.get(str(t_key.strip()), {})
        
        # If event_epa_data is missing or EPA is 0 (even if confidence exists), fallback to team database
        if not info or info.get("epa", 0) == 0:
            # Fallback to team database for the specific year
            if event_year == current_year:
                team_data = TEAM_DATABASE.get(event_year, {}).get(int(t_key), {})
            else:
                try:
                    year_team_data, _, _, _, _, _ = load_year_data(event_year)
                    team_data = year_team_data.get(int(t_key), {})
                except Exception:
                    team_data = {}
            return {
                "team_number": int(t_key.strip()),
                "epa": team_data.get("epa", 0),
                "confidence": team_data.get("confidence", 0.7),
            }
        # Use event-specific EPA data, but ensure confidence has a reasonable fallback
        return {
            "team_number": int(t_key.strip()),
            "epa": info.get("epa", 0),
            "confidence": info.get("confidence", 0.7),  # Use 0.7 as fallback instead of 0
        }
    
    def build_match_rows(matches, table_style="both"):
        rows = []
        for match in matches:
            red_str = match.get("rt", "")
            blue_str = match.get("bt", "")
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            if red_score <= 0 or blue_score <= 0:
                red_score = 0
                blue_score = 0
            winner = match.get("wa", "")
            label = match.get("k", "").split("_", 1)[-1]
            event_key = match.get("ek", "")  # Extract event_key early

            if label.lower().startswith("sf") and "m" in label.lower():
                label = label.lower().split("m")[0].upper()
            else:
                label = label.upper()
    
            red_info = [get_team_epa_info(t) for t in red_str.split(",") if t.strip().isdigit()]
            blue_info = [get_team_epa_info(t) for t in blue_str.split(",") if t.strip().isdigit()]

            # Use adaptive prediction that learns from previous matches
            p_red, p_blue = predict_win_probability_adaptive(red_info, blue_info, event_key, match.get("k", ""))
            
            # Learn from completed matches
            winner = match.get("wa", "Tie").lower()
            if winner in ["red", "blue"]:
                learn_from_match_outcome(event_key, match.get("k", ""), winner, red_score, blue_score)
            
            if p_red == 0.5 and p_blue == 0.5:
                pred_red = "50%"
                pred_blue = "50%"
                pred_winner = "Tie"
            else:
                pred_red = f"{p_red:.0%}"
                pred_blue = f"{p_blue:.0%}"
                pred_winner = "Red" if p_red > p_blue else "Blue"

            yid = match.get("yt")
            video_link = f"[Watch](https://www.youtube.com/watch?v={yid})" if yid else "N/A"

            # Add match link for the label
            match_link = f"[{label}](/match/{event_key}/{label})"
            
            if table_style == "both":
                # Both alliances view - show all predictions
                rows.append({
                    "Video": video_link,
                    "Match": match_link,
                    "Red Alliance": format_teams_markdown(red_str),
                    "Blue Alliance": format_teams_markdown(blue_str),
                    "Red Score": red_score,
                    "Blue Score": blue_score,
                    "Winner": winner.title() if winner else "Tie",
                    "Pred Winner": pred_winner,
                    "Red Pred": f"{pred_red}",
                    "Blue Pred": f"{pred_blue}",
                    "Red Prediction %": p_red * 100,  # For conditional styling
                    "Blue Prediction %": p_blue * 100,  # For conditional styling
                })
            else:
                # Team focus view - only show selected team's alliance
                team_alliance = None
                team_prediction = "N/A"
                team_prediction_percent = None
                
                if selected_team and selected_team != "ALL":
                    if selected_team in red_str.split(","):
                        team_alliance = "Red"
                        team_prediction = pred_red
                        team_prediction_percent = p_red * 100
                    elif selected_team in blue_str.split(","):
                        team_alliance = "Blue"
                        team_prediction = pred_blue
                        team_prediction_percent = p_blue * 100
                
                rows.append({
                    "Video": video_link,
                    "Match": match_link,
                    "Alliance": team_alliance or "N/A",
                    "Red Alliance": format_teams_markdown(red_str),
                    "Blue Alliance": format_teams_markdown(blue_str),
                    "Score": red_score if team_alliance == "Red" else blue_score if team_alliance == "Blue" else "N/A",
                    "Opponent Score": blue_score if team_alliance == "Red" else red_score if team_alliance == "Blue" else "N/A",
                    "Winner": winner.title() if winner else "Tie",
                    "Pred Winner": pred_winner,
                    "Prediction": team_prediction,
                    "Prediction %": team_prediction_percent,
                    "Outcome": "",
                })
        return rows

    qual_data = build_match_rows(qual_matches, table_style)
    playoff_data = build_match_rows(playoff_matches, table_style)

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

    if table_style == "both":
        row_style = [
            # Row coloring for winner (these should come first)
            {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
            # --- Cell-level prediction rules (these should come after row-level rules) ---
            # Red prediction styling
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
            # Blue prediction styling
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
            # Predicted Winner styling
            {"if": {"filter_query": '{Pred Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Pred Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Pred Winner} = "Tie"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-yellow)", "color": "var(--text-primary)"},
        ]
    else:
        # Team focus styling
        row_style = [
            # Row coloring for winner
            {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
            # Team prediction styling
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
            # Outcome styling (win/loss for team)
            {"if": {"filter_query": '{Winner} = "Red" && {Alliance} = "Red"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-green)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Red" && {Alliance} != "Red"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue" && {Alliance} = "Blue"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-green)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue" && {Alliance} != "Blue"', "column_id": "Outcome"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
        ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "color": "var(--text-primary)", "backgroundColor": "transparent"}
    style_header={
        "backgroundColor": "var(--card-bg)",        # Match the table background
        "color": "var(--text-primary)",
        "fontWeight": "bold",              # Keep column labels strong
        "textAlign": "center",
        "borderBottom": "1px solid var(--border-color)",  # Thin line under header only
        "padding": "6px",                  # Reduce banner size
        "fontSize": "13px",                # Optional: shrink text slightly
    }

    style_cell={
        "backgroundColor": "transparent", 
        "color": "var(--text-primary)",
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }

    qual_table = [
        dash_table.DataTable(
            columns=match_columns,
            sort_action="native",
            sort_mode="multi",
            data=qual_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if qual_data else [
        dbc.Alert("No qualification matches found.", color="info"),
    ]

    playoff_table = [
        dash_table.DataTable(
            columns=match_columns,
            sort_action="native",
            sort_mode="multi",
            data=playoff_data,
            page_size=10,
            style_table=style_table,
            style_header=style_header,
            style_cell=style_cell,
            style_data_conditional=row_style,
        )
    ] if playoff_data else [
        dbc.Alert("No playoff matches found.", color="info"),
    ]

        # Calculate prediction accuracy for quals and playoffs
    def compute_accuracy(matches, table_style):
        total = 0
        correct = 0
        excluded_ties = 0
        for match_data in build_match_rows(matches, table_style):
            winner = match_data.get("Winner", "").lower()
            if winner == "tie":
                # Only count as correct if prediction is 50%
                if table_style == "both":
                    pred_red = match_data.get("Red Prediction %", 50)
                    pred_blue = match_data.get("Blue Prediction %", 50)
                    if pred_red == 50 and pred_blue == 50:
                        total += 1
                        correct += 1
                    else:
                        excluded_ties += 1
                else:
                    prediction_percent = match_data.get("Prediction %", 50)
                    if prediction_percent == 50:
                        total += 1
                        correct += 1
                    else:
                        excluded_ties += 1
            elif winner in ["red", "blue"]:
                total += 1
                if table_style == "both":
                    pred_winner = match_data.get("Pred Winner", "").lower()
                    if pred_winner and winner == pred_winner:
                        correct += 1
                else:
                    prediction_percent = match_data.get("Prediction %", 0)
                    if prediction_percent is not None:
                        team_alliance = match_data.get("Alliance", "").lower()
                        if team_alliance == winner and prediction_percent > 50:
                            correct += 1
                        elif team_alliance != winner and prediction_percent < 50:
                            correct += 1
        acc = (correct / total * 100) if total > 0 else 0
        return correct, total, acc, excluded_ties

    qual_correct, qual_total, qual_acc, qual_excluded = compute_accuracy(qual_matches, table_style)
    playoff_correct, playoff_total, playoff_acc, playoff_excluded = compute_accuracy(playoff_matches, table_style)

    def accuracy_badge(correct, total, acc, excluded_ties):
        if excluded_ties:
            note = f" (excluding {excluded_ties} ties)" if excluded_ties > 1 else f" (excluding {excluded_ties} tie)"
        else:
            note = ""
        return html.Span(
            f"Prediction Accuracy: {correct}/{total} ({acc:.0f}%)" + note,
            style={
                "color": "var(--text-secondary)",
                "fontSize": "0.98rem",
                "marginLeft": "12px",
                "fontWeight": "normal"
            }
        )

    # Section headers with accuracy - only create if there are matches
    qual_header = None
    if qual_matches:
        qual_header = html.Div([
            html.Span("Qualification Matches", style={"fontWeight": "bold", "fontSize": "1.15rem"}),
            accuracy_badge(qual_correct, qual_total, qual_acc, qual_excluded)
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "0.5rem"})

    playoff_header = None
    if playoff_matches:
        playoff_header = html.Div([
            html.Span("Playoff Matches", style={"fontWeight": "bold", "fontSize": "1.15rem"}),
            accuracy_badge(playoff_correct, playoff_total, playoff_acc, playoff_excluded)
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "0.5rem"})

    # Calculate insights statistics with more metrics and match links
    def calculate_insights(matches):
        if not matches:
            return {}
        
        scores = []
        win_margins = []
        winning_scores = []
        losing_scores = []
        high_score = 0
        high_score_match = None
        low_score = float('inf')
        low_score_match = None
        high_win_margin = 0
        high_win_margin_match = None
        score_counts = {}
        team_set = set()
        for match in matches:
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            match_key = match.get("k", "").split("_", 1)[-1].upper()
            event_key = match.get("ek", "")
            if red_score > 0 and blue_score > 0:
                scores.extend([red_score, blue_score])
                for t in match.get("rt", "").split(","):
                    if t.strip().isdigit():
                        team_set.add(t.strip())
                for t in match.get("bt", "").split(","):
                    if t.strip().isdigit():
                        team_set.add(t.strip())
                # Win margin
                win_margin = abs(red_score - blue_score)
                win_margins.append(win_margin)
                if win_margin > high_win_margin:
                    high_win_margin = win_margin
                    high_win_margin_match = (event_key, match_key)
                # Winning/losing scores
                if red_score > blue_score:
                    winning_scores.append(red_score)
                    losing_scores.append(blue_score)
                else:
                    winning_scores.append(blue_score)
                    losing_scores.append(red_score)
                # High/low score
                for score in [red_score, blue_score]:
                    score_counts[score] = score_counts.get(score, 0) + 1
                    if score > high_score:
                        high_score = score
                        high_score_match = (event_key, match_key)
                    if score < low_score:
                        low_score = score
                        low_score_match = (event_key, match_key)
        # Mode (most common score)
        mode_score = max(score_counts.items(), key=lambda x: x[1])[0] if score_counts else None
        return {
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "avg_win_margin": sum(win_margins) / len(win_margins) if win_margins else 0,
            "avg_winning_score": sum(winning_scores) / len(winning_scores) if winning_scores else 0,
            "avg_losing_score": sum(losing_scores) / len(losing_scores) if losing_scores else 0,
            "high_score": high_score,
            "high_score_match": high_score_match,
            "low_score": low_score if low_score != float('inf') else 0,
            "low_score_match": low_score_match,
            "high_win_margin": high_win_margin,
            "high_win_margin_match": high_win_margin_match,
            "mode_score": mode_score,
            "num_matches": len(matches),
            "num_teams": len(team_set)
        }
    
    qual_insights = calculate_insights(qual_matches)
    playoff_insights = calculate_insights(playoff_matches)
    
    def match_link(event_key, match_key, value, icon=None):
        if not event_key or not match_key:
            return html.Span(value)
        # For SF/QF, use only the set number (e.g., SF4M1 -> SF4)
        cleaned_key = match_key
        if match_key.startswith("SF") or match_key.startswith("QF"):
            m = re.match(r"(SF|QF)(\d+)", match_key)
            if m:
                cleaned_key = f"{m.group(1)}{m.group(2)}"
        # Finals and quals remain unchanged
        return html.A([
            html.I(className=f"fas fa-link me-1", style={"fontSize": "0.9em"}) if icon else None,
            str(value)
        ], href=f"/match/{event_key}/{cleaned_key}", style={"color": "#ffc107" if icon else "inherit", "textDecoration": "underline", "fontWeight": "bold"})
    
    # Create insights card with improved layout and minimal icons
    # Only show sections that have actual data
    insights_sections = []
    
    if playoff_matches:
        playoff_section = dbc.Col([
            html.H6([
                html.I(className="fas fa-trophy me-1", style={"color": "#007bff"}),
                "Playoff Stats"
            ], style={"color": "#007bff", "fontWeight": "bold", "textAlign": "center", "marginBottom": "15px"}),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(f"{playoff_insights['avg_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(f"{playoff_insights['avg_win_margin']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Win Margin", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(f"{playoff_insights['avg_winning_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Winning Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(f"{playoff_insights['avg_losing_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Losing Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        match_link(*(playoff_insights['high_score_match'] or (None, None)), playoff_insights['high_score'], icon=True),
                        html.Div("High Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        match_link(*(playoff_insights['high_win_margin_match'] or (None, None)), playoff_insights['high_win_margin'], icon=True),
                        html.Div("High Win Margin", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        match_link(*(playoff_insights['low_score_match'] or (None, None)), playoff_insights['low_score'], icon=True),
                        html.Div("Low Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(playoff_insights['mode_score'] if playoff_insights['mode_score'] is not None else "-", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Most Common Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            html.Div([
                html.Span(f"{playoff_insights['num_matches']} matches, {playoff_insights['num_teams']} teams", style={"fontSize": "0.95rem", "color": "var(--text-secondary)"})
            ], style={"textAlign": "center", "marginTop": "10px"})
        ], width=6, style={"borderRight": "1.5px solid #333" if qual_matches else "none"})
        insights_sections.append(playoff_section)
    
    if qual_matches:
        qual_section = dbc.Col([
            html.H6([
                html.I(className="fas fa-robot me-1", style={"color": "#007bff"}),
                "Qualification Stats"
            ], style={"color": "#007bff", "fontWeight": "bold", "textAlign": "center", "marginBottom": "15px"}),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(f"{qual_insights['avg_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(f"{qual_insights['avg_win_margin']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Win Margin", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(f"{qual_insights['avg_winning_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Winning Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(f"{qual_insights['avg_losing_score']:.1f}", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Avg Losing Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        match_link(*(qual_insights['high_score_match'] or (None, None)), qual_insights['high_score'], icon=True),
                        html.Div("High Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        match_link(*(qual_insights['high_win_margin_match'] or (None, None)), qual_insights['high_win_margin'], icon=True),
                        html.Div("High Win Margin", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        match_link(*(qual_insights['low_score_match'] or (None, None)), qual_insights['low_score'], icon=True),
                        html.Div("Low Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.Span(qual_insights['mode_score'] if qual_insights['mode_score'] is not None else "-", style={"fontSize": "1.6rem", "fontWeight": "bold"}),
                        html.Div("Most Common Score", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"})
                    ], style={"textAlign": "center", "padding": "10px"})
                ], width=6)
            ]),
            html.Div([
                html.Span(f"{qual_insights['num_matches']} matches, {qual_insights['num_teams']} teams", style={"fontSize": "0.95rem", "color": "var(--text-secondary)"})
            ], style={"textAlign": "center", "marginTop": "10px"})
        ], width=6)
        insights_sections.append(qual_section)
    
    # Only create insights card if there are matches to show
    insights_card = None
    if insights_sections:
        insights_card = dbc.Card([
            dbc.CardHeader([
                html.H5([
                    html.I(className="fas fa-chart-line me-2", style={"color": "#007bff"}),
                    "Event Insights"
                ], className="mb-0", style={"color": "var(--text-primary)"}),
            ], style={"backgroundColor": "var(--card-bg)", "borderBottom": "1px solid var(--border-color)"}),
            dbc.CardBody([
                dbc.Row(insights_sections, className="g-0"),
            ], style={"backgroundColor": "var(--card-bg)"})
        ], className="mb-4 shadow-sm", style={"borderRadius": "14px", "border": "1.5px solid var(--border-color)", "overflow": "hidden", "marginTop": "3rem"})
    
    # Build the content list dynamically based on what exists
    content = []
    
    if qual_header and qual_table:
        content.extend([qual_header, html.Div(qual_table, className="recent-events-table")])
    
    if playoff_header and playoff_table:
        content.extend([playoff_header, html.Div(playoff_table, className="recent-events-table")])
    
    # Only include insights card if it exists
    if insights_card:
        content.append(insights_card)
    
    return html.Div(content)

# Add a callback for the compare teams table
@app.callback(
    Output("compare-teams-table-container", "children"),
    Input("compare-teams-dropdown", "value"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-rankings", "data"),
    State("store-event-year", "data"),
    State("store-event-matches", "data"),
)
def update_compare_teams_table(selected_teams, epa_data, event_teams, rankings, event_year, event_matches):
    if not selected_teams:
        return dbc.Alert("Select two or more teams to compare.", color="info")
    # Build lookup for event_teams
    team_lookup = {str(t["tk"]): t for t in event_teams}

    # Compute avg score and SoS for each team
    avg_score_map = {}
    sos_map = {}
    matches = event_matches or []
    for tnum in selected_teams:
        tnum_str = str(tnum)
        team_matches = [m for m in matches if tnum_str in m.get("rt", "").split(",") or tnum_str in m.get("bt", "").split(",")]
        scores = []
        win_probs = []
        for m in team_matches:
            # Determine alliance
            if tnum_str in m.get("rt", "").split(","):
                alliance = "red"
                score = m.get("rs", 0)
                opp_teams = [int(t) for t in m.get("bt", "").split(",") if t.strip().isdigit()]
            else:
                alliance = "blue"
                score = m.get("bs", 0)
                opp_teams = [int(t) for t in m.get("rt", "").split(",") if t.strip().isdigit()]
            scores.append(score)
            # Win probability (use adaptive prediction)
            red_info = [
                {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                for t in m.get("rt", "").split(",") if t.strip().isdigit()
            ]
            blue_info = [
                {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                for t in m.get("bt", "").split(",") if t.strip().isdigit()
            ]
            p_red, p_blue = predict_win_probability_adaptive(red_info, blue_info, m.get("ek", ""), m.get("k", ""))
            win_prob = p_red if alliance == "red" else p_blue
            win_probs.append(win_prob)
        avg_score_map[tnum_str] = sum(scores) / len(scores) if scores else 0
        sos_map[tnum_str] = sum(win_probs) / len(win_probs) if win_probs else 0

    # Build rows for each team
    rows = []
    for tnum in selected_teams:
        t = team_lookup.get(str(tnum), {})
        epa = epa_data.get(str(tnum), {})
        rank_info = (rankings or {}).get(str(tnum), {})
        rows.append({
            "Team": f"[{tnum} | {truncate_name(t.get('nn', 'Unknown'))}](/team/{tnum}/{event_year})",
            "Rank": rank_info.get("rk", "N/A"),
            "W-L-T": f"{rank_info.get('w', 'N/A')}-{rank_info.get('l', 'N/A')}-{rank_info.get('t', 'N/A')}",
            "SoS": sos_map.get(str(tnum), 0),
            "EPA": float(epa.get('normal_epa', 0)),
            "Auto EPA": float(epa.get('auto_epa', 0)),
            "Teleop EPA": float(epa.get('teleop_epa', 0)),
            "Endgame EPA": float(epa.get('endgame_epa', 0)),
            "Confidence": float(epa.get('confidence', 0)),
            "ACE": float(epa.get('epa', 0)),
        })
    # Compute global percentiles for coloring
    if event_year == current_year:
        global_teams = TEAM_DATABASE.get(event_year, {}).values()
    else:
        year_team_data, _, _, _, _, _ = load_year_data(event_year)
        global_teams = year_team_data.values()
    global_ace_values = [t.get("epa", 0) for t in global_teams]
    global_auto_values = [t.get("auto_epa", 0) for t in global_teams]
    global_teleop_values = [t.get("teleop_epa", 0) for t in global_teams]
    global_endgame_values = [t.get("endgame_epa", 0) for t in global_teams]
    global_confidence_values = [t.get("confidence", 0) for t in global_teams]
    percentiles_dict = {
        "Auto EPA": compute_percentiles(global_auto_values),
        "Teleop EPA": compute_percentiles(global_teleop_values),
        "Endgame EPA": compute_percentiles(global_endgame_values),
        "Confidence": compute_percentiles(global_confidence_values),
        "ACE": compute_percentiles(global_ace_values),
    }
    style_data_conditional = get_epa_styling(percentiles_dict)
    columns = [
        {"name": "Team", "id": "Team", "presentation": "markdown"},
        {"name": "Rank", "id": "Rank"},
        {"name": "W-L-T", "id": "W-L-T"},
        {"name": "SoS", "id": "SoS"},
        {"name": "EPA", "id": "EPA"},
        {"name": "Auto EPA", "id": "Auto EPA"},
        {"name": "Teleop EPA", "id": "Teleop EPA"},
        {"name": "Endgame EPA", "id": "Endgame EPA"},
        {"name": "Confidence", "id": "Confidence"},
        {"name": "ACE", "id": "ACE"},
    ]
    # Radar chart for visual comparison
    
    radar_stats = ["Auto EPA", "Teleop EPA", "Endgame EPA", "Confidence", "EPA", "ACE", "Avg Score", "SoS"]
    # Gather all event teams' stats for normalization
    all_team_stats = {stat: [] for stat in radar_stats}
    for t in event_teams:
        tnum = str(t["tk"])
        epa = epa_data.get(tnum, {})
        all_team_stats["Auto EPA"].append(float(epa.get("auto_epa", 0)))
        all_team_stats["Teleop EPA"].append(float(epa.get("teleop_epa", 0)))
        all_team_stats["Endgame EPA"].append(float(epa.get("endgame_epa", 0)))
        all_team_stats["Confidence"].append(float(epa.get("confidence", 0)))
        all_team_stats["EPA"].append(float(epa.get("normal_epa", 0)))
        all_team_stats["ACE"].append(float(epa.get("epa", 0)))
        all_team_stats["Avg Score"].append(avg_score_map.get(tnum, 0))
        all_team_stats["SoS"].append(sos_map.get(tnum, 0))
    # Compute min/max for each stat
    stat_minmax = {}
    for stat in radar_stats:
        vals = all_team_stats[stat]
        if vals:
            stat_min = min(vals)
            stat_max = max(vals)
            stat_minmax[stat] = (stat_min, stat_max)
        else:
            stat_minmax[stat] = (0, 1)
    # Radar chart with normalized values
    fig = go.Figure()
    for row in rows:
        tnum = row["Team"].split("|")[0].replace("[", "").strip()
        tnum_key = tnum
        values = [
            row["Auto EPA"],
            row["Teleop EPA"],
            row["Endgame EPA"],
            row["Confidence"],
            row["EPA"],
            row["ACE"],
            avg_score_map.get(tnum_key, 0),
            sos_map.get(tnum_key, 0),
        ]
        norm_values = []
        for v, stat in zip(values, radar_stats):
            stat_min, stat_max = stat_minmax[stat]
            if stat_max > stat_min:
                norm = (v - stat_min) / (stat_max - stat_min)
            else:
                norm = 0.5
            norm_values.append(norm)
        fig.add_trace(go.Scatterpolar(
            r=norm_values,
            theta=radar_stats,
            fill='toself',
            name=tnum,
        ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, showticklabels=True, ticks=''),
            bgcolor='rgba(0,0,0,0)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        margin=dict(l=30, r=30, t=30, b=30),
        height=400,
        template="plotly_dark"
    )
    return html.Div([
        dash_table.DataTable(
            columns=columns,
            sort_action="native",
            sort_mode="multi",
            data=[{k: (f"{v:.2f}" if isinstance(v, float) else v) for k, v in row.items()} for row in rows],
            style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
            style_header={
                "backgroundColor": "var(--card-bg)",
                "fontWeight": "bold",
                "textAlign": "center",
                "borderBottom": "1px solid #ccc",
                "padding": "6px",
                "fontSize": "13px",
            },
            style_cell={
                "backgroundColor": "var(--card-bg)",
                "textAlign": "center",
                "padding": "10px",
                "border": "none",
                "fontSize": "14px",
            },
            style_data_conditional=style_data_conditional,
            style_as_list_view=True,
        ),
        html.Div([
            html.Hr(),
            html.H5("Radar Chart Comparison", style={"marginTop": "20px"}),
            dcc.Graph(figure=fig)
        ])
    ])

# Add a client-side callback to handle opening the playlist in a new tab
app.clientside_callback(
    """
    function(n_clicks, selected_team, event_matches, pathname) {
        if (!n_clicks) return window.dash_clientside.no_update;
        
        // Extract event_key from pathname
        let event_key = null;
        if (pathname && pathname.includes('/event/')) {
            event_key = pathname.split('/event/')[1].split('/')[0];
        }
        
        if (!event_key || !event_matches) return window.dash_clientside.no_update;
        
        // Get event name from the first match (they all have the same event)
        const event_name = event_matches[0]?.ek || event_key;
        
        // Create playlist title
        let playlist_title = event_name;
        if (selected_team && selected_team !== 'ALL') {
            playlist_title = `${event_name} - Team ${selected_team}`;
        }
        
        // Filter matches based on team selection
        let filtered_matches = event_matches;
        if (selected_team && selected_team !== 'ALL') {
            filtered_matches = event_matches.filter(match => {
                const redTeams = match.rt ? match.rt.split(',') : [];
                const blueTeams = match.bt ? match.bt.split(',') : [];
                return redTeams.includes(selected_team) || blueTeams.includes(selected_team);
            });
        }
        
        // Sort matches in correct order: quals first, then semis, then finals
        filtered_matches.sort((a, b) => {
            // Get competition level and match number from match key
            const getMatchInfo = (match) => {
                const key = match.k ? match.k.split('_').pop().toLowerCase() : '';
                
                // Extract comp level and match number
                let compLevel = 'qm'; // default
                let matchNum = 0;
                let setNum = 0;
                
                if (key.startsWith('qm')) {
                    compLevel = 'qm';
                    matchNum = parseInt(key.replace('qm', '').replace('m', '')) || 0;
                } else if (key.startsWith('qf')) {
                    compLevel = 'qf';
                    const parts = key.replace('qf', '').split('m');
                    setNum = parseInt(parts[0]) || 0;
                    matchNum = parseInt(parts[1]) || 0;
                } else if (key.startsWith('sf')) {
                    compLevel = 'sf';
                    const parts = key.replace('sf', '').split('m');
                    setNum = parseInt(parts[0]) || 0;
                    matchNum = parseInt(parts[1]) || 0;
                } else if (key.startsWith('f')) {
                    compLevel = 'f';
                    matchNum = parseInt(key.replace('f', '').replace('m', '')) || 0;
                }
                
                return { compLevel, setNum, matchNum };
            };
            
            const aInfo = getMatchInfo(a);
            const bInfo = getMatchInfo(b);
            
            // Define comp level order: qm < qf < sf < f
            const compLevelOrder = { 'qm': 0, 'qf': 1, 'sf': 2, 'f': 3 };
            
            // Compare by comp level first
            if (compLevelOrder[aInfo.compLevel] !== compLevelOrder[bInfo.compLevel]) {
                return compLevelOrder[aInfo.compLevel] - compLevelOrder[bInfo.compLevel];
            }
            
            // If same comp level, compare by set number (for qf/sf)
            if (aInfo.setNum !== bInfo.setNum) {
                return aInfo.setNum - bInfo.setNum;
            }
            
            // Finally compare by match number
            return aInfo.matchNum - bInfo.matchNum;
        });
        
        // Extract YouTube video IDs from sorted matches
        const video_ids = filtered_matches
            .map(match => match.yt)
            .filter(yt => yt);
        
        if (video_ids.length === 0) return window.dash_clientside.no_update;
        
        // Split into multiple playlists if more than 50 videos (YouTube limit)
        const maxVideosPerPlaylist = 50;
        const numPlaylists = Math.ceil(video_ids.length / maxVideosPerPlaylist);
        
        // Open playlists with a delay to avoid browser blocking
        for (let i = 0; i < numPlaylists; i++) {
            setTimeout(() => {
                const startIndex = i * maxVideosPerPlaylist;
                const endIndex = Math.min(startIndex + maxVideosPerPlaylist, video_ids.length);
                const playlistVideoIds = video_ids.slice(startIndex, endIndex);
                
                // Create playlist title with part number if multiple playlists
                let playlistTitle = playlist_title;
                if (numPlaylists > 1) {
                    playlistTitle = `${playlist_title} - ${i + 1}`;
                }
                
                // Create YouTube playlist URL with title
                const playlist_url = `https://www.youtube.com/watch_videos?video_ids=${playlistVideoIds.join(',')}&title=${encodeURIComponent(playlistTitle)}`;
                
                // Open in new tab
                window.open(playlist_url, '_blank');
            }, i * 100); // 100ms delay between each tab
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("url", "pathname", allow_duplicate=True),
    Input("create-playlist-btn", "n_clicks"),
    [
        State("team-filter", "value"),
        State("store-event-matches", "data"),
        State("url", "pathname"),
    ],
    prevent_initial_call=True
)

@app.callback(
    [
        Output("teams-table", "data"),
        Output("state-dropdown", "options"),
        Output("top-teams-container", "children"),
        Output("teams-table-container", "style"),
        Output("avatar-gallery", "children"),
        Output("avatar-gallery", "style"),
        Output("bubble-chart", "figure"),
        Output("bubble-chart", "style"),
        Output("teams-url", "search"),
        Output("teams-table", "style_data_conditional"), 
    ],
    [
        Input("district-dropdown", "value"),
        Input("teams-year-dropdown", "value"),
        Input("country-dropdown", "value"),
        Input("state-dropdown", "value"),
        Input("search-bar", "value"),
        Input("teams-tabs", "active_tab"),
        Input("x-axis-dropdown", "value"),
        Input("y-axis-dropdown", "value"),
        Input("percentile-toggle", "value"),
    ],
    [State("teams-url", "href")],
    prevent_initial_call=True,
)
def load_teams(
    selected_district,
    selected_year,
    selected_country,
    selected_state,
    search_query,
    active_tab,
    x_axis,
    y_axis,
    percentile_mode,
    href
):
    ctx = callback_context
    # Default filter values
    default_values = {
        "year": current_year,
        "country": "All",
        "state": "All",
        "search": "",
        "x": "teleop_epa",
        "y": "auto+endgame",
        "tab": "table-tab",
        "district": "All"
    }

    # Build query string for updating URL
    params = {
        "year": selected_year,
        "country": selected_country,
        "state": selected_state,
        "search": search_query,
        "x": x_axis,
        "y": y_axis,
        "tab": active_tab,
        "district": selected_district,
        "percentile": "filtered" if "filtered" in percentile_mode else None,
    }
    query_string = "?" + urlencode({
        k: v for k, v in params.items()
        if v not in (None, "", "All") and str(v) != str(default_values.get(k, ""))
    })
    # Only update the URL if a dropdown was the trigger
    if ctx.triggered and not any(t["prop_id"].startswith("teams-url.search") for t in ctx.triggered):
        url_update = query_string
    else:
        url_update = no_update

    # Load and filter teams
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(selected_year):
        # Load data for the specific year if it's not current year
        if selected_year != current_year:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(selected_year)
                year_team_database = {selected_year: year_team_data}
                teams_data, epa_ranks = calculate_all_ranks(selected_year, year_team_database)
            except Exception as e:
                return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, url_update, []
        else:
            return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, url_update, []
    else:
        teams_data, epa_ranks = calculate_all_ranks(selected_year, TEAM_DATABASE)

    empty_style = []
    if not teams_data:
        return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, url_update, empty_style

    if selected_country and selected_country != "All":
        teams_data = [t for t in teams_data if (t.get("country") or "").lower() == selected_country.lower()]

    if selected_district and selected_district != "All":
        if selected_district == "ISR":
            teams_data = [
                t for t in teams_data
                if (t.get("country") or "").lower() == "israel"
            ]
        elif selected_district == "FMA":
            # For FMA district, exclude teams from western Pennsylvania cities
            teams_data = [
                t for t in teams_data
                if (t.get("state_prov") or "").lower() in ["delaware", "new jersey", "pa", "pennsylvania"] and
                not is_western_pennsylvania_city(t.get("city", ""))
            ]
        else:
            district_info = DISTRICT_STATES_COMBINED.get(selected_district, {})
            allowed_states = []
            if district_info:
                allowed_states = [s.lower() for s in district_info.get("abbreviations", []) + district_info.get("names", [])]
            teams_data = [
                t for t in teams_data
                if (t.get("state_prov") or "").lower() in allowed_states
            ]
    elif selected_state and selected_state != "All":
        teams_data = [t for t in teams_data if (t.get("state_prov") or "").lower() == selected_state.lower()]

    if search_query:
        q = search_query.lower()
        teams_data = [
            t for t in teams_data
            if q in str(t.get("team_number", "")).lower()
            or q in t.get("nickname", "").lower()
            or q in t.get("city", "").lower()
        ]

    teams_data.sort(key=lambda t: t.get("weighted_ace") or 0, reverse=True)
    
    # Always compute global percentiles
    if not TEAM_DATABASE.get(selected_year):
        if selected_year != current_year:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(selected_year)
                year_team_database = {selected_year: year_team_data}
                global_data, _ = calculate_all_ranks(selected_year, year_team_database)
            except Exception as e:
                global_data = teams_data
        else:
            global_data = teams_data
    else:
        global_data, _ = calculate_all_ranks(selected_year, TEAM_DATABASE)
    
    extract_global = lambda key: [t[key] for t in global_data if t.get(key) is not None]
    
    extract_valid = lambda key: [t[key] for t in teams_data if t.get(key) is not None]
    
    # Use filtered data only if toggle is on
    extract_used = extract_valid if "filtered" in percentile_mode else extract_global
    
    overall_percentiles = compute_percentiles(extract_used("epa"))
    auto_percentiles = compute_percentiles(extract_used("auto_epa"))
    teleop_percentiles = compute_percentiles(extract_used("teleop_epa"))
    endgame_percentiles = compute_percentiles(extract_used("endgame_epa"))
    confidence_percentiles = compute_percentiles(extract_used("confidence"))
    
    percentiles_dict = {
        "ace": overall_percentiles,
        "confidence": confidence_percentiles,
        "auto_epa": auto_percentiles,
        "teleop_epa": teleop_percentiles,
        "endgame_epa": endgame_percentiles,
    }

    style_data_conditional = get_epa_styling(percentiles_dict)
    
    # Add favorites styling
    favorites_styling = [
        {
            "if": {
                "filter_query": "{favorites} >= 10",
                "column_id": "favorites"
            },
            "backgroundColor": "#ff33cc99",
            "fontWeight": "bold",
            "borderRadius": "6px",
            "padding": "4px 6px",
        },
        {
            "if": {
                "filter_query": "{favorites} >= 5 && {favorites} < 10",
                "column_id": "favorites"
            },
            "backgroundColor": "#0099ff99",
            "borderRadius": "6px",
            "padding": "4px 6px",
        },
        {
            "if": {
                "filter_query": "{favorites} >= 1 && {favorites} < 5",
                "column_id": "favorites"
            },
            "backgroundColor": "#33cc3399",
            "borderRadius": "6px",
            "padding": "4px 6px",
        }
    ]
    
    style_data_conditional.extend(favorites_styling)

    with open('data/states.json', 'r', encoding='utf-8') as f:
        STATES = json.load(f)

    state_options = [{"label": "All States", "value": "All"}]
    if selected_country and selected_country in STATES:
        state_options += [
            {"label": s["label"], "value": s["value"]}
            for s in STATES[selected_country] if isinstance(s, dict)
        ]
    elif not selected_country or selected_country == "All":
        # Default to US states if global
        state_options += [
            {"label": s["label"], "value": s["value"]}
            for s in STATES.get("USA", []) if isinstance(s, dict)
        ]

    def get_axis_value(team, axis):
        auto = abs(team.get("auto_epa") or 0)
        teleop = abs(team.get("teleop_epa") or 0)
        endgame = abs(team.get("endgame_epa") or 0)
        total = abs(team.get("epa") or 0)
        return {
            "auto_epa": auto,
            "teleop_epa": teleop,
            "endgame_epa": endgame,
            "auto+teleop": auto + teleop,
            "auto+endgame": auto + endgame,
            "teleop+endgame": teleop + endgame,
            "epa": total,
        }.get(axis, 0)

    # Get favorites counts for all teams
    from datagather import get_all_team_favorites_counts
    favorites_counts = get_all_team_favorites_counts()
    
    table_rows = []
    for t in teams_data:
        team_num = t.get("team_number")
        rank = epa_ranks.get(str(team_num), {}).get("rank", "N/A")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        nickname = t.get('nickname', 'Unknown')
        nickname_safe = nickname.replace('"', "'")
        truncated = truncate_name(nickname)
        team_display = f'[{team_num} | {truncated}](/team/{team_num}/{selected_year} "{nickname_safe}")'
        favorites_count = favorites_counts.get(team_num, 0)
        table_rows.append({
            "epa_rank": rank,
            "team_display": team_display,
            "epa": round(abs(t.get("normal_epa") or 0), 2),
            "confidence": t.get("confidence", 0),
            "ace": round(abs(t.get("epa") or 0), 2),
            "auto_epa": round(abs(t.get("auto_epa") or 0), 2),
            "teleop_epa": round(abs(t.get("teleop_epa") or 0), 2),
            "endgame_epa": round(abs(t.get("endgame_epa") or 0), 2),
            "favorites": favorites_count,
            "record": record,
        })

    top_teams_layout = html.Div(
        [
            create_team_card(
                t,
                selected_year,
                get_team_avatar(t.get("team_number"), selected_year),
                epa_ranks,
            )
            for t in teams_data[:3] if t.get("team_number")
        ],
        style={
            "display": "flex",
            "justifyContent": "center",
            "flexWrap": "wrap",
            "gap": "1rem",
            "padding": "1rem",
        }
    )

    # Avatars Tab
    if active_tab == "avatars-tab":
        avatars = []
        for t in teams_data:
            team_number = t.get("team_number")
            if isinstance(team_number, int):
                path = f"assets/avatars/{team_number}.png"
                avatars.append(html.A(
                    html.Img(
                        src=f"/assets/avatars/{team_number}.png?v=1" if os.path.exists(path) else "/assets/avatars/stock.png",
                        title=str(team_number),
                        style={"width": "64px", "height": "64px", "objectFit": "contain", "imageRendering": "pixelated", "border": "1px solid #ccc"},
                    ),
                    href=f"/team/{team_number}/{selected_year}",
                    style={"display": "inline-block"}
                ))
        
        # Add toggle background button
        toggle_button = dbc.Button(
            "Toggle Background Color",
            id="avatar-bg-toggle",
            color="primary",
            style={
                "marginBottom": "20px",
                "backgroundColor": "#0066B3",
                "borderColor": "#0066B3"
            }
        )
        
        avatars_container = html.Div(
            avatars,
            id="avatars-container",
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "gap": "10px",
                "padding": "20px",
                "backgroundColor": "#0066B3",
                "borderRadius": "8px"
            }
        )
        
        return table_rows, state_options, top_teams_layout, {"display": "none"}, [toggle_button, avatars_container], {"display": "flex", "flexDirection": "column"}, go.Figure(), {"display": "none"}, url_update, style_data_conditional

    # Bubble Chart Tab
    elif active_tab == "bubble-chart-tab":
        chart_data = []
        for t in teams_data:
            x_val = get_axis_value(t, x_axis)
            y_val = get_axis_value(t, y_axis)
            if x_val is not None and y_val is not None:
                chart_data.append({
                    "x": x_val,
                    "y": y_val,
                    "epa": t.get("epa") or 0,
                    "team": f"{t.get('team_number')} - {t.get('nickname', '')}",
                    "team_number": str(t.get("team_number")),
                })

        if not chart_data:
            # Return empty figure if no data
            fig = go.Figure()
            fig.update_layout(
                title="No data available for selected filters",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                annotations=[{
                    "text": "No teams match the current filters",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#777"}
                }]
            )
            return table_rows, state_options, top_teams_layout, {"display": "none"}, [], {"display": "none"}, fig, {"display": "block"}, url_update, style_data_conditional

        df = pd.DataFrame(chart_data)
        q = (search_query or "").lower().strip()
        df["is_match"] = df["team"].str.lower().str.contains(q) if q else False
        
        # Improved hover text with better formatting
        df["hover"] = df.apply(lambda r: f"<b>{r['team']}</b><br>{x_axis.replace('_epa', ' ACE').replace('epa', 'Total EPA').replace('+', ' + ')}: {r['x']:.2f}<br>{y_axis.replace('_epa', ' ACE').replace('epa', 'Total EPA').replace('+', ' + ')}: {r['y']:.2f}<br>ACE: {r['epa']:.2f}", axis=1)

        # Create figure with improved styling
        fig = go.Figure()
        
        # Regular teams (non-matching search)
        if len(df[~df["is_match"]]) > 0:
            fig.add_trace(go.Scatter(
                x=df.loc[~df["is_match"], "x"],
                y=df.loc[~df["is_match"], "y"],
                mode="markers",
                marker=dict(
                    size=8,
                    color=df.loc[~df["is_match"], "epa"],
                    colorscale="Viridis",
                    colorbar=dict(
                        title=dict(
                            text="ACE",
                            font=dict(color="#777")
                        ),
                        tickfont=dict(color="#777"),
                        thickness=15,
                        len=1.0,
                        x=0,
                        y=-0.15,
                        orientation="h",
                        xanchor="left",
                        yanchor="top"
                    ),
                    showscale=True,
                    line=dict(width=1, color="rgba(255,255,255,0.3)"),
                    opacity=0.7
                ),
                hovertext=df.loc[~df["is_match"], "hover"],
                hoverinfo="text",
                showlegend=False,
                hovertemplate="%{hovertext}<extra></extra>"
            ))
        
        # Highlighted teams (matching search)
        if len(df[df["is_match"]]) > 0:
            fig.add_trace(go.Scatter(
                x=df.loc[df["is_match"], "x"],
                y=df.loc[df["is_match"], "y"],
                mode="markers+text",
                marker=dict(
                    size=12,
                    color="#ffdd00",
                    line=dict(width=2, color="#000000"),
                    opacity=0.9
                ),
                text=df.loc[df["is_match"], "team_number"],
                textfont=dict(size=10, color="#000000"),
                textposition="middle center",
                hovertext=df.loc[df["is_match"], "hover"],
                hoverinfo="text",
                name="Search Results",
                hovertemplate="%{hovertext}<extra></extra>"
            ))

        # Improved layout with better mobile responsiveness
        fig.update_layout(
            xaxis_title=dict(
                text=x_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
                font=dict(size=14, color="#777")
            ),
            yaxis_title=dict(
                text=y_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
                font=dict(size=14, color="#777")
            ),
            margin=dict(l=60, r=80, t=60, b=60),  # Increased margins for mobile
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor="rgba(0,0,0,0.7)",
                bordercolor="#777",
                borderwidth=1,
                font=dict(color="#ffffff")
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.2)",
                color="#777",
                title=dict(font=dict(color="#777")),
                tickfont=dict(color="#777", size=12)
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.2)",
                color="#777",
                title=dict(font=dict(color="#777")),
                tickfont=dict(color="#777", size=12)
            ),
            font=dict(color="#777"),
            # Mobile-friendly settings
            autosize=True,
            height=600,  # Responsive height
            # Performance optimizations
            uirevision=True,  # Maintains zoom/pan state
            dragmode="pan",  # Better mobile interaction
        )
        

        return table_rows, state_options, top_teams_layout, {"display": "none"}, [], {"display": "none"}, fig, {"display": "block"}, url_update, style_data_conditional

    return table_rows, state_options, top_teams_layout, {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, url_update, style_data_conditional

@app.callback(
    [
        Output("country-dropdown", "value"),
        Output("state-dropdown", "value"),
        Output("district-dropdown", "value"),
        Output("teams-year-dropdown", "value"),
        Output("percentile-toggle", "value"),
    ],
    Input("teams-url", "search"),
)
def sync_teams_dropdowns_with_url(search):
    country = "All"
    state = "All"
    district = "All"
    year = current_year
    percentile = []
    if search and search.startswith("?"):
        params = parse_qs(search[1:])
        country = params.get("country", [country])[0]
        state = params.get("state", [state])[0]
        district = params.get("district", [district])[0]
        try:
            year = int(params.get("year", [year])[0])
        except Exception:
            year = current_year
        if params.get("percentile", [""])[0] == "filtered":
            percentile = ["filtered"]
    return country, state, district, year, percentile

@app.callback(
    Output("axis-dropdown-container", "style"),
    Input("teams-tabs", "active_tab")
)
def toggle_axis_dropdowns(active_tab):
    if active_tab == "bubble-chart-tab":
        return {"display": "block", "marginBottom": "15px"}
    return {"display": "none"}

# Avatar background toggle callback
@app.callback(
    [Output("avatar-bg-toggle", "style"),
     Output("avatars-container", "style")],
    [Input("avatar-bg-toggle", "n_clicks")],
    [State("avatar-bg-toggle", "style"),
     State("avatars-container", "style")],
    prevent_initial_call=True
)
def toggle_avatar_background(n_clicks, button_style, container_style):
    if not n_clicks:
        return button_style, container_style
    
    # Get current background color from button style
    current_bg = button_style.get("backgroundColor", "#0066B3")
    
    # Toggle between blue and red
    if current_bg == "#0066B3":
        new_bg = "#ED1C24"
    else:
        new_bg = "#0066B3"
    
    # Update button style
    new_button_style = button_style.copy()
    new_button_style["backgroundColor"] = new_bg
    new_button_style["borderColor"] = new_bg
    
    # Update container style
    new_container_style = container_style.copy()
    new_container_style["backgroundColor"] = new_bg
    
    return new_button_style, new_container_style

# Export callbacks for teams table
@app.callback(
    [Output("download-dataframe-csv", "data"),
     Output("download-dataframe-excel", "data"),
     Output("download-dataframe-tsv", "data"),
     Output("download-dataframe-json", "data"),
     Output("download-dataframe-html", "data"),
     Output("download-dataframe-latex", "data")],
    [Input("export-csv-dropdown", "n_clicks"),
     Input("export-excel-dropdown", "n_clicks"),
     Input("export-tsv-dropdown", "n_clicks"),
     Input("export-json-dropdown", "n_clicks"),
     Input("export-html-dropdown", "n_clicks"),
     Input("export-latex-dropdown", "n_clicks"),
     Input("export-selected-csv-dropdown", "n_clicks"),
     Input("export-selected-excel-dropdown", "n_clicks"),
     Input("export-selected-tsv-dropdown", "n_clicks"),
     Input("export-selected-json-dropdown", "n_clicks"),
     Input("export-selected-html-dropdown", "n_clicks"),
     Input("export-selected-latex-dropdown", "n_clicks")],
    [State("teams-table", "data"),
     State("teams-table", "selected_rows")],
    prevent_initial_call=True
)
def export_data(csv_clicks, excel_clicks, tsv_clicks, json_clicks, html_clicks, latex_clicks,
                selected_csv_clicks, selected_excel_clicks, selected_tsv_clicks, selected_json_clicks, selected_html_clicks, selected_latex_clicks,
                data, selected_rows):
    ctx = dash.callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    export_selected = triggered_id in [
        "export-selected-csv-dropdown", "export-selected-excel-dropdown", "export-selected-tsv-dropdown",
        "export-selected-json-dropdown", "export-selected-html-dropdown", "export-selected-latex-dropdown",
    ]
    if export_selected:
        if not selected_rows:
            return [None] * 6
        df = df.iloc[selected_rows]
        filename_prefix = "selected_teams"
    else:
        filename_prefix = "teams_data"
    df_export = df.copy()
    if 'team_display' in df_export.columns:
        df_export['team_display'] = df_export['team_display'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Prepare outputs for all formats
    outputs = [None] * 6
    if triggered_id in ["export-csv-dropdown", "export-selected-csv-dropdown"]:
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id in ["export-excel-dropdown", "export-selected-excel-dropdown"]:
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id in ["export-tsv-dropdown", "export-selected-tsv-dropdown"]:
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id in ["export-json-dropdown", "export-selected-json-dropdown"]:
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id in ["export-html-dropdown", "export-selected-html-dropdown"]:
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id in ["export-latex-dropdown", "export-selected-latex-dropdown"]:
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event insights table
@app.callback(
    [Output("download-event-insights-csv", "data"),
     Output("download-event-insights-excel", "data"),
     Output("download-event-insights-tsv", "data"),
     Output("download-event-insights-json", "data"),
     Output("download-event-insights-html", "data"),
     Output("download-event-insights-latex", "data")],
    [Input("event-export-csv-dropdown", "n_clicks"),
     Input("event-export-tsv-dropdown", "n_clicks"),
     Input("event-export-excel-dropdown", "n_clicks"),
     Input("event-export-json-dropdown", "n_clicks"),
     Input("event-export-html-dropdown", "n_clicks"),
     Input("event-export-latex-dropdown", "n_clicks")],
    [State("event-insights-table", "data")],
    prevent_initial_call=True
)
def export_event_insights_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Name' in df_export.columns:
        df_export['Name'] = df_export['Name'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_prefix = "event_insights"
    # Prepare outputs for all formats
    outputs = [None] * 6
    if triggered_id == "event-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Search toggle callback
@app.callback(
    [Output("search-container", "style"),
     Output("search-toggle", "style")],
    [Input("search-toggle", "n_clicks")],
    [State("search-container", "style")],
    prevent_initial_call=True
)
def toggle_search_bar(n_clicks, current_style):
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    # Toggle the search container visibility
    if current_style and current_style.get("display") == "none":
        # Show search bar
        new_container_style = {
            "display": "flex",
            "flex": "1",
            "maxWidth": "300px",
            "transition": "all 0.3s ease"
        }
        new_button_style = {
            "background": "var(--input-bg)",
            "border": "1px solid var(--input-border)",
            "color": "var(--text-primary)",
            "fontSize": "16px",
            "cursor": "pointer",
            "padding": "8px",
            "borderRadius": "4px",
            "transition": "all 0.2s ease"
        }
    else:
        # Hide search bar
        new_container_style = {
            "display": "none",
            "flex": "1",
            "maxWidth": "300px",
            "transition": "all 0.3s ease"
        }
        new_button_style = {
            "background": "none",
            "border": "none",
            "color": "var(--text-primary)",
            "fontSize": "16px",
            "cursor": "pointer",
            "padding": "8px",
            "borderRadius": "4px",
            "transition": "all 0.2s ease"
        }
    
    return new_container_style, new_button_style

@app.callback(
    Output("compare-teams", "options"),
    Input("compare-year", "value")
)
def update_compare_team_dropdowns(year):
    year = year or current_year
    
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(year):
        # Load data for the specific year if it's not current year
        if year != current_year:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(year)
                teams = year_team_data
            except Exception as e:
                return []  # Return empty options if loading fails
        else:
            return []  # Return empty options for current year if not loaded
    else:
        teams = TEAM_DATABASE.get(year, {})
    
    options = [
        {"label": f"{t['team_number']} | {t.get('nickname', '')}", "value": t["team_number"]}
        for t in teams.values()
    ]
    return options

@app.callback(
    Output("compare-output-section", "children"),
    Input("compare-teams", "value"), # Change trigger to team dropdown value
    Input("compare-year", "value"), # Also trigger on year change
    # Removed prevent_initial_call=True so it runs on page load with defaults
)
def compare_multiple_teams(team_ids, year): # Update function signature

    if not team_ids or len(team_ids) < 2:
        # Provide a message prompting the user to select teams
        return dbc.Alert("Select at least 2 teams to compare.", color="info", className="text-center my-4")

    year = year or current_year
    
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(year):
        # Load data for the specific year if it's not current year
        if year != current_year:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(year)
                teams = year_team_data
            except Exception as e:
                return html.Div(f"Error loading data for year {year}: {str(e)}", className="text-center my-4", style={"color": "var(--text-secondary)"})
        else:
            return html.Div(f"Loading data for year {year}...", className="text-center my-4", style={"color": "var(--text-secondary)"})
    else:
        teams = TEAM_DATABASE.get(year, {})
    
    selected = [teams.get(int(tid)) for tid in team_ids if tid and int(tid) in teams]

    if not all(selected) or len(selected) < 2:
        return dbc.Alert("Please select valid teams for the chosen year.", color="warning", className="text-center my-4")

    def pill(label, value, color):
        return html.Span(f"{label}: {value}", style={
            "backgroundColor": color,
            "borderRadius": "6px",
            "padding": "4px 10px",
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "0.85rem",
            "marginRight": "6px",
            "display": "inline-block",
            "marginBottom": "4px"
        })

    # Color palette for pills
    colors = {
        "ACE": "#673ab7",
        "EPA": "#d32f2f",
        "Auto": "#1976d2",
        "Teleop": "#fb8c00",
        "Endgame": "#388e3c",
        "Confidence": "#555"
    }

    def team_card(t, year):
        team_number = t['team_number']
        nickname = t.get('nickname', '')
        avatar_url = get_team_avatar(team_number)

        return dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col( # Avatar column
                        html.Img(
                            src=avatar_url,
                            style={
                                "height": "60px",
                                "width": "60px",
                                "borderRadius": "50%",
                                "objectFit": "contain",
                                "marginRight": "15px",
                                "backgroundColor": "transparent"
                            }
                        ) if avatar_url else html.Div(), # Show empty div if no avatar
                        width="auto",
                        className="d-flex align-items-center"
                    ),
                    dbc.Col( # Team Info and Stats Column
                        html.Div([
                            # Make team name/number clickable link
                            html.A(
                                html.H4(f"#{team_number} | {nickname}", style={"fontWeight": "bold", "color": "var(--text-primary)", "marginBottom": "8px"}),
                                href=f"/team/{team_number}/{year}", # Link to team page
                                style={"textDecoration": "none"} # Remove underline
                            ),
                            html.Div([
                                pill("Auto", f"{t.get('auto_epa', 'N/A'):.2f}", colors["Auto"]),
                                pill("Teleop", f"{t.get('teleop_epa', 'N/A'):.2f}", colors["Teleop"]),
                                pill("Endgame", f"{t.get('endgame_epa', 'N/A'):.2f}", colors["Endgame"]),
                                pill("ACE", f"{t.get('epa', 'N/A'):.2f}", colors["ACE"]),
                            ], style={"display": "flex", "flexWrap": "wrap", "gap": "4px", "marginBottom": "6px"}), # Reduced margin
                            html.Div([
                                html.Span("Record: ", style={"fontWeight": "bold"}),
                                html.Span(str(t.get('wins', 0)), style={"color": "green", "fontWeight": "bold"}),
                                html.Span("-"),
                                html.Span(str(t.get('losses', 0)), style={"color": "red", "fontWeight": "bold"}),
                                html.Span("-"),
                                html.Span(str(t.get('ties', 0)), style={"color": "#777", "fontWeight": "bold"}),
                            ], style={"marginBottom": "0px"}), # Removed margin
                        ]),
                        width=True, # Take remaining width
                    )
                ], className="g-0"), # Remove gutter for tighter layout
            ])
        ], style={
            "borderRadius": "12px",
            "boxShadow": "0px 4px 12px rgba(0,0,0,0.10)",
            "backgroundColor": "var(--card-bg)",
            "marginBottom": "16px",
            "minWidth": "280px",
            "maxWidth": "350px",
            "marginLeft": "auto",
            "marginRight": "auto",
            "padding": "8px" # Reduced padding
        })

    # Radar chart - NORMALIZED SPIDER WEB
    categories = ["ACE", "Auto", "Teleop", "Endgame", "Confidence", "EPA", "Avg Score"]
    stat_keys = ["epa", "auto_epa", "teleop_epa", "endgame_epa", "confidence", "normal_epa", "average_match_score"]

    # Compute min/max for each stat across selected teams
    def get_stat(t, k):
        v = t.get(k, 0)
        try:
            return float(v) if v is not None else 0.0 # Handle None values
        except Exception:
            return 0.0

    # Calculate global min/max for the selected year
    all_teams_in_year = TEAM_DATABASE.get(year, {}).values()
    if not all_teams_in_year:
        # Fallback if no data for the year
        mins = {k: 0.0 for k in stat_keys}
        maxs = {k: 1.0 for k in stat_keys} # Use a dummy range if no data
    else:
        mins = {k: min(get_stat(t, k) for t in all_teams_in_year) for k in stat_keys}
        maxs = {k: max(get_stat(t, k) for t in all_teams_in_year) for k in stat_keys}

    def normalize(val, min_val, max_val):
        if max_val == min_val:
            return 0.5  # Avoid division by zero, return middle value
        return (val - min_val) / (max_val - min_val)

    fig = go.Figure()

    # Define a palette of semi-transparent colors
    colors_rgba = [
        'rgba(31, 119, 180, 0.3)',  # Blue
        'rgba(255, 127, 14, 0.3)',   # Orange
        'rgba(44, 160, 44, 0.3)',    # Green
        'rgba(214, 39, 40, 0.3)',    # Red
        'rgba(148, 103, 189, 0.3)',  # Purple
        'rgba(140, 86, 75, 0.3)',    # Brown
        'rgba(227, 119, 194, 0.3)',  # Pink
        'rgba(127, 127, 127, 0.3)',  # Gray
    ]

    for i, t in enumerate(selected): # Use enumerate to get an index
        r_norm = [
            normalize(get_stat(t, k), mins[k], maxs[k]) for k in stat_keys
        ]
        r_actual = [get_stat(t, k) for k in stat_keys]
        fig.add_trace(go.Scatterpolar(
            r=r_norm,
            theta=categories,
            fill='toself',
            fillcolor=colors_rgba[i % len(colors_rgba)], # Assign color from palette
            line=dict(color=colors_rgba[i % len(colors_rgba)].replace(', 0.6', ', 1.0'), width=2), # Thicker, opaque line
            name=f"#{t['team_number']} | {t.get('nickname', 'Unknown')}", # Add nickname to legend/hover name
            hovertemplate='<b>%{theta}</b><br>Normalized: %{r:.2f}<br>Actual: %{customdata:.2f}<extra>Team ' + str(t['team_number']) + '</extra>',
            customdata=r_actual,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0, 0.2, 0.4, 0.6, 0.8, 1],
                ticktext=["0", "20", "40", "60", "80", "100"],
                gridcolor="#bbb",
                gridwidth=1,
                linecolor="#888",
                linewidth=1,
                rangemode="tozero", # Ensure the radial axis starts at the center
            ),
            angularaxis=dict(
                gridcolor="#bbb",
                gridwidth=1,
                linecolor="#888",
                linewidth=1,
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=True,
        margin=dict(l=80, r=80, t=80, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#999")
    )

    # Container for team cards using Flexbox for wrapping
    cards_container = html.Div([
        team_card(t, year) for t in selected
    ], style={
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "12px", # Space between cards
        "justifyContent": "center" # Center cards in the container
    })

    return html.Div([
        dbc.Row([ # Main row for cards and graph
            dbc.Col( # Column for team cards container
                cards_container, # Use the flex container here
                md=4, # Allocate more space for cards
                xs=12, # Stack vertically on extra small screens
                className="mb-4" # Add bottom margin when stacked
            ),
            dbc.Col( # Column for the radar chart
                dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "475px"}), # Added style for height
                md=8, # Allocate more space for the graph
                xs=12, # Stack vertically on extra small screens
                className="mb-4" # Add bottom margin when stacked
            ),
        ], className="justify-content-center"), # Center the main row
    ], style={"padding": "10px 0"})

@app.callback(
    Output("favorite-alert", "children", allow_duplicate=True),
    Output("favorite-alert", "is_open", allow_duplicate=True),
    Output({"type": "favorite-team-btn", "key": ALL}, "children"),
    Input({"type": "favorite-team-btn", "key": ALL}, "n_clicks"),
    State({"type": "favorite-team-btn", "key": ALL}, "id"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def toggle_favorite_team(n_clicks_list, id_list, session_data):
    if not session_data or "user_id" not in session_data:
        return "Please log in to favorite teams.", True, [dash.no_update] * len(id_list)

    user_id = session_data["user_id"]
    # Only one button per team page, so we expect len(id_list) == 1
    if not id_list or len(id_list) != 1:
        return dash.no_update, dash.no_update, [dash.no_update]
    button_id = id_list[0]
    team_number = button_id["key"]

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()

            # Check if already favorited
            cursor.execute("""
                SELECT id FROM saved_items
                WHERE user_id = %s AND item_type = 'team' AND item_key = %s
            """, (user_id, team_number))
            existing = cursor.fetchone()

            if existing:
                # Remove favorite
                cursor.execute("""
                    DELETE FROM saved_items
                    WHERE user_id = %s AND item_type = 'team' AND item_key = %s
                """, (user_id, team_number))
                conn.commit()
                return "Team removed from favorites.", True, ["☆"]
            else:
                # Add favorite
                cursor.execute("""
                    INSERT INTO saved_items (user_id, item_type, item_key)
                    VALUES (%s, 'team', %s)
                """, (user_id, team_number))
                conn.commit()
                return "Team added to favorites.", True, ["★"]

    except Exception as e:
        return "Error updating favorites.", True, [dash.no_update]

@app.callback(
    Output({"type": "team-favorites-popover-body", "team_number": MATCH}, "children"),
    Input({"type": "team-favorites-popover", "team_number": MATCH}, "is_open"),
    State("url", "pathname"), # Keep pathname state to double check team number if needed
    prevent_initial_call=True
)
def update_team_favorites_popover_content(is_open, pathname):
    # Extract team number from the triggered input ID
    triggered = ctx.triggered_id
    if not triggered or not triggered.get("team_number"):
        return "Error: Could not determine team number."
        
    team_number_str = triggered["team_number"]
    
    if not is_open:
        return "Loading..." # Reset content when popover closes

    # team_number_str is already validated from the ID, just convert
    try:
        team_number = int(team_number_str)
    except ValueError:
         # This case should theoretically not happen with MATCH if ID is set correctly
        return "Error: Invalid team number in ID."

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM saved_items
                WHERE item_type = 'team' AND item_key = %s
            """, (str(team_number),))
            favorited_user_ids = [row[0] for row in cursor.fetchall()]

            if not favorited_user_ids:
                return "No users have favorited this team yet."

            # Get usernames and avatars for these user IDs
            user_details = []
            # Use IN clause for efficiency
            # Ensure favorited_user_ids is not empty before executing IN query
            if not favorited_user_ids:
                 return "No users have favorited this team yet."

            format_strings = ','.join(['%s'] * len(favorited_user_ids))
            cursor.execute("SELECT id, username, avatar_key FROM users WHERE id IN (%s)" % format_strings, tuple(favorited_user_ids))
            user_rows = cursor.fetchall()

            user_list_items = []
            for uid, username, avatar_key in user_rows:
                avatar_src = get_user_avatar(avatar_key or "stock")
                user_list_items.append(html.Li([
                    html.Img(src=avatar_src, height="20px", style={"borderRadius": "50%", "marginRight": "8px"}),
                    html.A(username, href=f"/user/{quote(username)}", style={"textDecoration": "none", "color": "#007bff"})
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"}))

            return html.Ul(user_list_items, style={
                "listStyleType": "none",
                "paddingLeft": "0",
                "marginBottom": "0"
            })

    except Exception as e:
        return "Error loading favoriting users."

@app.callback(
    Output("team-insights-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data"),
    suppress_callback_exceptions=True,
)
def update_team_insights(active_tab, store_data):
    if active_tab != "insights-tab" or not store_data:
        return "Loading insights..."
    
    team_number = store_data.get("team_number")
    year = store_data.get("year")
    performance_year = store_data.get("performance_year")
    
    if not team_number:
        return "No team data available."
    
    # Load year-specific data if needed
    if performance_year == current_year:
        team_data = TEAM_DATABASE.get(performance_year, {}).get(team_number, {})
        event_database = EVENT_DATABASE
    else:
        try:
            year_team_data, year_event_data, _, _, _, _ = load_year_data(performance_year)
            team_data = year_team_data.get(team_number, {})
            event_database = {performance_year: year_event_data}
        except Exception:
            return "No team data available for this year."
    
    if not team_data:
        return "No team data available for this year."
    
    # Create performance trends chart based on URL type
    if year:  # Specific year view - show event-by-event ACE
        # Get team's event EPAs for the specific year
        event_epas = team_data.get("event_epas", [])
        if isinstance(event_epas, str):
            try:
                event_epas = json.loads(event_epas)
            except:
                event_epas = []
        
        if not event_epas:
            return "No event data available for this team in this year."
        
        # Sort events by actual event dates
        def get_event_date(event_epa):
            event_key = event_epa.get("event_key", "")
            if event_key in event_database.get(performance_year, {}):
                event_data = event_database[performance_year][event_key]
                start_date = event_data.get("sd", "")
                if start_date:
                    try:
                        return datetime.strptime(start_date, "%Y-%m-%d")
                    except:
                        pass
            return datetime.max
        
        sorted_events = sorted(event_epas, key=get_event_date)
        
        # Extract data for plotting
        event_names = []
        event_keys = []
        ace_values = []
        
        for event in sorted_events:
            event_key = event.get("event_key", "")
            if event_key in event_database.get(performance_year, {}):
                event_name = event_database[performance_year][event_key].get("n", event_key)
                event_names.append(event_name)
                event_keys.append(event_key)
                ace_values.append(event.get("overall", 0))
        
        if not ace_values:
            return "No valid event data found."
        
        # Create the chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=event_names,
            y=ace_values,
            mode='lines+markers',
            line=dict(color='#007BFF', width=3),
            marker=dict(size=8, color='#007BFF'),
            name='ACE'
        ))
        
        fig.update_layout(
            title=f"Team {team_number} Event Performance in {performance_year}",
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            font=dict(color="#777"),
            xaxis_title="Event",
            yaxis_title="ACE",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', zeroline=False)
        
        trends_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    
    else:  # History view - show year-by-year rank trends
        # Get all years this team has participated in
        years_participated = get_team_years_participated(team_number)
        
        # Get team's historical data across all years they participated in
        years_data = []
        for year_key in sorted(years_participated):
            
            if year_key == current_year:
                # Use global database for current year
                year_team_data = TEAM_DATABASE[year_key]
            else:
                # Load data for other years
                try:
                    year_team_data, _, _, _, _, _ = load_year_data(year_key)
                except Exception as e:
                    print(f"Failed to load data for {year_key}: {e}")
                    continue
            
            if team_number in year_team_data:
                team_year_data = year_team_data[team_number]
                from utils import calculate_single_rank
                global_rank, _, _ = calculate_single_rank(list(year_team_data.values()), team_year_data)
                years_data.append({
                    'year': year_key,
                    'rank': global_rank,
                    'ace': team_year_data.get('epa', 0)
                })
            else:
                print(f"Team {team_number} not found in {year_key} data")
        
        if not years_data:
            return "No historical data available for this team."
        
        years_data.sort(key=lambda x: x['year'])
        
        # Create the chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d['year'] for d in years_data],
            y=[d['rank'] for d in years_data],
            mode='lines+markers',
            line=dict(color='#007BFF', width=3),
            marker=dict(size=8, color='#007BFF'),
            name='Global Rank'
        ))
        
        fig.update_layout(
            title=f"Team {team_number} Historical Performance",
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            font=dict(color="#777"),
            xaxis_title="Year",
            yaxis_title="Rank",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', autorange="reversed", zeroline=False)
        
        trends_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    
    return html.Div([
        html.Div(trends_chart, className="trends-chart-container"),
        html.Hr(style={"margin": "30px 0"}),
    ])

@app.callback(
    Output("team-events-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data"),
    suppress_callback_exceptions=True,
)
def update_team_events(active_tab, store_data):
    if active_tab != "events-tab" or not store_data:
        return ""
    
    team_number = store_data.get("team_number")
    year = store_data.get("year")
    
    if not team_number:
        return "No team data available."

    is_history = not year or str(year).lower() == "history"
    team_key = f"frc{team_number}"
    events = []

    if is_history:
        # Pull from TBA API
        tba_keys = os.environ.get("TBA_API_KEYS", "").split(",")
        tba_keys = [k.strip() for k in tba_keys if k.strip()]
        if not tba_keys:
            return "No TBA API key found."
        api_key = random.choice(tba_keys)

        try:
            headers = {"X-TBA-Auth-Key": api_key}
            url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/events"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            raw_events = response.json()
            events = [
                {
                    "name": ev.get("name"),
                    "event_key": ev.get("key"),
                    "start_date": ev.get("start_date"),
                    "end_date": ev.get("end_date"),
                    "location": ", ".join(filter(None, [ev.get("city"), ev.get("state_prov")])),
                    "week": ev.get("week"),
                    "year": ev.get("year"),
                }
                for ev in raw_events
            ]
        except Exception as e:
            return f"Error loading events from TBA: {e}"

    else:
        # Local logic for current or past specific year
        year = int(year)
        try:
            if year == current_year:
                event_iter = EVENT_DATABASE[year].items()
                for event_key, event in event_iter:
                    team_list = EVENT_TEAMS[year].get(event_key, [])
                    if any(t["tk"] == team_number for t in team_list):
                        events.append({
                            "name": event.get("n", ""),
                            "event_key": event_key,
                            "start_date": event.get("sd", ""),
                            "end_date": event.get("ed", ""),
                            "location": ", ".join(filter(None, [event.get("c", ""), event.get("s", "")])),
                            "week": None,  # Local data doesn't have week info
                            "year": year,
                        })
            else:
                _, year_event_data, year_event_teams, year_event_rankings, _, _ = load_year_data(year)
                for event_key, event in year_event_data.items():
                    team_list = year_event_teams.get(event_key, [])
                    if any(t["tk"] == team_number for t in team_list):
                        events.append({
                            "name": event.get("n", ""),
                            "event_key": event_key,
                            "start_date": event.get("sd", ""),
                            "end_date": event.get("ed", ""),
                            "location": ", ".join(filter(None, [event.get("c", ""), event.get("s", "")])),
                            "week": None,  # Local data doesn't have week info
                            "year": year,
                        })
        except Exception:
            return "Error loading local event data."

    # Sort by start date (most recent first)
    events.sort(key=lambda ev: ev.get("start_date", ""), reverse=True)

    def get_week_display(ev):
        """Get week display string for an event."""
        # For TBA API data, use the week field directly
        if ev.get("week") is not None:
            return f"Week {ev['week']}"
        elif ev.get("week") is None and is_history:
            return "Off-season"
        
        # For local data, calculate week from start date
        start_date = ev.get("start_date")
        year = ev.get("year")
        if not start_date or not year:
            return "N/A"
        
        try:
            # Convert start_date to date object for the existing get_week_number function
            if isinstance(start_date, str):
                event_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            else:
                event_date = start_date.date() if hasattr(start_date, 'date') else start_date
            
            week_num = get_week_number(event_date)
            if week_num is not None:
                return f"Week {week_num + 1}"  # Add 1 since get_week_number returns 0-based index
            else:
                return "Off-season"
        except:
            return "N/A"

    # Format for Dash table
    events_data = [
        {
            "event_name": f"[{ev['name']}](/event/{ev['event_key']})",
            "week": get_week_display(ev),
            "event_location": ev["location"],
            "start_date": format_human_date(ev["start_date"]),
            "end_date": format_human_date(ev["end_date"]),
        } for ev in events
    ]

    events_table = dash_table.DataTable(
        columns=[
            {"name": "Event Name", "id": "event_name", "presentation": "markdown"},
            {"name": "Location", "id": "event_location"},
            {"name": "Week", "id": "week"},
            {"name": "Start Date", "id": "start_date"},
            {"name": "End Date", "id": "end_date"},
        ],
        sort_action="native",
        sort_mode="multi",
        data=events_data,
        page_size=10,
        style_table={
            "overflowX": "auto",
            "borderRadius": "10px",
            "border": "none",
            "backgroundColor": "var(--card-bg)",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
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
            "backgroundColor": "var(--card-bg)",
            "textAlign": "center",
            "padding": "10px",
            "border": "none",
            "fontSize": "14px",
        },
        style_cell_conditional=[
            {"if": {"column_id": "event_name"}, "textAlign": "center"},
        ],
        style_data_conditional=[
            {"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}
        ],
    )

    return html.Div([events_table])

@app.callback(
    Output("team-awards-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data"),
    suppress_callback_exceptions=True,
)
def update_team_awards(active_tab, store_data):
    if active_tab != "awards-tab" or not store_data:
        return ""
    
    team = store_data.get("team_number")
    year = store_data.get("year")
    if not team:
        return "No team data available."
    
    def build_output(awards):
        if not awards:
            return "No awards data available."
        
        # Sort awards newest-first
        awards.sort(key=lambda a: a.get("year", 0), reverse=True)
        
        table_data = [
            {
                "award_name": aw.get("name", ""),
                "event_name": f"[{aw.get('event_key')}](/event/{aw.get('event_key')})",
                "award_year": aw.get("year", "")
            }
            for aw in awards
        ]
        
        # Build DataTable
        awards_table = dash_table.DataTable(
            columns=[
                {"name": "Award Name", "id": "award_name"},
                {"name": "Event", "id": "event_name", "presentation": "markdown"},
                {"name": "Year", "id": "award_year"},
            ],
            data=table_data,
            sort_action="native", sort_mode="multi",
            page_size=10,
            style_table={ 
                "overflowX": "auto", "borderRadius": "10px", "border": "none",
                "backgroundColor": "var(--card-bg)",
                "boxShadow": "0px 4px 8px rgba(0,0,0,0.1)"
            },
            style_header={ "backgroundColor": "var(--card-bg)",
                "fontWeight": "bold", "textAlign": "center",
                "borderBottom": "1px solid #ccc", "padding": "6px", "fontSize": "13px"
            },
            style_cell={ "backgroundColor": "var(--card-bg)",
                "textAlign": "center", "padding": "10px",
                "border": "none", "fontSize": "14px"
            },
            style_cell_conditional=[{"if": {"column_id": "award_name"}, "textAlign": "left"}],
            style_data_conditional=[
                {"if": {"state": "selected"},
                 "backgroundColor": "rgba(255,221,0,0.5)",
                 "border": "1px solid #FFCC00"}
            ],
        )
        
        # Blue banners: filter via keywords
        keywords = ["chairman's","impact","woodie flowers","winner"]
        banners = [
            {
                "award_name": aw["name"],
                "event_label": f"{aw['event_key']}",
                "event_key": aw["event_key"]
            }
            for aw in awards if any(k in aw["name"].lower() for k in keywords)
        ]
        
        banner_section = html.Div(
            [
                html.H4("Blue Banners", style={
                    "marginTop":"30px","marginBottom":"15px","color":"var(--text-primary)"
                }),
                html.Div(
                    [
                        html.A(
                            href=f"/event/{b['event_key']}",
                            children=html.Div([
                                html.Img(src="/assets/banner.png", style={"width":"120px","height":"auto"}),
                                html.Div([
                                    html.P(b['award_name'], style={
                                        "fontSize":"0.8rem","color":"white",
                                        "fontWeight":"bold","textAlign":"center",
                                        "marginBottom":"3px"
                                    }),
                                    html.P(b['event_label'], style={
                                        "fontSize":"0.6rem","color":"white","textAlign":"center"
                                    })
                                ], style={
                                    "position":"absolute","top":"50%","left":"50%",
                                    "transform":"translate(-50%,-50%)"
                                })
                            ], style={"position":"relative","marginBottom":"15px"}),
                            style={"textDecoration":"none"},
                        ) for b in banners
                    ],
                    style={"display":"flex","flexWrap":"wrap","justifyContent":"center","gap":"10px"}
                )
            ], style={
                "marginBottom":"15px","borderRadius":"8px",
                "backgroundColor":"var(--card-bg)","padding":"10px"
            }
        ) if banners else html.Div()
        
        return html.Div([awards_table, banner_section])

    # Only fetch history from TBA API
    if not year or str(year).lower() == "history":
        team_key = f"frc{team}"
        tba_keys = os.environ.get("TBA_API_KEYS", "").split(",")
        tba_keys = [k.strip() for k in tba_keys if k.strip()]
        if not tba_keys:
            return "No TBA API key found."
        key = random.choice(tba_keys)
        url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/awards"
        headers = {"X-TBA-Auth-Key": key}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
            awards = [
                {
                    "event_key": aw["event_key"],
                    "name": aw["name"],
                    "year": aw["year"]
                }
                for aw in raw if any(rec.get("team_key") == team_key for rec in aw.get("recipient_list", []))
            ]
            return build_output(awards)
        except Exception as e:
            return f"Error loading awards from TBA: {e}"
    
    # Otherwise, use local logic for single year
    awards = []
    try:
        if int(year) == current_year:
            awards = [
                {"event_key": aw["ek"], "name": aw["an"], "year": aw["y"]}
                for aw in EVENT_AWARDS
                if aw.get("tk") == int(team) and aw.get("y") == current_year
            ]
        else:
            _, _, _, _, aya, _ = load_year_data(int(year))
            source = aya.values() if isinstance(aya, dict) else aya
            awards = [
                {"event_key": aw["ek"], "name": aw["an"], "year": aw["y"]}
                for aw in source if aw.get("tk") == int(team)
            ]
    except Exception:
        return "Error processing awards locally."

    return build_output(awards)

@app.callback(
    Output("event-alliances-content", "children"),
    Input("event-data-tabs", "active_tab"),
    State("store-event-year", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def load_event_alliances(active_tab, event_year, pathname):
    if active_tab != "alliances":
        return ""
    # Extract event key from URL
    if not pathname or "/event/" not in pathname:
        return "No event selected."
    event_key = pathname.split("/event/")[-1].split("/")[0]
    tba_keys = os.environ.get("TBA_API_KEYS", "").split(",")
    tba_keys = [k.strip() for k in tba_keys if k.strip()]
    if not tba_keys:
        return "No TBA API key found."
    tba_key = random.choice(tba_keys)
    tba_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams/statuses"
    headers = {"X-TBA-Auth-Key": tba_key}
    try:
        resp = requests.get(tba_url, headers=headers, timeout=10)
        data = resp.json()
    except Exception as e:
        return f"Error loading alliances: {e}"

    # Parse alliances
    alliances = {}
    for team, info in data.items():
        alliance = info.get("alliance")
        if alliance:
            number = alliance.get("number")
            if number not in alliances:
                alliances[number] = []
            alliances[number].append({
                "team": team,
                "pick": alliance.get("pick"),
                "name": alliance.get("name"),
                "status": info.get("alliance_status_str"),
                "playoff": info.get("playoff_status_str"),
            })

    # --- Bracket Visuals ---
    round_order = [
        "Winner", "Finals", "Round 5", "Round 4", "Round 3", "Round 2", "Round 1"
    ]
    round_colors = {
        "Winner": "#FFD700",  # Gold
        "Finals": "#C0C0C0",  # Silver
        "Round 5": "#1976d2",
        "Round 4": "#388e3c",
        "Round 3": "#f9a825",
        "Round 2": "#ef6c00",
        "Round 1": "#c62828",
        "Eliminated": "#888"
    }
    def get_round_from_playoff(playoff_str):
        if "Won the event" in playoff_str:
            return "Winner"
        for r in round_order:
            if r in playoff_str:
                return r
        if "Finals" in playoff_str:
            return "Finals"
        return "Eliminated"
    def alliance_box(alliance_num, members):
        members_sorted = sorted(members, key=lambda x: x["pick"] if x["pick"] is not None else 99)
        captain = next((m for m in members_sorted if m["pick"] == 0), None)
        playoff_str = (captain or members_sorted[0])["playoff"] or ""
        round_name = get_round_from_playoff(playoff_str)
        is_winner = round_name == "Winner"
        badge_bg = "var(--navbar-hover)" if is_winner else "var(--border-color)"
        badge_text = "var(--text-primary)"
        border_color = "var(--navbar-hover)" if is_winner else "var(--border-color)"
        # Badge
        badge = html.Div(round_name, style={
            "background": badge_bg,
            "color": "black" if is_winner else badge_text,
            "padding": "6px 18px",
            "borderRadius": "8px",
            "fontWeight": "bold",
            "marginRight": "14px",
            "display": "flex",
            "alignItems": "center",
            "minWidth": "70px",
            "justifyContent": "center"
        }, className="alliance-badge")
        # Team boxes
        team_boxes = [
            html.Div([
                html.B("C" if m["pick"] == 0 else f"P{m['pick']}", style={"display": "block", "fontSize": "0.9em", "color": badge_text}),
                html.Br(),
                html.A(
                    m["team"].replace("frc", ""),
                    href=f"https://www.peekorobo.com/team/{m['team'].replace('frc','')}",
                    target="_blank",
                    style={
                        "color": "#FFDD00" if m["pick"] == 0 else badge_text,
                        "textDecoration": "underline",
                        "fontWeight": "bold",
                        "fontSize": "1.1em"
                    }
                ),
            ], style={
                "background": "var(--card-bg)",
                "color": badge_text,
                "border": f"2px solid #FFDD00" if m["pick"] == 0 else f"1px solid var(--border-color)",
                "borderRadius": "6px",
                "padding": "6px 10px",
                "margin": "2px",
                "fontWeight": "bold",
                "fontSize": "1.1em",
                "textAlign": "center",
                "minWidth": "48px"
            }, className="alliance-team-box") for m in members_sorted
        ]
        # Row: badge + team boxes
        row = html.Div([
            badge,
            html.Div(team_boxes, style={"display": "flex", "gap": "8px"})
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"})
        # Progress/description
        progress = html.Div([
            dcc.Markdown(playoff_str, dangerously_allow_html=True, style={"color": "var(--text-primary)"}, className="markdown-text")
        ], style={"marginLeft": "2px", "color": "var(--text-secondary)", "fontSize": "0.95em"})
        return html.Div([
            html.Div(f"Alliance {alliance_num}", style={"fontWeight": "bold", "fontSize": "1.2em", "marginBottom": "4px", "color": "var(--text-primary)"}),
            row,
            progress
        ], style={
            "background": "var(--card-bg)",
            "border": f"3px solid {border_color}",
            "borderRadius": "12px",
            "padding": "12px 18px",
            "marginBottom": "18px",
            "boxShadow": "0 2px 8px #0004",
            "minWidth": "0"
        }, className="alliance-card")
    alliance_bracket = [
        alliance_box(number, members)
        for number, members in sorted(alliances.items())
    ]
    # Grid: 2 per row, always 4 rows for 8 alliances
    grid_style = {
        "display": "grid",
        # Remove gridTemplateColumns from here; move to CSS
        "gap": "20px 18px",
        "maxWidth": "1250px",
        "margin": "0 auto",
        "marginTop": "18px"
    }
    return html.Div(alliance_bracket, style=grid_style, className="alliance-bracket-grid")

@app.callback(
    Output("event-metrics-content", "children"),
    Input("event-data-tabs", "active_tab"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def load_event_metrics(active_tab, pathname):
    if active_tab != "metrics":
        return ""
    
    # Extract event key from URL
    if not pathname or "/event/" not in pathname:
        return "No event selected."
    event_key = pathname.split("/event/")[-1].split("/")[0]
    
    # Get TBA API key
    tba_keys = os.environ.get("TBA_API_KEYS", "").split(",")
    tba_keys = [k.strip() for k in tba_keys if k.strip()]
    if not tba_keys:
        return "No TBA API key found."
    
    tba_key = random.choice(tba_keys)
    
    # Fetch both COPRs and OPRs data
    coprs_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/coprs"
    oprs_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
    headers = {"X-TBA-Auth-Key": tba_key}
    
    all_metrics = {}
    
    # Fetch COPRs data
    try:
        coprs_resp = requests.get(coprs_url, headers=headers, timeout=10)
        coprs_data = coprs_resp.json()
        if coprs_data:
            all_metrics.update(coprs_data)
    except Exception as e:
        print(f"Error loading COPRs data: {e}")
    
    # Fetch OPRs data
    try:
        oprs_resp = requests.get(oprs_url, headers=headers, timeout=10)
        oprs_data = oprs_resp.json()
        if oprs_data:
            all_metrics.update(oprs_data)
    except Exception as e:
        print(f"Error loading OPRs data: {e}")
    
    if not all_metrics:
        return "No metrics data available for this event."
    
    # Create dropdown options from available metrics
    metric_options = [{"label": metric, "value": metric} for metric in all_metrics.keys()]
    
    # Create the layout with dropdown and table
    layout = html.Div([
        html.P("Select an option to view team performance metrics:", style={"marginBottom": "15px", "color": "var(--text-secondary)"}),
        dcc.Dropdown(
            id="metrics-metric-dropdown",
            options=metric_options,
            placeholder="Select a metric...",
            style={"marginBottom": "20px"},
            className="custom-input-box"
        ),
        html.Div(id="metrics-table-container", children="Select a metric to view data.")
    ])
    
    return layout

@app.callback(
    Output("metrics-table-container", "children"),
    Input("metrics-metric-dropdown", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def update_metrics_table(selected_metric, pathname):
    if not selected_metric or not pathname or "/event/" not in pathname:
        return "Select a metric to view data."
    
    event_key = pathname.split("/event/")[-1].split("/")[0]
    
    # Get TBA API key
    tba_keys = os.environ.get("TBA_API_KEYS", "").split(",")
    tba_keys = [k.strip() for k in tba_keys if k.strip()]
    if not tba_keys:
        return "No TBA API key found."
    
    tba_key = random.choice(tba_keys)
    
    # Determine which API endpoint to use based on the metric
    if selected_metric in ["oprs", "dprs", "ccwms"]:
        tba_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
    else:
        tba_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/coprs"
    
    headers = {"X-TBA-Auth-Key": tba_key}
    
    try:
        resp = requests.get(tba_url, headers=headers, timeout=10)
        data = resp.json()
    except Exception as e:
        return f"Error loading metrics data: {e}"
    
    if not data or selected_metric not in data:
        return f"No data available for {selected_metric}."
    
    metric_data = data[selected_metric]
    
    # Convert data to table format
    table_data = []
    for team_key, value in metric_data.items():
        team_number = team_key.replace("frc", "")
        table_data.append({
            "Team": f"[{team_number}](/team/{team_number}/{current_year})",
            "Value": f"{value:.3f}" if isinstance(value, (int, float)) else str(value)
        })
    
    # Sort by value (descending)
    table_data.sort(key=lambda x: float(x["Value"]) if x["Value"].replace(".", "").replace("-", "").isdigit() else 0, reverse=True)
    
    # Create DataTable
    table = dash_table.DataTable(
        columns=[
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": selected_metric, "id": "Value", "type": "numeric"}
        ],
        data=table_data,
        sort_action="native",
        sort_mode="single",
        page_size=20,
        style_table={
            "overflowX": "auto", 
            "borderRadius": "10px", 
            "border": "none", 
            "backgroundColor": "var(--card-bg)",
            "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"
        },
        style_header={
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text-primary)",
            "fontWeight": "bold",
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",
            "padding": "8px",
            "fontSize": "13px"
        },
        style_cell={
            "textAlign": "center",
            "padding": "8px",
            "border": "none",
            "fontSize": "14px",
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text-primary)"
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgba(0, 0, 0, 0.05)",
            },
        ]
    )
    
    return table

@app.callback(
    Output("insights-table-container", "children"),
    Input("insights-dropdown", "value"),
    State("url", "pathname"),
    State("challenge-event-teams-db", "data"),
    State("challenge-event-db", "data"),
)
def update_insights_table(selected_insight, pathname, event_teams, event_db):
    # Helper to get nickname from any event in event_teams
    def find_nickname_across_events(event_teams, team_number):
        for teams in event_teams.values():
            for t in teams:
                if str(t.get("tk")) == str(team_number):
                    return t.get("nn", "")
        return ""
    # Extract year from pathname (should be /challenge/<year>)
    try:
        year = int(pathname.strip("/").split("/")[-1])
    except Exception:
        return None
    # Load insights
    try:
        with open(os.path.join("data", "insights.json"), "r", encoding="utf-8") as f:
            all_insights = json.load(f)
        year_insights = all_insights.get(str(year), [])
    except Exception:
        return html.Div("No insights data available.", style={"color": "#c00"})
    # Find the selected insight
    insight = next((i for i in year_insights if i.get("name") == selected_insight), None)
    if not insight or not insight.get("data"):
        return html.Div("No data for this insight.", style={"color": "#c00"})
    data = insight["data"]
    # Try to find a rankings list
    rankings = data.get("rankings")
    key_type = data.get("key_type", "")
    if not rankings or not isinstance(rankings, list) or len(rankings) == 0:
        return html.Div("No rankings data available for this insight.", style={"color": "#c00"})
    # Build table rows
    rows = []
    for r in rankings:
        keys = r.get("keys", [])
        value = r.get("value", "")
        if isinstance(keys, list):
            for k in keys:
                if key_type == "team" and k.startswith("frc"):
                    num = k[3:]
                    nickname = find_nickname_across_events(event_teams, num)
                    label = f"{num} | {nickname}" if nickname else num
                    link = f"/team/{num}/{year}"
                    rows.append({"Team": f"[{label}]({link})", "Value": value})
                elif key_type == "event":
                    event_key = k
                    event_name = event_db.get(event_key, "") if event_db else ""
                    label = f"{event_key} | {event_name}" if event_name else event_key
                    link = f"/event/{event_key}"
                    rows.append({"Event": f"[{label}]({link})", "Value": value})
                elif key_type == "match":
                    match_key = k
                    event_key = match_key.split('_')[0] if '_' in match_key else match_key[:8]
                    match_part = match_key.split('_')[1] if '_' in match_key else match_key[8:]
                    event_name = event_db.get(event_key, "") if event_db else ""
                    m = re.match(r"([a-z]+)(\d+)?m?(\d+)?", match_part.lower())
                    match_label = match_part.upper()
                    match_url_part = match_part.upper()
                    if m:
                        mtype, setnum, matchnum = m.groups()
                        mtype = mtype.upper()
                        if mtype == "QM":
                            match_label = f"Qualification {setnum}" if setnum else "Qualification"
                        elif mtype == "SF":
                            match_label = f"SF {setnum}" if setnum else "SF"
                            if setnum:
                                match_url_part = f"SF{setnum}"
                        elif mtype == "QF":
                            match_label = f"QF {setnum} Match {matchnum}" if setnum and matchnum else f"QF {setnum or ''}"
                        elif mtype == "F":
                            match_label = f"Finals {setnum} Match {matchnum}" if setnum and matchnum else f"Finals {setnum or ''}"
                        else:
                            match_label = match_part.upper()
                    display = f"{event_key} | {event_name} | {match_label}" if event_name else f"{event_key} | {match_label}"
                    link = f"/match/{event_key}/{match_url_part}"
                    rows.append({"Match": f"[{display}]({link})", "Value": value})
                else:
                    rows.append({"Keys": k, "Value": value})
        else:
            k = str(keys)
            if key_type == "team" and k.startswith("frc"):
                num = k[3:]
                nickname = find_nickname_across_events(event_teams, num)
                label = f"{num} | {nickname}" if nickname else num
                link = f"/team/{num}/{year}"
                rows.append({"Team": f"[{label}]({link})", "Value": value})
            elif key_type == "event":
                event_key = k
                event_name = event_db.get(event_key, "") if event_db else ""
                label = f"{event_key} | {event_name}" if event_name else event_key
                link = f"/event/{event_key}"
                rows.append({"Event": f"[{label}]({link})", "Value": value})
            elif key_type == "match":
                match_key = k
                event_key = match_key.split('_')[0] if '_' in match_key else match_key[:8]
                match_part = match_key.split('_')[1] if '_' in match_key else match_key[8:]
                event_name = event_db.get(event_key, "") if event_db else ""
                label = match_part.upper() if match_part else match_key[8:].upper()
                match_url_part = label
                if label.startswith('SF'):
                    match_num = ''.join(filter(str.isdigit, label[2:]))
                    match_label = f"Semi-Finals {match_num}" if match_num else "SF"
                    if match_num:
                        match_url_part = f"SF{match_num}"
                elif label.startswith('QF'):
                    match_num = ''.join(filter(str.isdigit, label[2:]))
                    match_label = f"Quarter-Finals {match_num}" if match_num else "QF"
                elif label.startswith('F'):
                    match_num = ''.join(filter(str.isdigit, label[1:]))
                    match_label = f"Finals {match_num}" if match_num else "Finals"
                elif label.startswith('QM'):
                    match_num = ''.join(filter(str.isdigit, label[2:]))
                    match_label = f"Qualification {match_num}" if match_num else "Qualification"
                else:
                    match_label = label
                display = f"{event_key} | {event_name} | {match_label}" if event_name else f"{event_key} | {match_label}"
                link = f"/match/{event_key}/{match_url_part}"
                rows.append({"Match": f"[{display}]({link})", "Value": value})
            else:
                rows.append({"Keys": k, "Value": value})
    # Set columns
    if key_type == "team":
        columns = [
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Value", "id": "Value"},
        ]
    elif key_type == "event":
        columns = [
            {"name": "Event", "id": "Event", "presentation": "markdown"},
            {"name": "Value", "id": "Value"},
        ]
    elif key_type == "match":
        columns = [
            {"name": "Match", "id": "Match", "presentation": "markdown"},
            {"name": "Value", "id": "Value"},
        ]
    else:
        columns = [
            {"name": "Keys", "id": "Keys"},
            {"name": "Value", "id": "Value"},
        ]
    return dash_table.DataTable(
        columns=columns,
        data=rows,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
        style_header={
            "backgroundColor": "var(--card-bg)",
            "fontWeight": "bold",
            "textAlign": "center",
            "borderBottom": "1px solid #ccc",
            "padding": "6px",
            "fontSize": "13px",
        },
        style_cell={
            "backgroundColor": "var(--card-bg)",
            "textAlign": "center",
            "padding": "10px",
            "border": "none",
            "fontSize": "14px",
        },
        page_size=20,
        style_as_list_view=True,
    )

# Callback for collapsible team cards
@app.callback(
    [Output({"type": "team-card-arrow", "index": MATCH}, "children"),
     Output({"type": "team-card-body", "index": MATCH}, "style")],
    [Input({"type": "team-card-header", "index": MATCH}, "n_clicks")],
    [State({"type": "team-card-body", "index": MATCH}, "style")],
    prevent_initial_call=True
)
def toggle_team_card_collapse(n_clicks, current_style):
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    # Get current state from style
    current_max_height = current_style.get("maxHeight", "2000px")
    is_collapsed = current_max_height == "0px"
    
    if is_collapsed:
        # Expand
        new_style = {
            "overflow": "hidden",
            "transition": "max-height 0.3s ease, opacity 0.3s ease",
            "maxHeight": "2000px",
            "opacity": "1"
        }
        arrow = "▼"
    else:
        # Collapse
        new_style = {
            "overflow": "hidden",
            "transition": "max-height 0.3s ease, opacity 0.3s ease",
            "maxHeight": "0px",
            "opacity": "0"
        }
        arrow = "▲"
    
    return arrow, new_style

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=False)