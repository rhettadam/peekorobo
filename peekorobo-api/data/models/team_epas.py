import json
from typing import Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import INT, REAL, select, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from data.models.teams import Teams, _district_match
from query.team_epas import TeamPerfRequest, TeamPerfResponse, TeamPerfInfo, TeamPerfListRequest, TeamPerfListResponse


def _as_float(value) -> Optional[float]:
    return float(value) if value is not None else None


def _as_int(value) -> Optional[int]:
    return int(value) if value is not None else None


class TeamEpa(Base):
    __tablename__ = "team_epas"

    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    year : Mapped[int] = mapped_column(INT, primary_key=True)
    raw : Mapped[float] = mapped_column(REAL)
    ace : Mapped[float] = mapped_column(REAL)
    confidence : Mapped[float] = mapped_column(REAL)
    auto_raw : Mapped[float] = mapped_column(REAL)
    teleop_raw : Mapped[float] = mapped_column(REAL)
    endgame_raw : Mapped[float] = mapped_column(REAL)
    wins : Mapped[int] = mapped_column(INT)
    losses : Mapped[int] = mapped_column(INT)
    event_perf : Mapped[JSONB] = mapped_column(JSONB)
    ties : Mapped[int] = mapped_column(INT)
    rank_global : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    rank_country : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    rank_state : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    rank_district : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    count_global : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    count_country : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    count_state : Mapped[Optional[int]] = mapped_column(INT, nullable=True)
    count_district : Mapped[Optional[int]] = mapped_column(INT, nullable=True)

def from_db_row(team_epa : TeamEpa) -> TeamPerfInfo:
    event_perf_raw = team_epa.event_perf
    if event_perf_raw is None:
        event_perf_raw = []
    elif isinstance(event_perf_raw, str):
        try:
            event_perf_raw = json.loads(event_perf_raw)
        except (json.JSONDecodeError, TypeError):
            event_perf_raw = []
    if not isinstance(event_perf_raw, list):
        event_perf_raw = []
    return TeamPerfInfo(
        year=team_epa.year.numerator,
        raw=_as_float(team_epa.raw),
        ace=_as_float(team_epa.ace),
        confidence=_as_float(team_epa.confidence),
        auto_raw=_as_float(team_epa.auto_raw),
        teleop_raw=_as_float(team_epa.teleop_raw),
        endgame_raw=_as_float(team_epa.endgame_raw),
        wins=_as_int(team_epa.wins),
        losses=_as_int(team_epa.losses),
        ties=_as_int(team_epa.ties),
        event_perf=event_perf_raw,
        rank_global=_as_int(team_epa.rank_global),
        rank_country=_as_int(team_epa.rank_country),
        rank_state=_as_int(team_epa.rank_state),
        rank_district=_as_int(team_epa.rank_district),
        count_global=_as_int(team_epa.count_global),
        count_country=_as_int(team_epa.count_country),
        count_state=_as_int(team_epa.count_state),
        count_district=_as_int(team_epa.count_district),
    )

def get_team_epa(db : Session, team_number : int, query: TeamPerfRequest) -> TeamPerfResponse:
    where_args = []
    if query.year:
        where_args.append(TeamEpa.year == query.year)
    where_args.append(TeamEpa.team_number == team_number)
    stmt = select(TeamEpa).where(*where_args)
    result = db.scalars(stmt)
    perfs = list(map(from_db_row, result.all()))
    return TeamPerfResponse(team_number=team_number, team_perfs=perfs)

def get_team_perfs_list(db: Session, query: TeamPerfListRequest) -> TeamPerfListResponse:
    stmt = select(TeamEpa).where(TeamEpa.year == query.year)
    needs_teams_join = query.city or query.state_prov or query.country or query.district_key
    if needs_teams_join:
        stmt = stmt.join(Teams, TeamEpa.team_number == Teams.team_number)
        if query.city:
            stmt = stmt.where(func.lower(Teams.city) == func.lower(query.city))
        if query.state_prov:
            stmt = stmt.where(func.lower(Teams.state_prov) == func.lower(query.state_prov))
        if query.country:
            stmt = stmt.where(func.lower(Teams.country) == func.lower(query.country))
        if query.district_key:
            cond = _district_match(Teams.district_key, query.district_key)
            if cond is not None:
                stmt = stmt.where(cond)
    # Fast "top N" path for the leaderboard preview: order by ACE descending
    # (nulls last) and return the top `limit` with no cursor. We sort by ACE
    # rather than rank_global because ranks aren't computed for the in-progress
    # season, whereas ACE is always populated.
    if query.sort == "rank":
        stmt = stmt.order_by(
            TeamEpa.ace.is_(None), TeamEpa.ace.desc(), TeamEpa.team_number
        ).limit(query.limit)
        rows = db.scalars(stmt).all()
        team_perfs_list = [
            TeamPerfResponse(team_number=r.team_number, team_perfs=[from_db_row(r)])
            for r in rows
        ]
        return TeamPerfListResponse(team_perfs=team_perfs_list, next=None)

    if query.next_team_number is not None:
        stmt = stmt.where(TeamEpa.team_number > query.next_team_number)
    stmt = stmt.order_by(TeamEpa.team_number).limit(query.limit + 1)
    result = db.scalars(stmt)
    rows = result.all()
    team_perfs_list = [
        TeamPerfResponse(team_number=r.team_number, team_perfs=[from_db_row(r)])
        for r in rows[: query.limit]
    ]
    next_val = rows[query.limit].team_number if len(rows) > query.limit else None
    return TeamPerfListResponse(team_perfs=team_perfs_list, next=next_val)
