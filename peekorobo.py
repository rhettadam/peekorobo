import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc, dash_table, ctx, ALL, MATCH, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import flask
from flask import session
from auth import register_user, verify_user

import os
import numpy as np
import datetime
from datetime import datetime, date

import re
from urllib.parse import parse_qs, urlencode
import json
import pandas as pd

import plotly.graph_objects as go
from scipy.interpolate import interp1d

from datagather import COUNTRIES,STATES,load_data_2025,load_search_data,load_year_data,get_team_avatar,DISTRICT_STATES,DISTRICT_STATES_A,DatabaseConnection,get_team_years_participated

from layouts import home_layout,footer,topbar,blog_layout,challenges_layout,challenge_details_layout,teams_map_layout,login_layout,create_team_card,teams_layout,epa_legend_layout,events_layout, build_recent_events_section, compare_layout

from utils import calculate_single_rank,pill,predict_win_probability,calculate_all_ranks,get_user_avatar,get_epa_styling,compute_percentiles,sort_key,get_available_avatars,get_contrast_text_color,parse_event_key,user_team_card,user_event_card,team_link_with_avatar,wrap_with_toast_or_star,get_week_number,event_card,truncate_name

from dotenv import load_dotenv
load_dotenv()

# Load optimized data: 2025 data globally + search data with all events
TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES = load_data_2025()
SEARCH_TEAM_DATA, SEARCH_EVENT_DATA = load_search_data()

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

server = app.server
server.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-placeholder-key")

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='tab-title', data='Peekorobo'),
    dcc.Store(id='theme-store'),
    html.Div(
        id='page-content-animated-wrapper',
        children=html.Div(id='page-content'),
        className='fade-page'
    ),
    html.Div(id='dummy-output', style={'display': 'none'}),
    html.Button(id='page-load-trigger', n_clicks=1, style={'display': 'none'})
])

def user_layout(_user_id=None, deleted_items=None):

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
                    html.A(team_affil, href=f"/team/{team_affil}/2025", style={
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
        for team_num, data in TEAM_DATABASE.get(2025, {}).items()
    }
    
    team_cards = []
    for team_key in team_keys:
        try:
            team_number = int(team_key)
        except:
            continue

        team_data = TEAM_DATABASE.get(2025, {}).get(team_number)
        year_data = TEAM_DATABASE.get(2025, {})

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
                    html.Span(f" in 2025.")
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
                href=f"/team/{team_key}/2025",
                style={"textDecoration": "none", "color": "inherit"}
            ),

            [
                html.Img(src=get_team_avatar(team_key), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, 2025, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
            ],
            delete_button=delete_team_btn
        ))

    event_cards = []
    for event_key in event_keys:
        if event_key not in EVENT_DATABASE.get(2025, {}):
            continue  # Skip deleted or invalid events
    
        # Skip 2025cmptx unless team actually participated
        if event_key == "2025cmptx":
            year = 2025
            # Check for matches
            played_matches = any(
                str(team_number) in m.get("rt", "").split(",") or str(team_number) in m.get("bt", "").split(",")
                for m in EVENT_MATCHES.get(year, [])
                if m.get("ek") == "2025cmptx"
            )
            # Check for awards
            earned_awards = any(
                aw["tk"] == team_number and aw["ek"] == "2025cmptx" and aw["y"] == 2025
                for aw in EVENT_AWARDS
            )
    
            if not played_matches and not earned_awards:
                continue  # skip Einstein if no participation
    
        year = 2025
        matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
        # ... rest of your card building logic ...

        delete_event_btn = html.Button(
            html.Img(
                src="/assets/trash.png",
                style={
                    "width": "20px",
                    "height": "20px",
                    "verticalAlign": "middle"
                }
            ),
            id={"type": "delete-favorite", "item_type": "event", "key": event_key},
            style={
                "backgroundColor": "transparent",
                "border": "none",
                "cursor": "pointer",
                "padding": "4px"
            }
        )

        match_rows = []
        if matches:
            match_rows = [
                m for m in matches
                if any(t.strip().isdigit() for t in (m.get("rt", "") + "," + m.get("bt", "")).split(","))
            ]
            event_teams = EVENT_TEAMS.get(2025, {}).get(event_key, [])
            fav_team_numbers = [int(k) for k in team_keys if k.isdigit()]
            matched_team = next((t for t in event_teams if int(t["tk"]) in fav_team_numbers), None)
            
            if matched_team:
                team_number = int(matched_team["tk"])
                event_section = build_recent_events_section(f"frc{team_number}", team_number, epa_data, 2025, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
                match_rows = event_section.children[-1].children
            else:
                match_rows = [html.P("No favorited teams at this event.")]


        event_data = EVENT_DATABASE.get(year, {}).get(event_key, {})
        event_name = event_data.get("n", "Unknown Event")
        event_label = f"{event_name} | {event_key}"
        event_url = f"/event/{event_key}"
        location = ", ".join(filter(None, [event_data.get("c", ""), event_data.get("s", ""), event_data.get("co", "")]))
        

        event_cards.append(user_event_card(
            body_elements=[
                html.Div([
                    html.A(
                        event_label,
                        href=event_url,
                        style={
                            "fontWeight": "bold",
                            "fontSize": "1.1rem",
                            "textDecoration": "underline",
                            "color": "#007bff",
                            "cursor": "pointer"
                        }
                    ),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
        
                html.Div(location, style={"fontSize": "0.85rem", "color": "#666", "marginBottom": "0.5rem"}),
                html.Hr(),
            ]
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
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer
    ])

def other_user_layout(username):
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
        for team_num, data in TEAM_DATABASE.get(2025, {}).items()
    }

    team_cards = []
    for team_key in team_keys:
        try:
            team_number = int(team_key)
        except:
            continue

        team_data = TEAM_DATABASE.get(2025, {}).get(team_number)
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
        for other in TEAM_DATABASE.get(2025, {}).values():
            if (other.get("epa", 0) or 0) > epa:
                global_rank += 1
                if (other.get("country") or "").lower() == country:
                    country_rank += 1
                if (other.get("state_prov") or "").lower() == state:
                    state_rank += 1

        year_data = list(TEAM_DATABASE.get(2025, {}).values())

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
                html.Span(f" in {year_data[0].get('year', 2025) if year_data else 2025}.")
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
                href=f"/team/{team_key}/2025",
                style={"textDecoration": "none", "color": "inherit"}
            ),
            [
                html.Img(src=get_team_avatar(team_key), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, 2025, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
            ]
        ))

    event_cards = []
    for event_key in event_keys:
        if event_key not in EVENT_DATABASE.get(2025, {}):
            continue  # Skip deleted or invalid events
        event_data = EVENT_DATABASE.get(2025, {}).get(event_key, {})
        event_name = event_data.get("n", "Unknown Event")
        location = ", ".join(filter(None, [event_data.get("c", ""), event_data.get("s", ""), event_data.get("co", "")]))

        matches = [m for m in EVENT_MATCHES.get(2025, []) if m.get("ek") == event_key]
        event_teams = EVENT_TEAMS.get(2025, {}).get(event_key, [])
        fav_team_numbers = [int(k) for k in team_keys if k.isdigit()]
        matched_team = next((t for t in event_teams if int(t["tk"]) in fav_team_numbers), None)

        if matched_team:
            team_number = int(matched_team["tk"])
            section = build_recent_events_section(f"frc{team_number}", team_number, epa_data, 2025, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS)
        else:
            section = html.P("No favorited teams at this event.")

        event_cards.append(
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.A(f"{event_name} | {event_key}", href=f"/event/{event_key}", style={"fontWeight": "bold", "fontSize": "1.1rem", "textDecoration": "underline", "color": "#007bff"})
                    ], style={"display": "flex", "justifyContent": "space-between"}),
                    html.Div(location, style={"fontSize": "0.85rem", "color": "#666", "marginBottom": "0.5rem"}),
                    html.Hr(),
                    section
                ]),
                className="mb-4",
                style={"borderRadius": "10px", "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)", "backgroundColor": "var(--card-bg)"}
            )
        )

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
                    html.A(team, href=f"/team/{team}/2025", style={
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
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer,
    ])


