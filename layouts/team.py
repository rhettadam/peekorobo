from datagather import get_team_avatar, load_data
from dash import html,dash_table
import dash_bootstrap_components as dbc
import json
from collections import defaultdict
from layouts.topbar import topbar, footer    

def calculate_ranks(team_data, selected_team):
    global_rank = 1
    country_rank = 1
    state_rank = 1

    # Define your preferred weights
    WEIGHTS = {
        "auto_epa": 0.4,
        "teleop_epa": 0.5,
        "endgame_epa": 0.1,
    }

    # Compute selected team weighted EPA
    selected_epa = (
        (selected_team.get("auto_epa") or 0) * WEIGHTS["auto_epa"] +
        (selected_team.get("teleop_epa") or 0) * WEIGHTS["teleop_epa"] +
        (selected_team.get("endgame_epa") or 0) * WEIGHTS["endgame_epa"]
    )

    selected_country = (selected_team.get("country") or "").lower()
    selected_state = (selected_team.get("state_prov") or "").lower()

    for team in team_data.values():
        if team.get("team_number") == selected_team.get("team_number"):
            continue

        team_epa = (
            (team.get("auto_epa") or 0) * WEIGHTS["auto_epa"] +
            (team.get("teleop_epa") or 0) * WEIGHTS["teleop_epa"] +
            (team.get("endgame_epa") or 0) * WEIGHTS["endgame_epa"]
        )

        team_country = (team.get("country") or "").lower()
        team_state = (team.get("state_prov") or "").lower()

        if team_epa > selected_epa:
            global_rank += 1
            if team_country == selected_country:
                country_rank += 1
            if team_state == selected_state:
                state_rank += 1

    return global_rank, country_rank, state_rank

