import numpy as np
import math
import os
from collections import defaultdict
import re
import pandas as pd

import dash_bootstrap_components as dbc
from dash import html
from flask import session
from datagather import DatabaseConnection
from datetime import datetime, date
import json

current_year = 2025

with open('data/week_ranges.json', 'r', encoding='utf-8') as f:
    WEEK_RANGES_BY_YEAR = json.load(f)

def get_event_week_label(event_start_date):
    """Return a string like 'Week 1', 'Week 6', 'Worlds', 'Pre-Season', or 'Off-Season' for the event date."""
    year = str(event_start_date.year)
    week_ranges = WEEK_RANGES_BY_YEAR.get(year)
    if not week_ranges:
        return None
    
    # Check if date is before the first week range (pre-season)
    if week_ranges:
        first_start = date.fromisoformat(week_ranges[0][0])
        if event_start_date < first_start:
            return "Pre-Season"
    
    # Check if date is within any week range
    for i, (start, end) in enumerate(week_ranges):
        start_dt = date.fromisoformat(start)
        end_dt = date.fromisoformat(end)
        if start_dt <= event_start_date <= end_dt:
            if i == len(week_ranges) - 1:
                return "Worlds"
            else:
                return f"Week {i+1}"
    
    # If we get here, the date is after all week ranges (off-season)
    return "Off-Season"

def apply_simple_filter(df, filter_query):
    # Only supports simple "{"col"} op value" and "and"/"or"
    if not filter_query:
        return df
    # Split on " && " for AND logic
    for clause in filter_query.split(" && "):
        m = re.match(r'\{(.+?)\} ([=><!]+) (.+)', clause)
        if m:
            col, op, val = m.groups()
            col = col.strip()
            val = val.strip().strip('"').strip("'")
            if op == '=':
                df = df[df[col].astype(str) == val]
            elif op == '!=':
                df = df[df[col].astype(str) != val]
            elif op == '>':
                df = df[pd.to_numeric(df[col], errors='coerce') > float(val)]
            elif op == '<':
                df = df[pd.to_numeric(df[col], errors='coerce') < float(val)]
            elif op == '>=':
                df = df[pd.to_numeric(df[col], errors='coerce') >= float(val)]
            elif op == '<=':
                df = df[pd.to_numeric(df[col], errors='coerce') <= float(val)]
            # Add more ops as needed
    return df

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
    
