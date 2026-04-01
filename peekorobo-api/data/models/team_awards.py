from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Session
from data.models.event_awards import EventAwards
from data.models.events import Events, _district_match
from query.team_awards import TeamAwardsResponse, TeamAwardData, TeamAwardsQuery

def get_team_awards(db: Session, team_number: int, query: TeamAwardsQuery) -> TeamAwardsResponse:
    stmt = (
        select(EventAwards)
        .where(EventAwards.team_number == team_number)
    )
    if query.year is not None:
        stmt = stmt.where(EventAwards.event_key.like(f"{query.year}%"))
    if query.district_key:
        cond = _district_match(Events.district_key, query.district_key)
        if cond is not None:
            stmt = stmt.join(Events, EventAwards.event_key == Events.event_key).where(cond)
    stmt = stmt.order_by(EventAwards.event_key, EventAwards.award_name)
    result = db.scalars(stmt)
    rows = result.all()
    # De-dupe (event_key, award_name): duplicate rows can appear from bad imports or ORM/DB quirks.
    seen: set[tuple[str, str]] = set()
    awards: list[TeamAwardData] = []
    for r in rows:
        ek = (r.event_key or "").strip()
        an = (r.award_name or "").strip()
        key = (ek, an)
        if key in seen:
            continue
        seen.add(key)
        awards.append(TeamAwardData(event_key=ek, award_name=an))
    return TeamAwardsResponse(team_number=team_number, awards=awards)
