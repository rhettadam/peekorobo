import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv
import sqlite3
import math
import random
from typing import Dict, List, Optional, Union

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

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
        mobility = b.get("autoMobilityPoints", 0)
        
        # Scale entire contribution based on alliance size
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (mobility + coral_score) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in teleop
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)


def estimate_consistent_teleop(breakdowns, team_count):
    def score_per_breakdown(b):
        reef = b.get("teleopReef", {})
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        trough = reef.get("trough", 0)
        net = b.get("netAlgaeCount", 0)
        processor = b.get("wallAlgaeCount", 0)
        estimated_teleop = (bot * 3 + mid * 4 + top * 5 + trough * 2 + net * 4 + processor * 2.5)
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return estimated_teleop * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Smoothed trimming based on match count
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]  # trim from low-end only

    return round(statistics.mean(trimmed_scores), 2)

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):

    importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    total_score = wins = losses = 0
    breakdowns = []
    dominance_scores = []
    endgame_scenarios = {"DeepCage": 0, "ShallowCage": 0, "Parked": 0, "None": 0}
    total_l4 = total_l3 = total_l2 = total_l1 = total_net = total_processor = 0

    for match in matches:

        event_key = match.get("event_key", "")
        division_keys = {
            "2025hop", "2025gal", "2025new", "2025arc",
            "2025dal", "2025cur", "2025mil", "2025joh"
        }

        is_division = event_key in division_keys
        is_einstein = event_key == "2025cmptx"

        if is_einstein:
            world_champ_penalty = 0.95  # Optional bonus for Einstein
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
        breakdowns.append(breakdown)

        # Aggregate scoring metrics from breakdown
        reef = breakdown.get("autoReef", {})
        reef_teleop = breakdown.get("teleopReef", {})
        
        # Track endgame scenarios
        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        if robot_endgame in endgame_scenarios:
            endgame_scenarios[robot_endgame] += 1

        actual_auto = estimate_consistent_auto(breakdowns, team_count)
        actual_teleop = estimate_consistent_teleop(breakdowns, team_count)
        actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)
        actual_overall = actual_auto + actual_teleop + actual_endgame
        
        opponent_score = match["alliances"][opponent_alliance]["score"] / team_count
        margin = actual_overall - opponent_score
        scaled_margin = margin / (opponent_score + 1e-6)
        norm_margin = (scaled_margin + 1) / 1.3  # maps [-1, 1] → [0, 1]
        dominance_scores.append(min(1.0, max(0.0, norm_margin)))

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        total_matches = sum(1 for m in matches if team_key in m["alliances"]["red"]["team_keys"] or team_key in m["alliances"]["blue"]["team_keys"])

        decay = world_champ_penalty * (match_count / len(matches)) ** 2

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            endgame_epa = actual_endgame
            teleop_epa = actual_teleop
            continue

        K = 0.4

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
    dominance = min(1., statistics.mean(dominance_scores))

    event_count = len({match["event_key"] for match in matches})
    event_boost = 1.0 if event_count >= 2 else 0.60
    
    win_rate = wins / match_count if match_count else 0

    average_match_score = total_score / match_count if match_count else 0

    expected_win_rate = dominance  # roughly aligned
    record_alignment_score = 1.0 - abs(expected_win_rate - win_rate)

    weights = {
        "consistency": 0.35,
        "dominance": 0.35,
        "record_alignment": 0.15,
        "veteran": 0.10,
        "events": 0.05,
    }
    
    raw_confidence = (
        weights["consistency"] * consistency +
        weights["dominance"] * dominance +
        weights["record_alignment"] * record_alignment_score +
        weights["veteran"] * (1.0 if is_veteran else 0.4) +
        weights["events"] * event_boost 
    )
    
    # Apply non-linear scaling to create wider spread
    if raw_confidence > 0.7:  # Boost top performers
        raw_confidence = 0.7 + (raw_confidence - 0.7) * 1.5
    elif raw_confidence < 0.3:  # Penalize poor performers more
        raw_confidence = raw_confidence * 0.8
    
    confidence = min(1.0, raw_confidence)

    actual_epa = overall_epa * confidence

    # Track individual match values for each component
    l4_values = []
    l3_values = []
    l2_values = []
    l1_values = []
    net_values = []
    processor_values = []
    
    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue
            
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        breakdown = match.get("score_breakdown", {}).get(alliance, {})
        team_count = len(match["alliances"][alliance]["team_keys"])
        
        reef = breakdown.get("autoReef", {})
        reef_teleop = breakdown.get("teleopReef", {})
        
        # Calculate per-team values using logarithmic scaling
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        
        # For branch levels, apply scaling factor to get per-team contribution
        l4_val = (reef.get("tba_topRowCount", 0) + reef_teleop.get("tba_topRowCount", 0)) * scaling_factor
        l3_val = (reef.get("tba_midRowCount", 0) + reef_teleop.get("tba_midRowCount", 0)) * scaling_factor
        l2_val = (reef.get("tba_botRowCount", 0) + reef_teleop.get("tba_botRowCount", 0)) * scaling_factor
        l1_val = (reef.get("trough", 0) + reef_teleop.get("trough", 0)) * scaling_factor
        
        # For algae, also use scaling factor but keep max possible at 9
        net_val = breakdown.get("netAlgaeCount", 0) * scaling_factor
        processor_val = breakdown.get("wallAlgaeCount", 0) * scaling_factor
        
        # Store values for capability check
        l4_values.append(l4_val)
        l3_values.append(l3_val)
        l2_values.append(l2_val)
        l1_values.append(l1_val)
        net_values.append(net_val)
        processor_values.append(processor_val)
        
        # Add to totals
        total_l4 += l4_val
        total_l3 += l3_val
        total_l2 += l2_val
        total_l1 += l1_val
        total_net += net_val
        total_processor += processor_val
        
        # Track endgame scenarios
        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        if robot_endgame in endgame_scenarios:
            endgame_scenarios[robot_endgame] += 1

        actual_auto = estimate_consistent_auto(breakdowns, team_count)
        actual_teleop = estimate_consistent_teleop(breakdowns, team_count)
        actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)
        actual_overall = actual_auto + actual_teleop + actual_endgame
        
        opponent_score = match["alliances"][opponent_alliance]["score"] / team_count
        margin = actual_overall - opponent_score
        scaled_margin = margin / (opponent_score + 1e-6)
        norm_margin = (scaled_margin + 1) / 1.3  # maps [-1, 1] → [0, 1]
        dominance_scores.append(min(1.0, max(0.0, norm_margin)))

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        total_matches = sum(1 for m in matches if team_key in m["alliances"]["red"]["team_keys"] or team_key in m["alliances"]["blue"]["team_keys"])

        decay = world_champ_penalty * (match_count / len(matches)) ** 2

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            endgame_epa = actual_endgame
            teleop_epa = actual_teleop
            continue

        K = 0.4
        K *= match_importance * world_champ_penalty

        delta_auto = decay * K * (actual_auto - auto_epa)
        delta_teleop = decay * K * (actual_teleop - teleop_epa)
        delta_endgame = decay * K * (actual_endgame - endgame_epa)

        auto_epa += delta_auto
        teleop_epa += delta_teleop
        endgame_epa += delta_endgame
        overall_epa = auto_epa + teleop_epa + endgame_epa

        contributions.append(actual_overall)

    # Calculate averages for new metrics
    num_matches = len(matches)
    # Calculate final averages, setting to 0 if team can't do the component or if average is below 1
    avg_l4 = round(total_l4 / num_matches, 1) if l4_values and (total_l4 / num_matches) >= 1 else 0
    avg_l3 = round(total_l3 / num_matches, 1) if l3_values and (total_l3 / num_matches) >= 1 else 0
    avg_l2 = round(total_l2 / num_matches, 1) if l2_values and (total_l2 / num_matches) >= 1 else 0
    avg_l1 = round(total_l1 / num_matches, 1) if l1_values and (total_l1 / num_matches) >= 1 else 0
    avg_net = round(total_net / num_matches, 1) if net_values and (total_net / num_matches) >= 1 else 0
    avg_processor = round(total_processor / num_matches, 1) if processor_values and (total_processor / num_matches) >= 1 else 0

    # Determine most common endgame scenario
    most_common_endgame = max(endgame_scenarios, key=endgame_scenarios.get) if endgame_scenarios else "N/A"

    # Algae EPA (assuming it's a combination of net and processor points)
    # Based on scoring: Net Algae (4 pts) + Wall Algae (2.5 pts)
    algae_epa = round(avg_net * 4 + avg_processor * 2.5, 2)

    print(f"\n===== DEBUG for {team_key} =====")
    print("===== EPA Component Breakdown =====")
    print(f"Auto EPA:     {round(auto_epa, 2)}")
    print(f"Teleop EPA:   {round(teleop_epa, 2)}")
    print(f"Endgame EPA:  {round(endgame_epa, 2)}")
    print(f"→ Overall EPA (unweighted): {round(overall_epa, 2)}")
    print("\n===== Confidence Breakdown =====")
    print(f"→ Consistency:     {round(consistency, 3)} × 0.35 = {round(0.35 * consistency, 4)}")
    print(f"→ Record Align:    {round(record_alignment_score, 3)} × 0.15 = {round(0.15 * record_alignment_score, 4)}")
    print(f"→ Veteran Boost:   {'1.0' if is_veteran else '0.4'} × 0.05 = {round(0.05 * (1.0 if is_veteran else 0.6), 4)}")
    print(f"→ Dominance:       {round(dominance, 3)} × 0.35 = {round(0.35 * dominance, 4)}")
    print(f"→ Confidence Total: {round(raw_confidence, 4)} → Capped: {round(confidence, 3)}")
    print("\n===== Final EPA Calculation =====")
    print(f"{round(overall_epa, 2)} (overall) × {round(confidence, 3)} (confidence) = {round(actual_epa, 2)}")

    # Define thresholds for considering a component as "capable"
    THRESHOLD_MATCHES = 3  # Minimum matches needed to make a determination
    THRESHOLD_CONSISTENCY = 0.1  # If they score this fraction of their max in this component, they can do it
    
    def check_component_capability(values, max_possible):
        if len(values) < THRESHOLD_MATCHES:
            return True  # Not enough data to make a determination
        # Calculate what fraction of their max possible they achieved
        max_achieved = max(values)
        if max_achieved < max_possible * THRESHOLD_CONSISTENCY:
            return False
        return True
    
    # Check capability for each component
    # Max possible values are now per-team maximums with scaling considered
    can_do_l4 = check_component_capability(l4_values, 12)  # Max 12 pieces per team per match
    can_do_l3 = check_component_capability(l3_values, 12)
    can_do_l2 = check_component_capability(l2_values, 12)
    can_do_l1 = check_component_capability(l1_values, 30)  # Level 1 can hold more pieces
    can_do_net = check_component_capability(net_values, 9)  # Max 9 algae per team per match
    can_do_processor = check_component_capability(processor_values, 9)  # Max 9 algae per team per match
    
    # Calculate final averages, setting to 0 if team can't do the component or if average is below 1
    avg_l4 = round(total_l4 / num_matches, 1) if can_do_l4 and num_matches > 0 and (total_l4 / num_matches) >= 1 else 0
    avg_l3 = round(total_l3 / num_matches, 1) if can_do_l3 and num_matches > 0 and (total_l3 / num_matches) >= 1 else 0
    avg_l2 = round(total_l2 / num_matches, 1) if can_do_l2 and num_matches > 0 and (total_l2 / num_matches) >= 1 else 0
    avg_l1 = round(total_l1 / num_matches, 1) if can_do_l1 and num_matches > 0 and (total_l1 / num_matches) >= 1 else 0
    avg_net = round(total_net / num_matches, 1) if can_do_net and num_matches > 0 and (total_net / num_matches) >= 1 else 0
    avg_processor = round(total_processor / num_matches, 1) if can_do_processor and num_matches > 0 and (total_processor / num_matches) >= 1 else 0

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
        "losses": losses,
        "avg_l4": avg_l4,
        "avg_l3": avg_l3,
        "avg_l2": avg_l2,
        "avg_l1": avg_l1,
        "avg_net": avg_net,
        "avg_processor": avg_processor,
        "algae_epa": algae_epa,
        "most_common_endgame": most_common_endgame
    }

