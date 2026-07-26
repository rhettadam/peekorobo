#!/usr/bin/env python3
"""Walk-forward ACE attribution bake-off (fetches matches + breakdowns from TBA).

Usage (from repo `data/` directory):

    python eval_ace.py --year 2026 --limit-events 30
    python eval_ace.py --year 2026 --limit-events 40 --config-bakeoff
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_attribution import Method, multi_event_walk_forward, walk_forward_metrics

METHODS: List[Method] = ["baseline_current", "equal_split", "residual", "residual_shrink"]


def aggregate_event_metrics(
    events_matches: List[List[dict]],
    year: int,
    method: Method,
    k_base: float,
    shrink: float,
    win_scale: float,
    spike_damp: float = 0.5,
    warmup_frac: float = 0.0,
) -> Dict[str, float]:
    """Reset RAW per event (matches production), then pool score/win metrics."""
    abs_err = bias_sum = 0.0
    n_score = 0
    correct = total_wl = 0
    brier_sum = 0.0
    n_brier = 0
    for matches in events_matches:
        m = walk_forward_metrics(
            matches,
            year,
            method=method,
            k_base=k_base,
            shrink=shrink,
            win_scale=win_scale,
            spike_damp=spike_damp,
            warmup_frac=warmup_frac,
        )
        ns = int(m["n_score_obs"])
        nw = int(m["n_wl"])
        nb = int(m.get("n_brier", m["n_wl"]))
        if ns:
            abs_err += m["score_mae"] * ns
            bias_sum += m["score_bias"] * ns
            n_score += ns
        if nw:
            correct += round(m["win_accuracy"] / 100.0 * nw)
            total_wl += nw
        if nb and m["brier"] == m["brier"]:  # not NaN
            brier_sum += m["brier"] * nb
            n_brier += nb
    return {
        "score_mae": abs_err / n_score if n_score else float("nan"),
        "score_bias": bias_sum / n_score if n_score else float("nan"),
        "win_accuracy": (correct / total_wl * 100.0) if total_wl else float("nan"),
        "brier": brier_sum / n_brier if n_brier else float("nan"),
        "n_score_obs": float(n_score),
        "n_wl": float(total_wl),
    }


def _load_matches_tba(year: int, limit_events: int | None) -> Tuple[List[dict], Dict[str, str]]:
    # Import after path setup; uses TBA_API_KEYS from env
    import run as pipeline

    events = pipeline.tba_get(f"events/{year}") or []

    def _prio(e: dict) -> tuple:
        et = e.get("event_type") if e.get("event_type") is not None else 99
        return (0 if et in (0, 1, 2, 3, 4, 5, 6) else 1, e.get("start_date") or "", e.get("key") or "")

    events = sorted(events, key=_prio)
    start_dates: Dict[str, str] = {
        e["key"]: (e.get("start_date") or "") for e in events if e.get("key")
    }

    matches: List[dict] = []
    used = 0
    for ev in events:
        if limit_events and used >= limit_events:
            break
        ek = ev.get("key")
        if not ek:
            continue
        raw = pipeline.tba_get(f"event/{ek}/matches") or []
        if not raw:
            continue
        for m in raw:
            m = dict(m)
            m["event_key"] = ek
            matches.append(m)
        used += 1
        print(f"  {ek}: {len(raw)} matches")
    return matches, start_dates


def _ordered_events(
    matches: List[dict], start_dates: Dict[str, str]
) -> List[Tuple[str, List[dict]]]:
    by_event: Dict[str, List[dict]] = defaultdict(list)
    for m in matches:
        ek = m.get("event_key") or str(m.get("key", ""))[:8]
        by_event[ek].append(m)

    def sort_key(ek: str) -> tuple:
        return (start_dates.get(ek) or "", ek)

    return [(ek, by_event[ek]) for ek in sorted(by_event.keys(), key=sort_key)]


def _print_row(label: str, metrics: Dict[str, float]) -> None:
    print(
        "{:<44} {:>8.2f} {:>8.2f} {:>8.2f} {:>8.4f} {:>7.0f}".format(
            label[:44],
            metrics["score_mae"],
            metrics["score_bias"],
            metrics["win_accuracy"],
            metrics["brier"],
            metrics["n_wl"],
        )
    )


def run_method_bakeoff(
    event_list: List[List[dict]],
    year: int,
    k_base: float,
    shrink: float,
    win_scale: float,
) -> Method:
    print("\n{:<20} {:>10} {:>10} {:>12} {:>10} {:>8}".format(
        "method", "MAE", "bias", "win_acc%", "Brier", "n_wl"
    ))
    print("-" * 78)

    results = {}
    for method in METHODS:
        metrics = aggregate_event_metrics(
            event_list,
            year,
            method=method,
            k_base=k_base,
            shrink=shrink,
            win_scale=win_scale,
        )
        results[method] = metrics
        print(
            "{:<20} {:>10.2f} {:>10.2f} {:>12.2f} {:>10.4f} {:>8.0f}".format(
                method,
                metrics["score_mae"],
                metrics["score_bias"],
                metrics["win_accuracy"],
                metrics["brier"],
                metrics["n_wl"],
            )
        )

    best_win = max(r["win_accuracy"] for r in results.values())
    baseline_acc = results.get("baseline_current", {}).get("win_accuracy", best_win)
    candidates = {
        m: r
        for m, r in results.items()
        if r["win_accuracy"] >= min(best_win, baseline_acc) - 2.0
    }
    if not candidates:
        candidates = results
    winner = min(
        candidates.items(),
        key=lambda kv: (abs(kv[1]["score_bias"]), kv[1]["score_mae"]),
    )
    print(
        f"\nRecommended method: {winner[0]}  "
        f"(bias={winner[1]['score_bias']:.2f}, MAE={winner[1]['score_mae']:.2f}, "
        f"win={winner[1]['win_accuracy']:.1f}%)"
    )
    return winner[0]


def run_config_bakeoff(
    ordered: List[Tuple[str, List[dict]]],
    year: int,
    win_scale: float,
) -> None:
    """Grid over prior carry / shrink / k / spike-damp for residual_shrink."""
    configs = []
    # Grid centered on production defaults; includes neighbors for regression checks.
    for carry in (False, True):
        for shrink in (0.05, 0.10, 0.15, 0.25):
            for k_base in (0.35, 0.40, 0.50):
                for spike_damp in (0.5, 1.0):
                    for blend in (1.0,):
                        configs.append(
                            {
                                "carry": carry,
                                "shrink": shrink,
                                "k_base": k_base,
                                "spike_damp": spike_damp,
                                "prior_blend": blend,
                            }
                        )

    header = "{:<44} {:>8} {:>8} {:>8} {:>8} {:>7}".format(
        "config", "MAE", "bias", "|bias|", "win%", "n_wl"
    )
    print("\n=== Config bake-off (residual_shrink), full walk-forward ===")
    print(header)
    print("-" * 90)

    rows = []
    for cfg in configs:
        label = (
            f"carry={int(cfg['carry'])} blend={cfg['prior_blend']:.1f} "
            f"sh={cfg['shrink']:.2f} k={cfg['k_base']:.2f} sp={cfg['spike_damp']:.2f}"
        )
        m = multi_event_walk_forward(
            ordered,
            year,
            method="residual_shrink",
            k_base=cfg["k_base"],
            shrink=cfg["shrink"],
            win_scale=win_scale,
            spike_damp=cfg["spike_damp"],
            carry_prior=cfg["carry"],
            prior_blend=cfg["prior_blend"],
            warmup_frac=0.0,
        )
        row = {**cfg, **m, "label": label}
        rows.append(row)
        print(
            "{:<44} {:>8.2f} {:>8.2f} {:>8.2f} {:>8.2f} {:>7.0f}".format(
                label[:44],
                m["score_mae"],
                m["score_bias"],
                abs(m["score_bias"]),
                m["win_accuracy"],
                m["n_wl"],
            )
        )

    # Also report post-warmup bias for the best few (reduces cold-start noise).
    print("\n=== Same configs, metrics after 25% event warmup ===")
    print(header)
    print("-" * 90)
    warm_rows = []
    # Evaluate a reduced grid first for speed? Full grid is ~144 configs * events - might be slow but OK.
    for cfg in configs:
        label = (
            f"carry={int(cfg['carry'])} blend={cfg['prior_blend']:.1f} "
            f"sh={cfg['shrink']:.2f} k={cfg['k_base']:.2f} sp={cfg['spike_damp']:.2f}"
        )
        m = multi_event_walk_forward(
            ordered,
            year,
            method="residual_shrink",
            k_base=cfg["k_base"],
            shrink=cfg["shrink"],
            win_scale=win_scale,
            spike_damp=cfg["spike_damp"],
            carry_prior=cfg["carry"],
            prior_blend=cfg["prior_blend"],
            warmup_frac=0.25,
        )
        warm_rows.append({**cfg, **m, "label": label})
        print(
            "{:<44} {:>8.2f} {:>8.2f} {:>8.2f} {:>8.2f} {:>7.0f}".format(
                label[:44],
                m["score_mae"],
                m["score_bias"],
                abs(m["score_bias"]),
                m["win_accuracy"],
                m["n_wl"],
            )
        )

    def pick(rows_in: List[dict], min_win: Optional[float] = None) -> dict:
        best_win = max(r["win_accuracy"] for r in rows_in)
        floor = (min_win if min_win is not None else best_win) - 1.5
        cands = [r for r in rows_in if r["win_accuracy"] >= floor]
        return min(cands, key=lambda r: (abs(r["score_bias"]), r["score_mae"], -r["win_accuracy"]))

    # Baseline = current production knobs.
    baseline = next(
        (
            r
            for r in warm_rows
            if (
                r["carry"]
                and r["shrink"] == 0.05
                and r["k_base"] == 0.40
                and r["spike_damp"] == 1.0
                and r["prior_blend"] == 1.0
            )
        ),
        warm_rows[0],
    )
    winner = pick(warm_rows)
    # Prefer carry if it clearly improves |bias| without hurting wins much.
    carry_rows = [r for r in warm_rows if r["carry"]]
    best_carry = pick(carry_rows) if carry_rows else winner

    print("\n--- Summary (post-warmup) ---")
    print(
        f"Current defaults: {baseline['label']}  "
        f"bias={baseline['score_bias']:+.2f} MAE={baseline['score_mae']:.2f} "
        f"win={baseline['win_accuracy']:.1f}%"
    )
    print(
        f"Best overall:     {winner['label']}  "
        f"bias={winner['score_bias']:+.2f} MAE={winner['score_mae']:.2f} "
        f"win={winner['win_accuracy']:.1f}%"
    )
    print(
        f"Best with prior:  {best_carry['label']}  "
        f"bias={best_carry['score_bias']:+.2f} MAE={best_carry['score_mae']:.2f} "
        f"win={best_carry['win_accuracy']:.1f}%"
    )
    print(
        "\nSuggested env:\n"
        f"  ACE_METHOD=residual_shrink\n"
        f"  ACE_SHRINK={winner['shrink']}\n"
        f"  ACE_K_BASE={winner['k_base']}\n"
        f"  ACE_SPIKE_DAMP={winner['spike_damp']}\n"
        f"  ACE_CARRY_PRIOR={1 if winner['carry'] else 0}\n"
        f"  ACE_PRIOR_BLEND={winner['prior_blend']}\n"
        f"  ACE_WIN_PROB_SCALE={win_scale}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="ACE attribution bake-off")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--limit-events", type=int, default=25)
    ap.add_argument("--k-base", type=float, default=0.4)
    ap.add_argument("--shrink", type=float, default=0.05)
    ap.add_argument("--win-scale", type=float, default=0.04, help="Logistic scale for win probs")
    ap.add_argument(
        "--config-bakeoff",
        action="store_true",
        help="Grid search prior/shrink/k/spike-damp for residual_shrink",
    )
    args = ap.parse_args()

    print(f"Fetching TBA matches for {args.year} (limit_events={args.limit_events})...")
    matches, start_dates = _load_matches_tba(args.year, args.limit_events)
    print(f"Total matches: {len(matches)}")

    ordered = _ordered_events(matches, start_dates)
    event_list = [ms for _, ms in ordered]

    if args.config_bakeoff:
        run_config_bakeoff(ordered, args.year, win_scale=args.win_scale)
        return

    winner = run_method_bakeoff(
        event_list, args.year, args.k_base, args.shrink, args.win_scale
    )

    print("\nWin-prob scale bake-off on", winner, ":")
    scale_results = []
    for scale in (0.04, 0.06, 0.08, 0.10, 0.12):
        m = aggregate_event_metrics(
            event_list,
            args.year,
            method=winner,
            k_base=args.k_base,
            shrink=args.shrink,
            win_scale=scale,
        )
        scale_results.append((scale, m))
        print(
            "  scale={:.2f}  win_acc={:.2f}%  Brier={:.4f}".format(
                scale, m["win_accuracy"], m["brier"]
            )
        )
    best_scale = min(scale_results, key=lambda t: (t[1]["brier"], -t[1]["win_accuracy"]))
    print(
        f"\nSuggested ACE_WIN_PROB_SCALE={best_scale[0]:.2f}  "
        f"(Brier={best_scale[1]['brier']:.4f}, win={best_scale[1]['win_accuracy']:.1f}%)"
    )


if __name__ == "__main__":
    main()
