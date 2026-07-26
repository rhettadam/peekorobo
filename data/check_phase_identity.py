#!/usr/bin/env python3
"""Phase-identity audit: auto+teleop+endgame should match alliance score.

Usage (from data/):

    python check_phase_identity.py --years 2015-2026 --events-per-year 3
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase_totals import phase_totals


def _load_events(year: int, limit: int) -> List[Tuple[str, List[dict]]]:
    import run as pipeline

    events = pipeline.tba_get(f"events/{year}") or []

    def prio(e: dict) -> tuple:
        et = e.get("event_type") if e.get("event_type") is not None else 99
        return (0 if et in (0, 1, 2, 3, 4, 5, 6) else 1, e.get("start_date") or "", e.get("key") or "")

    events = sorted(events, key=prio)
    out: List[Tuple[str, List[dict]]] = []
    for ev in events:
        if len(out) >= limit:
            break
        ek = ev.get("key")
        if not ek:
            continue
        matches = pipeline.tba_get(f"event/{ek}/matches") or []
        played = [m for m in matches if m.get("score_breakdown")]
        if len(played) < 8:
            continue
        out.append((ek, played))
        print(f"  {ek}: {len(played)} matches with breakdown")
    return out


def identity_for_matches(year: int, matches: List[dict]) -> Dict[str, float]:
    err = 0.0
    abs_err = 0.0
    n = 0
    for match in matches:
        bd_root = match.get("score_breakdown")
        if not isinstance(bd_root, dict):
            continue
        for color in ("red", "blue"):
            b = bd_root.get(color)
            if not isinstance(b, dict):
                continue
            keys = list(match["alliances"][color].get("team_keys") or [])
            n_teams = max(1, len(keys))
            auto, tele, _, per = phase_totals(year, b, n_teams, 1)
            if per:
                ends = sum(phase_totals(year, b, n_teams, i)[2] for i in range(1, n_teams + 1))
            else:
                ends = phase_totals(year, b, n_teams, 1)[2]
            pred = auto + tele + ends
            actual = float(match["alliances"][color]["score"] or 0)
            delta = pred - actual
            err += delta
            abs_err += abs(delta)
            n += 1
    return {
        "bias": err / n if n else float("nan"),
        "mae": abs_err / n if n else float("nan"),
        "n": float(n),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2015-2026", help="e.g. 2015-2026 or 2024,2025")
    ap.add_argument("--events-per-year", type=int, default=3)
    args = ap.parse_args()

    years: List[int] = []
    for part in args.years.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(part))

    print(f"Phase identity audit years={years} events/year={args.events_per_year}")
    print(f"{'year':<6} {'bias':>8} {'mae':>8} {'n':>6}  status")
    print("-" * 44)
    bad = []
    for y in years:
        print(f"Fetching {y}...")
        try:
            bundles = _load_events(y, args.events_per_year)
        except Exception as e:
            print(f"{y:<6} FETCH FAIL {e}")
            bad.append(y)
            continue
        if not bundles:
            print(f"{y:<6} NO DATA")
            bad.append(y)
            continue
        matches = [m for _, ms in bundles for m in ms]
        m = identity_for_matches(y, matches)
        # Allow tiny float noise; flag |bias| > 1.0 or mae > 3
        ok = abs(m["bias"]) <= 1.0 and m["mae"] <= 3.0
        status = "OK" if ok else "FAIL"
        if not ok:
            bad.append(y)
        print(f"{y:<6} {m['bias']:+8.2f} {m['mae']:8.2f} {int(m['n']):6d}  {status}")

    if bad:
        print(f"\nYears needing extractor fixes: {bad}")
        sys.exit(1)
    print("\nAll years pass phase identity.")
    sys.exit(0)


if __name__ == "__main__":
    main()