class AdaptivePredictor:
    """Learns from match outcomes to improve predictions within an event."""
    
    def __init__(self, learning_rate=0.05, decay_factor=0.99, min_matches=3):
        self.learning_rate = learning_rate
        self.decay_factor = decay_factor
        self.min_matches = min_matches
        self.event_predictions = defaultdict(list)  # event_key -> list of predictions
        self.team_adjustments = defaultdict(lambda: {"bias": 0.0, "matches": 0, "accuracy": 0.0})  # team -> adjustment data
        self.event_accuracy = defaultdict(list)  # event_key -> list of prediction accuracies
        
    def predict_with_learning(self, red_info, blue_info, event_key, match_key, boost=1.1):
        """Make prediction with learning from previous matches in the event."""
        # Get base prediction
        base_p_red, base_p_blue = predict_win_probability(red_info, blue_info, boost)
        
        # Only apply adjustments if we have enough learning data
        event_match_count = len(self.event_predictions[event_key])
        if event_match_count >= self.min_matches:
            adjusted_p_red, adjusted_p_blue = self._apply_team_adjustments(
                red_info, blue_info, base_p_red, base_p_blue, event_key
            )
        else:
            adjusted_p_red, adjusted_p_blue = base_p_red, base_p_blue
        
        # Store prediction for later learning
        self.event_predictions[event_key].append({
            "match_key": match_key,
            "red_teams": [t.get("team_number", 0) for t in red_info],
            "blue_teams": [t.get("team_number", 0) for t in blue_info],
            "predicted_red": adjusted_p_red,
            "predicted_blue": adjusted_p_blue,
            "base_red": base_p_red,
            "base_blue": base_p_blue,
            "red_epa": effective_epa(red_info),
            "blue_epa": effective_epa(blue_info)
        })
        
        return adjusted_p_red, adjusted_p_blue
    
    def _apply_team_adjustments(self, red_info, blue_info, base_p_red, base_p_blue, event_key):
        """Apply learned adjustments to base prediction."""
        red_teams = [t.get("team_number", 0) for t in red_info]
        blue_teams = [t.get("team_number", 0) for t in blue_info]
        
        # Calculate weighted adjustments based on team accuracy
        red_adjustment = 0.0
        red_weights = 0.0
        for team in red_teams:
            team_key = f"{event_key}_{team}"
            team_data = self.team_adjustments[team_key]
            if team_data["matches"] >= 2:  # Only use teams with enough data
                weight = min(team_data["accuracy"], 0.8)  # Cap weight at 0.8
                red_adjustment += team_data["bias"] * weight
                red_weights += weight
        
        blue_adjustment = 0.0
        blue_weights = 0.0
        for team in blue_teams:
            team_key = f"{event_key}_{team}"
            team_data = self.team_adjustments[team_key]
            if team_data["matches"] >= 2:  # Only use teams with enough data
                weight = min(team_data["accuracy"], 0.8)  # Cap weight at 0.8
                blue_adjustment += team_data["bias"] * weight
                blue_weights += weight
        
        # Apply weighted adjustments
        if red_weights > 0:
            red_adjustment /= red_weights
        if blue_weights > 0:
            blue_adjustment /= blue_weights
        
        # Conservative adjustment (max 10% change)
        max_adjustment = 0.1
        red_adjustment = np.clip(red_adjustment, -max_adjustment, max_adjustment)
        blue_adjustment = np.clip(blue_adjustment, -max_adjustment, max_adjustment)
        
        # Apply adjustments (clamp to reasonable bounds)
        adjusted_p_red = np.clip(base_p_red + red_adjustment - blue_adjustment, 0.1, 0.9)
        adjusted_p_blue = 1.0 - adjusted_p_red
        
        return adjusted_p_red, adjusted_p_blue
    
    def learn_from_outcome(self, event_key, match_key, actual_winner, red_score, blue_score):
        """Learn from match outcome to adjust future predictions."""
        # Find the prediction for this match
        prediction = None
        for pred in self.event_predictions[event_key]:
            if pred["match_key"] == match_key:
                prediction = pred
                break
        
        if not prediction:
            return  # No prediction found for this match
        
        # Calculate prediction error
        predicted_red = prediction["predicted_red"]
        actual_red_win = 1.0 if actual_winner == "red" else 0.0
        
        error = actual_red_win - predicted_red
        
        # Calculate learning rate that decreases with more matches in the event
        event_match_count = len(self.event_predictions[event_key])
        current_learning_rate = self.learning_rate * (self.decay_factor ** (event_match_count - 1))
        
        # Update team adjustments with accuracy tracking
        red_teams = prediction["red_teams"]
        blue_teams = prediction["blue_teams"]
        
        # Calculate prediction accuracy for this match
        prediction_accuracy = 1.0 - abs(error)
        
        # Adjust red alliance teams
        for team in red_teams:
            team_key = f"{event_key}_{team}"
            team_data = self.team_adjustments[team_key]
            
            # Update bias
            team_data["bias"] += current_learning_rate * error
            team_data["matches"] += 1
            
            # Update accuracy (exponential moving average)
            alpha = 0.3
            team_data["accuracy"] = alpha * prediction_accuracy + (1 - alpha) * team_data["accuracy"]
        
        # Adjust blue alliance teams (opposite direction)
        for team in blue_teams:
            team_key = f"{event_key}_{team}"
            team_data = self.team_adjustments[team_key]
            
            # Update bias
            team_data["bias"] -= current_learning_rate * error
            team_data["matches"] += 1
            
            # Update accuracy (exponential moving average)
            alpha = 0.3
            team_data["accuracy"] = alpha * prediction_accuracy + (1 - alpha) * team_data["accuracy"]
        
        # Track event-level accuracy
        self.event_accuracy[event_key].append(prediction_accuracy)
    
    def get_prediction_confidence(self, event_key):
        """Get confidence in predictions based on learning progress and accuracy."""
        event_predictions = self.event_predictions[event_key]
        if not event_predictions:
            return 0.5  # No learning yet
        
        # Calculate average accuracy for this event
        accuracies = self.event_accuracy.get(event_key, [])
        if accuracies:
            avg_accuracy = np.mean(accuracies[-5:])  # Last 5 matches
        else:
            avg_accuracy = 0.5
        
        # Confidence increases with more matches and higher accuracy
        match_count = len(event_predictions)
        base_confidence = 0.5 + 0.1 * min(match_count, 10)  # Cap at 10 matches
        accuracy_boost = avg_accuracy * 0.3  # Up to 30% boost from accuracy
        
        return min(0.9, base_confidence + accuracy_boost)
    
    def reset_event(self, event_key):
        """Reset learning for a specific event."""
        if event_key in self.event_predictions:
            del self.event_predictions[event_key]
        if event_key in self.event_accuracy:
            del self.event_accuracy[event_key]
        
        # Remove team adjustments for this event
        keys_to_remove = [k for k in self.team_adjustments.keys() if k.startswith(f"{event_key}_")]
        for key in keys_to_remove:
            del self.team_adjustments[key]

