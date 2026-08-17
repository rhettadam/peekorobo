from typing import Optional, List, Dict, Any
from sqlalchemy import Text, INT, select, or_, case, func
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSONB
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from data.models.events import Events
from query.event_matches import (
    EventMatchesRequest,
    EventMatchResponse,
    MatchResponse,
    TeamMatchRating,
    TeamMatchRatingsResponse,
)


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
    red_predicted_score: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    blue_predicted_score: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    pre_match_teams: Mapped[Optional[dict]] = mapped_column(JSONB)


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
            red_predicted_score=r.red_predicted_score,
            blue_predicted_score=r.blue_predicted_score,
            pre_match_teams=r.pre_match_teams,
        )
        for r in rows
    ]
    return EventMatchResponse(event_key=event_key, matches=matches)


def _compact_floats(raw: Any) -> Optional[Dict[str, float]]:
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    out: Dict[str, float] = {}
    for key in ("a", "t", "e", "r", "c", "ace"):
        val = raw.get(key)
        if isinstance(val, (int, float)):
            out[key] = float(val)
    return out if "ace" in out else None


def get_team_match_ratings(db: Session, team_number: int, year: int) -> TeamMatchRatingsResponse:
    """Walk-forward ACE components for one team in one season.

    Extracts only this team's compact JSONB object in SQL so the API does not
    ship six-robot payloads or other matches at the event.
    """
    team_key = str(int(team_number))
    rating_col = EventMatch.pre_match_teams.op("->")(team_key)
    level_ord = case(
        (EventMatch.comp_level == "qm", 0),
        (EventMatch.comp_level == "ef", 1),
        (EventMatch.comp_level == "qf", 2),
        (EventMatch.comp_level == "sf", 3),
        (EventMatch.comp_level == "f", 4),
        else_=9,
    )
    stmt = (
        select(
            EventMatch.match_key,
            EventMatch.event_key,
            EventMatch.comp_level,
            EventMatch.match_number,
            EventMatch.set_number,
            EventMatch.red_score,
            EventMatch.blue_score,
            EventMatch.winning_alliance,
            rating_col.label("rating"),
        )
        .select_from(EventMatch)
        .outerjoin(Events, Events.event_key == EventMatch.event_key)
        .where(
            func.left(EventMatch.event_key, 4) == str(year),
            or_(*_team_in_list(team_number)),
            rating_col.is_not(None),
        )
        .order_by(
            Events.start_date.nulls_last(),
            EventMatch.event_key,
            level_ord,
            EventMatch.set_number,
            EventMatch.match_number,
        )
    )
    matches: List[TeamMatchRating] = []
    for row in db.execute(stmt).all():
        compact = _compact_floats(row.rating)
        if not compact:
            continue
        played = (
            (row.red_score or 0) > 0
            or (row.blue_score or 0) > 0
            or (row.winning_alliance or "") in ("red", "blue")
        )
        matches.append(
            TeamMatchRating(
                match_key=row.match_key or "",
                event_key=row.event_key or "",
                comp_level=row.comp_level or "",
                match_number=row.match_number or 0,
                set_number=row.set_number or 0,
                played=played,
                a=compact.get("a"),
                t=compact.get("t"),
                e=compact.get("e"),
                r=compact.get("r"),
                c=compact.get("c"),
                ace=compact.get("ace"),
            )
        )
    return TeamMatchRatingsResponse(team_number=team_number, year=year, matches=matches)
