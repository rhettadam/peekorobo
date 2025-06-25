import numpy as np
import math
import os

import dash_bootstrap_components as dbc
from dash import html
from flask import session
from datagather import get_pg_connection
from datetime import datetime, date

#### PREDICTIONS

def effective_epa(team_infos):
        if not team_infos:
            return 0
        
        weighted_epas = []
        for t in team_infos:
            epa = t["epa"]
            conf = t["confidence"]
            reliability = 1.0 * conf
            weighted_epas.append(epa * reliability)
        
        return np.mean(weighted_epas)
    
def predict_win_probability(red_info, blue_info, boost=1.1):
    red_eff = effective_epa(red_info)
    blue_eff = effective_epa(blue_info)
    reliability = np.mean([t["confidence"] for t in red_info + blue_info]) if red_info + blue_info else 0
    
    if red_eff + blue_eff == 0:
        return 0.5, 0.5
    
    diff = red_eff - blue_eff
    scale = boost * (0.06 + 0.3 * (1 - reliability))
    p_red = 1 / (1 + math.exp(-scale * diff))
    p_red = max(0.15, min(0.90, p_red))  # clip for calibration
    return p_red, 1 - p_red

def calculate_single_rank(team_data, selected_team):
    global_rank = 1
    country_rank = 1
    state_rank = 1

    # Extract selected team's information
    selected_epa = selected_team.get("epa", 0) or 0  # Ensure selected_epa is a number
    selected_country = (selected_team.get("country") or "").lower()
    selected_state = (selected_team.get("state_prov") or "").lower()

    for team in team_data:
        if team.get("team_number") == selected_team.get("team_number"):
            continue

        team_epa = team.get("epa", 0) or 0  # Default to 0 if ACE is None
        team_country = (team.get("country") or "").lower()
        team_state = (team.get("state_prov") or "").lower()

        # Global Rank
        if team_epa > selected_epa:
            global_rank += 1

        # Country Rank
        if team_country == selected_country and team_epa > selected_epa:
            country_rank += 1

        # State Rank
        if team_state == selected_state and team_epa > selected_epa:
            state_rank += 1

    return global_rank, country_rank, state_rank

### RANKINGS

def calculate_all_ranks(year, data):
    epa_info = {}

    year_data = data.get(year)
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

def get_epa_styling(percentiles_dict):
        color_map = [
            ("99", "#6a1b9a99"),   # Deep Purple
            ("97", "#8e24aa99"),   # Medium Purple
            ("95", "#3949ab99"),   # Indigo
            ("93", "#1565c099"),   # Blue
            ("91", "#1e88e599"),   # Sky Blue
            ("89", "#2e7d3299"),   # Medium Green
            ("85", "#43a04799"),   # Dark Green
            ("80", "#c0ca3399"),   # Lime
            ("75", "#ffb30099"),   # Yellow
            ("65", "#f9a82599"),   # Dark Yellow
            ("55", "#fb8c0099"),   # Orange
            ("40", "#e5393599"),   # Red
            ("25", "#b71c1c99"),   # Dark Red
            ("10", "#7b000099"),   # Maroon
            ("0",  "#4d000099"),   # Deep Maroon
        ]
    
        style_rules = []
    
        for col, percentiles in percentiles_dict.items():
            thresholds = {int(k): v for k, v in percentiles.items()}
    
            for i, (lower_str, color) in enumerate(color_map):
                lower = thresholds.get(int(lower_str), 0)
                upper = thresholds.get(int(color_map[i - 1][0]), float("inf")) if i > 0 else float("inf")
    
                style_rules.append({
                    "if": {
                        "filter_query": f"{{{col}}} >= {lower}" + (f" && {{{col}}} < {upper}" if upper < float("inf") else ""),
                        "column_id": col
                    },
                    "backgroundColor": color,
                    "color": "white !important",
                    "borderRadius": "6px",
                    "padding": "4px 6px",
                })
    
        return style_rules

def compute_percentiles(values):
    percentiles = ["99", "97", "95", "93", "91", "89", "85", "80", "75", "65", "55", "40", "25", "10", "0"]
    return {p: np.percentile(values, int(p)) for p in percentiles} if values else {p: 0 for p in percentiles}

### USERS

def sort_key(filename):
    name = filename.split('.')[0]
    return (0, int(name)) if name.isdigit() else (1, name.lower())

def get_username(user_id):
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0].title() if row else f"USER {user_id}"

def get_available_avatars():
        avatar_dir = "assets/avatars"
        return [f for f in os.listdir(avatar_dir) if f.endswith(".png")]

def get_contrast_text_color(hex_color):
        """Return black or white text color based on background brightness."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#000000" if brightness > 150 else "#FFFFFF"

def parse_event_key(event_key):
    if len(event_key) >= 5 and event_key[:4].isdigit():
        return int(event_key[:4]), event_key[4:]
    return None, event_key

def get_user_avatar(avatar_key):
    return f"/assets/avatars/{avatar_key}"

def get_user_epa_color(value, all_values):
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
            
def user_team_card(title, body_elements, delete_button=None):
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

def user_event_card(body_elements, delete_button=None):
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

### TEAMS

def team_link_with_avatar(team):
    team_number = team.get("team_number", "???")
    nickname = team.get("nickname", "")
    # Construct avatar URL, ensuring default if not found
    avatar_path = f"assets/avatars/{team_number}.png"
    avatar_url = f"/assets/avatars/{team_number}.png?v=1" if os.path.exists(avatar_path) else "/assets/avatars/stock.png"

    return html.A(
        html.Div([
            html.Img(src=avatar_url, style={
                "height": "20px",
                "width": "20px",
                "marginRight": "8px",
                "objectFit": "contain",
                "verticalAlign": "middle",
                "borderRadius": "50%", # Ensure avatars are round
            }),
            html.Span(f"{team_number} | {nickname}", style={
                # Remove inline color style from span
                # "color": text_color
            })
        ], style={
            "display": "flex",
            "alignItems": "center",
            # Remove inline color style from div
            # "color": "black"
        }),
        href=f"/team/{team_number}/2025",
        style={
            "textDecoration": "none",
            # Remove inline color style from A
            # "color": text_color
        }
    )

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
                        "backgroundColor": "var(--bg-secondary)",
                        "color": "var(--text-primary)",
                        "border": "1px solid #999"
                    }),
                    width=6
                ),
                dbc.Col(
                    dbc.Button("Register", href="/login", size="sm", color="warning", className="mt-2", style={
                        "width": "100%",
                        "backgroundColor": "var(--bg-secondary)",
                        "color": "var(--text-primary)",
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
        header_style={  # Added header_style
            "backgroundColor": "var(--card-bg)",
            "color": "var(--text-primary)"
        },
        style={
            "position": "fixed",
            "backgroundColor": "var(--card-bg)",
            "bottom": 20,
            "right": 20,
            "width": 250,
            "zIndex": 9999
        },
    )

def wrap_with_toast_or_star(content):
    return html.Div([
        content,
        universal_profile_icon_or_toast()
    ])

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

def event_card(event, favorited=False):
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
                    dbc.Button(
                        "View Details",
                        href=event_url,
                        color="warning",
                        outline=True,
                        className="custom-view-btn mt-3",
                    ),
                ]
            )
        ],
        className="mb-4 shadow",
        style={"width": "18rem", "height": "22rem", "margin": "10px"},
    )

def truncate_name(name, max_length=32):
        return name if len(name) <= max_length else name[:max_length-3] + '...'

