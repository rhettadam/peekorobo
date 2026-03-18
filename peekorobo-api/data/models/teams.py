from sqlalchemy import Text, select, ScalarResult, or_, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from typing import List, Optional
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

def to_team_response(input : Teams) -> TeamData:
    return TeamData(team_number=input.team_number.numerator,
                    nickname=str(input.nickname),
                    state_prov=str(input.state_prov),
                    city=str(input.city),
                    country=str(input.country),
                    website=str(input.website),
                    district_key=input.district_key)
    
def get_teams(db : Session, query : TeamQuery) -> TeamResponse:
    whereargs = []
    if query.city:
        whereargs.append(Teams.city == query.city)
    if query.state_prov:
        whereargs.append(Teams.state_prov == query.state_prov)
    if query.country:
        whereargs.append(Teams.country == query.country)
    if query.district_key:
        cond = _district_match(Teams.district_key, query.district_key)
        if cond is not None:
            whereargs.append(cond)
    if query.team_number:
        whereargs.append(Teams.team_number == query.team_number)
    if query.next_team_number:
        whereargs.append(Teams.team_number > query.next_team_number)
    stmt = select(Teams).where(*whereargs).limit(query.limit).order_by(Teams.team_number)
    result : ScalarResult[Teams] = db.scalars(stmt)
    team_infos : List[TeamData] = list(map(to_team_response, result.all()))
    last_id : Optional[int] = None
    if len(team_infos) > 0:
        last_id = team_infos[-1].team_number
    db.commit()
    return TeamResponse(team_info=team_infos, next=last_id)
