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

import sqlite3
import psycopg2
import re
from urllib.parse import urlparse
from urllib.parse import parse_qs
from urllib.parse import urlencode
import json
from statistics import mean, pstdev
import statistics
import math
import pandas as pd

import plotly.graph_objects as go

from datagather import COUNTRIES,STATES,load_data,get_team_avatar,calculate_ranks,DISTRICT_STATES,get_pg_connection,get_epa_styling,compute_percentiles,sort_key,get_username,get_available_avatars,get_contrast_text_color

from layouts.basic import home_layout,footer,topbar,team_link_with_avatar,blog_layout,challenges_layout,challenge_details_layout

from dotenv import load_dotenv
load_dotenv()

TEAM_DATABASE, EVENT_DATABASE, EVENTS_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES, EVENT_OPRS = load_data()

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

# -------------- LAYOUTS --------------

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='tab-title', data='Peekorobo'),
    html.Div(id='page-content'),
    html.Div(id='dummy-output', style={'display': 'none'})
])

@app.callback(
    Output('tab-title', 'data'),
    Input('url', 'pathname'),
)
def update_tab_title(pathname):
    if pathname.startswith('/team/'):
        team_number = pathname.split('/team/')[1].split('/')[0]
        return f'Peekorobo - {team_number}'
    elif pathname.startswith('/teams'):
        return 'Peekorobo - Teams'
    elif pathname.startswith('/event/'):
        event_key = pathname.split('/event/')[1].split('/')[0]
        return f'Peekorobo - {event_key}'
    elif pathname.startswith('/events'):
        return 'Peekorobo - Events'
    elif pathname.startswith('/map'):
        return 'Peekorobo - Map'
    elif pathname.startswith('/user/'):
        username = pathname.split('/user/')[1].split('/')[0]
        return f'Peekorobo - {username}'
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
                            src="/assets/dozer.gif",
                            style={"width": "100%", "maxWidth": "400px", "marginBottom": "30px"},
                            className="dozer-image"
                        ),
                        html.H3("Login or Register", style={"textAlign": "center", "marginBottom": "20px", "color": "var(--text-primary)"}),
                        dbc.Input(id="username", type="text", placeholder="Username", className="custom-input-box", style={"width": "100%", "maxWidth": "400px", "margin": "auto", "marginBottom": "1rem"}),
                        dbc.Input(id="password", type="password", placeholder="Password", className="custom-input-box", style={"width": "100%", "maxWidth": "400px", "margin": "auto", "marginBottom": "1.5rem"}),
                        dbc.Row([
                            dbc.Col(dbc.Button("Login", id="login-btn", style={
                                "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%"
                            }), width=6),
                            dbc.Col(dbc.Button("Register", id="register-btn", style={
                                "backgroundColor": "#ffdd00ff", "border": "2px solid #555", "color": "black", "width": "100%"
                            }), width=6),
                        ], justify="center", style={"maxWidth": "400px", "margin": "auto"}),
                        html.Div(id="login-message", style={"textAlign": "center", "marginTop": "1rem", "color": "#333", "fontWeight": "bold"}),
                    ], style={"textAlign": "center", "paddingTop": "50px"})
                , width=12),
            )
        ], class_name="py-5", style={"backgroundColor": "var(--bg-primary)"}),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer
    ])

def universal_profile_icon_or_toast():
    if "user_id" in session:
        user_id = session["user_id"]

        # Fetch avatar_key from database
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT avatar_key FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            avatar_key = row[0] if row and row[0] else "stock"
        except Exception as e:
            print(f"Error fetching avatar: {e}")
            avatar_key = "stock.png"
        finally:
            conn.close()

        return html.A(
    html.Img(
        src=f"/assets/avatars/{avatar_key}",
        style={
            "position": "fixed",
            "bottom": "10px",
            "right": "10px",
            "height": "45px",
            "width": "auto",           # ✅ Let width adjust naturally
            "cursor": "pointer",
            "zIndex": 9999,
            "border": "none",          # ✅ No border
            "borderRadius": "0",       # ✅ NOT a circle
            "backgroundColor": "transparent",  # ✅ No background
            "objectFit": "contain"     # ✅ Avoid distortion
        }
    ),
    href="/user"
)


    # Unauthenticated fallback toast
    return dbc.Toast(
        [
            html.Strong("New here?", className="me-auto"),
            html.Div("Create an account or log in to save favorite teams & events."),
            dbc.Row([
                dbc.Col(
                    dbc.Button("Login", href="/login", size="sm", color="secondary", className="mt-2", style={
                        "width": "100%",
                        "backgroundColor": "#ddd",
                        "color": "#000",
                        "border": "1px solid #999"
                    }),
                    width=6
                ),
                dbc.Col(
                    dbc.Button("Register", href="/login", size="sm", color="warning", className="mt-2", style={
                        "width": "100%",
                        "backgroundColor": "#ffdd00ff",
                        "color": "#000",
                        "border": "1px solid #999"
                    }),
                    width=6
                )
            ], className="mt-1")
        ],
        id="register-popup",
        header="Join Peekorobo",
        is_open=True,
        dismissable=True,
        icon="warning",
        style={
            "position": "fixed",
            "bottom": 20,
            "right": 20,
            "width": 300,
            "zIndex": 9999
        },
    )

