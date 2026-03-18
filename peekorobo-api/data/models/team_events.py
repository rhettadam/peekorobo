from sqlalchemy import select
from sqlalchemy.orm import Session
from data.models.event_teams import EventTeams
from query.team_events import TeamEventsResponse

def get_team_events(db: Session, team_number: int) -> TeamEventsResponse:
    stmt = (
        select(EventTeams.event_key)
        .where(EventTeams.team_number == team_number)
        .order_by(EventTeams.event_key)
    )
    result = db.scalars(stmt)
    event_keys = result.all()
    return TeamEventsResponse(team_number=team_number, events=event_keys)
