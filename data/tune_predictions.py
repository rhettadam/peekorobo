#!/usr/bin/env python3
"""Master tuner for walk-forward pre_match prediction accuracy.

Loads TBA matches once (with optional disk cache), then coordinate-descent
searches prediction + ACE parameters. Always evaluates with pre_match scope.

Examples:
  python data/tune_predictions.py --year 2025
  python data/tune_predictions.py --start-year 2024 --end-year 2025 --per-year
  python data/tune_predictions.py --year 2026 --mode quick --cache-dir data/.tune_cache
  python data/tune_predictions.py --year 2025 --baseline-only
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

import run as run_module
from db_target import describe_db_target
from prediction import (
    AceParams,
    DbPredictionData,
    PredictionAccuracySummary,
    PredictionConfig,
    compute_prediction_accuracy_summary,
    compute_walk_forward_strengths,
    load_prediction_data_from_db,
    predictions_from_strengths,
)
from run import (
    finalize_pre_match_team,
    get_pg_connection,
    match_cache,
    preload_confidence_lookups_from_match_cache,
)
from tba_match_cache import load_matches_by_event

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **kwargs):
        return iterable


Metric = Literal["brier", "accuracy"]
Mode = Literal["quick", "standard", "exhaustive"]


@dataclass
class YearBundle:
    year: int
    data: DbPredictionData
    matches_by_event: Dict[str, list]


@dataclass
class TuneKnobs:
    """All tunable prediction + walk-forward ACE parameters."""

    win_scale_base: float = 6.4
    prob_min: float = 0.02
    prob_max: float = 0.98
    rating_field: str = "ace"
    aggregation: str = "sum"
    method: str = "residual_shrink"
    k_base: float = 0.4
    shrink: float = 0.05
    spike_damp: float = 1.0
    k_up: float = 1.0
    k_down: float = 1.0
    partner_cap: float = 1.25
    carry_prior: bool = True
    prior_blend: float = 1.0
    confidence_ceiling: float = 0.88

    @classmethod
    def from_env(cls) -> "TuneKnobs":
        pred = PredictionConfig.from_env()
        ace = AceParams.from_env()
        return cls(
            win_scale_base=pred.win_scale_base,
            prob_min=pred.prob_min,
            prob_max=pred.prob_max,
            rating_field=pred.rating_field,
            aggregation=pred.aggregation,
            method=ace.method,
            k_base=ace.k_base,
            shrink=ace.shrink,
            spike_damp=ace.spike_damp,
            k_up=ace.k_up,
            k_down=ace.k_down,
            partner_cap=ace.partner_cap,
            carry_prior=ace.carry_prior,
            prior_blend=ace.prior_blend,
            confidence_ceiling=float(os.environ.get("ACE_CONFIDENCE_CEILING", "0.88")),
        )

    def to_pred_config(self) -> PredictionConfig:
        return PredictionConfig(
            win_scale_base=self.win_scale_base,
            prob_min=self.prob_min,
            prob_max=self.prob_max,
            rating_field=self.rating_field,  # type: ignore[arg-type]
            rating_scope="pre_match",
            aggregation=self.aggregation,  # type: ignore[arg-type]
        )

    def to_ace_params(self) -> AceParams:
        return AceParams(
            method=self.method,  # type: ignore[arg-type]
            k_base=self.k_base,
            shrink=self.shrink,
            spike_damp=self.spike_damp,
            k_up=self.k_up,
            k_down=self.k_down,
            partner_cap=self.partner_cap,
            carry_prior=self.carry_prior,
            prior_blend=self.prior_blend,
        )

    def env_lines(self) -> List[str]:
        return [
            f"ACE_WIN_PROB_SCALE={self.win_scale_base}",
            f"PRED_PROB_MIN={self.prob_min}",
            f"PRED_PROB_MAX={self.prob_max}",
            f"PRED_RATING_FIELD={self.rating_field}",
            f"PRED_RATING_SCOPE=pre_match",
            f"PRED_AGGREGATION={self.aggregation}",
            f"ACE_METHOD={self.method}",
            f"ACE_K_BASE={self.k_base}",
            f"ACE_SHRINK={self.shrink}",
            f"ACE_SPIKE_DAMP={self.spike_damp}",
            f"ACE_K_UP={self.k_up}",
            f"ACE_K_DOWN={self.k_down}",
            f"ACE_PARTNER_CAP={self.partner_cap}",
            f"ACE_CARRY_PRIOR={'1' if self.carry_prior else '0'}",
            f"ACE_PRIOR_BLEND={self.prior_blend}",
            f"ACE_CONFIDENCE_CEILING={self.confidence_ceiling}",
        ]


@dataclass
class TuneOutcome:
    knobs: TuneKnobs
    summary: PredictionAccuracySummary
    label: str = "pooled"


PRED_PARAM_ORDER = [
    "win_scale_base",
    "aggregation",
    "rating_field",
    "prob_min",
    "prob_max",
]

ACE_PARAM_ORDER = [
    "confidence_ceiling",
    "k_base",
    "shrink",
    "spike_damp",
    "k_up",
    "k_down",
    "partner_cap",
    "carry_prior",
    "prior_blend",
    "method",
]

GRIDS: Dict[Mode, Dict[str, List[Any]]] = {
    "quick": {
        "win_scale_base": [5.6, 6.4, 7.2, 8.0],
        "aggregation": ["sum", "mean"],
        "rating_field": ["ace", "raw"],
        "prob_min": [0.02],
        "prob_max": [0.98],
        "confidence_ceiling": [0.88],
        "k_base": [0.35, 0.4, 0.45],
        "shrink": [0.03, 0.05, 0.08],
        "spike_damp": [1.0],
        "k_up": [1.0],
        "k_down": [1.0],
        "partner_cap": [1.0, 1.25],
        "carry_prior": [True],
        "prior_blend": [1.0],
        "method": ["residual_shrink"],
    },
    "standard": {
        "win_scale_base": [4.8, 5.6, 6.4, 7.2, 8.0, 9.0],
        "aggregation": ["sum", "mean"],
        "rating_field": ["ace", "raw"],
        "prob_min": [0.02, 0.05],
        "prob_max": [0.95, 0.98],
        "confidence_ceiling": [0.80, 0.88, 0.95],
        "k_base": [0.30, 0.35, 0.4, 0.45, 0.5],
        "shrink": [0.0, 0.05, 0.10],
        "spike_damp": [0.75, 1.0],
        "k_up": [0.9, 1.0, 1.1],
        "k_down": [0.9, 1.0, 1.1],
        "partner_cap": [0.0, 1.0, 1.25, 1.5],
        "carry_prior": [True, False],
        "prior_blend": [0.75, 1.0],
        "method": ["residual_shrink"],
    },
    "exhaustive": {
        "win_scale_base": [4.0, 5.0, 5.6, 6.0, 6.4, 7.0, 7.6, 8.5, 10.0],
        "aggregation": ["sum", "mean"],
        "rating_field": ["ace", "raw"],
        "prob_min": [0.01, 0.02, 0.05, 0.10],
        "prob_max": [0.90, 0.95, 0.98, 0.99],
        "confidence_ceiling": [0.75, 0.80, 0.88, 0.95, 1.0],
        "k_base": [0.25, 0.30, 0.35, 0.4, 0.45, 0.5, 0.55],
        "shrink": [0.0, 0.03, 0.05, 0.08, 0.12, 0.15],
        "spike_damp": [0.5, 0.75, 1.0],
        "k_up": [0.8, 0.9, 1.0, 1.1, 1.2],
        "k_down": [0.8, 0.9, 1.0, 1.1, 1.2],
        "partner_cap": [0.0, 0.75, 1.0, 1.25, 1.5, 1.75],
        "carry_prior": [True, False],
        "prior_blend": [0.5, 0.75, 1.0],
        "method": ["residual_shrink", "residual"],
    },
}


def _discover_years(conn) -> List[int]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT CAST(LEFT(event_key, 4) AS INTEGER) AS yr
            FROM events
            WHERE event_key ~ '^[0-9]{4}'
            ORDER BY yr
            """
        )
        return [int(row[0]) for row in cur.fetchall() if row[0] is not None]
    finally:
        cur.close()