def fetch_team_components(team, year, team_epa_cache=None, veteran_teams=None):
    team_key = team["key"]
    try:
        matches = tba_get(f"team/{team_key}/matches/{year}")
        components = calculate_epa_components(matches, team_key, year, team_epa_cache, veteran_teams) if matches else None
    except Exception as e:
        print(f"Failed to fetch matches for team {team_key}: {e}")
        components = None
    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": team.get("website", "N/A"),
        "normal_epa": components["overall"] if components else None,
        "ace": components["actual_epa"] if components else None,
        "confidence": components["confidence"] if components else None,
        "auto_ace": components["auto"] if components else None,
        "teleop_ace": components["teleop"] if components else None,
        "endgame_ace": components["endgame"] if components else None,
        "consistency": components["consistency"] if components else None,
        "average_match_score": components["average_match_score"] if components else None,
        "wins": components["wins"] if components else None,
        "losses": components["losses"] if components else None,
    }

def fetch_and_store_team_data():
    for year in tqdm(range(2025, 2026), desc="Processing Years"):
        print(f"\nProcessing year {year}...")
        section_count = 0
        all_teams = []
        veteran_teams = load_veteran_teams()

        while True:
            endpoint = f"teams/{year}/{section_count}"
            try:
                teams_data = tba_get(endpoint)
            except Exception as e:
                print(f"Error fetching teams for year {year}, section {section_count}: {e}")
                break

            if not teams_data:
                break

            all_teams.extend(teams_data)
            section_count += 1

        print(f"Total teams found: {len(all_teams)}")

        team_epa_cache = {}

        def fetch_epa_for_cache(team):
            team_key = team["key"]
            try:
                matches = tba_get(f"team/{team_key}/matches/{year}")
                components = calculate_epa_components(matches, team_key, year, None, veteran_teams)
                if components:
                    return (team_key, components["overall"])
            except Exception as e:
                print(f"Initial EPA error for {team_key}: {e}")
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_epa_for_cache, team) for team in all_teams]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Initial EPA Pass"):
                result = future.result()
                if result:
                    team_epa_cache[result[0]] = result[1]

        combined_teams = []

        def fetch_team_for_final(team):
            return fetch_team_components(team, year, team_epa_cache, veteran_teams)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_team_for_final, team) for team in all_teams]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Final EPA Pass"):
                result = future.result()
                if result:
                    combined_teams.append(result)

        output_file = f"teams_{year}.json"
        with open(output_file, "w") as f:
            json.dump(combined_teams, f, indent=4)

        print(f"Year {year} data combined and saved to {output_file}")