@app.server.route("/logout")
def logout():
    flask.session.clear()
    return flask.redirect("/login")

@callback(
    Output("profile-display", "hidden"),
    Output("profile-card", "style"),
    Output("profile-edit-form", "hidden"),
    Output("save-profile-btn", "style"),
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
        return [dash.no_update] * 15

    user_id = session_data if isinstance(session_data, str) else session_data.get("user_id") if session_data else None
    if not user_id:
        return [dash.no_update] * 15

    if triggered_id == "save-profile-btn":
        if not username or len(username.strip()) < 3:
            return [dash.no_update] * 15

        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                cur.execute("SELECT id FROM users WHERE LOWER(username) = %s AND id != %s", (username.lower(), user_id))
                if cur.fetchone():
                    return [dash.no_update] * 15

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
            print(f"Error saving profile: {e}")
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
            0,
            get_user_avatar(avatar_key_selected),
            html.Span(f"Role: {new_role}", style={"color": text_color}),
            html.Span([
                html.Span("Team: ", style={"color": text_color, "fontWeight": "500"}),
                html.A(new_team, href=f"/team/{new_team}/2025", style={"color": text_color, "textDecoration": "underline"})
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
            print(f"Error loading color on edit: {e}")
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
            dash.no_update,
            dash.no_update,
            html.Span(f"Role: {role}", style={"color": text_color}),
            html.Span([
                "Team: ",
                html.A(team, href=f"/team/{team}/2025", style={"color": text_color, "textDecoration": "underline"})
            ]),
            html.Div(bio, style={"color": text_color}),
            {"color": text_color},  # profile-header
            {"color": text_color},  # profile-subheader
            {"color": text_color},  # profile-search-header
            {"color": text_color, "fontWeight": "500"},  # profile-followers style
            {"color": text_color, "fontWeight": "500"},  # profile-following style
            f"Followers: {followers_count}",  # profile-followers children
        )

    return [dash.no_update] * 15
    
@callback(
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
        print("Error during follow/unfollow:", e)
        return current_text

@callback(
    Output("user-search-results", "children"),
    Input("user-search-input", "value"),
    State("user-session", "data")
)
def search_users(query, session_data):
    if not query or not session_data:
        return []

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
            followers = json.loads(followers) if isinstance(followers, str) else (followers or [])
            is_following = current_user_id in followers
            avatar_src = get_user_avatar(avatar_key or "stock")

            user_blocks.append(html.Div([
                html.Img(src=avatar_src, style={
                    "height": "32px", "width": "32px", "borderRadius": "50%", "marginRight": "8px"
                }),
                html.A(username, href=f"/user/{username}", style={
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

    except Exception as e:
        print(f"Error searching users: {e}")
        return []

@callback(
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
        return new_store, user_layout(user_id, deleted)
    except Exception as e:
        print(f"Error removing favorite: {e}")
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
                print(f"Error getting user ID after registration: {e}")
                return "Registration successful but login failed. Please try logging in.", dash.no_update
        else:
            return message, dash.no_update

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

    # Use search-specific data: 2025 teams and all events
    teams_data = list(SEARCH_TEAM_DATA[2025].values())
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
            print("User search error:", e)
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
                background_color = "var(--card-bg)"
                is_highlighted = False
                if (closest_team_number and tn == closest_team_number["team_number"]) or \
                   (closest_team_nickname and nm == closest_team_nickname["nickname"]):
                    background_color = "#FFDD0080"
                    is_highlighted = True

                team_link_element = html.A([
                    html.Img(src=get_team_avatar(tn), style={
                        "height": "20px", "width": "20px", "borderRadius": "50%", "marginRight": "8px"
                    }),
                    html.Span(f"{tn} | {nm}")
                ], href=f"/team/{tn}/2025", style={
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
        print(f"Error favoriting team: {e}")
        return "Error favoriting team.", True

@app.callback(
    [
        Output("events-tab-content", "children"),
        Output("district-dropdown", "options"),
    ],
    [
        Input("events-tabs", "active_tab"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("week-dropdown", "value"),
        Input("search-input", "value"),
        Input("district-dropdown", "value"),
        Input("sort-mode-toggle", "value"),
        Input("event-favorites-store", "data"),
    ],
)
def update_events_tab_content(
    active_tab,
    selected_year,
    selected_event_types,
    selected_week,
    search_query,
    selected_district,
    sort_mode,
    store_data,
):
    user_favorites = set(store_data or [])
    
    # Load data for the selected year
    if selected_year == 2025:
        # Use global data for 2025
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
        
        # Special cases for non-US districts
        if country == "Israel":
            return "ISR"
        if country == "Canada":
            return "ONT"
        
        # Check US states against DISTRICT_STATES
        for district_acronym, states in DISTRICT_STATES_A.items():
            if state in states:
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

    if "all" not in selected_event_types:
        filtered = []
        for et in selected_event_types:
            if et == "season":
                filtered.extend([ev for ev in events_data if ev.get("et") not in [99, 100]])
            elif et == "offseason":
                filtered.extend([ev for ev in events_data if ev.get("et") in [99, 100]])
            elif et == "regional":
                filtered.extend([ev for ev in events_data if "regional" in (ev.get("et") or "").lower()])
            elif et == "district":
                filtered.extend([ev for ev in events_data if "district" in (ev.get("et") or "").lower()])
            elif et == "championship":
                filtered.extend([ev for ev in events_data if "championship" in (ev.get("et") or "").lower()])
        events_data = list({ev["k"]: ev for ev in filtered}.values())

    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    def truncate_name(name, max_length=32):
        return name if len(name) <= max_length else name[:max_length-3] + '...'

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

    if sort_mode == "time":
        events_data.sort(key=lambda x: x["_start_date_obj"])
    elif sort_mode == "alpha":
        events_data.sort(key=lambda x: x.get("n", "").lower())

    if active_tab == "table-tab":
        # Create year-specific databases for the compute function
        year_event_database = {selected_year: {ev["k"]: ev for ev in events_data}}
        df = compute_event_insights_from_data(year_event_teams, year_event_database, year_team_database, selected_year)
    
        # Sort by "Top 8 ACE"
        df = df.sort_values(by="Top 8 ACE", ascending=False).reset_index(drop=True)
    
        # Ensure no NaNs interfere with percentile calculations
        percentiles_map = {}
        for col in ["Max ACE", "Top 8 ACE", "Top 24 ACE"]:
            values = df[col].dropna().values
            percentiles_map[col] = np.percentile(values, [99, 95, 90, 75, 50, 25])
    
        # Define color scale by percentile
        def get_color(value, thresholds):
            if value >= thresholds[0]: return "#6a1b9a"  # Purple
            if value >= thresholds[1]: return "#1565c0"  # Blue
            if value >= thresholds[2]: return "#2e7d32"  # Green
            if value >= thresholds[3]: return "#f9a825"  # Yellow
            if value >= thresholds[4]: return "#ef6c00"  # Orange
            if value >= thresholds[5]: return "#c62828"  # Red
            return "#4e342e"                             # Brown
    
        # Create conditional styling for each EPA cell
        style_data_conditional = []
        for i, row in df.iterrows():
            for col in ["Max ACE", "Top 8 ACE", "Top 24 ACE"]:
                color = get_color(row[col], percentiles_map[col])
                style_data_conditional.append({
                    "if": {"row_index": i, "column_id": col},
                    "backgroundColor": color,
                    "color": "white",
                    "fontWeight": "bold",
                    "borderRadius": "6px",
                })
    
        return dash_table.DataTable(
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
        ), district_options


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
    
    return html.Div([
        upcoming_section,
        html.Br(),
        ongoing_section,
        html.Br(),
        html.Div(all_event_cards, className="d-flex flex-wrap justify-content-center"),
    ]), district_options

def event_layout(event_key):
    parsed_year, _ = parse_event_key(event_key)
    
    # Load data for the specific year
    if parsed_year == 2025:
        # Use global data for 2025
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
    website = event.get("w", "#")

    # Header card
    header_card = dbc.Card(
        html.Div([
            dbc.CardBody([
                html.H2(f"{event_name} ({parsed_year})", className="card-title mb-3", style={"fontWeight": "bold"}),
                html.P(f"Location: {event_location}", className="card-text"),
                html.P(f"Dates: {start_date} - {end_date}", className="card-text"),
                html.P(f"Type: {event_type}", className="card-text"),
                dbc.Button(
                    "Visit Website",
                    href=website,
                    external_link=True,
                    className="mt-3",
                    style={
                        "backgroundColor": "#FFCC00",
                        "borderColor": "#FFCC00",
                        "color": "black",
                    },
                )
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
            dbc.Tab(label="Matches", tab_id="matches", label_style=tab_style, active_label_style=tab_style),
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
                    html.Div(id="data-display-container"),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

# Add a callback to set the event-tab-store from the URL's search string
@app.callback(
    Output("event-tab-store", "data"),
    Input("url", "search"),
)
def set_event_tab_from_url(search):
    if search and search.startswith("?"):
        params = parse_qs(search[1:])
        tab = params.get("tab", [None])[0]
        if tab in ["teams", "rankings", "matches"]:
            return tab
    return "teams"

# Add a callback to set the active_tab of event-data-tabs from event-tab-store
@app.callback(
    Output("event-data-tabs", "active_tab"),
    Input("event-tab-store", "data"),
)
def set_event_tabs_active_tab(tab):
    return tab

@callback(
    Output("data-display-container", "children"),
    Output("event-url", "search"),  # NEW: update the event tab URL
    Input("event-data-tabs", "active_tab"),
    State("store-rankings", "data"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-event-matches", "data"),
    State("store-event-year", "data"),
    State("url", "pathname"),  # get the event_key from the URL
)
def update_event_display(active_tab, rankings, epa_data, event_teams, event_matches, event_year, pathname):

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

        # === EPA & Rank Calculation (standalone) ===
        team_epas = [
            (tnum, data.get("epa", 0))
            for tnum, data in all_teams.items()
            if isinstance(data, dict)
        ]
        team_epas.sort(key=lambda x: x[1], reverse=True)
        rank_map = {tnum: i + 1 for i, (tnum, _) in enumerate(team_epas)}

        team_epa = team_data.get("epa", 0)
        epa_display = f"{team_epa:.1f}"
        epa_rank = rank_map.get(t_num, "N/A")

        # === Avatar and link ===
        avatar_url = get_team_avatar(t_num, event_year)
        team_url = f"/team/{t_num}/{event_year}"

        # === Card Layout ===
        card_body = dbc.CardBody(
            [
                html.H5(f"#{t_num} | {nickname}", className="card-title", style={
                    "fontSize": "1.1rem",
                    "textAlign": "center",
                    "marginBottom": "0.5rem"
                }),
                html.P(f"Location: {location_str}", className="card-text", style={
                    "fontSize": "0.9rem",
                    "textAlign": "center",
                    "marginBottom": "0.5rem"
                }),
                html.P(f"ACE: {epa_display} (Global Rank: {epa_rank})", className="card-text", style={
                    "fontSize": "0.9rem",
                    "textAlign": "center",
                    "marginBottom": "auto"
                }),
                dbc.Button(
                    "View Team",
                    href=team_url,
                    color="warning",
                    outline=True,
                    className="custom-view-btn mt-3",
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "flexGrow": "1",
                "justifyContent": "space-between",
                "padding": "1rem"
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
                        "height": "150px",
                        "objectFit": "contain",
                        "backgroundColor": "transparent",
                        "padding": "0.5rem"
                    }
                )
            )

        card_elements.append(card_body)

        return dbc.Card(
            card_elements,
            className="m-2 shadow-sm",
            style={
                "width": "18rem",
                "height": "22rem",
                "display": "flex",
                "flexDirection": "column",
                "justifyContent": "space-between",
                "alignItems": "stretch",
                "borderRadius": "12px"
            },
        )
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
    if event_year == 2025:
        year_team_data = TEAM_DATABASE # Use global data for 2025
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
    auto_values = [data.get("auto_epa", 0) for data in epa_data.values()]
    teleop_values = [data.get("teleop_epa", 0) for data in epa_data.values()]
    endgame_values = [data.get("endgame_epa", 0) for data in epa_data.values()]

    percentiles_dict = {
        "ACE": compute_percentiles(epa_values),
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
            team_data = year_team_data.get(int(team_num), {})
            nickname = team_data.get("nickname", "Unknown")

            data_rows.append({
                "Rank": rank_info.get("rk", "N/A"),
                "Team": f"[{tstr} | {nickname}](/team/{tstr}/{event_year})",
                "Wins": rank_info.get("w", "N/A"),
                "Losses": rank_info.get("l", "N/A"),
                "Ties": rank_info.get("t", "N/A"),
                "DQ": rank_info.get("dq", "N/A"),
                "ACE Rank": rank_map.get(int(tstr), "N/A"),
                "ACE": epa_data.get(tstr, {}).get("epa", "N/A"),
            })

        data_rows.sort(key=lambda r: safe_int(r["Rank"]))

        columns = [
            {"name": "Rank", "id": "Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "Wins", "id": "Wins"},
            {"name": "Losses", "id": "Losses"},
            {"name": "Ties", "id": "Ties"},
            {"name": "DQ", "id": "DQ"},
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
        ]

        return html.Div([
            epa_legend_layout(),
            dash_table.DataTable(
                columns=columns,
                data=data_rows,
                page_size=10,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_data_conditional=style_data_conditional
            )
        ]), query_string

    # === Teams Tab ===
    elif active_tab == "teams":

        if event_year != 2025:
            year_team_data = {event_year: year_team_data}
        
        # Sort teams by overall EPA from year_team_database
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
        spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")

        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            # Convert team number to integer for year_team_database lookup
            team_data = year_team_data.get(event_year, {}).get(int(tnum), {})
            
            rows.append({
                "ACE Rank": rank_map.get(int(tnum), "N/A"),
                "ACE": f"{team_data.get('epa', 0):.2f}",
                "Auto": f"{team_data.get('auto_epa', 0):.2f}",
                "Teleop": f"{team_data.get('teleop_epa', 0):.2f}",
                "Endgame": f"{team_data.get('endgame_epa', 0):.2f}",
                "Team": f"[{tstr} | {t.get('nn', 'Unknown')}](/team/{tstr}/{event_year})",
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })

        # Sort by overall EPA value
        rows.sort(key=lambda r: float(r["ACE"]) if r["ACE"] != "N/A" else 0, reverse=True)

        columns = [
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "ACE", "id": "ACE"},
            {"name": "Auto", "id": "Auto"},
            {"name": "Teleop", "id": "Teleop"},
            {"name": "Endgame", "id": "Endgame"},
            {"name": "Location", "id": "Location"},
        ]

        return html.Div([
            html.H4("Spotlight Teams", className="text-center mb-4", style={"fontWeight": "bold"}),
            spotlight_layout,
            epa_legend_layout(),
            dash_table.DataTable(
                columns=columns,
                data=rows,
                page_size=10,
                style_table=common_style_table,
                style_header=common_style_header,
                style_cell=common_style_cell,
                style_data_conditional=style_data_conditional
            )
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
                ], md=6),
                dbc.Col([
                    dbc.Button(
                        "Create Playlist ▶︎",
                        id="create-playlist-btn",
                        color="warning",
                        className="w-100",
                        style={"marginTop": "10px"}
                    )
                ], md=6, className="d-flex align-items-end")
            ], className="mb-4"),
            html.Div(id="matches-container")
        ]), query_string

    return dbc.Alert("No data available.", color="warning"), query_string

@app.callback(
    Output("matches-container", "children"),
    Input("team-filter", "value"),
    [
        State("store-event-matches", "data"),
        State("store-event-epa", "data"),
        State("store-event-year", "data"),  # Add event year state
    ],
)
def update_matches_table(selected_team, event_matches, epa_data, event_year):
    event_matches = event_matches or []
    epa_data = epa_data or {}
    event_year = event_year or 2025  # Default fallback
    
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
            if event_year == 2025:
                team_data = TEAM_DATABASE.get(event_year, {}).get(int(t_key), {})
            else:
                try:
                    year_team_data, _, _, _, _, _ = load_year_data(event_year)
                    team_data = year_team_data.get(int(t_key), {})
                except Exception:
                    team_data = {}
            return {
                "epa": team_data.get("epa", 0),
                "confidence": team_data.get("confidence", 0.7),
            }
        # Use event-specific EPA data, but ensure confidence has a reasonable fallback
        return {
            "epa": info.get("epa", 0),
            "confidence": info.get("confidence", 0.7),  # Use 0.7 as fallback instead of 0
        }
    
    def build_match_rows(matches):
        rows = []
        for match in matches:
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
                pred_red = "50%"
                pred_blue = "50%"
                pred_winner = "Tie"
            else:
                pred_red = f"{p_red:.0%}"
                pred_blue = f"{p_blue:.0%}"
                pred_winner = "Red" if p_red > p_blue else "Blue"

            yid = match.get("yt")
            video_link = f"[Watch](https://www.youtube.com/watch?v={yid})" if yid else "N/A"

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Alliance": format_teams_markdown(red_str),
                "Blue Alliance": format_teams_markdown(blue_str),
                "Red Score": red_score,
                "Blue Score": blue_score,
                "Winner": winner.title() if winner else "Tie",
                "Pred Winner": pred_winner,
                "Red Pred": pred_red,
                "Blue Pred": pred_blue,
                "Red Prediction %": p_red * 100,  # For conditional styling
                "Blue Prediction %": p_blue * 100,  # For conditional styling
            })
        return rows

    qual_data = build_match_rows(qual_matches)
    playoff_data = build_match_rows(playoff_matches)

    match_columns = [
        {"name": "Video", "id": "Video", "presentation": "markdown"},
        {"name": "Match", "id": "Match"},
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
        # Row coloring for winner (these should come first)
        {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
        {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
        # --- Cell-level prediction rules (these should come after row-level rules) ---
        # Red prediction styling
        {"if": {"filter_query": "{Red Prediction %} >= 45 && {Red Prediction %} <= 55", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-neutral)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} > 55 && {Red Prediction %} <= 65", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} > 65 && {Red Prediction %} <= 75", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} > 75 && {Red Prediction %} <= 85", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} > 85 && {Red Prediction %} <= 95", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} > 95", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} < 45 && {Red Prediction %} >= 35", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} < 35 && {Red Prediction %} >= 25", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} < 25 && {Red Prediction %} >= 15", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} < 15 && {Red Prediction %} >= 5", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-darkred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Red Prediction %} < 5", "column_id": "Red Pred"}, "backgroundColor": "var(--table-row-prediction-deepred)", "color": "var(--text-primary)"},
        # Blue prediction styling
        {"if": {"filter_query": "{Blue Prediction %} >= 45 && {Blue Prediction %} <= 55", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-neutral)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} > 55 && {Blue Prediction %} <= 65", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} > 65 && {Blue Prediction %} <= 75", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightergreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} > 75 && {Blue Prediction %} <= 85", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightestgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} > 85 && {Blue Prediction %} <= 95", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-darkgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} > 95", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-deepgreen)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} < 45 && {Blue Prediction %} >= 35", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} < 35 && {Blue Prediction %} >= 25", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lighterred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} < 25 && {Blue Prediction %} >= 15", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-lightestred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} < 15 && {Blue Prediction %} >= 5", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-darkred)", "color": "var(--text-primary)"},
        {"if": {"filter_query": "{Blue Prediction %} < 5", "column_id": "Blue Pred"}, "backgroundColor": "var(--table-row-prediction-deepred)", "color": "var(--text-primary)"},
        # Predicted Winner styling
        {"if": {"filter_query": '{Pred Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-red)", "color": "var(--text-primary)"},
        {"if": {"filter_query": '{Pred Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-blue)", "color": "var(--text-primary)"},
        {"if": {"filter_query": '{Pred Winner} = "Tie"', "column_id": "Pred Winner"}, "backgroundColor": "var(--table-row-yellow)", "color": "var(--text-primary)"},
    ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "color": "var(--text-primary)", "backgroundColor": "transparent" }
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
        "backgroundColor": "#181a1b", 
        "color": "var(--text-primary)",
        "textAlign": "center",
        "padding": "10px",
        "border": "none",
        "fontSize": "14px",
    }

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
        html.Div(playoff_table, className="recent-events-table"),
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
        
        // Create YouTube playlist URL
        const playlist_url = `https://www.youtube.com/playlist?list=PL${event_key}`;
        
        // Open in new tab
        window.open(playlist_url, '_blank');
        
        return window.dash_clientside.no_update;
    }
    """,
    Output('dummy-output', 'children', allow_duplicate=True),
    [Input('create-playlist-btn', 'n_clicks')],
    [State('team-filter', 'value'), State('store-event-matches', 'data'), State('url', 'pathname')],
    prevent_initial_call=True
)

# Add a client-side callback for smooth page transitions
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

@callback(
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
    prevent_initial_call="initial_duplicate",
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
    # Default filter values
    default_values = {
        "year": 2025,
        "country": "All",
        "state": "All",
        "search": "",
        "x": "teleop_epa",
        "y": "auto+endgame",
        "tab": "table-tab",
        "district": "All"
    }

    # Parse from URL if present
    if href and "?" in href:
        query = href.split("?", 1)[1]
        params = parse_qs(query)
        def get_param(name, fallback):
            val = params.get(name, [fallback])
            return val[0] if isinstance(val, list) else val
        selected_year = int(get_param("year", selected_year))
        selected_country = get_param("country", selected_country)
        selected_state = get_param("state", selected_state)
        selected_district = get_param("district", selected_district)
        search_query = get_param("search", search_query)
        x_axis = get_param("x", x_axis)
        y_axis = get_param("y", y_axis)
        active_tab = get_param("tab", active_tab)
        percentile_mode = ["filtered"] if get_param("percentile", "") == "filtered" else []

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

    # Load and filter teams
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(selected_year):
        # Load data for the specific year if it's not 2025
        if selected_year != 2025:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(selected_year)
                year_team_database = {selected_year: year_team_data}
                teams_data, epa_ranks = calculate_all_ranks(selected_year, year_team_database)
            except Exception as e:
                return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, query_string, []
        else:
            return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, query_string, []
    else:
        teams_data, epa_ranks = calculate_all_ranks(selected_year, TEAM_DATABASE)

    empty_style = []
    if not teams_data:
        return [], [{"label": "All States", "value": "All"}], [], {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, query_string, empty_style

    if selected_country and selected_country != "All":
        teams_data = [t for t in teams_data if (t.get("country") or "").lower() == selected_country.lower()]

    if selected_district and selected_district != "All":
        if selected_district == "ISR":
            teams_data = [
                t for t in teams_data
                if (t.get("country") or "").lower() == "israel"
            ]
        else:
            allowed_states = [s.lower() for s in DISTRICT_STATES.get(selected_district, [])]
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
        if selected_year != 2025:
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
    
    percentiles_dict = {
        "ace": overall_percentiles,
        "auto_epa": auto_percentiles,
        "teleop_epa": teleop_percentiles,
        "endgame_epa": endgame_percentiles,
    }

    style_data_conditional = get_epa_styling(percentiles_dict)

    state_options = [{"label": "All States", "value": "All"}]
    if selected_country and selected_country in STATES:
        state_options += [
            {"label": s["label"], "value": s["value"]}
            for s in STATES[selected_country] if isinstance(s, dict)
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

    table_rows = []
    for t in teams_data:
        team_num = t.get("team_number")
        rank = epa_ranks.get(str(team_num), {}).get("rank", "N/A")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        nickname = t.get('nickname', 'Unknown')
        nickname_safe = nickname.replace('"', "'")
        truncated = truncate_name(nickname)
        team_display = f'[{team_num} | {truncated}](/team/{team_num}/{selected_year} "{nickname_safe}")'
        table_rows.append({
            "epa_rank": rank,
            "team_display": team_display,
            "epa": round(abs(t.get("normal_epa") or 0), 2),
            "confidence": t.get("confidence", 0),
            "ace": round(abs(t.get("epa") or 0), 2),
            "auto_epa": round(abs(t.get("auto_epa") or 0), 2),
            "teleop_epa": round(abs(t.get("teleop_epa") or 0), 2),
            "endgame_epa": round(abs(t.get("endgame_epa") or 0), 2),
            "location_display": ", ".join(filter(None, [t.get("city", ""), t.get("state_prov", ""), t.get("country", "")])),
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
        return table_rows, state_options, top_teams_layout, {"display": "none"}, avatars, {"display": "flex"}, go.Figure(), {"display": "none"}, query_string, style_data_conditional

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

        df = pd.DataFrame(chart_data)
        df["label"] = ""
        q = (search_query or "").lower().strip()
        df["is_match"] = df["team"].str.lower().str.contains(q) if q else False
        df["hover"] = df.apply(lambda r: f"<b>{r['team']}</b><br>X: {r['x']:.2f}<br>Y: {r['y']:.2f}", axis=1)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.loc[~df["is_match"], "x"],
            y=df.loc[~df["is_match"], "y"],
            mode="markers+text",
            marker=dict(size=6, color="rgba(30, 136, 229, 0.3)", line=dict(width=0)),
            text=df.loc[~df["is_match"], "label"],
            textfont=dict(size=9, color="#777"),
            textposition="top center",
            hovertext=df.loc[~df["is_match"], "hover"],
            hoverinfo="text",
        ))
        fig.add_trace(go.Scatter(
            x=df.loc[df["is_match"], "x"],
            y=df.loc[df["is_match"], "y"],
            mode="markers+text",
            marker=dict(size=8, color="#777", line=dict(width=2, color="black")),
            text=df.loc[df["is_match"], "label"],
            textfont=dict(size=10, color="#777"),
            textposition="top center",
            hovertext=df.loc[df["is_match"], "hover"],
            hoverinfo="text",
        ))

        fig.update_layout(
            title="EPA Breakdown Bubble Chart",
            xaxis_title=x_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
            yaxis_title=y_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
            margin=dict(l=40, r=40, t=40, b=40),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                color="#777",  # Axis ticks and label color
                title=dict(font=dict(color="#777")),  # x-axis title color
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                color="#777",  # Axis ticks and label color
                title=dict(font=dict(color="#777")),  # y-axis title color
            ),
            font=dict(color="#777"),  # Title and general font color
        )
        return table_rows, state_options, top_teams_layout, {"display": "none"}, [], {"display": "none"}, fig, {"display": "block"}, query_string, style_data_conditional

    return table_rows, state_options, top_teams_layout, {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, query_string, style_data_conditional

@callback(
    Output("axis-dropdown-container", "style"),
    Input("teams-tabs", "active_tab")
)
def toggle_axis_dropdowns(active_tab):
    if active_tab == "bubble-chart-tab":
        return {"display": "block", "marginBottom": "15px"}
    return {"display": "none"}

@app.callback(
    Output("url", "pathname"),
    [
        Input("btn-search-home", "n_clicks"),
        Input("input-team-home", "n_submit"),
        Input("input-year-home", "n_submit"),
        Input("desktop-search-button", "n_clicks"),
        Input("desktop-search-input", "n_submit"),
        Input("mobile-search-button", "n_clicks"),
        Input("mobile-search-input", "n_submit"),
    ],
    [
        State("input-team-home", "value"),
        State("input-year-home", "value"),
        State("desktop-search-input", "value"),
        State("mobile-search-input", "value"),
    ],
    prevent_initial_call=True,
)
def handle_navigation(
    home_click, home_submit, home_year_submit, desktop_click, desktop_submit,
    mobile_click, mobile_submit, home_team_value, home_year_value,
    desktop_search_value, mobile_search_value
):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id in ["btn-search-home", "input-team-home", "input-year-home"]:
        search_value = home_team_value
        year_value = home_year_value
    elif trigger_id in ["desktop-search-button", "desktop-search-input"]:
        search_value = desktop_search_value
        year_value = None
    elif trigger_id in ["mobile-search-button", "mobile-search-input"]:
        search_value = mobile_search_value
        year_value = None
    else:
        return dash.no_update

    if not search_value:
        return dash.no_update

    search_value = search_value.strip().lower()
    selected_year = int(year_value) if year_value and year_value.isdigit() else None
    
    # Search through all years if no specific year selected
    if selected_year is None:
        # Use search data which only has 2025 teams
        year_data = SEARCH_TEAM_DATA[2025]
        matching_team = next(
            (
                team for team in year_data.values()
                if str(team.get("team_number", "")).lower() == search_value
                or search_value in (team.get("nickname", "") or "").lower()
            ),
            None
        )
        if matching_team:
            team_number = matching_team.get("team_number", "")
            return f"/team/{team_number}/2025"
    else:
        if selected_year == 2025:
            year_data = SEARCH_TEAM_DATA.get(selected_year)
            if year_data:
                matching_team = next(
                    (
                        team for team in year_data.values()
                        if str(team.get("team_number", "")).lower() == search_value
                        or search_value in (team.get("nickname", "") or "").lower()
                    ),
                    None
                )
                if matching_team:
                    team_number = matching_team.get("team_number", "")
                    return f"/team/{team_number}/{selected_year}"

    # Use search event data which has all events
    events_data = [ev for year_dict in SEARCH_EVENT_DATA.values() for ev in year_dict.values()]
    # --- EVENT SEARCH ---
    matching_events = []
    for event in events_data:
        event_key = event.get("k", "").lower()
        event_name = (event.get("n", "") or "").lower()
        event_year = event_key[:4] if len(event_key) >= 4 else ""

        if (
            search_value in event_key
            or search_value in event_name
            or search_value in event_year
            or search_value in f"{event_year} {event_name}".lower()
        ):
            matching_events.append(event)

    if matching_events:
        # pick the "closest" match — most character overlap
        best_event = max(
            matching_events,
            key=lambda e: (
                len(set(search_value) & set((e.get("k") or "").lower())) +
                len(set(search_value) & set((e.get("n") or "").lower()))
            )
        )
        return f"/event/{best_event['k']}"

    return "/"

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

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    path_parts = pathname.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "team":
        team_number = path_parts[1]
        year = path_parts[2] if len(path_parts) > 2 else None
        
        # If year is specified and it's not 2025, load that year's data
        if year and year != "2025":
            try:
                year = int(year)
                if year != 2025:
                    # Load data for the specific year
                    year_team_data, year_event_data, year_event_teams, year_event_rankings, year_event_awards, year_event_matches = load_year_data(year)
                    
                    # Create year-specific databases
                    year_team_database = {year: year_team_data}
                    year_event_database = {year: year_event_data}
                    
                    return wrap_with_toast_or_star(team_layout(
                        team_number, year, 
                        year_team_database, year_event_database, 
                        year_event_matches, year_event_awards, 
                        year_event_rankings, year_event_teams
                    ))
            except (ValueError, TypeError):
                # If year parsing fails, fall back to 2025
                pass
        
        # Use global 2025 data for current year or fallback
        return wrap_with_toast_or_star(team_layout(team_number, year, TEAM_DATABASE, EVENT_DATABASE, EVENT_MATCHES, EVENT_AWARDS, EVENT_RANKINGS, EVENT_TEAMS))
    
    if pathname.startswith("/event/"):
        event_key = pathname.split("/")[-1]
        return wrap_with_toast_or_star(event_layout(event_key))
    
    if pathname == "/teams":
        return wrap_with_toast_or_star(teams_layout())
    
    if pathname == "/map":
        return wrap_with_toast_or_star(teams_map_layout())
    
    if pathname == "/events":
        return wrap_with_toast_or_star(events_layout())
    
    if pathname == "/challenges":
        return wrap_with_toast_or_star(challenges_layout())

    if pathname == "/blog":
        return wrap_with_toast_or_star(blog_layout)

    if pathname == "/login":
        return login_layout()

    if pathname == "/user":
        return html.Div([
            dcc.Store(id="favorites-store", data={"deleted": []}),
            dcc.Store(id="user-session", data={"user_id": session.get("user_id")}),
            html.Div(id="user-layout-wrapper", children=user_layout())
        ])


    if len(path_parts) == 2 and path_parts[0] == "user":
        try:
            username = pathname.split("/user/")[1]
            return wrap_with_toast_or_star(other_user_layout(username))
        except ValueError:
            pass
    
    if pathname.startswith("/challenge/"):
        year = pathname.split("/")[-1]
        try:
            year = int(year)
        except ValueError:
            year = None
        return challenge_details_layout(year)

    if pathname == "/compare":
        return wrap_with_toast_or_star(compare_layout())

    return wrap_with_toast_or_star(home_layout)

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
        event_key = pathname.split('/event/')[1].split('/')[0]
        return f'{event_key} - Peekorobo'
    elif pathname.startswith('/events'):
        return 'Events - Peekorobo'
    elif pathname.startswith('/map'):
        return 'Map - Peekorobo'
    elif pathname.startswith('/compare'):
        return 'Compare - Peekorobo'
    elif pathname.startswith('/blog'):
        return 'Blog - Peekorobo'
    elif pathname.startswith('/challenges'):
        return 'Challenges - Peekorobo'
    elif pathname.startswith('/challenge/'):
        challenge = pathname.split('/challenge/')[1].split('/')[0]
        return f'{challenge} Season - Peekorobo'
    elif pathname.startswith('/user/'):
        username = pathname.split('/user/')[1].split('/')[0]
        return f'{username} - Peekorobo'
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
    Output("compare-teams", "options"),
    Input("compare-year", "value")
)
def update_compare_team_dropdowns(year):
    year = year or 2025
    
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(year):
        # Load data for the specific year if it's not 2025
        if year != 2025:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(year)
                teams = year_team_data
            except Exception as e:
                return []  # Return empty options if loading fails
        else:
            return []  # Return empty options for 2025 if not loaded
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

    year = year or 2025
    
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(year):
        # Load data for the specific year if it's not 2025
        if year != 2025:
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
        # fallback year to use for metrics (default to 2025 or latest available)
        performance_year = 2025
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
    
    # Estimate rookie year just like before
    rookie_year = years_participated[0] if years_participated else year or 2025
    
    with open("data/notables_by_year.json", "r") as f:
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
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

@callback(
    Output("followers-hidden", "style"),
    Input("followers-see-more", "n_clicks"),
    prevent_initial_call=True
)
def toggle_followers_list(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

@callback(
    Output("following-hidden", "style"),
    Input("following-see-more", "n_clicks"),
    prevent_initial_call=True
)
def toggle_following_list(n_clicks):
    if n_clicks is None:
        return dash.no_update
    
    # Toggle between hidden and visible
    return {"display": "block", "marginTop": "5px", "paddingLeft": "0", "listStyleType": "none", "marginBottom": "0"}

@callback(
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
        print(f"Error toggling team favorite: {e}")
        return "Error updating favorites.", True, [dash.no_update]

@callback(
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
                    html.A(username, href=f"/user/{username}", style={"textDecoration": "none", "color": "#007bff"})
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "5px"}))

            return html.Ul(user_list_items, style={
                "listStyleType": "none",
                "paddingLeft": "0",
                "marginBottom": "0"
            })

    except Exception as e:
        print(f"Error fetching favoriting users: {e}")
        return "Error loading favoriting users."

@callback(
    Output("team-insights-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data")
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
    if performance_year == 2025:
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
        print(f"Team {team_number} participated in years: {years_participated}")
        
        # Get team's historical data across all years they participated in
        years_data = []
        for year_key in sorted(years_participated):
            print(f"Loading data for year {year_key}")
            
            if year_key == 2025:
                # Use global database for 2025
                year_team_data = TEAM_DATABASE[year_key]
            else:
                # Load data for other years
                try:
                    year_team_data, _, _, _, _, _ = load_year_data(year_key)
                    print(f"Successfully loaded data for {year_key}")
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
                print(f"Added data for {year_key}: rank {global_rank}, ace {team_year_data.get('epa', 0)}")
            else:
                print(f"Team {team_number} not found in {year_key} data")
        
        if not years_data:
            return "No historical data available for this team."
        
        years_data.sort(key=lambda x: x['year'])
        print(f"Final years_data: {years_data}")
        
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
    
    # Similar Teams Section
    similar_teams = find_similar_teams(team_number, performance_year, TEAM_DATABASE)
    
    similar_teams_cards = []
    for similar_team in similar_teams[:6]:  # Show top 6 similar teams
        team_num = similar_team["team_number"]
        nickname = similar_team.get("nickname", "Unknown")
        ace = similar_team.get("epa", 0)
        similarity_score = similar_team.get("similarity_score", 0)
        avatar_url = get_team_avatar(team_num)
        
        card = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Img(
                            src=avatar_url,
                            style={
                                "width": "50px",
                                "height": "50px",
                                "borderRadius": "50%",
                                "objectFit": "contain"
                            }
                        ) if avatar_url else html.Div("", style={"width": "50px", "height": "50px"}),
                    ], width="auto"),
                    dbc.Col([
                        html.A(
                            f"#{team_num} {nickname}",
                            href=f"/team/{team_num}/{performance_year}",
                            style={"fontWeight": "bold", "textDecoration": "none", "color": "var(--text-primary)"}
                        ),
                        html.Div(f"ACE: {ace:.1f}", style={"fontSize": "0.9rem", "color": "var(--text-secondary)"}),
                        html.Div(f"Similarity: {similarity_score:.1%}", style={"fontSize": "0.8rem", "color": "var(--text-muted)"}),
                    ])
                ])
            ])
        ], style={"marginBottom": "10px", "backgroundColor": "var(--card-bg)"})
        
        similar_teams_cards.append(card)
    
    return html.Div([
        html.Div(trends_chart, className="trends-chart-container"),
        html.Hr(style={"margin": "30px 0"}),
        html.H3("Similar Teams", style={"marginBottom": "20px", "color": "var(--text-primary)"}),
        html.Div(similar_teams_cards, className="similar-teams-container")
    ])

@callback(
    Output("team-events-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data")
)
def update_team_events(active_tab, store_data):
    if active_tab != "events-tab" or not store_data:
        return ""
    
    team_number = store_data.get("team_number")
    year = store_data.get("year")
    performance_year = store_data.get("performance_year")
    
    if not team_number:
        return "No team data available."
    
    participated_events = []
    # Detect if we're on the history page
    is_history = not year or str(year).lower() == "history"
    years_to_process = get_team_years_participated(team_number) if is_history else [int(year)]
    
    for year_key in years_to_process:
        if year_key == 2025:
            year_event_database = EVENT_DATABASE
            year_event_teams = EVENT_TEAMS
            year_event_rankings = EVENT_RANKINGS
            event_iter = year_event_database[2025].items()
            for event_key, event in event_iter:
                team_list = year_event_teams[2025].get(event_key, [])
                if any(t["tk"] == team_number for t in team_list):
                    participated_events.append((year_key, event_key, event))
        else:
            try:
                _, year_event_data, year_event_teams, year_event_rankings, _, _ = load_year_data(year_key)
                year_event_database = year_event_data
                year_event_teams = year_event_teams
                year_event_rankings = year_event_rankings
                event_iter = year_event_database.items()
                for event_key, event in event_iter:
                    team_list = year_event_teams.get(event_key, []) if isinstance(year_event_teams, dict) else year_event_teams
                    if any(t["tk"] == team_number for t in team_list):
                        participated_events.append((year_key, event_key, event))
            except Exception as e:
                continue
    
    # Sort events by start date
    participated_events.sort(key=lambda tup: tup[2].get("sd", ""), reverse=True)
    
    # Build event rows
    events_data = []
    for year_key, event_key, event in participated_events:
        event_name = event.get("n", "")
        location = f"{event.get('c', '')}, {event.get('s', '')}".strip(", ")
        start_date = event.get("sd", "")
        end_date = event.get("ed", "")
        event_url = f"https://www.peekorobo.com/event/{event_key}"
    
        # Rank
        rank = None
        if year_key == 2025:
            rankings = year_event_rankings.get(year_key, {}).get(event_key, {})
        else:
            rankings = year_event_rankings.get(event_key, {}) if isinstance(year_event_rankings, dict) else {}
        
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
        page_size=10,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)", "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"},
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
        style_cell_conditional=[{"if": {"column_id": "event_name"}, "textAlign": "center"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    return html.Div([
        events_table
    ])

@callback(
    Output("team-awards-content", "children"),
    Input("team-tabs", "active_tab"),
    State("team-insights-store", "data")
)
def update_team_awards(active_tab, store_data):
    if active_tab != "awards-tab" or not store_data:
        return ""
    team_number = store_data.get("team_number")
    year = store_data.get("year")
    performance_year = store_data.get("performance_year")
    if not team_number:
        return "No team data available."

    participated_events = []
    all_event_awards = []

    # Detect if we're on the history page
    is_history = not year or str(year).lower() == "history"
    years_to_process = get_team_years_participated(team_number) if is_history else [int(year)]

    for year_key in years_to_process:
        if year_key == 2025:
            year_event_database = EVENT_DATABASE
            year_event_teams = EVENT_TEAMS
            year_event_awards = EVENT_AWARDS  # Flat list for 2025!
            event_iter = year_event_database[2025].items()
            year_awards = [aw for aw in year_event_awards if isinstance(aw, dict) and aw.get("tk") == team_number and aw.get("y") == 2025]
            for event_key, event in event_iter:
                team_list = year_event_teams[2025].get(event_key, [])
                if any(t["tk"] == team_number for t in team_list):
                    participated_events.append((year_key, event_key, event))
            for aw in year_awards:
                all_event_awards.append(aw)
        else:
            try:
                _, year_event_data, year_event_teams, _, year_event_awards, _ = load_year_data(year_key)
                year_event_database = year_event_data
                year_event_teams = year_event_teams
                year_event_awards = year_event_awards
                event_iter = year_event_database.items()
                for event_key, event in event_iter:
                    team_list = year_event_teams.get(event_key, []) if isinstance(year_event_teams, dict) else year_event_teams
                    if any(t["tk"] == team_number for t in team_list):
                        participated_events.append((year_key, event_key, event))
                if isinstance(year_event_awards, dict):
                    year_awards = list(year_event_awards.values())
                else:
                    year_awards = year_event_awards
                year_awards = [aw for aw in year_awards if isinstance(aw, dict)]
                for aw in year_awards:
                    if aw["tk"] == team_number:
                        all_event_awards.append(aw)
            except Exception as e:
                continue
    
    # Map event keys to names
    event_key_to_name = {ek: e.get("n", "Unknown") for _, ek, e in participated_events}
    
    # Sort awards by year (newest first)
    all_event_awards.sort(key=lambda aw: aw["y"], reverse=True)
    
    awards_data = [
        {
            "award_name": aw["an"],
            "event_name": f"[{event_key_to_name.get(aw['ek'], 'Unknown Event')}](/event/{aw['ek']})",
            "award_year": aw["y"]
        }
        for aw in all_event_awards
    ]
    
    awards_table = dash_table.DataTable(
        columns=[
            {"name": "Award Name", "id": "award_name"},
            {"name": "Event Name", "id": "event_name", "presentation": "markdown"},
            {"name": "Year", "id": "award_year"},
        ],
        data=awards_data,
        page_size=10,
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)", "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)"},
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
        style_cell_conditional=[{"if": {"column_id": "award_name"}, "textAlign": "left"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    # Blue Banners Section
    blue_banner_keywords = ["chairman's", "impact", "woodie flowers", "winner"]
    blue_banners = []
    
    for award in all_event_awards:
        name_lower = award["an"].lower()
        if any(keyword in name_lower for keyword in blue_banner_keywords):
            event_key = award["ek"]
            year_str = str(award["y"])
            
            # Find the event in the participated events
            event = None
            for _, ek, e in participated_events:
                if ek == event_key:
                    event = e
                    break
            
            event_name = event.get("n", "Unknown Event") if event else "Unknown Event"
            full_event_name = f"{year_str} {event_name}"
    
            blue_banners.append({
                "award_name": award["an"],
                "event_name": full_event_name,
                "event_key": event_key
            })
    
    blue_banner_section = html.Div(
        [
            html.H4("Blue Banners", style={"marginTop": "30px", "marginBottom": "15px", "color": "var(--text-primary)"}),
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
    ) if blue_banners else html.Div()
    
    return html.Div([
        awards_table,
        blue_banner_section
    ])

def find_similar_teams(team_number, year, TEAM_DATABASE):
    """Find teams with similar performance characteristics"""
    # Load year-specific data if needed
    if year == 2025:
        year_data = TEAM_DATABASE.get(year, {})
    else:
        try:
            year_team_data, _, _, _, _, _ = load_year_data(year)
            year_data = year_team_data
        except Exception:
            return []
    
    if team_number not in year_data:
        return []
    
    target_team = year_data[team_number]
    
    # Get target team's characteristics
    target_auto = target_team.get("auto_epa", 0)
    target_teleop = target_team.get("teleop_epa", 0)
    target_endgame = target_team.get("endgame_epa", 0)
    target_ace = target_team.get("epa", 0)
    
    similar_teams = []
    
    for team_num, team_data in year_data.items():
        if team_num == team_number:
            continue
        
        # Calculate similarity based on EPA components
        auto_diff = abs(team_data.get("auto_epa", 0) - target_auto)
        teleop_diff = abs(team_data.get("teleop_epa", 0) - target_teleop)
        endgame_diff = abs(team_data.get("endgame_epa", 0) - target_endgame)
        ace_diff = abs(team_data.get("epa", 0) - target_ace)
        
        # Calculate similarity score (lower is more similar)
        similarity_score = (auto_diff + teleop_diff + endgame_diff + ace_diff) / 4
        
        similar_teams.append({
            "team_number": team_num,
            "nickname": team_data.get("nickname", "Unknown"),
            "epa": team_data.get("epa", 0),
            "similarity_score": max(0, 1 - (similarity_score / 10))  # Normalize to 0-1
        })
    
    # Sort by similarity (highest first)
    similar_teams.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    return similar_teams

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=False)
