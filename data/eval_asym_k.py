#!/usr/bin/env python3
"""Walk-forward bake-off for asymmetric EMA (k_up / k_down).

Stratifies alliance score bias into:
  - overall
  - elite: alliance includes a season-top-N team (by end-of-walk RAW)
  - mid: everyone else

Usage (from repo `data/`):

    python eval_asym_k.py --year 2026 --limit-events 40
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_attribution import TeamPhaseState, walk_forward_metrics


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _mae(xs: List[float]) -> float:
    return sum(abs(x) for x in xs) / len(xs) if xs else float("nan")


def run_season_walk(
    ordered: List[Tuple[str, List[dict]]],
    year: int,
    k_base: float,
    shrink: float,
    spike_damp: float,
    k_up: float,
    k_down: float,
    win_scale: float,
) -> Tuple[Dict[str, float], Dict[str, float], List[dict]]:
    """Carry priors across events; return season finals + pooled score rows."""
    priors: Dict[str, Tuple[float, float, float]] = {}
    all_rows: List[dict] = []
    abs_err = bias_sum = 0.0
    n_score = 0
    correct = total_wl = 0

    for _ek, matches in ordered:
        m = walk_forward_metrics(
            matches,
            year,
            method="residual_shrink",
            k_base=k_base,
            shrink=shrink,
            win_scale=win_scale,
            spike_damp=spike_damp,
            prior_means=priors,
            seed_priors=True,
            k_up=k_up,
            k_down=k_down,
        )
        ns = int(m["n_score_obs"])
        nw = int(m["n_wl"])
        if ns:
            abs_err += m["score_mae"] * ns
            bias_sum += m["score_bias"] * ns
            n_score += ns
        if nw:
            correct += round(m["win_accuracy"] / 100.0 * nw)
            total_wl += nw

        rows: List[dict] = m.get("score_rows") or []  # type: ignore[assignment]
        for r in rows:
            r = dict(r)
            r["event"] = _ek
            all_rows.append(r)

        finals: Dict[str, TeamPhaseState] = m.get("final_states") or {}  # type: ignore[assignment]
        for key, st in finals.items():
            if st.initialized:
                priors[key] = (st.auto, st.teleop, st.endgame)

    season_raw = {k: sum(v) for k, v in priors.items()}
    metrics = {
        "score_mae": abs_err / n_score if n_score else float("nan"),
        "score_bias": bias_sum / n_score if n_score else float("nan"),
        "win_accuracy": (correct / total_wl * 100.0) if total_wl else float("nan"),
        "n_score_obs": float(n_score),
        "n_wl": float(total_wl),
    }
    return metrics, season_raw, all_rows


def stratify(
    rows: List[dict],
    season_raw: Dict[str, float],
    top_n: int,
) -> Dict[str, Dict[str, float]]:
    ranked = sorted(season_raw.items(), key=lambda kv: kv[1], reverse=True)
    elite: Set[str] = {k for k, _ in ranked[:top_n]}

    overall_bias: List[float] = []
    elite_bias: List[float] = []
    mid_bias: List[float] = []
    for r in rows:
        keys = r.get("keys") or []
        b = float(r["bias"])
        overall_bias.append(b)
        if any(k in elite for k in keys):
            elite_bias.append(b)
        else:
            mid_bias.append(b)

    def pack(xs: List[float]) -> Dict[str, float]:
        return {"bias": _mean(xs), "mae": _mae(xs), "n": float(len(xs))}

    return {
        "overall": pack(overall_bias),
        "elite": pack(elite_bias),
        "mid": pack(mid_bias),
        "elite_n_teams": float(len(elite)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--limit-events", type=int, default=40)
    ap.add_argument("--top-n", type=int, default=150, help="Season-top-N RAW for elite slice")
    ap.add_argument("--k-base", type=float, default=0.4)
    ap.add_argument("--shrink", type=float, default=0.05)
    ap.add_argument("--spike-damp", type=float, default=1.0)
    ap.add_argument("--win-scale", type=float, default=0.04)
    ap.add_argument(
        "--event",
        action="append",
        default=None,
        help="Optional event key(s); repeatable. Default: first N by TBA priority.",
    )
    args = ap.parse_args()

    from eval_ace import _load_matches_tba, _ordered_events

    if args.event:
        import run as pipeline

        ordered: List[Tuple[str, List[dict]]] = []
        for ek in args.event:
            raw = pipeline.tba_get(f"event/{ek}/matches") or []
            if raw:
                ordered.append((ek, raw))
        print(f"Loaded {len(ordered)} explicit event(s)")
    else:
        matches, start_dates = _load_matches_tba(args.year, args.limit_events)
        ordered = _ordered_events(matches, start_dates)
        print(f"Loaded {len(ordered)} events / {len(matches)} matches ({args.year})")

    # Grid: baseline + moderate/aggressive up, with optional down adjustment.
    grid = [
        (1.00, 1.00),
        (1.20, 1.00),
        (1.30, 1.00),
        (1.40, 1.00),
        (1.50, 1.00),
        (1.60, 1.00),
        (1.30, 1.15),
        (1.40, 1.15),
        (1.50, 1.15),
        (1.40, 1.25),
        (1.50, 1.25),
        (1.60, 1.25),
        (1.75, 1.25),
    ]

    header = (
        f"{'k_up':>5} {'k_dn':>5} {'MAE':>7} {'bias':>7} "
        f"{'elite':>7} {'mid':>7} {'e-m':>7} {'win%':>6} {'n_e':>6}"
    )
    print(header)
    print("-" * len(header))

    best: Optional[Tuple[float, float, float]] = None  # (score, k_up, k_down)
    for k_up, k_down in grid:
        metrics, season_raw, rows = run_season_walk(
            ordered,
            args.year,
            k_base=args.k_base,
            shrink=args.shrink,
            spike_damp=args.spike_damp,
            k_up=k_up,
            k_down=k_down,
            win_scale=args.win_scale,
        )
        slices = stratify(rows, season_raw, args.top_n)
        e_bias = slices["elite"]["bias"]
        m_bias = slices["mid"]["bias"]
        # Prefer closing the elite hole without blowing midfield overprediction.
        # Score = |elite_bias| + 0.5*|mid_bias| + 0.25*|overall_bias|
        score = abs(e_bias) + 0.5 * abs(m_bias) + 0.25 * abs(metrics["score_bias"])
        if best is None or score < best[0]:
            best = (score, k_up, k_down)

        print(
            f"{k_up:5.2f} {k_down:5.2f} {metrics['score_mae']:7.2f} {metrics['score_bias']:7.2f} "
            f"{e_bias:7.2f} {m_bias:7.2f} {e_bias - m_bias:7.2f} "
            f"{metrics['win_accuracy']:6.1f} {slices['elite']['n']:6.0f}"
        )

    assert best is not None
    print(
        f"\nSuggested (min |elite|+0.5|mid|+0.25|all|): "
        f"ACE_K_UP={best[1]} ACE_K_DOWN={best[2]}  (score={best[0]:.2f})"
    )
    print(
        "Elite = alliance containing a season-top-"
        f"{args.top_n} team by end-of-walk RAW. Bias = pred - actual."
    )


if __name__ == "__main__":
    main()
