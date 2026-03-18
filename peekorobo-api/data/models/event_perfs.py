import json
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from data.models.event_teams import EventTeams
from data.models.team_epas import TeamEpa
from query.event_perfs import EventPerfsResponse, EventPerfInfo


def _extract_year(event_key: str) -> Optional[int]:
    """Extract year from event_key (e.g. 2024cmp -> 2024)."""
    if not event_key or len(event_key) < 4:
        return None
    try:
        return int(event_key[:4])
    except ValueError:
        return None


def get_event_perfs(db: Session, event_key: str) -> EventPerfsResponse:
    year = _extract_year(event_key)
    if year is None:
        return EventPerfsResponse(event_key=event_key, perfs=[])

    # Get teams at this event
    teams_stmt = select(EventTeams.team_number).where(EventTeams.event_key == event_key)
    team_numbers = [r for r in db.scalars(teams_stmt).all()]

    if not team_numbers:
        return EventPerfsResponse(event_key=event_key, perfs=[])

    # Get team_epas for these teams in this year
    stmt = (
        select(TeamEpa)
        .where(and_(TeamEpa.year == year, TeamEpa.team_number.in_(team_numbers)))
    )
    rows = db.scalars(stmt).all()

    perfs = []
    for row in rows:
        event_perf_raw = row.event_perf
        if event_perf_raw is None:
            continue
        if isinstance(event_perf_raw, str):
            try:
                event_perf_raw = json.loads(event_perf_raw)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(event_perf_raw, list):
            continue

        # Find the entry for this event_key
        for obj in event_perf_raw:
            if not isinstance(obj, dict):
                continue
            if obj.get("event_key") != event_key:
                continue
            perfs.append(
                EventPerfInfo(
                    team_number=row.team_number,
                    event_key=event_key,
                    raw=obj.get("raw"),
                    ace=obj.get("ace"),
                    confidence=obj.get("confidence"),
                    auto_raw=obj.get("auto_raw"),
                    teleop_raw=obj.get("teleop_raw"),
                    endgame_raw=obj.get("endgame_raw"),
                )
            )
            break

    # Sort by ace descending (best first)
    perfs.sort(key=lambda p: (p.ace if p.ace is not None else 0), reverse=True)

    return EventPerfsResponse(event_key=event_key, perfs=perfs)
