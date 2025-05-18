import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv
import random
import sqlite3
import math

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

@retry(
    stop=stop_never,
    wait=wait_exponential(multiplier=1, min=0.5, max=5),
    retry=retry_if_exception_type(Exception),
)
def tba_get(endpoint: str):
    # Cycle through keys by selecting one randomly or using a round-robin approach.
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def load_veteran_teams():
    db_path = "epa_teams.sqlite"  # Adjust path if needed
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT team_number FROM epa_history WHERE year <= 2021")
        rows = cursor.fetchall()
        conn.close()
        return {f"frc{row[0]}" for row in rows if isinstance(row[0], int)}
    except Exception as e:
        print(f"Warning: Failed to load veteran teams from database: {e}")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    def score_per_breakdown(b):
        # 2022 Auto Scoring
        # autoTaxiPoints is typically 6 if all taxis succeed
        auto_taxi = b.get("autoTaxiPoints", 0)
        
        # Sum cargo from all sources (near, far, blue, red) for lower and upper hubs
        auto_cargo_lower = b.get("autoCargoLowerNear", 0) + b.get("autoCargoLowerFar", 0) + b.get("autoCargoLowerBlue", 0) + b.get("autoCargoLowerRed", 0)
        auto_cargo_upper = b.get("autoCargoUpperNear", 0) + b.get("autoCargoUpperFar", 0) + b.get("autoCargoUpperBlue", 0) + b.get("autoCargoUpperRed", 0)
        
        # Points per cargo: Lower = 2, Upper = 4
        auto_cargo_points = (auto_cargo_lower * 2) + (auto_cargo_upper * 4)

        # Total Auto points for the alliance from scoring actions
        # Note: autoPoints field in API breakdown already sums these, but calculating explicitly mirrors rules
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (auto_taxi + auto_cargo_points) * scaling_factor

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
        # 2022 Teleop Scoring
        # Sum cargo from all sources (near, far, blue, red) for lower and upper hubs
        teleop_cargo_lower = b.get("teleopCargoLowerNear", 0) + b.get("teleopCargoLowerFar", 0) + b.get("teleopCargoLowerBlue", 0) + b.get("teleopCargoLowerRed", 0)
        teleop_cargo_upper = b.get("teleopCargoUpperNear", 0) + b.get("teleopCargoUpperFar", 0) + b.get("teleopCargoUpperBlue", 0) + b.get("teleopCargoUpperRed", 0)

        # Points per cargo: Lower = 1, Upper = 2
        teleop_cargo_points = (teleop_cargo_lower * 1) + (teleop_cargo_upper * 2)

        # Total Teleop points for the alliance from scoring actions
        # Note: teleopCargoPoints field in API breakdown already sums these, but calculating explicitly mirrors rules
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return teleop_cargo_points * scaling_factor

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

def calculate_epa_components_2022(matches, team_key, year, team_epa_cache=None, veteran_teams=None):

    importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    total_score = wins = losses = 0
    breakdowns = []
    dominance_scores = []

    for match in matches:

        event_key = match.get("event_key", "")
        division_keys = {
            "2022tur", "2022carv", "2022gal", "2022hop",
            "2022roe", "2022new"
        }

        is_division = event_key in division_keys
        is_einstein = event_key == "2022cmptx"

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

        # Use total points from breakdown for the current match's actual scores
        actual_auto = breakdown.get("autoPoints", 0)
        actual_teleop = breakdown.get("teleopCargoPoints", 0) # Or teleopPoints depending on desired granularity
        
        # Calculate individual robot's endgame points
        robot_index = team_keys.index(team_key) + 1 
        robot_endgame_status = breakdown.get(f"endgameRobot{robot_index}", "None")
        actual_endgame = {"Low": 4, "Mid": 6, "High": 10, "Traversal": 15, "None": 0}.get(robot_endgame_status, 0)

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
        "consistency": 0.4,
        "dominance": 0.25,
        "record_alignment": 0.15,
        "veteran": 0.1,
        "events": 0.05,
        "base": 0.05,
    }
    
    raw_confidence = (
        weights["consistency"] * consistency +
        weights["dominance"] * dominance +
        weights["record_alignment"] * record_alignment_score +
        weights["veteran"] * (1.0 if is_veteran else 0.6) +
        weights["events"] * event_boost +
        weights["base"]
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
    print(f"→ Record Align:    {round(record_alignment_score, 3)} × 0.15 = {round(0.15 * record_alignment_score, 4)}")
    print(f"→ Veteran Boost:   {'1.0' if is_veteran else '0.6'} × 0.1 = {round(0.1 * (1.0 if is_veteran else 0.6), 4)}")
    print(f"→ Dominance:       {round(dominance, 3)} × 0.25 = {round(0.25 * dominance, 4)}")
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

def fetch_team_components(team, year, team_epa_cache=None, veteran_teams=None):
    team_key = team["key"]
    try:
        matches = tba_get(f"team/{team_key}/matches/{year}")
        components = calculate_epa_components_2022(matches, team_key, year, team_epa_cache, veteran_teams) if matches else None
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
        "epa": components["actual_epa"] if components else None,
        "confidence": components["confidence"] if components else None,
        "auto_epa": components["auto"] if components else None,
        "teleop_epa": components["teleop"] if components else None,
        "endgame_epa": components["endgame"] if components else None,
        "consistency": components["consistency"] if components else None,
        "trend": components["trend"] if components else None,
        "average_match_score": components["average_match_score"] if components else None,
        "wins": components["wins"] if components else None,
        "losses": components["losses"] if components else None,
    }

def fetch_and_store_team_data():
    for year in tqdm(range(2022, 2023), desc="Processing Years"):
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
                components = calculate_epa_components_2022(matches, team_key, year, None, veteran_teams)
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

if __name__ == "__main__":
    try:
        fetch_and_store_team_data()
    except Exception as e:
        print("An error occurred during processing:")
        print(e)
        print("Please check your network connection and DNS settings.")
