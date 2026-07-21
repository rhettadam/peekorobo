"""Career / all-time Insights aggregates for the Overall Insights page."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from itertools import combinations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from data.db import SessionLocal
from data.models.event_teams import EventTeams
from data.models.notables import Notables
from query.insights_overview import (
    AccuracyPoint,
    InsightsOverviewResponse,
    LeaderRow,
    PredBucket,
    PredSummary,
    PredictionStats,
    TeamupRow,
    YearSeriesPoint,
)

LEADER_LIMIT = 12
TEAMUP_LIMIT = 12
_YEAR_FILTER = "event_key ~ '^[0-9]{4}'"
# Overview changes only when the data pipeline runs; keep a long process cache.
_CACHE_TTL_SEC = 3600.0
_cache_payload: InsightsOverviewResponse | None = None
_cache_at: float = 0.0

WINNER_RE = re.compile(r"\b(?:winners?|champions?)\b", re.I)
FINALIST_RE = re.compile(r"finalists?", re.I)

REGIONAL_TYPES = {"Regional"}
DISTRICT_TYPES = {"District", "District Championship", "District Championship Division"}
DCMP_TYPES = {"District Championship", "District Championship Division"}
DIVISION_TYPES = {"Championship Division"}
TEAMUP_EVENT_TYPES = {
    "Regional",
    "District",
    "District Championship",
    "District Championship Division",
    "Championship Division",
    "Championship Finals",
    "Festival of Champions",
}
IMPACT_REGIONAL_DCMP_TYPES = REGIONAL_TYPES | DCMP_TYPES

_PRED_MATERIALIZED_CTE = """
WITH pred AS MATERIALIZED (
  SELECT
    CAST(LEFT(m.event_key, 4) AS INT) AS year,
    COALESCE(m.comp_level, '') AS comp_level,
    m.red_win_prob,
    m.winning_alliance,
    COALESCE(e.event_type, 'Unknown') AS event_type,
    CASE
      WHEN m.winning_alliance = 'red' THEN 1.0
      WHEN m.winning_alliance = 'blue' THEN 0.0
      ELSE 0.5
    END AS red_outcome,
    CASE
      WHEN m.winning_alliance = 'red' AND m.red_win_prob > 0.5 THEN 1
      WHEN m.winning_alliance = 'blue' AND m.red_win_prob < 0.5 THEN 1
      WHEN COALESCE(m.winning_alliance, '') NOT IN ('red', 'blue')
           AND m.red_win_prob = 0.5 THEN 1
      ELSE 0
    END AS is_correct,
    ABS(m.red_win_prob - 0.5) AS edge,
    CASE
      WHEN m.red_win_prob > 0.5 THEN 'red'
      WHEN m.red_win_prob < 0.5 THEN 'blue'
      ELSE 'toss'
    END AS favorite
  FROM event_matches m
  LEFT JOIN events e ON e.event_key = m.event_key
  WHERE m.red_win_prob IS NOT NULL
    AND m.event_key ~ '^[0-9]{4}'
    AND (
      COALESCE(m.red_score, 0) > 0
      OR COALESCE(m.blue_score, 0) > 0
      OR m.winning_alliance IN ('red', 'blue')
    )
    AND NOT (
      COALESCE(m.winning_alliance, '') NOT IN ('red', 'blue')
      AND m.red_win_prob IS DISTINCT FROM 0.5
    )
)
"""

_PRED_ROLLUP_SQL = (
    _PRED_MATERIALIZED_CTE
    + """
