from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.event_awards import EventAwardsResponse, AwardData, EventAwardsQuery


class EventAwards(Base):
    __tablename__ = "event_awards"

    # Matches Neon / ingest uniqueness: a team can earn multiple awards at one event.
    event_key: Mapped[str] = mapped_column(Text, primary_key=True)
    team_number: Mapped[int] = mapped_column(INT, primary_key=True)
    award_name: Mapped[str] = mapped_column(Text, primary_key=True)


def get_event_awards(db: Session, event_key: str, query: EventAwardsQuery) -> EventAwardsResponse:
    # Column select avoids ORM identity-map collapse if the mapper drifts again.
    stmt = select(
        EventAwards.team_number,
        EventAwards.award_name,
    ).where(EventAwards.event_key == event_key)
    if query.team_number is not None:
        stmt = stmt.where(EventAwards.team_number == query.team_number)
    stmt = stmt.order_by(EventAwards.award_name, EventAwards.team_number)
    rows = db.execute(stmt).all()
    teams_and_awards = [
        AwardData(team_number=team_number, award_name=(award_name or "").strip())
        for team_number, award_name in rows
    ]
    return EventAwardsResponse(event_key=event_key, teams_and_awards=teams_and_awards)
