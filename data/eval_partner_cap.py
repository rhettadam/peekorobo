#!/usr/bin/env python3
"""Walk-forward bake-off for partner credit cap (ACE_PARTNER_CAP).

Reports elite/mid score bias plus end-of-walk season shape (# ≥300, #1−#2 gap).

Usage (from repo `data/`):

    python eval_partner_cap.py --year 2026 --limit-events 50
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


def run_season_walk(
    ordered: List[Tuple[str, List[dict]]],
    year: int,
    k_base: float,
    shrink: float,
    spike_damp: float,
    partner_cap: float,
    win_scale: float,
) -> Tuple[Dict[str, float], Dict[str, float], List[dict]]:
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
            k_up=1.0,
            k_down=1.0,
            partner_cap=partner_cap,
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
        return {"bias": _mean(xs), "n": float(len(xs))}

    return {
        "overall": pack(overall_bias),
        "elite": pack(elite_bias),
        "mid": pack(mid_bias),
    }


def shape_stats(season_raw: Dict[str, float]) -> Dict[str, float]:
    vals = sorted(season_raw.values(), reverse=True)
    if not vals:
        return {"n300": 0.0, "n275": 0.0, "gap12": float("nan"), "top100_spread": float("nan")}
    top100 = vals[:100]
    return {
        "n300": float(sum(1 for v in vals if v >= 300)),
        "n275": float(sum(1 for v in vals if v >= 275)),
        "gap12": float(vals[0] - vals[1]) if len(vals) > 1 else 0.0,
        "top100_spread": float(top100[0] - top100[-1]) if top100 else float("nan"),
        "max": float(vals[0]),
        "p2": float(vals[1]) if len(vals) > 1 else float("nan"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--limit-events", type=int, default=50)
    ap.add_argument("--top-n", type=int, default=150)
    ap.add_argument("--k-base", type=float, default=0.4)
    ap.add_argument("--shrink", type=float, default=0.05)
    ap.add_argument("--spike-damp", type=float, default=1.0)
    ap.add_argument("--win-scale", type=float, default=0.04)
    args = ap.parse_args()

    from eval_ace import _load_matches_tba, _ordered_events

    matches, start_dates = _load_matches_tba(args.year, args.limit_events)
    ordered = _ordered_events(matches, start_dates)
    print(f"Loaded {len(ordered)} events / {len(matches)} matches ({args.year})")

    # 0 = off (uncapped residual)
    grid = [0.0, 1.15, 1.25, 1.35, 1.50]

    header = (
        f"{'cap':>5} {'MAE':>7} {'bias':>7} {'elite':>7} {'mid':>7} "
        f"{'n300':>5} {'n275':>5} {'gap12':>6} {'spr100':>6} {'win%':>6}"
    )
    print(header)
    print("-" * len(header))

    best: Optional[Tuple[float, float]] = None  # (score, cap)
    for cap in grid:
        metrics, season_raw, rows = run_season_walk(
            ordered,
            args.year,
            k_base=args.k_base,
            shrink=args.shrink,
            spike_damp=args.spike_damp,
            partner_cap=cap,
            win_scale=args.win_scale,
        )
        slices = stratify(rows, season_raw, args.top_n)
        shape = shape_stats(season_raw)
        e_bias = slices["elite"]["bias"]
        m_bias = slices["mid"]["bias"]
        # Prefer closing elite hole + more ≥300, without huge midfield overprediction
        # or a ballooning #1 gap.
        score = (
            abs(e_bias)
            + 0.4 * abs(m_bias)
            + 0.2 * abs(metrics["score_bias"])
            + 0.15 * shape["gap12"]
            - 2.0 * shape["n300"]
            - 0.5 * shape["n275"]
        )
        if best is None or score < best[0]:
            best = (score, cap)

        label = "off" if cap <= 0 else f"{cap:.2f}"
        print(
            f"{label:>5} {metrics['score_mae']:7.2f} {metrics['score_bias']:7.2f} "
            f"{e_bias:7.2f} {m_bias:7.2f} "
            f"{shape['n300']:5.0f} {shape['n275']:5.0f} {shape['gap12']:6.1f} "
            f"{shape['top100_spread']:6.1f} {metrics['win_accuracy']:6.1f}"
        )

    assert best is not None
    chosen = "off" if best[1] <= 0 else f"{best[1]}"
    print(f"\nSuggested ACE_PARTNER_CAP={chosen}  (score={best[0]:.2f})")
    print(
        f"Elite = alliance with a season-top-{args.top_n} team. "
        "Bias = pred - actual. Shape from end-of-walk RAW."
    )


if __name__ == "__main__":
    main()
