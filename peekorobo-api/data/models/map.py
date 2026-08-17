from typing import List, Optional, Tuple

from sqlalchemy import select, func, cast, DateTime
from sqlalchemy.orm import Session

from data.models.teams import Teams
from data.models.events import Events
from query.map import MapTeam, MapTeamsResponse, MapEvent, MapEventsResponse


def _loc_key(city, state, country) -> Optional[str]:
    parts = [
        (city or "").strip().lower(),
        (state or "").strip().lower(),
        (country or "").strip().lower(),
    ]
    if not any(parts):
        return None
    return "|".join(parts)


def get_map_teams(db: Session) -> MapTeamsResponse:
    stmt = (
        select(
            Teams.team_number,
            Teams.nickname,
            Teams.city,
            Teams.state_prov,
            Teams.country,
            Teams.district_key,
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
            district_key=r[5],
            lat=r[6],
            lng=r[7],
        )
        for r in rows
    ]
    return MapTeamsResponse(count=len(teams), teams=teams)


def get_map_events(db: Session, year: int) -> MapEventsResponse:
    """Events for a season year (from event_key), including offseason.

    TBA often omits lat/lng for offseason venues. When missing, fall back to
    another event (or team) in the same city/state/country so they still plot.
    """
    year_prefix = str(year)
    start_as_dt = cast(Events.start_date, DateTime())
    stmt = (
        select(
            Events.event_key,
            Events.name,
            Events.city,
            Events.state_prov,
            Events.country,
            Events.district_key,
            Events.lat,
            Events.lng,
            Events.event_type,
            Events.week,
            Events.start_date,
            Events.end_date,
        )
        .where(func.left(Events.event_key, 4) == year_prefix)
        .order_by(start_as_dt.nulls_last(), Events.event_key)
    )
    rows = db.execute(stmt).all()

    # Location → coords from events that already have them.
    loc_coords: dict[str, Tuple[float, float]] = {}
    for r in rows:
        key = _loc_key(r[2], r[3], r[4])
        lat, lng = r[6], r[7]
        if key and lat is not None and lng is not None and key not in loc_coords:
            loc_coords[key] = (float(lat), float(lng))

    # Fill gaps from teams in the same city when no peer event has coords.
    missing_locs = set()
    for r in rows:
        if r[6] is not None and r[7] is not None:
            continue
        key = _loc_key(r[2], r[3], r[4])
        if key and key not in loc_coords:
            missing_locs.add(key)

    if missing_locs:
        team_stmt = select(Teams.city, Teams.state_prov, Teams.country, Teams.lat, Teams.lng).where(
            Teams.lat.is_not(None),
            Teams.lng.is_not(None),
        )
        for city, state, country, lat, lng in db.execute(team_stmt).all():
            key = _loc_key(city, state, country)
            if key and key in missing_locs and key not in loc_coords:
                loc_coords[key] = (float(lat), float(lng))

    events: List[MapEvent] = []
    for r in rows:
        lat, lng = r[6], r[7]
        if lat is None or lng is None:
            key = _loc_key(r[2], r[3], r[4])
            filled = loc_coords.get(key) if key else None
            if not filled:
                continue
            lat, lng = filled
        events.append(
            MapEvent(
                event_key=r[0],
                name=r[1],
                city=r[2],
                state_prov=r[3],
                country=r[4],
                district_key=r[5],
                lat=float(lat),
                lng=float(lng),
                event_type=r[8],
                week=r[9],
                start_date=r[10],
                end_date=r[11],
            )
        )
    return MapEventsResponse(year=year, count=len(events), events=events)
