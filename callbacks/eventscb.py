from dash import callback, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import datetime
from data_store import EVENT_DATABASE
from layouts.events import create_event_card

WEEK_RANGES_2025 = [
    (datetime.date(2025, 2, 17), datetime.date(2025, 2, 23)),  # Week 0
    (datetime.date(2025, 2, 24), datetime.date(2025, 3, 3)),   # Week 1
    (datetime.date(2025, 3, 4), datetime.date(2025, 3, 10)),  # Week 2
    (datetime.date(2025, 3, 11), datetime.date(2025, 3, 17)), # Week 3
    (datetime.date(2025, 3, 18), datetime.date(2025, 3, 24)), # Week 4
    (datetime.date(2025, 3, 25), datetime.date(2025, 3, 31)), # Week 5
    (datetime.date(2025, 4, 1), datetime.date(2025, 4, 7)),   # Week 6
    (datetime.date(2025, 4, 8), datetime.date(2025, 4, 15)),  # Week 7
    (datetime.date(2025, 4, 16), datetime.date(2025, 4, 23)), # Week 8
]

@callback(
    Output("filtered-events-list", "children"),
    [
        Input("event-search", "value"),
        Input("event-week-filter", "value"),
        Input("event-country-filter", "value"),
        Input("event-state-filter", "value"),
        Input("event-year-dropdown", "value"),
        Input("events-visible-count-upcoming", "data"),
        Input("events-visible-count-recent", "data"),
        Input("events-visible-count-past", "data"),
        Input("show-more-upcoming", "n_clicks"),
        Input("show-more-recent", "n_clicks"),
        Input("show-more-past", "n_clicks"),
    ],
    [
        State("events-visible-count-upcoming", "data"),
        State("events-visible-count-recent", "data"),
        State("events-visible-count-past", "data"),
    ]
)
def update_filtered_events(search_text, selected_week, selected_country, selected_state, selected_year,
                            visible_upcoming, visible_recent, visible_past,
                            click_upcoming, click_recent, click_past,
                            state_upcoming, state_recent, state_past):

    triggered = ctx.triggered_id
    
    if triggered == "show-more-upcoming":
        visible_upcoming = state_upcoming + 8
    elif triggered == "show-more-recent":
        visible_recent = state_recent + 8
    elif triggered == "show-more-past":
        visible_past = state_past + 8

    events = list(EVENT_DATABASE.get(selected_year, {}).values())

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    def assign_week(event_date):
        for i, (start, end) in enumerate(WEEK_RANGES_2025):
            if start <= event_date <= end:
                return f"Week {i}"
        return None

    for ev in events:
        ev["_start_date_obj"] = parse_date(ev.get("sd", "1900-01-01"))
        ev["_week_number"] = assign_week(ev["_start_date_obj"])

    def matches(event):
        if search_text and search_text.lower() not in event.get("n", "").lower():
            return False
        if selected_week and event.get("_week_number") != selected_week:
            return False
        if selected_country and event.get("co") != selected_country:
            return False
        if selected_state and event.get("s") != selected_state:
            return False
        return True

    filtered = [event for event in events if matches(event)]
    filtered.sort(key=lambda x: x["_start_date_obj"])

    today = datetime.date.today()
    upcoming = [ev for ev in filtered if ev["_start_date_obj"] and ev["_start_date_obj"] > today]
    recent = [ev for ev in filtered if ev["_start_date_obj"] and (today - ev["_start_date_obj"]).days <= 21 and ev["_start_date_obj"] <= today]
    past = [ev for ev in filtered if ev["_start_date_obj"] and ev["_start_date_obj"] < today and ev not in recent]

    sections = []
    if upcoming:
        sections.append(
            dbc.Row([
                dbc.Col(html.H4("Upcoming Events", className="my-3"), width="auto"),
                dbc.Col(dbc.Button("Show More", id="show-more-upcoming", color="warning", size="sm"), width="auto")
            ], className="align-items-center mb-2")
        )
        sections.append(
            dbc.Row(
                [dbc.Col(create_event_card(ev), width="auto") for ev in upcoming[:visible_upcoming]],
                className="justify-content-center"
            )
        )

    if recent:
        sections.append(
            dbc.Row([
                dbc.Col(html.H4("Recent Events", className="my-3"), width="auto"),
                dbc.Col(dbc.Button("Show More", id="show-more-recent", color="warning", size="sm"), width="auto")
            ], className="align-items-center mb-2")
        )
        sections.append(
            dbc.Row(
                [dbc.Col(create_event_card(ev), width="auto") for ev in recent[:visible_recent]],
                className="justify-content-center"
            )
        )

    if past:
        sections.append(
            dbc.Row([
                dbc.Col(html.H4("Completed Events", className="my-3"), width="auto"),
                dbc.Col(dbc.Button("Show More", id="show-more-past", color="warning", size="sm"), width="auto")
            ], className="align-items-center mb-2")
        )
        sections.append(
            dbc.Row(
                [dbc.Col(create_event_card(ev), width="auto") for ev in past[:visible_past]],
                className="justify-content-center"
            )
        )

    if not sections:
        return [html.Div("No events found matching your filters.", className="text-center my-5")]

    return sections