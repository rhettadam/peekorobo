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
        with open("teams_2023.json", "r") as f:
            data = json.load(f)
        return {f"frc{team['team_number']}" for team in data if 'team_number' in team}
    except FileNotFoundError:
        print("Warning: teams_2023.json not found. All teams will be treated as rookies.")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    if not breakdowns:
        return 0

    def score_per_breakdown(b):
        # Determine how many speaker notes were scored total
        speaker_notes = b.get("autoSpeakerNoteCount", 0)
        amp_notes = b.get("autoAmpNoteCount", 0)
        leave_pts = b.get("autoLeavePoints", 0)

        # Try to weight the estimate based on the likelihood that the team is carrying
        avg_speaker_per_team = speaker_notes / team_count if team_count else 0
        speaker_ratio = (speaker_notes + 1e-6) / (avg_speaker_per_team + 1e-6) if avg_speaker_per_team else 1

        # Cap ratio so we don't overinflate
        speaker_ratio = min(speaker_ratio, 3.0)

        # Estimate as if the team did the majority of the notes in this match
        est_speaker = speaker_ratio * 5
        est_amp = (amp_notes / team_count) * 2
        est_leave = leave_pts / team_count  

        coop_bonus = 3 / team_count if b.get("coopertitionBonusAchieved") else 0

        return est_speaker + est_amp + est_leave + coop_bonus

    scores = sorted(score_per_breakdown(b) for b in breakdowns)

    if len(scores) >= 4:
        cutoff = int(len(scores) * 0.75)
        trimmed_scores = scores[:cutoff]
        average = statistics.mean(trimmed_scores)
    else:
        average = statistics.median(scores)

    return round(min(average, 40), 2)  # bump cap slightly for high auto teams

def estimate_consistent_teleop(breakdowns, team_count):
    if not breakdowns:
        return 0

    def score_per_breakdown(b):
        amp_notes = b.get("teleopAmpNoteCount", 0)
        speaker_notes = b.get("teleopSpeakerNoteCount", 0)
        amplified_notes = b.get("amplifiedSpeakerNoteCount", 0)

        # Estimate team contribution based on note type and rarity of amplification
        base_score = (
            (amp_notes * 1) +
            (speaker_notes * 2) +
            (amplified_notes * 3)  # amplification usually means team is strong
        )

        per_team_score = base_score / team_count if team_count else base_score
        return per_team_score * 1.1  # Apply small boost for higher impact scoring

    scores = [score_per_breakdown(b) for b in breakdowns]
    trimmed = statistics.median_high(scores) if len(scores) < 4 else statistics.mean(sorted(scores)[:int(0.75 * len(scores))])
    return round(min(trimmed, 50), 2)  # reasonable cap

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):
    import statistics

    importance = {"qm": 1.2, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    trend_deltas, contributions, teammate_epas = [], [], []
    total_score = wins = losses = 0
    auto_breakdowns = []

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

        actual_auto = estimate_consistent_auto(auto_breakdowns, team_count)

        actual_teleop = estimate_consistent_teleop(auto_breakdowns, team_count)

        # === ENDGAME CALCULATION (2024) ===
        actual_endgame = 0
        trap_keys = ["trapStageLeft", "trapCenterStage", "trapStageRight"]
        trap_flags = [breakdown.get(k) for k in trap_keys]
        trap_bonus_given = [False, False, False]

        for i in range(1, 4):
            status = breakdown.get(f"endGameRobot{i}", "None")
            if status == "Parked":
                actual_endgame += 1
            elif status in ["StageLeft", "CenterStage", "StageRight"]:
                actual_endgame += 3
                trap_idx = ["StageLeft", "CenterStage", "StageRight"].index(status)
                if trap_flags[trap_idx] and not trap_bonus_given[trap_idx]:
                    actual_endgame += 5
                    trap_bonus_given[trap_idx] = True

        # === TOTAL EPA ===
        actual_overall = actual_auto + actual_teleop + actual_endgame
        opponent_score = match["alliances"][opponent]["score"] / team_count

        if overall_epa is None:
            auto_epa = estimate_consistent_auto(auto_breakdowns, team_count)
            teleop_epa = actual_teleop
            endgame_epa = actual_endgame
            overall_epa = auto_epa + teleop_epa + endgame_epa
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
        "trend": components["trend"] if components else None,
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
