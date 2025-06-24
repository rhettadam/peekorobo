import dash
import dash_bootstrap_components as dbc
from dash import callback, html, dcc, dash_table, ctx, ALL, MATCH, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import flask
from flask import session
from auth import get_pg_connection, register_user, verify_user

import os
import numpy as np
import datetime
from datetime import datetime, date

import re
from urllib.parse import parse_qs, urlencode
import json
import pandas as pd

import plotly.graph_objects as go

from datagather import COUNTRIES,STATES,load_data,get_team_avatar,DISTRICT_STATES,get_pg_connection

from layouts import home_layout,footer,topbar,team_layout,blog_layout,challenges_layout,challenge_details_layout,teams_map_layout,login_layout,create_team_card,teams_layout,epa_legend_layout,events_layout, build_recent_events_section, compare_layout

from utils import pill,predict_win_probability,calculate_all_ranks,get_user_avatar,get_epa_styling,compute_percentiles,sort_key,get_available_avatars,get_contrast_text_color,parse_event_key,user_team_card,user_event_card,team_link_with_avatar,wrap_with_toast_or_star,get_week_number,event_card

from dotenv import load_dotenv
load_dotenv()

TEAM_DATABASE, EVENT_DATABASE, _, _, _, _ = load_data(only_teams_and_events=True)

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
    html.Div(id='page-content'),
    html.Div(id='dummy-output', style={'display': 'none'}),
    html.Button(id='page-load-trigger', n_clicks=1, style={'display': 'none'})  # <-- THIS is what you're missing
])

