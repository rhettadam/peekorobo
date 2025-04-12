from layouts.topbar import topbar, footer
import re
import numpy as np
import datetime
from layouts.epalegend import epa_legend_layout, get_epa_display
import dash_bootstrap_components as dbc
from dash import html, dcc
from dash import dash_table
from datagather import tba_get, get_team_avatar,load_data

from data_store import TEAM_DATABASE

def create_team_card_spotlight(team, epa_data, event_year):
    """
    Build a team spotlight card using compressed event team data
    and full-schema TEAM_DATABASE.
    """
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

    avatar_url = get_team_avatar(t_num, event_year)
    team_url = f"/team/{t_num}/{event_year}"

    card_elems = []
    if avatar_url:
        card_elems.append(
            dbc.CardImg(
                src=avatar_url,
                top=True,
                style={"width": "100%", "height": "150px", "objectFit": "contain", "backgroundColor": "#fff", "padding": "5px"}
            )
        )

    card_elems.append(
        dbc.CardBody([
            html.H5(f"#{t_num} | {nickname}", className="card-title mb-3"),
            html.P(f"Location: {location_str}", className="card-text"),
            html.P(f"ACE: {epa_display} (Global Rank: {epa_rank})", className="card-text"),
            dbc.Button("View Team", href=team_url, color="warning", className="mt-2"),
        ])
    )

    return dbc.Card(card_elems, className="m-2 shadow", style={
        "width": "18rem", "height": "26rem", "display": "flex",
        "flexDirection": "column", "justifyContent": "start", "alignItems": "stretch",
    })

def parse_event_key(event_key):
    m = re.match(r'^(\d{4})(.+)$', event_key)
    if m:
        return int(m.group(1)), m.group(2)
    return None, event_key
    
def is_recent_event(start_date_str, end_date_str):
    try:
        today = datetime.today().date()
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        return (start <= today <= end + timedelta(days=2))
    except Exception:
        return False

def fetch_event_data(event_key):
    year, _ = parse_event_key(event_key)
    event = tba_get(f"event/{event_key}")
    teams = tba_get(f"event/{event_key}/teams")

    rankings_raw = tba_get(f"event/{event_key}/rankings")
    rankings = {
        int(r["team_key"][3:]): {
            "rk": r.get("rank"),
            "w": r.get("record", {}).get("wins"),
            "l": r.get("record", {}).get("losses"),
            "t": r.get("record", {}).get("ties"),
            "dq": r.get("dq", 0),
        }
        for r in rankings_raw.get("rankings", [])
    } if rankings_raw else {}

    matches_raw = tba_get(f"event/{event_key}/matches") or []
    compressed_matches = [
        {
            "k": m["key"],
            "ek": event_key,
            "cl": m.get("comp_level"),
            "mn": m.get("match_number"),
            "sn": m.get("set_number"),
            "rt": ",".join(str(int(t[3:])) for t in m["alliances"]["red"]["team_keys"]),
            "bt": ",".join(str(int(t[3:])) for t in m["alliances"]["blue"]["team_keys"]),
            "rs": m["alliances"]["red"]["score"],
            "bs": m["alliances"]["blue"]["score"],
            "wa": m.get("winning_alliance"),
            "yt": next((v["key"] for v in m.get("videos", []) if v["type"] == "youtube"), None)
        }
        for m in matches_raw
    ]

    oprs_raw = tba_get(f"event/{event_key}/oprs") or {}
    oprs = {"oprs": {int(k[3:]): v for k, v in oprs_raw.get("oprs", {}).items()}}

    compressed_teams = [
        {
            "tk": t["team_number"],
            "nn": t.get("nickname"),
            "c": t.get("city"),
            "s": t.get("state_prov"),
            "co": t.get("country"),
        }
        for t in teams or []
    ]

    return event, compressed_teams, rankings, compressed_matches, oprs

def fetch_event_data_fallback(event_key):
    return fetch_event_data(event_key)

def load_teams_and_compute_epa_ranks(year):
    epa_info = {}

    year_data = TEAM_DATABASE.get(year)
    if not year_data:
        return epa_info  # Return empty if no data

    teams_data = list(year_data.values())

    teams_data = sorted(teams_data, key=lambda x: x.get("epa", 0) or 0, reverse=True)

    epa_values = [team["epa"] for team in teams_data if team.get("epa") is not None]
    if not epa_values:
        return epa_info  # No ACE values to rank

    percentiles = {
        "99": np.percentile(epa_values, 99),
        "95": np.percentile(epa_values, 95),
        "90": np.percentile(epa_values, 90),
        "75": np.percentile(epa_values, 75),
        "50": np.percentile(epa_values, 50),
        "25": np.percentile(epa_values, 25),
    }

    for idx, team in enumerate(teams_data):
        team_number = team["team_number"]
        epa_val = team.get("epa")
        rank = idx + 1
        epa_info[str(team_number)] = {
            "epa": epa_val,
            "rank": rank,
            "epa_display": get_epa_display(epa_val, percentiles),
        }

    return epa_info

