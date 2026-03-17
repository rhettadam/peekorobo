import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import Text, INT, select, func
from sqlalchemy.orm import Mapped, mapped_column, Session, QueryEvents
from db import Base
from query.events import EventQuery, EventResponse, LocationInfo, EventMetaInfo, EventData

class Events(Base):
    __tablename__="events"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    name : Mapped[str] = mapped_column(Text)
    start_date: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP)
    end_date: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP)
    event_type: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    state_prov: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text)
    website: Mapped[str] = mapped_column(Text)
    webcast_type: Mapped[str] = mapped_column(Text)
    webcast_channel: Mapped[str] = mapped_column(Text)
    district_key: Mapped[str] = mapped_column(Text)
    district_abbrev : Mapped[str] = mapped_column(Text)
    district_name : Mapped[str] = mapped_column(Text)
    week : Mapped[Optional[int]] = mapped_column(INT)

def build_events_response(event : Events) -> EventData:
    meta_data = EventMetaInfo(name = "", start_date=datetime.datetime.now(), end_date=datetime.datetime.now(), event_type="")
    location_info = LocationInfo(city = "", state_prov = "", country = "")
    return EventData( event_key="",
                          event_data = meta_data,
                          location_info = location_info,
                          website = None,
                          webcast_type = None,
                          webcast_channel = None)

def get_events(db: Session, event_year : int, event_query : EventQuery) -> EventResponse:
    where_clause = []
    if event_query.city is not None:
        where_clause.append(Events.city == event_query.city)
    if event_query.state_prov is not None:
        where_clause.append(Events.state_prov == event_query.state_prov)
    if event_query.country is not None:
        where_clause.append(Events.country == event_query.country)
    where_clause.append(func.extract('year',Events.start_date) == event_year)
     
    stmt = select(Events).where(*where_clause).order_by(Events.start_date)

    result = db.scalars(stmt)

    events = list(map(build_events_response, result.all()))
    
    return EventResponse(
        events=events,
        next=None
    )
