from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from data.models.event_matches import EventMatch
from data.models.event_teams import EventTeams
from data.models.events import Events
from query.season_summary import SeasonSummaryResponse


def get_season_summary(db: Session, year: int) -> SeasonSummaryResponse:
    """Season-wide totals in a few cheap COUNT queries.

    Event keys are prefixed with the season year in TBA format (e.g. ``2024cmp``),
    so a ``LIKE '{year}%'`` scan matches the pattern used by ``event_insights`` and
    the legacy ``count_season_matches`` helper. Teams are counted distinctly across
    every event that season (teams that actually competed).
    """
    prefix = f"{year}%"
    team_count = db.scalar(
        select(func.count(distinct(EventTeams.team_number))).where(
            EventTeams.event_key.like(prefix)
        )
    )
    event_count = db.scalar(
        select(func.count()).select_from(Events).where(Events.event_key.like(prefix))
    )
    match_count = db.scalar(
        select(func.count())
        .select_from(EventMatch)
        .where(EventMatch.event_key.like(prefix))
    )
    return SeasonSummaryResponse(
        year=year,
        team_count=int(team_count or 0),
        event_count=int(event_count or 0),
        match_count=int(match_count or 0),
    )
