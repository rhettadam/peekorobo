import statistics
import json
import requests
import os
import math
from dotenv import load_dotenv
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS", "").split(",")

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = API_KEYS[0] if API_KEYS else ""
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    raise Exception(f"Failed to fetch {endpoint}: {r.status_code}")

def estimate_consistent_auto(breakdowns, team_count):
    def score(b):
        reef = b.get("autoReef", {})
        return (
            reef.get("trough", 0) * 3 +
            reef.get("tba_botRowCount", 0) * 4 +
            reef.get("tba_midRowCount", 0) * 6 +
            reef.get("tba_topRowCount", 0) * 7 +
            b.get("autoMobilityPoints", 0) / team_count
        )
    scores = sorted(score(b) for b in breakdowns)
    if len(scores) >= 4:
        scores = scores[:int(len(scores) * 0.75)]
    return round(min(statistics.mean(scores) if scores else 0, 33), 2)

def calculate_epa_components(matches, team_key):
    importance = {"qm": 1.4, "qf": 1.3, "sf": 1.2, "f": 1.1}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    auto_epa = teleop_epa = endgame_epa = overall_epa = None
    auto_breakdowns = []
    contributions = []
    dominance_scores = []
    carry_scores = []
    wins = losses = total_score = 0

    for match in matches:

        event_key = match.get("event_key", "")
        is_worlds = event_key in {
            "2025hop", "2025gal", "2025new", "2025arc",
            "2025dal", "2025cur", "2025mil", "2025joh"
        }

        # ↓ Optional: apply multiplier to importance or decay
        world_champ_penalty = 0.7 if is_worlds else 1.0  # Downweight champs matches
        print(f"Match: {match.get('key', 'unknown')} | Event: {event_key} | World Champ Penalty: {world_champ_penalty}")
        
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent = "blue" if alliance == "red" else "red"
        team_keys = match["alliances"][alliance]["team_keys"]
        team_count = len(team_keys)
        index = team_keys.index(team_key) + 1
        alliance_score = match["alliances"][alliance]["score"]
        total_score += alliance_score

        if match.get("winning_alliance") == alliance:
            wins += 1
        elif match.get("winning_alliance") == opponent:
            losses += 1

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})
        auto_breakdowns.append(breakdown)
        actual_auto = estimate_consistent_auto(auto_breakdowns, team_count)

        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)

        reef = breakdown.get("teleopReef", {})
        actual_teleop = (
            reef.get("tba_botRowCount", 0) * 3 +
            reef.get("tba_midRowCount", 0) * 4 +
            reef.get("tba_topRowCount", 0) * 5 +
            reef.get("trough", 0) * 2 +
            breakdown.get("netAlgaeCount", 0) * 4 +
            breakdown.get("wallAlgaeCount", 0) * 2.5
        ) / team_count

        actual_overall = actual_auto + actual_teleop + actual_endgame
        opponent_score = match["alliances"][opponent]["score"] / team_count
        margin = actual_overall - opponent_score
        norm_margin = ((actual_overall - opponent_score) / (opponent_score + 1e-6) + 1) / 1.3
        dominance_score = min(1.0, max(0.0, norm_margin))
        dominance_scores.append(dominance_score)

        others = [k for k in team_keys if k != team_key]
        if others:
            teammate_score = (alliance_score - actual_overall) / (team_count - 1)
            ratio = actual_overall / (teammate_score + 1e-6)
            carry_scores.append(1 / (1 + math.exp(-4 * (ratio - 0.5))))

        decay = world_champ_penalty * (match_count / len(matches)) ** 2
        match_weight = importance.get(match.get("comp_level", "qm"), 1.0)

        if overall_epa is None:
            auto_epa, teleop_epa, endgame_epa = actual_auto, actual_teleop, actual_endgame
            overall_epa = auto_epa + teleop_epa + endgame_epa
            continue

        K = 0.5 if match_count <= 6 else (0.5 + (match_count - 6) * ((1.0 - 0.5) / 6)) if match_count <= 12 else 0.3
        K *= match_weight * world_champ_penalty

        auto_epa += decay * K * (actual_auto - auto_epa)
        teleop_epa += decay * K * (actual_teleop - teleop_epa)
        endgame_epa += decay * K * (actual_endgame - endgame_epa)
        overall_epa = auto_epa + teleop_epa + endgame_epa
        contributions.append(actual_overall)

    consistency = 1.0
    if len(contributions) >= 2:
        stdev = statistics.stdev(contributions)
        consistency = max(0.0, 1.0 - stdev / (max(contributions) + 1e-6))

    carry = statistics.mean(carry_scores or [1.0])
    dominance = statistics.mean(dominance_scores or [0.0])
    win_rate = wins / match_count if match_count else 0
    
    expected_margin = dominance
    actual_margin = (wins - losses) / match_count if match_count else 0
    
    # Let dominance override weak records with diminishing punishment
    record_alignment_score = 1 / (1 + math.exp(10 * (actual_margin - dominance)))
    
    # Confidence Components
    consistency_weight = 0.3
    carry_weight = 0.25
    dominance_weight = 0.25
    record_weight = 0.15
    base_weight = 0.05
    
    confidence = (
        consistency_weight * consistency +
        carry_weight * carry +
        dominance_weight * dominance +
        record_weight * record_alignment_score +
        base_weight
    )
    confidence = min(1.0, max(0.0, confidence))

    return {
        "auto": round(auto_epa, 2),
        "teleop": round(teleop_epa, 2),
        "endgame": round(endgame_epa, 2),
        "overall": round(overall_epa, 2),
        "confidence": round(confidence, 2),
        "epa": round(overall_epa * confidence, 2),
        "consistency": round(consistency, 2),
        "wins": wins,
        "losses": losses,
        "match_count": match_count,
        "average_match_score": round(total_score / match_count, 2) if match_count else 0,
    }

if __name__ == "__main__":
    team_key = "frc1912"
    year = 2025
    matches = tba_get(f"team/{team_key}/matches/{year}")
    if matches:
        result = calculate_epa_components(matches, team_key)
        print(f"\nResults for {team_key} ({year}):\n")
        for k, v in result.items():
            print(f"{k.capitalize().replace('_', ' ')}: {v}")
    else:
        print("No matches found.")
