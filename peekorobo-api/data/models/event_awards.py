from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.event_awards import EventAwardsResponse, AwardData

class EventAwards(Base):
    __tablename__ = "event_awards"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    award_name : Mapped[str] = mapped_column(Text)

def get_event_awards(db: Session, event_key: str) -> EventAwardsResponse:
    stmt = select(EventAwards).where(EventAwards.event_key == event_key).order_by(EventAwards.team_number, EventAwards.award_name)
    result = db.scalars(stmt)
    rows = result.all()
    teams_and_awards = [AwardData(team_number=r.team_number, award_name=r.award_name or "") for r in rows]
    return EventAwardsResponse(event_key=event_key, teams_and_awards=teams_and_awards)
