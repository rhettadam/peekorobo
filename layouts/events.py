from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from layouts.topbar import topbar, footer
import datetime
from data_store import EVENT_DATABASE

# Updated week definitions based on actual 2025 FRC season structure
WEEK_RANGES_2025 = [
    (datetime.date(2025, 2, 17), datetime.date(2025, 2, 23)),  # Week 0
    (datetime.date(2025, 2, 24), datetime.date(2025, 3, 3)),   # Week 1
    (datetime.date(2025, 3, 4), datetime.date(2025, 3, 10)),  # Week 2
    (datetime.date(2025, 3, 11), datetime.date(2025, 3, 17)), # Week 3
    (datetime.date(2025, 3, 18), datetime.date(2025, 3, 24)), # Week 4
    (datetime.date(2025, 3, 25), datetime.date(2025, 3, 31)), # Week 5
    (datetime.date(2025, 4, 1), datetime.date(2025, 4, 7)),   # Week 6
]

def assign_week_number(event_date):
    for i, (start, end) in enumerate(WEEK_RANGES_2025):
        if start <= event_date <= end:
            return i
    return None

def create_event_card(event):
    event_url = f"https://www.peekorobo.com/event/{event['k']}"
    location = f"{event.get('c','')}, {event.get('s','')}, {event.get('co','')}"
    start = event.get('sd', 'N/A')
    end = event.get('ed', 'N/A')

    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(event.get("n", "Unknown Event"), className="card-title mb-2"),
                html.P(location, className="card-text", style={"fontSize": "0.85rem", "marginBottom": "4px"}),
                html.P(f"{start} - {end}", className="card-text", style={"fontSize": "0.8rem", "marginBottom": "auto"}),
                html.Div(style={"flexGrow": "1"}),  # spacer to push button down
                html.Div(
                    dbc.Button("View", href=event_url, target="_blank", color="warning", size="sm"),
                    style={"textAlign": "right", "marginTop": "-50px"}
                )
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "height": "100%",
                "padding": "0.75rem"
            }
        ),
        className="shadow-sm",
        style={
            "width": "15rem",
            "height": "8rem",
            "margin": "5px 2px"
        }
    )

def events_layout(year=2025):
    today = datetime.date.today()
    all_years = sorted(EVENT_DATABASE.keys(), reverse=True)
    events_data = list(EVENT_DATABASE.get(year, {}).values())

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return None

    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("sd"))
        ev["_end_date_obj"] = parse_date(ev.get("ed"))

    week_options = sorted({f"Week {i}" for i in range(len(WEEK_RANGES_2025))}, key=lambda w: int(w.split()[1]))
    country_options = sorted({ev.get("co") for ev in events_data if ev.get("co")})
    state_options = sorted({ev.get("s") for ev in events_data if ev.get("s")})

    filter_controls = dbc.Row([
        dbc.Col(dcc.Dropdown(id="event-week-filter", options=[{"label": w, "value": w} for w in week_options], placeholder="Week"), xs=6, sm=4, md=2),
        dbc.Col(dcc.Dropdown(id="event-country-filter", options=[{"label": c, "value": c} for c in country_options], placeholder="Country"), xs=6, sm=4, md=2),
        dbc.Col(dcc.Dropdown(id="event-state-filter", options=[{"label": s, "value": s} for s in state_options], placeholder="State"), xs=6, sm=4, md=2),
        dbc.Col(dcc.Input(id="event-search", placeholder="Search", type="text", debounce=True, className="form-control"), xs=6, sm=4, md=2),
        dbc.Col(dcc.Dropdown(id="event-year-dropdown", options=[{"label": str(y), "value": y} for y in all_years], value=year), xs=6, sm=4, md=2),
    ], className="mb-4 justify-content-center", style={"gap": "0.5rem"})

    return html.Div([
        topbar,
        dbc.Container([
            html.Div(filter_controls, style={"textAlign": "center"}),
            html.Div(id="filtered-events-list"),
            dcc.Store(id="events-visible-count-upcoming", data=8),
            dcc.Store(id="events-visible-count-recent", data=8),
            dcc.Store(id="events-visible-count-past", data=8),
            html.Div(id="show-more-buttons", children=[
                dbc.Row([
                    dbc.Col(dbc.Button("Show More", id="show-more-upcoming", color="primary", className="mt-2", size="sm"), width="auto")
                ], className="justify-content-center", style={"display": "none"}),
                dbc.Row([
                    dbc.Col(dbc.Button("Show More", id="show-more-recent", color="primary", className="mt-2", size="sm"), width="auto")
                ], className="justify-content-center", style={"display": "none"}),
                dbc.Row([
                    dbc.Col(dbc.Button("Show More", id="show-more-past", color="primary", className="mt-2", size="sm"), width="auto")
                ], className="justify-content-center", style={"display": "none"})
            ])
        ], style={"padding": "20px", "maxWidth": "1300px", "margin": "0 auto"}),
        dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
        dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
        dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
        footer
    ])