def _resolve_years(args, conn) -> List[int]:
    if args.years:
        return sorted({int(y) for y in args.years.split(",")})
    if args.year is not None:
        return [int(args.year)]
    discovered = _discover_years(conn)
    if not discovered:
        return []
    start = args.start_year if args.start_year is not None else min(discovered)
    end = args.end_year if args.end_year is not None else max(discovered)
    return [y for y in discovered if start <= y <= end]


def load_year_bundle(
    year: int,
    *,
    cache_dir: Optional[Path],
    max_workers: int,
    refetch: bool,
    sample_events: Optional[float],
) -> Optional[YearBundle]:
    conn = get_pg_connection()
    try:
        data = load_prediction_data_from_db(conn, year)
    finally:
        conn.close()

    if not data.matches:
        print(f"  {year}: no matches in DB, skipping", flush=True)
        return None

    event_keys = sorted(data.event_order.keys())
    if sample_events and 0 < sample_events < 1:
        random.seed(year)
        k = max(1, int(len(event_keys) * sample_events))
        event_keys = sorted(random.sample(event_keys, k))
        allowed = set(event_keys)
        data = replace(
            data,
            matches=[m for m in data.matches if m.event_key in allowed],
            event_order={ek: v for ek, v in data.event_order.items() if ek in allowed},
        )
        print(
            f"  {year}: sampled {len(event_keys)} event(s) ({sample_events:.0%}) for faster tuning",
            flush=True,
        )

    matches_by_event = load_matches_by_event(
        year, event_keys, cache_dir=cache_dir, max_workers=max_workers, refetch=refetch
    )
    if not matches_by_event:
        print(f"  {year}: no TBA match data", flush=True)
        return None

    for ek, matches in matches_by_event.items():
        match_cache[ek] = matches
    preload_confidence_lookups_from_match_cache(year)
    return YearBundle(year=year, data=data, matches_by_event=matches_by_event)


