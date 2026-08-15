from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models.events import Events
from data.models.team_epas import TeamEpa
from data.models.teams import Teams
from query.search_index import SearchIndexResponse, SearchTeamEntry


def get_search_index(db: Session) -> SearchIndexResponse:
    """Compact team/event lookup tables for client-side navbar search."""
    last_year_sq = (
        select(
            TeamEpa.team_number.label("team_number"),
            func.max(TeamEpa.year).label("last_year"),
        )
        .group_by(TeamEpa.team_number)
        .subquery()
    )

    team_rows = db.execute(
        select(Teams.team_number, Teams.nickname, last_year_sq.c.last_year)
        .outerjoin(last_year_sq, Teams.team_number == last_year_sq.c.team_number)
        .order_by(Teams.team_number)
    ).all()

    teams: dict[str, SearchTeamEntry] = {}
    for team_number, nickname, last_year in team_rows:
        tn = int(team_number)
        teams[str(tn)] = SearchTeamEntry(
            nickname=str(nickname or ""),
            last_year=int(last_year) if last_year is not None else None,
        )

    event_rows = db.execute(
        select(Events.event_key, Events.name).order_by(Events.event_key)
    ).all()

    events: dict[str, str] = {
        str(event_key): str(name or "") for event_key, name in event_rows
    }

    return SearchIndexResponse(teams=teams, events=events)
