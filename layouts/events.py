from dash import dcc, html
import dash_bootstrap_components as dbc
from layouts.topbar import topbar, footer
from datagather import load_data
import datetime

from data_store import EVENT_DATABASE

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

def events_layout(year=2025):
    today = datetime.date.today()
    events_data = list(EVENT_DATABASE.get(year, {}).values())

    def parse_date(d):
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return datetime.date(1900, 1, 1)

    for ev in events_data:
        ev["_start_date_obj"] = parse_date(ev.get("sd", "1900-01-01"))
        ev["_end_date_obj"] = parse_date(ev.get("ed", "1900-01-01"))

    events_data.sort(key=lambda x: x["_start_date_obj"])

    upcoming = [ev for ev in events_data if ev["_start_date_obj"] > today]
    ongoing = [ev for ev in events_data if ev["_start_date_obj"] <= today <= ev["_end_date_obj"]]

    up_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in upcoming[:5]]
    ongoing_cards = [dbc.Col(create_event_card(ev), width="auto") for ev in ongoing]
    all_event_cards = [create_event_card(ev) for ev in events_data]

    return html.Div(
        [
            topbar,
            dbc.Container(
                [
                    html.H3("Upcoming Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(up_cards, className="justify-content-center"),

                    html.H3("Ongoing Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(ongoing_cards, className="justify-content-center"),

                    html.H3("All Events", className="mb-4 mt-4 text-center"),
                    dbc.Row(all_event_cards, className="justify-content-center"),
                ],
                style={"padding": "20px", "maxWidth": "1200px", "margin": "0 auto"},
            ),
            dbc.Button("Invisible", id="btn-search-home", style={"display": "none"}),
            dbc.Button("Invisible2", id="input-team-home", style={"display": "none"}),
            dbc.Button("Invisible3", id="input-year-home", style={"display": "none"}),
            footer
        ]
    )
