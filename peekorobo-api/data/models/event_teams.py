from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.event_teams import EventTeamsQuery, EventTeamsResponse, EventTeamEntry

class EventTeams(Base):
    __tablename__ = "event_teams"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    nickname : Mapped[str] = mapped_column(Text)
    city : Mapped[str] = mapped_column(Text)
    state_prov : Mapped[str] = mapped_column(Text)
    country : Mapped[str] = mapped_column(Text)

def get_event_teams(db: Session, event_key: str, query: EventTeamsQuery) -> EventTeamsResponse:
    stmt = select(EventTeams).where(EventTeams.event_key == event_key)
    if query.team_number is not None:
        stmt = stmt.where(EventTeams.team_number == query.team_number)
    stmt = stmt.order_by(EventTeams.team_number)
    result = db.scalars(stmt)
    rows = result.all()
    teams = [
        EventTeamEntry(
            team_number=int(r.team_number),
            nickname=(r.nickname or "").strip(),
            city=(r.city or "").strip(),
            state_prov=(r.state_prov or "").strip(),
            country=(r.country or "").strip(),
        )
        for r in rows
    ]
    return EventTeamsResponse(event_key=event_key, teams=teams)
