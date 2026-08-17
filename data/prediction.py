"""Match prediction from stored RAW/ACE ratings and walk-forward pre-match ACE.

Legacy scopes read ``team_epas`` only (DB-only). ``pre_match`` replays ACE
simulation with TBA match payloads (score breakdown) for point-in-time ratings.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Tuple

from psycopg2.extras import execute_values

from ace_attribution import (
    Method,
    TeamPhaseState,
    merge_carry_prior,
    simulate_event,
    simulate_event_pre_match_snapshots,
)

RatingField = Literal["ace", "raw"]
RatingScope = Literal[
    "event",
    "prior_event",
    "prior_event_or_prior_year",
    "season",
    "prior_year",
    "pre_match",
]
Aggregation = Literal["sum", "mean"]


@dataclass
class AceParams:
    method: Method = "residual_shrink"
    k_base: float = 0.3
    shrink: float = 0.1
    spike_damp: float = 0.75
    k_up: float = 0.9
    k_down: float = 0.9
    partner_cap: float = 1.5
    carry_prior: bool = True
    prior_blend: float = 0.75

    @classmethod
    def from_env(cls) -> "AceParams":
        method = os.environ.get("ACE_METHOD", "residual_shrink").strip().lower()
        if method not in ("residual", "equal_split", "residual_shrink", "baseline_current"):
            method = "residual_shrink"
        return cls(
            method=method,  # type: ignore[arg-type]
            k_base=float(os.environ.get("ACE_K_BASE", "0.3")),
            shrink=float(os.environ.get("ACE_SHRINK", "0.1")),
            spike_damp=float(os.environ.get("ACE_SPIKE_DAMP", "0.75")),
            k_up=float(os.environ.get("ACE_K_UP", "0.9")),
            k_down=float(os.environ.get("ACE_K_DOWN", "0.9")),
            partner_cap=float(os.environ.get("ACE_PARTNER_CAP", "1.5")),
            carry_prior=os.environ.get("ACE_CARRY_PRIOR", "1").strip().lower()
            in ("1", "true", "yes"),
            prior_blend=float(os.environ.get("ACE_PRIOR_BLEND", "0.75")),
        )


@dataclass
class PredictionConfig:
    """Production prediction parameters."""

    win_scale_base: float = 8.0
    prob_min: float = 0.05
    prob_max: float = 0.95
    rating_field: RatingField = "ace"
    rating_scope: RatingScope = "pre_match"
    aggregation: Aggregation = "sum"

    @classmethod
    def from_env(cls) -> "PredictionConfig":
        return cls(
            win_scale_base=float(os.environ.get("ACE_WIN_PROB_SCALE", "8.0")),
            prob_min=float(os.environ.get("PRED_PROB_MIN", "0.05")),
            prob_max=float(os.environ.get("PRED_PROB_MAX", "0.95")),
            rating_field=_normalize_rating_field(
                os.environ.get("PRED_RATING_FIELD", "ace")
            ),
            rating_scope=os.environ.get("PRED_RATING_SCOPE", "pre_match").strip().lower(),  # type: ignore[arg-type]
            aggregation=os.environ.get("PRED_AGGREGATION", "sum").strip().lower(),  # type: ignore[arg-type]
        )

    def label(self) -> str:
        return (
            f"scope={self.rating_scope} field={self.rating_field} "
            f"agg={self.aggregation} scale={self.win_scale_base}"
        )


@dataclass
class MatchRow:
    match_key: str
    event_key: str
    red_teams: List[int]
    blue_teams: List[int]
    red_score: int
    blue_score: int
    winning_alliance: str
    predicted_time: Optional[int] = None
    comp_level: str = "qm"
    red_win_prob: Optional[float] = None
    blue_win_prob: Optional[float] = None
    red_predicted_score: Optional[float] = None
    blue_predicted_score: Optional[float] = None


@dataclass
class TeamSeasonData:
    ace: float = 0.0
    raw: float = 0.0
    confidence: float = 0.0
    auto_raw: float = 0.0
    teleop_raw: float = 0.0
    endgame_raw: float = 0.0
    event_perf: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class DbPredictionData:
    year: int
    event_order: Dict[str, Tuple[str, str]]  # event_key -> (start_date, event_key)
    season: Dict[int, TeamSeasonData]
    prior_season: Dict[int, TeamSeasonData]
    matches: List[MatchRow]


@dataclass
class MatchPrediction:
    match_key: str
    p_red: float
    p_blue: float
    red_predicted_score: float
    blue_predicted_score: float
    pre_match_teams: Optional[Dict[str, Dict[str, float]]] = None


# Compact JSON keys stored in event_matches.pre_match_teams (per team: a,t,e,r,c,ace).
PRE_MATCH_TEAM_KEYS = ("a", "t", "e", "r", "c", "ace")


def pack_pre_match_team(
    auto: float,
    teleop: float,
    endgame: float,
    raw: float,
    confidence: float,
    ace: float,
) -> Dict[str, float]:
    return {
        "a": round(auto, 2),
        "t": round(teleop, 2),
        "e": round(endgame, 2),
        "r": round(raw, 2),
        "c": round(confidence, 2),
        "ace": round(ace, 2),
    }


def empty_pre_match_team() -> Dict[str, float]:
    return pack_pre_match_team(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def rating_from_pre_match_team(
    payload: Dict[str, float], rating_field: RatingField
) -> float:
    if rating_field == "raw":
        return float(payload.get("r") or 0.0)
    return float(payload.get("ace") or 0.0)


def _compact_from_perf(perf: Dict[str, float]) -> Dict[str, float]:
    auto = float(perf.get("auto_raw") or 0.0)
    teleop = float(perf.get("teleop_raw") or 0.0)
    endgame = float(perf.get("endgame_raw") or 0.0)
    raw = float(perf.get("raw") or (auto + teleop + endgame))
    conf = float(perf.get("confidence") or 0.0)
    ace = float(perf.get("ace") or (raw * conf))
    return pack_pre_match_team(auto, teleop, endgame, raw, conf, ace)


def _compact_from_season(td: Optional[TeamSeasonData]) -> Dict[str, float]:
    if not td:
        return empty_pre_match_team()
    auto = float(td.auto_raw or 0.0)
    teleop = float(td.teleop_raw or 0.0)
    endgame = float(td.endgame_raw or 0.0)
    raw = float(td.raw or (auto + teleop + endgame))
    conf = float(td.confidence or 0.0)
    ace = float(td.ace or (raw * conf))
    return pack_pre_match_team(auto, teleop, endgame, raw, conf, ace)


def fallback_pre_match_team(
    data: DbPredictionData,
    team_number: int,
    event_key: str,
) -> Dict[str, float]:
    """Prior-event or prior-season components when walk-forward snapshot is missing."""
    team = data.season.get(team_number)
    prior = data.prior_season.get(team_number)
    if team:
        pek = _prior_event_key(data, team, event_key)
        if pek and pek in team.event_perf:
            return _compact_from_perf(team.event_perf[pek])
    if prior:
        return _compact_from_season(prior)
    return empty_pre_match_team()


def resolve_pre_match_teams_for_match(
    data: DbPredictionData,
    row: MatchRow,
    snapshots: Dict[int, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for tn in row.red_teams + row.blue_teams:
        if tn in snapshots:
            out[str(tn)] = snapshots[tn]
        else:
            out[str(tn)] = fallback_pre_match_team(data, tn, row.event_key)
    return out


def _pre_match_teams_json(teams: Optional[Dict[str, Dict[str, float]]]) -> Optional[str]:
    if not teams:
        return None
    return json.dumps(teams, sort_keys=True, separators=(",", ":"))


def _normalize_jsonb(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, str):
        return val
    return json.dumps(val, sort_keys=True, separators=(",", ":"))


def _normalize_rating_field(value: str) -> RatingField:
    """ACE is RAW × confidence; treat legacy raw_x_conf as ace."""
    field = (value or "ace").strip().lower()
    if field in ("raw_x_conf", "rawxconf"):
        return "ace"
    if field == "raw":
        return "raw"
    return "ace"


def is_played(row: MatchRow) -> bool:
    if row.red_score > 0 or row.blue_score > 0:
        return True
    return row.winning_alliance in ("red", "blue")


@dataclass
class PredictionAccuracySummary:
    correct: int = 0
    total: int = 0
    pct: Optional[float] = None
    brier: Optional[float] = None
    favorite_correct: int = 0
    favorite_total: int = 0
    favorite_win_pct: Optional[float] = None

    def label(self) -> str:
        pct_s = f"{self.pct:.1f}%" if self.pct is not None else "n/a"
        brier_s = f"{self.brier:.4f}" if self.brier is not None else "n/a"
        fav_s = (
            f"{self.favorite_win_pct:.1f}% ({self.favorite_correct}/{self.favorite_total})"
            if self.favorite_win_pct is not None
            else "n/a"
        )
        return (
            f"{self.correct}/{self.total} ({pct_s}), "
            f"Brier {brier_s}, favorite {fav_s}"
        )


def compute_prediction_accuracy_summary(
    matches: List[MatchRow],
    prob_by_match_key: Optional[Dict[str, float]] = None,
) -> PredictionAccuracySummary:
    """Accuracy stats mirroring insights_overview / frontend predictionAccuracy."""
    correct = 0
    total = 0
    brier_sum = 0.0
    favorite_correct = 0
    favorite_total = 0

    for row in matches:
        if not is_played(row):
            continue
        if prob_by_match_key is not None:
            p_red = prob_by_match_key.get(row.match_key)
        else:
            p_red = row.red_win_prob
        if p_red is None:
            continue

        winning = row.winning_alliance or ""
        actual_tie = winning not in ("red", "blue")
        pred_tie = p_red == 0.5
        if actual_tie and not pred_tie:
            continue

        if winning == "red":
            red_outcome = 1.0
        elif winning == "blue":
            red_outcome = 0.0
        else:
            red_outcome = 0.5

        is_correct = False
        if winning == "red" and p_red > 0.5:
            is_correct = True
        elif winning == "blue" and p_red < 0.5:
            is_correct = True
        elif actual_tie and pred_tie:
            is_correct = True

        total += 1
        if is_correct:
            correct += 1
        brier_sum += (p_red - red_outcome) ** 2

        if p_red > 0.5:
            favorite = "red"
        elif p_red < 0.5:
            favorite = "blue"
        else:
            favorite = "toss"
        if favorite != "toss":
            favorite_total += 1
            if favorite == winning:
                favorite_correct += 1

    pct = (100.0 * correct / total) if total else None
    brier = (brier_sum / total) if total else None
    favorite_win_pct = (
        (100.0 * favorite_correct / favorite_total) if favorite_total else None
    )
    return PredictionAccuracySummary(
        correct=correct,
        total=total,
        pct=pct,
        brier=brier,
        favorite_correct=favorite_correct,
        favorite_total=favorite_total,
        favorite_win_pct=favorite_win_pct,
    )


def _parse_event_perf(raw_val) -> Dict[str, Dict[str, float]]:
    if raw_val is None:
        return {}
    data = raw_val
    if isinstance(raw_val, str):
        try:
            data = json.loads(raw_val)
        except (json.JSONDecodeError, TypeError):
            return {}
    if not isinstance(data, list):
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        ek = entry.get("event_key")
        if not ek:
            continue
        out[str(ek)] = {
            "ace": float(entry.get("ace") or 0.0),
            "raw": float(entry.get("raw") or 0.0),
            "confidence": float(entry.get("confidence") or 0.0),
        }
    return out


_PRED_SCORE_COLS: Optional[bool] = None


def _event_matches_has_pred_scores(cur) -> bool:
    global _PRED_SCORE_COLS
    if _PRED_SCORE_COLS is not None:
        return _PRED_SCORE_COLS
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'event_matches'
          AND column_name = 'red_predicted_score'
        LIMIT 1
        """
    )
    _PRED_SCORE_COLS = cur.fetchone() is not None
    return _PRED_SCORE_COLS


