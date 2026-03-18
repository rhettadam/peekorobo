from typing import Optional, List
from sqlalchemy import Text, INT, select, or_
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.event_matches import EventMatchesRequest, EventMatchResponse, MatchResponse


def _team_in_list(team: int) -> List:
    """Build OR conditions for team number in comma-separated list."""
    t = str(team)
    return [
        EventMatch.red_teams == t,
        EventMatch.red_teams.like(f"{t},%"),
        EventMatch.red_teams.like(f"%,{t},%"),
        EventMatch.red_teams.like(f"%,{t}"),
        EventMatch.blue_teams == t,
        EventMatch.blue_teams.like(f"{t},%"),
        EventMatch.blue_teams.like(f"%,{t},%"),
        EventMatch.blue_teams.like(f"%,{t}"),
    ]


def _parse_team_list(s: Optional[str]) -> List[int]:
    if not s or not s.strip():
        return []
    return [int(t.strip()) for t in s.split(",") if t.strip().isdigit()]


class EventMatch(Base):
    __tablename__ = "event_matches"

    match_key: Mapped[str] = mapped_column(Text, primary_key=True)
    event_key: Mapped[Optional[str]] = mapped_column(Text)
    comp_level: Mapped[Optional[str]] = mapped_column(Text)
    match_number: Mapped[Optional[int]] = mapped_column(INT)
    set_number: Mapped[Optional[int]] = mapped_column(INT)
    red_teams: Mapped[Optional[str]] = mapped_column(Text)
    blue_teams: Mapped[Optional[str]] = mapped_column(Text)
    red_score: Mapped[Optional[int]] = mapped_column(INT)
    blue_score: Mapped[Optional[int]] = mapped_column(INT)
    winning_alliance: Mapped[Optional[str]] = mapped_column(Text)
    youtube_key: Mapped[Optional[str]] = mapped_column(Text)
    predicted_time: Mapped[Optional[int]] = mapped_column(INT)
    red_win_prob: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    blue_win_prob: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)


def get_event_matches(db: Session, event_key: str, query: EventMatchesRequest) -> EventMatchResponse:
    stmt = select(EventMatch).where(EventMatch.event_key == event_key)
    if query.team_number is not None:
        try:
            team_num = int(query.team_number)
            stmt = stmt.where(or_(*_team_in_list(team_num)))
        except (ValueError, TypeError):
            pass
    if query.match_key is not None:
        stmt = stmt.where(EventMatch.match_key == query.match_key)
    stmt = stmt.order_by(EventMatch.comp_level, EventMatch.set_number, EventMatch.match_number)
    result = db.scalars(stmt)
    rows = result.all()
    matches = [
        MatchResponse(
            match_key=r.match_key or "",
            comp_level=r.comp_level or "",
            match_number=r.match_number or 0,
            set_number=r.set_number or 0,
            red_teams=_parse_team_list(r.red_teams),
            blue_teams=_parse_team_list(r.blue_teams),
            red_score=r.red_score or 0,
            blue_score=r.blue_score or 0,
            winning_alliance=r.winning_alliance or "",
            youtube_key=r.youtube_key,
            predicted_time=r.predicted_time,
            red_win_prob=r.red_win_prob,
            blue_win_prob=r.blue_win_prob,
        )
        for r in rows
    ]
    return EventMatchResponse(event_key=event_key, matches=matches)
