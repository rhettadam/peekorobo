from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Session
from data.models.event_awards import EventAwards
from query.team_awards import TeamAwardsResponse, TeamAwardData, TeamAwardsQuery

def get_team_awards(db: Session, team_number: int, query: TeamAwardsQuery) -> TeamAwardsResponse:
    stmt = (
        select(EventAwards)
        .where(EventAwards.team_number == team_number)
    )
    if query.year is not None:
        stmt = stmt.where(EventAwards.event_key.like(f"{query.year}%"))
    stmt = stmt.order_by(EventAwards.event_key, EventAwards.award_name)
    result = db.scalars(stmt)
    rows = result.all()
    awards = [TeamAwardData(event_key=r.event_key, award_name=r.award_name or "") for r in rows]
    return TeamAwardsResponse(team_number=team_number, awards=awards)
