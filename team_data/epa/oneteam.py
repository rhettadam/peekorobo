import statistics
import json
import requests
import os
import math
from dotenv import load_dotenv
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import sqlite3
import random

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS", "demo_key").split(',')

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    raise Exception(f"Failed to fetch {endpoint}: {r.status_code}")

def load_veteran_teams():
    try:
        conn = sqlite3.connect("epa_teams.sqlite")
        cursor = conn.cursor()
        cursor.execute("SELECT team_number FROM epa_history WHERE year = 2024")
        rows = cursor.fetchall()
        conn.close()
        return {f"frc{row[0]}" for row in rows if isinstance(row[0], int)}
    except Exception as e:
        print(f"Failed to load veteran teams: {e}")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    def score_per_breakdown(b):
        reef = b.get("autoReef", {})
        trough = reef.get("trough", 0)
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        coral_score = trough * 3 + bot * 4 + mid * 6 + top * 7
        mobility = b.get("autoMobilityPoints", 0) / team_count
        return mobility + coral_score
    scores = sorted(score_per_breakdown(b) for b in breakdowns)
    if len(scores) >= 4:
        scores = scores[:int(len(scores) * 0.75)]
    return round(min(statistics.mean(scores) if scores else 0, 33), 2)

# This is the exact same function logic you provided.
from types import SimpleNamespace
def calculate_for_one_team(team_key, year):
    veteran_teams = load_veteran_teams()
    matches = tba_get(f"team/{team_key}/matches/{year}")
    if not matches:
        print("No matches found.")
        return

    result = calculate_epa_components(matches, team_key, year, veteran_teams=veteran_teams)
    print(f"\nResults for {team_key} ({year}):\n")
    for k, v in result.items():
        print(f"{k.capitalize().replace('_', ' ')}: {v}")

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):

    importance = {"qm": 1.0, "qf": 1.1, "sf": 1.2, "f": 1.2}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    total_score = wins = losses = 0
    auto_breakdowns = []
    dominance_scores = []
    carry_scores = []

    for match in matches:

        event_key = match.get("event_key", "")
        division_keys = {
            "2025hop", "2025gal", "2025new", "2025arc",
            "2025dal", "2025cur", "2025mil", "2025joh"
        }

        is_division = event_key in division_keys
        is_einstein = event_key == "2025cmptx"

        if is_einstein:
            world_champ_penalty = 0.85  # Optional bonus for Einstein
        elif is_division:
            world_champ_penalty = 0.85  # Slight penalty (less than 0.7)
        else:
            world_champ_penalty = 1.0  # Regular events
        
        # Skip matches where the team did not play
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent_alliance = "blue" if alliance == "red" else "red"

        team_keys = match["alliances"][alliance].get("team_keys", [])
        team_count = len(team_keys)
        index = team_keys.index(team_key) + 1
        
        alliance_score = match["alliances"][alliance]["score"]
        total_score += alliance_score

        # Count wins and losses based on the winning alliance
        winning_alliance = match.get("winning_alliance", "")
        if winning_alliance == alliance:
            wins += 1
        elif winning_alliance and winning_alliance != alliance:
            losses += 1

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})
        auto_breakdowns.append(breakdown)

        # Auto EPA from consistent pattern analysis
        actual_auto = estimate_consistent_auto(auto_breakdowns, team_count)

        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)

        reef = breakdown.get("teleopReef", {})
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        trough = reef.get("trough", 0)
        net = breakdown.get("netAlgaeCount", 0)
        processor = breakdown.get("wallAlgaeCount", 0)

        estimated_teleop = (bot * 3 + mid * 4 + top * 5 + trough * 2 + net * 4 + processor * 2.5)
        actual_teleop = estimated_teleop / team_count
        actual_overall = actual_auto + actual_teleop + actual_endgame
        opponent_score = match["alliances"][opponent_alliance]["score"] / team_count

        margin = actual_overall - opponent_score
        scaled_margin = margin / (opponent_score + 1e-6)
        norm_margin = (scaled_margin + 1) / 1.3  # maps [-1, 1] → [0, 1]
        dominance_scores.append(min(1.0, max(0.0, norm_margin)))

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        total_matches = sum(1 for m in matches if team_key in m["alliances"]["red"]["team_keys"] or team_key in m["alliances"]["blue"]["team_keys"])

        decay = world_champ_penalty * (match_count / len(matches)) ** 2

        others = [k for k in team_keys if k != team_key]
        if others:
            match_teammate_epa = (alliance_score - actual_overall) / (team_count - 1)
            carry_ratio = actual_overall / (match_teammate_epa + 1e-6)

            # Sharper sigmoid: higher slope, lower midpoint
            match_carry_score = 1 / (1 + math.exp(-4.0 * (carry_ratio - 0.5)))  # Midpoint at 0.9, steeper curve
            carry_scores.append(match_carry_score)

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            endgame_epa = actual_endgame
            teleop_epa = actual_teleop
            continue


        if match_count <= 6:
            K = 0.5
        elif match_count <= 12:
            K = 0.5 + ((match_count - 6) * ((1.0 - 0.5) / 6))
        else:
            K = 0.3

        K *= match_importance * world_champ_penalty

        delta_auto = decay * K * (actual_auto - auto_epa)
        delta_teleop = decay * K * (actual_teleop - teleop_epa)
        delta_endgame = decay * K * (actual_endgame - endgame_epa)

        auto_epa += delta_auto
        teleop_epa += delta_teleop
        endgame_epa += delta_endgame
        overall_epa = auto_epa + teleop_epa + endgame_epa

        contributions.append(actual_overall)

    if len(contributions) >= 2:
        peak = max(contributions)
        stdev = statistics.stdev(contributions)
        consistency = max(0.0, 1.0 - stdev / (peak + 1e-6))
    else:
        consistency = 1.0
        
    is_veteran = veteran_teams and team_key in veteran_teams
    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry = min(1.25, statistics.mean(carry_scores)) if carry_scores else 1.0
    dominance = min(1., statistics.mean(dominance_scores))
    win_rate = wins / match_count if match_count else 0
    
    expected_margin = dominance
    actual_margin = (wins - losses) / match_count if match_count else 0
    
    record_alignment_score = 1.0 if actual_margin >= dominance else 1 - (dominance - actual_margin) / 0.8
    record_alignment_score = max(0.0, record_alignment_score)

    average_match_score = total_score / match_count if match_count else 0

    raw_confidence = (
        0.25 * consistency +
        0.1 * (1.0 if is_veteran else 0.6) +
        0.25  * carry +
        0.25  * dominance + 
        0.15 * record_alignment_score
    )
    confidence = min(1.0, raw_confidence)

    actual_epa = overall_epa * confidence

    print(f"\n===== DEBUG for {team_key} =====")
    print("===== EPA Component Breakdown =====")
    print(f"Auto EPA:     {round(auto_epa, 2)}")
    print(f"Teleop EPA:   {round(teleop_epa, 2)}")
    print(f"Endgame EPA:  {round(endgame_epa, 2)}")
    print(f"→ Overall EPA (unweighted): {round(overall_epa, 2)}")
    print("\n===== Confidence Breakdown =====")
    print(f"→ Consistency:     {round(consistency, 3)} × 0.25 = {round(0.25 * consistency, 4)}")
    print(f"→ Veteran Boost:   {'1.0' if is_veteran else '0.6'} × 0.1 = {round(0.1 * (1.0 if is_veteran else 0.6), 4)}")
    print(f"→ Carry Score:     {round(carry, 3)} × 0.25 = {round(0.25 * carry, 4)}")
    print(f"→ Dominance:       {round(dominance, 3)} × 0.25 = {round(0.25 * dominance, 4)}")
    print(f"→ Record Align:    {round(record_alignment_score, 3)} × 0.15 = {round(0.15 * record_alignment_score, 4)}")
    print(f"→ Confidence Total: {round(raw_confidence, 4)} → Capped: {round(confidence, 3)}")
    print("\n===== Final EPA Calculation =====")
    print(f"{round(overall_epa, 2)} (overall) × {round(confidence, 3)} (confidence) = {round(actual_epa, 2)}")


    return {
        "overall": round(overall_epa, 2),
        "auto": round(auto_epa, 2),
        "teleop": round(teleop_epa, 2),
        "endgame": round(endgame_epa, 2),
        "consistency": round(consistency, 2),
        "confidence": round(confidence, 2),
        "actual_epa": round(actual_epa, 2),
        "average_match_score": round(average_match_score, 2),
        "wins": wins,
        "losses": losses
    }

# === EXECUTION ===
if __name__ == "__main__":
    team_key = "frc4020"  # CHANGE THIS to whatever team you want to test
    year = 2025           # CHANGE THIS too if needed
    calculate_for_one_team(team_key, year)