# Global adaptive predictor instance
adaptive_predictor = AdaptivePredictor(learning_rate=0.05, decay_factor=0.99, min_matches=3)  # Conservative learning

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

def predict_win_probability_adaptive(red_info, blue_info, event_key, match_key, boost=1.1):
    """Enhanced prediction that learns from previous matches in the event."""
    return adaptive_predictor.predict_with_learning(red_info, blue_info, event_key, match_key, boost)

def learn_from_match_outcome(event_key, match_key, actual_winner, red_score, blue_score):
    """Learn from a completed match to improve future predictions."""
    adaptive_predictor.learn_from_outcome(event_key, match_key, actual_winner, red_score, blue_score)

def get_event_prediction_confidence(event_key):
    """Get confidence level for predictions in a specific event."""
    return adaptive_predictor.get_prediction_confidence(event_key)

def reset_event_learning(event_key):
    """Reset learning for a specific event (useful for testing or new events)."""
    adaptive_predictor.reset_event(event_key)

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

            # Special subtle styling for confidence: only accentuate below 50th percentile
            if col.lower() == "confidence":
                # Use 50th percentile as threshold
                p50 = thresholds.get(50) or thresholds.get(55) or 0
                style_rules.append({
                    "if": {
                        "filter_query": f"{{{col}}} < {p50}",
                        "column_id": col
                    },
                    "backgroundColor": "#e5393575",  
                    "borderRadius": "6px",
                    "padding": "4px 6px",
                })
                continue  # Skip normal color map for confidence

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
    return {p: np.percentile(values, int(p)) for p in percentiles} if len(values) > 0 else {p: 0 for p in percentiles}

### USERS

def sort_key(filename):
    name = filename.split('.')[0]
    return (0, int(name)) if name.isdigit() else (1, name.lower())

def get_username(user_id):
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
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
            