def _apply_confidence_ceiling(ceiling: float) -> None:
    run_module.CONFIDENCE_CEILING = float(ceiling)


def _score(summary: PredictionAccuracySummary, metric: Metric) -> Tuple[float, float]:
    """Return (primary, secondary) for sorting. Higher is better."""
    if metric == "brier":
        primary = -(summary.brier if summary.brier is not None else 999.0)
        secondary = summary.pct if summary.pct is not None else 0.0
    else:
        primary = summary.pct if summary.pct is not None else 0.0
        secondary = -(summary.brier if summary.brier is not None else 999.0)
    return primary, secondary


def evaluate_knobs(
    bundles: List[YearBundle],
    knobs: TuneKnobs,
    *,
    metric: Metric,
    strength_cache: Optional[Dict[str, Dict[str, Tuple[float, float]]]] = None,
) -> PredictionAccuracySummary:
    _apply_confidence_ceiling(knobs.confidence_ceiling)
    pred_config = knobs.to_pred_config()
    ace_params = knobs.to_ace_params()

    all_matches = []
    prob_by_key: Dict[str, float] = {}

    for bundle in bundles:
        cache_key = _strength_cache_key(knobs)
        strengths = None
        if strength_cache is not None:
            strengths = strength_cache.get(f"{bundle.year}:{cache_key}")
        if strengths is None:
            strengths, _ = compute_walk_forward_strengths(
                bundle.data,
                bundle.matches_by_event,
                pred_config,
                ace_params,
                finalize_pre_match_team,
            )
            if strength_cache is not None:
                strength_cache[f"{bundle.year}:{cache_key}"] = strengths

        preds = predictions_from_strengths(bundle.data, strengths, pred_config)
        for p in preds:
            prob_by_key[p.match_key] = p.p_red
        all_matches.extend(bundle.data.matches)

    return compute_prediction_accuracy_summary(all_matches, prob_by_match_key=prob_by_key)


