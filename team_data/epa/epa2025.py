import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv

import random

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
    try:
        with open("teams_2024.json", "r") as f:
            data = json.load(f)
        return {f"frc{team['team_number']}" for team in data if 'team_number' in team}
    except FileNotFoundError:
        print("Warning: teams_2024.json not found. All teams will be treated as rookies.")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    if not breakdowns:
        return 0

    def score_per_breakdown(b):
        reef = b.get("autoReef", {})
        trough = reef.get("trough", 0)
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)

        coral_score = trough * 3 + bot * 4 + mid * 6 + top * 7
        mobility = b.get("autoMobilityPoints", 0) / team_count
        bonus = 5 / team_count if b.get("autoBonusAchieved") else 0

        return mobility + coral_score + bonus

    scores = sorted(score_per_breakdown(b) for b in breakdowns)

    if len(scores) >= 4:
        # Trim top 25% to reduce overestimation
        cutoff = int(len(scores) * 0.75)
        trimmed_scores = scores[:cutoff]
        average = statistics.mean(trimmed_scores)
    else:
        average = statistics.median(scores)

    # Optional: cap extremely high values
    return round(min(average, 40), 2)

def estimate_consistent_teleop(breakdowns, team_count):
    if not breakdowns:
        return 0

    def score_per_breakdown(b):
        reef = b.get("teleopReef", {})
        trough = reef.get("trough", 0)
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)

        barge = b.get("netAlgaeCount", 0) * 4
        processor = b.get("netAlgaeCount", 0) * 6

        coral_score = trough * 2 + bot * 3 + mid * 4 + top * 5  
        algae_score = barge + processor
        bonus = 5 / team_count if b.get("coralBonusAchieved") else 0

        return coral_score + algae_score + bonus

    scores = sorted(score_per_breakdown(b) for b in breakdowns)

    if len(scores) >= 4:
        cutoff = int(len(scores) * 0.75)
        trimmed_scores = scores[:cutoff]
        average = statistics.mean(trimmed_scores)
    else:
        average = statistics.median(scores)

    return round(min(average, 80), 2)  # Adjust max cap based on observed teleop values

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):

    importance = {
        "qm": 1.4,
        "qf": 1,
        "sf": 1,
        "f": 1,
    }

    matches = sorted(matches, key=lambda m: m.get("time") or 0)
    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    trend_deltas = []
    contributions = []
    teammate_epas = []
    auto_breakdowns = []
    teleop_breakdowns = []

    # Variables for new match stats
    total_score = 0
    wins = 0
    losses = 0

    for match in matches:
        # Skip matches where the team did not play
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1

        if team_key in match["alliances"]["red"]["team_keys"]:
            alliance = "red"
            opponent_alliance = "blue"
        else:
            alliance = "blue"
            opponent_alliance = "red"

        # --- New: Update match statistics ---
        # Get the alliance score and accumulate it
        alliance_score = match["alliances"][alliance]["score"]
        total_score += alliance_score

        # Count wins and losses based on the winning alliance
        winning_alliance = match.get("winning_alliance", "")
        if winning_alliance == alliance:
            wins += 1
        elif winning_alliance and winning_alliance != alliance:
            losses += 1

        team_keys = match["alliances"][alliance].get("team_keys", [])
        team_count = len(team_keys)
        if team_count == 0:
            continue

        if team_epa_cache:
            others = [k for k in team_keys if k != team_key]
            for k in others:
                if k in team_epa_cache:
                    teammate_epas.append(team_epa_cache[k])

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})
        auto_breakdowns.append(breakdown)
        teleop_breakdowns.append(breakdown)
        index = team_keys.index(team_key) + 1

        # Auto EPA from consistent pattern analysis
        actual_auto = estimate_consistent_auto(auto_breakdowns, team_count)

        # Endgame EPA based on individual robot position
        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        if robot_endgame == "DeepCage":
            actual_endgame = 12
        elif robot_endgame == "ShallowCage":
            actual_endgame = 6
        elif robot_endgame == "Parked":
            actual_endgame = 2
        else:
            actual_endgame = 0

        actual_teleop = estimate_consistent_teleop(teleop_breakdowns, team_count)
        
        if breakdown.get("autoBonusAchieved"):
            actual_auto += 5 / team_count
        
        if breakdown.get("coralBonusAchieved"):
            actual_teleop += 5 / team_count
        
        if breakdown.get("bargeBonusAchieved"):
            actual_endgame += 5 / team_count

        #foul_points = breakdown.get("foulPoints", 0)
        actual_overall = actual_auto + actual_teleop + actual_endgame

        opponent_score = match["alliances"][opponent_alliance]["score"] / team_count

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            endgame_epa = actual_endgame
            teleop_epa = actual_teleop
            continue

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        decay = 0.95 ** match_count

        if match_count <= 6:
            K = 0.5
        elif match_count <= 12:
            K = 0.5 + ((match_count - 6) * ((1.0 - 0.5) / 6))
        else:
            K = 0.3

        K *= match_importance

        if match_count <= 12:
            M = 0
        elif match_count <= 36:
            M = (match_count - 12) / 24
        else:
            M = 1

        delta_overall = decay * (K / (1 + M)) * ((actual_overall - overall_epa) - M * (opponent_score - overall_epa))
        delta_auto = decay * K * (actual_auto - auto_epa)
        delta_endgame = decay * K * (actual_endgame - endgame_epa)
        delta_teleop = decay * K * (actual_teleop - teleop_epa)

        overall_epa += delta_overall
        auto_epa += delta_auto
        endgame_epa += delta_endgame
        teleop_epa += delta_teleop

        trend_deltas.append(delta_overall)
        contributions.append(actual_overall)

    if not match_count:
        return None

    trend = sum(trend_deltas[-3:]) if len(trend_deltas) >= 3 else sum(trend_deltas)
    consistency = 1.0 - (statistics.stdev(contributions) / statistics.mean(contributions)) if len(contributions) >= 2 else 1.0

    is_veteran = veteran_teams and team_key in veteran_teams
    rookie_score = 1.0 if is_veteran else 0.6

    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry_score = min(1.0, overall_epa / (teammate_avg_epa + 1e-6))

    confidence = max(0.0, min(1.0, (consistency + rookie_score + carry_score /3)))

    actual_epa = overall_epa * confidence

    average_match_score = total_score / match_count if match_count else 0

    return {
        "overall": round(overall_epa, 2),
        "auto": round(auto_epa, 2),
        "teleop": round(teleop_epa, 2),
        "endgame": round(endgame_epa, 2),
        "trend": round(trend, 2),
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
        "epa": components["actual_epa"] if components else None,
        "confidence": components["confidence"] if components else None,
        "auto_epa": components["auto"] if components else None,
        "teleop_epa": components["teleop"] if components else None,
        "endgame_epa": components["endgame"] if components else None,
        "consistency": overall["consistency"] if overall else None,
        "trend": components["trend"] if components else None,
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
                try:
                    result = future.result(timeout=30)
                    if result:
                        team_epa_cache[result[0]] = result[1]
                except Exception as e:
                    print(f"Initial EPA error for a team: {e}")
            executor.shutdown(wait=True)  # optional but explicit

        combined_teams = []

        def fetch_team_for_final(team):
            return fetch_team_components(team, year, team_epa_cache, veteran_teams)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_team_for_final, team) for team in all_teams]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Final EPA Pass"):
                try:
                    result = future.result(timeout=30)
                    if result:
                        combined_teams.append(result)
                except Exception as e:
                    print(f"Final EPA error for a team: {e}")
            executor.shutdown(wait=True)  # optional but explicit

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