def _event_matches_select_sql(cur) -> str:
    """SELECT list for event_matches; predicted score cols optional (added by pipeline)."""
    score_cols = ""
    if _event_matches_has_pred_scores(cur):
        score_cols = ", red_predicted_score, blue_predicted_score"
    return f"""
            SELECT match_key, event_key, red_teams, blue_teams,
                   COALESCE(red_score, 0), COALESCE(blue_score, 0),
                   COALESCE(winning_alliance, ''), predicted_time, COALESCE(comp_level, 'qm'),
                   red_win_prob, blue_win_prob{score_cols}
            """


def load_prediction_data_from_db(conn, year: int, *, limit_events: Optional[int] = None) -> DbPredictionData:
    """Load matches, event order, and team ratings from Postgres."""
    cur = conn.cursor()

    match_select = _event_matches_select_sql(cur)
    has_pred_scores = "red_predicted_score" in match_select

    cur.execute(
        """
        SELECT event_key, COALESCE(start_date::text, ''), COALESCE(event_type, '')
        FROM events
        WHERE event_key LIKE %s
        ORDER BY start_date NULLS LAST, event_key
        """,
        (f"{year}%",),
    )
    event_rows = cur.fetchall()
    if limit_events:
        event_rows = event_rows[:limit_events]
    allowed_events = {r[0] for r in event_rows}
    event_order = {r[0]: (r[1] or "", r[0]) for r in event_rows}

    def _load_season(y: int) -> Dict[int, TeamSeasonData]:
        cur.execute(
            """
            SELECT team_number, ace, confidence, raw,
                   auto_raw, teleop_raw, endgame_raw, event_perf
            FROM team_epas
            WHERE year = %s
            """,
            (y,),
        )
        result: Dict[int, TeamSeasonData] = {}
        for (
            team_number,
            ace,
            confidence,
            raw,
            auto_raw,
            teleop_raw,
            endgame_raw,
            event_perf_raw,
        ) in cur.fetchall():
            result[int(team_number)] = TeamSeasonData(
                ace=float(ace or 0.0),
                raw=float(raw or 0.0),
                confidence=float(confidence or 0.0),
                auto_raw=float(auto_raw or 0.0),
                teleop_raw=float(teleop_raw or 0.0),
                endgame_raw=float(endgame_raw or 0.0),
                event_perf=_parse_event_perf(event_perf_raw),
            )
        return result

    season = _load_season(year)
    prior_season = _load_season(year - 1)

    if allowed_events:
        cur.execute(
            match_select
            + """
            FROM event_matches
            WHERE event_key = ANY(%s)
            ORDER BY event_key, predicted_time NULLS LAST, comp_level, match_key
            """,
            (list(allowed_events),),
        )
    else:
        cur.execute(
            match_select
            + """
            FROM event_matches
            WHERE event_key LIKE %s
            ORDER BY event_key, predicted_time NULLS LAST, comp_level, match_key
            """,
            (f"{year}%",),
        )

    matches: List[MatchRow] = []
    for row in cur.fetchall():
        if has_pred_scores:
            (
                match_key,
                event_key,
                red_teams,
                blue_teams,
                red_score,
                blue_score,
                winning_alliance,
                predicted_time,
                comp_level,
                red_win_prob,
                blue_win_prob,
                red_pred_score,
                blue_pred_score,
            ) = row
        else:
            (
                match_key,
                event_key,
                red_teams,
                blue_teams,
                red_score,
                blue_score,
                winning_alliance,
                predicted_time,
                comp_level,
                red_win_prob,
                blue_win_prob,
            ) = row
            red_pred_score = blue_pred_score = None
        if allowed_events and event_key not in allowed_events:
            continue
        matches.append(
            MatchRow(
                match_key=match_key,
                event_key=event_key or "",
                red_teams=_parse_team_csv(red_teams),
                blue_teams=_parse_team_csv(blue_teams),
                red_score=int(red_score or 0),
                blue_score=int(blue_score or 0),
                winning_alliance=winning_alliance or "",
                predicted_time=predicted_time,
                comp_level=comp_level or "qm",
                red_win_prob=float(red_win_prob) if red_win_prob is not None else None,
                blue_win_prob=float(blue_win_prob) if blue_win_prob is not None else None,
                red_predicted_score=float(red_pred_score) if red_pred_score is not None else None,
                blue_predicted_score=float(blue_pred_score) if blue_pred_score is not None else None,
            )
        )

    cur.close()
    return DbPredictionData(
        year=year,
        event_order=event_order,
        season=season,
        prior_season=prior_season,
        matches=matches,
    )


