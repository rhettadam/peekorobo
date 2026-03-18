from sqlalchemy import select
from sqlalchemy.orm import Session
from data.models.event_teams import EventTeams
from data.models.events import Events, _district_match
from query.team_events import TeamEventsResponse, TeamEventsQuery

def get_team_events(db: Session, team_number: int, query: TeamEventsQuery) -> TeamEventsResponse:
    stmt = (
        select(EventTeams.event_key)
        .outerjoin(Events, EventTeams.event_key == Events.event_key)
        .where(EventTeams.team_number == team_number)
    )
    if query.year is not None:
        stmt = stmt.where(EventTeams.event_key.like(f"{query.year}%"))
    if query.district_key:
        cond = _district_match(Events.district_key, query.district_key)
        if cond is not None:
            stmt = stmt.where(cond)
    stmt = stmt.order_by(Events.start_date, EventTeams.event_key)
    result = db.scalars(stmt)
    event_keys = result.all()
    return TeamEventsResponse(team_number=team_number, events=event_keys)
