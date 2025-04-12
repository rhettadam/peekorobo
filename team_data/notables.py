import os
import json
import time
import random
import requests
from tqdm import tqdm
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS", "").split(",")
HEADERS = lambda: {"X-TBA-Auth-Key": random.choice(API_KEYS)}

OUTPUT_FILE = "notables_by_year.json"

# Known Hall of Fame video links
HOF_VIDEOS = {
    "frc16": "https://youtu.be/_0d-Bpb54wA",
    "frc103": "https://youtu.be/93QaCAN78BY",
    "frc27": "https://youtu.be/BCz2yTVPxbM",
    "frc67": "https://youtu.be/-j2grFq6RIc",
    "frc120": "https://youtu.be/oAqcyov8qBc",
    "frc175": "https://youtu.be/7bq_-GzJRdc",
    "frc1902": "https://youtu.be/SwSMUPLeQLE",
    "frc236": "https://youtu.be/NmzCLohIZLg",
    "frc341": "https://youtu.be/-AzvT02ZCNk",
    "frc359": "https://youtu.be/e9IV1chHJtg",
    "frc503": "https://youtu.be/34gb_BMgnw8",
    "frc597": "https://youtu.be/2FKks-d6LOo",
    "frc842": "https://youtu.be/MnzIYVUJzzM",
    "frc1114": "https://youtu.be/VqciMgjw-SY",
    "frc1311": "https://youtu.be/PkJ1ogk7lVY",
    "frc1538": "https://youtu.be/p62jRCMkoiw",
    "frc1629": "https://youtu.be/PvDw-LUi4ck",
    "frc1816": "https://youtu.be/z22VXg6aIlI",
    "frc2486": "https://www.youtube.com/watch?v=9oBL8s2Y7tA",
    "frc2614": "https://youtu.be/8EeHoscHnKI",
    "frc2834": "https://youtu.be/dCE90sw1mD0",
    "frc3132": "https://youtu.be/yyZr4mHW2XE",
    "frc321": "https://youtu.be/1aBjvwdYF5o",
    "frc365": "https://youtu.be/rklPfwfEatU",
    "frc254": "https://youtu.be/fhEf3Z39spA",
    "frc111": "https://youtu.be/SfCjZMMIt0k",
    "frc191": "https://youtu.be/nhHMEnl-Ugs",
    "frc987": "https://youtu.be/wpv-9yd_CJk"
}

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
)
def tba_get(endpoint):
    response = requests.get(f"{TBA_BASE_URL}/{endpoint}", headers=HEADERS())
    response.raise_for_status()
    return response.json()

def fetch_notables_by_year(year):
    try:
        data = tba_get(f"insights/notables/{year}")
    except Exception as e:
        print(f"❌ Failed to fetch notables for {year}: {e}")
        return {}

    result = {}
    for entry in data:
        category = entry.get("name")
        teams = []
        for record in entry.get("data", {}).get("entries", []):
            team_key = record.get("team_key")
            context = record.get("context", [])
            if team_key:
                team_info = {"team": team_key, "context": context}
                if category == "notables_hall_of_fame" and team_key in HOF_VIDEOS:
                    team_info["video"] = HOF_VIDEOS[team_key]
                teams.append(team_info)
        result[category] = teams
    return result

def build_notables_database(start=1992, end=2025):
    full_data = {}
    for year in tqdm(range(start, end + 1), desc="Fetching Notables"):
        year_data = fetch_notables_by_year(year)
        if year_data:
            full_data[year] = year_data
        time.sleep(0.5)  # Be nice to TBA
    return full_data

if __name__ == "__main__":
    notables_data = build_notables_database()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(notables_data, f, indent=2)
    print(f"\n✅ Notables with Hall of Fame video links saved to {OUTPUT_FILE}")
