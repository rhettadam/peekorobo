import os
import json
import random
import sqlite3
import statistics
import requests
import concurrent.futures
from tqdm import tqdm
from dotenv import load_dotenv
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type

# --- Setup ---
load_dotenv()
TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS").split(',')

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def load_veteran_teams():
    try:
        with open("teams_2024.json", "r") as f:
            data = json.load(f)
        return {f"frc{team['team_number']}" for team in data if 'team_number' in team}
    except FileNotFoundError:
        print("Warning: teams_2024.json not found. All teams will be treated as rookies.")
        return set()

def estimate_consistent_auto(breakdowns, team_count):
    def score_per_breakdown(b):
        reef = b.get("autoReef", {})
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        coral_score = bot * 3 + mid * 4 + top * 7
        mobility = b.get("autoMobilityPoints", 0)
        bonus = 5 / team_count if b.get("autoBonusAchieved") else 0
        return mobility + coral_score + bonus

    scores = sorted(score_per_breakdown(b) for b in breakdowns)
    if len(scores) >= 4:
        trimmed = scores[:int(len(scores) * 0.75)]
        avg = statistics.mean(trimmed)
    else:
        avg = statistics.median(scores)
    return round(min(avg, 30), 2)

def calculate_epa_components(matches, team_key, year, team_epa_cache=None, veteran_teams=None):
    importance = {"qm": 1.4, "qf": 1, "sf": 1, "f": 1}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)
    match_count, wins, losses = 0, 0, 0
    trend_deltas, contributions, teammate_epas, auto_breakdowns = [], [], [], []

    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    total_score = 0

    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent = "blue" if alliance == "red" else "red"
        score = match["alliances"][alliance]["score"]
        total_score += score
        if match.get("winning_alliance", "") == alliance:
            wins += 1
        elif match.get("winning_alliance", "") == opponent:
            losses += 1

        team_keys = match["alliances"][alliance].get("team_keys", [])
        if team_epa_cache:
            for k in team_keys:
                if k != team_key and k in team_epa_cache:
                    teammate_epas.append(team_epa_cache[k])

        breakdown = (match.get("score_breakdown") or {}).get(alliance, {})
        auto_breakdowns.append(breakdown)
        index = team_keys.index(team_key) + 1

        actual_auto = estimate_consistent_auto(auto_breakdowns, len(team_keys))
        robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
        actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)
        teleop_score = breakdown.get("teleopPoints", 0)
        actual_teleop = teleop_score / len(team_keys)

        if breakdown.get("autoBonusAchieved"): actual_auto += 5 / len(team_keys)
        if breakdown.get("coralBonusAchieved"): actual_teleop += 5 / len(team_keys)
        if breakdown.get("bargeBonusAchieved"): actual_endgame += 5 / len(team_keys)

        foul_points = breakdown.get("foulPoints", 0)
        actual_overall = actual_auto + actual_teleop + actual_endgame - foul_points
        opponent_score = match["alliances"][opponent]["score"] / len(team_keys)

        if overall_epa is None:
            overall_epa = actual_overall
            auto_epa = actual_auto
            teleop_epa = actual_teleop
            endgame_epa = actual_endgame
            continue

        match_importance = importance.get(match.get("comp_level", "qm"), 1)
        decay = 0.95 ** match_count
        K = 0.5 if match_count <= 6 else 0.5 + ((match_count - 6) * (0.5 / 6)) if match_count <= 12 else 0.3
        K *= match_importance
        M = 0 if match_count <= 12 else min(1, (match_count - 12) / 24)

        delta = decay * (K / (1 + M)) * ((actual_overall - overall_epa) - M * (opponent_score - overall_epa))
        overall_epa += delta
        auto_epa += decay * K * (actual_auto - auto_epa)
        teleop_epa += decay * K * (actual_teleop - teleop_epa)
        endgame_epa += decay * K * (actual_endgame - endgame_epa)

        trend_deltas.append(delta)
        contributions.append(actual_overall)

    if match_count == 0:
        return None

    trend = sum(trend_deltas[-3:]) if len(trend_deltas) >= 3 else sum(trend_deltas)
    consistency = 1.0 - (statistics.stdev(contributions) / statistics.mean(contributions)) if len(contributions) >= 2 else 1.0
    rookie_score = 1.0 if (veteran_teams and team_key in veteran_teams) else 0.6
    teammate_avg_epa = statistics.mean(teammate_epas) if teammate_epas else overall_epa
    carry_score = min(1.0, overall_epa / (teammate_avg_epa + 1e-6))
    confidence = max(0.0, min(1.0, (consistency + rookie_score + carry_score) / 3))
    actual_epa = overall_epa * confidence
    avg_score = total_score / match_count

    return {
        "overall": round(overall_epa, 2),
        "auto": round(auto_epa, 2),
        "teleop": round(teleop_epa, 2),
        "endgame": round(endgame_epa, 2),
        "trend": round(trend, 2),
        "consistency": round(consistency, 2),
        "confidence": round(confidence, 2),
        "actual_epa": round(actual_epa, 2),
        "average_match_score": round(avg_score, 2),
        "wins": wins,
        "losses": losses
    }

