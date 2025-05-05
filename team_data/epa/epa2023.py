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
        with open("teams_2022.json", "r") as f:
            data = json.load(f)
        return {f"frc{team['team_number']}" for team in data if 'team_number' in team}
    except FileNotFoundError:
        print("Warning: teams_2022.json not found. All teams will be treated as rookies.")
        return set()

def split_matches_by_event(matches):
    events = {}
    for match in matches:
        key = match.get("event_key")
        if key not in events:
            events[key] = []
        events[key].append(match)
    return events

def calculate_epa_for_all_events(matches, team_key, year, team_epa_cache, veteran_teams):
    event_match_dict = split_matches_by_event(matches)
    event_results = {}

    # Compute event-specific EPA using only matches from that event
    for event_key, event_matches in event_match_dict.items():
        event_results[event_key] = calculate_epa_components(event_matches, team_key, year, team_epa_cache, veteran_teams)

    # Compute overall EPA using all matches (unchanged logic)
    overall = calculate_epa_components(matches, team_key, year, team_epa_cache, veteran_teams)

    return overall, event_results

def get_past_epa_percentile_range(team_key, years=(2022), history_dir="team_data"):
    epa_values = []

    for year in years:
        file_path = os.path.join(history_dir, f"teams_{year}.json")
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r") as f:
                year_data = json.load(f)
            for team in year_data:
                if team.get("team_number") and f"frc{team['team_number']}" == team_key:
                    epa = team.get("epa")
                    if epa is not None:
                        epa_values.append(epa)
        except Exception as e:
            print(f"Error reading {file_path} for {team_key}: {e}")
            continue

    if len(epa_values) < 2:
        return 1.0  # Not enough data, assume high uncertainty (i.e., low confidence boost)

    percentile_range = max(epa_values) - min(epa_values)
    if percentile_range == 0:
        return 1.0  # Perfect stability
    mean_epa = statistics.mean(epa_values)
    stability = max(0.0, min(1.0, 1.0 - (percentile_range / (mean_epa + 1e-6))))
    return stability

def estimate_consistent_auto(breakdowns, team_count):
    leave_points = []
    scored_rows = {"B": 3, "M": 4, "T": 6}

    for b in breakdowns:
        # Mobility (3 pts per Yes)
        mobility = sum(1 for i in range(1, 4) if b.get(f"mobilityRobot{i}") == "Yes") * 3
        leave_points.append(mobility)

    median_mobility = statistics.median(leave_points) if leave_points else 0

    # Estimate speaker scoring (less reliable, but balanced)
    game_piece_scores = []
    for b in breakdowns:
        score = 0
        auto_comm = b.get("autoCommunity", {})
        for row, row_vals in auto_comm.items():
            row_score = scored_rows.get(row, 0)
            score += sum(1 for v in row_vals if v != "None") * row_score
        game_piece_scores.append(score)

    median_auto_score = statistics.median(game_piece_scores) if game_piece_scores else 0

    estimated_auto = (median_mobility + (median_auto_score / team_count))
    return estimated_auto

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):
    import statistics

    importance = {"qm": 1.2, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    trend_deltas, contributions, teammate_epas = [], [], []
    total_score = wins = losses = 0

    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent = "blue" if alliance == "red" else "red"
        team_keys = match["alliances"][alliance]["team_keys"]
        team_count = len(team_keys)

        if team_epa_cache:
            for k in team_keys:
                if k != team_key and k in team_epa_cache:
                    teammate_epas.append(team_epa_cache[k])

        alliance_score = match["alliances"][alliance]["score"]
        total_score += alliance_score

        winner = match.get("winning_alliance", "")
        if winner == alliance:
            wins += 1
        elif winner and winner != alliance:
            losses += 1

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})

        index = team_keys.index(team_key) + 1

        # --- AUTO ---
        mobility_pts = sum(1 for i in range(1, 4) if breakdown.get(f"mobilityRobot{i}") == "Yes") * 3
        
        auto_score = 0
        auto_comm = breakdown.get("autoCommunity", {})
        row_scores = {"B": 3, "M": 4, "T": 6}
        for row, cells in auto_comm.items():
            score = row_scores.get(row, 0)
            auto_score += sum(1 for val in cells if val != "None") * score
        
        charge_auto = 0
        for i in range(1, 4):
            state = breakdown.get(f"autoChargeStationRobot{i}", "None")
            if state == "Docked":
                charge_auto += 8  # no "Engaged" in auto in TBA data
            elif state == "Engaged":
                charge_auto += 12
        
        actual_auto = (mobility_pts + auto_score + charge_auto) / team_count
        
        # --- TELEOP ---
        teleop_score = 0
        teleop_comm = breakdown.get("teleopCommunity", {})
        row_scores = {"B": 2, "M": 3, "T": 5}
        for row, cells in teleop_comm.items():
            score = row_scores.get(row, 0)
            teleop_score += sum(1 for val in cells if val != "None") * score
        actual_teleop = teleop_score / team_count
        
        # --- ENDGAME ---
        actual_endgame = 0
        for i in range(1, 4):
            state = breakdown.get(f"endGameChargeStationRobot{i}", "None")
            if state == "Docked":
                actual_endgame += 6
            elif state == "Engaged":
                actual_endgame += 10
            elif state == "Park":
                actual_endgame += 2

        # === TOTAL EPA ===
        actual_overall = actual_auto + actual_teleop + actual_endgame
        opponent_score = match["alliances"][opponent]["score"] / team_count

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
        M = 0 if match_count <= 12 else min((match_count - 12) / 24, 1.0)

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
    percentile_score = get_past_epa_percentile_range(team_key) if is_veteran else 0.5
    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry_score = min(1.0, overall_epa / (teammate_avg_epa + 1e-6))
    confidence = max(0.0, min(1.0, (consistency + rookie_score + carry_score + percentile_score) / 4))
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
        if matches:
            overall, event_breakdowns = calculate_epa_for_all_events(matches, team_key, year, team_epa_cache, veteran_teams)
        else:
            overall = None
            event_breakdowns = {}
    except Exception as e:
        print(f"Failed to fetch matches for team {team_key}: {e}")
        overall = None
        event_breakdowns = {}

    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": team.get("website", "N/A"),
        "normal_epa": overall["overall"] if overall else None,
        "epa": overall["actual_epa"] if overall else None,
        "confidence": overall["confidence"] if overall else None,
        "auto_epa": overall["auto"] if overall else None,
        "teleop_epa": overall["teleop"] if overall else None,
        "endgame_epa": overall["endgame"] if overall else None,
        "consistency": overall["consistency"] if overall else None,
        "trend": overall["trend"] if overall else None,
        "average_match_score": overall["average_match_score"] if overall else None,
        "wins": overall["wins"] if overall else None,
        "losses": overall["losses"] if overall else None,
        "event_breakdowns": event_breakdowns,
    }

def fetch_and_store_team_data():
    for year in tqdm(range(2023, 2024), desc="Processing Years"):
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
                if not matches:
                    return None  # Skip teams with no matches or bad response
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

if __name__ == "__main__":
    try:
        fetch_and_store_team_data()
    except Exception as e:
        print("An error occurred during processing:")
        print(e)
        print("Please check your network connection and DNS settings.")