def build_recent_events_section(team_key, team_number, epa_data, performance_year, is_history):
    from data_store import TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_RANKINGS, EVENT_AWARDS    
    selected_year_data = TEAM_DATABASE.get(performance_year, {})
    selected_team = selected_year_data.get(team_number)
    
    epa_data = epa_data or {}
    recent_rows = []
    year = performance_year 

    for event_key, event in EVENT_DATABASE.get(year, {}).items():
        event_teams = EVENT_TEAMS.get(year, {}).get(event_key, [])
        if not any(t["tk"] == team_number for t in event_teams):
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
                html.Span(f"/{total_teams}", style={"color": "black", "fontWeight": "normal"})
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
        matches = [m for m in matches if str(team_number) in (m.get("rt") or "") or str(team_number) in (m.get("bt") or "")]

        def build_match_rows(matches):
            rows = []
            comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}
            matches.sort(key=lambda m: (comp_level_order.get(m.get("cl", ""), 99), m.get("mn", 9999)))
        
            def format_team_list(team_str):
                return ", ".join(f"[{t}](/team/{t})" for t in team_str.split(",") if t.strip().isdigit())

            def sum_epa(team_str):
                return sum(epa_data.get(t.strip(), {}).get("epa", 0) for t in team_str.split(",") if t.strip().isdigit())

        
            for match in matches:
                red_str = match.get("rt", "")
                blue_str = match.get("bt", "")
                red_score = match.get("rs", 0)
                blue_score = match.get("bs", 0)
                label = match.get("cl", "").upper() + " " + str(match.get("mn", ""))
        
                red_epa = sum_epa(red_str)
                blue_epa = sum_epa(blue_str)
        
                if red_epa + blue_epa > 0:
                    p_red = red_epa / (red_epa + blue_epa)
                    p_blue = 1 - p_red
                    prediction = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"
                else:
                    prediction = "N/A"
        
                winner = match.get("wa", "N/A").title()
                youtube_id = match.get("yt")
                video_link = f"[Watch](https://youtube.com/watch?v={youtube_id})" if youtube_id else "N/A"
        
                rows.append({
                    "Video": video_link,
                    "Match": label,
                    "Red Teams": format_team_list(red_str),
                    "Blue Teams": format_team_list(blue_str),
                    "Red Score": red_score,
                    "Blue Score": blue_score,
                    "Winner": winner,
                    "Prediction": prediction,
                    "rowColor": "#ffe6e6" if winner == "Red" else "#e6f0ff" if winner == "Blue" else "white"
                })
        
            return rows


        match_rows = build_match_rows(matches)

        table = dash_table.DataTable(
            columns=[
                {"name": "Video", "id": "Video", "presentation": "markdown"},
                {"name": "Match", "id": "Match"},
                {"name": "Red Teams", "id": "Red Teams", "presentation": "markdown"},
                {"name": "Blue Teams", "id": "Blue Teams", "presentation": "markdown"},
                {"name": "Red Score", "id": "Red Score"},
                {"name": "Blue Score", "id": "Blue Score"},
                {"name": "Winner", "id": "Winner"},
                {"name": "Prediction", "id": "Prediction", "presentation": "markdown"},
            ],
            data=match_rows,
            page_size=10,
            style_table={"overflowX": "auto", "border": "1px solid #ddd", "borderRadius": "5px"},
            style_header={"backgroundColor": "#F2F2F2", "fontWeight": "bold", "border": "1px solid #ddd", "textAlign": "center"},
            style_cell={"textAlign": "center", "border": "1px solid #ddd", "padding": "8px"},
            style_data_conditional=[
                {
                    "if": {"filter_query": '{Winner} = "Red"'},
                    "backgroundColor": "#ffe6e6"
                },
                {
                    "if": {"filter_query": '{Winner} = "Blue"'},
                    "backgroundColor": "#e6f0ff"
                }
            ]
        )

        recent_rows.append(
            html.Div([
                header,
                table
            ])
        )

    return html.Div([
        html.H3("Recent Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
        html.Div(recent_rows)
    ])

def team_layout(team_number, year):
    from data_store import TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_MATCHES, EVENT_RANKINGS, EVENT_AWARDS    
    if not team_number:
        return dbc.Alert("No team number provided. Please go back and search again.", color="warning")

    team_number = int(team_number)
    team_key = f"frc{team_number}"

    # Separate handling for performance year (used for ACE/stats) vs. awards/events year
    is_history = not year or str(year).lower() == "history"

    if not is_history:
        try:
            year = int(year)
            performance_year = year
        except ValueError:
            return dbc.Alert("Invalid year provided.", color="danger")
    else:
        year = None
        performance_year = 2025

    selected_year_data = TEAM_DATABASE.get(performance_year, {})
    selected_team = selected_year_data.get(team_number)

    if not selected_team:
        return dbc.Alert(f"Team {team_number} not found in the data for {performance_year}.", color="danger")

    # Calculate Rankings
    global_rank, country_rank, state_rank = calculate_ranks(selected_year_data, selected_team)

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
        for team_num, data in selected_year_data.items()
    }

    nickname = selected_team.get("nickname", "Unknown")
    city = selected_team.get("city", "")
    state = selected_team.get("state_prov", "")
    country = selected_team.get("country", "")
    website = selected_team.get("website", "N/A")
    if website and website.startswith("http://"):
        website = "https://" + website[len("http://"):]
    
    avatar_url = get_team_avatar(team_number, performance_year)
    
    # Get all years this team appears in, sorted
    years_participated = sorted([
        y for y in TEAM_DATABASE
        if team_number in TEAM_DATABASE[y]
    ])
    
    # Build clickable year linksget_team
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
        category_data = defaultdict(lambda: {"years": [], "video": None})
    
        for year, categories in NOTABLES_DB.items():
            for category, entries in categories.items():
                if category in INCLUDED_CATEGORIES:
                    for entry in entries:
                        if entry["team"] == team_key:
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
                                html.H2(f"Team {team_number}: {nickname}", style={"color": "#333", "fontWeight": "bold"}),
                                *badges,
                                html.P([html.I(className="bi bi-geo-alt-fill"), f"📍 {city}, {state}, {country}"]),
                                html.P([html.I(className="bi bi-link-45deg"), "Website: ", 
                                        html.A(website, href=website, target="_blank", style={"color": "#007BFF", "textDecoration": "none"})]),
                                html.P([html.I(className="bi bi-award"), f" Rookie Year: {rookie_year}"]),
                                html.Div(
                                    [
                                        html.I(className="bi bi-calendar"),
                                        " Years Participated: ",
                                        html.Div(
                                            years_links,
                                            style={"display": "flex", "flexWrap": "wrap", "gap": "8px"},
                                        ),
                                    ],
                                    style={"marginBottom": "10px"},
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
            "backgroundColor": "#f9f9f9",
        },
    )

    wins = selected_team.get("wins")
    losses = selected_team.get("losses")
    avg_score = selected_team.get("average_match_score")
    
    wins_str = str(wins) if wins is not None else "N/A"
    losses_str = str(losses) if losses is not None else "N/A"
    avg_score_str = f"{avg_score:.2f}" if avg_score is not None else "N/A"
    
    win_loss_ratio = html.Span([
        html.Span(wins_str, style={"color": "green", "fontWeight": "bold"}),
        html.Span(" / ", style={"color": "#333", "fontWeight": "bold"}),
        html.Span(losses_str, style={"color": "red", "fontWeight": "bold"})
    ])

    perf = html.H5(
        f"{performance_year} Performance Metrics",
        style={
            "textAlign": "center",
            "color": "#444",
            "fontSize": "1.3rem",
            "fontWeight": "bold",
            "marginBottom": "10px",
        },
    )

    performance_card = dbc.Card(
        dbc.CardBody(
            [
                perf,
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{country} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(f"{country_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#FFC107"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Global Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(f"{global_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#007BFF"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P(f"{state} Rank", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.1rem"}),
                                        html.P(f"{state_rank}", style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#FFC107"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                        style={"marginBottom": "10px"},
                    ),
                ),
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Win/Loss Ratio", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(win_loss_ratio, style={"fontSize": "1.1rem", "fontWeight": "bold"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Avg Match Score", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(avg_score_str, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ],
                    ),
                ),
                html.Div(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Auto ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(auto_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Teleop ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(teleop_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.P("Endgame ACE", style={"color": "#666", "marginBottom": "2px", "fontSize": "1.0rem"}),
                                        html.P(endgame_epa_display, style={"fontSize": "1.1rem", "fontWeight": "bold", "color": "#17A2B8"}),
                                    ],
                                    style={"textAlign": "center"},
                                ),
                                width=4,
                            ),
                        ]
                    )
                ),
            ],
        ),
        style={"marginBottom": "15px", "borderRadius": "8px", "boxShadow": "0px 2px 4px rgba(0,0,0,0.1)", "backgroundColor": "#f9f9f9", "padding": "10px"},
    )
    
        # --- Team Events from local database ---
    events_data = []
    
    year_keys = [year] if year else TEAM_DATABASE.keys()
    participated_events = []
    
    for year_key in year_keys:
        for event_key, event in EVENT_DATABASE.get(year_key, {}).items():
            team_list = EVENT_TEAMS.get(year_key, {}).get(event_key, [])
            if any(t["tk"] == team_number for t in team_list):  # using team_number now
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
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"},
        style_cell={"textAlign": "center", "padding": "10px", "border": "1px solid #ddd"},
        style_cell_conditional=[{"if": {"column_id": "event_name"}, "textAlign": "center"}],
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "rgba(255, 221, 0, 0.5)", "border": "1px solid #FFCC00"}],
    )
    
    # --- Awards Section ---
    team_awards = [
        row for row in EVENT_AWARDS
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
        style_table={"overflowX": "auto", "borderRadius": "10px", "border": "1px solid #ddd"},
        style_header={"backgroundColor": "#FFCC00", "fontWeight": "bold", "textAlign": "center", "border": "1px solid #ddd"},
        style_cell={"textAlign": "center", "padding": "10px", "border": "1px solid #ddd"},
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
            event = TEAM_DATABASE.get(int(year_str), {}).get(event_key, {})
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
        style={"marginBottom": "15px", "borderRadius": "8px", "backgroundColor": "white", "padding": "10px"},
    )

    
    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    team_card,
                    performance_card,
                    html.Hr(),
                    build_recent_events_section(team_key, team_number, epa_data, performance_year, is_history),
                    html.H3("Events", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    events_table,
                    html.H3("Awards", style={"marginTop": "2rem", "color": "#333", "fontWeight": "bold"}),
                    awards_table,
                    #rank_tabs,  # Rank Over Time tabs inserted here
                    blue_banner_section,
                    html.Br(),
                    dbc.Button("Go Back", id="btn-go-back", color="secondary", href="/", external_link=True, 
                               style={"borderRadius": "5px", "padding": "10px 20px", "marginTop": "20px"}),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer,
        ]
    )