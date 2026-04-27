import json
from sqlalchemy import Text, select, ScalarResult, or_, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, Session
from typing import List, Optional, Any
from data.db import Base
from query.teams import TeamQuery, TeamResponse, TeamData

def _district_match(column, district_key: str):
    """Match district_key (handles 2024fim or FIM format)."""
    dk = (district_key or "").strip()
    if not dk:
        return None
    if len(dk) > 4 and dk[:4].isdigit():
        return column.ilike(dk)
    return or_(
        column.ilike(dk),
        (func.length(column) > 4) & (func.substring(column, 5).ilike(dk)),
    )

class Teams(Base):
    __tablename__="teams"

    team_number : Mapped[int] = mapped_column(primary_key=True)
    nickname : Mapped[str] = mapped_column(Text)
    city : Mapped[str] = mapped_column(Text)
    state_prov : Mapped[str] = mapped_column(Text)
    country : Mapped[str] = mapped_column(Text)
    website : Mapped[str] = mapped_column(Text)
    district_key : Mapped[Optional[str]] = mapped_column(Text)
    team_colors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

def to_team_response(input : Teams) -> TeamData:
    tc = input.team_colors
    if isinstance(tc, str):
        try:
            tc = json.loads(tc)
        except (json.JSONDecodeError, TypeError):
            tc = None
    if tc is not None and not isinstance(tc, dict):
        tc = None
    return TeamData(team_number=input.team_number.numerator,
                    nickname=str(input.nickname),
                    state_prov=str(input.state_prov),
                    city=str(input.city),
                    country=str(input.country),
                    website=str(input.website),
                    district_key=input.district_key,
                    team_colors=tc)
    
def get_teams(db : Session, query : TeamQuery) -> TeamResponse:
    whereargs = []
    stmt = select(Teams)
    if query.year is not None:
        from data.models.team_epas import TeamEpa
        stmt = stmt.join(TeamEpa, Teams.team_number == TeamEpa.team_number).where(TeamEpa.year == query.year)
    if query.city:
        whereargs.append(func.lower(Teams.city) == func.lower(query.city))
    if query.state_prov:
        whereargs.append(func.lower(Teams.state_prov) == func.lower(query.state_prov))
    if query.country:
        whereargs.append(func.lower(Teams.country) == func.lower(query.country))
    if query.district_key:
        cond = _district_match(Teams.district_key, query.district_key)
        if cond is not None:
            whereargs.append(cond)
    if query.team_number:
        whereargs.append(Teams.team_number == query.team_number)
    if query.next_team_number:
        whereargs.append(Teams.team_number > query.next_team_number)
    if whereargs:
        stmt = stmt.where(*whereargs)
    stmt = stmt.limit(query.limit).order_by(Teams.team_number)
    result : ScalarResult[Teams] = db.scalars(stmt)
    team_infos : List[TeamData] = list(map(to_team_response, result.all()))
    last_id : Optional[int] = None
    if len(team_infos) > 0:
        last_id = team_infos[-1].team_number
    db.commit()
    return TeamResponse(team_info=team_infos, next=last_id)
