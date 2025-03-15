import os
import json
import requests
from dotenv import load_dotenv
from tqdm import tqdm
import concurrent.futures
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type, RetryError

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

def calculate_epa_components(matches, team_key, year):
    if year <= 2022:
        endgame_key = "endgamePoints"
    elif year == 2023:
        endgame_key = "endGameChargeStationPoints"
    elif year == 2024:
        endgame_key = "endGameTotalStagePoints"
    elif year == 2025:
        endgame_key = "endGameBargePoints"
    else:
        endgame_key = "endgamePoints"

    # Sort matches chronologically; if "time" is None, use 0.
    matches = sorted(matches, key=lambda m: m.get("time") or 0)
    overall_epa = None
    auto_epa = None
    endgame_epa = None
    match_count = 0

    for match in matches:
        match_count += 1
        # Determine alliance and opponent.
        if team_key in match["alliances"]["red"]["team_keys"]:
            alliance = "red"
            opponent_alliance = "blue"
        elif team_key in match["alliances"]["blue"]["team_keys"]:
            alliance = "blue"
            opponent_alliance = "red"
        else:
            continue  # Skip matches where the team is not present.

        # Overall contribution: alliance score / 3.
        actual_overall = match["alliances"][alliance]["score"] / 3
        opponent_overall = match["alliances"][opponent_alliance]["score"] / 3

        # Get breakdown for this alliance; default missing to empty dict.
        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})
        auto_score = breakdown.get("autoPoints", 0)
        endgame_score = breakdown.get(endgame_key, 0)
        actual_auto = auto_score / 3
        actual_endgame = endgame_score / 3

        # Initialize EPAs on the first match.
        if overall_epa is None:
            overall_epa = actual_overall
        if auto_epa is None:
            auto_epa = actual_auto
        if endgame_epa is None:
            endgame_epa = actual_endgame

        # Determine update factor K.
        if match_count <= 6:
            K = 0.5
        elif match_count <= 12:
            K = 0.5 + ((match_count - 6) * ((1.0 - 0.5) / 6))
        else:
            K = 0.3

        # Determine margin parameter M for overall EPA update.
        if match_count <= 12:
            M = 0
        elif match_count <= 36:
            M = (match_count - 12) / (36 - 12)
        else:
            M = 1

        # Update overall EPA.
        delta_overall = (K / (1 + M)) * ((actual_overall - overall_epa) - M * (opponent_overall - overall_epa))
        overall_epa += delta_overall

        # Update Auto EPA.
        delta_auto = K * (actual_auto - auto_epa)
        auto_epa += delta_auto

        # Update Endgame EPA.
        delta_endgame = K * (actual_endgame - endgame_epa)
        endgame_epa += delta_endgame

    # Compute Teleop EPA as the residual.
    teleop_epa = overall_epa - auto_epa - endgame_epa if overall_epa is not None and auto_epa is not None and endgame_epa is not None else None

    return {
        "overall": abs(overall_epa),
        "auto": abs(auto_epa),
        "teleop": abs(teleop_epa),
        "endgame": abs(endgame_epa),
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
    for year in tqdm(range(2025, 2026), desc="Processing Years"):
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