SELECT bucket, sort_key, label, total, correct, brier, fav_total, fav_correct
FROM (
  SELECT 'summary'::text AS bucket, 0 AS sort_key, ''::text AS label,
    COUNT(*)::bigint AS total,
    SUM(is_correct)::bigint AS correct,
    AVG(POWER(red_win_prob - red_outcome, 2))::double precision AS brier,
    SUM(CASE WHEN favorite <> 'toss' THEN 1 ELSE 0 END)::bigint AS fav_total,
    SUM(CASE WHEN favorite = winning_alliance THEN 1 ELSE 0 END)::bigint AS fav_correct
  FROM pred
  UNION ALL
  SELECT 'year', year, '', COUNT(*)::bigint, SUM(is_correct)::bigint,
    AVG(POWER(red_win_prob - red_outcome, 2))::double precision, NULL::bigint, NULL::bigint
  FROM pred GROUP BY year
  UNION ALL
  SELECT 'conf',
    CASE WHEN edge < 0.05 THEN 1 WHEN edge < 0.15 THEN 2 WHEN edge < 0.25 THEN 3 ELSE 4 END,
    CASE
      WHEN edge < 0.05 THEN '50-55% (toss-up)'
      WHEN edge < 0.15 THEN '55-65%'
      WHEN edge < 0.25 THEN '65-75%'
      ELSE '75%+ (strong)'
    END,
    COUNT(*)::bigint, SUM(is_correct)::bigint,
    AVG(POWER(red_win_prob - red_outcome, 2))::double precision, NULL::bigint, NULL::bigint
  FROM pred GROUP BY 2, 3
  UNION ALL
  SELECT 'comp',
    CASE
      WHEN LOWER(comp_level) = 'qm' THEN 1
      WHEN LOWER(comp_level) IN ('ef', 'qf', 'sf', 'f') THEN 2
      ELSE 3
    END,
    CASE
      WHEN LOWER(comp_level) = 'qm' THEN 'Quals'
      WHEN LOWER(comp_level) IN ('ef', 'qf', 'sf', 'f') THEN 'Playoffs'
      ELSE 'Other'
    END,
    COUNT(*)::bigint, SUM(is_correct)::bigint,
    AVG(POWER(red_win_prob - red_outcome, 2))::double precision, NULL::bigint, NULL::bigint
  FROM pred GROUP BY 2, 3
  UNION ALL
  SELECT 'etype',
    CASE
      WHEN event_type = 'Regional' THEN 1
      WHEN event_type = 'District' THEN 2
      WHEN event_type IN ('District Championship', 'District Championship Division') THEN 3
      WHEN event_type IN ('Championship Division', 'Championship Finals', 'Festival of Champions') THEN 4
      WHEN event_type IN ('Offseason', 'Preseason') THEN 5
      ELSE 6
    END,
    CASE
      WHEN event_type = 'Regional' THEN 'Regional'
      WHEN event_type = 'District' THEN 'District'
      WHEN event_type IN ('District Championship', 'District Championship Division') THEN 'District Champs'
      WHEN event_type IN ('Championship Division', 'Championship Finals', 'Festival of Champions')
        THEN 'World Champs'
      WHEN event_type IN ('Offseason', 'Preseason') THEN 'Offseason'
      ELSE 'Other'
    END,
    COUNT(*)::bigint, SUM(is_correct)::bigint,
    AVG(POWER(red_win_prob - red_outcome, 2))::double precision, NULL::bigint, NULL::bigint
  FROM pred GROUP BY 2, 3
) rolled
ORDER BY bucket, sort_key
"""
)


def _banner_kind(award_name: str) -> str | None:
    name = (award_name or "").lower()
    if not name:
        return None
    if "chairman" in name:
        return "chairmans"
    if "impact" in name:
        return "impact"
    if "woodie flowers" in name:
        return "woodie"
    if WINNER_RE.search(name) and not FINALIST_RE.search(name):
        return "winner"
    return None


def _is_champ_winner(award_name: str) -> bool:
    name = (award_name or "").strip().lower()
    if "division" in name or "subdivision" in name:
        return False
    return name in ("championship winner", "championship winners")


def _parse_team_key(team_key: str) -> int | None:
    raw = (team_key or "").strip().lower().replace("frc", "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _longest_streak(years: list[int]) -> tuple[int, int, int]:
    if not years:
        return 0, 0, 0
    ys = sorted(set(years))
    best = (1, ys[0], ys[0])
    run_start = ys[0]
    prev = ys[0]
    for y in ys[1:]:
        if y == prev + 1:
            prev = y
            length = prev - run_start + 1
            if length > best[0]:
                best = (length, run_start, prev)
        else:
            run_start = y
            prev = y
    return best


def _top_counts(counter: dict[int, int], limit: int = LEADER_LIMIT) -> list[LeaderRow]:
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [LeaderRow(team_number=t, count=c) for t, c in rows if c > 0]


def _top_teamups(counter: dict[tuple[int, int], int], limit: int = TEAMUP_LIMIT) -> list[TeamupRow]:
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:limit]
    return [TeamupRow(team_a=a, team_b=b, count=c) for (a, b), c in rows if c > 0]


def _pct(correct: int, total: int) -> float | None:
    return round(100.0 * correct / total, 2) if total else None


def _bucket_from_row(label: str, total, correct, brier) -> PredBucket:
    total_i = int(total or 0)
    correct_i = int(correct or 0)
    return PredBucket(
        label=label,
        correct=correct_i,
        total=total_i,
        pct=_pct(correct_i, total_i),
        brier=round(float(brier), 4) if brier is not None and total_i else None,
    )


def _compute_prediction_stats(db: Session) -> PredictionStats:
    rows = db.execute(text(_PRED_ROLLUP_SQL)).all()

    summary = PredSummary(correct=0, total=0, pct=None, brier=None, favorite_win_pct=None, upset_pct=None)
    by_year: list[AccuracyPoint] = []
    by_confidence: list[PredBucket] = []
    by_comp_level: list[PredBucket] = []
    by_event_type: list[PredBucket] = []

    for bucket, sort_key, label, total, correct, brier, fav_total, fav_correct in rows:
        total_i = int(total or 0)
        correct_i = int(correct or 0)
        brier_f = round(float(brier), 4) if brier is not None and total_i else None
        if bucket == "summary":
            fav_pct = _pct(int(fav_correct or 0), int(fav_total or 0))
            summary = PredSummary(
                correct=correct_i,
                total=total_i,
                pct=_pct(correct_i, total_i),
                brier=brier_f,
                favorite_win_pct=fav_pct,
                upset_pct=round(100.0 - fav_pct, 2) if fav_pct is not None else None,
            )
        elif bucket == "year":
            by_year.append(
                AccuracyPoint(
                    year=int(sort_key),
                    correct=correct_i,
                    total=total_i,
                    pct=_pct(correct_i, total_i),
                    brier=brier_f,
                )
            )
        elif bucket == "conf":
            by_confidence.append(_bucket_from_row(str(label), total_i, correct_i, brier_f))
        elif bucket == "comp":
            by_comp_level.append(_bucket_from_row(str(label), total_i, correct_i, brier_f))
        elif bucket == "etype":
            by_event_type.append(_bucket_from_row(str(label), total_i, correct_i, brier_f))

    return PredictionStats(
        summary=summary,
        by_year=by_year,
        by_confidence=by_confidence,
        by_comp_level=by_comp_level,
        by_event_type=by_event_type,
    )


def prewarm_insights_cache() -> None:
    """Populate the process cache (call from a background thread on startup)."""
    db = SessionLocal()
    try:
        get_insights_overview(db)
    finally:
        db.close()


def get_insights_overview(db: Session) -> InsightsOverviewResponse:
    global _cache_payload, _cache_at
    now = time.monotonic()
    if _cache_payload is not None and (now - _cache_at) < _CACHE_TTL_SEC:
        return _cache_payload

    payload = _compute_insights_overview(db)
    _cache_payload = payload
    _cache_at = now
    return payload


def _compute_insights_overview(db: Session) -> InsightsOverviewResponse:
    team_rows = db.execute(
        text(
            f"""
            SELECT CAST(LEFT(event_key, 4) AS INT) AS year,
                   COUNT(DISTINCT team_number) AS team_count
            FROM event_teams
            WHERE {_YEAR_FILTER}
            GROUP BY 1
            ORDER BY 1
            """
        )
    ).all()
    event_meta_rows = db.execute(
        text(f"SELECT event_key, event_type, name FROM events WHERE {_YEAR_FILTER}")
    ).all()
    match_rows = db.execute(
        text(
            f"""
            SELECT CAST(LEFT(event_key, 4) AS INT) AS year,
                   COUNT(*) AS match_count
            FROM event_matches
            WHERE {_YEAR_FILTER}
            GROUP BY 1
            ORDER BY 1
            """
        )
    ).all()

    event_types = {str(ek): str(et or "Unknown") for ek, et, _name in event_meta_rows if ek}
    event_counts: dict[int, int] = defaultdict(int)
    einstein_keys_set: set[str] = set()
    for ek, _et, name in event_meta_rows:
        if not ek:
            continue
        try:
            y = int(str(ek)[:4])
        except ValueError:
            continue
        if 1992 <= y <= 2100:
            event_counts[y] += 1
        if name and "einstein" in str(name).lower():
            einstein_keys_set.add(str(ek))

    predictions = _compute_prediction_stats(db)

    by_year: dict[int, dict[str, int]] = defaultdict(
        lambda: {"team_count": 0, "event_count": 0, "match_count": 0}
    )
    for year, team_count in team_rows:
        by_year[int(year)]["team_count"] = int(team_count or 0)
    for year, event_count in event_counts.items():
        by_year[year]["event_count"] = event_count
    for year, match_count in match_rows:
        by_year[int(year)]["match_count"] = int(match_count or 0)

    years = [
        YearSeriesPoint(year=y, **by_year[y])
        for y in sorted(by_year.keys())
        if 1992 <= y <= 2100
    ]

    prediction_accuracy = [
        AccuracyPoint(year=p.year, correct=p.correct, total=p.total, pct=p.pct, brier=p.brier)
        for p in predictions.by_year
    ]

    award_rows = db.execute(
        text(
            """
            SELECT team_number, award_name, event_key
            FROM event_awards
            WHERE team_number IS NOT NULL
            """
        )
    ).all()

    banners: dict[int, int] = defaultdict(int)
    impact: dict[int, int] = defaultdict(int)
    regional_dcmp_impact: dict[int, int] = defaultdict(int)
    regional_wins: dict[int, int] = defaultdict(int)
    district_wins: dict[int, int] = defaultdict(int)
    division_wins: dict[int, int] = defaultdict(int)
    woodie: dict[int, int] = defaultdict(int)
    champ_from_awards: dict[int, int] = defaultdict(int)
    winners_by_event: dict[str, set[int]] = defaultdict(set)
    einstein_winners_by_event: dict[str, set[int]] = defaultdict(set)

    for team_number, award_name, event_key in award_rows:
        t = int(team_number)
        et = event_types.get(str(event_key), "").strip()
        kind = _banner_kind(award_name or "")
        if kind:
            banners[t] += 1
        if kind in ("chairmans", "impact"):
            impact[t] += 1
            if et in IMPACT_REGIONAL_DCMP_TYPES:
                regional_dcmp_impact[t] += 1
        if kind == "woodie":
            woodie[t] += 1
        if kind == "winner":
            if et in REGIONAL_TYPES:
                regional_wins[t] += 1
            elif et in DISTRICT_TYPES:
                district_wins[t] += 1
            elif et in DIVISION_TYPES:
                division_wins[t] += 1
            if event_key and et in TEAMUP_EVENT_TYPES:
                winners_by_event[str(event_key)].add(t)
            if event_key and str(event_key) in einstein_keys_set:
                einstein_winners_by_event[str(event_key)].add(t)
        if _is_champ_winner(award_name or ""):
            champ_from_awards[t] += 1

    notable_rows = db.execute(
        select(Notables.team_key, Notables.year, Notables.category).where(
            Notables.category == "notables_world_champions"
        )
    ).all()
    champ_from_notables: dict[int, list[int]] = defaultdict(list)
    for team_key, year, _cat in notable_rows:
        num = _parse_team_key(team_key or "")
        if num is None:
            continue
        champ_from_notables[num].append(int(year))

    championship_wins: list[LeaderRow] = []
    if champ_from_notables:
        ranked = sorted(
            ((t, len(ys), sorted(ys)) for t, ys in champ_from_notables.items()),
            key=lambda x: (-x[1], x[0]),
        )[:LEADER_LIMIT]
        championship_wins = [
            LeaderRow(team_number=t, count=c, detail=", ".join(str(y) for y in ys))
            for t, c, ys in ranked
        ]
    else:
        championship_wins = _top_counts(champ_from_awards)

    event_pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    for teams in winners_by_event.values():
        uniq = sorted(teams)
        if len(uniq) < 2:
            continue
        for a, b in combinations(uniq[:4], 2):
            event_pair_counts[(a, b)] += 1

    einstein_pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    for teams in einstein_winners_by_event.values():
        uniq = sorted(teams)
        if len(uniq) < 2:
            continue
        for a, b in combinations(uniq[:4], 2):
            einstein_pair_counts[(a, b)] += 1

    einstein_keys = list(einstein_keys_set)
    einstein_years_by_team: dict[int, list[int]] = defaultdict(list)
    if einstein_keys:
        et_rows = db.execute(
            select(EventTeams.team_number, EventTeams.event_key).where(
                EventTeams.event_key.in_(einstein_keys)
            )
        ).all()
        for team_number, event_key in et_rows:
            if team_number is None or not event_key:
                continue
            try:
                year = int(str(event_key)[:4])
            except ValueError:
                continue
            einstein_years_by_team[int(team_number)].append(year)

    einstein_appearances = sorted(
        (LeaderRow(team_number=t, count=len(set(ys))) for t, ys in einstein_years_by_team.items() if ys),
        key=lambda r: (-r.count, r.team_number),
    )[:LEADER_LIMIT]

    streak_rows: list[LeaderRow] = []
    for t, ys in einstein_years_by_team.items():
        length, start, end = _longest_streak(ys)
        if length <= 0:
            continue
        streak_rows.append(
            LeaderRow(
                team_number=t,
                count=length,
                detail=f"{start}\u2013{end}" if start != end else str(start),
            )
        )
    einstein_streaks = sorted(streak_rows, key=lambda r: (-r.count, r.team_number))[:LEADER_LIMIT]

    totals = {
        "seasons": len(years),
        "events": int(sum(y.event_count for y in years)),
        "matches": int(sum(y.match_count for y in years)),
        "blue_banners": int(sum(banners.values())),
        "predicted_matches": int(sum(p.total for p in prediction_accuracy)),
        "teams_latest": int(years[-1].team_count) if years else 0,
    }

    return InsightsOverviewResponse(
        years=years,
        prediction_accuracy=prediction_accuracy,
        predictions=predictions,
        blue_banners=_top_counts(banners),
        championship_wins=championship_wins,
        impact_chairmans=_top_counts(impact),
        regional_dcmp_impact=_top_counts(regional_dcmp_impact),
        regional_wins=_top_counts(regional_wins),
        district_wins=_top_counts(district_wins),
        division_wins=_top_counts(division_wins),
        woodie_flowers=_top_counts(woodie),
        einstein_appearances=einstein_appearances,
        einstein_streaks=einstein_streaks,
        event_teamups=_top_teamups(event_pair_counts),
        einstein_teamups=_top_teamups(einstein_pair_counts),
        totals=totals,
    )
