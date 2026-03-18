import json
from sqlalchemy.util import NoneType
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import INT, REAL, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from data.models.teams import Teams, _district_match
from query.team_epas import TeamPerfRequest, TeamPerfResponse, TeamPerfInfo, TeamPerfListRequest, TeamPerfListResponse

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
        raw=float(team_epa.raw) if not isinstance(team_epa.raw, NoneType) else None,
        ace=float(team_epa.ace) if not isinstance(team_epa.ace, NoneType) else None,
        confidence=float(team_epa.confidence) if not isinstance(team_epa.confidence, NoneType) else None,
        auto_raw=float(team_epa.auto_raw) if not isinstance(team_epa.auto_raw, NoneType) else None,
        teleop_raw=float(team_epa.teleop_raw) if not isinstance(team_epa.teleop_raw, NoneType) else None,
        endgame_raw=float(team_epa.endgame_raw) if not isinstance(team_epa.endgame_raw, NoneType) else None,
        wins=int(team_epa.wins) if not isinstance(team_epa.wins, NoneType) else None,
        losses=int(team_epa.losses) if not isinstance(team_epa.losses, NoneType) else None,
        ties=int(team_epa.ties) if not isinstance(team_epa.ties, NoneType) else None,
        event_perf=event_perf_raw,
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
    if query.district_key:
        cond = _district_match(Teams.district_key, query.district_key)
        if cond is not None:
            stmt = stmt.join(Teams, TeamEpa.team_number == Teams.team_number).where(cond)
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
