from dash import callback, Input, Output, State, html, dcc
from dash import dash_table
import dash_bootstrap_components as dbc

from layouts.epalegend import epa_legend_layout
from layouts.event import create_team_card_spotlight

@callback(
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
    common_style_table = {
        "overflowX": "auto",
        "border": "1px solid #ddd",
        "borderRadius": "5px",
    }
    common_style_header = {
        "backgroundColor": "#F2F2F2",
        "fontWeight": "bold",
        "border": "1px solid #ddd",
        "textAlign": "center",
    }
    common_style_cell = {
        "textAlign": "center",
        "border": "1px solid #ddd",
        "padding": "8px",
    }

    def safe_int(val):
        try: return int(val)
        except: return 999999

    # === Rankings Tab ===
    if active_tab == "rankings":
        data_rows = []
        for team_num, rank_info in (rankings or {}).items():
            tnum_str = str(team_num)

            epa_rank = epa_data.get(tnum_str, {}).get("rank", "N/A")
            epa_display = epa_data.get(tnum_str, {}).get("epa_display", "N/A")

            data_rows.append({
                "Rank": rank_info.get("rk", "N/A"),
                "Team": f"[{tnum_str}](/team/{tnum_str})",
                "Wins": rank_info.get("w", "N/A"),
                "Losses": rank_info.get("l", "N/A"),
                "Ties": rank_info.get("t", "N/A"),
                "DQ": rank_info.get("dq", "N/A"),
                "ACE Rank": epa_rank,
                "ACE": epa_display,
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
            )
        ])

    # === OPRs Tab ===
    elif active_tab == "oprs":
        data = []
        for team_num, opr_val in (oprs.get("oprs") or {}).items():
            tnum_str = str(team_num)
            epa_rank = epa_data.get(tnum_str, {}).get("rank", "N/A")
            epa_display = epa_data.get(tnum_str, {}).get("epa_display", "N/A")

            data.append({
                "Team": f"[{tnum_str}](/team/{tnum_str})",
                "OPR": opr_val,
                "ACE Rank": epa_rank,
                "ACE": epa_display,
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
        )

    # === Teams Tab ===
    elif active_tab == "teams":
        sorted_teams = sorted(
            event_teams,
            key=lambda t: safe_int(epa_data.get(str(t.get("tk")), {}).get("rank", 999999))
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
            epa_rank = epa_data.get(tstr, {}).get("rank", "N/A")
            epa_disp = epa_data.get(tstr, {}).get("epa_display", "N/A")

            loc = ", ".join(filter(None, [t.get("c", ""), t.get("s", ""), t.get("co", "")])) or "Unknown"

            rows.append({
                "ACE Rank": epa_rank,
                "ACE": epa_disp,
                "Team Number": f"[{tstr}](/team/{tstr})",
                "Nickname": t.get("nn", "Unknown"),
                "Location": loc,
            })

        rows.sort(key=lambda r: safe_int(r["ACE Rank"]))

        columns = [
            {"name": "ACE Rank", "id": "ACE Rank"},
            {"name": "ACE", "id": "ACE"},
            {"name": "Team Number", "id": "Team Number", "presentation": "markdown"},
            {"name": "Nickname", "id": "Nickname"},
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

    return dbc.Alert("No data available.", color="warning")

@callback(
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
            if selected_team in (m.get("rt", "") + "," + m.get("bt", ""))
        ]

    # 2) Sort and separate by comp level
    comp_level_order = {"qm": 0, "qf": 1, "sf": 2, "f": 3}

    def match_sort_key(m):
        lvl = comp_level_order.get(m.get("cl", ""), 99)
        num = m.get("mn", 9999)
        return (lvl, num)

    event_matches.sort(key=match_sort_key)
    qual_matches = [m for m in event_matches if m.get("cl") == "qm"]
    playoff_matches = [m for m in event_matches if m.get("cl") != "qm"]

    # 3) Utility functions
    def format_teams_markdown(team_list_str):
        return ", ".join(f"[{t}](/team/{t})" for t in team_list_str.split(",") if t.strip().isdigit())

    def sum_epa(team_list_str):
        return sum(
            epa_data.get(t.strip(), {}).get("epa", 0)
            for t in team_list_str.split(",") if t.strip().isdigit()
        )

    def build_match_rows(matches):
        rows = []
        for match in matches:
            red_str = match.get("rt", "")
            blue_str = match.get("bt", "")
            red_score = match.get("rs", 0)
            blue_score = match.get("bs", 0)
            winner = match.get("wa", "")
            label = match.get("cl", "").upper() + str(match.get("mn", ""))

            r_sum = sum_epa(red_str)
            b_sum = sum_epa(blue_str)
            if (r_sum + b_sum) > 0:
                p_red = r_sum / (r_sum + b_sum)
                p_blue = 1.0 - p_red
                pred_str = f"🔴 **{p_red:.0%}** vs 🔵 **{p_blue:.0%}**"
            else:
                pred_str = "N/A"

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

    style_table = {
        "overflowX": "auto",
        "border": "1px solid #ddd",
        "borderRadius": "5px",
    }
    style_header = {
        "backgroundColor": "#F2F2F2",
        "fontWeight": "bold",
        "border": "1px solid #ddd",
        "textAlign": "center",
    }
    style_cell = {
        "textAlign": "center",
        "border": "1px solid #ddd",
        "padding": "8px",
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