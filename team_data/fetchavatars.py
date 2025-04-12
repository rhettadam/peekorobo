import os
import base64
import json
import concurrent.futures
from tqdm import tqdm
import requests
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv
import random

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS", "").split(',')

AVATAR_DIR = "avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

@retry(
    stop=stop_never,
    wait=wait_exponential(multiplier=1, min=0.5, max=5),
    retry=retry_if_exception_type(Exception),
)
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def download_avatar_if_not_exists(team_number, year):
    filepath = os.path.join(AVATAR_DIR, f"{team_number}.png")
    if os.path.exists(filepath):
        return False  # Already has an avatar, skip it

    team_key = f"frc{team_number}"
    avatar_data = tba_get(f"team/{team_key}/media/{year}")
    if not avatar_data:
        return False

    for media in avatar_data:
        if media.get("type") == "avatar":
            base64_img = media.get("details", {}).get("base64Image")
            if base64_img:
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(base64_img))
                return True  # Avatar saved
    return False

def fetch_all_avatars(start_year=2025, end_year=2018):
    already_downloaded = set(os.path.splitext(f)[0] for f in os.listdir(AVATAR_DIR) if f.endswith(".png"))

    for year in range(start_year, end_year - 1, -1):
        print(f"\nProcessing avatars from {year}...")

        try:
            with open(f"teams_{year}.json", "r") as f:
                teams = json.load(f)
        except FileNotFoundError:
            print(f"teams_{year}.json not found. Skipping.")
            continue

        team_numbers = [team["team_number"] for team in teams if "team_number" in team]
        team_numbers = [tn for tn in team_numbers if str(tn) not in already_downloaded]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(tqdm(
                executor.map(lambda tn: (tn, download_avatar_if_not_exists(tn, year)), team_numbers),
                total=len(team_numbers),
                desc=f"Avatars {year}"
            ))

        # Add successfully saved avatars to the downloaded set
        for team_number, saved in results:
            if saved:
                already_downloaded.add(str(team_number))

if __name__ == "__main__":
    fetch_all_avatars()
