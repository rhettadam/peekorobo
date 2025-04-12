from dash import dcc, html, callback, Output, Input
from dash import dash_table
import dash_bootstrap_components as dbc
from layouts.topbar import topbar, footer
from datagather import load_data
import datetime

data = load_data(
    load_teams=False,
    load_events=True,
    load_event_teams=False,
    load_rankings=False,
    load_awards=False,
    load_matches=False,
    load_oprs=False,
)

EVENT_DATABASE = data.get("event_data", {})

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
            [{"label": "All", "value": "all"}] +
            [{"label": f"Week {i+1}", "value": i} for i in range(0, 9)]
        ),
        value="all",
        placeholder="Week",
        clearable=False,
    )
    search_input = dbc.Input(
        id="search-input",
        placeholder="Search",
        type="text",
    )

    filters_row = dbc.Row(
        [
            dbc.Col(year_dropdown, xs=6, sm=3, md=2),
            dbc.Col(event_type_dropdown, xs=6, sm=3, md=2),
            dbc.Col(week_dropdown, xs=6, sm=3, md=2),
            dbc.Col(search_input, xs=6, sm=3, md=2),
        ],
        className="mb-4 justify-content-center",
        style={"gap": "10px"},
    )

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="upcoming-events-container", className="justify-content-center"),

                    html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(id="ongoing-events-container", className="justify-content-center"),

                    html.H3("All Events", className="mb-4 mt-4 text-center"),
                    filters_row,
                    html.Div(
                        id="all-events-container",
                        className="d-flex flex-wrap justify-content-center"
                    ),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer
        ]
    )


def create_event_card(event):
    event_url = f"https://www.peekorobo.com/event/{event['k']}"
    location = f"{event.get('c','')}, {event.get('s','')}, {event.get('co','')}"
    start = event.get('sd', 'N/A')
    end = event.get('ed', 'N/A')
    event_type = event.get('et', 'N/A')

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H5(event.get("n", "Unknown Event"), className="card-title mb-3"),
                    html.P(location, className="card-text"),
                    html.P(f"Dates: {start} - {end}", className="card-text"),
                    html.P(f"Type: {event_type}", className="card-text"),
                    dbc.Button("View Details", href=event_url, target="_blank",
                               color="warning", className="mt-2"),
                ]
            )
        ],
        className="mb-4 shadow",
        style={
            "width": "18rem",
            "height": "20rem",
            "margin": "10px"
        }
    )

@callback(
    [
        Output("upcoming-events-container", "children"),
        Output("ongoing-events-container", "children"),
        Output("all-events-container", "children"),
    ],
    [
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("week-dropdown", "value"),
        Input("search-input", "value"),
    ],
)
def update_events_table(selected_year, selected_event_types, selected_week, search_query):
    events_data = list(EVENT_DATABASE.get(selected_year, {}).values())
    if not events_data:
        return [], [], []

    if not isinstance(selected_event_types, list):
        selected_event_types = [selected_event_types]

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

    if selected_week != "all":
        events_data = [ev for ev in events_data if ev.get("w") == selected_week]  # Optional: include week in compressed schema

    if search_query:
        q = search_query.lower()
        events_data = [
            ev for ev in events_data
            if q in ev.get("n", "").lower() or q in ev.get("c", "").lower()
        ]

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("sd", "1900-01-01"))
        ev["_end_date_obj"] = parse_date(ev.get("ed", "1900-01-01"))
    events_data.sort(key=lambda x: x["_start_date_obj"])

    today = datetime.date.today()
    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    up_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in upcoming[:5]]
    upcoming_layout = dbc.Row(up_cards, className="justify-content-center")

    ongoing_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in ongoing]
    ongoing_layout = dbc.Row(ongoing_cards, className="justify-content-center")

    all_event_cards = [create_event_card(ev) for ev in events_data]

    return upcoming_layout, ongoing_layout, all_event_cards