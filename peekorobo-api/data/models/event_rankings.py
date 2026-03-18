from sqlalchemy import INT, Text, select
from sqlalchemy.orm import mapped_column, Mapped, Session
from data.db import Base
from query.event_rankings import EventRankingsResponse, TeamRankingInfo, EventRankingsQuery

class EventRankings(Base):
    __tablename__ = "event_rankings"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    rank : Mapped[int] = mapped_column(INT)
    wins : Mapped[int] = mapped_column(INT)
    losses : Mapped[int] = mapped_column(INT)
    ties : Mapped[int] = mapped_column(INT)
    dq : Mapped[int] = mapped_column(INT)

def get_event_rankings(db: Session, event_key: str, query: EventRankingsQuery) -> EventRankingsResponse:
    stmt = select(EventRankings).where(EventRankings.event_key == event_key)
    if query.team_number is not None:
        stmt = stmt.where(EventRankings.team_number == query.team_number)
    stmt = stmt.order_by(EventRankings.rank, EventRankings.team_number)
    result = db.scalars(stmt)
    rows = result.all()
    event_rankings = [
        TeamRankingInfo(
            team_number=r.team_number,
            rank=r.rank or 0,
            wins=r.wins or 0,
            losses=r.losses or 0,
            ties=r.ties or 0,
            dq=r.dq or 0,
        )
        for r in rows
    ]
    return EventRankingsResponse(event_key=event_key, event_rankings=event_rankings)
