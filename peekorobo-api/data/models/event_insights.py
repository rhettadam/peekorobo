import math
from collections import defaultdict
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.event_teams import EventTeams
from data.models.team_epas import TeamEpa
from query.event_insights import EventInsightRow, EventInsightsResponse


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


def get_event_insights(db: Session, year: int) -> EventInsightsResponse:
    """Season-wide per-event ACE statistics.

    For every event in the season, aggregate the season ACE of its participating
    teams into a single summary row (max / top-8 / top-24 / mean / median / IQR /
    std dev). Mirrors the legacy Dash "Event Insights" table. Metadata (name,
    week, district, ...) is left to the client, which already has the events list.
    """
    # team_number -> season ACE for this year
    epa_rows = db.execute(
        select(TeamEpa.team_number, TeamEpa.ace).where(TeamEpa.year == year)
    ).all()
    ace_by_team = {int(tn): float(ace) for tn, ace in epa_rows if ace is not None}

    # event_key -> list of participating team numbers (this season's events)
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
        aces = sorted(ace_by_team[tn] for tn in team_list if tn in ace_by_team)
        if not aces:
            continue
        n = len(aces)
        desc = aces[::-1]
        mean_ace = sum(aces) / n
        top8 = sum(desc[:8]) / min(8, n)
        top24 = sum(desc[:24]) / min(24, n)
        variance = sum((x - mean_ace) ** 2 for x in aces) / n
        rows.append(
            EventInsightRow(
                event_key=event_key,
                team_count=len(team_list),
                max_ace=round(aces[-1], 2),
                top8_ace=round(top8, 2),
                top24_ace=round(top24, 2),
                mean_ace=round(mean_ace, 2),
                median_ace=round(_percentile(aces, 50), 2),
                iqr_ace=round(_percentile(aces, 75) - _percentile(aces, 25), 2),
                std_ace=round(math.sqrt(variance), 2),
            )
        )

    rows.sort(key=lambda r: r.top8_ace, reverse=True)
    return EventInsightsResponse(year=year, events=rows)
