import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc, dash_table, ctx, ALL, MATCH, no_update, callback_context
from dash.dependencies import Input, Output, State

import flask
from flask import session
from auth import register_user, verify_user, hash_password

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

from datagather import load_data_current_year,load_search_data,load_year_data,get_team_avatar,DatabaseConnection,get_team_years_participated

from layouts import create_team_card_spotlight,create_team_card_spotlight_event,insights_layout,insights_details_layout,team_layout,match_layout,user_profile_layout,home_layout,map_layout,login_layout,register_layout,create_team_card,teams_layout,event_layout,ace_legend_layout,events_layout,peekolive_layout,build_peekolive_grid,build_peekolive_layout_with_events,raw_vs_ace_blog_layout,blog_index_layout,features_blog_layout,predictions_blog_layout,higher_lower_layout

from utils import format_human_date,predict_win_probability,calculate_all_ranks,calculate_single_rank,get_user_avatar,get_epa_styling,compute_percentiles,get_contrast_text_color,universal_profile_icon_or_toast,get_week_number,event_card,truncate_name,get_team_data_with_fallback

from dotenv import load_dotenv
load_dotenv()

# Load optimized data: current year data globally + search data with all events
TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES = load_data_current_year()
SEARCH_TEAM_DATA, SEARCH_EVENT_DATA = load_search_data()


# Store app startup time for "Last Updated" indicator
APP_STARTUP_TIME = datetime.now()

current_year = 2026


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

