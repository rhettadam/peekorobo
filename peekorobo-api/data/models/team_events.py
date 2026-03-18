from sqlalchemy import select
from sqlalchemy.orm import Session
from data.models.event_teams import EventTeams
from query.team_events import TeamEventsResponse, TeamEventsQuery

def get_team_events(db: Session, team_number: int, query: TeamEventsQuery) -> TeamEventsResponse:
    stmt = (
        select(EventTeams.event_key)
        .where(EventTeams.team_number == team_number)
    )
    if query.year is not None:
        stmt = stmt.where(EventTeams.event_key.like(f"{query.year}%"))
    stmt = stmt.order_by(EventTeams.event_key)
    result = db.scalars(stmt)
    event_keys = result.all()
    return TeamEventsResponse(team_number=team_number, events=event_keys)
