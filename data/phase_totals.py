"""Alliance-level phase point totals (no per-team scaling).

Residual attribution uses these as S in obs_i = S - r_j - r_k.

Design rule for every year: prefer TBA official totals so
``auto + teleop + endgame_alliance == totalPoints`` (≈ match score).

Teleop is reconstructed as ``totalPoints - auto - endgame_alliance``, which
folds fouls/adjust/bonus fields that live outside auto/endgame.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import yearmodels


def _f(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _tba_auto(b: dict) -> float:
    if b.get("autoPoints") is not None:
        return _f(b.get("autoPoints"))
    if b.get("auto_points") is not None:
        return _f(b.get("auto_points"))
    # 2026 TBA schema
    if b.get("totalAutoPoints") is not None:
        return _f(b.get("totalAutoPoints"))
    hub = b.get("hubScore")
    if isinstance(hub, dict) and hub.get("autoPoints") is not None:
        return _f(hub.get("autoPoints"))
    return 0.0


def _hub(b: dict) -> dict:
    hub = b.get("hubScore")
    return hub if isinstance(hub, dict) else {}


def _tba_total(b: dict) -> float:
    if b.get("totalPoints") is not None:
        return _f(b.get("totalPoints"))
    if b.get("total_points") is not None:
        return _f(b.get("total_points"))
    hub = _hub(b)
    if hub.get("totalPoints") is not None:
        return _f(hub.get("totalPoints"))
    # Last resort: auto + teleop + fouls (may miss year-specific extras)
    tele = _f(b.get("teleopPoints", b.get("teleop_points")))
    foul = _f(b.get("foulPoints", b.get("foul_points"))) + _f(
        b.get("adjustPoints", b.get("adjust_points"))
    )
    return _tba_auto(b) + tele + foul


# ---- Per-robot endgame maps -------------------------------------------------

def robot_endgame_2026(b: dict, index: int) -> float:
    return float(yearmodels.endgame_2026(b, index) or 0.0)


def robot_endgame_2025(b: dict, index: int) -> float:
    return float(yearmodels.endgame_2025(b, index) or 0.0)


def robot_endgame_2019(b: dict, index: int) -> float:
    status = b.get(f"endgameRobot{index}", "None")
    return float({"HabLevel3": 12, "HabLevel2": 6, "HabLevel1": 3, "None": 0}.get(status, 0))


def robot_endgame_2018(b: dict, index: int) -> float:
    status = b.get(f"endgameRobot{index}", "None")
    return float({"Climbing": 30, "Levitate": 30, "Parking": 5, "None": 0}.get(status, 0))


def robot_endgame_2020(b: dict, index: int) -> float:
    # Level / engagement bonuses are alliance-wide; folded into teleop via total - auto - end.
    status = b.get(f"endgameRobot{index}", "None")
    return float({"Hang": 25, "Park": 5, "None": 0}.get(status, 0))


def robot_endgame_2022(b: dict, index: int) -> float:
    status = b.get(f"endgameRobot{index}", "None")
    return float(
        {"Traversal": 15, "High": 10, "Mid": 6, "Low": 4, "None": 0}.get(status, 0)
    )


# ---- Alliance endgame totals (shared) --------------------------------------

def alliance_endgame_2024(b: dict) -> float:
    return (
        _f(b.get("endGameParkPoints"))
        + _f(b.get("endGameOnStagePoints"))
        + _f(b.get("endGameSpotLightBonusPoints"))
        + _f(b.get("endGameHarmonyPoints"))
        + _f(b.get("endGameNoteInTrapPoints"))
    )


def alliance_endgame_2017(b: dict) -> float:
    return _f(b.get("teleopTakeoffPoints"))


def alliance_endgame_2016(b: dict) -> float:
    return _f(b.get("teleopChallengePoints")) + _f(b.get("teleopScalePoints"))


def _per_robot_ends(year: int, b: dict, team_count: int) -> Optional[List[float]]:
    """Return per-robot endgame list, or None if endgame is alliance-shared."""
    y = int(year)
    n = max(1, int(team_count) or 1)
    if y == 2015:
        return [0.0] * n
    if y == 2026:
        # Prefer per-robot tower statuses when TBA fills them; otherwise hub endgame
        # is an alliance-shared fuel total (common in 2026 dumps).
        ends = [robot_endgame_2026(b, i) for i in range(1, n + 1)]
        if sum(ends) > 0:
            official = _f(_hub(b).get("endgamePoints"))
            if official > 0:
                return _scale_ends_to_official(ends, official, n)
            return ends
        return None
    if y == 2025:
        return [robot_endgame_2025(b, i) for i in range(1, n + 1)]
    if y == 2019:
        ends = [robot_endgame_2019(b, i) for i in range(1, n + 1)]
        official = _f(b.get("habClimbPoints"))
        return _scale_ends_to_official(ends, official, n)
    if y == 2018:
        ends = [robot_endgame_2018(b, i) for i in range(1, n + 1)]
        return _scale_ends_to_official(ends, _f(b.get("endgamePoints")), n)
    if y in (2020, 2021):
        ends = [robot_endgame_2020(b, i) for i in range(1, n + 1)]
        return _scale_ends_to_official(ends, _f(b.get("endgamePoints")), n)
    if y == 2022:
        ends = [robot_endgame_2022(b, i) for i in range(1, n + 1)]
        return _scale_ends_to_official(ends, _f(b.get("endgamePoints")), n)
    if y == 2023:
        official = _f(b.get("endGameChargeStationPoints")) + _f(b.get("endGameParkPoints"))
        statuses = [b.get(f"endGameChargeStationRobot{i}", "None") for i in range(1, n + 1)]
        raw = []
        for st in statuses:
            if st == "Docked":
                raw.append(10.0)
            elif st == "Park":
                raw.append(2.0)
            else:
                raw.append(0.0)
        return _scale_ends_to_official(raw, official, n)
    return None


def _scale_ends_to_official(ends: List[float], official: float, n: int) -> List[float]:
    raw_sum = sum(ends)
    if official > 0 and raw_sum > 0 and abs(official - raw_sum) > 0.5:
        scale = official / raw_sum
        return [x * scale for x in ends]
    if official > 0 and raw_sum == 0:
        return [official / n] * n
    return ends


def _shared_endgame(year: int, b: dict) -> float:
    y = int(year)
    if y == 2026:
        hub = _hub(b)
        if hub.get("endgamePoints") is not None:
            return _f(hub.get("endgamePoints"))
        return _f(b.get("endGameTowerPoints"))
    if y == 2024:
        return alliance_endgame_2024(b)
    if y == 2017:
        return alliance_endgame_2017(b)
    if y == 2016:
        return alliance_endgame_2016(b)
    if y == 2021:
        # Same game as 2020; use endgamePoints if present.
        return _f(b.get("endgamePoints"))
    # Generic TBA field
    if b.get("endgamePoints") is not None:
        return _f(b.get("endgamePoints"))
    if b.get("endGamePoints") is not None:
        return _f(b.get("endGamePoints"))
    return 0.0


def alliance_auto(year: int, breakdown: dict, team_count: int = 3) -> float:
    """Official TBA auto total (preferred). Never use log-scaled yearmodel means here."""
    auto = _tba_auto(breakdown)
    if (
        auto
        or breakdown.get("autoPoints") is not None
        or breakdown.get("auto_points") is not None
        or breakdown.get("totalAutoPoints") is not None
        or _hub(breakdown).get("autoPoints") is not None
    ):
        return auto
    # Rare fallback: year-specific invert from a single breakdown (no log trim path).
    # Prefer hub/year fields already handled above; keep 0 rather than log-scaled EPA helpers.
    return 0.0


def phase_totals(
    year: int, breakdown: dict, team_count: int, robot_index: int
) -> Tuple[float, float, float, bool]:
    """Return (auto_S, teleop_S, endgame_obs_or_S, endgame_is_per_robot)."""
    auto_s = max(0.0, alliance_auto(year, breakdown, team_count))
    total = max(0.0, _tba_total(breakdown))
    ends = _per_robot_ends(year, breakdown, team_count)
    if ends is not None:
        # Floor per-robot endgame; keep alliance endgame <= remaining points.
        ends = [max(0.0, float(x)) for x in ends]
        end_alliance = sum(ends)
        remaining = max(0.0, total - auto_s)
        if end_alliance > remaining and end_alliance > 0:
            scale = remaining / end_alliance
            ends = [x * scale for x in ends]
            end_alliance = sum(ends)
        teleop_s = max(0.0, total - auto_s - end_alliance)
        idx = min(max(robot_index, 1), len(ends)) - 1
        return auto_s, teleop_s, float(ends[idx]), True
    end_s = max(0.0, _shared_endgame(year, breakdown))
    remaining = max(0.0, total - auto_s)
    if end_s > remaining:
        end_s = remaining
    teleop_s = max(0.0, total - auto_s - end_s)
    return auto_s, teleop_s, float(end_s), False
