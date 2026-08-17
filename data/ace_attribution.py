"""ACE attribution math: residual / equal-split observations and event simulation.

Production and eval both use ``simulate_event`` so research and live scores match.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
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
    # Previous-event confidence; used for pre-match ACE until this event has a played match.
    carried_confidence: Optional[float] = None

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
    partner_cap: float = 0.0,
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

    # Cap each partner's credited RAW so overrated partners cannot zero a
    # stacked elite. partner_cap <= 0 disables. Cap = alpha * (S/n).
    if partner_cap and partner_cap > 0:
        equal = alliance_total / n
        ceil = partner_cap * equal
        partners = [min(float(p), ceil) for p in partners]

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
    k_up: float = 1.0,
    k_down: float = 1.0,
) -> Tuple[float, bool]:
    # First observation: take obs as-is so residual equal-share inits still sum to S.
    if not initialized:
        return max(0.0, float(obs)), True

    early_weight = max(early_weight_floor, min(1.0, match_count / early_match_target))
    # comp_level intentionally ignored — no match-importance scaling.
    K = k_base * early_weight
    # Asymmetric learning: faster catch-up on positive residuals (underpredicted
    # elites), optional faster/slower decay on negative residuals.
    if obs > current:
        K *= max(0.0, float(k_up))
    elif obs < current:
        K *= max(0.0, float(k_down))
    # spike_damp=1.0 disables; <1 slows large positive jumps.
    if spike_damp < 1.0 and current > 10 and obs > current * spike_ratio:
        K *= spike_damp
    updated = current + K * (obs - current)
    return max(0.0, float(updated)), True


def seed_states_from_priors(
    states: Dict[str, TeamPhaseState],
    prior_means: Optional[Dict[str, Tuple[float, ...]]],
) -> None:
    """Seed RAW from cross-event priors so the event does not cold-start at 0."""
    if not prior_means:
        return
    for key, phases in prior_means.items():
        if not phases or len(phases) < 3:
            continue
        auto, teleop, endgame = float(phases[0]), float(phases[1]), float(phases[2])
        if auto == 0 and teleop == 0 and endgame == 0:
            continue
        st = states.get(key) or TeamPhaseState()
        if st.initialized:
            continue
        st.auto = max(0.0, auto)
        st.teleop = max(0.0, teleop)
        st.endgame = max(0.0, endgame)
        if len(phases) > 3 and phases[3] is not None:
            st.carried_confidence = max(0.0, min(1.0, float(phases[3])))
        st.initialized = True
        states[key] = st


def merge_carry_prior(
    old: Optional[Tuple[float, ...]],
    new: Tuple[float, ...],
    prior_blend: float,
) -> Tuple[float, ...]:
    """Blend cross-event RAW priors; keep optional 4th-slot confidence."""
    if not old or prior_blend >= 1.0:
        return new
    b = prior_blend
    blended = (
        (1.0 - b) * old[0] + b * new[0],
        (1.0 - b) * old[1] + b * new[1],
        (1.0 - b) * old[2] + b * new[2],
    )
    new_c = float(new[3]) if len(new) > 3 and new[3] is not None else None
    old_c = float(old[3]) if len(old) > 3 and old[3] is not None else None
    if new_c is None and old_c is None:
        return blended
    if old_c is None:
        conf = new_c
    elif new_c is None:
        conf = old_c
    else:
        conf = (1.0 - b) * old_c + b * new_c
    return (*blended, conf)


def apply_match_updates(
    states: Dict[str, TeamPhaseState],
    match: dict,
    year: int,
    method: Method,
    k_base: float = 0.4,
    shrink: float = 0.05,
    prior_means: Optional[Dict[str, Tuple[float, ...]]] = None,
    spike_damp: float = 0.5,
    k_up: float = 1.0,
    k_down: float = 1.0,
    partner_cap: float = 0.0,
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
                    method,
                    auto_s,
                    snapshots[key][0],
                    partner_auto,
                    n,
                    prior[0],
                    shrink,
                    partner_cap=partner_cap,
                )
                obs_teleop = observation_for_phase(
                    method,
                    teleop_s,
                    snapshots[key][1],
                    partner_teleop,
                    n,
                    prior[1],
                    shrink,
                    partner_cap=partner_cap,
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
                        method,
                        end_s,
                        snapshots[key][2],
                        partner_end,
                        n,
                        prior[2],
                        shrink,
                        partner_cap=partner_cap,
                    )

            was_init = st.initialized
            st.auto, _ = ema_update(
                st.auto,
                obs_auto,
                st.match_count,
                comp,
                was_init,
                k_base=k_base,
                spike_damp=spike_damp,
                k_up=k_up,
                k_down=k_down,
            )
            st.teleop, _ = ema_update(
                st.teleop,
                obs_teleop,
                st.match_count,
                comp,
                was_init,
                k_base=k_base,
                spike_damp=spike_damp,
                k_up=k_up,
                k_down=k_down,
            )
            st.endgame, _ = ema_update(
                st.endgame,
                obs_end,
                st.match_count,
                comp,
                was_init,
                k_base=k_base,
                spike_damp=spike_damp,
                k_up=k_up,
                k_down=k_down,
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


def _match_sort_key(match: dict) -> Tuple:
    """Deterministic match order: time, then comp/set/number/key."""
    return (
        match.get("time") or 0,
        match.get("comp_level") or "qm",
        match.get("match_number") or 0,
        match.get("set_number") or 0,
        match.get("key") or "",
    )


def _copy_team_phase_state(st: TeamPhaseState) -> TeamPhaseState:
    return replace(
        st,
        contributions=list(st.contributions),
        dominance_scores=list(st.dominance_scores),
    )


def simulate_event(
    matches: List[dict],
    year: int,
    method: Method = "residual_shrink",
    k_base: float = 0.4,
    shrink: float = 0.05,
    prior_means: Optional[Dict[str, Tuple[float, ...]]] = None,
    spike_damp: float = 0.5,
    seed_priors: bool = True,
    k_up: float = 1.0,
    k_down: float = 1.0,
    partner_cap: float = 0.0,
) -> Dict[str, TeamPhaseState]:
    """Match-centric walk: update all alliance members from each played match."""
    states: Dict[str, TeamPhaseState] = {}
    if seed_priors:
        seed_states_from_priors(states, prior_means)
    ordered = sorted(matches, key=_match_sort_key)
    for match in ordered:
        if not _played(match):
            continue
        apply_match_updates(
            states,
            match,
            year,
            method,
            k_base,
            shrink,
            prior_means,
            spike_damp=spike_damp,
            k_up=k_up,
            k_down=k_down,
            partner_cap=partner_cap,
        )
    return states


def simulate_event_pre_match_snapshots(
    matches: List[dict],
    year: int,
    method: Method = "residual_shrink",
    k_base: float = 0.4,
    shrink: float = 0.05,
    prior_means: Optional[Dict[str, Tuple[float, ...]]] = None,
    spike_damp: float = 0.5,
    seed_priors: bool = True,
    k_up: float = 1.0,
    k_down: float = 1.0,
    partner_cap: float = 0.0,
) -> Tuple[Dict[str, TeamPhaseState], Dict[str, Dict[str, TeamPhaseState]]]:
    """Walk an event and capture each team's state before every match.

    Returns final states and ``match_key -> team_key -> pre-match TeamPhaseState``.
    Unplayed matches receive snapshots reflecting all prior played matches only.
    """
    states: Dict[str, TeamPhaseState] = {}
    snapshots: Dict[str, Dict[str, TeamPhaseState]] = {}
    if seed_priors:
        seed_states_from_priors(states, prior_means)

    ordered = sorted(matches, key=_match_sort_key)
    for match in ordered:
        match_key = match.get("key") or ""
        if not match_key:
            continue

        team_snapshots: Dict[str, TeamPhaseState] = {}
        for color in ("red", "blue"):
            for key in match["alliances"][color].get("team_keys") or []:
                st = states.get(key) or TeamPhaseState()
                team_snapshots[key] = _copy_team_phase_state(st)
        snapshots[match_key] = team_snapshots

        if _played(match):
            apply_match_updates(
                states,
                match,
                year,
                method,
                k_base,
                shrink,
                prior_means,
                spike_damp=spike_damp,
                k_up=k_up,
                k_down=k_down,
                partner_cap=partner_cap,
            )

    return states, snapshots
