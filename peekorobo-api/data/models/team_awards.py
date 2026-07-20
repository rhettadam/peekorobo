from sqlalchemy import select
from sqlalchemy.orm import Session
from data.models.event_awards import EventAwards
from data.models.events import Events, _district_match
from query.team_awards import TeamAwardsResponse, TeamAwardData, TeamAwardsQuery


def get_team_awards(db: Session, team_number: int, query: TeamAwardsQuery) -> TeamAwardsResponse:
    # Column select: return every DB row. Do not collapse by award "kind" or year.
    stmt = select(
        EventAwards.event_key,
        EventAwards.award_name,
    ).where(EventAwards.team_number == team_number)
    if query.year is not None:
        stmt = stmt.where(EventAwards.event_key.like(f"{query.year}%"))
    if query.district_key:
        cond = _district_match(Events.district_key, query.district_key)
        if cond is not None:
            stmt = stmt.join(Events, EventAwards.event_key == Events.event_key).where(cond)
    stmt = stmt.order_by(EventAwards.event_key, EventAwards.award_name)
    rows = db.execute(stmt).all()

    # Exact duplicate rows only (bad imports). Keep multiple awards per event / multiple
    # Chairman's across events and years.
    seen: set[tuple[str, str]] = set()
    awards: list[TeamAwardData] = []
    for event_key, award_name in rows:
        ek = (event_key or "").strip()
        an = (award_name or "").strip()
        key = (ek, an)
        if key in seen:
            continue
        seen.add(key)
        awards.append(TeamAwardData(event_key=ek, award_name=an))
    return TeamAwardsResponse(team_number=team_number, awards=awards)
