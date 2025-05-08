import statistics
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from dotenv import load_dotenv
import random
import sqlite3

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
    db_path = "epa_teams.sqlite"  # Adjust path if needed
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT team_number FROM epa_history WHERE year <= 2023")
        rows = cursor.fetchall()
        conn.close()
        return {f"frc{row[0]}" for row in rows if isinstance(row[0], int)}
    except Exception as e:
        print(f"Warning: Failed to load veteran teams from database: {e}")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    def score_per_breakdown(b):
        speaker_notes = b.get("autoSpeakerNoteCount", 0)
        amp_notes = b.get("autoAmpNoteCount", 0)
        leave_pts = b.get("autoLeavePoints", 0)
        coop_bonus = 3 / team_count if b.get("coopertitionBonusAchieved") else 0
        score = speaker_notes * 5 + amp_notes * 2 + leave_pts + coop_bonus
        return score
    scores = [score_per_breakdown(b) for b in breakdowns]
    trimmed = scores[:int(len(scores) * 0.75)] if len(scores) >= 4 else scores
    avg = statistics.mean(trimmed)
    return round(min(avg, 40), 2)

def estimate_consistent_teleop(breakdowns, team_count):
    def score_per_breakdown(b):
        amp = b.get("teleopAmpNoteCount", 0)
        speaker = b.get("teleopSpeakerNoteCount", 0)
        amplified = b.get("teleopSpeakerNoteAmplifiedCount", 0)
        base = amp * 1 + speaker * 2 + amplified * 5
        fallback = b.get("teleopTotalNotePoints", base)
        score = max(base, fallback)
        return (score / team_count) * 1.1
    scores = [score_per_breakdown(b) for b in breakdowns]
    scores.sort(reverse=True)
    trimmed = scores[:int(len(scores) * 0.75)] if len(scores) >= 4 else scores
    avg = statistics.mean(trimmed)
    return round(min(avg, 50), 2)

def estimate_endgame_points(breakdown, team_count):
    if not breakdown:
        return 0

    park_points = breakdown.get("endGameParkPoints", 0)
    onstage_points = breakdown.get("endGameOnStagePoints", 0)
    spotlight_points = breakdown.get("endGameSpotLightBonusPoints", 0)
    harmony_points = breakdown.get("endGameHarmonyPoints", 0)
    trap_points = breakdown.get("endGameNoteInTrapPoints", 0)

    return park_points + onstage_points + spotlight_points + harmony_points + trap_points / team_count

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):
    import statistics

    importance = {"qm": 1.2, "qf": 1.1, "sf": 1.1, "f": 1.3}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    total_score = wins = losses = 0
    auto_breakdowns = []
    teleop_breakdowns = []
    dominance_scores = []

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
        auto_breakdowns.append(breakdown)
        teleop_breakdowns.append(breakdown)

        actual_auto = estimate_consistent_auto(auto_breakdowns, team_count)

        actual_teleop = estimate_consistent_teleop(teleop_breakdowns, team_count)

        actual_endgame = estimate_endgame_points(breakdown, team_count)
        
        # === TOTAL EPA ===
        actual_overall = actual_auto + actual_teleop + actual_endgame

        if alliance_score > 0:
            dominance_scores.append(actual_overall / alliance_score)

        opponent_score = match["alliances"][opponent]["score"] / team_count

        if overall_epa is None:
            auto_epa = actual_auto
            teleop_epa = actual_teleop
            endgame_epa = actual_endgame
            overall_epa = actual_overall
            continue  # keep this

        match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
        decay = 0.8

        if match_count <= 6:
            K = 0.5
        elif match_count <= 12:
            K = 0.5 + ((match_count - 6) * ((1.0 - 0.5) / 6))
        else:
            K = 0.3

        K *= match_importance
        M = 0 if match_count <= 12 else min((match_count - 12) / 24, 1.0)

        delta_auto = decay * K * (actual_auto - auto_epa)
        delta_endgame = decay * K * (actual_endgame - endgame_epa)
        delta_teleop = decay * K * (actual_teleop - teleop_epa)

        auto_epa += delta_auto
        endgame_epa += delta_endgame
        teleop_epa += delta_teleop
        overall_epa = auto_epa + endgame_epa + teleop_epa

        contributions.append(actual_overall)

    if not match_count:
        return None

    if len(contributions) >= 2:
        peak = max(contributions)
        stdev = statistics.stdev(contributions)
        consistency = max(0.0, 1.0 - stdev / (peak + 1e-6))
    else:
        consistency = 1.0

    is_veteran = veteran_teams and team_key in veteran_teams
    rookie_score = 1.0 if is_veteran else 0.6
    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry_score = overall_epa / (teammate_avg_epa + 1e-6)
    dominance_avg = statistics.mean(dominance_scores) if dominance_scores else 0.33
    
    # Confidence baseline is still a mix of consistency, veteran status, and carry
    confidence = (
    0.35 * consistency +
    0.2 * (1.0 if is_veteran else 0.6) +
    0.25 * min(1.25, carry_score) +
    0.2 * min(1.0, dominance_avg)
    )
    
    # Bonus boost for extreme performance
    if overall_epa >= 50 and carry_score > 1.1:
        confidence += 0.1

    confidence = min(1.0, round(confidence, 3))
    actual_epa = overall_epa * confidence
    average_match_score = total_score / match_count if match_count else 0

    return {
        "overall": round(overall_epa, 2),
        "auto": round(auto_epa, 2),
        "teleop": round(teleop_epa, 2),
        "endgame": round(endgame_epa, 2),
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
        "consistency": components["consistency"] if components else None,
        "average_match_score": components["average_match_score"] if components else None,
        "wins": components["wins"] if components else None,
        "losses": components["losses"] if components else None,
    }

def fetch_and_store_team_data():
    for year in tqdm(range(2024, 2025), desc="Processing Years"):
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