def user_team_card(title, body_elements, delete_button=None, team_number=None):
        # Load team colors if team_number is provided
        gradient_style = {}
        if team_number:
            try:
                import json
                with open('data/team_colors.json', 'r') as f:
                    team_colors = json.load(f)
                
                team_colors_data = team_colors.get(str(team_number), {})
                primary_color = team_colors_data.get('primary', '#1566ac')
                secondary_color = team_colors_data.get('secondary', '#c0b8bb')
                
                gradient_style = {
                    "background": f"linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%)",
                    "color": "white",
                    "padding": "10px 15px",
                    "borderRadius": "8px 8px 0 0",
                    "margin": "-15px -15px 15px -15px"  # Extend to card edges
                }
            except Exception as e:
                print(f"Error loading team colors for team {team_number}: {e}")
                gradient_style = {
                    "background": "linear-gradient(135deg, #1566ac 0%, #c0b8bb 100%)",
                    "color": "white",
                    "padding": "10px 15px",
                    "borderRadius": "8px 8px 0 0",
                    "margin": "-15px -15px 15px -15px"
                }
        
        return dbc.Card(
            dbc.CardBody([
                html.Div([
                    html.Div(title, style={
                        "fontWeight": "bold",
                        "fontSize": "1.1rem",
                        "textDecoration": "underline",
                        "color": gradient_style.get("color", "#007bff") if gradient_style else "#007bff",
                        "cursor": "pointer"
                    }),
                    delete_button if delete_button else None
                ], style={
                    "display": "flex", 
                    "justifyContent": "space-between", 
                    "alignItems": "center",
                    **gradient_style
                }),
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

### TEAMS

def team_link_with_avatar(team):
    team_number = team.get("team_number", "???")
    nickname = team.get("nickname", "")
    last_year = team.get("last_year", None)
    # Construct avatar URL, ensuring default if not found
    avatar_path = f"assets/avatars/{team_number}.png"
    avatar_url = f"/assets/avatars/{team_number}.png?v=1" if os.path.exists(avatar_path) else "/assets/avatars/stock.png"

    # Use last_year for the link, fallback to current_year if missing
    year_for_link = last_year if last_year is not None else current_year

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
        href=f"/team/{team_number}/{year_for_link}",
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
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT avatar_key FROM users WHERE id = %s", (user_id,))
                row = cursor.fetchone()
                avatar_key = row[0] if row and row[0] else "stock"
            except Exception as e:
                print(f"Error fetching avatar: {e}")
                avatar_key = "stock.png"

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
            "width": 215,
            "height": 170,
            "zIndex": 9999
        },
    )

def get_week_number(start_date):
    year = str(start_date.year)
    week_ranges = WEEK_RANGES_BY_YEAR.get(year)
    if not week_ranges:
        return None
    for i, (start, end) in enumerate(week_ranges):
        start_dt = date.fromisoformat(start)
        end_dt = date.fromisoformat(end)
        if start_dt <= start_date <= end_dt:
            return i
    return None

def event_card(event, favorited=False):
    event_key = event["k"]
    event_url = f"https://www.peekorobo.com/event/{event_key}"
    location = f"{event.get('c','')}, {event.get('s','')}, {event.get('co','')}"
    start = event.get("sd", "N/A")
    end = event.get("ed", "N/A")
    event_type = event.get("et", "N/A")

    # Add week label
    week_label = None
    if start and start != "N/A":
        try:
            week_label = get_event_week_label(date.fromisoformat(start))
        except Exception:
            week_label = None

    # Format dates for display
    start_display = format_human_date(start) if start and start != "N/A" else start
    end_display = format_human_date(end) if end and end != "N/A" else end

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H5(event.get("n", "Unknown Event"), className="card-title mb-3"),
                    html.P(location, className="card-text"),
                    html.P(f"{start_display} - {end_display}", className="card-text"),
                    html.P(f"{week_label} {event_type}" if week_label else f"{event_type}", className="card-text"),
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

def get_event_learning_stats(event_key):
    """Get learning statistics for a specific event."""
    event_predictions = adaptive_predictor.event_predictions.get(event_key, [])
    team_adjustments = adaptive_predictor.team_adjustments
    event_accuracies = adaptive_predictor.event_accuracy.get(event_key, [])
    
    # Count teams with adjustments for this event
    event_teams = [k for k in team_adjustments.keys() if k.startswith(f"{event_key}_")]
    teams_with_adjustments = len(event_teams)
    
    # Calculate average adjustment magnitude
    avg_adjustment = 0.0
    if event_teams:
        adjustments = [team_adjustments[team]["bias"] for team in event_teams]
        avg_adjustment = np.mean(np.abs(adjustments))
    
    # Calculate average accuracy
    avg_accuracy = np.mean(event_accuracies) if event_accuracies else 0.5
    
    return {
        "matches_processed": len(event_predictions),
        "teams_with_adjustments": teams_with_adjustments,
        "average_adjustment": avg_adjustment,
        "average_accuracy": avg_accuracy,
        "prediction_confidence": get_event_prediction_confidence(event_key),
        "learning_active": len(event_predictions) >= adaptive_predictor.min_matches
    }

def get_prediction_difference(event_key, match_key):
    """Get the difference between base and adaptive predictions for debugging."""
    return adaptive_predictor.get_prediction_difference(event_key, match_key)

def format_human_date(date_str):
    """Convert 'YYYY-MM-DD' to 'Month D, YYYY' (e.g., 'April 2, 2025'). Returns '' if invalid."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %-d, %Y") if os.name != 'nt' else dt.strftime("%B %#d, %Y")
    except Exception:
        return ""
    
def is_western_pennsylvania_city(city_name):
    """
    Check if a city is in western Pennsylvania (west of Harrisburg).
    Returns True if the city is in western Pennsylvania, False otherwise.
    """
    if not city_name:
        return False
    
    city_lower = city_name.lower().strip()
    
    # Major western Pennsylvania cities (west of Harrisburg)
    western_pa_cities = {
        # Pittsburgh area
        "pittsburgh", "allegheny", "bethel park", "monroeville", "mckeesport", "new kensington",
        "greensburg", "latrobe", "jeannette", "connellsville", "uniontown", "washington",
        "canonsburg", "mcmurray", "peters township", "upper st. clair", "mt. lebanon",
        "brentwood", "baldwin", "whitehall", "dormont", "carnegie", "robinson township", "cranberry township", "baden",
        "brownsville", "vanderbilt", "monessen", "murrysville", "bridgeville",
        
        # Erie area
        "erie", "meadville", "oil city", "franklin", "venango", "crawford",
        
        # Johnstown area
        "johnstown", "ebensburg", "cambria", "somerset", "bedford", "blair",
        
        # Altoona area
        "altoona", "huntingdon", "clearfield", "centre", "state college", "bellefonte",
        
        # Other western cities
        "butler", "indiana", "armstrong", "westmoreland", "fayette", "greene",
        "lawrence", "mercer", "crawford", "warren", "mckean", "elk", "forest",
        "jefferson", "clarion", "venango", "butler county", "indiana county",
        
        # Additional cities that are clearly west of Harrisburg
        "duquesne", "braddock", "swissvale", "edgewood", "forest hills", "wilkinsburg",
        "east pittsburgh", "turtle creek", "rankin", "homestead", "west homestead",
        "munhall", "white oak", "north versailles", "plum", "oakmont", "verona",
        "aspinwall", "fox chapel", "shaler", "ross", "mccandless", "franklin park",
        "marshall", "pine", "richland", "hampton", "bradford woods", "gibsonia",
        "wexford", "cranberry", "mars", "valencia", "butler", "hermitage", "sharon",
        "farrell", "new castle", "ellwood city", "beaver", "beaver falls", "aliquippa",
        "monaca", "rochester", "new brighton", "beaver county", "lawrence county",
        "mercer county", "crawford county", "erie county", "warren county",
        "mckean county", "elk county", "forest county", "jefferson county",
        "clarion county", "venango county", "butler county", "indiana county",
        "armstrong county", "westmoreland county", "fayette county", "greene county", "chambersburg",
        "marion center", "emlenton"
    }
    
    return city_lower in western_pa_cities
