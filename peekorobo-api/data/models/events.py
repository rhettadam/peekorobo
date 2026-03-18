import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import Text, INT, select, func, or_
from sqlalchemy.orm import Mapped, mapped_column, Session, QueryEvents
from data.db import Base
from query.events import EventQuery, EventResponse, LocationInfo, EventMetaInfo, EventData

def _district_match(column, district_key: str):
    """Match district_key (handles 2024fim or FIM format)."""
    dk = (district_key or "").strip()
    if not dk:
        return None
    if len(dk) > 4 and dk[:4].isdigit():
        return column.ilike(dk)
    return or_(
        column.ilike(dk),
        (func.length(column) > 4) & (func.substring(column, 5).ilike(dk)),
    )

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
        where_clause.append(func.lower(Events.city) == func.lower(event_query.city))
    if event_query.state_prov is not None:
        where_clause.append(func.lower(Events.state_prov) == func.lower(event_query.state_prov))
    if event_query.country is not None:
        where_clause.append(func.lower(Events.country) == func.lower(event_query.country))
    if event_query.district_key:
        cond = _district_match(Events.district_key, event_query.district_key)
        if cond is not None:
            where_clause.append(cond)
    where_clause.append(func.extract('year',Events.start_date) == event_year)

    stmt = select(Events).where(*where_clause).order_by(Events.start_date)
    if event_query.limit is not None:
        stmt = stmt.limit(event_query.limit)

    result = db.scalars(stmt)
    event_list = list(map(build_events_response, result.all()))

    return EventResponse(
        events=event_list,
        next=None
    )

def get_event_keys(db: Session, year: int, event_query: EventQuery):
    """Return event keys for a given year, sorted by start_date. Uses same filters as get_events."""
    where_clause = [func.extract('year', Events.start_date) == year]
    if event_query.city is not None:
        where_clause.append(func.lower(Events.city) == func.lower(event_query.city))
    if event_query.state_prov is not None:
        where_clause.append(func.lower(Events.state_prov) == func.lower(event_query.state_prov))
    if event_query.country is not None:
        where_clause.append(func.lower(Events.country) == func.lower(event_query.country))
    if event_query.district_key:
        cond = _district_match(Events.district_key, event_query.district_key)
        if cond is not None:
            where_clause.append(cond)
    stmt = (
        select(Events.event_key)
        .where(*where_clause)
        .order_by(Events.start_date)
    )
    if event_query.limit is not None:
        stmt = stmt.limit(event_query.limit)
    result = db.scalars(stmt)
    return list(result.scalars().all())
