from datagather import load_data

data = load_data(
    load_teams=True,
    load_events=True,
    load_event_teams=True,
    load_rankings=True,
    load_awards=True,
    load_matches=True,
    load_oprs=True,
    #years=[2025],  # <-- Limit to 2025
)

TEAM_DATABASE = data.get("team_data", {})
EVENT_DATABASE = data.get("event_data", {})
EVENTS_DATABASE = data.get("flat_event_list", [])
EVENT_TEAMS = data.get("event_teams", {})
EVENT_RANKINGS = data.get("event_rankings", {})
EVENT_AWARDS = data.get("event_awards", [])
EVENT_MATCHES = data.get("event_matches", {})
EVENT_OPRS = data.get("event_oprs", {})

def load_legacy_data():
    all_years = list(range(1992, 2025))  # 1992 to 2024 inclusive
    return load_data(
        load_teams=True,
        load_events=True,
        load_event_teams=True,
        load_rankings=True,
        load_awards=True,
        load_matches=True,
        load_oprs=True
    )