def event_layout(event_key):
    parsed_year, _ = parse_event_key(event_key)
    event_year = parsed_year

    # Load only the relevant year's data
    data = load_data(
        load_teams=False,
        load_events=True,
        load_event_teams=True,
        load_rankings=True,
        load_awards=False,
        load_matches=True,
        load_oprs=True,
        years=[event_year],
    )

    event = data["event_data"].get(event_year, {}).get(event_key)
    if not event:
        return dbc.Alert("Event details could not be found.", color="danger")

    start_date = event.get("sd", "")
    end_date = event.get("ed", "")
    event_name = event.get("n", "Unknown Event")
    event_location = f"{event.get('c', '')}, {event.get('s', '')}, {event.get('co', '')}"
    event_type = event.get("et", "N/A")
    website = event.get("w", "#")

    should_fallback = is_recent_event(start_date, end_date)

    event_teams = data.get("event_teams", {}).get(event_year, {}).get(event_key, [])
    rankings = data.get("event_rankings", {}).get(event_year, {}).get(event_key, {})
    event_matches = [m for m in data.get("event_matches", {}).get(event_year, []) if m.get("ek") == event_key]
    oprs = data.get("event_oprs", {}).get(event_year, {}).get(event_key, {})

    if should_fallback or not (rankings and event_matches and oprs):
        print(f"🔄 Fetching live data for {event_key}...")
        event, event_teams, rankings, event_matches, oprs = fetch_event_data_fallback(event_key)

    # Recompute EPA ranks
    epa_data = load_teams_and_compute_epa_ranks(event_year)

    # --- UI Components ---
    last_match = next((m for m in reversed(event_matches) if m.get("cl") in {"f", "sf"}), None)
    thumbnail_url = f"https://img.youtube.com/vi/{last_match.get('yt')}/hqdefault.jpg" if last_match and last_match.get("yt") else None
    last_match_thumbnail = dbc.Card(
        dbc.CardBody(html.A(html.Img(src=thumbnail_url, style={"width": "100%", "borderRadius": "5px"}),
        href=f"https://www.youtube.com/watch?v={last_match.get('yt')}", target="_blank"))
    ) if thumbnail_url else None

    header_card = dbc.Card(
        dbc.CardBody([
            html.H2(f"{event_name} ({event_year})", className="card-title mb-3", style={"fontWeight": "bold"}),
            html.P(f"Location: {event_location}", className="card-text"),
            html.P(f"Date: {start_date} - {end_date}", className="card-text"),
            html.P(f"Type: {event_type}", className="card-text"),
            dbc.Button("Visit Event Website", href=website, external_link=True,
                       style={"backgroundColor": "#FFCC00", "borderColor": "#FFCC00", "color": "black"},
                       className="mt-3")
        ]),
        className="mb-4 shadow-sm flex-fill", style={"borderRadius": "10px"}
    )

    header_layout = dbc.Row([
        dbc.Col(header_card, md=8, className="d-flex align-items-stretch"),
        dbc.Col(last_match_thumbnail, md=4, className="d-flex align-items-stretch") if last_match_thumbnail else dbc.Col()
    ])

    tab_style = {"color": "#3b3b3b"}
    data_tabs = dbc.Tabs(
        [
            dbc.Tab(label="Teams", tab_id="teams", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Rankings", tab_id="rankings", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="OPRs", tab_id="oprs", label_style=tab_style, active_label_style=tab_style),
            dbc.Tab(label="Matches", tab_id="matches", label_style=tab_style, active_label_style=tab_style),
        ],
        id="event-data-tabs", active_tab="teams", className="mb-4"
    )

    return html.Div([
        topbar,
        dbc.Container([
            header_layout,
            data_tabs,
            dcc.Store(id="store-event-epa", data=epa_data),
            dcc.Store(id="store-event-teams", data=event_teams),
            dcc.Store(id="store-rankings", data=rankings),
            dcc.Store(id="store-event-matches", data=event_matches),
            dcc.Store(id="store-event-year", data=event_year),
            dcc.Store(id="store-oprs", data={"oprs": oprs}),
            html.Div(id="data-display-container"),
        ], style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"}),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer,
    ])
