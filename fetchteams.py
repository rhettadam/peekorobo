import os
import json
import requests
from statistics import mean
from dotenv import load_dotenv
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

TBA_API_BASE_URL = "https://www.thebluealliance.com/api/v3"
TBA_AUTH_KEY = os.getenv("TBA_API_KEY")
HEADERS = {"X-TBA-Auth-Key": TBA_AUTH_KEY}


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def tba_get(endpoint):
    """Fetch data from The Blue Alliance API with retries."""
    url = f"{TBA_API_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()


def calculate_epa(matches, team_key):
    """Calculate EPA for a team based on their matches."""
    epa_scores = []

    for match in matches:
        alliance = None
        if team_key in match["alliances"]["red"]["team_keys"]:
            alliance = "red"
        elif team_key in match["alliances"]["blue"]["team_keys"]:
            alliance = "blue"

        if alliance:
            total_score = match["alliances"][alliance]["score"]
            epa_scores.append(total_score / 3)  # Divide by 3 for three teams in an alliance

    return mean(epa_scores) if epa_scores else None


def fetch_and_store_team_data():
    """Fetch data for all teams from 1992 to 2025 and store it locally."""
    for year in tqdm(range(2018, 2026), desc="Processing Years"):
        print(f"\nProcessing year {year}...")
        section_count = 0
        combined_teams = []

        while True:
            teams = []
            endpoint = f"teams/{year}/{section_count}"
            teams_data = tba_get(endpoint)

            if not teams_data:
                break

            for team in tqdm(
                teams_data, desc=f"Fetching teams for {year}, Section {section_count}", leave=False
            ):
                team_key = team["key"]
                try:
                    matches = tba_get(f"team/{team_key}/matches/{year}")
                    epa = calculate_epa(matches, team_key) if matches else None
                except requests.exceptions.RequestException as e:
                    print(f"Failed to fetch matches for team {team_key}: {e}")
                    epa = None

                # Prepare team data
                team_info = {
                    "team_number": team.get("team_number"),
                    "nickname": team.get("nickname"),
                    "city": team.get("city"),
                    "state_prov": team.get("state_prov"),
                    "country": team.get("country"),
                    "epa": epa,
                }
                teams.append(team_info)

            combined_teams.extend(teams)
            section_count += 1

        # Save combined data for the year
        output_file = f"teams_{year}.json"
        with open(output_file, "w") as f:
            json.dump(combined_teams, f, indent=4)

        print(f"Year {year} data combined and saved to {output_file}")


if __name__ == "__main__":
    fetch_and_store_team_data()
