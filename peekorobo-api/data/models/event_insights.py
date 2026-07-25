import json
import math
from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.event_teams import EventTeams
from data.models.team_epas import TeamEpa
from query.event_insights import EventInsightRow, EventInsightsResponse

# ace only (components removed from event insights)
TeamAce = Optional[float]


def _percentile(sorted_asc: List[float], p: float) -> float:
    """Linear-interpolation percentile, matching numpy's default 'linear' method."""
    n = len(sorted_asc)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_asc[0]
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_asc[int(k)]
    return sorted_asc[f] + (sorted_asc[c] - sorted_asc[f]) * (k - f)


def _parse_event_perf(raw) -> List[dict]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(raw, list):
        return []
    return [obj for obj in raw if isinstance(obj, dict)]


def _f(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _row_from_aces(
    event_key: str,
    roster_count: int,
    aces: List[float],
    source: str,
) -> Optional[EventInsightRow]:
    if not aces:
        return None
    n = len(aces)
    aces_sorted = sorted(aces)
    desc = aces_sorted[::-1]
    mean_ace = sum(aces_sorted) / n
    top8 = sum(desc[:8]) / min(8, n)
    top24 = sum(desc[:24]) / min(24, n)
    variance = sum((x - mean_ace) ** 2 for x in aces_sorted) / n
    return EventInsightRow(
        event_key=event_key,
        team_count=roster_count,
        max_ace=round(aces_sorted[-1], 2),
        top8_ace=round(top8, 2),
        top24_ace=round(top24, 2),
        mean_ace=round(mean_ace, 2),
        median_ace=round(_percentile(aces_sorted, 50), 2),
        iqr_ace=round(_percentile(aces_sorted, 75) - _percentile(aces_sorted, 25), 2),
        std_ace=round(math.sqrt(variance), 2),
        source=source,  # type: ignore[arg-type]
    )


def get_event_insights(db: Session, year: int) -> EventInsightsResponse:
    """Per-event ACE statistics for a season.

    Prefer each team's **event ACE** (from ``team_epas.event_perf``) when an
    event has any event-perf rows. Otherwise fall back to season totals for
    teams on that event's roster. Metadata (name, week, district, ...) stays
    on the client via the events list.
    """
    epa_rows = db.execute(
        select(
            TeamEpa.team_number,
            TeamEpa.ace,
            TeamEpa.event_perf,
        ).where(TeamEpa.year == year)
    ).all()

    season_by_team: Dict[int, TeamAce] = {}
    # event_key -> team_number -> ace
    event_by_key: Dict[str, Dict[int, float]] = defaultdict(dict)

    for tn, ace, event_perf in epa_rows:
        team = int(tn)
        season_by_team[team] = _f(ace)
        for obj in _parse_event_perf(event_perf):
            ek = obj.get("event_key")
            if not ek or not str(ek).startswith(str(year)):
                continue
            event_ace = _f(obj.get("ace"))
            if event_ace is None:
                continue
            event_by_key[str(ek)][team] = event_ace

    et_rows = db.execute(
        select(EventTeams.event_key, EventTeams.team_number).where(
            EventTeams.event_key.like(f"{year}%")
        )
    ).all()
    teams_by_event: dict[str, List[int]] = defaultdict(list)
    for event_key, team_number in et_rows:
        teams_by_event[event_key].append(int(team_number))

    rows: List[EventInsightRow] = []
    for event_key, team_list in teams_by_event.items():
        event_aces = event_by_key.get(event_key) or {}
        if event_aces:
            aces = list(event_aces.values())
            source = "event"
        else:
            aces = [a for tn in team_list if (a := season_by_team.get(tn)) is not None]
            source = "season"
        row = _row_from_aces(event_key, len(team_list), aces, source)
        if row:
            rows.append(row)

    rows.sort(key=lambda r: r.top8_ace, reverse=True)
    return EventInsightsResponse(year=year, events=rows)
