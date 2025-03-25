import os
import json
import requests
from dotenv import load_dotenv
from tqdm import tqdm
import concurrent.futures
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type, RetryError
import statistics
import math

load_dotenv()

TBA_API_BASE_URL = "https://www.thebluealliance.com/api/v3"
TBA_AUTH_KEY = os.getenv("TBA_API_KEY")
HEADERS = {"X-TBA-Auth-Key": TBA_AUTH_KEY}

@retry(
    stop=stop_never,  # retry indefinitely
    wait=wait_exponential(multiplier=1, min=0.5, max=5),  # wait between 0.5 and 5 sec
    retry=retry_if_exception_type(Exception),
)
def tba_get(endpoint):
    """Fetch data from The Blue Alliance API with retries."""
    url = f"{TBA_API_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()

import statistics

def calculate_epa_components(matches, team_key, year):
    if year == 2023:
        endgame_key = "endGameChargeStationPoints"
    elif year == 2024:
        endgame_key = "endGameTotalStagePoints"
    elif year == 2025:
        endgame_key = "endGameBargePoints"
    else:
        endgame_key = "endgamePoints"

    importance = {
        "qm": 1.0,
        "qf": 1.2,
        "sf": 1.3,
        "f": 1.4
    }

    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    match_count = 0
    trend_deltas = []
    contributions = []

    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1

        if team_key in match["alliances"]["red"]["team_keys"]:
            alliance = "red"
            opponent_alliance = "blue"
        else:
            alliance = "blue"
            opponent_alliance = "red"

        team_count = len(match["alliances"][alliance].get("team_keys", []))
        if team_count == 0:
            continue

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})

        auto_score = breakdown.get("autoPoints", 0)
        endgame_score = breakdown.get(endgame_key, 0)
        teleop_score = breakdown.get("teleopPoints", 0)

        # Exclude foul points from overall calculation
        foul_points = breakdown.get("foulPoints", 0)

        actual_auto = auto_score / team_count
        actual_endgame = endgame_score / team_count
        actual_teleop = teleop_score / team_count
        actual_overall = (auto_score + teleop_score + endgame_score - foul_points) / team_count

        opponent_score = match["alliances"][opponent_alliance]["score"] / team_count

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            endgame_epa = actual_endgame
            teleop_epa = actual_teleop
            continue

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        decay = 0.95 ** match_count

        # Dynamic learning rate
        if match_count <= 6:
            K = 0.5
        elif match_count <= 12:
            K = 0.5 + ((match_count - 6) * ((1.0 - 0.5) / 6))
        else:
            K = 0.3

        K *= match_importance

        # Margin factor for opponent strength
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

    return {
        "overall": round(abs(overall_epa), 2),
        "auto": round(abs(auto_epa), 2),
        "teleop": round(abs(teleop_epa), 2),
        "endgame": round(abs(endgame_epa), 2),
        "trend": round(trend, 2),
        "consistency": round(consistency, 2)
    }

def fetch_team_components(team, year):
    """Fetch match data for a team and calculate EPA components."""
    team_key = team["key"]
    try:
        matches = tba_get(f"team/{team_key}/matches/{year}")
        components = calculate_epa_components(matches, team_key, year) if matches else None
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
        "epa": components["overall"] if components else None,
        "auto_epa": components["auto"] if components else None,
        "teleop_epa": components["teleop"] if components else None,
        "endgame_epa": components["endgame"] if components else None,
    }

def fetch_and_store_team_data():
    # Process years 2000 through 2025 (adjust as needed)
    for year in tqdm(range(2023, 2024), desc="Processing Years"):
        print(f"\nProcessing year {year}...")
        section_count = 0
        combined_teams = []

        while True:
            endpoint = f"teams/{year}/{section_count}"
            try:
                teams_data = tba_get(endpoint)
            except Exception as e:
                print(f"Error fetching teams for year {year}, section {section_count}: {e}")
                break

            if not teams_data:
                break

            # Use a ThreadPoolExecutor for concurrent fetching.
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_team_components, team, year) for team in teams_data]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        team_info = future.result()
                        combined_teams.append(team_info)
                    except Exception as e:
                        print(f"Error processing a team: {e}")

            section_count += 1

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