def user_layout(_user_id=None, deleted_items=None):

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
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
        }
        for team_num, data in TEAM_DATABASE.get(2025, {}).items()
    }

    def team_card(title, body_elements, delete_button=None):
        return dbc.Card(
            dbc.CardBody([
                html.Div([
                    html.Div(title, style={
                        "fontWeight": "bold",
                        "fontSize": "1.1rem",
                        "textDecoration": "underline",
                        "color": "#007bff",
                        "cursor": "pointer"
                    }),
                    delete_button if delete_button else None
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                html.Hr(),
                *body_elements,
            ]),
            className="mb-4",
            style={  # ✅ Custom styling applied here
                "borderRadius": "10px",
                "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                "backgroundColor": "var(--card-bg)",
                "marginBottom": "20px"
            }
        )


    def event_card(body_elements, delete_button=None):
        return dbc.Card(
            dbc.CardBody([
                html.Div([
                    delete_button if delete_button else None
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                *body_elements
            ]),
            className="mb-4",
            style={  # ← You can replace this block:
                "borderRadius": "10px",
                "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                "backgroundColor": "var(--card-bg)",
                "marginBottom": "20px"
            }
        )

    
    team_cards = []
    for team_key in team_keys:
        try:
            team_number = int(team_key)
        except:
            continue

        team_data = TEAM_DATABASE.get(2025, {}).get(team_number)
        year_data = TEAM_DATABASE.get(2025, {})

        delete_team_btn = html.Button(
            "🗑️",
            id={"type": "delete-favorite", "item_type": "team", "key": team_key},
            style={
                "backgroundColor": "transparent",
                "border": "none",
                "color": "#dc3545",  # optional: red trash color
                "cursor": "pointer",
                "fontSize": "1.2rem"  # optional: adjust icon size
            }
        )

        def get_epa_color(value, all_values):
            if not all_values:
                return "#000000"  # default to black
            sorted_vals = sorted(all_values, reverse=True)
            rank = sorted_vals.index(value) + 1
            percentile = rank / len(sorted_vals)
        
            if percentile <= 0.01:
                return "#800080"  # purple
            elif percentile <= 0.05:
                return "#0000ff"  # blue
            elif percentile <= 0.10:
                return "#008000"  # green
            elif percentile <= 0.25:
                return "orange"  # yellow
            elif percentile <= 0.50:
                return "#ff0000"  # red
            else:
                return "#8B4513"  # brown
        


        if team_data:
            epa = team_data.get("epa", 0)
            teleop = team_data.get("teleop_epa", 0)
            auto = team_data.get("auto_epa", 0)
            endgame = team_data.get("endgame_epa", 0)
            wins = team_data.get("wins", 0)
            losses = team_data.get("losses", 0)
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

            team_data_2025 = list(TEAM_DATABASE.get(2025, {}).values())

            epa_vals = [t.get("epa", 0) or 0 for t in team_data_2025]
            auto_vals = [t.get("auto_epa", 0) or 0 for t in team_data_2025]
            teleop_vals = [t.get("teleop_epa", 0) or 0 for t in team_data_2025]
            endgame_vals = [t.get("endgame_epa", 0) or 0 for t in team_data_2025]


            epa_color = get_epa_color(epa, epa_vals)
            auto_color = get_epa_color(auto, auto_vals)
            teleop_color = get_epa_color(teleop, teleop_vals)
            endgame_color = get_epa_color(endgame, endgame_vals)


            metrics = html.Div([
                html.Div("ACE", className="metric-label"),
                html.Div(f"{epa:.2f}", className="metric-value", style={"color": epa_color, "fontWeight": "bold"}),
            
                html.Div("Auto", className="metric-label"),
                html.Div(f"{auto:.2f}", className="metric-value", style={"color": auto_color, "fontWeight": "bold"}),
            
                html.Div("Teleop", className="metric-label"),
                html.Div(f"{teleop:.2f}", className="metric-value", style={"color": teleop_color, "fontWeight": "bold"}),
            
                html.Div("Endgame", className="metric-label"),
                html.Div(f"{endgame:.2f}", className="metric-value", style={"color": endgame_color, "fontWeight": "bold"}),
            
                html.Div("Global Rank", className="metric-label"),
                    html.A(
                        str(global_rank),
                        href="/teams?sort_by=epa&x=teleop_epa&y=auto%2Bendgame",
                        className="metric-value",
                        style={
                            "color": "#007BFF",
                            "fontWeight": "bold",
                            "textDecoration": "underline",
                            "cursor": "pointer"
                        }
                    ),

                    
                    html.Div(f"{country.title()} Rank", className="metric-label"),
                    html.A(
                        str(country_rank),
                        href=f"/teams?country={country}&sort_by=epa&x=teleop_epa&y=auto%2Bendgame",
                        className="metric-value",
                        style={
                            "color": "#007BFF",
                            "fontWeight": "bold",
                            "textDecoration": "underline",
                            "cursor": "pointer"
                        }
                    ),
                    
                    html.Div(f"{state.title()} Rank", className="metric-label"),
                    html.A(
                        str(state_rank),
                        href=f"/teams?country={country}&state={state}&sort_by=epa&x=teleop_epa&y=auto%2Bendgame",
                        className="metric-value",
                        style={
                            "color": "#007BFF",
                            "fontWeight": "bold",
                            "textDecoration": "underline",
                            "cursor": "pointer"
                        }
                    ),
            
                html.Div([
                    html.Span("Record", className="metric-label", style={"marginRight": "8px"}),
                    html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
                    html.Span(" / "),
                    html.Span(str(losses), style={"color": "red", "fontWeight": "bold"})
                ], style={"gridColumn": "span 8", "display": "flex", "alignItems": "center"})
            ], style={
                "display": "grid",
                "gridTemplateColumns": "repeat(8, 1fr)",
                "gap": "4px 8px",
                "fontSize": "0.85rem",
                "marginTop": "10px",
                "width": "100%"
            })

        team_cards.append(team_card(
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
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, 2025)
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
                for aw in EVENTS_AWARDS
            )
    
            if not played_matches and not earned_awards:
                continue  # skip Einstein if no participation
    
        year = 2025
        matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
        # ... rest of your card building logic ...

        delete_event_btn = html.Button(
            "🗑️",
            id={"type": "delete-favorite", "item_type": "event", "key": event_key},
            style={
                "backgroundColor": "transparent",
                "border": "none",
                "color": "#dc3545",  # optional: red trash color
                "cursor": "pointer",
                "fontSize": "1.2rem"  # optional: adjust icon size
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
                event_section = build_recent_events_section(f"frc{team_number}", team_number, epa_data, 2025)
                match_rows = event_section.children[-1].children
            else:
                match_rows = [html.P("No favorited teams at this event.")]


        event_data = EVENT_DATABASE.get(year, {}).get(event_key, {})
        event_name = event_data.get("n", "Unknown Event")
        event_label = f"{event_name} | {event_key}"
        event_url = f"/event/{event_key}"
        location = ", ".join(filter(None, [event_data.get("c", ""), event_data.get("s", ""), event_data.get("co", "")]))
        

        event_cards.append(event_card(
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
                    delete_event_btn
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
        
                html.Div(location, style={"fontSize": "0.85rem", "color": "#666", "marginBottom": "0.5rem"}),
                html.Hr(),
                build_recent_matches_section(event_key, year, epa_data)
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
                                    f"{len(team_keys)} favorite teams | {len(event_keys)} favorite events",
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
            html.H3("Favorite Events", className="mb-3"),
            *event_cards,

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
            "auto_epa": data.get("auto_epa", 0),
            "teleop_epa": data.get("teleop_epa", 0),
            "endgame_epa": data.get("endgame_epa", 0),
        }
        for team_num, data in TEAM_DATABASE.get(2025, {}).items()
    }

    def get_epa_color(value, all_values):
        if not all_values:
            return "#000000"
        sorted_vals = sorted(all_values, reverse=True)
        rank = sorted_vals.index(value) + 1
        percentile = rank / len(sorted_vals)
        if percentile <= 0.01:
            return "#800080"
        elif percentile <= 0.05:
            return "#0000ff"
        elif percentile <= 0.10:
            return "#008000"
        elif percentile <= 0.25:
            return "orange"
        elif percentile <= 0.50:
            return "#ff0000"
        else:
            return "#8B4513"

    def team_card(title, body_elements):
        return dbc.Card(
            dbc.CardBody([
                html.Div([
                    html.Div(title, style={
                        "fontWeight": "bold",
                        "fontSize": "1.1rem",
                        "textDecoration": "underline",
                        "color": "#007bff",
                        "cursor": "pointer"
                    })
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                html.Hr(),
                *body_elements
            ]),
            className="mb-4",
            style={
                "borderRadius": "10px",
                "boxShadow": "0px 6px 16px rgba(0,0,0,0.2)",
                "backgroundColor": "var(--card-bg)",
                "marginBottom": "20px"
            }
        )

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
        teleop = team_data.get("teleop_epa", 0)
        auto = team_data.get("auto_epa", 0)
        endgame = team_data.get("endgame_epa", 0)
        wins = team_data.get("wins", 0)
        losses = team_data.get("losses", 0)
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
        epa_vals = [t.get("epa", 0) or 0 for t in year_data]
        auto_vals = [t.get("auto_epa", 0) or 0 for t in year_data]
        teleop_vals = [t.get("teleop_epa", 0) or 0 for t in year_data]
        endgame_vals = [t.get("endgame_epa", 0) or 0 for t in year_data]

        epa_color = get_epa_color(epa, epa_vals)
        auto_color = get_epa_color(auto, auto_vals)
        teleop_color = get_epa_color(teleop, teleop_vals)
        endgame_color = get_epa_color(endgame, endgame_vals)

        metrics = html.Div([
            html.Div("ACE", className="metric-label"),
            html.Div(f"{epa:.2f}", className="metric-value", style={"color": epa_color, "fontWeight": "bold"}),
            html.Div("Auto", className="metric-label"),
            html.Div(f"{auto:.2f}", className="metric-value", style={"color": auto_color, "fontWeight": "bold"}),
            html.Div("Teleop", className="metric-label"),
            html.Div(f"{teleop:.2f}", className="metric-value", style={"color": teleop_color, "fontWeight": "bold"}),
            html.Div("Endgame", className="metric-label"),
            html.Div(f"{endgame:.2f}", className="metric-value", style={"color": endgame_color, "fontWeight": "bold"}),
            html.Div("Global Rank", className="metric-label"),
            html.Div(global_rank, className="metric-value", style={"color": "blue", "fontWeight": "bold"}),
            html.Div(f"{country} Rank", className="metric-label"),
            html.Div(country_rank, className="metric-value", style={"color": "blue", "fontWeight": "bold"}),
            html.Div(f"{state} Rank", className="metric-label"),
            html.Div(state_rank, className="metric-value", style={"color": "blue", "fontWeight": "bold"}),
            html.Div([
                html.Span("Record", className="metric-label", style={"marginRight": "8px"}),
                html.Span(str(wins), style={"color": "green", "fontWeight": "bold"}),
                html.Span(" / "),
                html.Span(str(losses), style={"color": "red", "fontWeight": "bold"})
            ], style={"gridColumn": "span 8", "display": "flex", "alignItems": "center"})
        ], style={
            "display": "grid",
            "gridTemplateColumns": "repeat(8, 1fr)",
            "gap": "4px 8px",
            "fontSize": "0.85rem",
            "marginTop": "10px",
            "width": "100%"
        })

        team_cards.append(team_card(
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
                build_recent_events_section(f"frc{team_key}", int(team_key), epa_data, 2025)
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
            section = build_recent_events_section(f"frc{team_number}", team_number, epa_data, 2025)
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
                                html.Div(f"{len(team_keys)} favorite teams | {len(event_keys)} favorite events", style={"fontSize": "0.85rem", "color": text_color}),
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
            html.H3("Favorite Events", className="mb-3"),
            *event_cards,
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

def get_user_avatar(avatar_key):
    return f"/assets/avatars/{avatar_key}"

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
)
def update_search_preview(desktop_value, mobile_value):
    desktop_value = (desktop_value or "").strip().lower()
    mobile_value = (mobile_value or "").strip().lower()

    # Collapse TEAM_DATABASE to a flat dict keeping only the most recent year for each team
    latest_teams = {}
    for year in sorted(TEAM_DATABASE.keys(), reverse=True):
        for team_number, team_data in TEAM_DATABASE[year].items():
            if team_number not in latest_teams:
                latest_teams[team_number] = team_data
    teams_data = list(latest_teams.values())

    events_data = EVENTS_DATABASE  # flat list of compressed event dicts

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
        for e in events_data:
            event_code = (e.get("cd") or "").lower()
            event_name = (e.get("n") or "").lower()
            start_date = e.get("sd", "")
            event_year = start_date[:4] if len(start_date) >= 4 else ""
            year_name_combo = f"{event_year} {event_name}".lower()

            if (val in event_code) or (val in event_name) or (val in year_name_combo):
                filtered_events.append(e)
        filtered_events = filtered_events[:20]

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
                background_color = "white"
                if (closest_team_number and tn == closest_team_number["team_number"]) or \
                   (closest_team_nickname and nm == closest_team_nickname["nickname"]):
                    background_color = "#FFDD00"

                row_el = dbc.Row(
                    dbc.Col(team_link_with_avatar(team)),
                    style={"padding": "5px", "backgroundColor": background_color},
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
                background_color = "white"

                if closest_event and event_key == closest_event.get("k"):
                    background_color = "#FFDD00"

                display_text = f"{event_key} | {e_year} {e_name}"
                row_el = dbc.Row(
                    dbc.Col(
                        html.A(
                            display_text,
                            href=f"/event/{event_key}",
                            style={"lineHeight": "20px", "textDecoration": "none", "color": "black"},
                        ),
                        width=True,
                    ),
                    style={"padding": "5px", "backgroundColor": background_color},
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
                        ], href=f"/user/{username}", style={"textDecoration": "none", "color": "black"}),
                    ),
                    style={"padding": "5px", "backgroundColor": "white"},
                )
                children.append(row_el)


        if not filtered_teams and not filtered_events:
            children.append(html.Div("No results found.", style={"padding": "5px", "color": "#555"}))

        style_dict = {
            "display": "block",
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
        }
        return children, style_dict

    desktop_children, desktop_style = get_children_and_style(desktop_value)
    mobile_children, mobile_style = get_children_and_style(mobile_value)

    return desktop_children, desktop_style, mobile_children, mobile_style

def build_recent_events_section(team_key, team_number, epa_data, performance_year):
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


    def effective_epa(team_infos):
        if not team_infos:
            return 0
        
        weighted_epas = []
        for t in team_infos:
            epa = t["epa"]
            conf = t["confidence"]
            cons = t["consistency"]
            reliability = 0.5 * conf + 0.5 * cons
            weight = 0.5 + 0.5 * reliability
            weighted_epas.append(epa * weight)
        
        return mean(weighted_epas)
    
    def predict_win_probability(red_info, blue_info, boost=1.1):
        red_eff = effective_epa(red_info)
        blue_eff = effective_epa(blue_info)
        reliability = mean([t["confidence"] for t in red_info + blue_info]) if red_info + blue_info else 0
    
        if red_eff + blue_eff == 0:
            return 0.5, 0.5
    
        diff = red_eff - blue_eff
        scale = boost * (0.06 + 0.3 * (1 - reliability))
        p_red = 1 / (1 + math.exp(-scale * diff))
        p_red = max(0.15, min(0.90, p_red))  # clip for calibration
        return p_red, 1 - p_red



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
        
                winner = match.get("wa", "N/A").title()
                youtube_id = match.get("yt")
                video_link = f"[Watch](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
        
                row = {
                    "Video": video_link,
                    "Match": label,
                    "Red Teams": format_team_list(red_str),
                    "Blue Teams": format_team_list(blue_str),
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
                    {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
                    {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
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

def build_recent_matches_section(event_key, year, epa_data):
    matches = [m for m in EVENT_MATCHES.get(year, []) if m.get("ek") == event_key]
    if not matches:
        return html.P("No matches available for this event.")

    epa_data = epa_data or {}

    # Sort matches by comp level and match number
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

    def effective_epa(team_infos):
        if not team_infos:
            return 0
        
        weighted_epas = []
        for t in team_infos:
            epa = t["epa"]
            conf = t["confidence"]
            cons = t["consistency"]
            reliability = 0.5 * conf + 0.5 * cons
            weight = 0.5 + 0.5 * reliability
            weighted_epas.append(epa * weight)
        
        return mean(weighted_epas)
    
    def predict_win_probability(red_info, blue_info, boost=1.1):
        red_eff = effective_epa(red_info)
        blue_eff = effective_epa(blue_info)
        reliability = mean([t["confidence"] for t in red_info + blue_info]) if red_info + blue_info else 0
    
        if red_eff + blue_eff == 0:
            return 0.5, 0.5
    
        diff = red_eff - blue_eff
        scale = boost * (0.06 + 0.3 * (1 - reliability))
        p_red = 1 / (1 + math.exp(-scale * diff))
        p_red = max(0.15, min(0.90, p_red))  # clip for calibration
        return p_red, 1 - p_red


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
                prediction = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"

            yid = match.get("yt")
            video_link = f"[Watch](https://youtube.com/watch?v={yid})" if yid else "N/A"

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Teams": format_teams_markdown(red_str),
                "Blue Teams": format_teams_markdown(blue_str),
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
        {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
        {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
        {"name": "Red Score", "id": "Red Score"},
        {"name": "Blue Score", "id": "Blue Score"},
        {"name": "Winner", "id": "Winner"},
        {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
    ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none"}
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
        *qual_table,
        *playoff_table
    ])

def team_layout(team_number, year):

    user_id = session.get("user_id")
    is_logged_in = bool(user_id)
    
    favorite_button = dbc.Button(
        "⭐  Favorite",
        id="favorite-team-btn",
        href="/login" if not is_logged_in else None,
        color="warning",
        style={
            "marginTop": "10px",
            "backgroundColor": "#fffff0",
            "color": "black",
            "border": "1px solid #555",
            "fontWeight": "bold",
        }
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
    global_rank, country_rank, state_rank = calculate_ranks(list(year_data.values()), selected_team)

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
                        "color": "#333",
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
            dbc.Alert(id="favorite-alert", is_open=False, duration=3000, color="warning"),
            dbc.Container(
                [
                    team_card,
                    rank_card,  # ← new
                    performance_metrics_card,  # ← new
                    html.Hr(),
                    build_recent_events_section(team_key, team_number, epa_data, performance_year),
                    html.H3("Events", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Awards", style={"marginTop": "2rem", "color": "var(--text-secondary)", "fontWeight": "bold"}),
                    awards_table,
                    # rank_tabs,
                    blue_banner_section,
                    html.Br(),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )


@app.callback(
    Output("favorite-alert", "children"),
    Output("favorite-alert", "is_open"),
    Input("favorite-team-btn", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True
)
def save_favorite(n_clicks, pathname):

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
    )
    week_dropdown = dcc.Dropdown(
        id="week-dropdown",
        options=(
            [{"label": "All Wks", "value": "all"}] +
            [{"label": f"Wk {i+1}", "value": i} for i in range(0, 6)]
        ),
        placeholder="Week",
        value="all",
        clearable=False,
    )
    district_dropdown = dcc.Dropdown(
        id="district-dropdown",
        options=[],
        placeholder="District",
        value="all",
        clearable=False,
    )
    sort_toggle = dcc.RadioItems(
        id="sort-mode-toggle",
        options=[
            {"label": "Sort by Time", "value": "time"},
            {"label": "Sort A–Z", "value": "alpha"},
        ],
        value="time",
        labelStyle={"display": "inline-block", "margin-right": "15px"},
    )
    search_input = dbc.Input(
        id="search-input",
        placeholder="Search",
        type="text",
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
                            dbc.Tab(label="Cards", tab_id="cards-tab"),
                            dbc.Tab(label="Event Insights", tab_id="table-tab"),
                        ],
                        className="mb-4",
                    ),
                    html.Div(id="events-tab-content"),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

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

    def get_week_number(start_date):
        WEEK_RANGES = [
            (date(2025, 2, 26), date(2025, 3, 2)),   # Week 1
            (date(2025, 3, 5),  date(2025, 3, 9)),   # Week 2
            (date(2025, 3, 12), date(2025, 3, 17)),  # Week 3
            (date(2025, 3, 19), date(2025, 3, 23)),  # Week 4
            (date(2025, 3, 25), date(2025, 3, 30)),  # Week 5
            (date(2025, 4, 2),  date(2025, 4, 6)),   # Week 6
        ]
        
        if start_date < WEEK_RANGES[0][0]:
            return 0
        elif start_date > WEEK_RANGES[-1][1]:
            return 7
    
        for i, (start, end) in enumerate(WEEK_RANGES):
            if start <= start_date <= end:
                return i + 1
    
        return "N/A"


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
            name = full_name.split(" presented by")[0].strip()

            try:
                start_date = datetime.strptime(event.get("sd", ""), "%Y-%m-%d").date()
                week = get_week_number(start_date)
            except Exception:
                week = "N/A"
    
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
            top_8 = statistics.mean(epa_values[:8]) if len(epa_values) >= 8 else statistics.mean(epa_values)
            top_24 = statistics.mean(epa_values[:24]) if len(epa_values) >= 24 else statistics.mean(epa_values)
            mean_epa = statistics.median(epa_values)
    
            rows.append({
                "Name": f"[{name}](/event/{event_key})",
                "Week": week,
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
                {"name": "Week", "id": "Week"},
                {"name": "Event Type", "id": "Event Type"},
                {"name": "Max ACE", "id": "Max ACE"},
                {"name": "Top 8 ACE", "id": "Top 8 ACE"},
                {"name": "Top 24 ACE", "id": "Top 24 ACE"},
            ],
            data=df.to_dict("records"),
            style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none"},
            style_header={
                "backgroundColor": "white",        # Match the table background
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
            },
            style_data_conditional=style_data_conditional,
            style_as_list_view=True,
        ), district_options


    # Default: cards tab
    today = date.today()
    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    up_cards = [dbc.Col(create_event_card(ev, favorited=(ev["k"] in user_favorites)), width="auto") for ev in upcoming[:5]]

    ongoing_section = html.Div([
        html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
        dbc.Row([dbc.Col(create_event_card(ev, favorited=(ev["k"] in user_favorites)), width="auto") for ev in ongoing], className="justify-content-center"),
    ]) if ongoing else html.Div()

    all_event_cards = [create_event_card(ev, favorited=(ev["k"] in user_favorites)) for ev in events_data]

        # Conditionally render Upcoming Events section
    upcoming_section = html.Div([
        html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
        dbc.Row(up_cards, className="justify-content-center"),
    ]) if upcoming else html.Div()
    
    return html.Div([
        upcoming_section,
        ongoing_section,
        html.Div(all_event_cards, className="d-flex flex-wrap justify-content-center"),
    ]), district_options
    

def create_event_card(event, favorited=False):
    event_key = event["k"]
    event_url = f"https://www.peekorobo.com/event/{event_key}"
    location = f"{event.get('c','')}, {event.get('s','')}, {event.get('co','')}"
    start = event.get("sd", "N/A")
    end = event.get("ed", "N/A")
    event_type = event.get("et", "N/A")

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H5(event.get("n", "Unknown Event"), className="card-title mb-3"),
                    html.P(location, className="card-text"),
                    html.P(f"Dates: {start} - {end}", className="card-text"),
                    html.P(f"Type: {event_type}", className="card-text"),
                    dbc.Button("View Details", href=event_url, target="_blank",
                               color="warning", className="mt-2 me-2"),
                    dbc.Button(
                        "★" if favorited else "☆",
                        id={"type": "favorite-event-btn", "key": event_key},
                        color="link",
                        className="mt-2 p-0",
                        style={
                            "fontSize": "1.5rem",
                            "lineHeight": "1",
                            "border": "none",
                            "boxShadow": "none",
                            "background": "none",
                            "textDecoration": "none"
                        }
                    )
                ]
            )
        ],
        className="mb-4 shadow",
        style={"width": "18rem", "height": "22rem", "margin": "10px"},
    )

@app.callback(
    [
        Output("favorite-event-alert", "children"),
        Output("favorite-event-alert", "is_open"),
        Output("event-favorites-store", "data"),
    ],
    Input({"type": "favorite-event-btn", "key": ALL}, "n_clicks"),
    State({"type": "favorite-event-btn", "key": ALL}, "id"),
    State("event-favorites-store", "data"),
    prevent_initial_call=True,
)
def toggle_favorite_event(n_clicks_list, id_list, store_data):
    if "user_id" not in session:
        return dash.no_update, False, dash.no_update

    triggered = ctx.triggered_id
    if not triggered or "key" not in triggered:
        return dash.no_update, False, dash.no_update

    index = next((i for i, id_ in enumerate(id_list) if id_["key"] == triggered["key"]), None)
    if index is None or n_clicks_list[index] is None or n_clicks_list[index] == 0:
        return dash.no_update, False, dash.no_update

    user_id = session["user_id"]
    event_key = triggered["key"]
    store_data = store_data or []

    conn = get_pg_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM saved_items
        WHERE user_id = %s AND item_type = 'event' AND item_key = %s
    """, (user_id, event_key))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            DELETE FROM saved_items
            WHERE user_id = %s AND item_type = 'event' AND item_key = %s
        """, (user_id, event_key))
        conn.commit()
        new_store = [k for k in store_data if k != event_key]
        result = ("Event removed from favorites.", True, new_store)
    else:
        cursor.execute("""
            INSERT INTO saved_items (user_id, item_type, item_key)
            VALUES (%s, 'event', %s)
        """, (user_id, event_key))
        conn.commit()
        result = ("Event added to favorites.", True, store_data + [event_key])

    conn.close()
    return result

WEEK_RANGES = [
    (date(2025, 2, 26), date(2025, 3, 2)),  # Week 1
    (date(2025, 3, 5),  date(2025, 3, 9)),   # Week 2
    (date(2025, 3, 12), date(2025, 3, 17)),  # Week 3
    (date(2025, 3, 19), date(2025, 3, 23)),  # Week 4
    (date(2025, 3, 25), date(2025, 3, 30)),  # Week 5
    (date(2025, 4, 2),  date(2025, 4, 6)),   # Week 6
]


def get_week_number(start_date):
    for i, (start, end) in enumerate(WEEK_RANGES):
        if start <= start_date <= end:
            return i
    return None

def load_teams_and_compute_epa_ranks(year):
    epa_info = {}

    year_data = TEAM_DATABASE.get(year)
    if not year_data:
        return [], {}

    teams_data = list(year_data.values())

    for team in teams_data:
        epa = team.get("epa", 0) or 0  # <- already includes confidence

        # For display: this is the "Total ACE"
        team["display_ace"] = epa
        # Choose sorting strategy
        team["sort_metric"] = epa

    # Sort by the chosen ranking metric
    teams_data = sorted(teams_data, key=lambda x: x.get("sort_metric", 0), reverse=True)

    # Compute percentiles for display using `display_ace` only
    values = [team.get("display_ace") for team in teams_data if team.get("display_ace") is not None]
    percentiles = {p: np.percentile(values, int(p)) for p in ["99", "95", "90", "75", "50", "25"]} if values else {p: 0 for p in ["99", "95", "90", "75", "50", "25"]}

    for idx, team in enumerate(teams_data):
        team_number = str(team["team_number"])
        ace = team["display_ace"]
        rank = idx + 1
        epa_info[team_number] = {
            "epa": ace,
            "rank": rank,
            "epa_display": ace,
        }

    return teams_data, epa_info

def event_layout(event_key):
    parsed_year, _ = parse_event_key(event_key)
    event = EVENT_DATABASE.get(parsed_year, {}).get(event_key)
    if not event:
        return dbc.Alert("Event details could not be found.", color="danger")

    _, epa_data = load_teams_and_compute_epa_ranks(parsed_year)
    event_year = parsed_year
    event_teams = EVENT_TEAMS.get(event_year, {}).get(event_key, [])
    rankings = EVENT_RANKINGS.get(event_year, {}).get(event_key, {})

    # Compressed match keys
    event_matches = [m for m in EVENT_MATCHES.get(event_year, []) if m.get("ek") == event_key]

    event_name = event.get("n", "Unknown Event")
    event_location = f"{event.get('c', '')}, {event.get('s', '')}, {event.get('co', '')}"
    start_date = event.get("sd", "N/A")
    end_date = event.get("ed", "N/A")
    event_type = event.get("et", "N/A")
    website = event.get("w", "#")

    # Header card
    header_card = dbc.Card(
        html.Div([
            dbc.Button(
                id="favorite-event-btn",
                children="★",  # will be toggled dynamically
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
            ),
            dbc.CardBody([
                html.H2(f"{event_name} ({event_year})", className="card-title mb-3", style={"fontWeight": "bold"}),
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

    tab_style = {"color": "#3b3b3b"}
    data_tabs = dbc.Tabs(
        [
            dbc.Tab(label="Teams", tab_id="teams", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Rankings", tab_id="rankings", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="OPRs", tab_id="oprs", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Matches", tab_id="matches", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Alliances", tab_id="alliances", label_style=tab_style, active_label_style=tab_style),
        ],
        id="event-data-tabs",
        active_tab="teams",
        className="mb-4",
    )

    return html.Div(
        [
            dcc.Store(id="user-session"),  # Holds user_id from session
            topbar(),
            dbc.Store(id="event-favorites-store", storage_type="session"),
            dbc.Alert(id="favorite-event-alert", is_open=False, duration=3000, color="warning"),
            dbc.Container(
                [
                    header_layout,
                    data_tabs,
                    dcc.Store(id="store-event-epa", data=epa_data),
                    dcc.Store(id="store-event-teams", data=event_teams),
                    dcc.Store(id="store-rankings", data=rankings),
                    dcc.Store(id="store-event-matches", data=event_matches),
                    dcc.Store(id="store-event-year", data=event_year),
                    dcc.Store(
                        id="store-oprs",
                        data={"oprs": EVENT_OPRS.get(event_year, {}).get(event_key, {})}
                    ),
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

def create_team_card_spotlight(team, epa_data, event_year):
    t_num = team.get("tk")  # from compressed team list
    team_data = TEAM_DATABASE.get(event_year, {}).get(t_num, {})

    nickname = team_data.get("nickname", "Unknown")
    city = team_data.get("city", "")
    state = team_data.get("state_prov", "")
    country = team_data.get("country", "")
    location_str = ", ".join(filter(None, [city, state, country])) or "Unknown"

    # ACE info
    t_key_str = str(t_num)
    epa_rank = epa_data.get(t_key_str, {}).get("rank", "N/A")
    epa_display = epa_data.get(t_key_str, {}).get("epa_display", "N/A")

    # Avatar and team link
    avatar_url = get_team_avatar(t_num, event_year)
    team_url = f"/team/{t_num}/{event_year}"

    card_elems = []
    if avatar_url:
        card_elems.append(
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={
                    "width": "100%",
                    "height": "150px",
                    "objectFit": "contain",
                    "backgroundColor": "transparent",
                    "padding": "5px"
                }
            )
        )

    card_elems.append(
        dbc.CardBody(
            [
                html.H5(f"#{t_num} | {nickname}", className="card-title mb-3"),
                html.P(f"Location: {location_str}", className="card-text"),
                html.P(f"ACE: {epa_display} (Global Rank: {epa_rank})", className="card-text"),
                dbc.Button("View", href=team_url, color="warning", className="mt-2"),
            ]
        )
    )

    return dbc.Card(
        card_elems,
        className="m-2 shadow",
        style={
            "width": "18rem",
            "height": "26rem",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "start",
            "alignItems": "stretch",
        },
    )

def parse_event_key(event_key):
    if len(event_key) >= 5 and event_key[:4].isdigit():
        return int(event_key[:4]), event_key[4:]
    return None, event_key

@callback(
    Output("event-favorites-store", "data", allow_duplicate=True),
    Output("favorite-event-alert", "children", allow_duplicate=True),
    Output("favorite-event-alert", "is_open", allow_duplicate=True),
    Input("url", "pathname"),
    Input("favorite-event-btn", "n_clicks"),
    State("event-favorites-store", "data"),
    prevent_initial_call=True
)
def handle_event_favorite(pathname, n_clicks, store_data):

    if "user_id" not in session:
        raise PreventUpdate

    user_id = session["user_id"]
    event_key = pathname.strip("/").split("/")[-1]
    store_data = store_data or []

    # Case: user clicked star
    if ctx.triggered_id == "favorite-event-btn":
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM saved_items WHERE user_id = %s AND item_type = 'event' AND item_key = %s", (user_id, event_key))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("DELETE FROM saved_items WHERE user_id = %s AND item_type = 'event' AND item_key = %s", (user_id, event_key))
            conn.commit()
            conn.close()
            new_store = [k for k in store_data if k != event_key]
            return new_store, "Removed from favorites", True
        else:
            cursor.execute("INSERT INTO saved_items (user_id, item_type, item_key) VALUES (%s, 'event', %s)", (user_id, event_key))
            conn.commit()
            conn.close()
            return store_data + [event_key], "Added to favorites", True

    # Case: just loading the page (preload from DB)
    if ctx.triggered_id == "url":
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM saved_items WHERE user_id = %s AND item_type = 'event' AND item_key = %s", (user_id, event_key))
        favorited = cursor.fetchone()
        conn.close()
        return ([event_key] if favorited else []), dash.no_update, dash.no_update

    raise PreventUpdate

@callback(
    Output("favorite-event-btn", "children"),
    Input("event-favorites-store", "data"),
    State("url", "pathname")
)
def update_button_icon(favorites, pathname):
    event_key = pathname.strip("/").split("/")[-1]
    if favorites and event_key in favorites:
        return "★"
    return "☆"

@app.callback(
    Output("data-display-container", "children"),
    Input("event-data-tabs", "active_tab"),
    State("store-rankings", "data"),
    State("store-oprs", "data"),
    State("store-event-epa", "data"),
    State("store-event-teams", "data"),
    State("store-event-matches", "data"),
    State("store-event-year", "data"), 
)
def update_display(active_tab, rankings, oprs, epa_data, event_teams, event_matches, event_year):
    if not active_tab:
        return dbc.Alert("Select a data category above.", color="info")

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

    event_team_keys = {t["tk"] for t in event_teams}
    full_teams = [t for t in TEAM_DATABASE.get(event_year, {}).values() if t.get("team_number") in event_team_keys]


    extract_valid = lambda key: [t[key] for t in full_teams if key in t and t[key] is not None]

    overall_percentiles = compute_percentiles(extract_valid("epa"))
    auto_percentiles = compute_percentiles(extract_valid("auto_epa"))
    teleop_percentiles = compute_percentiles(extract_valid("teleop_epa"))
    endgame_percentiles = compute_percentiles(extract_valid("endgame_epa"))

    percentiles_dict = {
        "ACE": overall_percentiles,
        "Auto ACE": auto_percentiles,
        "Teleop ACE": teleop_percentiles,
        "Endgame ACE": endgame_percentiles,
    }
        
    style_data_conditional = get_epa_styling(percentiles_dict)

    # === Rankings Tab ===
    if active_tab == "rankings":
        data_rows = []
        for team_num, rank_info in (rankings or {}).items():
            tstr = str(team_num)

            epa_rank = epa_data.get(tstr, {}).get("rank", "N/A")
            epa_display = epa_data.get(tstr, {}).get("epa_display", "N/A")

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
                "ACE Rank": epa_rank,
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
        ])

    # === OPRs Tab ===
    elif active_tab == "oprs":
        data = []
        year_teams = TEAM_DATABASE.get(event_year, {})
    
        for team_num, opr_val in (oprs.get("oprs") or {}).items():
            tnum_str = str(team_num)
            team_data = year_teams.get(int(team_num), {})
            nickname = team_data.get("nickname", "Unknown")
            epa_rank = epa_data.get(tnum_str, {}).get("rank", "N/A")
    
            data.append({
                "Team": f"[{tnum_str} | {nickname}](/team/{tnum_str})",
                "OPR": opr_val,
                "ACE Rank": epa_rank,
                "ACE": epa_data.get(tnum_str, {}).get("epa", "N/A"),
            })
    
        data.sort(key=lambda x: x["OPR"], reverse=True)
        for i, row in enumerate(data):
            row["OPR Rank"] = i + 1
    
        columns = [
            {"name": "OPR Rank", "id": "OPR Rank"},
            {"name": "Team", "id": "Team", "presentation": "markdown"},
            {"name": "OPR", "id": "OPR"},
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
        ]
    
        return dash_table.DataTable(
            columns=columns,
            data=data,
            page_size=10,
            style_table=common_style_table,
            style_header=common_style_header,
            style_cell=common_style_cell,
            style_data_conditional=style_data_conditional
        )

    # === Teams Tab ===
    elif active_tab == "teams":

        # Sort by global ACE rank
        sorted_teams = sorted(
            event_teams,
            key=lambda t: safe_int(epa_data.get(str(t.get("tk")), {}).get("rank")),
        )
        top_3 = sorted_teams[:3]

        spotlight_cards = [
            dbc.Col(create_team_card_spotlight(t, epa_data, event_year), width="auto")
            for t in top_3
        ]
        spotlight_layout = dbc.Row(spotlight_cards, className="justify-content-center mb-4")

        rows = []
        for t in event_teams:
            tnum = t.get("tk")
            tstr = str(tnum)
            full_data = next((team for team in full_teams if team.get("team_number") == tnum), {})
            epa_rank = epa_data.get(tstr, {}).get("rank", "N/A")
            epa_disp = epa_data.get(tstr, {}).get("epa_display", "N/A")

            rows.append({
                "ACE Rank": epa_rank,
                "ACE": epa_data.get(tstr, {}).get("epa", "N/A"),
                "Auto ACE": round(full_data.get("auto_epa", 0), 2),
                "Teleop ACE": round(full_data.get("teleop_epa", 0), 2),
                "Endgame ACE": round(full_data.get("endgame_epa", 0), 2),
                "Team": f"[{tstr} | {t.get('nn', 'Unknown')}](/team/{tstr})",
                "Location": ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown",
            })

        rows.sort(key=lambda r: safe_int(r["ACE Rank"]))

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
        ])


    # === Matches Tab ===
    elif active_tab == "matches":
        team_filter_options = [
            {"label": f"{t['tk']} - {t.get('nn', '')}", "value": str(t["tk"])}
            for t in event_teams
        ]

        return html.Div([
            html.Div(
                [
                    html.Label("Filter by Team:", style={"fontWeight": "bold"}),
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
        ])

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
            marker=dict(size=node_size, color=node_color, line=dict(width=1, color="black")),
            hoverinfo="text"
        ))
        fig.update_layout(
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-2.5, 2.5]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            height=1600,
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
            dcc.Graph(figure=fig),
        ])

    return dbc.Alert("No data available.", color="warning")

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
        info = epa_data.get(t_key.strip(), {})
        return {
            "epa": info.get("epa", 0),
            "confidence": info.get("confidence", 0) / 100,  # normalize to 0–1
            "consistency": info.get("consistency", 0),      # already normalized
        }

    def effective_epa(team_infos):
        if not team_infos:
            return 0
        
        weighted_epas = []
        for t in team_infos:
            epa = t["epa"]
            conf = t["confidence"]
            cons = t["consistency"]
            reliability = 0.5 * conf + 0.5 * cons
            weight = 0.5 + 0.5 * reliability
            weighted_epas.append(epa * weight)
        
        return mean(weighted_epas)
    
    def predict_win_probability(red_info, blue_info, boost=1.1):
        red_eff = effective_epa(red_info)
        blue_eff = effective_epa(blue_info)
        reliability = mean([t["confidence"] for t in red_info + blue_info]) if red_info + blue_info else 0
    
        if red_eff + blue_eff == 0:
            return 0.5, 0.5
    
        diff = red_eff - blue_eff
        scale = boost * (0.06 + 0.3 * (1 - reliability))
        p_red = 1 / (1 + math.exp(-scale * diff))
        p_red = max(0.15, min(0.90, p_red))  # clip for calibration
        return p_red, 1 - p_red


    
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
                pred_str = "N/A"
            else:
                pred_str = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"


            yid = match.get("yt")
            video_link = f"[Watch](https://www.youtube.com/watch?v={yid})" if yid else "N/A"

            rows.append({
                "Video": video_link,
                "Match": label,
                "Red Teams": format_teams_markdown(red_str),
                "Blue Teams": format_teams_markdown(blue_str),
                "Red Score": red_score,
                "Blue Score": blue_score,
                "Winner": winner.title() if winner else "N/A",
                "Prediction": pred_str,
            })
        return rows

    qual_data = build_match_rows(qual_matches)
    playoff_data = build_match_rows(playoff_matches)

    match_columns = [
        {"name": "Video", "id": "Video", "presentation": "markdown"},
        {"name": "Match", "id": "Match"},
        {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
        {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
        {"name": "Red Score", "id": "Red Score"},
        {"name": "Blue Score", "id": "Blue Score"},
        {"name": "Winner", "id": "Winner"},
        {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
    ]

    row_style = [
        {"if": {"filter_query": '{Winner} = "Red"'}, "backgroundColor": "#ffe6e6"},
        {"if": {"filter_query": '{Winner} = "Blue"'}, "backgroundColor": "#e6f0ff"},
    ]

    style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "color": "var(--text-tertiary) !important"}
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
        "backgroundColor": "var(--card-bg)", 
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

    return html.Div(qual_table + playoff_table)

def epa_legend_layout():
    color_map = [
        ("≥ 99%", "#8e24aa"),   # Deep Purple
        ("≥ 97%", "#6a1b9a"),
        ("≥ 95%", "#3949ab"),
        ("≥ 93%", "#1565c0"),
        ("≥ 91%", "#1e88e5"),
        ("≥ 89%", "#2e7d32"),
        ("≥ 85%", "#43a047"),
        ("≥ 80%", "#c0ca33"),
        ("≥ 75%", "#ffb300"),
        ("≥ 65%", "#f9a825"),
        ("≥ 55%", "#fb8c00"),
        ("≥ 40%", "#e53935"),
        ("≥ 25%", "#b71c1c"),
        ("≥ 10%", "#7b0000"),
        ("< 10%", "#4d0000"),
    ]
    blocks = [
        html.Div(
            label,
            style={
                "backgroundColor": color,
                "color": "white",
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
                style={"objectFit": "contain", "height": "150px", "padding": "0.5rem", "backgroundColor": "#fff"}
            ),
            html.Div([
                dbc.CardBody([
                    html.H5(f"#{team_number} | {nickname}", className="card-title", style={"fontSize": "1.1rem"}),
                    html.P(f"Location: {location}", className="card-text", style={"fontSize": "0.9rem"}),
                    html.P(f"ACE: {epa_display} (Global Rank: {rank})", className="card-text", style={"fontSize": "0.9rem"}),
                    dbc.Button("View", href=f"/team/{team_number}/{year}", color="warning", className="mt-auto"),
                ], style={"display": "flex", "flexDirection": "column", "flexGrow": "1"})
            ], style={"position": "relative"})
        ],
        className="m-2 shadow",
        style={
            "width": "18rem", "height": "22rem",
            "display": "flex", "flexDirection": "column",
            "justifyContent": "start", "alignItems": "stretch",
            "borderRadius": "10px"
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
    )

    country_dropdown = dcc.Dropdown(
        id="country-dropdown",
        options=COUNTRIES,
        value="All",
        clearable=False,
        placeholder="Select Country",
        style={"width": "100%"},
    )

    state_dropdown = dcc.Dropdown(
        id="state-dropdown",
        options=[{"label": "All States", "value": "All"}],
        value="All",
        clearable=False,
        placeholder="Select State/Province",
        style={"width": "100%"},
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
    )
    percentile_toggle = dbc.Checklist(
        options=[{"label": "Filter Percentiles", "value": "filtered"}],
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
        style={"width": "130px"}
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
        style={"width": "130px"}
    )

    axis_dropdowns = html.Div(
        id="axis-dropdown-container",
        children=[
            dbc.Row([
                dbc.Col(html.Label("X Axis:"), width="auto"),
                dbc.Col(x_axis_dropdown, width=3),
                dbc.Col(html.Label("Y Axis:"), width="auto"),
                dbc.Col(y_axis_dropdown, width=3),
            ], className="align-items-center")
        ],
        style={"display": "none", "marginBottom": "5px", "marginTop": "0px"}
    )

    search_input = dbc.Input(
        id="search-bar",
        placeholder="Search",
        type="text",
        className="mb-3",
        style={"width": "100%"},
    )

    filters_row = html.Div(
        dbc.Row(
            [
                dbc.Col(teams_year_dropdown, sm=2),
                dbc.Col(country_dropdown, sm=2),
                dbc.Col(state_dropdown, sm=2),
                dbc.Col(district_dropdown, sm=2),
                dbc.Col(percentile_toggle, sm=2),
                dbc.Col(search_input, sm=2),
            ],
            className="gx-2 gy-2 justify-content-center",
            style={"margin": "0 auto", "maxWidth": "1000px"},
        ),
        style={
            "top": "60px",
            "zIndex": 10,
            "backgroundColor": "transparent",
            "padding": "6px 8px",
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
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "none", "backgroundColor": "var(--card-bg)"},
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

    tabs = dbc.Tabs([
        dbc.Tab(label="Insights", tab_id="table-tab"),
        dbc.Tab(label="Avatars", tab_id="avatars-tab"),
        dbc.Tab(label="Bubble Chart", tab_id="bubble-map-tab"),
    ], id="teams-tabs", active_tab="table-tab", className="mb-3")

    content = html.Div(id="teams-tab-content", children=[
        html.Div(id="teams-table-container", children=[teams_table]),
        html.Div(id="avatar-gallery", className="d-flex flex-wrap justify-content-center", style={"gap": "5px", "padding": "1rem", "display": "none"}),
        dcc.Graph(id="bubble-map", style={"display": "none", "height": "700px"})
    ])

    return html.Div(
        [
            dcc.Location(id="teams-url", refresh=False),
            dcc.Store(id="user-session"),
            topbar(),
            dbc.Container([
                dbc.Row(id="top-teams-container", className="gx-4 gy-4 justify-content-center mb-5", justify="center"),
                filters_row,
                axis_dropdowns,
                epa_legend_layout(),
                tabs,
                content,
            ], style={"padding": "10px", "maxWidth": "1200px", "margin": "0 auto"}),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )

@callback(
    [
        Output("teams-table", "data"),
        Output("state-dropdown", "options"),
        Output("top-teams-container", "children"),
        Output("teams-table-container", "style"),
        Output("avatar-gallery", "children"),
        Output("avatar-gallery", "style"),
        Output("bubble-map", "figure"),
        Output("bubble-map", "style"),
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
    from urllib.parse import parse_qs, urlencode
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
    all_teams, epa_ranks = load_teams_and_compute_epa_ranks(selected_year)
    teams_data = all_teams.copy()

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
    global_data, _ = load_teams_and_compute_epa_ranks(selected_year)
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
    elif active_tab == "bubble-map-tab":
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
            textfont=dict(size=9, color="black"),
            textposition="top center",
            hovertext=df.loc[~df["is_match"], "hover"],
            hoverinfo="text",
        ))
        fig.add_trace(go.Scatter(
            x=df.loc[df["is_match"], "x"],
            y=df.loc[df["is_match"], "y"],
            mode="markers+text",
            marker=dict(size=8, color="rgba(255,0,0,0.6)", line=dict(width=2, color="black")),
            text=df.loc[df["is_match"], "label"],
            textfont=dict(size=10, color="darkred"),
            textposition="top center",
            hovertext=df.loc[df["is_match"], "hover"],
            hoverinfo="text",
        ))

        fig.update_layout(
            title="EPA Breakdown Bubble Chart",
            xaxis_title=x_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
            yaxis_title=y_axis.replace("_epa", " ACE").replace("epa", "Total EPA").replace("+", " + "),
            margin=dict(l=40, r=40, t=40, b=40),
            plot_bgcolor="white",
            showlegend=False,
        )
        return table_rows, state_options, top_teams_layout, {"display": "none"}, [], {"display": "none"}, fig, {"display": "block"}, query_string, style_data_conditional

    return table_rows, state_options, top_teams_layout, {"display": "block"}, [], {"display": "none"}, go.Figure(), {"display": "none"}, query_string, style_data_conditional

@callback(
    Output("teams-year-dropdown", "value"),
    Output("country-dropdown", "value"),
    Output("state-dropdown", "value"),
    Output("district-dropdown", "value"),
    Output("x-axis-dropdown", "value"),
    Output("y-axis-dropdown", "value"),
    Output("percentile-toggle", "value"),  # ← ADD THIS
    Input("teams-url", "href"),
    prevent_initial_call=True,
)
def apply_url_filters(href):
    if not href or "?" not in href:
        return 2025, "All", "All", "All", "teleop_epa", "auto+endgame"

    query = href.split("?", 1)[1]
    params = parse_qs(query)

    def get_param(name, default):
        val = params.get(name, [default])
        if isinstance(val, list):
            val = val[0]
        return val if val not in ("[]", "['']") else default
    
        

    return (
        int(get_param("year", 2025)),
        get_param("country", "All"),
        get_param("state", "All"),
        get_param("district", "All"),
        get_param("x", "teleop_epa"),
        get_param("y", "auto+endgame"),
        ["filtered"] if get_param("percentile", "") == "filtered" else [],
    )

@callback(
    Output("axis-dropdown-container", "style"),
    Input("teams-tabs", "active_tab")
)
def toggle_axis_dropdowns(active_tab):
    if active_tab == "bubble-map-tab":
        return {"display": "block", "marginBottom": "15px"}
    return {"display": "none"}


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
            fluid=True
        ),
        footer,
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
    ])

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
    year_data = TEAM_DATABASE.get(selected_year)

    # --- TEAM SEARCH ---
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

    # --- EVENT SEARCH ---
    matching_events = []
    for event in EVENTS_DATABASE:
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

def wrap_with_toast_or_star(content):
    return html.Div([
        content,
        universal_profile_icon_or_toast()
    ])

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    path_parts = pathname.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "team":
        team_number = path_parts[1]
        year = path_parts[2] if len(path_parts) > 2 else None
        return wrap_with_toast_or_star(team_layout(team_number, year))
    
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

    return wrap_with_toast_or_star(home_layout)

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
        const savedTheme = localStorage.getItem('theme') || 'light';
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
    Input("url", "pathname"),
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))  
    app.run(host="0.0.0.0", port=port, debug=False)