app.clientside_callback(
    """
    function(theme_clicks, page_load_clicks) {
        // Handle page load - just return the current theme
        if (page_load_clicks && !theme_clicks) {
            const savedTheme = localStorage.getItem('theme') || 'dark';
            return savedTheme;
        }
        
        // Handle theme toggle - update both theme AND icon in same operation
        if (theme_clicks) {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            // Update theme
            document.documentElement.setAttribute('data-theme', newTheme);
            
            // Update icon IMMEDIATELY - no delays, no separate operations
            const icon = document.querySelector('#theme-toggle i');
            if (icon) {
                icon.className = newTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
            }
            
            // Save to localStorage
            localStorage.setItem('theme', newTheme);
            
            return newTheme;
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("theme-store", "data"),
    [Input("theme-toggle", "n_clicks"),
     Input("page-load-trigger", "n_clicks")],
    prevent_initial_call=True
)

# Callback to update the "Last Updated" text
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

# Callback to update navigation link styles based on current page
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
    Output("register-popup", "is_open"),
    [Input("url", "pathname"),
     Input("register-popup", "n_dismiss")]
)
def toggle_register_popup(pathname, n_dismiss):
    """Hide popup on login and register pages, or if user has dismissed it"""
    # If user dismissed the popup, mark it in session
    if n_dismiss and n_dismiss > 0:
        session["popup_dismissed"] = True
    
    # Hide popup on login and register pages
    if pathname == "/login" or pathname == "/register":
        return False
    
    # Only show if user is not logged in AND hasn't dismissed it
    if "user_id" in session:
        return False
    if session.get("popup_dismissed", False):
        return False
    return True

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
        return map_layout()
    
    if pathname == "/events":
        return events_layout()
    
    if pathname == "/events/peekolive":
        return events_layout(active_tab="peekolive-tab")
    
    if pathname.startswith("/events/peekolive/"):
        # Extract event_key from pathname
        event_key = pathname.split("/events/peekolive/")[-1]
        from layouts import focused_peekolive_layout
        return focused_peekolive_layout(event_key)
    
    if pathname == "/events/insights":
        return events_layout(active_tab="table-tab")

    if pathname == "/login":
        return login_layout()
    
    if pathname == "/register":
        return register_layout()

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

    if pathname.startswith("/match/"):
        # /match/<event_key>/<match_key>
        parts = pathname.split("/")
        if len(parts) >= 4:
            event_key = parts[2]
            match_key = parts[3]
            return match_layout(event_key, match_key)
        else:
            return dbc.Alert("Invalid match URL.", color="danger")

    if pathname == "/blog":
        return blog_index_layout()
    
    if pathname == "/blog/raw-vs-ace":
        return raw_vs_ace_blog_layout()
    
    if pathname == "/blog/features":
        return features_blog_layout()
    
    if pathname == "/blog/predictions":
        return predictions_blog_layout()
    
    if pathname == "/higher-lower":
        return higher_lower_layout()

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
    State("edit-email", "value"),
    State("edit-password", "value"),
    State("edit-bg-color", "value"),
    State("edit-role", "value"),
    State("edit-team", "value"),
    State("edit-bio", "value"),
    State("edit-avatar-key", "value"),
    State("user-session", "data")
)
def handle_profile_edit(
    edit_clicks, save_clicks, editing_hidden,
    username, email, password, color, role, team, bio, avatar_key_selected,
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

                # Check if email is already in use by another user
                if email and email.strip():
                    cur.execute("SELECT id FROM users WHERE LOWER(email) = %s AND id != %s", (email.lower().strip(), user_id))
                    if cur.fetchone():
                        return [dash.no_update] * 18
                
                # Validate password if provided
                if password and password.strip():
                    password_str = password.strip()
                    if len(password_str) < 8 or not any(c.isupper() for c in password_str) or not any(c.islower() for c in password_str) or not any(c.isdigit() for c in password_str):
                        return [dash.no_update] * 18
                    password_hash = hash_password(password_str)
                    # Update with password
                    cur.execute("""
                        UPDATE users
                        SET username = %s,
                            email = %s,
                            password_hash = %s,
                            role = %s,
                            team = %s,
                            bio = %s,
                            avatar_key = %s,
                            color = %s
                        WHERE id = %s
                    """, (username, email.strip() if email else None, password_hash, role, team, bio, avatar_key_selected, color, user_id))
                else:
                    # Update without password
                    cur.execute("""
                        UPDATE users
                        SET username = %s,
                            email = %s,
                            role = %s,
                            team = %s,
                            bio = %s,
                            avatar_key = %s,
                            color = %s
                        WHERE id = %s
                    """, (username, email.strip() if email else None, role, team, bio, avatar_key_selected, color, user_id))
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
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True
)
def handle_login(login_clicks, username, password):
    if not username or not password:
        return "Please enter both username and password.", dash.no_update

    valid, user_id = verify_user(username, password)
    if valid:
        session["user_id"] = user_id
        session["username"] = username
        redirect_url = "/user"
        return f"✅ Welcome, {username}!", redirect_url
    else:
        return "❌ Invalid username or password.", dash.no_update

@app.callback(
    Output("register-message", "children"),
    Output("register-redirect", "href"),
    Input("register-btn", "n_clicks"),
    State("register-username", "value"),
    State("register-email", "value"),
    State("register-password", "value"),
    prevent_initial_call=True
)
def handle_register(register_clicks, username, email, password):
    if not username or not password:
        return "Please enter both username and password.", dash.no_update

    success, message = register_user(username.strip(), password.strip(), email.strip() if email else None)
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

# Callback to update URL when tabs are clicked
@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("events-tabs", "active_tab"),
    prevent_initial_call=True
)
def update_events_url(active_tab):
    if active_tab == "peekolive-tab":
        return "/events/peekolive"
    elif active_tab == "table-tab":
        return "/events/insights"
    else:  # cards-tab
        return "/events"

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
    if active_tab == "peekolive-tab":
        # Handle search filtering for PeekoLive tab
        from layouts import get_peekolive_events_categorized
        
        # Detect team from search query
        detected_team = None
        try:
            if search_query:
                s = str(search_query).lower().strip()
                # Only detect team if it's explicitly "frc" prefixed or a standalone number
            
                frc_match = re.search(r"frc(\d{1,5})", s)
                if frc_match:
                    detected_team = frc_match.group(1)
                else:
                    # Only treat as team if it's a standalone number (not part of a larger string)
                    # This prevents years like "2024" from being treated as team 2024
                    if re.fullmatch(r"\d{1,5}", s):
                        detected_team = s
        except Exception:
            detected_team = None
        
        # Get categorized events
        events_data = get_peekolive_events_categorized(include_all=bool(search_query) or bool(detected_team))
        
        # Apply team filtering if a team was detected
        if detected_team:
            try:
                t_str = str(detected_team)
                # Filter each category by team participation
                for category in ["completed", "ongoing", "upcoming"]:
                    filtered_events = []
                    for ev in events_data[category]:
                        evk = ev.get("event_key")
                        found = False
                        # Search across all years for the event key
                        for _, year_map in (EVENT_TEAMS or {}).items():
                            teams = (year_map or {}).get(evk, [])
                            if any(str(t.get("tk")) == t_str for t in teams):
                                found = True
                                break
                        if found:
                            filtered_events.append(ev)
                    events_data[category] = filtered_events
            except Exception:
                pass
        # Apply text search if no team was detected and there's a search query
        elif search_query:
            q = str(search_query).lower()
            # Filter each category by text search
            for category in ["completed", "ongoing", "upcoming"]:
                events_data[category] = [
                    ev for ev in events_data[category]
                    if q in (ev.get("name", "").lower()) or q in (ev.get("location", "").lower())
                ]
        
        # Build the PeekoLive layout with filtered events
        return build_peekolive_layout_with_events(events_data, detected_team), dash.no_update, dash.no_update
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
            return html.Div(f"Error loading data for year {selected_year}: {str(e)}"), [], "▼"
    
    if not events_data:
        return html.Div("No events available."), [], "▼"

    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    def get_event_district(event):
        """Get district for an event using stored district data."""
        district_abbrev = (event.get("da") or "").strip().upper()
        if district_abbrev:
            return district_abbrev

        district_key = (event.get("dk") or "").strip()
        return district_key[-2:].upper() if len(district_key) >= 2 else None

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

    def compute_event_insights_from_data(event_teams, event_database, team_database, selected_year, filtered_event_keys=None):
        rows = []
    
        teams_by_event = event_teams
        events = event_database
    
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
                team_data, actual_year = get_team_data_with_fallback(team_number, selected_year, team_database)
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
    
        # Use standard styling for the ACE columns
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

        # Export container (at top)
        export_container = html.Div([
            event_export_dropdown,
            dcc.Download(id="download-event-insights-csv"),
            dcc.Download(id="download-event-insights-excel"),
            dcc.Download(id="download-event-insights-tsv"),
            dcc.Download(id="download-event-insights-json"),
            dcc.Download(id="download-event-insights-html"),
            dcc.Download(id="download-event-insights-latex"),
        ], style={"textAlign": "right", "marginBottom": "10px"})
        
        # Rows per page container (at bottom)
        rows_per_page_container = html.Div([
            html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
            dcc.Dropdown(
                id="event-insights-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "25", "value": 25},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                ],
                value=25,
                clearable=False,
                style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
            ),
        ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})

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
                page_size=25,
                page_current=0,
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
            ),
            rows_per_page_container
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
    
    # Create export dropdown buttons for cards tab
    cards_export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="event-cards-export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="event-cards-export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="event-cards-export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="event-cards-export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="event-cards-export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="event-cards-export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    # Export container
    cards_export_container = html.Div([
        cards_export_dropdown,
        dcc.Download(id="download-event-cards-csv"),
        dcc.Download(id="download-event-cards-excel"),
        dcc.Download(id="download-event-cards-tsv"),
        dcc.Download(id="download-event-cards-json"),
        dcc.Download(id="download-event-cards-html"),
        dcc.Download(id="download-event-cards-latex"),
    ], style={"textAlign": "right", "marginBottom": "10px"})
    
    # Store events data for export
    events_data_store = dcc.Store(id="event-cards-data-store", data=events_data)
    
    return html.Div([
        events_data_store,
        cards_export_container,
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
        
    # Sort by ACE to calculate ranks
    team_epas.sort(key=lambda x: x[1], reverse=True)
    rank_map = {tnum: i+1 for i, (tnum, _) in enumerate(team_epas)}

    # Get all performance values for percentile calculations
    ace_values = [data.get("epa", 0) for data in epa_data.values()]
    confidence_values = [data.get("confidence", 0) for data in epa_data.values()]
    auto_values = [data.get("auto_epa", 0) for data in epa_data.values()]
    teleop_values = [data.get("teleop_epa", 0) for data in epa_data.values()]
    endgame_values = [data.get("endgame_epa", 0) for data in epa_data.values()]

    percentiles_dict = {
        "ACE": compute_percentiles(ace_values),
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

            nickname_safe = nickname.replace('"', "'")
            truncated = truncate_name(nickname)
            nickname_link = f'[{truncated}](/team/{tstr}/{event_year} "{nickname_safe}")'
            data_rows.append({
                "Rank": rank_info.get("rk", None),
                "Team #": int(team_num) if team_num else 0,
                "Nickname": nickname_link,
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
            {"name": "Team #", "id": "Team #", "type": "numeric"},
            {"name": "Nickname", "id": "Nickname", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins", "type": "numeric"},
            {"name": "Losses", "id": "Losses", "type": "numeric"},
            {"name": "Ties", "id": "Ties", "type": "numeric"},
            {"name": "DQ", "id": "DQ", "type": "numeric"},
            {"name": "ACE Rank", "id": "ACE Rank", "type": "numeric"},
            {"name": "ACE", "id": "ACE", "type": "numeric"},
        ]

        # Export dropdown for rankings
        rankings_export_dropdown = dbc.DropdownMenu(
            label="Export",
            color="primary",
            className="me-2",
            children=[
                dbc.DropdownMenuItem("Export as CSV", id="event-rankings-export-csv-dropdown"),
                dbc.DropdownMenuItem("Export as TSV", id="event-rankings-export-tsv-dropdown"),
                dbc.DropdownMenuItem("Export as Excel", id="event-rankings-export-excel-dropdown"),
                dbc.DropdownMenuItem("Export as JSON", id="event-rankings-export-json-dropdown"),
                dbc.DropdownMenuItem("Export as HTML", id="event-rankings-export-html-dropdown"),
                dbc.DropdownMenuItem("Export as LaTeX", id="event-rankings-export-latex-dropdown"),
            ],
            toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
            style={"display": "inline-block"}
        )

        # Export container (at top)
        rankings_export_container = html.Div([
            rankings_export_dropdown,
            dcc.Download(id="download-event-rankings-csv"),
            dcc.Download(id="download-event-rankings-excel"),
            dcc.Download(id="download-event-rankings-tsv"),
            dcc.Download(id="download-event-rankings-json"),
            dcc.Download(id="download-event-rankings-html"),
            dcc.Download(id="download-event-rankings-latex"),
        ], style={"textAlign": "right", "marginBottom": "10px"})
        
        # Rows per page container (at bottom)
        rankings_rows_per_page_container = html.Div([
            html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
            dcc.Dropdown(
                id="event-rankings-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "25", "value": 25},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                ],
                value=10,
                clearable=False,
                style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
            ),
        ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})

        # Store rankings data for export
        rankings_data_store = dcc.Store(id="event-rankings-data-store", data=data_rows)

        return html.Div([
            rankings_data_store,
            ace_legend_layout(),
            rankings_export_container,
            dash_table.DataTable(
                id="event-rankings-table",
                columns=columns,
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                filter_options={"case": "insensitive"},
                data=data_rows,
                page_size=10,
                page_current=0,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_data_conditional=style_data_conditional,
                style_filter={
                    "backgroundColor": "var(--input-bg)",
                    "color": "var(--text-primary)",
                    "borderColor": "var(--input-border)",
                }
            ),
            rankings_rows_per_page_container
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

        # Calculate global rankings for teams in the event
        if event_year == current_year:
            # Use global database for current year
            global_teams_data = list(TEAM_DATABASE.get(event_year, {}).values())
        else:
            # For other years, use the year_team_data
            global_teams_data = list(year_team_data.get(event_year, {}).values())
        
        # Calculate global rankings
        global_teams_data.sort(key=lambda t: t.get("epa", 0), reverse=True)
        global_rank_map = {t.get("team_number"): i + 1 for i, t in enumerate(global_teams_data)}
        
        # Add global rankings to year_team_data
        for team_num, team_data in year_team_data.get(event_year, {}).items():
            if team_data:
                team_data["global_rank"] = global_rank_map.get(team_num, "N/A")
        
        # Sort teams by overall ACE from year_team_database for spotlight cards
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
        # For each team, get their matches, compute average predicted opponent ACE, avg win prob, hardest/easiest match
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
                # Opponent ACE
                opp_ace = 0
                opp_count = 0
                for opp in opp_teams:
                    opp_ace += epa_data.get(str(opp), {}).get("epa", 0)
                    opp_count += 1
                avg_opp_ace = opp_ace / opp_count if opp_count else 0
                opp_aces.append(avg_opp_ace)
                # Win probability
                red_info = [
                    {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                    for t in m.get("rt", "").split(",") if t.strip().isdigit()
                ]
                blue_info = [
                    {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                    for t in m.get("bt", "").split(",") if t.strip().isdigit()
                ]
                p_red, p_blue = predict_win_probability(red_info, blue_info)
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
            nickname_safe = nickname.replace('"', "'")
            truncated = truncate_name(nickname)
            nickname_link = f'[{truncated}](/team/{team_num}/{event_year} "{nickname_safe}")'
            team_sos_rows.append({
                "Team #": int(team_num_int) if team_num_int else 0,
                "Nickname": nickname_link,
                "SoS": round(sos_metric, 2),
                "Avg Opponent ACE": round(avg_opp_ace, 2),
                "Avg Win Prob": round(avg_win_prob, 2),
                "Hardest Match": match_label(hardest),
                "Hardest Win Prob": round(hardest_prob, 2),
                "Easiest Match": match_label(easiest),
                "Easiest Win Prob": round(easiest_prob, 2),
                "# Matches": len(team_matches),
            })
        # Sort by SoS (ascending: hardest at bottom, easiest at top)
        team_sos_rows.sort(key=lambda r: r["SoS"], reverse=True)
        sos_columns = [
            {"name": "Team #", "id": "Team #", "type": "numeric"},
            {"name": "Nickname", "id": "Nickname", "presentation": "markdown"},
            {"name": "SoS", "id": "SoS", "type": "numeric"},
            {"name": "Avg Opponent ACE", "id": "Avg Opponent ACE", "type": "numeric"},
            {"name": "Avg Win Prob", "id": "Avg Win Prob", "type": "numeric"},
            {"name": "Hardest Match", "id": "Hardest Match", "presentation": "markdown"},
            {"name": "Hardest Win Prob", "id": "Hardest Win Prob", "type": "numeric"},
            {"name": "Easiest Match", "id": "Easiest Match", "presentation": "markdown"},
            {"name": "Easiest Win Prob", "id": "Easiest Win Prob", "type": "numeric"},
            {"name": "# Matches", "id": "# Matches", "type": "numeric"},
        ]

        # Export dropdown for SoS
        sos_export_dropdown = dbc.DropdownMenu(
            label="Export",
            color="primary",
            className="me-2",
            children=[
                dbc.DropdownMenuItem("Export as CSV", id="event-sos-export-csv-dropdown"),
                dbc.DropdownMenuItem("Export as TSV", id="event-sos-export-tsv-dropdown"),
                dbc.DropdownMenuItem("Export as Excel", id="event-sos-export-excel-dropdown"),
                dbc.DropdownMenuItem("Export as JSON", id="event-sos-export-json-dropdown"),
                dbc.DropdownMenuItem("Export as HTML", id="event-sos-export-html-dropdown"),
                dbc.DropdownMenuItem("Export as LaTeX", id="event-sos-export-latex-dropdown"),
            ],
            toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
            style={"display": "inline-block"}
        )

        # Export container (at top)
        sos_export_container = html.Div([
            sos_export_dropdown,
            dcc.Download(id="download-event-sos-csv"),
            dcc.Download(id="download-event-sos-excel"),
            dcc.Download(id="download-event-sos-tsv"),
            dcc.Download(id="download-event-sos-json"),
            dcc.Download(id="download-event-sos-html"),
            dcc.Download(id="download-event-sos-latex"),
        ], style={"textAlign": "right", "marginBottom": "10px"})
        
        # Rows per page container (at bottom)
        sos_rows_per_page_container = html.Div([
            html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
            dcc.Dropdown(
                id="event-sos-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "15", "value": 15},
                    {"label": "25", "value": 25},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                ],
                value=15,
                clearable=False,
                style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
            ),
        ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})

        # Store SoS data for export
        sos_data_store = dcc.Store(id="event-sos-data-store", data=team_sos_rows)

        return html.Div([
            sos_data_store,
            html.H4("Strength of Schedule (SoS)", className="mb-3 mt-3"),
            sos_export_container,
            dash_table.DataTable(
                id="event-sos-table",
                columns=sos_columns,
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                filter_options={"case": "insensitive"},
                data=team_sos_rows,
                page_size=15,
                page_current=0,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_filter={
                    "backgroundColor": "var(--input-bg)",
                    "color": "var(--text-primary)",
                    "borderColor": "var(--input-border)",
                }
            ),
            sos_rows_per_page_container
        ]), query_string

    # === Compare Teams Tab ===
    elif active_tab == "compare":
        # Multi-select dropdown for teams
        team_options = [
            {"label": f"{t['tk']} - {t.get('nn', '')}", "value": str(t["tk"])}
            for t in event_teams
        ]
        # Default: top 2 teams by ACE
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
                style={"marginBottom": "10px"}
            ),
            dbc.ButtonGroup(
                [
                    dbc.Button("Compare Teams", id="event-compare-mode-teams", n_clicks=0, active=True, outline=True, color="warning", size="sm"),
                    dbc.Button("Compare Alliances", id="event-compare-mode-alliances", n_clicks=0, active=False, outline=True, color="warning", size="sm"),
                ],
                id="event-compare-mode-toggle",
                className="mb-3"
            ),
            html.Div(id="event-compare-mode-hint", style={"marginBottom": "10px", "fontSize": "0.85rem", "color": "var(--text-secondary)"}),
            html.Div(id="compare-teams-table-container"),
            dcc.Store(id="event-compare-mode-store", data="teams"),
            dcc.Store(id="event-radar-toggles-store", data={"show_alliances": True, "show_teams": True})
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
        # Use overall ACE for ranking (with fallback data)
        team_epas = []
        for tnum, team_data in year_team_data.get(event_year, {}).items():
            if team_data:
                # Use fallback data for ranking
                fallback_team_data, _ = get_team_data_with_fallback(tnum, event_year, year_team_data)
                epa_value = fallback_team_data.get("epa", 0) if fallback_team_data else 0
                team_epas.append((tnum, epa_value))
        team_epas.sort(key=lambda x: x[1], reverse=True)
        rank_map = {tnum: i+1 for i, (tnum, _) in enumerate(team_epas)}
        
        # Sort teams by overall ACE for spotlight cards (using fallback data)
        def get_team_epa_for_sorting(t):
            tnum = int(t.get("tk"))
            team_data, _ = get_team_data_with_fallback(tnum, event_year, year_team_data)
            return team_data.get("epa", 0) if team_data else 0
        
        sorted_teams = sorted(event_teams, key=get_team_epa_for_sorting, reverse=True)
        
        # Build rows with overall stats
        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            team_data, actual_year = get_team_data_with_fallback(int(tnum), event_year, year_team_data)
            
            nickname = t.get('nn', 'Unknown')
            nickname_safe = nickname.replace('"', "'")
            truncated = truncate_name(nickname)
            nickname_link = f'[{truncated}](/team/{tstr}/{event_year} "{nickname_safe}")'
            rows.append({
                "ACE Rank": rank_map.get(int(tnum), None),
                "Team #": int(tnum) if tnum else 0,
                "Nickname": nickname_link,
                "RAW": team_data.get('normal_epa', 0),
                "Confidence": team_data.get('confidence', 0),
                "ACE": team_data.get('epa', 0),
                "Auto": team_data.get('auto_epa', 0),
                "Teleop": team_data.get('teleop_epa', 0),
                "Endgame": team_data.get('endgame_epa', 0),
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })
        
        # Sort by overall ACE value
        rows.sort(key=lambda r: r["ACE"] if r["ACE"] is not None else 0, reverse=True)
        
        # Use global percentiles for coloring (with fallback data)
        if event_year == current_year:
            global_teams = TEAM_DATABASE.get(event_year, {}).values()
            global_epa_values = [t.get("epa", 0) for t in global_teams]
            global_confidence_values = [t.get("confidence", 0) for t in global_teams]
            global_auto_values = [t.get("auto_epa", 0) for t in global_teams]
            global_teleop_values = [t.get("teleop_epa", 0) for t in global_teams]
            global_endgame_values = [t.get("endgame_epa", 0) for t in global_teams]
        else:
            # For non-current years, use fallback data for percentile calculations
            global_epa_values = []
            global_confidence_values = []
            global_auto_values = []
            global_teleop_values = []
            global_endgame_values = []
            
            for tnum, team_data in year_team_data.get(event_year, {}).items():
                if team_data:
                    # Use fallback data for percentile calculations
                    fallback_team_data, _ = get_team_data_with_fallback(tnum, event_year, year_team_data)
                    if fallback_team_data:
                        global_epa_values.append(fallback_team_data.get("epa", 0))
                        global_confidence_values.append(fallback_team_data.get("confidence", 0))
                        global_auto_values.append(fallback_team_data.get("auto_epa", 0))
                        global_teleop_values.append(fallback_team_data.get("teleop_epa", 0))
                        global_endgame_values.append(fallback_team_data.get("endgame_epa", 0))
        
    else:  # stats_type == "event"
        # Use event-specific data for ranking within the event
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
                    
                    # Win probability
                    red_info = [
                        {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                        for t in m.get("rt", "").split(",") if t.strip().isdigit()
                    ]
                    blue_info = [
                        {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                        for t in m.get("bt", "").split(",") if t.strip().isdigit()
                    ]
                    p_red, p_blue = predict_win_probability(red_info, blue_info)
                    win_prob = p_red if alliance == "red" else p_blue
                    win_probs.append(win_prob)
                
                avg_win_prob = sum(win_probs) / len(win_probs) if win_probs else 0
                team_sos[team_num] = round(avg_win_prob, 2)  # SoS: 0 = lose all, 1 = win all
        else:
            # Fallback to simplified calculation if no match data
            for team_num in team_numbers:
                team_sos[team_num] = 0.5  # Default to 50% win probability
        
        # Sort teams by event-specific ACE  for spotlight cards
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
            
            # Find rank for this team's event ACE 
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
            
            nickname = t.get('nn', 'Unknown')
            nickname_safe = nickname.replace('"', "'")
            truncated = truncate_name(nickname)
            nickname_link = f'[{truncated}](/team/{tstr}/{event_year} "{nickname_safe}")'
            rows.append({
                "Event Rank": event_rank,
                "ACE Rank": overall_ace_rank,
                "Team #": int(tnum) if tnum else 0,
                "Nickname": nickname_link,
                "RAW": event_team_data.get('normal_epa', 0),
                "Confidence": event_team_data.get('confidence', 0),
                "ACE": event_team_data.get('epa', 0),
                "Auto": event_team_data.get('auto_epa', 0),
                "Teleop": event_team_data.get('teleop_epa', 0),
                "Endgame": event_team_data.get('endgame_epa', 0),
                "SoS": round(sos_value, 2),
                "ACE Δ": round(ace_improvement, 2),
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })
        
        # Sort by event ACE value
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
            ace_improvement_values.append(round(event_ace - overall_ace, 2))
        

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
            {"name": "Team #", "id": "Team #", "type": "numeric"},
            {"name": "Nickname", "id": "Nickname", "presentation": "markdown"},
            {"name": "RAW", "id": "RAW", "type": "numeric"},
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
            {"name": "Team #", "id": "Team #", "type": "numeric"},
            {"name": "Nickname", "id": "Nickname", "presentation": "markdown"},
            {"name": "RAW", "id": "RAW", "type": "numeric"},
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
        # Use overall stats for spotlight cards (with fallback data)
        spotlight_cards = []
        for t in top_3:
            tnum = int(t.get("tk"))
            team_data, actual_year = get_team_data_with_fallback(tnum, event_year, year_team_data)
            # Create a modified team data dict with the fallback data
            fallback_team_data = {event_year: {tnum: team_data}} if team_data else {event_year: {tnum: {}}}
            spotlight_cards.append(
                dbc.Col(create_team_card_spotlight(t, fallback_team_data, event_year), width="auto")
            )
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
    
    # Export dropdown for teams
    teams_export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="event-teams-export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="event-teams-export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="event-teams-export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="event-teams-export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="event-teams-export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="event-teams-export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    # Export container (at top)
    teams_export_container = html.Div([
        teams_export_dropdown,
        dcc.Download(id="download-event-teams-csv"),
        dcc.Download(id="download-event-teams-excel"),
        dcc.Download(id="download-event-teams-tsv"),
        dcc.Download(id="download-event-teams-json"),
        dcc.Download(id="download-event-teams-html"),
        dcc.Download(id="download-event-teams-latex"),
    ], style={"textAlign": "right", "marginBottom": "10px"})
    
    # Rows per page container (at bottom)
    teams_rows_per_page_container = html.Div([
        html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
        dcc.Dropdown(
            id="event-teams-page-size",
            options=[
                {"label": "10", "value": 10},
                {"label": "25", "value": 25},
                {"label": "50", "value": 50},
                {"label": "100", "value": 100},
            ],
            value=10,
            clearable=False,
            style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
        ),
    ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})

    # Store teams data for export
    teams_data_store = dcc.Store(id="event-teams-data-store", data=rows)
    
    return html.Div([
        teams_data_store,
        teams_export_container,
        dash_table.DataTable(
            id="event-teams-table",
            columns=columns,
            sort_action="native",
            sort_mode="multi",
            filter_action="native",
            filter_options={"case": "insensitive"},
            data=rows,
            page_size=10,
            page_current=0,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
            style_data_conditional=style_data_conditional,
            style_filter={
                "backgroundColor": "var(--input-bg)",
                "color": "var(--text-primary)",
                "borderColor": "var(--input-border)",
            }
        ),
        teams_rows_per_page_container
    ]), spotlight_layout

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
        
        # If event_epa_data is missing (even if confidence exists), fallback to team database
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
        # Use event-specific data, but ensure confidence has a reasonable fallback
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

            # Use simple prediction
            p_red, p_blue = predict_win_probability(red_info, blue_info)
            
            if p_red == 0.5 and p_blue == 0.5:
                pred_red = "50%"
                pred_blue = "50%"
                pred_winner = "Tie"
            else:
                pred_red = f"{p_red:.0%}"
                pred_blue = f"{p_blue:.0%}"
                pred_winner = "Red" if p_red > p_blue else "Blue"

            yid = match.get("yt")
            video_link = f"[▶](https://www.youtube.com/watch?v={yid})" if yid else "N/A"

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
    
    # Combine all match data for export
    all_matches_data = qual_data + playoff_data

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
            # Row coloring for winner (excluding Video and Match columns)
            {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},

            # --- Cell-level prediction rules (these should come after row-level rules) ---
            # Alliance column styling
            {"if": {"column_id": "Red Alliance"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            {"if": {"column_id": "Blue Alliance"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            # Score column styling
            {"if": {"column_id": "Red Score"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            {"if": {"column_id": "Blue Score"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
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
            {"if": {"filter_query": '{Pred Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Pred Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Pred Winner} = "Tie"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-yellow)", "color": "var(--text-primary)"},
        ]
    else:
        # Team focus styling
        row_style = [
            # Row coloring for winner (excluding Video and Match columns)
            {"if": {"filter_query": '{Winner} = "Red"', "column_id": "Winner"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)"},
            {"if": {"filter_query": '{Winner} = "Blue"', "column_id": "Winner"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)"},

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
            # Alliance column styling
            {"if": {"column_id": "Red Alliance"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            {"if": {"column_id": "Blue Alliance"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            # Score column styling
            {"if": {"column_id": "Score"}, "backgroundColor": "rgba(220, 53, 69, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
            {"if": {"column_id": "Opponent Score"}, "backgroundColor": "rgba(13, 110, 253, 0.1)", "color": "var(--text-primary)", "fontWeight": "bold"},
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
            id="qual-matches-table",
            columns=match_columns,
            sort_action="native",
            sort_mode="multi",
            data=qual_data,
            page_size=10,
            page_current=0,
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
            id="playoff-matches-table",
            columns=match_columns,
            sort_action="native",
            sort_mode="multi",
            data=playoff_data,
            page_size=10,
            page_current=0,
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
            if winner == "tie" or winner == "":
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
    
    # Export dropdown for matches
    matches_export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="event-matches-export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="event-matches-export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="event-matches-export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="event-matches-export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="event-matches-export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="event-matches-export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    # Export container (at top)
    matches_export_container = html.Div([
        matches_export_dropdown,
        dcc.Download(id="download-event-matches-csv"),
        dcc.Download(id="download-event-matches-excel"),
        dcc.Download(id="download-event-matches-tsv"),
        dcc.Download(id="download-event-matches-json"),
        dcc.Download(id="download-event-matches-html"),
        dcc.Download(id="download-event-matches-latex"),
    ], style={"textAlign": "right", "marginBottom": "10px"})
    
    # Rows per page container (at bottom)
    matches_rows_per_page_container = html.Div([
        html.Label("Qual rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
        dcc.Dropdown(
            id="qual-matches-page-size",
            options=[
                {"label": "10", "value": 10},
                {"label": "25", "value": 25},
                {"label": "50", "value": 50},
                {"label": "100", "value": 100},
            ],
            value=10,
            clearable=False,
            style={"width": "65px", "display": "inline-block", "marginRight": "10px", "fontSize": "0.85rem"}
        ),
        html.Label("Playoff rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
        dcc.Dropdown(
            id="playoff-matches-page-size",
            options=[
                {"label": "10", "value": 10},
                {"label": "25", "value": 25},
                {"label": "50", "value": 50},
                {"label": "100", "value": 100},
            ],
            value=10,
            clearable=False,
            style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
        ),
    ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px", "gap": "10px"})

    # Store matches data for export
    matches_data_store = dcc.Store(id="event-matches-data-store", data=all_matches_data)
    
    # Build the content list dynamically based on what exists
    content = [matches_data_store, matches_export_container]
    
    if qual_header and qual_table:
        content.extend([qual_header, html.Div(qual_table, className="recent-events-table")])
    
    if playoff_header and playoff_table:
        content.extend([playoff_header, html.Div(playoff_table, className="recent-events-table")])
    
    # Only include insights card if it exists
    if insights_card:
        content.append(insights_card)
    
    # Add rows per page container at the end
    content.append(matches_rows_per_page_container)
    
    return html.Div(content)

# Add callback for radar chart toggles
@app.callback(
    Output("event-radar-toggles-store", "data"),
    Input("event-radar-toggles-checklist", "value"),
    prevent_initial_call=True
)
def update_event_radar_toggles(selected_values):
    if not selected_values:
        return {"show_alliances": False, "show_teams": False}
    return {
        "show_alliances": "show_alliances" in selected_values,
        "show_teams": "show_teams" in selected_values
    }

# Add callback for event compare mode toggle
@app.callback(
    [
        Output("event-compare-mode-store", "data"),
        Output("event-compare-mode-teams", "active"),
        Output("event-compare-mode-alliances", "active"),
        Output("event-compare-mode-hint", "children"),
    ],
    [
        Input("event-compare-mode-teams", "n_clicks"),
        Input("event-compare-mode-alliances", "n_clicks"),
    ],
    State("compare-teams-dropdown", "value"),
)
def update_event_compare_mode(teams_clicks, alliances_clicks, selected_teams):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "teams", True, False, "Select 2+ teams to compare"
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if button_id == "event-compare-mode-alliances":
        if selected_teams and len(selected_teams) >= 3 and len(selected_teams) % 3 == 0:
            num_alliances = len(selected_teams) // 3
            return "alliances", False, True, f"Comparing {num_alliances} alliance{'s' if num_alliances > 1 else ''} ({len(selected_teams)} teams)"
        elif selected_teams and len(selected_teams) > 0:
            return "alliances", False, True, f"Select a multiple of 3 teams (currently {len(selected_teams)} teams)"
        else:
            return "alliances", False, True, "Select 3, 6, 9, or more teams (multiple of 3) to compare as alliances"
    else:
        if selected_teams and len(selected_teams) >= 2:
            return "teams", True, False, f"Comparing {len(selected_teams)} teams"
        else:
            return "teams", True, False, "Select 2+ teams to compare"

# Add a callback for the compare teams table
@app.callback(
    Output("compare-teams-table-container", "children"),
    Input("compare-teams-dropdown", "value"),
    Input("event-compare-mode-store", "data"),
    Input("event-radar-toggles-store", "data"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-rankings", "data"),
    State("store-event-year", "data"),
    State("store-event-matches", "data"),
)
def update_compare_teams_table(selected_teams, mode, radar_toggles, epa_data, event_teams, rankings, event_year, event_matches):
    mode = mode or "teams"
    radar_toggles = radar_toggles or {"show_alliances": True, "show_teams": True}
    show_alliances = radar_toggles.get("show_alliances", True)
    show_teams = radar_toggles.get("show_teams", True)
    
    if not selected_teams:
        return dbc.Alert("Select teams to compare.", color="info")
    
    if mode == "alliances":
        if len(selected_teams) < 3 or len(selected_teams) % 3 != 0:
            return dbc.Alert(f"Select a multiple of 3 teams to compare as alliances (currently {len(selected_teams)} teams). Select 3, 6, 9, 12, etc.", color="warning")
    else:
        if len(selected_teams) < 2:
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
            # Win probability
            red_info = [
                {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                for t in m.get("rt", "").split(",") if t.strip().isdigit()
            ]
            blue_info = [
                {"team_number": int(t), "epa": epa_data.get(str(t), {}).get("epa", 0), "confidence": epa_data.get(str(t), {}).get("confidence", 0.7)}
                for t in m.get("bt", "").split(",") if t.strip().isdigit()
            ]
            p_red, p_blue = predict_win_probability(red_info, blue_info)
            win_prob = p_red if alliance == "red" else p_blue
            win_probs.append(win_prob)
        avg_score_map[tnum_str] = sum(scores) / len(scores) if scores else 0
        sos_map[tnum_str] = sum(win_probs) / len(win_probs) if win_probs else 0

    # Handle alliance mode - calculate combined stats for multiple alliances
    alliance_rows = []
    if mode == "alliances" and len(selected_teams) >= 3 and len(selected_teams) % 3 == 0:
        # Group teams into alliances (3 teams per alliance)
        num_alliances = len(selected_teams) // 3
        for alliance_idx in range(num_alliances):
            alliance_teams = selected_teams[alliance_idx * 3:(alliance_idx + 1) * 3]
            
            # Calculate combined alliance stats
            combined_auto = sum(float(epa_data.get(str(tnum), {}).get('auto_epa', 0)) for tnum in alliance_teams)
            combined_teleop = sum(float(epa_data.get(str(tnum), {}).get('teleop_epa', 0)) for tnum in alliance_teams)
            combined_endgame = sum(float(epa_data.get(str(tnum), {}).get('endgame_epa', 0)) for tnum in alliance_teams)
            combined_ace = sum(float(epa_data.get(str(tnum), {}).get('epa', 0)) for tnum in alliance_teams)
            combined_raw = sum(float(epa_data.get(str(tnum), {}).get('normal_epa', 0)) for tnum in alliance_teams)
            combined_confidence = sum(float(epa_data.get(str(tnum), {}).get('confidence', 0)) for tnum in alliance_teams) / 3.0
            combined_wins = sum((rankings or {}).get(str(tnum), {}).get('w', 0) for tnum in alliance_teams)
            combined_losses = sum((rankings or {}).get(str(tnum), {}).get('l', 0) for tnum in alliance_teams)
            combined_ties = sum((rankings or {}).get(str(tnum), {}).get('t', 0) for tnum in alliance_teams)
            combined_sos = sum(sos_map.get(str(tnum), 0) for tnum in alliance_teams) / 3.0
            
            team_numbers = [int(tnum) for tnum in alliance_teams]
            alliance_label = " | ".join([f"#{num}" for num in team_numbers])
            alliance_name = f"Alliance {alliance_idx + 1}" if num_alliances > 1 else "Alliance"
            
            alliance_rows.append({
                "Team #": alliance_label,
                "Nickname": alliance_name,
                "Rank": "N/A",
                "W-L-T": f"{combined_wins}-{combined_losses}-{combined_ties}",
                "SoS": round(combined_sos, 2),
                "RAW": round(combined_raw, 2),
                "Auto": round(combined_auto, 2),
                "Teleop": round(combined_teleop, 2),
                "Endgame": round(combined_endgame, 2),
                "Confidence": round(combined_confidence, 2),
                "ACE": round(combined_ace, 2),
                "_alliance_teams": alliance_teams,  # Store for radar chart
            })
    
    # Build rows for each team
    rows = []
    for tnum in selected_teams:
        t = team_lookup.get(str(tnum), {})
        epa = epa_data.get(str(tnum), {})
        rank_info = (rankings or {}).get(str(tnum), {})
        nickname = t.get('nn', 'Unknown')
        nickname_safe = nickname.replace('"', "'")
        truncated = truncate_name(nickname)
        nickname_link = f'[{truncated}](/team/{tnum}/{event_year} "{nickname_safe}")'
        rows.append({
            "Team #": int(tnum) if tnum else 0,
            "Nickname": nickname_link,
            "Rank": rank_info.get("rk", "N/A"),
            "W-L-T": f"{rank_info.get('w', 'N/A')}-{rank_info.get('l', 'N/A')}-{rank_info.get('t', 'N/A')}",
            "SoS": sos_map.get(str(tnum), 0),
            "RAW": float(epa.get('normal_epa', 0)),
            "Auto": float(epa.get('auto_epa', 0)),
            "Teleop": float(epa.get('teleop_epa', 0)),
            "Endgame": float(epa.get('endgame_epa', 0)),
            "Confidence": float(epa.get('confidence', 0)),
            "ACE": float(epa.get('epa', 0)),
        })
    
    # Add alliance rows at the beginning if in alliance mode
    if alliance_rows:
        rows = alliance_rows + rows
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
        "Auto": compute_percentiles(global_auto_values),
        "Teleop": compute_percentiles(global_teleop_values),
        "Endgame": compute_percentiles(global_endgame_values),
        "Confidence": compute_percentiles(global_confidence_values),
        "ACE": compute_percentiles(global_ace_values),
    }
    style_data_conditional = get_epa_styling(percentiles_dict)
    columns = [
        {"name": "Team #", "id": "Team #", "type": "numeric"},
        {"name": "Nickname", "id": "Nickname", "presentation": "markdown"},
        {"name": "Rank", "id": "Rank"},
        {"name": "W-L-T", "id": "W-L-T"},
        {"name": "SoS", "id": "SoS"},
        {"name": "RAW", "id": "RAW"},
        {"name": "Auto", "id": "Auto"},
        {"name": "Teleop", "id": "Teleop"},
        {"name": "Endgame", "id": "Endgame"},
        {"name": "Confidence", "id": "Confidence"},
        {"name": "ACE", "id": "ACE"},
    ]
    # Radar chart for visual comparison
    
    radar_stats = ["Auto", "Teleop", "Endgame", "Confidence", "RAW", "ACE", "Avg Score", "SoS"]
    # Gather all event teams' stats for normalization
    all_team_stats = {stat: [] for stat in radar_stats}
    for t in event_teams:
        tnum = str(t["tk"])
        epa = epa_data.get(tnum, {})
        all_team_stats["Auto"].append(float(epa.get("auto_epa", 0)))
        all_team_stats["Teleop"].append(float(epa.get("teleop_epa", 0)))
        all_team_stats["Endgame"].append(float(epa.get("endgame_epa", 0)))
        all_team_stats["Confidence"].append(float(epa.get("confidence", 0)))
        all_team_stats["RAW"].append(float(epa.get("normal_epa", 0)))
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
    
    # Define colors for multiple alliances
    alliance_colors = [
        'rgba(244, 67, 54, 0.4)',    # Red
        'rgba(33, 150, 243, 0.4)',   # Blue
        'rgba(76, 175, 80, 0.4)',    # Green
        'rgba(255, 193, 7, 0.4)',    # Yellow
        'rgba(255, 87, 34, 0.4)',    # Orange
    ]

    alliance_line_colors = [
        'rgba(244, 67, 54, 1.0)',    
        'rgba(33, 150, 243, 1.0)',   
        'rgba(76, 175, 80, 1.0)',    
        'rgba(255, 193, 7, 1.0)',    
        'rgba(255, 87, 34, 1.0)',    
    ]
    # Process alliance rows first if they exist and toggle is on
    if mode == "alliances" and alliance_rows and show_alliances:
        # Remove "Avg Score" from radar stats for alliances since it's not meaningful
        alliance_radar_stats = [s for s in radar_stats if s != "Avg Score"]
        for idx, alliance_row in enumerate(alliance_rows):
            # For alliance, use combined values but scale normalization
            values = [
                alliance_row["Auto"],
                alliance_row["Teleop"],
                alliance_row["Endgame"],
                alliance_row["Confidence"],
                alliance_row["RAW"],
                alliance_row["ACE"],
                alliance_row["SoS"],
            ]
            # Scale mins/maxs by 3 for alliance comparison (except averaged stats)
            alliance_stat_minmax = {}
            for stat in alliance_radar_stats:
                if stat in ["Confidence", "SoS"]:
                    # Confidence and SoS are averaged, so keep original range
                    alliance_stat_minmax[stat] = (stat_minmax[stat][0], stat_minmax[stat][1])
                else:
                    # Other stats (Auto, Teleop, Endgame, RAW, ACE) are summed, so scale by 3
                    alliance_stat_minmax[stat] = (stat_minmax[stat][0] * 3, stat_minmax[stat][1] * 3)
            norm_values = []
            for v, stat in zip(values, alliance_radar_stats):
                stat_min, stat_max = alliance_stat_minmax[stat]
                if stat_max > stat_min:
                    norm = (v - stat_min) / (stat_max - stat_min)
                else:
                    norm = 0.5
                norm_values.append(norm)
            color_idx = idx % len(alliance_colors)
            fig.add_trace(go.Scatterpolar(
                r=norm_values,
                theta=alliance_radar_stats,
                fill='toself',
                fillcolor=alliance_colors[color_idx],
                line=dict(color=alliance_line_colors[color_idx], width=3),
                name=alliance_row["Nickname"],
            ))
    
    # Process team rows (skip alliance rows if they exist) - only if toggle is on
    if show_teams:
        # Use alliance_radar_stats if in alliance mode (to exclude Avg Score), otherwise use full radar_stats
        team_radar_stats = alliance_radar_stats if (mode == "alliances" and alliance_rows) else radar_stats
        for row in rows:
            # Skip alliance rows - we already processed them
            if row.get("Nickname") and ("Alliance" in row.get("Nickname", "")):
                continue
            
            tnum = str(row["Team #"])
            tnum_key = tnum
            
            if mode == "alliances" and alliance_rows:
                # In alliance mode, exclude Avg Score for consistency
                values = [
                    row["Auto"],
                    row["Teleop"],
                    row["Endgame"],
                    row["Confidence"],
                    row["RAW"],
                    row["ACE"],
                    row["SoS"],
                ]
            else:
                # In team mode, include all stats
                values = [
                    row["Auto"],
                    row["Teleop"],
                    row["Endgame"],
                    row["Confidence"],
                    row["RAW"],
                    row["ACE"],
                    avg_score_map.get(tnum_key, 0),
                    sos_map.get(tnum_key, 0),
                ]
            norm_values = []
            for v, stat in zip(values, team_radar_stats):
                stat_min, stat_max = stat_minmax[stat]
                if stat_max > stat_min:
                    norm = (v - stat_min) / (stat_max - stat_min)
                else:
                    norm = 0.5
                norm_values.append(norm)
            fig.add_trace(go.Scatterpolar(
                r=norm_values,
                theta=team_radar_stats,
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
    # Export dropdown for compare
    compare_export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="event-compare-export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="event-compare-export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="event-compare-export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="event-compare-export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="event-compare-export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="event-compare-export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    compare_export_container = html.Div([
        compare_export_dropdown,
        dcc.Download(id="download-event-compare-csv"),
        dcc.Download(id="download-event-compare-excel"),
        dcc.Download(id="download-event-compare-tsv"),
        dcc.Download(id="download-event-compare-json"),
        dcc.Download(id="download-event-compare-html"),
        dcc.Download(id="download-event-compare-latex"),
    ], style={"textAlign": "right", "marginBottom": "10px"})

    # Store compare data for export
    compare_data_store = dcc.Store(id="event-compare-data-store", data=rows)
    
    return html.Div([
        compare_data_store,
        compare_export_container,
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
            html.H5("Radar Chart Comparison", style={"marginTop": "20px", "marginBottom": "10px"}),
            html.Div([
                dbc.Checklist(
                    id="event-radar-toggles-checklist",
                    options=[opt for opt in [
                        {"label": " Show Alliances", "value": "show_alliances"} if mode == "alliances" else None,
                        {"label": " Show Teams", "value": "show_teams"},
                    ] if opt is not None],
                    value=["show_alliances", "show_teams"] if (mode == "alliances" and show_alliances and show_teams) else (["show_alliances"] if (mode == "alliances" and show_alliances) else ["show_teams"]),
                    inline=True,
                    style={"marginBottom": "10px", "color": "var(--text-primary)"}
                )
            ]) if mode == "alliances" else html.Div(),
            dcc.Graph(figure=fig, id="event-compare-radar-chart")
        ])
    ])

# client-side callback to handle opening the playlist in a new tab
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
        Input("z-axis-dropdown", "value"),
        Input("percentile-toggle", "value"),
    ],
    [State("teams-url", "href")],
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
    z_axis,
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

    # Build query string for updating URL (always build it, even for empty search)
    params = {
        "year": selected_year,
        "country": selected_country,
        "state": selected_state,
        "search": search_query or "",  # Ensure empty string instead of None
        "x": x_axis,
        "y": y_axis,
        "z": z_axis,
        "tab": active_tab,
        "district": selected_district,
        "percentile": "filtered" if "filtered" in percentile_mode else None,
    }
    query_string = "?" + urlencode({
        k: v for k, v in params.items()
        if v not in (None, "", "All") and str(v) != str(default_values.get(k, ""))
    })
    # Only update the URL if not triggered by URL change itself
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
        teams_data = [
            t for t in teams_data
            if (t.get("district") or "").upper() == selected_district.upper()
        ]
    elif selected_state and selected_state != "All":
        teams_data = [t for t in teams_data if (t.get("state_prov") or "").lower() == selected_state.lower()]

    if search_query:
        q = search_query.lower().strip()
        if q:  # Only search if there's actually a query
            # Split search terms for more flexible matching
            search_terms = q.split()
            
            def team_matches_search(team):
                """Enhanced search function for teams"""
                team_num = str(team.get("team_number", "")).lower()
                nickname = (team.get("nickname", "") or "").lower()
                city = (team.get("city", "") or "").lower()
                
                # Check if all search terms match any field
                for term in search_terms:
                    term_matches = False
                    
                    # For numeric terms, prioritize exact team number matches
                    if term.isdigit():
                        # Exact match is fastest
                        if term == team_num:
                            term_matches = True
                        # Then check if team number starts with the term
                        elif team_num.startswith(term):
                            term_matches = True
                        # Only do substring search as last resort for numbers
                        elif term in team_num:
                            term_matches = True
                    else:
                        # For text terms, check nickname and city
                        if term in nickname or term in city:
                            term_matches = True
                        # Check word boundaries for names
                        elif any(word.startswith(term) for word in nickname.split()):
                            term_matches = True
                    
                    if not term_matches:
                        return False
                return True
            
            # Apply search filter
            filtered_teams = [t for t in teams_data if team_matches_search(t)]
            
            # Limit results to prevent performance issues with very broad searches
            if len(filtered_teams) > 1000:
                # If search returns too many results, prioritize exact matches
                exact_matches = []
                partial_matches = []
                
                for team in filtered_teams:
                    team_num = str(team.get("team_number", "")).lower()
                    nickname = (team.get("nickname", "") or "").lower()
                    
                    # Check for exact matches first
                    if any(term == team_num for term in search_terms if term.isdigit()):
                        exact_matches.append(team)
                    elif any(term in nickname.split() for term in search_terms if not term.isdigit()):
                        exact_matches.append(team)
                    else:
                        partial_matches.append(team)
                
                # Return exact matches first, then partial matches up to limit
                teams_data = exact_matches + partial_matches[:1000 - len(exact_matches)]
            else:
                teams_data = filtered_teams

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
        ace = abs(team.get("epa") or 0)
        raw = abs(team.get("normal_epa") or 0)
        team_number = team.get("team_number", 0)
        confidence = team.get("confidence", 0)
        wins = team.get("wins", 0)
        losses = team.get("losses", 0)
        ties = team.get("ties", 0)
        favorites = favorites_counts.get(team_number, 0)
        total_matches = wins + losses + ties
        auto_share = (auto / ace) if ace else 0
        teleop_share = (teleop / ace) if ace else 0
        endgame_share = (endgame / ace) if ace else 0
        win_rate = (wins / total_matches) if total_matches else 0
        return {
            "auto_epa": auto,
            "teleop_epa": teleop,
            "endgame_epa": endgame,
            "auto+teleop": auto + teleop,
            "auto+endgame": auto + endgame,
            "teleop+endgame": teleop + endgame,
            "raw": raw,
            "ace": ace,
            "auto_share": auto_share,
            "teleop_share": teleop_share,
            "endgame_share": endgame_share,
            "win_rate": win_rate,
            "team_number": team_number,
            "confidence": confidence,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "favorites": favorites,
        }.get(axis, 0)

    from datagather import get_all_team_favorites_counts
    # Get favorites counts for all teams
    favorites_counts = get_all_team_favorites_counts()
    
    table_rows = []
    for t in teams_data:
        team_num = t.get("team_number")
        rank = epa_ranks.get(str(team_num), {}).get("rank", "N/A")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        nickname = t.get('nickname', 'Unknown')
        nickname_safe = nickname.replace('"', "'")
        truncated = truncate_name(nickname)
        nickname_link = f'[{truncated}](/team/{team_num}/{selected_year} "{nickname_safe}")'
        favorites_count = favorites_counts.get(team_num, 0)
        table_rows.append({
            "ace_rank": rank,
            "team_number": int(team_num) if team_num else 0,
            "nickname": nickname_link,
            "epa": round(abs(t.get("normal_epa") or 0), 2),  # RAW column shows normal_epa
            "confidence": t.get("confidence", 0),
            "ace": round(abs(t.get("epa") or 0), 2),  # ACE column shows epa
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
                # Use cached avatar lookup instead of os.path.exists
                from datagather import _load_avatar_cache
                available_avatars = _load_avatar_cache()
                avatar_src = f"/assets/avatars/{team_number}.png?v=1" if team_number in available_avatars else "/assets/avatars/stock.png"
                avatars.append(html.A(
                    html.Img(
                        src=avatar_src,
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
            team_number = t.get("team_number", 0)
            # Filter out test teams (9970-9999)
            if 9970 <= team_number <= 9999:
                continue
                
            x_val = get_axis_value(t, x_axis)
            y_val = get_axis_value(t, y_axis)
            z_val = get_axis_value(t, z_axis)
            if x_val is not None and y_val is not None and z_val is not None:
                chart_data.append({
                    "x": x_val,
                    "y": y_val,
                    "z": z_val,
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
        def format_hover_value(axis, value):
            if axis in ["team_number", "wins", "losses", "ties", "favorites"]:
                return f"{int(value)}"
            if axis in ["auto_share", "teleop_share", "endgame_share", "win_rate"]:
                return f"{value * 100:.1f}%"
            else:
                return f"{value:.2f}"
        
        def format_axis_label(axis):
            return (axis.replace('_epa', ' ACE')
                       .replace('raw', 'RAW')
                       .replace('ace', 'ACE')
                       .replace('auto_share', 'Auto % of ACE')
                       .replace('teleop_share', 'Teleop % of ACE')
                       .replace('endgame_share', 'Endgame % of ACE')
                       .replace('win_rate', 'Win Rate')
                       .replace('+', ' + ')
                       .replace('team_number', 'Team Number')
                       .replace('confidence', 'Confidence')
                       .replace('wins', 'Wins')
                       .replace('losses', 'Losses')
                       .replace('ties', 'Ties')
                       .replace('favorites', 'Favorites'))
        
        df["hover"] = df.apply(
            lambda r: (
                f"<b>{r['team']}</b><br>"
                f"{format_axis_label(x_axis)}: {format_hover_value(x_axis, r['x'])}<br>"
                f"{format_axis_label(y_axis)}: {format_hover_value(y_axis, r['y'])}<br>"
                f"{format_axis_label(z_axis)}: {format_hover_value(z_axis, r['z'])}"
            ),
            axis=1
        )

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
                    color=df.loc[~df["is_match"], "z"],
                    colorscale="Viridis",
                    colorbar=dict(
                        title=dict(
                            text=format_axis_label(z_axis),
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
                text=format_axis_label(x_axis),
                font=dict(size=14, color="#777")
            ),
            yaxis_title=dict(
                text=format_axis_label(y_axis),
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
    if 'nickname' in df_export.columns:
        df_export['nickname'] = df_export['nickname'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
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

# Export callbacks for event cards tab
@app.callback(
    [Output("download-event-cards-csv", "data"),
     Output("download-event-cards-excel", "data"),
     Output("download-event-cards-tsv", "data"),
     Output("download-event-cards-json", "data"),
     Output("download-event-cards-html", "data"),
     Output("download-event-cards-latex", "data")],
    [Input("event-cards-export-csv-dropdown", "n_clicks"),
     Input("event-cards-export-tsv-dropdown", "n_clicks"),
     Input("event-cards-export-excel-dropdown", "n_clicks"),
     Input("event-cards-export-json-dropdown", "n_clicks"),
     Input("event-cards-export-html-dropdown", "n_clicks"),
     Input("event-cards-export-latex-dropdown", "n_clicks")],
    [State("event-cards-data-store", "data")],
    prevent_initial_call=True
)
def export_event_cards_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    
    # Convert events data to DataFrame
    rows = []
    for ev in data:
        # Get district from stored fields
        district = (ev.get("da") or "").strip().upper()
        if not district:
            district_key = (ev.get("dk") or "").strip()
            district = district_key[-2:].upper() if len(district_key) >= 2 else None

        city = ev.get("c", "")
        state = ev.get("s", "")
        country = ev.get("co", "")
        
        # Get week
        week = "N/A"
        try:
            start_date_str = ev.get("sd", "")
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                week_idx = get_week_number(start_date)
                if week_idx is not None:
                    week = f"{week_idx+1}"
        except Exception:
            pass
        
        # Build location string
        location = ", ".join([v for v in [state, country] if v])
        
        # Event type name
        event_type_map = {0: "Regional", 1: "District", 2: "District Championship", 3: "Championship Division", 4: "Championship", 5: "Offseason", 99: "Offseason"}
        event_type_name = event_type_map.get(ev.get("et"), "Unknown")
        
        rows.append({
            "Event Key": ev.get("k", ""),
            "Name": ev.get("n", ""),
            "Year": ev.get("y", ""),
            "Week": week,
            "District": district or "",
            "Location": location,
            "City": city,
            "State/Province": state,
            "Country": country,
            "Event Type": event_type_name,
            "Start Date": ev.get("sd", ""),
            "End Date": ev.get("ed", ""),
            "Website": ev.get("w", ""),
        })
    
    df = pd.DataFrame(rows)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_prefix = "event_cards"
    
    # Prepare outputs for all formats
    outputs = [None] * 6
    if triggered_id == "event-cards-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-cards-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-cards-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-cards-export-json-dropdown":
        outputs[3] = dict(content=df.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-cards-export-html-dropdown":
        outputs[4] = dict(content=df.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-cards-export-latex-dropdown":
        outputs[5] = dict(content=df.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs


# Export callbacks for event rankings table
@app.callback(
    [Output("download-event-rankings-csv", "data"),
     Output("download-event-rankings-excel", "data"),
     Output("download-event-rankings-tsv", "data"),
     Output("download-event-rankings-json", "data"),
     Output("download-event-rankings-html", "data"),
     Output("download-event-rankings-latex", "data")],
    [Input("event-rankings-export-csv-dropdown", "n_clicks"),
     Input("event-rankings-export-tsv-dropdown", "n_clicks"),
     Input("event-rankings-export-excel-dropdown", "n_clicks"),
     Input("event-rankings-export-json-dropdown", "n_clicks"),
     Input("event-rankings-export-html-dropdown", "n_clicks"),
     Input("event-rankings-export-latex-dropdown", "n_clicks")],
    [State("event-rankings-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_rankings_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Team' in df_export.columns:
        df_export['Team'] = df_export['Team'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_rankings"
    outputs = [None] * 6
    if triggered_id == "event-rankings-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-rankings-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-rankings-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-rankings-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-rankings-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-rankings-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event teams table
@app.callback(
    [Output("download-event-teams-csv", "data"),
     Output("download-event-teams-excel", "data"),
     Output("download-event-teams-tsv", "data"),
     Output("download-event-teams-json", "data"),
     Output("download-event-teams-html", "data"),
     Output("download-event-teams-latex", "data")],
    [Input("event-teams-export-csv-dropdown", "n_clicks"),
     Input("event-teams-export-tsv-dropdown", "n_clicks"),
     Input("event-teams-export-excel-dropdown", "n_clicks"),
     Input("event-teams-export-json-dropdown", "n_clicks"),
     Input("event-teams-export-html-dropdown", "n_clicks"),
     Input("event-teams-export-latex-dropdown", "n_clicks")],
    [State("event-teams-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_teams_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Team' in df_export.columns:
        df_export['Team'] = df_export['Team'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_teams"
    outputs = [None] * 6
    if triggered_id == "event-teams-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-teams-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-teams-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-teams-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-teams-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-teams-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event SoS table
@app.callback(
    [Output("download-event-sos-csv", "data"),
     Output("download-event-sos-excel", "data"),
     Output("download-event-sos-tsv", "data"),
     Output("download-event-sos-json", "data"),
     Output("download-event-sos-html", "data"),
     Output("download-event-sos-latex", "data")],
    [Input("event-sos-export-csv-dropdown", "n_clicks"),
     Input("event-sos-export-tsv-dropdown", "n_clicks"),
     Input("event-sos-export-excel-dropdown", "n_clicks"),
     Input("event-sos-export-json-dropdown", "n_clicks"),
     Input("event-sos-export-html-dropdown", "n_clicks"),
     Input("event-sos-export-latex-dropdown", "n_clicks")],
    [State("event-sos-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_sos_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Team' in df_export.columns:
        df_export['Team'] = df_export['Team'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    if 'Hardest Match' in df_export.columns:
        df_export['Hardest Match'] = df_export['Hardest Match'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    if 'Easiest Match' in df_export.columns:
        df_export['Easiest Match'] = df_export['Easiest Match'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_sos"
    outputs = [None] * 6
    if triggered_id == "event-sos-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-sos-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-sos-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-sos-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-sos-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-sos-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event matches table
@app.callback(
    [Output("download-event-matches-csv", "data"),
     Output("download-event-matches-excel", "data"),
     Output("download-event-matches-tsv", "data"),
     Output("download-event-matches-json", "data"),
     Output("download-event-matches-html", "data"),
     Output("download-event-matches-latex", "data")],
    [Input("event-matches-export-csv-dropdown", "n_clicks"),
     Input("event-matches-export-tsv-dropdown", "n_clicks"),
     Input("event-matches-export-excel-dropdown", "n_clicks"),
     Input("event-matches-export-json-dropdown", "n_clicks"),
     Input("event-matches-export-html-dropdown", "n_clicks"),
     Input("event-matches-export-latex-dropdown", "n_clicks")],
    [State("event-matches-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_matches_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    # Remove markdown from columns
    for col in df_export.columns:
        if df_export[col].dtype == 'object':
            df_export[col] = df_export[col].astype(str).str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    # Remove hidden columns used for styling
    df_export = df_export.drop(columns=[col for col in df_export.columns if col.endswith(' Prediction %')], errors='ignore')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_matches"
    outputs = [None] * 6
    if triggered_id == "event-matches-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-matches-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-matches-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-matches-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-matches-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-matches-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event compare table
@app.callback(
    [Output("download-event-compare-csv", "data"),
     Output("download-event-compare-excel", "data"),
     Output("download-event-compare-tsv", "data"),
     Output("download-event-compare-json", "data"),
     Output("download-event-compare-html", "data"),
     Output("download-event-compare-latex", "data")],
    [Input("event-compare-export-csv-dropdown", "n_clicks"),
     Input("event-compare-export-tsv-dropdown", "n_clicks"),
     Input("event-compare-export-excel-dropdown", "n_clicks"),
     Input("event-compare-export-json-dropdown", "n_clicks"),
     Input("event-compare-export-html-dropdown", "n_clicks"),
     Input("event-compare-export-latex-dropdown", "n_clicks")],
    [State("event-compare-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_compare_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Team' in df_export.columns:
        df_export['Team'] = df_export['Team'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_compare"
    outputs = [None] * 6
    if triggered_id == "event-compare-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-compare-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-compare-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-compare-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-compare-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-compare-export-latex-dropdown":
        outputs[5] = dict(content=df_export.to_latex(index=False), filename=f"{filename_prefix}_{timestamp}.tex")
    return outputs

# Export callbacks for event metrics table
@app.callback(
    [Output("download-event-metrics-csv", "data"),
     Output("download-event-metrics-excel", "data"),
     Output("download-event-metrics-tsv", "data"),
     Output("download-event-metrics-json", "data"),
     Output("download-event-metrics-html", "data"),
     Output("download-event-metrics-latex", "data")],
    [Input("event-metrics-export-csv-dropdown", "n_clicks"),
     Input("event-metrics-export-tsv-dropdown", "n_clicks"),
     Input("event-metrics-export-excel-dropdown", "n_clicks"),
     Input("event-metrics-export-json-dropdown", "n_clicks"),
     Input("event-metrics-export-html-dropdown", "n_clicks"),
     Input("event-metrics-export-latex-dropdown", "n_clicks")],
    [State("event-metrics-data-store", "data"),
     State("store-event-key", "data")],
    prevent_initial_call=True
)
def export_event_metrics_data(csv_clicks, tsv_clicks, excel_clicks, json_clicks, html_clicks, latex_clicks, data, event_key):
    ctx = callback_context
    if not ctx.triggered:
        return [None] * 6
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not data:
        return [None] * 6
    df = pd.DataFrame(data)
    df_export = df.copy()
    if 'Team' in df_export.columns:
        df_export['Team'] = df_export['Team'].str.replace(r'\[([^\]]+)\]\([^)]+\)', r'\1', regex=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    event_code = event_key or "unknown_event"
    filename_prefix = f"{event_code}_metrics"
    outputs = [None] * 6
    if triggered_id == "event-metrics-export-csv-dropdown":
        outputs[0] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.csv", index=False)
    if triggered_id == "event-metrics-export-excel-dropdown":
        outputs[1] = dcc.send_data_frame(df_export.to_excel, f"{filename_prefix}_{timestamp}.xlsx", index=False)
    if triggered_id == "event-metrics-export-tsv-dropdown":
        outputs[2] = dcc.send_data_frame(df_export.to_csv, f"{filename_prefix}_{timestamp}.tsv", sep='\t', index=False)
    if triggered_id == "event-metrics-export-json-dropdown":
        outputs[3] = dict(content=df_export.to_json(orient='records', indent=2), filename=f"{filename_prefix}_{timestamp}.json")
    if triggered_id == "event-metrics-export-html-dropdown":
        outputs[4] = dict(content=df_export.to_html(index=False), filename=f"{filename_prefix}_{timestamp}.html")
    if triggered_id == "event-metrics-export-latex-dropdown":
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
        # Get team's event data for the specific year
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
        
        # Extract data for plotting, filtering out events with 0 stats
        event_names = []
        event_keys = []
        ace_values = []
        
        for event in sorted_events:
            event_key = event.get("event_key", "")
            if event_key in event_database.get(performance_year, {}):
                ace_value = event.get("overall", 0)
                auto_value = event.get("auto", 0)
                teleop_value = event.get("teleop", 0)
                endgame_value = event.get("endgame", 0)
                raw_value = event.get("normal_epa", 0)
                
                # Only include events that have at least one non-zero stat
                if ace_value > 0 or auto_value > 0 or teleop_value > 0 or endgame_value > 0 or raw_value > 0:
                    event_name = event_database[performance_year][event_key].get("n", event_key)
                    event_names.append(event_name)
                    event_keys.append(event_key)
                    ace_values.append(ace_value)
        
        if not ace_values:
            return "No valid event data with non-zero stats found."
        
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
            return ""
        
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
                return ""
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
        id="team-events-table",
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
        page_current=0,
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

    return html.Div([
        events_table,
        html.Div([
            html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
            dcc.Dropdown(
                id="team-events-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "25", "value": 25},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                ],
                value=10,
                clearable=False,
                style={"width": "65px", "display": "inline-block", "marginRight": "20px", "fontSize": "0.85rem"}
            ),
        ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})
    ])

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
            id="team-awards-table",
            columns=[
                {"name": "Award Name", "id": "award_name"},
                {"name": "Event", "id": "event_name", "presentation": "markdown"},
                {"name": "Year", "id": "award_year"},
            ],
            data=table_data,
            sort_action="native", sort_mode="multi",
            page_size=10,
            page_current=0,
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
        
        return html.Div([
            awards_table,
            html.Div([
                html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
                dcc.Dropdown(
                    id="team-awards-page-size",
                    options=[
                        {"label": "10", "value": 10},
                        {"label": "25", "value": 25},
                        {"label": "50", "value": 50},
                        {"label": "100", "value": 100},
                    ],
                    value=10,
                    clearable=False,
                    style={"width": "65px", "display": "inline-block", "marginRight": "20px", "fontSize": "0.85rem"}
                ),
            ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"}),
            banner_section
        ])

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
            awards = []
            for aw in raw:
                if not any(rec.get("team_key") == team_key for rec in aw.get("recipient_list", [])):
                    continue
                event_key = aw.get("event_key", "")
                try:
                    event_year = int(str(event_key)[:4])
                except Exception:
                    event_year = None
                awards.append(
                    {
                        "event_key": event_key,
                        "name": aw.get("name"),
                        "year": event_year,
                    }
                )
            return build_output(awards)
        except Exception as e:
            return f"Error loading awards from TBA: {e}"
    
    # Otherwise, use local logic for single year
    awards = []
    try:
        if int(year) == current_year:
            awards = [
                {
                    "event_key": aw["ek"],
                    "name": aw["an"],
                    "year": int(str(aw["ek"])[:4]) if str(aw.get("ek", ""))[:4].isdigit() else None,
                }
                for aw in EVENT_AWARDS
                if aw.get("tk") == int(team)
                and (int(str(aw.get("ek", ""))[:4]) if str(aw.get("ek", ""))[:4].isdigit() else None) == current_year
            ]
        else:
            _, _, _, _, aya, _ = load_year_data(int(year))
            source = aya.values() if isinstance(aya, dict) else aya
            awards = [
                {
                    "event_key": aw["ek"],
                    "name": aw["an"],
                    "year": int(str(aw["ek"])[:4]) if str(aw.get("ek", ""))[:4].isdigit() else None,
                }
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
    
    # Export dropdown for metrics
    metrics_export_dropdown = dbc.DropdownMenu(
        label="Export",
        color="primary",
        className="me-2",
        children=[
            dbc.DropdownMenuItem("Export as CSV", id="event-metrics-export-csv-dropdown"),
            dbc.DropdownMenuItem("Export as TSV", id="event-metrics-export-tsv-dropdown"),
            dbc.DropdownMenuItem("Export as Excel", id="event-metrics-export-excel-dropdown"),
            dbc.DropdownMenuItem("Export as JSON", id="event-metrics-export-json-dropdown"),
            dbc.DropdownMenuItem("Export as HTML", id="event-metrics-export-html-dropdown"),
            dbc.DropdownMenuItem("Export as LaTeX", id="event-metrics-export-latex-dropdown"),
        ],
        toggle_style={"backgroundColor": "transparent", "color": "var(--text-primary)", "fontWeight": "bold", "borderColor": "transparent"},
        style={"display": "inline-block"}
    )

    # Export container (at top)
    metrics_export_container = html.Div([
        metrics_export_dropdown,
        dcc.Download(id="download-event-metrics-csv"),
        dcc.Download(id="download-event-metrics-excel"),
        dcc.Download(id="download-event-metrics-tsv"),
        dcc.Download(id="download-event-metrics-json"),
        dcc.Download(id="download-event-metrics-html"),
        dcc.Download(id="download-event-metrics-latex"),
    ], style={"textAlign": "right", "marginBottom": "10px"})
    
    # Rows per page container (at bottom)
    metrics_rows_per_page_container = html.Div([
        html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
        dcc.Dropdown(
            id="event-metrics-page-size",
            options=[
                {"label": "10", "value": 10},
                {"label": "20", "value": 20},
                {"label": "50", "value": 50},
                {"label": "100", "value": 100},
            ],
            value=20,
            clearable=False,
            style={"width": "65px", "display": "inline-block", "fontSize": "0.85rem"}
        ),
    ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})

    # Store metrics data for export
    metrics_data_store = dcc.Store(id="event-metrics-data-store", data=table_data)
    
    # Create DataTable
    table = dash_table.DataTable(
        id="event-metrics-table",
        columns=[
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": selected_metric, "id": "Value", "type": "numeric"}
        ],
        data=table_data,
        sort_action="native",
        sort_mode="single",
        page_size=20,
        page_current=0,
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
    
    return html.Div([
        metrics_data_store,
        metrics_export_container,
        table,
        metrics_rows_per_page_container
    ])

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
    return html.Div([
        dash_table.DataTable(
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
            id="insights-table",
            page_size=20,
            page_current=0,
            style_as_list_view=True,
        ),
        html.Div([
            html.Label("Rows/page: ", style={"marginRight": "6px", "color": "var(--text-primary)", "fontSize": "0.85rem", "verticalAlign": "middle"}),
            dcc.Dropdown(
                id="insights-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "20", "value": 20},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                ],
                value=20,
                clearable=False,
                style={"width": "65px", "display": "inline-block", "marginRight": "20px", "fontSize": "0.85rem"}
            ),
        ], style={"display": "inline-flex", "alignItems": "center", "justifyContent": "flex-end", "width": "100%", "marginTop": "10px"})
    ])

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

# PeekoLive filters and refresh
@app.callback(
    Output("peekolive-grid", "children"),
    Output("peekolive-title", "children"),
    Input("peekolive-refresh", "n_intervals"),
    # Events page filters
    Input("year-dropdown", "value"),
    Input("event-type-dropdown", "value"),
    Input("week-dropdown", "value"),
    Input("search-input", "value"),
    Input("district-dropdown", "value"),
)
def update_peekolive_grid(_, selected_year, selected_event_types, selected_week, search_query, selected_district):
    
    # If the Events search contains a team (e.g., "frc123" or "123"), treat it as the team filter
    detected_team = None
    try:
        if search_query:
            s = str(search_query).lower().strip()
            # Only detect team if it's explicitly "frc" prefixed or a standalone number
            frc_match = re.search(r"frc(\d{1,5})", s)
            if frc_match:
                detected_team = frc_match.group(1)
            else:
                # Only treat as team if it's a standalone number (not part of a larger string)
                # This prevents years like "2024" from being treated as team 2024
                if re.fullmatch(r"\d{1,5}", s):
                    detected_team = s
    except Exception:
        detected_team = None

    effective_team = detected_team

    # Build baseline PeekoLive events; if a team filter is active OR there's a search query, do not cap
    from layouts import get_peekolive_events
    events = get_peekolive_events(include_all=bool(effective_team) or bool(search_query))

    # Apply Events page filters to PeekoLive list
    # Year filter
    if selected_year:
        events = [ev for ev in events if ev.get("year") == selected_year]

    # Event type filter uses EVENT_DATABASE to lookup type by key
    if selected_event_types:
        if not isinstance(selected_event_types, list):
            selected_event_types = [selected_event_types]
        try:
            # EVENT_DATABASE is keyed by year; when year filter missing, assume current
            lookup_year = selected_year or current_year
            ev_by_key = {e.get("k"): e for e in EVENT_DATABASE.get(lookup_year, {}).values()}
            def ev_type_ok(ev):
                ek = ev.get("event_key")
                meta = ev_by_key.get(ek, {})
                return meta.get("et") in selected_event_types
            events = [ev for ev in events if ev_type_ok(ev)]
        except Exception:
            # If lookup fails, skip type filter
            pass

    # Week filter: compute week from start_date using shared util get_week_number
    if selected_week != "all":
        try:
            def compute_week(ev):
                try:
                    sd = ev.get("start_date")
                    if not sd:
                        return None
                    return get_week_number(datetime.strptime(sd, "%Y-%m-%d").date())
                except Exception:
                    return None
            events = [ev for ev in events if compute_week(ev) == selected_week]
        except Exception:
            pass

    # District filter uses stored district fields
    if selected_district and selected_district != "all":
        try:
            def get_event_district_from_ev(ev):
                district_abbrev = (ev.get("district_abbrev") or "").strip().upper()
                if district_abbrev:
                    return district_abbrev
                district_key = (ev.get("district_key") or "").strip()
                return district_key[-2:].upper() if len(district_key) >= 2 else None
            events = [ev for ev in events if get_event_district_from_ev(ev) == selected_district]
        except Exception:
            pass

    # Text search on name/city (applied first, before team filtering)
    if search_query:
        q = str(search_query).lower()
        # Apply text search unless it's clearly just a team number
        should_apply_text_search = True
        try:
            q_clean = q.strip()
            # Only skip text search if it's purely a team number (frc123 or standalone digits)
            if re.fullmatch(r"frc\d{1,5}|\d{1,5}", q_clean):
                should_apply_text_search = False
        except Exception:
            should_apply_text_search = True
        
        if should_apply_text_search:
            original_count = len(events)
            events = [
                ev for ev in events
                if q in (ev.get("name", "").lower()) or q in (ev.get("location", "").lower())
            ]

    # If a team was detected (from dropdown or search), filter events by team across all years
    if effective_team:
        try:
            t_str = str(effective_team)
            filtered = []
            for ev in events:
                evk = ev.get("event_key")
                found = False
                for _, year_map in (EVENT_TEAMS or {}).items():
                    teams = (year_map or {}).get(evk, [])
                    if any(str(t.get("tk")) == t_str for t in teams):
                        found = True
                        break
                if found:
                    filtered.append(ev)
            events = filtered
        except Exception:
            pass

    # Title
    title = "Upcoming Events"
    if effective_team:
        title = f"Events for Team {effective_team}"
    elif search_query:
        title = f"Events matching '{search_query}'"

    # Build grid using prefiltered events and effective team value
    return build_peekolive_grid(team_value=effective_team, prefiltered_events=events), title

# Focus button callback for PeekoLive
@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input({"type": "focus-button", "event_key": dash.dependencies.ALL}, "n_clicks"),
    prevent_initial_call=True
)
def handle_focus_button_click(n_clicks_list):
    """Handle focus button clicks to navigate to event page"""
    if not any(n_clicks_list):
        return dash.no_update
    
    # Find which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    # Get the event_key from the triggered input
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        button_id = json.loads(triggered_id)
        event_key = button_id.get("event_key")
        if event_key:
            return f"/events/peekolive/{event_key}"
    except (json.JSONDecodeError, KeyError):
        pass
    
    return dash.no_update

# Team filter callback for focused peekolive
@app.callback(
    Output("match-notifications", "children"),
    Input({"type": "team-filter", "event_key": dash.dependencies.ALL}, "value"),
    prevent_initial_call=True
)
def update_match_notifications(selected_team):
    """Handle team filter changes for match notifications"""
    if not selected_team:
        return dash.no_update
    
    # Find which dropdown was changed
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    # Get the event_key from the triggered input
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        button_id = json.loads(triggered_id)
        event_key = button_id.get("event_key")
        if event_key:
            from layouts import build_match_notifications
            # Handle case where selected_team might be a list
            team_value = selected_team[0] if isinstance(selected_team, list) and selected_team else selected_team
            return build_match_notifications(event_key, team_value)
    except (json.JSONDecodeError, KeyError):
        pass
    
    return dash.no_update

# Page size callbacks for all DataTables
@app.callback(
    Output("event-insights-table", "page_size"),
    Input("event-insights-page-size", "value")
)
def update_event_insights_page_size(page_size):
    return page_size

@app.callback(
    Output("event-rankings-table", "page_size"),
    Input("event-rankings-page-size", "value")
)
def update_event_rankings_page_size(page_size):
    return page_size

@app.callback(
    Output("event-sos-table", "page_size"),
    Input("event-sos-page-size", "value")
)
def update_event_sos_page_size(page_size):
    return page_size

@app.callback(
    Output("event-teams-table", "page_size"),
    Input("event-teams-page-size", "value")
)
def update_event_teams_page_size(page_size):
    return page_size

@app.callback(
    Output("qual-matches-table", "page_size"),
    Input("qual-matches-page-size", "value")
)
def update_qual_matches_page_size(page_size):
    return page_size

@app.callback(
    Output("playoff-matches-table", "page_size"),
    Input("playoff-matches-page-size", "value")
)
def update_playoff_matches_page_size(page_size):
    return page_size

@app.callback(
    Output("team-events-table", "page_size"),
    Input("team-events-page-size", "value")
)
def update_team_events_page_size(page_size):
    return page_size

@app.callback(
    Output("team-awards-table", "page_size"),
    Input("team-awards-page-size", "value")
)
def update_team_awards_page_size(page_size):
    return page_size

@app.callback(
    Output("event-metrics-table", "page_size"),
    Input("event-metrics-page-size", "value")
)
def update_event_metrics_page_size(page_size):
    return page_size

@app.callback(
    Output("insights-table", "page_size"),
    Input("insights-page-size", "value")
)
def update_insights_page_size(page_size):
    return page_size

# Higher or Lower Game Callbacks
@app.callback(
    Output("selected-year-store", "data"),
    Input("higher-lower-year-dropdown", "value"),
    prevent_initial_call=False
)
def update_selected_year(selected_year):
    """Store the selected year"""
    return selected_year if selected_year else current_year

@app.callback(
    Output("selected-country-store", "data"),
    Input("higher-lower-country-dropdown", "value"),
    prevent_initial_call=False
)
def update_selected_country(selected_country):
    """Store the selected country"""
    return selected_country if selected_country else "All"

@app.callback(
    Output("selected-state-store", "data"),
    Input("higher-lower-state-dropdown", "value"),
    prevent_initial_call=False
)
def update_selected_state(selected_state):
    """Store the selected state"""
    return selected_state if selected_state else "All"

@app.callback(
    Output("selected-district-store", "data"),
    Input("higher-lower-district-dropdown", "value"),
    prevent_initial_call=False
)
def update_selected_district(selected_district):
    """Store the selected district"""
    return selected_district if selected_district else "All"

@app.callback(
    [Output("higher-lower-state-dropdown", "options"),
     Output("higher-lower-state-dropdown", "value")],
    Input("higher-lower-country-dropdown", "value"),
    prevent_initial_call=False
)
def update_higher_lower_state_options(selected_country):
    """Update state dropdown options based on selected country and reset value"""
    with open('data/states.json', 'r', encoding='utf-8') as f:
        STATES = json.load(f)
    
    state_options = [{"label": "All States", "value": "All"}]
    if selected_country and selected_country != "All" and selected_country in STATES:
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
    
    # Reset state to "All" when country changes
    return state_options, "All"

@app.callback(
    [Output("teams-data-store", "data"),
     Output("game-state-store", "data"),
     Output("game-started-store", "data"),
     Output("teams-cache-store", "data")],
    [Input("higher-lower-start-btn", "n_clicks"),
     Input("url", "pathname")],
    [State("selected-year-store", "data"),
     State("selected-country-store", "data"),
     State("selected-state-store", "data"),
     State("selected-district-store", "data"),
     State("game-started-store", "data"),
     State("teams-cache-store", "data")],
    prevent_initial_call=False
)
def initialize_higher_lower_game(start_clicks, pathname, selected_year, selected_country, selected_state, selected_district, game_started, teams_cache):
    """Load teams data and initialize game when Start button is clicked"""
    if pathname != "/higher-lower":
        return no_update, no_update, no_update, no_update
    
    ctx = callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    
    # Only initialize when Start button is clicked (not on page load)
    if triggered_id != "higher-lower-start-btn" and not game_started:
        teams_cache = teams_cache or {}
        return [], {
            "score": 0,
            "highscore": 0,
            "wrong_guesses": 0,
            "left_team": None,
            "right_team": None,
            "left_ace": None,
            "right_ace": None
        }, False, teams_cache
    
    # Use selected year or default to current year
    year = selected_year if selected_year else current_year
    
    # Normalize filter values
    selected_country = selected_country if selected_country else "All"
    selected_state = selected_state if selected_state else "All"
    selected_district = selected_district if selected_district else "All"
    
    # Create cache key that includes filters
    cache_key = f"{year}_{selected_country}_{selected_state}_{selected_district}"
    
    # Check cache first - avoid reloading if we already have data for this filter combination
    teams_cache = teams_cache or {}
    if cache_key in teams_cache:
        teams_list = teams_cache[cache_key]
    else:
        # Load team data for the selected year (only once per year)
        teams_list = []
        try:
            # Load avatar cache once (globally cached, but ensure it's loaded)
            from datagather import _load_avatar_cache
            available_avatars = _load_avatar_cache()  # This is cached globally, fast after first call
            
            if year == current_year:
                # Use global TEAM_DATABASE for current year
                year_data = TEAM_DATABASE.get(current_year, {})
            else:
                # Load data for other years using load_year_data
                year_team_data, _, _, _, _, _ = load_year_data(year)
                year_data = year_team_data
            
            # Extract teams with valid ACE values and pre-compute avatar URLs
            # Filter first to avoid storing unnecessary data
            filtered_year_data = {}
            for team_num, team_data in year_data.items():
                if isinstance(team_data, dict):
                    ace = team_data.get("epa")
                    if ace is not None and ace > 0:  # Only include teams with valid ACE
                        filtered_year_data[team_num] = team_data
            
            # Apply filters BEFORE building teams_list to avoid storing unnecessary data
            if selected_country and selected_country != "All":
                filtered_year_data = {
                    num: data for num, data in filtered_year_data.items()
                    if (data.get("country") or "").lower() == selected_country.lower()
                }
            
            if selected_district and selected_district != "All":
                filtered_year_data = {
                    num: data for num, data in filtered_year_data.items()
                    if (data.get("district") or "").upper() == selected_district.upper()
                }
            elif selected_state and selected_state != "All":
                filtered_year_data = {
                    num: data for num, data in filtered_year_data.items()
                    if (data.get("state_prov") or "").lower() == selected_state.lower()
                }
            
            # Now build minimal teams_list with only the data we need
            for team_num, team_data in filtered_year_data.items():
                ace = team_data.get("epa")
                # Pre-compute avatar URL to avoid repeated lookups
                if 9970 <= team_num <= 9999:
                    avatar_url = "/assets/avatars/bbot.png?v=1"
                elif team_num in available_avatars:
                    avatar_url = f"/assets/avatars/{team_num}.png?v=1"
                else:
                    avatar_url = "/assets/avatars/stock.png"
                
                # Only store the minimal data needed for the game
                teams_list.append({
                    "team_number": team_num,
                    "nickname": team_data.get("nickname", f"Team {team_num}"),
                    "ace": ace,
                    "avatar_url": avatar_url
                })
            
            # Cache the filtered teams list with the cache key
            teams_cache[cache_key] = teams_list
        except Exception as e:
            print(f"Error loading team data for year {year}: {e}")
            return [], {
                "score": 0,
                "highscore": 0,
                "wrong_guesses": 0,
                "left_team": None,
                "right_team": None,
                "left_ace": None,
                "right_ace": None
            }, False, teams_cache
    
    # Initialize game state with two random teams
    if not teams_list:
        # No teams available
        new_game_state = {
            "score": 0,
            "highscore": 0,
            "wrong_guesses": 0,
            "left_team": None,
            "right_team": None,
            "left_ace": None,
            "right_ace": None
        }
        return teams_list, new_game_state, True, teams_cache
    
    # Pick two random teams
    selected_teams = random.sample(teams_list, min(2, len(teams_list)))
    left_team = selected_teams[0]
    right_team = selected_teams[1] if len(selected_teams) > 1 else selected_teams[0]
    
    new_game_state = {
        "score": 0,
        "highscore": 0,
        "wrong_guesses": 0,
        "left_team": left_team,
        "right_team": right_team,
        "left_ace": left_team["ace"],
        "right_ace": right_team["ace"]
    }
    
    return teams_list, new_game_state, True, teams_cache

@app.callback(
    [Output("game-state-store", "data", allow_duplicate=True),
     Output("reveal-transition-interval", "disabled")],
    [Input("higher-btn", "n_clicks"),
     Input("lower-btn", "n_clicks")],
    State("game-state-store", "data"),
    prevent_initial_call=True
)
def handle_guess(higher_clicks, lower_clicks, current_state):
    """Handle higher/lower button clicks - show reveal first, then transition"""
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update
    
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if not current_state or triggered_id not in ["higher-btn", "lower-btn"]:
        return no_update, no_update
    
    game_state = current_state.copy()
    left_team = game_state.get("left_team")
    right_team = game_state.get("right_team")
    left_ace = game_state.get("left_ace")
    right_ace = game_state.get("right_ace")
    
    if not left_team or not right_team:
        return no_update, no_update
    
    # Check if guess is correct
    is_higher = triggered_id == "higher-btn"
    correct = (is_higher and right_ace > left_ace) or (not is_higher and right_ace < left_ace)
    
    # Set reveal phase - show ACE with color feedback
    game_state["revealing"] = True
    game_state["reveal_correct"] = correct
    game_state["reveal_right_ace"] = right_ace
    
    # Store pending changes (don't apply until after reveal)
    if correct:
        score = game_state.get("score", 0) + 1
        highscore = game_state.get("highscore", 0)
        if score > highscore:
            highscore = score
        game_state["pending_score"] = score
        game_state["pending_highscore"] = highscore
        game_state["pending_transition"] = True  # Mark that we need to transition teams
    else:
        wrong_guesses = game_state.get("wrong_guesses", 0) + 1
        game_state["pending_wrong_guesses"] = wrong_guesses
    
    # Enable interval to transition after reveal
    return game_state, False  # False = interval enabled

@app.callback(
    [Output("game-state-store", "data", allow_duplicate=True),
     Output("reveal-transition-interval", "disabled", allow_duplicate=True),
     Output("pick-new-team-trigger", "n_clicks", allow_duplicate=True)],
    Input("reveal-transition-interval", "n_intervals"),
    [State("game-state-store", "data"),
     State("pick-new-team-trigger", "n_clicks")],
    prevent_initial_call=True
)
def transition_after_reveal(n_intervals, current_state, current_trigger_clicks):
    """Transition to next round after ACE reveal - trigger team pick separately"""
    if not current_state or not current_state.get("revealing"):
        return no_update, no_update, no_update
    
    game_state = current_state.copy()
    
    # Clear reveal state
    game_state["revealing"] = False
    game_state.pop("reveal_correct", None)
    game_state.pop("reveal_right_ace", None)
    
    # Apply pending changes
    if "pending_score" in game_state:
        game_state["score"] = game_state.pop("pending_score")
        game_state["highscore"] = game_state.pop("pending_highscore")
        
        # Only transition teams if marked - trigger separate callback to pick new team
        if game_state.pop("pending_transition", False):
            # Move right team to left
            right_team = game_state.get("right_team")
            right_ace = game_state.get("right_ace")
            
            game_state["left_team"] = right_team
            game_state["left_ace"] = right_ace
            game_state["needs_new_right_team"] = True  # Flag to pick new team
            
            # Trigger team pick callback by incrementing trigger
            return game_state, True, (current_trigger_clicks or 0) + 1
    elif "pending_wrong_guesses" in game_state:
        game_state["wrong_guesses"] = game_state.pop("pending_wrong_guesses")
    
    # Disable interval after transition
    return game_state, True, no_update  # True = interval disabled

@app.callback(
    Output("game-state-store", "data", allow_duplicate=True),
    Input("pick-new-team-trigger", "n_clicks"),
    [State("game-state-store", "data"),
     State("teams-data-store", "data")],
    prevent_initial_call=True
)
def pick_new_right_team(trigger_clicks, current_state, teams_data):
    """Pick a new random team for right side - only called when needed"""
    if not trigger_clicks or not current_state or not teams_data:
        return no_update
    
    game_state = current_state.copy()
    
    # Only pick if flag is set
    if not game_state.get("needs_new_right_team"):
        return no_update
    
    # Clear the flag
    game_state.pop("needs_new_right_team", None)
    
    # Get current right team number to exclude it
    right_team = game_state.get("right_team")
    if not right_team:
        return no_update
    
    # Pick a new random team - only iterate through teams_data here
    current_right_num = right_team["team_number"]
    available_teams = [t for t in teams_data if t["team_number"] != current_right_num]
    
    if available_teams:
        new_right_team = random.choice(available_teams)
        game_state["right_team"] = new_right_team
        game_state["right_ace"] = new_right_team["ace"]
    
    return game_state

# Optimized display callbacks - split into smaller callbacks to avoid recreating all HTML
@app.callback(
    [Output("left-team-avatar-container", "children"),
     Output("left-team-name", "children"),
     Output("left-team-ace", "children")],
    Input("game-state-store", "data"),
    [State("selected-year-store", "data")],
    prevent_initial_call=False
)
def update_left_team_display(game_state, selected_year):
    """Update left team display - only when left team changes"""
    if not game_state:
        return html.Div(), "Loading...", "0.0"
    
    left_team = game_state.get("left_team")
    left_ace = game_state.get("left_ace")
    
    if not left_team:
        return html.Div(), "Loading...", "0.0"
    
    team_num = left_team["team_number"]
    avatar_url = left_team.get("avatar_url", f"/assets/avatars/{team_num}.png?v=1")
    year = selected_year if selected_year else current_year
    
    left_avatar = html.Img(
        src=avatar_url,
        style={
            "width": "200px",
            "height": "200px",
            "objectFit": "contain",
            "borderRadius": "50%",
            "border": "3px solid white"
        }
    )
    left_name = html.A(
        f"{left_team['nickname']} ({team_num})",
        href=f"/team/{team_num}/{year}",
        style={
            "color": "var(--text-primary)",
            "textDecoration": "underline",
            "cursor": "pointer"
        }
    )
    left_ace_display = f"{left_ace:.1f}" if left_ace is not None else "0.0"
    
    return left_avatar, left_name, left_ace_display

@app.callback(
    [Output("right-team-avatar-container", "children"),
     Output("right-team-name", "children")],
    Input("game-state-store", "data"),
    [State("selected-year-store", "data")],
    prevent_initial_call=False
)
def update_right_team_display(game_state, selected_year):
    """Update right team display - only when right team changes"""
    if not game_state:
        return html.Div(), "Loading..."
    
    right_team = game_state.get("right_team")
    
    if not right_team:
        return html.Div(), "Loading..."
    
    team_num = right_team["team_number"]
    avatar_url = right_team.get("avatar_url", f"/assets/avatars/{team_num}.png?v=1")
    year = selected_year if selected_year else current_year
    
    right_avatar = html.Img(
        src=avatar_url,
        style={
            "width": "200px",
            "height": "200px",
            "objectFit": "contain",
            "borderRadius": "50%",
            "border": "3px solid white"
        }
    )
    right_name = html.A(
        f"{right_team['nickname']} ({team_num})",
        href=f"/team/{team_num}/{year}",
        style={
            "color": "var(--text-primary)",
            "textDecoration": "underline",
            "cursor": "pointer"
        }
    )
    
    return right_avatar, right_name

@app.callback(
    [Output("right-team-ace-container", "children"),
     Output("higher-lower-buttons-container", "style")],
    Input("game-state-store", "data"),
    prevent_initial_call=False
)
def update_right_ace_and_buttons(game_state):
    """Update right ACE container and button visibility - optimized"""
    if not game_state:
        return html.Div(style={"display": "none"}), {"display": "none"}
    
    wrong_guesses = game_state.get("wrong_guesses", 0)
    right_ace = game_state.get("right_ace")
    revealing = game_state.get("revealing", False)
    reveal_right_ace = game_state.get("reveal_right_ace")
    reveal_correct = game_state.get("reveal_correct", False)
    right_team = game_state.get("right_team")
    
    game_over = wrong_guesses >= 3
    
    if not right_team:
        return html.Div(style={"display": "none"}), {"display": "none"}
    
    if game_over:
        right_ace_container = html.Div(
            f"{right_ace:.1f}" if right_ace is not None else "0.0",
            style={
                "fontSize": "3rem",
                "fontWeight": "bold",
                "textAlign": "center",
                "color": "var(--text-primary)"
            }
        )
        buttons_container_style = {"display": "none"}
    elif revealing and reveal_right_ace is not None:
        color = "#28a745" if reveal_correct else "#dc3545"
        right_ace_container = html.Div(
            f"{reveal_right_ace:.1f}",
            style={
                "fontSize": "3rem",
                "fontWeight": "bold",
                "textAlign": "center",
                "color": color,
                "transition": "opacity 0.3s ease-in-out, color 0.3s ease-in-out",
                "opacity": 1
            }
        )
        buttons_container_style = {"display": "none"}
    else:
        right_ace_container = html.Div(style={"display": "none"})
        buttons_container_style = {"textAlign": "center", "marginBottom": "10px"}
    
    return right_ace_container, buttons_container_style

@app.callback(
    [Output("score-display", "children"),
     Output("highscore-display", "children")],
    Input("game-state-store", "data"),
    prevent_initial_call=False
)
def update_scores(game_state):
    """Update score displays - only when scores change"""
    if not game_state:
        return "0", "0"
    
    score = game_state.get("score", 0)
    highscore = game_state.get("highscore", 0)
    
    return str(score), str(highscore)

@app.callback(
    [Output("game-over-message", "children"),
     Output("game-over-message", "style")],
    Input("game-state-store", "data"),
    prevent_initial_call=False
)
def update_game_over_message(game_state):
    """Update game over message - only when game over state changes"""
    if not game_state:
        return html.Div(), {"display": "none"}
    
    wrong_guesses = game_state.get("wrong_guesses", 0)
    score = game_state.get("score", 0)
    highscore = game_state.get("highscore", 0)
    
    game_over = wrong_guesses >= 3
    
    if not game_over:
        return html.Div(), {"display": "none"}
    
    game_over_msg = html.Div([
        html.H3("Game Over!", style={"color": "var(--text-primary)", "marginBottom": "20px"}),
        html.P(f"Final Score: {score}", style={"fontSize": "1.5rem", "color": "var(--text-primary)", "marginBottom": "10px"}),
        html.P(f"Highscore: {highscore}", style={"fontSize": "1.2rem", "color": "var(--text-secondary)", "marginBottom": "20px"}),
        dbc.Button("Play Again", id="play-again-btn", color="primary", size="lg",
                  style={"padding": "15px 40px", "fontSize": "1.2rem"})
    ], style={"textAlign": "center"})
    
    return game_over_msg, {"display": "block", "textAlign": "center", "padding": "20px"}

@app.callback(
    [Output("higher-btn", "disabled"),
     Output("lower-btn", "disabled")],
    Input("game-state-store", "data"),
    prevent_initial_call=False
)
def update_button_states(game_state):
    """Update button disabled states - only when relevant state changes"""
    if not game_state:
        return True, True
    
    wrong_guesses = game_state.get("wrong_guesses", 0)
    revealing = game_state.get("revealing", False)
    
    game_over = wrong_guesses >= 3
    buttons_disabled = game_over or revealing
    
    return buttons_disabled, buttons_disabled

@app.callback(
    [Output("game-state-store", "data", allow_duplicate=True),
     Output("pick-new-team-trigger", "n_clicks", allow_duplicate=True)],
    Input("play-again-btn", "n_clicks"),
    [State("teams-data-store", "data"),
     State("game-state-store", "data")],
    prevent_initial_call=True
)
def reset_game(play_again_clicks, teams_data, current_state):
    """Reset the game when Play Again is clicked"""
    if not play_again_clicks or not teams_data:
        return no_update, no_update
    
    # Preserve highscore
    highscore = current_state.get("highscore", 0) if current_state else 0
    
    # Pick two random teams - only access teams_data here when needed
    selected_teams = random.sample(teams_data, min(2, len(teams_data)))
    left_team = selected_teams[0]
    right_team = selected_teams[1] if len(selected_teams) > 1 else selected_teams[0]
    
    return {
        "score": 0,
        "highscore": highscore,
        "wrong_guesses": 0,
        "left_team": left_team,
        "right_team": right_team,
        "left_ace": left_team["ace"],
        "right_ace": right_team["ace"]
    }, no_update
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=False)