def user_layout(_user_id=None, deleted_items=None):

    _, _, EVENT_TEAMS, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES = load_data(year=2025)

    user_id = _user_id or session.get("user_id")

    if not user_id:
        return html.Div([
            dcc.Store(id="user-session", data={}),
            dcc.Location(href="/login", id="force-login-redirect")
        ])

    dcc.Store(id="user-session", data={"user_id": user_id}),

    conn = get_pg_connection()
    cursor = conn.cursor()

    username = f"USER {user_id}"
    avatar_key = "stock"

    try:
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
        else:
            role = "No role"
            team_affil = "####"
            bio = "No bio"
            followers = 0
            following = 0
            color = "#f9f9f9"
    except Exception as e:
        print(f"Error retrieving user info: {e}")
        role = "No role"
        team_affil = "####"
        bio = "No bio"
        followers = 0
        following = 0
        color = "#f9f9f9"

    cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'team'", (user_id,))
    team_keys = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'event'", (user_id,))
    event_keys = [r[0] for r in cursor.fetchall()]

    conn.close()

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
                    html.A(team_affil, href=f"/team/{team_affil}", style={
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
                href=f"/team/{team_key}",
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

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, avatar_key, role, team, bio, followers, following, color
        FROM users WHERE username = %s
    """, (username,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return html.Div("User not found.", style={"padding": "2rem", "fontSize": "1.2rem"})

    uid, avatar_key, role, team, bio, followers_json, following_json, color = row
    is_following = session_user_id in (followers_json or [])

    cur.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'team'", (uid,))
    team_keys = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT item_key FROM saved_items WHERE user_id = %s AND item_type = 'event'", (uid,))
    event_keys = [r[0] for r in cur.fetchall()]
    conn.close()

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
                href=f"/team/{team_key}",
                style={"textDecoration": "none", "color": "inherit"}
            ),
            [
                html.Img(src=get_team_avatar(team_key), style={"height": "80px", "borderRadius": "50%"}),
                metrics,
                html.Br(),
                html.Hr(),
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, 2025, EVENT_DATABASE)
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
                    html.A(team, href=f"/team/{team}", style={
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

    user_id = session_data if isinstance(session_data, str) else session_data.get("user_id") if session_data else None
    if not user_id:
        return [dash.no_update] * 15

    conn = get_pg_connection()
    cur = conn.cursor()

    if triggered_id == "save-profile-btn":
        if not username or len(username.strip()) < 3:
            return [dash.no_update] * 15

        cur.execute("SELECT id FROM users WHERE LOWER(username) = %s AND id != %s", (username.lower(), user_id))
        if cur.fetchone():
            return [dash.no_update] * 15

        try:
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
        finally:
            conn.close()

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
                html.A(new_team, href=f"/team/{new_team}", style={"color": text_color, "textDecoration": "underline"})
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
        finally:
            conn.close()

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
                html.A(team, href=f"/team/{team}", style={"color": text_color, "textDecoration": "underline"})
            ]),
            html.Div(bio, style={"color": text_color}),
            {"color": text_color},  # profile-header
            {"color": text_color},  # profile-subheader
            {"color": text_color},  # profile-search-header
            {"color": text_color, "fontWeight": "500"},  # profile-followers style
            {"color": text_color, "fontWeight": "500"},  # profile-following style
            f"Followers: {followers_count}",  # profile-followers children
        )

    conn.close()
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

    conn = get_pg_connection()
    cur = conn.cursor()

    try:
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
        conn.rollback()
        return current_text

    finally:
        conn.close()

@callback(
    Output("user-search-results", "children"),
    Input("user-search-input", "value"),
    State("user-session", "data")
)
def search_users(query, session_data):
    if not query or not session_data:
        return []

    current_user_id = session_data.get("user_id")
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, avatar_key, followers
        FROM users
        WHERE username ILIKE %s AND id != %s
        LIMIT 10
    """, (f"%{query}%", current_user_id))
    rows = cur.fetchall()
    conn.close()

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

    return user_blocks

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
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM saved_items WHERE user_id = %s AND item_type = %s AND item_key = %s",
        (user_id, item_type, item_key)
    )
    conn.commit()
    conn.close()

    # Update favorites store
    store_data = store_data or {"deleted": []}
    deleted = set(tuple(i) for i in store_data.get("deleted", []))
    deleted.add((item_type, item_key))
    new_store = {"deleted": list(deleted)}

    # Rerender layout
    return new_store, user_layout(user_id, deleted)

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
            conn = get_pg_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = %s", (username.strip(),))
            user_id = cursor.fetchone()[0]
            conn.close()
            session["user_id"] = user_id
            session["username"] = username.strip()
            redirect_url = "/user"
            return f"✅ Welcome, {username.strip()}!", redirect_url
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

    # Collapse TEAM_DATABASE to a flat dict keeping only the most recent year for each team
    latest_teams = {}
    for year in sorted(TEAM_DATABASE.keys(), reverse=True):
        for team_number, team_data in TEAM_DATABASE[year].items():
            if team_number not in latest_teams:
                latest_teams[team_number] = team_data
    teams_data = list(latest_teams.values())

    events_data = [ev for year_dict in EVENT_DATABASE.values() for ev in year_dict.values()]

    def get_children_and_style(val):
        if not val:
            return [], {"display": "none"}

                # --- Filter Users from PostgreSQL ---
        try:
            conn = get_pg_connection()
            cur = conn.cursor()
            cur.execute("SELECT username, avatar_key FROM users WHERE username ILIKE %s LIMIT 10", (f"%{val}%",))
            user_rows = cur.fetchall()
            conn.close()
        except Exception as e:
            print("User search error:", e)
            user_rows = []

        # --- Filter Teams ---
        filtered_teams = [
            t for t in teams_data
            if val in str(t.get("team_number", "")).lower()
            or val in (t.get("nickname", "")).lower()
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
                key=lambda t: len(set(val) & set(t["nickname"].lower())),
                default=None,
            )

        # --- Filter Events (using compressed keys) ---
        filtered_events = []
        search_terms = val.split()
        
        for e in events_data:
            event_code = (e.get("cd") or "").lower()
            event_key = (e.get("k") or "").lower()
            event_name_raw = (e.get("n") or "").lower()
            # Remove ' presented by' and everything after it for searching
            if "presented" in event_name_raw:
                event_name_searchable = event_name_raw.split(" presented by")[0]
            else:
                event_name_searchable = event_name_raw
                
            start_date = e.get("sd", "")
            event_year = start_date[:4] if len(start_date) >= 4 else ""
            
            # Create a combined string for searching
            searchable_text = f"{event_year} {event_name_searchable} {event_code} {event_key}".lower()

            # Check if all search terms are present in the searchable text
            if all(term in searchable_text for term in search_terms):
                filtered_events.append(e)
        
        # Sort events by date, newest first
        def parse_date_for_sort(date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except:
                return datetime.min # Put undateable events at the beginning

        filtered_events.sort(key=lambda x: parse_date_for_sort(x.get("sd", "")), reverse=True)

        closest_event = None
        if filtered_events:
            closest_event = max(
                filtered_events,
                key=lambda e: (
                    len(set(val) & set((e.get("cd") or "").lower()))
                    + len(set(val) & set((e.get("n") or "").lower()))
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

                # Create the team link element (without inline color from function)
                team_link_element = team_link_with_avatar(team)

                # Determine the correct text color based on highlight and theme
                if is_highlighted:
                    link_text_color = "black" # Always black on yellow background
                else:
                    # White in dark mode, Black in light mode for non-highlighted
                    link_text_color = "white" if current_theme == "dark" else "black"

                # Explicitly set the color on the A tag using inline style
                if hasattr(team_link_element, 'style'):
                     team_link_element.style['color'] = link_text_color

                row_el = dbc.Row(
                    dbc.Col(team_link_element), # Use the modified link element
                    style={
                        "padding": "5px",
                        "backgroundColor": background_color,
                        # Remove any explicit color setting here
                        # "color": "",
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
                start_date = evt.get("sd", "")
                e_year = start_date[:4] if len(start_date) >= 4 else ""
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
                                "color": "black" if background_color == "#FFDD00" else default_text_color, # Conditional color
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
                            "color": default_text_color # Apply default text color
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
            "color": "var(--text-primary)", # Use CSS variable for consistency
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

    conn = get_pg_connection()
    cursor = conn.cursor()

    # Avoid duplicates
    cursor.execute("""
        SELECT id FROM saved_items
        WHERE user_id = %s AND item_type = 'team' AND item_key = %s
    """, (user_id, team_key))
    if cursor.fetchone():
        conn.close()
        return "Team already favorited.", True

    cursor.execute("""
        INSERT INTO saved_items (user_id, item_type, item_key)
        VALUES (%s, 'team', %s)
    """, (user_id, team_key))
    conn.commit()
    conn.close()

    return "Team favorited successfully!", True

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
    events_data = list(EVENT_DATABASE.get(selected_year, {}).values())
    if not events_data:
        return html.Div("No events available."), []

    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

    def extract_district_key(event_name):
        parts = event_name.split()
        if "District" in parts:
            idx = parts.index("District")
            return parts[idx - 1] if idx > 0 else None
        return None

    district_keys = sorted(set(
        extract_district_key(ev["n"]) for ev in events_data
        if "District" in ev.get("n", "")
    ))

    district_options = [{"label": "All", "value": "all"}] + [
        {"label": dk, "value": dk} for dk in district_keys if dk
    ]

    if selected_district and selected_district != "all":
        events_data = [
            ev for ev in events_data
            if extract_district_key(ev.get("n", "")) == selected_district
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

    def compute_event_insights_from_data(EVENT_TEAMS, EVENT_DATABASE, TEAM_DATABASE, selected_year, filtered_event_keys=None):
        rows = []
    
        teams_by_event = EVENT_TEAMS.get(selected_year, {})
        events = EVENT_DATABASE.get(selected_year, {})
    
        for event_key, team_entries in teams_by_event.items():
            if filtered_event_keys and event_key not in filtered_event_keys:
                continue
    
            event = events.get(event_key)
            if not event:
                continue
    
            full_name = event.get("n", "")
            # Remove ' presented by' and everything after it
            if " presented by" in full_name:
                full_name = full_name.split(" presented by")[0]
            name = full_name.split(" presented by")[0].strip()
    
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
    
            rows.append({
                "Name": f"[{name}](/event/{event_key})",
                "Event Type": event.get("et", "N/A"),
                "District": extract_district_key(name) or "N/A",
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
        _, _, EVENT_TEAMS, _, _, _ = load_data(year=selected_year)
        df = compute_event_insights_from_data(EVENT_TEAMS, EVENT_DATABASE, TEAM_DATABASE, selected_year)
    
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
    event = EVENT_DATABASE.get(parsed_year, {}).get(event_key)
    if not event:
        return dbc.Alert("Event details could not be found.", color="danger")

    _, _, EVENT_TEAMS, EVENT_RANKINGS, _, EVENT_MATCHES = load_data(year=parsed_year)

    # Get event-specific EPA data for teams at this event
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
            if event_specific_epa and any(event_specific_epa.get(k, 0) not in (None, 0, "") for k in ["overall", "confidence"]):
                event_epa_data[str(team_num)] = {
                    "epa": event_specific_epa.get("actual_epa", 0),
                    "auto_epa": event_specific_epa.get("auto", 0),
                    "teleop_epa": event_specific_epa.get("teleop", 0),
                    "endgame_epa": event_specific_epa.get("endgame", 0),
                    "confidence": event_specific_epa.get("confidence", 0),
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
            dbc.Tab(label="Alliances", tab_id="alliances", label_style=tab_style, active_label_style=tab_style),
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
    from urllib.parse import parse_qs
    if search and search.startswith("?"):
        params = parse_qs(search[1:])
        tab = params.get("tab", [None])[0]
        if tab in ["teams", "rankings", "matches", "alliances"]:
            return tab
    return "teams"

# Add a callback to set the active_tab of event-data-tabs from event-tab-store
@app.callback(
    Output("event-data-tabs", "active_tab"),
    Input("event-tab-store", "data"),
)
def set_event_tabs_active_tab(tab):
    return tab

def create_team_card_spotlight(team, event_year):
    t_num = team.get("tk")  # from compressed team list
    team_data = TEAM_DATABASE.get(event_year, {}).get(t_num, {})

    nickname = team_data.get("nickname", "Unknown")
    city = team_data.get("city", "")
    state = team_data.get("state_prov", "")
    country = team_data.get("country", "")
    location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

    # === EPA & Rank Calculation (standalone) ===
    all_teams = TEAM_DATABASE.get(event_year, {})
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

    team_epas = []
    for tnum, team_data in TEAM_DATABASE.get(event_year, {}).items():
        if team_data:
            team_epas.append((tnum, team_data.get("epa", 0)))
        
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
        "Auto ACE": compute_percentiles(auto_values),
        "Teleop ACE": compute_percentiles(teleop_values),
        "Endgame ACE": compute_percentiles(endgame_values),
    }
        
    style_data_conditional = get_epa_styling(percentiles_dict)

    # === Rankings Tab ===
    if active_tab == "rankings":
        data_rows = []
        for team_num, rank_info in (rankings or {}).items():
            tstr = str(team_num)

            try:
                team_data = TEAM_DATABASE.get(event_year, {}).get(int(team_num), {})
            except Exception as e:
                team_data = {}
            nickname = team_data.get("nickname", "Unknown")

            data_rows.append({
                "Rank": rank_info.get("rk", "N/A"),
                "Team": f"[{tstr} | {nickname}](/team/{tstr})",
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
        # Sort teams by overall EPA from TEAM_DATABASE
        sorted_teams = sorted(
            event_teams,
            key=lambda t: TEAM_DATABASE.get(event_year, {}).get(int(t.get("tk")), {}).get("epa", 0),
            reverse=True
        )
        top_3 = sorted_teams[:3]

        spotlight_cards = [
            dbc.Col(create_team_card_spotlight(t, event_year), width="auto")
            for t in top_3
        ]
        spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")

        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            # Convert team number to integer for TEAM_DATABASE lookup
            team_data = TEAM_DATABASE.get(event_year, {}).get(int(tnum), {})
            
            rows.append({
                "ACE Rank": rank_map.get(int(tnum), "N/A"),
                "ACE": f"{team_data.get('epa', 0):.2f}",
                "Auto ACE": f"{team_data.get('auto_epa', 0):.2f}",
                "Teleop ACE": f"{team_data.get('teleop_epa', 0):.2f}",
                "Endgame ACE": f"{team_data.get('endgame_epa', 0):.2f}",
                "Team": f"[{tstr} | {t.get('nn', 'Unknown')}](/team/{tstr})",
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })

        # Sort by overall EPA value
        rows.sort(key=lambda r: float(r["ACE"]) if r["ACE"] != "N/A" else 0, reverse=True)

        columns = [
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "ACE", "id": "ACE"},
            {"name": "Auto ACE", "id": "Auto ACE"},
            {"name": "Teleop ACE", "id": "Teleop ACE"},
            {"name": "Endgame ACE", "id": "Endgame ACE"},
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
            html.Div(
                [
                    html.Label("Filter by Team:", style={"fontWeight": "bold", "color": "var(--text-primary)"}),
                    dcc.Dropdown(
                        id="team-filter",
                        options=[{"label": "All Teams", "value": "ALL"}] + team_filter_options,
                        value="ALL",
                        clearable=False
                    )
                ],
                style={"marginBottom": "20px"}
            ),
            html.Div(id="matches-container")
        ]), query_string

    elif active_tab == "alliances":
        # === Extract alliance picks ===
        def extract_alliance_picks(teams, rankings=None):
            teams = [t for t in teams if t.strip()] + ["?", "?", "?"]
            teams = teams[:3]
            if rankings:
                teams = sorted(teams, key=lambda t: rankings.get(t, {}).get("rk", 9999))
            return teams[0], teams[1], teams[2]
    
        # === Identify alliances from SF matches ===
        sf_alliance_map = {1: (1, 8), 2: (4, 5), 3: (2, 7), 4: (3, 6)}
        alliance_slots = {}
        sf_matches = [m for m in event_matches if m.get("cl") == "sf" and m.get("mn") == 1]
    
        for match in sf_matches:
            key = match.get("k", "").split("_", 1)[-1].lower()
            match_re = re.match(r"sf(\d+)m1", key)
            if not match_re:
                continue
            sf_num = int(match_re.group(1))
            if sf_num not in sf_alliance_map:
                continue
            red_alliance, blue_alliance = sf_alliance_map[sf_num]
            alliance_slots[red_alliance] = match.get("rt", "").split(",")
            alliance_slots[blue_alliance] = match.get("bt", "").split(",")
    
        # === Build picked team set ===
        picked_teams = set()
        for teams in alliance_slots.values():
            picked_teams.update([t for t in teams if t.strip()])
    
        # === Alliance table ===
        alliance_table_data = []
        for i in range(1, 9):
            teams = alliance_slots.get(i, [])
            captain, pick1, pick2 = extract_alliance_picks(teams, rankings)
            alliance_table_data.append({
                "Alliance": f"Alliance {i}",
                "Captain": f"[{captain}](/team/{captain})" if captain.isdigit() else "?",
                "Pick 1": f"[{pick1}](/team/{pick1})" if pick1.isdigit() else "?",
                "Pick 2": f"[{pick2}](/team/{pick2})" if pick2.isdigit() else "?",
            })
    
        # === Ranked teams ===
        ranked_teams = sorted(
            ((str(t["tk"]), rankings.get(str(t["tk"]), {}).get("rk", 9999)) for t in event_teams),
            key=lambda x: x[1]
        )
    
        # === Nodes and Edges ===
        nodes = []
        edges = []
    
        # Teams left and right, compact spacing
        team_spacing = 0.05
        left_teams = ranked_teams[::2]
        right_teams = ranked_teams[1::2]
    
        for idx, (tnum, rk) in enumerate(left_teams):
            nodes.append({
                "id": tnum,
                "label": f"{tnum} (#{rk})",
                "x": -2,
                "y": -idx * team_spacing,
                "type": "team",
                "picked": tnum in picked_teams
            })
    
        for idx, (tnum, rk) in enumerate(right_teams):
            nodes.append({
                "id": tnum,
                "label": f"{tnum} (#{rk})",
                "x": 2,
                "y": -idx * team_spacing,
                "type": "team",
                "picked": tnum in picked_teams
            })
    
        # Calculate vertical span and center alliances accordingly
        max_left_y = -(len(left_teams) - 1) * team_spacing / 2
        max_right_y = -(len(right_teams) - 1) * team_spacing / 2
        alliance_start_y = (max_left_y + max_right_y) / 2 + (8 / 2) * team_spacing
    
        for i in range(1, 9):
            y_pos = alliance_start_y - (i - 1) * team_spacing * 2
            nodes.append({
                "id": f"A{i}",
                "label": f"Alliance {i}",
                "x": 0,
                "y": y_pos,
                "type": "alliance"
            })
    
        # Edges from alliances to picked teams
        for i in range(1, 9):
            for t in alliance_slots.get(i, []):
                if t.strip():
                    edges.append((f"A{i}", t))
    
        # Build edge traces
        edge_x, edge_y = [], []
        for src, dst in edges:
            src_node = next(n for n in nodes if n["id"] == src)
            dst_node = next(n for n in nodes if n["id"] == dst)
            edge_x += [src_node["x"], dst_node["x"], None]
            edge_y += [src_node["y"], dst_node["y"], None]
    
        # Build node traces
        node_x = [n["x"] for n in nodes]
        node_y = [n["y"] for n in nodes]
        node_text = [n["label"] for n in nodes]
        node_color = [
            "#2759d6" if n["type"] == "alliance" else ("#2ca02c" if n.get("picked") else "#c62828")
            for n in nodes
        ]
        node_size = [30 if n["type"] == "alliance" else 12 for n in nodes]
    
        # === Build figure ===
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(width=2, color="#aaa"), hoverinfo="none"
        ))
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode="markers+text",
            text=node_text, textposition="middle right",
            marker=dict(size=node_size, color=node_color, line=dict(width=1, color=node_color)),
            hoverinfo="text",
            textfont=dict(color="#777")  # <-- Add this line
        ))
        fig.update_layout(
            font=dict(color="#777"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-2.5, 2.5]),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                color="#777",  # axis ticks and label color
                title=dict(font=dict(color="#777")),  # y-axis title color
            ),
            height=1000,
        )
    
        # === Render ===
        return html.Div([
            dash_table.DataTable(
                columns=[
                    {"name": "Alliance", "id": "Alliance", "presentation": "markdown"},
                    {"name": "Captain", "id": "Captain", "presentation": "markdown"},
                    {"name": "Pick 1", "id": "Pick 1", "presentation": "markdown"},
                    {"name": "Pick 2", "id": "Pick 2", "presentation": "markdown"},
                ],
                data=alliance_table_data,
                style_table=common_style_table,
                style_header={
                    "backgroundColor": "var(--card-bg)",
                    "fontWeight": "bold",
                    "padding": "6px",
                    "fontSize": "13px",
                },
                style_cell={
                    "backgroundColor": "var(--card-bg)", 
                    "padding": "8px",
                    "fontSize": "14px",
                    "textAlign": "center"  # Default to center for safety
                },
                style_cell_conditional=[
                    {"if": {"column_id": "Alliance"}, "textAlign": "left", "fontWeight": "bold"},
                ],
                style_header_conditional=[
                    {"if": {"column_id": "Alliance"}, "textAlign": "left"},
                    {"if": {"column_id": "Captain"}, "textAlign": "center"},
                    {"if": {"column_id": "Pick 1"}, "textAlign": "center"},
                    {"if": {"column_id": "Pick 2"}, "textAlign": "center"},
                ],
                page_size=8
            ),
            dcc.Graph(
                figure=fig,
                config={
                    "staticPlot": True,  # This disables all interactivity
                    "displayModeBar": True,  # Hide the toolbar
                    "displaylogo": False,     # Hide the Plotly logo
                }
            ),
        ]), query_string

    return dbc.Alert("No data available.", color="warning"), query_string

@app.callback(
    Output("matches-container", "children"),
    Input("team-filter", "value"),
    [
        State("store-event-matches", "data"),
        State("store-event-epa", "data"),
    ],
)
def update_matches_table(selected_team, event_matches, epa_data):
    event_matches = event_matches or []
    epa_data = epa_data or {}

    # 1) Filter by team number
    if selected_team and selected_team != "ALL":
        event_matches = [
            m for m in event_matches
            if selected_team in m.get("rt", "").split(",") or selected_team in m.get("bt", "").split(",")
        ] 

    # 2) Sort and separate by comp level
    comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}

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
        return ", ".join(f"[{t}](/team/{t})" for t in team_list_str.split(",") if t.strip().isdigit())

    def get_team_epa_info(t_key):
        info = epa_data.get(str(t_key.strip()), {})
        # If event_epa_data is missing or all zeros, fallback to TEAM_DATABASE
        if not info or all(info.get(k, 0) in (None, 0, "") for k in ["epa", "confidence"]):
            # Fallback to TEAM_DATABASE
            team_data = TEAM_DATABASE.get(event_year, {}).get(int(t_key), {})
            return {
                "epa": team_data.get("epa", 0),
                "confidence": team_data.get("confidence", 0.7),
            }
        return {
            "epa": info.get("epa", 0),
            "confidence": info.get("confidence", 0),
        }
    
    def build_match_rows(matches):
        rows = []
        for match in matches:
            red_str = match.get("rt", "")
            blue_str = match.get("bt", "")
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            winner = match.get("wa", "")
            event_key = match.get("ek")
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
        {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "#ffe6e6"},
        {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "#e6f0ff"},
        # Red prediction styling
        {"if": {"filter_query": "{Red Prediction %} >= 45 && {Red Prediction %} <= 55", "column_id": "Red Pred"}, "backgroundColor": "#ededd4", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} > 55 && {Red Prediction %} <= 65", "column_id": "Red Pred"}, "backgroundColor": "#d4edda", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} > 65 && {Red Prediction %} <= 75", "column_id": "Red Predn"}, "backgroundColor": "#b6dfc1", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} > 75 && {Red Prediction %} <= 85", "column_id": "Red Pred"}, "backgroundColor": "#8fd4a8", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} > 85 && {Red Prediction %} <= 95", "column_id": "Red Pred"}, "backgroundColor": "#68c990", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} > 95", "column_id": "Red Prediction"}, "backgroundColor": "#41be77", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} < 45 && {Red Prediction %} >= 35", "column_id": "Red Pred"}, "backgroundColor": "#f8d7da", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} < 35 && {Red Prediction %} >= 25", "column_id": "Red Pred"}, "backgroundColor": "#f1bfc2", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} < 25 && {Red Prediction %} >= 15", "column_id": "Red Pred"}, "backgroundColor": "#eaa7aa", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} < 15 && {Red Prediction %} >= 5", "column_id": "Red Pred"}, "backgroundColor": "#e39091", "color": "black"},
        {"if": {"filter_query": "{Red Prediction %} < 5", "column_id": "Red Prediction"}, "backgroundColor": "#dc7878", "color": "black"},
        # Blue prediction styling
        {"if": {"filter_query": "{Blue Prediction %} >= 45 && {Blue Prediction %} <= 55", "column_id": "Blue Pred"}, "backgroundColor": "#ededd4", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} > 55 && {Blue Prediction %} <= 65", "column_id": "Blue Pred"}, "backgroundColor": "#d4edda", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} > 65 && {Blue Prediction %} <= 75", "column_id": "Blue Pred"}, "backgroundColor": "#b6dfc1", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} > 75 && {Blue Prediction %} <= 85", "column_id": "Blue Pred"}, "backgroundColor": "#8fd4a8", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} > 85 && {Blue Prediction %} <= 95", "column_id": "Blue Pred"}, "backgroundColor": "#68c990", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} > 95", "column_id": "Blue Prediction"}, "backgroundColor": "#41be77", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} < 45 && {Blue Prediction %} >= 35", "column_id": "Blue Pred"}, "backgroundColor": "#f8d7da", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} < 35 && {Blue Prediction %} >= 25", "column_id": "Blue Pred"}, "backgroundColor": "#f1bfc2", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} < 25 && {Blue Prediction %} >= 15", "column_id": "Blue Pred"}, "backgroundColor": "#eaa7aa", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} < 15 && {Blue Prediction %} >= 5", "column_id": "Blue Pred"}, "backgroundColor": "#e39091", "color": "black"},
        {"if": {"filter_query": "{Blue Prediction %} < 5", "column_id": "Blue Prediction"}, "backgroundColor": "#dc7878", "color": "black"},
        # Predicted Winner styling
        {"if": {"filter_query": '{Pred Winner} = "Red"', "column_id": "Pred Winner"}, "backgroundColor": "#ffe6e6", "color": "black"},
        {"if": {"filter_query": '{Pred Winner} = "Blue"', "column_id": "Pred Winner"}, "backgroundColor": "#e6f0ff", "color": "black"},
        {"if": {"filter_query": '{Pred Winner} = "Tie"', "column_id": "Pred Winner"}, "backgroundColor": "#f8f9fa", "color": "black"},
    ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "color": "var(--text-tertiary) !important", "backgroundColor": "white" }
    style_header={
        "backgroundColor": "var(--card-bg)",        # Match the table background
        "color": "var(--text-tertiary) !important",
        "fontWeight": "bold",              # Keep column labels strong
        "textAlign": "center",
        "borderBottom": "1px solid #ccc",  # Thin line under header only
        "padding": "6px",                  # Reduce banner size
        "fontSize": "13px",                # Optional: shrink text slightly
    }

    style_cell={
        "backgroundColor": "white", 
        "color": "var(--text-tertiary) !important",
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
        team_str = str(t.get("team_number"))
        rank = epa_ranks.get(team_str, {}).get("rank", "N/A")
        team_num = t.get("team_number")
        record = f"{t.get('wins', 0)} - {t.get('losses', 0)} - {t.get('ties', 0)} - {t.get('dq', 0)}"
        table_rows.append({
            "epa_rank": rank,
            "team_display": f"[{team_num} | {t.get('nickname', 'Unknown')}](/team/{team_num}/{selected_year})",
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
                color="#777",  # Axis ticks and label color
                title=dict(font=dict(color="#777")),  # x-axis title color
            ),
            yaxis=dict(
                showgrid=False,
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
    selected_year = int(year_value) if year_value and year_value.isdigit() else 2025
    
    # Search through all years if no specific year selected
    if selected_year is None:
        for year in TEAM_DATABASE.keys():
            year_data = TEAM_DATABASE[year]
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
        year_data = TEAM_DATABASE.get(selected_year)
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

    events_data = [ev for year_dict in EVENT_DATABASE.values() for ev in year_dict.values()]
    # --- EVENT SEARCH ---
    matching_events = []
    for event in events_data:
        event_key = event.get("k", "").lower()
        event_name = (event.get("n", "") or "").lower()
        event_code = (event.get("cd", "") or "").lower()
        event_year = (event.get("sd", "") or "")[:4]

        if (
            search_value in event_key
            or search_value in event_name
            or search_value in event_code
            or search_value in f"{event_year} {event_name}".lower()
        ):
            matching_events.append(event)

    if matching_events:
        # pick the "closest" match — most character overlap
        best_event = max(
            matching_events,
            key=lambda e: (
                len(set(search_value) & set((e.get("cd") or "").lower())) +
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
        return wrap_with_toast_or_star(team_layout(team_number, year, TEAM_DATABASE, EVENT_DATABASE))
    
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
    import plotly.graph_objects as go
    from dash import html
    import dash_bootstrap_components as dbc

    if not team_ids or len(team_ids) < 2:
        # Provide a message prompting the user to select teams
        return dbc.Alert("Select at least 2 teams to compare.", color="info", className="text-center my-4")

    year = year or 2025
    
    # Check if data for the selected year is available
    if not TEAM_DATABASE.get(year):
        return html.Div(f"Loading data for year {year}...", className="text-center my-4", style={"color": "var(--text-secondary)"})

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

    # Import get_team_avatar
    from datagather import get_team_avatar

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

    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
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
    finally:
        conn.close()

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

    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
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
    finally:
        conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=False)

