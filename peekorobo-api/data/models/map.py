from typing import List

from sqlalchemy import select, func, cast, DateTime
from sqlalchemy.orm import Session

from data.models.teams import Teams
from data.models.events import Events
from query.map import MapTeam, MapTeamsResponse, MapEvent, MapEventsResponse


def get_map_teams(db: Session) -> MapTeamsResponse:
    stmt = (
        select(
            Teams.team_number,
            Teams.nickname,
            Teams.city,
            Teams.state_prov,
            Teams.country,
            Teams.lat,
            Teams.lng,
        )
        .where(Teams.lat.is_not(None), Teams.lng.is_not(None))
        .order_by(Teams.team_number)
    )
    rows = db.execute(stmt).all()
    teams: List[MapTeam] = [
        MapTeam(
            team_number=r[0],
            nickname=r[1],
            city=r[2],
            state_prov=r[3],
            country=r[4],
            lat=r[5],
            lng=r[6],
        )
        for r in rows
    ]
    return MapTeamsResponse(count=len(teams), teams=teams)


def get_map_events(db: Session, year: int) -> MapEventsResponse:
    start_as_dt = cast(Events.start_date, DateTime())
    stmt = (
        select(
            Events.event_key,
            Events.name,
            Events.city,
            Events.state_prov,
            Events.country,
            Events.lat,
            Events.lng,
            Events.event_type,
            Events.week,
            Events.start_date,
            Events.end_date,
        )
        .where(
            Events.lat.is_not(None),
            Events.lng.is_not(None),
            func.extract("year", start_as_dt) == year,
        )
        .order_by(start_as_dt)
    )
    rows = db.execute(stmt).all()
    events: List[MapEvent] = [
        MapEvent(
            event_key=r[0],
            name=r[1],
            city=r[2],
            state_prov=r[3],
            country=r[4],
            lat=r[5],
            lng=r[6],
            event_type=r[7],
            week=r[8],
            start_date=r[9],
            end_date=r[10],
        )
        for r in rows
    ]
    return MapEventsResponse(year=year, count=len(events), events=events)