def team_number_from_tba_key(team_key: str) -> int:
    tok = str(team_key or "").strip()
    if tok.lower().startswith("frc"):
        tok = tok[3:]
    digits = "".join(ch for ch in tok if ch.isdigit())
    return int(digits) if digits else 0


def _prior_with_confidence(
    st: TeamPhaseState,
    finalize_team: Callable[[TeamPhaseState, int, int], Dict[str, float]],
    year: int,
    team_key: str,
) -> Optional[Tuple[float, ...]]:
    new = (st.auto, st.teleop, st.endgame)
    if new == (0.0, 0.0, 0.0):
        return None
    tn = team_number_from_tba_key(team_key)
    payload = finalize_team(st, tn, year) if tn > 0 else None
    conf = payload.get("c") if payload else None
    if conf is None:
        return new
    return (*new, float(conf))


def _update_carry_priors(
    priors: Dict[str, Tuple[float, ...]],
    final_states: Dict[str, TeamPhaseState],
    prior_blend: float,
    finalize_team: Callable[[TeamPhaseState, int, int], Dict[str, float]],
    year: int,
) -> None:
    for key, st in final_states.items():
        if not st.initialized or st.match_count <= 0:
            continue
        new = _prior_with_confidence(st, finalize_team, year, key)
        if new is None:
            continue
        priors[key] = merge_carry_prior(priors.get(key), new, prior_blend)


