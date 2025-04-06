import os
import json
import statistics
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
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

def calculate_epa_components(matches, team_key):
    total_matches = 0
    total_score = 0
    wins = 0
    losses = 0
    contributions = []

    auto_scores = []
    teleop_scores = []
    endgame_scores = []

    for match in matches:
        alliances = match.get("alliances", {})
        red = alliances.get("red", {})
        blue = alliances.get("blue", {})
        teams = red.get("team_keys", []) + blue.get("team_keys", [])

        if team_key not in teams:
            continue

        total_matches += 1

        alliance = "red" if team_key in red.get("team_keys", []) else "blue"
        opponent = "blue" if alliance == "red" else "red"
        alliance_score = alliances[alliance].get("score", 0)
        opponent_score = alliances[opponent].get("score", 0)

        total_score += alliance_score
        contributions.append(alliance_score)

        # Wins / Losses
        if match.get("winning_alliance") == alliance:
            wins += 1
        elif match.get("winning_alliance") == opponent:
            losses += 1

        # Score breakdowns are rare pre-2015, but check anyway
        breakdown = match.get("score_breakdown", {})
        if breakdown:
            alliance_breakdown = breakdown.get(alliance, {})
            auto = alliance_breakdown.get("autoPoints", 0)
            teleop = alliance_breakdown.get("teleopPoints", 0)
            endgame = alliance_breakdown.get("endgamePoints", 0)

            auto_scores.append(auto)
            teleop_scores.append(teleop)
            endgame_scores.append(endgame)

    if total_matches == 0:
        return None

    avg_score = total_score / total_matches
    consistency = 1.0
    if len(contributions) >= 2 and statistics.mean(contributions) > 0:
        consistency = 1.0 - (statistics.stdev(contributions) / statistics.mean(contributions))

    def safe_avg(lst):
        return round(statistics.mean(lst), 2) if lst else None

    return {
        "average_match_score": round(avg_score, 2),
        "wins": wins,
        "losses": losses,
        "consistency": round(consistency, 2),
        "epa": round(avg_score, 2),
        "auto_epa": safe_avg(auto_scores),
        "teleop_epa": safe_avg(teleop_scores),
        "endgame_epa": safe_avg(endgame_scores),
    }

def fetch_team_data(team, year, veteran_teams):
    team_key = team["key"]
    try:
        matches = tba_get(f"team/{team_key}/matches/{year}")
        stats = calculate_epa_components(matches, team_key) if matches else None
    except Exception as e:
        print(f"Failed to fetch matches for team {team_key}: {e}")
        stats = None

    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": team.get("website", "N/A"),
        "epa": stats["epa"] if stats else None,
        "auto_epa": stats["auto_epa"] if stats else None,
        "teleop_epa": stats["teleop_epa"] if stats else None,
        "endgame_epa": stats["endgame_epa"] if stats else None,
        "consistency": stats["consistency"] if stats else None,
        "average_match_score": stats["average_match_score"] if stats else None,
        "wins": stats["wins"] if stats else None,
        "losses": stats["losses"] if stats else None,
        "confidence": None,
        "trend": None,
        "normal_epa": None
    }

def fetch_and_store_team_data_legacy():
    for year in tqdm(range(1992, 2015), desc="Processing Legacy Years"):
        print(f"\nProcessing year {year}...")
        section_count = 0
        all_teams = []

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
        combined_teams = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_team_data, team, year, set()) for team in all_teams]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=f"Building {year} Data"):
                result = future.result()
                if result:
                    combined_teams.append(result)

        output_file = f"teams_{year}.json"
        with open(output_file, "w") as f:
            json.dump(combined_teams, f, indent=4)

        print(f"Year {year} data saved to {output_file}")

if __name__ == "__main__":
    fetch_and_store_team_data_legacy()