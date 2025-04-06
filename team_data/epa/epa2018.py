import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

TBA_API_BASE_URL = "https://www.thebluealliance.com/api/v3"
TBA_AUTH_KEY = os.getenv("TBA_API_KEY")
HEADERS = {"X-TBA-Auth-Key": TBA_AUTH_KEY}

@retry(
    stop=stop_never,
    wait=wait_exponential(multiplier=1, min=0.5, max=5),
    retry=retry_if_exception_type(Exception),
)
def tba_get(endpoint):
    url = f"{TBA_API_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()

def load_veteran_teams():
    try:
        with open("teams_2017.json", "r") as f:
            data = json.load(f)
        return {f"frc{team['team_number']}" for team in data if 'team_number' in team}
    except FileNotFoundError:
        print("Warning: teams_2024.json not found. All teams will be treated as rookies.")
        return set()

def calculate_epa_components_2018(matches, team_key, year, team_epa_cache=None, veteran_teams=None):
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
        if team_count == 0:
            continue

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
        if not breakdown:
            continue

        # === AUTO ===
        auto_points = (
            breakdown.get("autoOwnershipPoints", 0) +
            breakdown.get("autoRunPoints", 0)
        )
        actual_auto = auto_points / team_count

        # === TELEOP ===
        teleop_points = breakdown.get("teleopOwnershipPoints", 0) + breakdown.get("vaultPoints", 0)
        actual_teleop = teleop_points / team_count

        # === ENDGAME ===
        actual_endgame = breakdown.get("endgamePoints", 0) / team_count

        # === TOTAL ===
        actual_overall = actual_auto + actual_teleop + actual_endgame
        opponent_score = match["alliances"][opponent]["score"] / team_count

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            teleop_epa = actual_teleop
            endgame_epa = actual_endgame
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
        delta_teleop = decay * K * (actual_teleop - teleop_epa)
        delta_endgame = decay * K * (actual_endgame - endgame_epa)

        overall_epa += delta_overall
        auto_epa += delta_auto
        teleop_epa += delta_teleop
        endgame_epa += delta_endgame

        trend_deltas.append(delta_overall)
        contributions.append(actual_overall)

    if not match_count:
        return None

    trend = sum(trend_deltas[-3:]) if len(trend_deltas) >= 3 else sum(trend_deltas)
    consistency = 1.0 - (statistics.stdev(contributions) / statistics.mean(contributions)) if len(contributions) >= 2 else 1.0
    rookie_score = 1.0 if (veteran_teams and team_key in veteran_teams) else 0.6
    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry_score = min(1.0, overall_epa / (teammate_avg_epa + 1e-6))
    confidence = max(0.0, min(1.0, (consistency + rookie_score + carry_score) / 3))
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
        components = calculate_epa_components_2018(matches, team_key, year, team_epa_cache, veteran_teams) if matches else None
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
    for year in tqdm(range(2018,2019), desc="Processing Years"):
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
                components = calculate_epa_components_2018(matches, team_key, year, None, veteran_teams)
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
