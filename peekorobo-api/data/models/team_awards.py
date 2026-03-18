from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Session
from data.models.event_awards import EventAwards
from query.team_awards import TeamAwardsResponse, TeamAwardData

def get_team_awards(db: Session, team_number: int) -> TeamAwardsResponse:
    stmt = (
        select(EventAwards)
        .where(EventAwards.team_number == team_number)
        .order_by(EventAwards.event_key, EventAwards.award_name)
    )
    result = db.scalars(stmt)
    rows = result.all()
    awards = [TeamAwardData(event_key=r.event_key, award_name=r.award_name or "") for r in rows]
    return TeamAwardsResponse(team_number=team_number, awards=awards)
