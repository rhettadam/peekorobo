from sqlalchemy.util import NoneType
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import INT, REAL, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from data.db import Base
from query.team_epas import TeamEpaRequest, TeamEpaResponse, TeamEpaInfo

class TeamEpa(Base):
    __tablename__ = "team_epas"

    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    year : Mapped[int] = mapped_column(INT, primary_key=True)
    normal_epa : Mapped[float] = mapped_column(REAL)
    epa : Mapped[float] = mapped_column(REAL)
    confidence : Mapped[float] = mapped_column(REAL)
    auto_epa : Mapped[float] = mapped_column(REAL)
    teleop_epa : Mapped[float] = mapped_column(REAL)
    endgame_epa : Mapped[float] = mapped_column(REAL)
    wins : Mapped[int] = mapped_column(INT)
    losses : Mapped[int] = mapped_column(INT)
    event_epas : Mapped[JSONB] = mapped_column(JSONB)
    ties : Mapped[int] = mapped_column(INT)

def from_db_row(team_epa : TeamEpa) -> TeamEpaInfo:
    return TeamEpaInfo(       
        year = team_epa.year.numerator,
        normal_epa = float(team_epa.normal_epa) if not isinstance(team_epa.normal_epa, NoneType) else None,
        epa=float(team_epa.epa) if not isinstance(team_epa.epa, NoneType) else None,
        confidence=float(team_epa.confidence) if not isinstance(team_epa.confidence, NoneType) else None,
        auto_epa=float(team_epa.auto_epa) if not isinstance(team_epa.auto_epa, NoneType) else None,
        teleop_epa=float(team_epa.teleop_epa) if not isinstance(team_epa.teleop_epa, NoneType) else None,
        endgame_epa=float(team_epa.endgame_epa) if not isinstance(team_epa.endgame_epa, NoneType) else None,
        wins=int(team_epa.wins) if not isinstance(team_epa.wins, NoneType) else None,
        losses=int(team_epa.losses) if not isinstance(team_epa.losses, NoneType) else None,
        ties=int(team_epa.ties) if not isinstance(team_epa.ties, NoneType) else None
    )

def get_team_epa(db : Session, team_number : int, query: TeamEpaRequest) -> TeamEpaResponse:
    where_args = []
    if query.year:
        where_args.append(TeamEpa.year == query.year)
    where_args.append(TeamEpa.team_number == team_number)
    stmt = select(TeamEpa).where(*where_args)
    result = db.scalars(stmt)
    epa_infos = list(map(from_db_row, result.all()))
    return TeamEpaResponse(team_number=team_number,team_epa_infos=epa_infos)