def analyze_single_team(team_key: str, year: int, team_epa_cache: Optional[Dict] = None, veteran_teams: Optional[List] = None):
    """Analyze EPA for a single team and print detailed results."""
    # Fetch matches for the team
    matches = tba_get(f"team/{team_key}/matches/{year}")
    if not matches:
        print(f"No matches found for team {team_key} in {year}")
        return None
    
    # Calculate EPA components
    result = calculate_epa_components(matches, team_key, year, team_epa_cache, veteran_teams)
    if not result:
        print(f"Could not calculate EPA for team {team_key}")
        return None
    
    # Print detailed results
    print(f"\n{'='*50}")
    print(f"EPA Analysis for Team {team_key} ({year})")
    print(f"{'='*50}")
    print(f"\nOverall EPA: {result['overall']}")
    print(f"Auto EPA: {result['auto']}")
    print(f"Teleop EPA: {result['teleop']}")
    print(f"Endgame EPA: {result['endgame']}")
    print(f"\nConfidence: {result['confidence']}")
    print(f"Consistency: {result['consistency']}")
    print(f"Actual EPA: {result['actual_epa']}")
    print(f"\nRecord: {result['wins']}-{result['losses']}")
    print(f"Average Match Score: {result['average_match_score']}")
    
    if 'avg_l4' in result:
        print(f"\nDetailed Metrics:")
        print(f"Level 4 Avg: {result['avg_l4']}")
        print(f"Level 3 Avg: {result['avg_l3']}")
        print(f"Level 2 Avg: {result['avg_l2']}")
        print(f"Level 1 Avg: {result['avg_l1']}")
        print(f"Net Avg: {result['avg_net']}")
        print(f"Processor Avg: {result['avg_processor']}")
        print(f"Algae EPA: {result['algae_epa']}")
        print(f"Most Common Endgame: {result['most_common_endgame']}")
    
    return result

def main():
    """Main function to handle user input and process EPA calculations."""
    print("\nEPA Calculator 2025")
    print("="*20)
    
    while True:
        mode = input("\nSelect mode:\n1. Single Team Analysis\n2. Process Entire JSON\nEnter choice (1 or 2): ").strip()
        
        if mode not in ['1', '2']:
            print("Invalid choice. Please enter 1 or 2.")
            continue
            
        year = input("Enter year (e.g., 2025): ").strip()
        try:
            year = int(year)
        except ValueError:
            print("Invalid year. Please enter a valid year.")
            continue
            
        if mode == '1':
            team_key = input("Enter team key (e.g., frc254): ").strip().lower()
            if not team_key.startswith('frc'):
                team_key = f"frc{team_key}"
            
            # Load veteran teams if available
            veteran_teams = load_veteran_teams()
            
            # Analyze single team
            analyze_single_team(team_key, year, None, veteran_teams)
            
        else:  # mode == '2'
            # Original JSON processing logic
            fetch_and_store_team_data()
        
        # Ask if user wants to continue
        if input("\nWould you like to analyze another team? (y/n): ").lower() != 'y':
            break

if __name__ == "__main__":
    main()