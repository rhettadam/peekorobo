"""Career / all-time Insights aggregates for the Overall Insights page."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from itertools import combinations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

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
# Overview is expensive; keep a short process-local cache.
_CACHE_TTL_SEC = 900.0
_cache_payload: InsightsOverviewResponse | None = None
_cache_at: float = 0.0

WINNER_RE = re.compile(r"\b(?:winners?|champions?)\b", re.I)
FINALIST_RE = re.compile(r"finalists?", re.I)

# DB stores TBA event_type as human labels (not numeric codes).
REGIONAL_TYPES = {"Regional"}
DISTRICT_TYPES = {"District", "District Championship", "District Championship Division"}
DCMP_TYPES = {"District Championship", "District Championship Division"}
DIVISION_TYPES = {"Championship Division"}
# Official events where alliance co-wins count as "teamups".
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
    """Return (length, start, end) for the longest consecutive year run."""
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
    return [
        TeamupRow(team_a=a, team_b=b, count=c)
        for (a, b), c in rows
        if c > 0
    ]


def _pct(correct: int, total: int) -> float | None:
    return round(100.0 * correct / total, 2) if total else None


def _roll_up_predictions(
    rows: list,
    event_types: dict[str, str],
) -> tuple[PredictionStats, dict[int, int]]:
    """Roll up win-prob accuracy + per-year match counts from one event_matches fetch.

    Each row is (event_key, comp_level, red_win_prob, winning_alliance, red_score, blue_score).
    """
    year_stats: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    conf_stats: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    comp_stats: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    etype_stats: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    match_counts: dict[int, int] = defaultdict(int)

    total = 0
    correct = 0
    brier_sum = 0.0
    fav_total = 0
    fav_correct = 0

    conf_labels = {
        1: "50-55% (toss-up)",
        2: "55-65%",
        3: "65-75%",
        4: "75%+ (strong)",
    }
    comp_labels = {1: "Quals", 2: "Playoffs", 3: "Other"}
    etype_labels = {
        1: "Regional",
        2: "District",
        3: "District Champs",
        4: "World Champs",
        5: "Offseason",
        6: "Other",
    }

    for event_key, comp_level, red_win_prob, winning_alliance, red_score, blue_score in rows:
        try:
            year = int(str(event_key)[:4])
        except (TypeError, ValueError):
            continue
        if year < 1992 or year > 2100:
            continue
        match_counts[year] += 1

        if red_win_prob is None:
            continue
        wa = str(winning_alliance or "")
        played = (red_score or 0) > 0 or (blue_score or 0) > 0 or wa in ("red", "blue")
        if not played:
            continue
        # Skip unresolved ties unless the model called a toss-up.
        if wa not in ("red", "blue") and float(red_win_prob) != 0.5:
            continue

        p = float(red_win_prob)
        red_outcome = 1.0 if wa == "red" else (0.0 if wa == "blue" else 0.5)
        is_correct = (
            1
            if (
                (wa == "red" and p > 0.5)
                or (wa == "blue" and p < 0.5)
                or (wa not in ("red", "blue") and p == 0.5)
            )
            else 0
        )
        edge = abs(p - 0.5)
        favorite = "red" if p > 0.5 else ("blue" if p < 0.5 else "toss")
        conf_ord = 1 if edge < 0.05 else (2 if edge < 0.15 else (3 if edge < 0.25 else 4))
        cl = str(comp_level or "").lower()
        comp_ord = 1 if cl == "qm" else (2 if cl in ("ef", "qf", "sf", "f") else 3)
        et = event_types.get(str(event_key), "Unknown")
        if et == "Regional":
            etype_ord = 1
        elif et == "District":
            etype_ord = 2
        elif et in ("District Championship", "District Championship Division"):
            etype_ord = 3
        elif et in ("Championship Division", "Championship Finals", "Festival of Champions"):
            etype_ord = 4
        elif et in ("Offseason", "Preseason"):
            etype_ord = 5
        else:
            etype_ord = 6

        brier = (p - red_outcome) ** 2
        total += 1
        correct += is_correct
        brier_sum += brier
        if favorite != "toss":
            fav_total += 1
            if favorite == wa:
                fav_correct += 1

        for bucket, key in (
            (year_stats, year),
            (conf_stats, conf_ord),
            (comp_stats, comp_ord),
            (etype_stats, etype_ord),
        ):
            bucket[key][0] += 1
            bucket[key][1] += is_correct
            bucket[key][2] += brier

    fav_pct = _pct(fav_correct, fav_total)
    summary = PredSummary(
        correct=correct,
        total=total,
        pct=_pct(correct, total),
        brier=round(brier_sum / total, 4) if total else None,
        favorite_win_pct=fav_pct,
        upset_pct=round(100.0 - fav_pct, 2) if fav_pct is not None else None,
    )
    by_year = [
        AccuracyPoint(
            year=year,
            correct=int(vals[1]),
            total=int(vals[0]),
            pct=_pct(int(vals[1]), int(vals[0])),
            brier=round(vals[2] / vals[0], 4) if vals[0] else None,
        )
        for year, vals in sorted(year_stats.items())
    ]
    by_confidence = [
        PredBucket(
            label=conf_labels[k],
            correct=int(vals[1]),
            total=int(vals[0]),
            pct=_pct(int(vals[1]), int(vals[0])),
            brier=round(vals[2] / vals[0], 4) if vals[0] else None,
        )
        for k, vals in sorted(conf_stats.items())
    ]
    by_comp_level = [
        PredBucket(
            label=comp_labels[k],
            correct=int(vals[1]),
            total=int(vals[0]),
            pct=_pct(int(vals[1]), int(vals[0])),
            brier=round(vals[2] / vals[0], 4) if vals[0] else None,
        )
        for k, vals in sorted(comp_stats.items())
    ]
    by_event_type = [
        PredBucket(
            label=etype_labels[k],
            correct=int(vals[1]),
            total=int(vals[0]),
            pct=_pct(int(vals[1]), int(vals[0])),
            brier=round(vals[2] / vals[0], 4) if vals[0] else None,
        )
        for k, vals in sorted(etype_stats.items())
    ]
    return (
        PredictionStats(
            summary=summary,
            by_year=by_year,
            by_confidence=by_confidence,
            by_comp_level=by_comp_level,
            by_event_type=by_event_type,
        ),
        dict(match_counts),
    )


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
    # ---- Season series: teams + events; matches come from the prediction scan ----
    team_rows = db.execute(
        text(
            """
            SELECT CAST(LEFT(event_key, 4) AS INT) AS year,
                   COUNT(DISTINCT team_number) AS team_count
            FROM event_teams
            WHERE LEFT(event_key, 4) ~ '^[0-9]{4}$'
            GROUP BY 1
            """
        )
    ).all()
    event_meta_rows = db.execute(
        text("SELECT event_key, event_type, name FROM events")
    ).all()
    event_types = {
        str(ek): str(et or "Unknown") for ek, et, _name in event_meta_rows if ek
    }
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

    match_rows = db.execute(
        text(
            """
            SELECT event_key,
                   COALESCE(comp_level, ''),
                   red_win_prob,
                   COALESCE(winning_alliance, ''),
                   COALESCE(red_score, 0),
                   COALESCE(blue_score, 0)
            FROM event_matches
            WHERE LEFT(event_key, 4) ~ '^[0-9]{4}$'
            """
        )
    ).all()
    predictions, match_counts = _roll_up_predictions(match_rows, event_types)

    by_year: dict[int, dict[str, int]] = defaultdict(
        lambda: {"team_count": 0, "event_count": 0, "match_count": 0}
    )
    for year, team_count in team_rows:
        by_year[int(year)]["team_count"] = int(team_count or 0)
    for year, event_count in event_counts.items():
        by_year[year]["event_count"] = event_count
    for year, match_count in match_counts.items():
        by_year[year]["match_count"] = match_count

    years = [
        YearSeriesPoint(year=y, **by_year[y])
        for y in sorted(by_year.keys())
        if 1992 <= y <= 2100
    ]

    prediction_accuracy = [
        AccuracyPoint(year=p.year, correct=p.correct, total=p.total, pct=p.pct, brier=p.brier)
        for p in predictions.by_year
    ]

    # ---- Awards scan (banners / wins / teamups) ----
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
            LeaderRow(
                team_number=t,
                count=c,
                detail=", ".join(str(y) for y in ys),
            )
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
        (
            LeaderRow(team_number=t, count=len(set(ys)))
            for t, ys in einstein_years_by_team.items()
            if ys
        ),
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
