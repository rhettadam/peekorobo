import os
import requests
import base64
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Set API Base URL and Auth Key
TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
TBA_AUTH_KEY = os.getenv("TBA_API_KEY")
HEADERS = {"X-TBA-Auth-Key": TBA_AUTH_KEY}

# Directory to save avatars
AVATAR_DIR = "team_avatars_2025"
os.makedirs(AVATAR_DIR, exist_ok=True)


def tba_get(endpoint: str):
    """Fetch data from The Blue Alliance API."""
    url = f"{TBA_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching {endpoint}: {response.status_code} - {response.text}")
        return None


def save_avatar(team_number: int, base64_data: str):
    """Save the avatar image from base64 data."""
    file_path = os.path.join(AVATAR_DIR, f"{team_number}.png")
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(base64_data))
    print(f"Saved avatar for team {team_number}.")


def download_team_avatars(year=2025):
    """Download avatars for all teams in the specified year."""
    page = 0
    while True:
        # Fetch a page of teams
        teams = tba_get(f"teams/{page}")
        if not teams:
            break

        for team in tqdm(teams, desc=f"Processing Page {page}"):
            team_number = team["team_number"]
            # Fetch media for the team
            media = tba_get(f"team/frc{team_number}/media/{year}")
            if not media:
                print(f"No media found for team {team_number}.")
                continue

            # Find and save the avatar
            avatar = next(
                (item for item in media if item.get("type") == "avatar" and "base64Image" in item.get("details", {})),
                None,
            )
            if avatar:
                base64_image = avatar["details"]["base64Image"]
                save_avatar(team_number, base64_image)
            else:
                print(f"No avatar available for team {team_number}.")

        page += 1


if __name__ == "__main__":
    download_team_avatars(year=2025)