def fetch_team_components(team, year, team_epa_cache=None, veteran_teams=None):
    team_key = team["key"]
    try:
        matches = tba_get(f"team/{team_key}/matches/{year}")
        components = calculate_epa_components(matches, team_key, year, team_epa_cache, veteran_teams) if matches else None
    except Exception as e:
        print(f"Failed to fetch matches for {team_key}: {e}")
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

def generate_and_store_epa(year=2025):
    print(f"Generating EPA for year {year}...")
    veteran_teams = load_veteran_teams()
    section, all_teams = 0, []

    while True:
        teams_data = tba_get(f"teams/{year}/{section}")
        if not teams_data: break
        all_teams.extend(teams_data)
        section += 1

    # EPA Cache
    team_epa_cache = {}

    def get_cache(team):
        team_key = team["key"]
        try:
            matches = tba_get(f"team/{team_key}/matches/{year}")
            components = calculate_epa_components(matches, team_key, year, None, veteran_teams)
            return (team_key, components["overall"]) if components else None
        except: return None

    print("Building initial EPA cache...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_cache, t) for t in all_teams]
        for f in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="EPA Prepass"):
            r = f.result()
            if r: team_epa_cache[r[0]] = r[1]

    print("Calculating final EPA values...")
    combined = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_team_components, t, year, team_epa_cache, veteran_teams) for t in all_teams]
        for f in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="EPA Final"):
            r = f.result()
            if r: combined.append(r)

    print(f"Inserting into database ({len(combined)} teams)...")
    conn = sqlite3.connect("epa_teams.sqlite")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS epa_history (
        year INTEGER,
        team_number INTEGER,
        nickname TEXT,
        city TEXT,
        state_prov TEXT,
        country TEXT,
        website TEXT,
        normal_epa REAL,
        epa REAL,
        confidence REAL,
        auto_epa REAL,
        teleop_epa REAL,
        endgame_epa REAL,
        consistency REAL,
        trend REAL,
        average_match_score REAL,
        wins INTEGER,
        losses INTEGER,
        PRIMARY KEY (year, team_number)
    )""")

    for team in combined:
        cur.execute("""
        INSERT OR REPLACE INTO epa_history (
            year, team_number, nickname, city, state_prov, country, website,
            normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
            consistency, trend, average_match_score, wins, losses
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            year,
            team.get("team_number"),
            team.get("nickname"),
            team.get("city"),
            team.get("state_prov"),
            team.get("country"),
            team.get("website"),
            team.get("normal_epa"),
            team.get("epa"),
            team.get("confidence"),
            team.get("auto_epa"),
            team.get("teleop_epa"),
            team.get("endgame_epa"),
            team.get("consistency"),
            team.get("trend"),
            team.get("average_match_score"),
            team.get("wins"),
            team.get("losses")
        ))

    conn.commit()
    conn.close()
    print("✅ Done.")

if __name__ == "__main__":
    generate_and_store_epa()