def build_pre_match_ratings_by_match(
    year: int,
    matches_by_event: Dict[str, List[dict]],
    event_order: Dict[str, Tuple[str, str]],
    ace_params: AceParams,
    finalize_team: Callable[[TeamPhaseState, int, int], Dict[str, float]],
    precomputed: Optional[Dict[str, Dict[int, Dict[str, float]]]] = None,
    initial_priors: Optional[Dict[str, Tuple[float, ...]]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Walk-forward pre-match team payloads keyed by match_key then team_number."""
    if precomputed and not matches_by_event:
        return dict(precomputed)

    priors: Dict[str, Tuple[float, ...]] = dict(initial_priors or {})
    ratings_by_match: Dict[str, Dict[int, Dict[str, float]]] = dict(precomputed or {})

    event_keys = sorted(
        matches_by_event.keys(),
        key=lambda ek: event_order.get(ek, ("", ek)),
    )
    total = len(event_keys)
    to_simulate = 0

    sim_kwargs = dict(
        year=year,
        method=ace_params.method,
        k_base=ace_params.k_base,
        shrink=ace_params.shrink,
        spike_damp=ace_params.spike_damp,
        k_up=ace_params.k_up,
        k_down=ace_params.k_down,
        partner_cap=ace_params.partner_cap,
        prior_means=priors if ace_params.carry_prior else None,
        seed_priors=ace_params.carry_prior,
    )

    for i, event_key in enumerate(event_keys, start=1):
        matches = matches_by_event.get(event_key) or []
        if not matches:
            continue
        match_keys = {m.get("key") for m in matches if m.get("key")}
        fully_cached = bool(match_keys) and all(mk in ratings_by_match for mk in match_keys)

        if fully_cached:
            if ace_params.carry_prior and initial_priors is None:
                states = simulate_event(matches, **sim_kwargs)
                _update_carry_priors(
                    priors, states, ace_params.prior_blend, finalize_team, year
                )
                sim_kwargs["prior_means"] = priors
            continue

        to_simulate += 1
        n_matches = len(matches)
        n_missing = sum(1 for mk in match_keys if mk not in ratings_by_match)
        print(
            f"  walk-forward ACE simulating {event_key} "
            f"(event {i}/{total}, #{to_simulate}; "
            f"{n_matches} match(es), {n_missing} missing snapshot(s))...",
            flush=True,
        )
        t0 = time.perf_counter()
        final_states, snapshots = simulate_event_pre_match_snapshots(matches, **sim_kwargs)
        for match_key, team_states in snapshots.items():
            if match_key not in ratings_by_match:
                ratings_by_match[match_key] = {}
            for team_key, st in team_states.items():
                tn = team_number_from_tba_key(team_key)
                if tn <= 0:
                    continue
                if not st.initialized and st.match_count <= 0:
                    continue
                ratings_by_match[match_key][tn] = finalize_team(st, tn, year)
        if ace_params.carry_prior:
            _update_carry_priors(
                priors, final_states, ace_params.prior_blend, finalize_team, year
            )
            sim_kwargs["prior_means"] = priors
        elapsed = time.perf_counter() - t0
        print(
            f"  walk-forward ACE done {event_key} ({elapsed:.1f}s)",
            flush=True,
        )

    if to_simulate:
        print(
            f"  walk-forward ACE complete ({to_simulate} event(s) simulated, "
            f"{len(ratings_by_match)} match snapshot(s) total)",
            flush=True,
        )

    return ratings_by_match


def alliance_strength_pre_match(
    data: DbPredictionData,
    team_numbers: List[int],
    event_key: str,
    config: PredictionConfig,
    teams_by_number: Dict[int, Dict[str, float]],
) -> float:
    ratings: List[float] = []
    for tn in team_numbers:
        if tn in teams_by_number:
            val = rating_from_pre_match_team(teams_by_number[tn], config.rating_field)
        else:
            val = rating_from_pre_match_team(
                fallback_pre_match_team(data, tn, event_key), config.rating_field
            )
        ratings.append(float(val or 0.0))
    if not ratings:
        return 0.0
    if config.aggregation == "mean":
        return sum(ratings) / len(ratings)
    return sum(ratings)


def predict_all_matches_walk_forward(
    data: DbPredictionData,
    matches_by_event: Dict[str, List[dict]],
    config: PredictionConfig,
    ace_params: AceParams,
    finalize_team: Callable[[TeamPhaseState, int, int], Dict[str, float]],
    precomputed_ratings: Optional[Dict[str, Dict[int, Dict[str, float]]]] = None,
    initial_priors: Optional[Dict[str, Tuple[float, ...]]] = None,
) -> List[MatchPrediction]:
    """Predict every match using walk-forward pre-match ACE snapshots."""
    strengths, teams_by_match = compute_walk_forward_strengths(
        data,
        matches_by_event,
        config,
        ace_params,
        finalize_team,
        precomputed_ratings=precomputed_ratings,
        initial_priors=initial_priors,
    )
    pre_match_by_key: Dict[str, Dict[str, Dict[str, float]]] = {}
    for row in data.matches:
        snap = teams_by_match.get(row.match_key, {})
        pre_match_by_key[row.match_key] = resolve_pre_match_teams_for_match(
            data, row, snap
        )
    return predictions_from_strengths(
        data, strengths, config, pre_match_by_key=pre_match_by_key
    )


def compute_walk_forward_strengths(
    data: DbPredictionData,
    matches_by_event: Dict[str, List[dict]],
    config: PredictionConfig,
    ace_params: AceParams,
    finalize_team: Callable[[TeamPhaseState, int, int], Dict[str, float]],
    precomputed_ratings: Optional[Dict[str, Dict[int, Dict[str, float]]]] = None,
    initial_priors: Optional[Dict[str, Tuple[float, ...]]] = None,
) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Dict[int, Dict[str, float]]]]:
    """Pre-match alliance strengths and per-team snapshot payloads."""
    pre = dict(precomputed_ratings or {})
    db_keys = {row.match_key for row in data.matches}
    if db_keys.issubset(pre.keys()):
        teams_by_match = pre
    else:
        teams_by_match = build_pre_match_ratings_by_match(
            data.year,
            matches_by_event,
            data.event_order,
            ace_params,
            finalize_team,
            precomputed=precomputed_ratings,
            initial_priors=initial_priors,
        )
    strengths: Dict[str, Tuple[float, float]] = {}
    for row in data.matches:
        snap = teams_by_match.get(row.match_key, {})
        red_strength = alliance_strength_pre_match(
            data, row.red_teams, row.event_key, config, snap
        )
        blue_strength = alliance_strength_pre_match(
            data, row.blue_teams, row.event_key, config, snap
        )
        strengths[row.match_key] = (red_strength, blue_strength)
    return strengths, teams_by_match


def predictions_from_strengths(
    data: DbPredictionData,
    strengths: Dict[str, Tuple[float, float]],
    config: PredictionConfig,
    pre_match_by_key: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
) -> List[MatchPrediction]:
    """Map cached alliance strengths to win probabilities."""
    predictions: List[MatchPrediction] = []
    for row in data.matches:
        red_strength, blue_strength = strengths.get(row.match_key, (0.0, 0.0))
        p_red, p_blue = predict_win_probability(red_strength, blue_strength, config)
        predictions.append(
            MatchPrediction(
                match_key=row.match_key,
                p_red=p_red,
                p_blue=p_blue,
                red_predicted_score=red_strength,
                blue_predicted_score=blue_strength,
                pre_match_teams=(pre_match_by_key or {}).get(row.match_key),
            )
        )
    return predictions


def _probs_unchanged(
    p_red: float, p_blue: float, ex_pr, ex_pb, tol: float = 1e-4
) -> bool:
    if ex_pr is None or ex_pb is None:
        return False
    return abs(float(ex_pr) - p_red) < tol and abs(float(ex_pb) - p_blue) < tol


def apply_match_predictions_to_db(conn, year: int, predictions: List[MatchPrediction]) -> Dict[str, int]:
    """Bulk-update event_matches with computed predictions. Returns skip/write counts."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT match_key, red_win_prob, blue_win_prob,
                   red_predicted_score, blue_predicted_score, pre_match_teams
            FROM event_matches
            WHERE LEFT(event_key, 4) = %s
            """,
            (str(year),),
        )
        existing = {row[0]: row[1:] for row in cur.fetchall()}

        updates = []
        skipped_missing = 0
        skipped_unchanged = 0
        skipped_bad = 0
        pred_by_key = {p.match_key: p for p in predictions}

        for match_key, pred in pred_by_key.items():
            if match_key not in existing:
                skipped_missing += 1
                continue
            ex_pr, ex_pb, ex_rs, ex_bs, ex_teams = existing[match_key]
            teams_json = _pre_match_teams_json(pred.pre_match_teams)
            ex_teams_json = _normalize_jsonb(ex_teams)
            if not math.isfinite(pred.p_red) or not math.isfinite(pred.p_blue):
                skipped_bad += 1
                continue
            if (
                _probs_unchanged(pred.p_red, pred.p_blue, ex_pr, ex_pb)
                and ex_rs is not None
                and ex_bs is not None
                and abs(float(ex_rs) - pred.red_predicted_score) < 1e-6
                and abs(float(ex_bs) - pred.blue_predicted_score) < 1e-6
                and teams_json == ex_teams_json
            ):
                skipped_unchanged += 1
                continue
            updates.append(
                (
                    pred.p_red,
                    pred.p_blue,
                    pred.red_predicted_score,
                    pred.blue_predicted_score,
                    teams_json,
                    match_key,
                )
            )

        if updates:
            n_updates = len(updates)
            page_size = max(500, min(5000, n_updates))
            print(
                f"Match predictions {year}: bulk-updating {n_updates} changed row(s) "
                f"(page_size={page_size})...",
                flush=True,
            )
            t0 = time.perf_counter()
            execute_values(
                cur,
                """
                UPDATE event_matches AS em
                SET red_win_prob = v.red_win_prob::double precision,
                    blue_win_prob = v.blue_win_prob::double precision,
                    red_predicted_score = v.red_predicted_score::double precision,
                    blue_predicted_score = v.blue_predicted_score::double precision,
                    pre_match_teams = v.pre_match_teams::jsonb
                FROM (VALUES %s) AS v(
                    red_win_prob,
                    blue_win_prob,
                    red_predicted_score,
                    blue_predicted_score,
                    pre_match_teams,
                    match_key
                )
                WHERE em.match_key = v.match_key
                """,
                updates,
                template="(%s, %s, %s, %s, %s::jsonb, %s)",
                page_size=page_size,
            )
            print(
                f"Match predictions {year}: bulk update finished ({time.perf_counter() - t0:.1f}s)",
                flush=True,
            )
        conn.commit()
        return {
            "written": len(updates),
            "computed": len(pred_by_key),
            "skipped_unchanged": skipped_unchanged,
            "skipped_missing": skipped_missing,
            "skipped_bad": skipped_bad,
        }
    finally:
        cur.close()


def _parse_team_csv(team_csv) -> List[int]:
    if not team_csv:
        return []
    out: List[int] = []
    for raw in str(team_csv).split(","):
        tok = raw.strip()
        if tok.lower().startswith("frc"):
            tok = tok[3:]
        digits = "".join(ch for ch in tok if ch.isdigit())
        if digits:
            out.append(int(digits))
    return out


def _event_sort_key(data: DbPredictionData, event_key: str) -> Tuple[str, str]:
    return data.event_order.get(event_key, ("", event_key))


def _prior_event_key(data: DbPredictionData, team: TeamSeasonData, event_key: str) -> Optional[str]:
    current = _event_sort_key(data, event_key)
    candidates: List[Tuple[Tuple[str, str], str]] = []
    for ek, perf in team.event_perf.items():
        if ek == event_key:
            continue
        sort_key = _event_sort_key(data, ek)
        if sort_key < current:
            candidates.append((sort_key, ek))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def team_rating_value(
    data: DbPredictionData,
    team_number: int,
    event_key: str,
    config: PredictionConfig,
) -> float:
    """Return rating value for one team."""
    team = data.season.get(team_number)
    prior = data.prior_season.get(team_number)

    def _from_perf(perf: Dict[str, float]) -> float:
        if config.rating_field == "raw":
            return float(perf.get("raw") or 0.0)
        return float(perf.get("ace") or 0.0)

    def _from_season(td: Optional[TeamSeasonData]) -> float:
        if not td:
            return 0.0
        if config.rating_field == "raw":
            return td.raw
        return td.ace

    scope = config.rating_scope

    if scope == "season":
        return _from_season(team)

    if scope == "prior_year":
        return _from_season(prior)

    if team:
        if scope == "event":
            perf = team.event_perf.get(event_key)
            if perf:
                return _from_perf(perf)
        elif scope in ("prior_event", "prior_event_or_prior_year"):
            pek = _prior_event_key(data, team, event_key)
            if pek and pek in team.event_perf:
                return _from_perf(team.event_perf[pek])
            if scope == "prior_event_or_prior_year" and prior:
                return _from_season(prior)

    if prior and scope in ("event", "prior_event", "prior_event_or_prior_year"):
        return _from_season(prior)

    return 0.0


def alliance_strength_db(
    data: DbPredictionData,
    team_numbers: List[int],
    event_key: str,
    config: PredictionConfig,
) -> float:
    ratings = [team_rating_value(data, tn, event_key, config) for tn in team_numbers]
    if not ratings:
        return 0.0
    if config.aggregation == "mean":
        return sum(ratings) / len(ratings)
    return sum(ratings)


def predict_win_probability(
    red_strength: float,
    blue_strength: float,
    config: PredictionConfig,
) -> Tuple[float, float]:
    """Map alliance strength differential to win probability.

    Uses logistic on normalized margin (red−blue)/(red+blue), which is invariant
    when ACE values shift across game seasons (e.g. 2026 vs 2024 scoring scale).
    """
    total = red_strength + blue_strength
    if total == 0:
        return 0.5, 0.5
    margin = (red_strength - blue_strength) / total
    x = max(-60.0, min(60.0, -config.win_scale_base * margin))
    p_red = 1.0 / (1.0 + math.exp(x))
    p_red = max(config.prob_min, min(config.prob_max, p_red))
    return p_red, 1.0 - p_red


def predict_match_db(data: DbPredictionData, row: MatchRow, config: PredictionConfig) -> MatchPrediction:
    red_strength = alliance_strength_db(data, row.red_teams, row.event_key, config)
    blue_strength = alliance_strength_db(data, row.blue_teams, row.event_key, config)
    p_red, p_blue = predict_win_probability(red_strength, blue_strength, config)
    return MatchPrediction(
        match_key=row.match_key,
        p_red=p_red,
        p_blue=p_blue,
        red_predicted_score=red_strength,
        blue_predicted_score=blue_strength,
    )


def predict_all_matches_db(data: DbPredictionData, config: PredictionConfig) -> List[MatchPrediction]:
    return [predict_match_db(data, row, config) for row in data.matches]
