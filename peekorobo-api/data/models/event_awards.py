from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.event_awards import EventAwardsResponse, AwardData, EventAwardsQuery

class EventAwards(Base):
    __tablename__ = "event_awards"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    award_name : Mapped[str] = mapped_column(Text)

def get_event_awards(db: Session, event_key: str, query: EventAwardsQuery) -> EventAwardsResponse:
    stmt = select(EventAwards).where(EventAwards.event_key == event_key)
    if query.team_number is not None:
        stmt = stmt.where(EventAwards.team_number == query.team_number)
    stmt = stmt.order_by(EventAwards.award_name, EventAwards.team_number)
    result = db.scalars(stmt)
    rows = result.all()
    teams_and_awards = [AwardData(team_number=r.team_number, award_name=r.award_name or "") for r in rows]
    return EventAwardsResponse(event_key=event_key, teams_and_awards=teams_and_awards)