def _strength_cache_key(knobs: TuneKnobs) -> str:
    """Hash ACE-affecting fields + rating_field/aggregation for strength cache."""
    return (
        f"{knobs.method}|{knobs.k_base}|{knobs.shrink}|{knobs.spike_damp}|"
        f"{knobs.k_up}|{knobs.k_down}|{knobs.partner_cap}|{int(knobs.carry_prior)}|"
        f"{knobs.prior_blend}|{knobs.confidence_ceiling}|{knobs.rating_field}|{knobs.aggregation}"
    )


def coordinate_descent(
    bundles: List[YearBundle],
    start: TuneKnobs,
    grid: Dict[str, List[Any]],
    param_order: List[str],
    *,
    metric: Metric,
    rounds: int,
    strength_cache: Dict[str, Dict[str, Tuple[float, float]]],
    label: str,
) -> TuneOutcome:
    best = TuneOutcome(
        knobs=replace(start),
        summary=evaluate_knobs(bundles, start, metric=metric, strength_cache=strength_cache),
        label=label,
    )
    print(f"\n[{label}] baseline: {best.summary.label()} (optimizing {metric})", flush=True)

    for round_idx in range(1, rounds + 1):
        print(f"[{label}] coordinate descent round {round_idx}/{rounds}", flush=True)
        improved = False
        for param in param_order:
            candidates = grid.get(param)
            if not candidates:
                continue
            param_best = best
            iterator = tqdm(candidates, desc=f"  {param}", leave=False)
            for value in iterator:
                trial = replace(best.knobs, **{param: value})
                summary = evaluate_knobs(
                    bundles, trial, metric=metric, strength_cache=strength_cache
                )
                if _score(summary, metric) > _score(param_best.summary, metric):
                    param_best = TuneOutcome(knobs=trial, summary=summary, label=label)
            if _score(param_best.summary, metric) > _score(best.summary, metric):
                print(
                    f"  {param}: {getattr(best.knobs, param)!r} -> {getattr(param_best.knobs, param)!r} "
                    f"({param_best.summary.label()})",
                    flush=True,
                )
                best = param_best
                improved = True
        if not improved:
            print(f"[{label}] round {round_idx}: no improvement, stopping early", flush=True)
            break

    return best


def tune_bundles(
    bundles: List[YearBundle],
    *,
    mode: Mode,
    metric: Metric,
    rounds_pred: int,
    rounds_ace: int,
    label: str,
) -> TuneOutcome:
    grid = GRIDS[mode]
    strength_cache: Dict[str, Dict[str, Tuple[float, float]]] = {}
    start = TuneKnobs.from_env()

    pred_best = coordinate_descent(
        bundles,
        start,
        grid,
        PRED_PARAM_ORDER,
        metric=metric,
        rounds=rounds_pred,
        strength_cache=strength_cache,
        label=f"{label}/pred",
    )
    ace_best = coordinate_descent(
        bundles,
        pred_best.knobs,
        grid,
        ACE_PARAM_ORDER,
        metric=metric,
        rounds=rounds_ace,
        strength_cache=strength_cache,
        label=f"{label}/ace",
    )
    # Final pass on win_scale with settled ACE strengths.
    final = coordinate_descent(
        bundles,
        ace_best.knobs,
        grid,
        ["win_scale_base"],
        metric=metric,
        rounds=1,
        strength_cache=strength_cache,
        label=f"{label}/final-scale",
    )
    final.label = label
    return final


def _print_outcome(title: str, outcome: TuneOutcome) -> None:
    print(f"\n=== {title} ===", flush=True)
    print(f"  {outcome.summary.label()}", flush=True)
    print("  Recommended env:", flush=True)
    for line in outcome.knobs.env_lines():
        print(f"    {line}", flush=True)


