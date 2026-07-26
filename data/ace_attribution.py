"""ACE attribution math: residual / equal-split observations and event simulation.

Production and eval both use ``simulate_event`` so research and live scores match.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from phase_totals import phase_totals

Method = Literal["residual", "equal_split", "residual_shrink", "baseline_current"]


@dataclass
class TeamPhaseState:
    auto: float = 0.0
    teleop: float = 0.0
    endgame: float = 0.0
    match_count: int = 0
    contributions: List[float] = field(default_factory=list)
    dominance_scores: List[float] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    ties: int = 0
    initialized: bool = False

    @property
    def raw(self) -> float:
        return self.auto + self.teleop + self.endgame


def _parse_breakdown(match: dict) -> Optional[dict]:
    breakdown = match.get("score_breakdown")
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(breakdown, dict):
        return None
    return breakdown


def _played(match: dict) -> bool:
    red = match["alliances"]["red"]["score"]
    blue = match["alliances"]["blue"]["score"]
    winning = match.get("winning_alliance")
    if red == 0 and blue == 0 and winning not in ("red", "blue"):
        return False
    return True


def _record_wl(state: TeamPhaseState, alliance: str, red: int, blue: int, year: int) -> None:
    if year != 2015 and (red == 0 or blue == 0):
        state.ties += 1
        return
    if alliance == "red":
        if red > blue:
            state.wins += 1
        elif red < blue:
            state.losses += 1
        else:
            state.ties += 1
    else:
        if blue > red:
            state.wins += 1
        elif blue < red:
            state.losses += 1
        else:
            state.ties += 1


def observation_for_phase(
    method: Method,
    alliance_total: float,
    self_r: float,
    partner_rs: List[float],
    team_count: int,
    prior_mean: float,
    shrink: float,
) -> float:
    n = max(1, team_count)
    if method == "equal_split":
        return alliance_total / n

    # residual / residual_shrink
    if len(partner_rs) >= n - 1:
        partners = partner_rs[: n - 1]
    else:
        # Cold partners: assume equal share of the remainder
        partners = partner_rs + [alliance_total / n] * max(0, (n - 1) - len(partner_rs))

    obs = alliance_total - sum(partners)
    if method == "residual_shrink":
        # Pull toward equal-share prior (not zero). Damps carry-inflation when
        # partners are underestimated and boosts suppressed stacked elites.
        equal = alliance_total / n
        target = prior_mean if prior_mean else equal
        obs = (1.0 - shrink) * obs + shrink * target
    # Contribution cannot be negative: if partners' RAW already exceeds S,
    # credit this robot 0 for the phase rather than a damaging negative.
    return max(0.0, float(obs))


def ema_update(
    current: float,
    obs: float,
    match_count: int,
    comp_level: str,
    initialized: bool,
    k_base: float = 0.4,
    early_match_target: int = 5,
    early_weight_floor: float = 0.75,
    spike_damp: float = 0.5,
    spike_ratio: float = 1.4,
) -> Tuple[float, bool]:
    # First observation: take obs as-is so residual equal-share inits still sum to S.
    if not initialized:
        return max(0.0, float(obs)), True

    early_weight = max(early_weight_floor, min(1.0, match_count / early_match_target))
    # comp_level intentionally ignored — no match-importance scaling.
    K = k_base * early_weight
    # spike_damp=1.0 disables; <1 slows large positive jumps.
    if spike_damp < 1.0 and current > 10 and obs > current * spike_ratio:
        K *= spike_damp
    updated = current + K * (obs - current)
    return max(0.0, float(updated)), True


def seed_states_from_priors(
    states: Dict[str, TeamPhaseState],
    prior_means: Optional[Dict[str, Tuple[float, float, float]]],
) -> None:
    """Seed RAW from cross-event priors so the event does not cold-start at 0."""
    if not prior_means:
        return
    for key, phases in prior_means.items():
        if not phases:
            continue
        auto, teleop, endgame = phases
        if auto == 0 and teleop == 0 and endgame == 0:
            continue
        st = states.get(key) or TeamPhaseState()
        if st.initialized:
            continue
        st.auto = max(0.0, float(auto))
        st.teleop = max(0.0, float(teleop))
        st.endgame = max(0.0, float(endgame))
        st.initialized = True
        states[key] = st


def apply_match_updates(
    states: Dict[str, TeamPhaseState],
    match: dict,
    year: int,
    method: Method,
    k_base: float = 0.4,
    shrink: float = 0.02,
    prior_means: Optional[Dict[str, Tuple[float, float, float]]] = None,
    spike_damp: float = 0.5,
) -> None:
    """Update states in-place for one played match (all six robots)."""
    prior_means = prior_means or {}
    breakdown_root = _parse_breakdown(match)
    red_score = match["alliances"]["red"]["score"]
    blue_score = match["alliances"]["blue"]["score"]
    comp = match.get("comp_level", "qm")

    def ensure(key: str) -> TeamPhaseState:
        if key not in states:
            states[key] = TeamPhaseState()
        return states[key]

    for color in ("red", "blue"):
        team_keys = list(match["alliances"][color].get("team_keys") or [])
        if not team_keys:
            continue
        n = len(team_keys)
        alliance_bd: dict = {}
        if breakdown_root:
            raw_bd = breakdown_root.get(color) or {}
            if isinstance(raw_bd, dict):
                alliance_bd = raw_bd

        snapshots = {
            k: (
                ensure(k).auto,
                ensure(k).teleop,
                ensure(k).endgame,
                ensure(k).initialized,
            )
            for k in team_keys
        }
        opp = "blue" if color == "red" else "red"
        opp_score = match["alliances"][opp]["score"]

        for idx, key in enumerate(team_keys):
            robot_index = idx + 1
            st = ensure(key)
            st.match_count += 1
            _record_wl(st, color, red_score, blue_score, year)

            if (not alliance_bd and year >= 2015) or year <= 2014:
                auto_s = teleop_s = 0.0
                end_s = float(match["alliances"][color]["score"] or 0)
                end_per_robot = False
            else:
                auto_s, teleop_s, end_s, end_per_robot = phase_totals(
                    year, alliance_bd, n, robot_index
                )

            prior = prior_means.get(key, (0.0, 0.0, 0.0))
            partner_auto = [
                snapshots[k][0] if snapshots[k][3] else auto_s / n
                for k in team_keys
                if k != key
            ]
            partner_teleop = [
                snapshots[k][1] if snapshots[k][3] else teleop_s / n
                for k in team_keys
                if k != key
            ]

            if method == "baseline_current":
                scale = 1 / (1 + math.log(n)) if n > 1 else 1.0
                obs_auto = auto_s * scale
                obs_teleop = teleop_s * scale
                obs_end = end_s if end_per_robot else end_s * scale
            else:
                obs_auto = observation_for_phase(
                    method, auto_s, snapshots[key][0], partner_auto, n, prior[0], shrink
                )
                obs_teleop = observation_for_phase(
                    method, teleop_s, snapshots[key][1], partner_teleop, n, prior[1], shrink
                )
                if end_per_robot:
                    obs_end = end_s
                else:
                    partner_end = [
                        snapshots[k][2] if snapshots[k][3] else end_s / n
                        for k in team_keys
                        if k != key
                    ]
                    obs_end = observation_for_phase(
                        method, end_s, snapshots[key][2], partner_end, n, prior[2], shrink
                    )

            was_init = st.initialized
            st.auto, _ = ema_update(
                st.auto, obs_auto, st.match_count, comp, was_init, k_base=k_base, spike_damp=spike_damp
            )
            st.teleop, _ = ema_update(
                st.teleop, obs_teleop, st.match_count, comp, was_init, k_base=k_base, spike_damp=spike_damp
            )
            st.endgame, _ = ema_update(
                st.endgame, obs_end, st.match_count, comp, was_init, k_base=k_base, spike_damp=spike_damp
            )
            st.initialized = True

            actual_overall = obs_auto + obs_teleop + obs_end
            # Consistency tracks the smoothed RAW estimate (post-EMA), not the raw
            # residual observation — residual obs are too noisy and were punishing
            # carry bots / ACE leaders with boom-bust match credits.
            st.contributions.append(st.raw)

            # Dominance: this match's attributed points vs fair share of alliance score.
            own_score = float(match["alliances"][color]["score"] or 0)
            fair = own_score / n if n else 1.0
            ratio = actual_overall / (fair + 1e-6)
            # fair share (1.0) → ~0.80; strong carry (1.4+) → 1.0; half share → ~0.55
            norm_margin = max(0.0, min(1.0, 0.25 + 0.55 * ratio))
            st.dominance_scores.append(norm_margin)


def simulate_event(
    matches: List[dict],
    year: int,
    method: Method = "residual_shrink",
    k_base: float = 0.4,
    shrink: float = 0.02,
    prior_means: Optional[Dict[str, Tuple[float, float, float]]] = None,
    spike_damp: float = 0.5,
    seed_priors: bool = True,
) -> Dict[str, TeamPhaseState]:
    """Match-centric walk: update all alliance members from each played match."""
    states: Dict[str, TeamPhaseState] = {}
    if seed_priors:
        seed_states_from_priors(states, prior_means)
    ordered = sorted(matches, key=lambda m: m.get("time") or 0)
    for match in ordered:
        if not _played(match):
            continue
        apply_match_updates(
            states, match, year, method, k_base, shrink, prior_means, spike_damp=spike_damp
        )
    return states


def predict_alliance_score(states: Dict[str, TeamPhaseState], team_keys: List[str]) -> float:
    total = 0.0
    for k in team_keys:
        st = states.get(k)
        if st and st.initialized:
            total += st.raw
        else:
            known = [states[x].raw for x in team_keys if x in states and states[x].initialized]
            total += (sum(known) / len(known)) if known else 0.0
    return total


def walk_forward_metrics(
    matches: List[dict],
    year: int,
    method: Method,
    k_base: float = 0.4,
    shrink: float = 0.02,
    win_scale: float = 0.06,
    spike_damp: float = 0.5,
    prior_means: Optional[Dict[str, Tuple[float, float, float]]] = None,
    seed_priors: bool = True,
    warmup_frac: float = 0.0,
) -> Dict[str, float]:
    """Single pass: score MAE/bias from RAW before each match, then update."""
    states: Dict[str, TeamPhaseState] = {}
    if seed_priors:
        seed_states_from_priors(states, prior_means)
    abs_err = 0.0
    bias_sum = 0.0
    n_score = 0
    correct = 0
    total_wl = 0
    brier_sum = 0.0
    n_brier = 0

    ordered = sorted(matches, key=lambda m: m.get("time") or 0)
    played = [m for m in ordered if _played(m)]
    warmup_cut = int(len(played) * max(0.0, min(1.0, warmup_frac)))
    for i, match in enumerate(played):
        score_now = i >= warmup_cut

        if score_now:
            for color in ("red", "blue"):
                keys = list(match["alliances"][color].get("team_keys") or [])
                actual = float(match["alliances"][color]["score"] or 0)
                pred = predict_alliance_score(states, keys)
                abs_err += abs(pred - actual)
                bias_sum += pred - actual
                n_score += 1

            red_keys = list(match["alliances"]["red"].get("team_keys") or [])
            blue_keys = list(match["alliances"]["blue"].get("team_keys") or [])
            red_pred = predict_alliance_score(states, red_keys)
            blue_pred = predict_alliance_score(states, blue_keys)
            diff = red_pred - blue_pred
            p_red = 1.0 / (1.0 + math.exp(-win_scale * diff))
            p_red = min(0.98, max(0.02, p_red))
            red_s = match["alliances"]["red"]["score"]
            blue_s = match["alliances"]["blue"]["score"]
            if red_s != blue_s:
                actual_red_win = 1.0 if red_s > blue_s else 0.0
                brier_sum += (p_red - actual_red_win) ** 2
                n_brier += 1
                if (p_red >= 0.5) == (red_s > blue_s):
                    correct += 1
                total_wl += 1

        apply_match_updates(
            states, match, year, method, k_base, shrink, prior_means, spike_damp=spike_damp
        )

    return {
        "score_mae": abs_err / n_score if n_score else float("nan"),
        "score_bias": bias_sum / n_score if n_score else float("nan"),
        "win_accuracy": (correct / total_wl * 100.0) if total_wl else float("nan"),
        "brier": brier_sum / n_brier if n_brier else float("nan"),
        "n_score_obs": float(n_score),
        "n_wl": float(total_wl),
        "n_brier": float(n_brier),
        "final_states": states,  # type: ignore[dict-item]
    }


def multi_event_walk_forward(
    events: List[Tuple[str, List[dict]]],
    year: int,
    method: Method,
    k_base: float = 0.4,
    shrink: float = 0.02,
    win_scale: float = 0.06,
    spike_damp: float = 0.5,
    carry_prior: bool = False,
    prior_blend: float = 0.5,
    warmup_frac: float = 0.0,
) -> Dict[str, float]:
    """Walk events in order; optionally carry RAW priors between events.

    prior_blend: when updating the carried prior after an event,
    ``prior = (1 - prior_blend) * old_prior + prior_blend * event_final``.
    ``prior_blend=1`` replaces with the event final each time.
    """
    priors: Dict[str, Tuple[float, float, float]] = {}
    abs_err = bias_sum = 0.0
    n_score = 0
    correct = total_wl = 0
    brier_sum = 0.0
    n_brier = 0

    for _ek, matches in events:
        m = walk_forward_metrics(
            matches,
            year,
            method=method,
            k_base=k_base,
            shrink=shrink,
            win_scale=win_scale,
            spike_damp=spike_damp,
            prior_means=priors if carry_prior else None,
            seed_priors=carry_prior,
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
        if nb and m["brier"] == m["brier"]:
            brier_sum += m["brier"] * nb
            n_brier += nb

        if carry_prior:
            finals: Dict[str, TeamPhaseState] = m.get("final_states") or {}  # type: ignore[assignment]
            for key, st in finals.items():
                if not st.initialized:
                    continue
                new = (st.auto, st.teleop, st.endgame)
                old = priors.get(key)
                if not old or prior_blend >= 1.0:
                    priors[key] = new
                else:
                    b = prior_blend
                    priors[key] = (
                        (1.0 - b) * old[0] + b * new[0],
                        (1.0 - b) * old[1] + b * new[1],
                        (1.0 - b) * old[2] + b * new[2],
                    )

    return {
        "score_mae": abs_err / n_score if n_score else float("nan"),
        "score_bias": bias_sum / n_score if n_score else float("nan"),
        "win_accuracy": (correct / total_wl * 100.0) if total_wl else float("nan"),
        "brier": brier_sum / n_brier if n_brier else float("nan"),
        "n_score_obs": float(n_score),
        "n_wl": float(total_wl),
        "n_brier": float(n_brier),
    }