def _write_results(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote results to {path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tune walk-forward pre_match prediction parameters for accuracy."
    )
    parser.add_argument("--year", type=int, help="Single evaluation year")
    parser.add_argument("--years", type=str, help="Comma-separated years, e.g. 2024,2025")
    parser.add_argument("--start-year", type=int, help="First year (inclusive)")
    parser.add_argument("--end-year", type=int, help="Last year (inclusive)")
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "exhaustive"],
        default="standard",
        help="Search breadth (default: standard)",
    )
    parser.add_argument(
        "--metric",
        choices=["brier", "accuracy"],
        default="brier",
        help="Primary objective — brier (lower better) recommended (default: brier)",
    )
    parser.add_argument(
        "--per-year",
        action="store_true",
        help="Also find best knobs per season (in addition to pooled)",
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Print current env baseline accuracy and exit",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/.tune_cache"),
        help="Disk cache for TBA match JSON (default: data/.tune_cache)",
    )
    parser.add_argument("--refetch", action="store_true", help="Ignore TBA disk cache")
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument(
        "--sample-events",
        type=float,
        default=None,
        help="Fraction of events to sample per year for faster iteration (0,1)",
    )
    parser.add_argument(
        "--rounds-pred",
        type=int,
        default=2,
        help="Coordinate descent rounds for prediction params",
    )
    parser.add_argument(
        "--rounds-ace",
        type=int,
        default=2,
        help="Coordinate descent rounds for ACE params",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/tune_results.json"),
        help="JSON output path (default: data/tune_results.json)",
    )
    args = parser.parse_args()

    print(f"DB target: {describe_db_target()} (read-only tuning)", flush=True)
    if not os.environ.get("TBA_API_KEYS", "").strip():
        print("TBA_API_KEYS is required.", file=sys.stderr)
        sys.exit(1)

    conn = get_pg_connection()
    try:
        years = _resolve_years(args, conn)
    finally:
        conn.close()

    if not years:
        print("No years to tune.", flush=True)
        sys.exit(1)

    print(f"Loading {len(years)} year(s): {years}", flush=True)
    t0 = time.time()
    bundles: List[YearBundle] = []
    for year in years:
        bundle = load_year_bundle(
            year,
            cache_dir=args.cache_dir,
            max_workers=args.max_workers,
            refetch=args.refetch,
            sample_events=args.sample_events,
        )
        if bundle:
            bundles.append(bundle)
    if not bundles:
        print("No data loaded.", flush=True)
        sys.exit(1)
    print(f"Loaded {len(bundles)} year bundle(s) in {time.time() - t0:.1f}s", flush=True)

    baseline = TuneKnobs.from_env()
    baseline_summary = evaluate_knobs(bundles, baseline, metric=args.metric)
    _print_outcome("Baseline (current env)", TuneOutcome(baseline, baseline_summary, "pooled"))

    if args.baseline_only:
        return

    results: Dict[str, Any] = {
        "metric": args.metric,
        "mode": args.mode,
        "years": [b.year for b in bundles],
        "baseline": {
            "knobs": asdict(baseline),
            "summary": asdict(baseline_summary),
        },
    }

    pooled = tune_bundles(
        bundles,
        mode=args.mode,
        metric=args.metric,
        rounds_pred=args.rounds_pred,
        rounds_ace=args.rounds_ace,
        label="pooled",
    )
    _print_outcome("Best pooled", pooled)
    results["pooled"] = {
        "knobs": asdict(pooled.knobs),
        "summary": {
            "correct": pooled.summary.correct,
            "total": pooled.summary.total,
            "pct": pooled.summary.pct,
            "brier": pooled.summary.brier,
            "favorite_win_pct": pooled.summary.favorite_win_pct,
        },
        "env": pooled.knobs.env_lines(),
    }

    if args.per_year:
        per_year: Dict[str, Any] = {}
        for bundle in bundles:
            outcome = tune_bundles(
                [bundle],
                mode=args.mode,
                metric=args.metric,
                rounds_pred=args.rounds_pred,
                rounds_ace=args.rounds_ace,
                label=str(bundle.year),
            )
            _print_outcome(f"Best {bundle.year}", outcome)
            per_year[str(bundle.year)] = {
                "knobs": asdict(outcome.knobs),
                "summary": {
                    "correct": outcome.summary.correct,
                    "total": outcome.summary.total,
                    "pct": outcome.summary.pct,
                    "brier": outcome.summary.brier,
                    "favorite_win_pct": outcome.summary.favorite_win_pct,
                },
                "env": outcome.knobs.env_lines(),
            }
        results["per_year"] = per_year

    _write_results(args.output, results)
    print(f"\nTotal elapsed: {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
