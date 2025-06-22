import statistics
import math
import json
from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import sqlite3
import random
from typing import Dict, List, Optional, Union

from models import *
from pg_epa import *

load_dotenv()

# Keep SQLite paths for backward compatibility during transition
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
EVENTS_DB_PATH = os.path.join(SCRIPT_DIR, "events.sqlite")
EPA_TEAMS_DB_PATH = os.path.join(SCRIPT_DIR, "epa_teams.sqlite")

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

def create_event_db(year):
    """Create and populate the events database for the specified year."""
    print(f"\n🧹 Creating events database for {year}...")
    
    # Create PostgreSQL tables if they don't exist
    create_epa_tables()
    
    # Clear existing data for this year
    clear_year_data(year)

    try:
        events = tba_get(f"events/{year}")
    except Exception as e:
        print(f"❌ Failed to load events for {year}: {e}")
        return

    def fetch(event):
        key = event["key"]
        data = {
            "event": (
                key, event.get("name"), year,
                event.get("start_date"), event.get("end_date"),
                event.get("event_type_string"), event.get("city"),
                event.get("state_prov"), event.get("country"),
                event.get("website")
            ),
            "teams": [], "rankings": [], "oprs": [], "matches": [], "awards": []
        }
        try:
            teams = tba_get(f"event/{key}/teams")
            for t in teams:
                t_num = t.get("team_number")
                data["teams"].append((key, t_num, t.get("nickname"),
                                      t.get("city"), t.get("state_prov"), t.get("country")))
        except:
            pass
        try:
            ranks = tba_get(f"event/{key}/rankings")
            for r in ranks.get("rankings", []):
                record = r.get("record", {})
                t_num = int(r.get("team_key", "frc0")[3:])
                data["rankings"].append((key, t_num, r.get("rank"),
                                         record.get("wins"), record.get("losses"),
                                         record.get("ties"), r.get("dq")))
        except:
            pass
        try:
            oprs = tba_get(f"event/{key}/oprs").get("oprs", {})
            for t_key, opr in oprs.items():
                t_num = int(t_key[3:])
                data["oprs"].append((key, t_num, opr))
        except:
            pass
        try:
            matches = tba_get(f"event/{key}/matches")
            for m in matches:
                data["matches"].append((
                    m["key"], key, m["comp_level"], m["match_number"],
                    m["set_number"],
                    ",".join(str(int(t[3:])) for t in m["alliances"]["red"]["team_keys"]),
                    ",".join(str(int(t[3:])) for t in m["alliances"]["blue"]["team_keys"]),
                    m["alliances"]["red"]["score"], m["alliances"]["blue"]["score"],
                    m.get("winning_alliance"),
                    next((v["key"] for v in m.get("videos", []) if v["type"] == "youtube"), None)
                ))
        except:
            pass
        try:
            awards = tba_get(f"event/{key}/awards")
            for aw in awards:
                for r in aw.get("recipient_list", []):
                    if r.get("team_key"):
                        t_num = int(r["team_key"][3:])
                        data["awards"].append((key, t_num, aw.get("name"), year))
        except:
            pass
        return data

    all_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch, ev) for ev in events]
        for f in tqdm(as_completed(futures), total=len(events), desc=f"Updating {year}"):
            try:
                all_data.append(f.result())
            except Exception as e:
                print(f"❌ Error processing: {e}")

    # Insert all data into PostgreSQL
    insert_event_data(all_data, year)
    print(f"\n✅ {year} events rebuilt and saved to PostgreSQL")

# Confidence calculation constants
CONFIDENCE_WEIGHTS = {
    "consistency": 0.35,
    "dominance": 0.35,
    "record_alignment": 0.10,
    "veteran": 0.10,
    "events": 0.10,
}

CONFIDENCE_THRESHOLDS = {
    "high": 0.85,  # Lower threshold for high confidence boost
    "low": 0.65,   # Higher threshold for low confidence reduction
}

CONFIDENCE_MULTIPLIERS = {
    "high_boost": 1.1,  # Reduced multiplier for high confidence
    "low_reduction": 0.9  # Increased multiplier for low confidence
}

EVENT_BOOSTS = {
    1: 0.5,   # Single event
    2: 0.9,  # Two events
    3: 1.0    # Three or more events
}

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, headers=headers, timeout=30)  # Add 30 second timeout
        if r.status_code == 200:
            return r.json()
        else:
            print(f"TBA API error for {endpoint}: {r.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout for {endpoint}")
        raise  # Let retry handle it
    except requests.exceptions.RequestException as e:
        print(f"Request error for {endpoint}: {e}")
        raise  # Let retry handle it
    except Exception as e:
        print(f"Unexpected error for {endpoint}: {e}")
        raise  # Let retry handle it

def get_team_experience(team_number: int, up_to_year: int) -> int:
    """
    Determine how many years a team has competed up to and including up_to_year.
    Returns the number of years of experience (1 for first year, 2 for second year, etc.)
    """
    try:
        return get_team_experience_pg(team_number, up_to_year)
    except Exception as e:
        print(f"Failed to get team experience: {e}")
        return 1  # Default to first year if we can't determine

def get_veteran_boost(years: int) -> float:
    """
    Calculate veteran boost based on years of experience.
    First year: 0.2
    Second year: 0.4
    Third year: 0.6
    Fourth year and beyond: 1.0
    """
    if years <= 1:
        return 0.2
    elif years == 2:
        return 0.4
    elif years == 3:
        return 0.6
    else:
        return 1.0

def calculate_confidence(consistency: float, dominance: float, event_boost: float, team_number: int, wins: int = 0, losses: int = 0, year: int = None) -> tuple[float, float, float]:
    """
    Calculate confidence score using universal parameters.
    Returns (raw_confidence, capped_confidence, record_alignment)
    """
    years = get_team_experience(team_number, year) if year is not None else get_team_experience(team_number, 2025)
    veteran_boost = get_veteran_boost(years)
    
    # Calculate record alignment based on win-loss record
    total_matches = wins + losses
    if total_matches > 0:
        win_rate = wins / total_matches
        # Scale win rate to be between 0.7 and 1.0
        # 0% win rate = 0.7, 50% win rate = 0.85, 100% win rate = 1.0
        record_alignment = 0.7 + (win_rate * 0.3)
    else:
        record_alignment = 0.7  # Default to middle value if no matches
    
    raw_confidence = (
        CONFIDENCE_WEIGHTS["consistency"] * consistency +
        CONFIDENCE_WEIGHTS["dominance"] * dominance +
        CONFIDENCE_WEIGHTS["record_alignment"] * record_alignment +
        CONFIDENCE_WEIGHTS["veteran"] * veteran_boost +
        CONFIDENCE_WEIGHTS["events"] * event_boost
    )
    
    # Apply non-linear scaling
    if raw_confidence > CONFIDENCE_THRESHOLDS["high"]:
        raw_confidence = CONFIDENCE_THRESHOLDS["high"] + (raw_confidence - CONFIDENCE_THRESHOLDS["high"]) * CONFIDENCE_MULTIPLIERS["high_boost"]
    elif raw_confidence < CONFIDENCE_THRESHOLDS["low"]:
        raw_confidence = raw_confidence * CONFIDENCE_MULTIPLIERS["low_reduction"]
    
    capped_confidence = max(0.0, min(1.0, raw_confidence))
    return raw_confidence, capped_confidence, record_alignment

def calculate_event_epa(matches: List[Dict], team_key: str) -> Dict:
    importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
    matches = sorted(matches, key=lambda m: m.get("time") or 0)

    match_count = 0
    overall_epa = auto_epa = teleop_epa = endgame_epa = None
    contributions, teammate_epas = [], []
    breakdowns = []
    dominance_scores = []
    event_wins = 0
    event_losses = 0

    # Get the year from the first match's event key
    year = matches[0]["event_key"][:4] if matches else "2025"
    
    # Get the appropriate scoring functions for this year
    try:
        auto_func = globals()[f"auto_{year}"]
        teleop_func = globals()[f"teleop_{year}"]
        endgame_func = globals()[f"endgame_{year}"]
    except KeyError:
        print(f"Warning: No scoring functions found for year {year}, using 2025 functions")
        auto_func = auto_2025
        teleop_func = teleop_2025
        endgame_func = endgame_2025

    for match in matches:
        if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
            continue

        match_count += 1
        alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
        opponent_alliance = "blue" if alliance == "red" else "red"

        # Track wins/losses
        winning_alliance = match.get("winning_alliance", "")
        if winning_alliance == alliance:
            event_wins += 1
        elif winning_alliance and winning_alliance != alliance:
            event_losses += 1

        team_keys = match["alliances"][alliance].get("team_keys", [])
        team_count = len(team_keys)
        index = team_keys.index(team_key) + 1

        # Safely get and validate breakdown
        breakdown = match.get("score_breakdown", {})
        
        # Handle case where breakdown might be a string
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse breakdown JSON for match {match.get('key', 'unknown')}")
                continue
        
        if not isinstance(breakdown, dict):
            print(f"Warning: Invalid breakdown format for match {match.get('key', 'unknown')}: {type(breakdown)}")
            continue
            
        alliance_breakdown = breakdown.get(alliance, {})
        if not isinstance(alliance_breakdown, dict):
            print(f"Warning: Invalid alliance breakdown format for match {match.get('key', 'unknown')}: {type(alliance_breakdown)}")
            continue

        breakdowns.append(alliance_breakdown)
        
        try:
            # Debug print the breakdown structure
            #print(f"\nProcessing match {match.get('key', 'unknown')}")
            #print(f"Breakdown keys: {list(alliance_breakdown.keys())}")
            
            actual_auto = auto_func(breakdowns, team_count)
            actual_teleop = teleop_func(breakdowns, team_count)
            
            # Handle endgame differently based on year
            if year == "2023" or year == "2017" or year == "2016": # Add 2016 to the list of years expecting breakdowns and team_count
                actual_endgame = endgame_func(breakdowns, team_count)
            else:  # 2024, 2025, etc. still expect alliance_breakdown and index
                actual_endgame = endgame_func(alliance_breakdown, index)
                
            actual_overall = actual_auto + actual_teleop + actual_endgame
            
            opponent_score = match["alliances"][opponent_alliance]["score"] / team_count
            margin = actual_overall - opponent_score
            scaled_margin = margin / (opponent_score + 1e-6)
            norm_margin = (scaled_margin + 1) / 1.3
            dominance_scores.append(min(1.0, max(0.0, norm_margin)))

            match_importance = importance.get(match.get("comp_level", "qm"), 1.0)

            # Decay simplified for event-specific EPA
            decay = 1.0 

            if overall_epa is None: # Initial EPA for the event
                overall_epa = actual_overall
                auto_epa = actual_auto
                endgame_epa = actual_endgame
                teleop_epa = actual_teleop
                continue

            K = 0.4
            K *= match_importance * decay

            delta_auto = K * (actual_auto - auto_epa)
            delta_teleop = K * (actual_teleop - teleop_epa)
            delta_endgame = K * (actual_endgame - endgame_epa)

            auto_epa += delta_auto
            teleop_epa += delta_teleop
            endgame_epa += delta_endgame
            overall_epa = auto_epa + teleop_epa + endgame_epa

            contributions.append(actual_overall)
        except Exception as e:
            print(f"Warning: Error processing match {match.get('key', 'unknown')}: {str(e)}")

    if not match_count:
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "match_count": 0, "raw_confidence": 0.0,
            "consistency": 0.0, "dominance": 0.0,
            "event_boost": 0.0, "veteran_boost": 0.0,
            "years_experience": 0, "weights": CONFIDENCE_WEIGHTS,
            "record_alignment": 0.0, "wins": event_wins,
            "losses": event_losses
        }

    if len(contributions) >= 2:
        peak = max(contributions)
        stdev = statistics.stdev(contributions)
        consistency = max(0.0, 1.0 - stdev / (peak + 1e-6))
    else:
        consistency = 1.0

    dominance = min(1., statistics.mean(dominance_scores)) if dominance_scores else 0.0

    # Get total number of events for this team
    event_keys = get_team_events(team_number, int(year))
    total_events = len(event_keys)

    # Calculate event boost based on number of events
    event_boost = EVENT_BOOSTS.get(min(total_events, 3), EVENT_BOOSTS[3])
    
    # Calculate confidence using universal function
    raw_confidence, confidence, record_alignment = calculate_confidence(consistency, dominance, event_boost, team_number, event_wins, event_losses, int(year))
    actual_epa = (overall_epa * confidence) if overall_epa is not None else 0.0

    # Get years of experience for display
    years = get_team_experience(team_number, int(year))
    veteran_boost = get_veteran_boost(years)

    return {
        "overall": round(overall_epa, 2) if overall_epa is not None else 0.0,
        "auto": round(auto_epa, 2) if auto_epa is not None else 0.0,
        "teleop": round(teleop_epa, 2) if teleop_epa is not None else 0.0,
        "endgame": round(endgame_epa, 2) if endgame_epa is not None else 0.0,
        "confidence": round(confidence, 2),
        "actual_epa": round(actual_epa, 2),
        "match_count": match_count,
        "raw_confidence": raw_confidence,
        "consistency": consistency,
        "dominance": dominance,
        "event_boost": event_boost,
        "veteran_boost": veteran_boost,
        "years_experience": years,
        "weights": CONFIDENCE_WEIGHTS,
        "record_alignment": record_alignment,
        "wins": event_wins,
        "losses": event_losses
    }

def aggregate_overall_epa(event_epas: List[Dict]) -> Dict:
    if not event_epas:
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0
        }

    # Filter out events with no valid matches or zero EPAs
    valid_events = [
        epa_data for epa_data in event_epas 
        if epa_data.get("match_count", 0) > 0 and epa_data["overall"] > 0
    ]

    if not valid_events:
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0
        }

    total_overall = 0.0
    total_auto = 0.0
    total_teleop = 0.0
    total_endgame = 0.0
    total_actual_epa = 0.0
    total_match_count = 0
    total_confidence = 0.0
    total_consistency = 0.0
    total_dominance = 0.0
    total_veteran_boost = 0.0
    total_event_boost = 0.0
    total_record_alignment = 0.0
    total_events = 0
    total_wins = 0
    total_losses = 0

    # Use a weighted average based on match count per event
    for epa_data in valid_events:
        match_count = epa_data.get("match_count", 0)
        if match_count == 0: # Skip events with no matches
            continue
        
        total_overall += epa_data["overall"] * match_count
        total_auto += epa_data["auto"] * match_count
        total_teleop += epa_data["teleop"] * match_count
        total_endgame += epa_data["endgame"] * match_count
        total_actual_epa += epa_data["actual_epa"] * match_count
        total_match_count += match_count
        total_confidence += epa_data["confidence"] * match_count
        total_consistency += epa_data["consistency"] * match_count
        total_dominance += epa_data["dominance"] * match_count
        total_veteran_boost += epa_data["veteran_boost"] * match_count
        total_event_boost += epa_data["event_boost"] * match_count
        total_record_alignment += epa_data["record_alignment"] * match_count
        total_wins += epa_data["wins"]
        total_losses += epa_data["losses"]
        total_events += 1
    
    if total_match_count == 0:
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0
        }

    avg_confidence = total_confidence / total_match_count
    avg_consistency = total_consistency / total_match_count
    avg_dominance = total_dominance / total_match_count
    avg_veteran_boost = total_veteran_boost / total_match_count
    avg_event_boost = total_event_boost / total_match_count
    avg_record_alignment = total_record_alignment / total_match_count

    # Calculate the weighted components for display
    weights = valid_events[0]["weights"]  # Weights are constant across events
    consistency_component = weights["consistency"] * avg_consistency
    record_component = weights["record_alignment"] * avg_record_alignment
    veteran_component = weights["veteran"] * avg_veteran_boost
    dominance_component = weights["dominance"] * avg_dominance
    event_component = weights["events"] * avg_event_boost

    # Calculate raw confidence from components
    raw_confidence = (
        consistency_component +
        record_component +
        veteran_component +
        dominance_component +
        event_component
    )

    # Apply non-linear scaling
    if raw_confidence > CONFIDENCE_THRESHOLDS["high"]:
        raw_confidence = CONFIDENCE_THRESHOLDS["high"] + (raw_confidence - CONFIDENCE_THRESHOLDS["high"]) * CONFIDENCE_MULTIPLIERS["high_boost"]
    elif raw_confidence < CONFIDENCE_THRESHOLDS["low"]:
        raw_confidence = raw_confidence * CONFIDENCE_MULTIPLIERS["low_reduction"]
    
    final_confidence = max(0.0, min(1.0, raw_confidence))

    return {
        "overall": round(total_overall / total_match_count, 2),
        "auto": round(total_auto / total_match_count, 2),
        "teleop": round(total_teleop / total_match_count, 2),
        "endgame": round(total_endgame / total_match_count, 2),
        "confidence": round(final_confidence, 2),
        "actual_epa": round((total_overall / total_match_count) * final_confidence, 2),
        "wins": total_wins,
        "losses": total_losses,
        "avg_consistency": avg_consistency,
        "avg_dominance": avg_dominance,
        "avg_veteran_boost": avg_veteran_boost,
        "avg_event_boost": avg_event_boost,
        "avg_record_alignment": avg_record_alignment,
        "total_events": total_events,
        "confidence_components": {
            "consistency": consistency_component,
            "record": record_component,
            "veteran": veteran_component,
            "dominance": dominance_component,
            "event": event_component,
            "raw": raw_confidence
        }
    }

def fetch_team_components(team, year):
    team_key = team["key"]
    team_number = team["team_number"]

    # Get team events from PostgreSQL
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    total_wins = 0
    total_losses = 0

    for event_key in event_keys:
        try:
            matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            if matches:
                # Calculate overall wins/losses from matches
                for match in matches:
                    if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                        continue
                    
                    alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
                    winning_alliance = match.get("winning_alliance", "")
                    if winning_alliance == alliance:
                        total_wins += 1
                    elif winning_alliance and winning_alliance != alliance:
                        total_losses += 1

                # Calculate EPA after processing all matches
                event_epa = calculate_event_epa(matches, team_key)
                event_epa["event_key"] = event_key
                event_epa_results.append(event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")
            continue

    # Aggregate overall EPA from event-specific EPAs
    overall_epa_data = aggregate_overall_epa(event_epa_results)
    overall_epa_data["wins"] = total_wins
    overall_epa_data["losses"] = total_losses

    # Always return a result, even if no events were found
    return {
        "team_number": team.get("team_number"),
        "nickname": team.get("nickname"),
        "city": team.get("city"),
        "state_prov": team.get("state_prov"),
        "country": team.get("country"),
        "website": team.get("website", "N/A"),
        "normal_epa": overall_epa_data.get("overall", 0),
        "confidence": overall_epa_data.get("confidence", 0),
        "epa": overall_epa_data.get("actual_epa", 0),
        "auto_epa": overall_epa_data.get("auto", 0),
        "teleop_epa": overall_epa_data.get("teleop", 0),
        "endgame_epa": overall_epa_data.get("endgame", 0),
        "wins": overall_epa_data.get("wins", 0),
        "losses": overall_epa_data.get("losses", 0),
        "event_epas": event_epa_results, # List of event-specific EPA results
    }

def fetch_and_store_team_data(year):
    # Ensure events.sqlite is created and populated before running the teams model
    create_event_db(year)
    print(f"\nProcessing year {year}...")

    # Get all teams directly from PostgreSQL
    all_teams = get_teams_for_year(year)
    print(f"Total unique teams found from events: {len(all_teams)}")

    def fetch_team_for_final(team):
        return fetch_team_components(team, year)

    inserted = 0
    failed_teams = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_team_for_final, team) for team in all_teams]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Final EPA Pass"):
            try:
                result = future.result()
                if result:
                    # Insert team EPA data into PostgreSQL
                    insert_team_epa(result, year)
                    inserted += 1
                    if inserted % 100 == 0:
                        print(f"Processed {inserted} teams so far...")
                else:
                    # This shouldn't happen anymore with our fix, but let's track it
                    failed_teams.append("Unknown team (result was None)")
            except Exception as e:
                # Get the team info from the future if possible
                team_info = "Unknown team"
                try:
                    # Try to get the team info from the future's args
                    if hasattr(future, '_args') and future._args:
                        team_info = f"Team {future._args[0].get('team_number', 'Unknown')}"
                except:
                    pass
                failed_teams.append(f"{team_info}: {str(e)}")
                print(f"Failed to process {team_info}: {e}")
                continue
    
    print(f"✅ Successfully updated {inserted} entries for {year} in PostgreSQL")
    if failed_teams:
        print(f"❌ Failed to process {len(failed_teams)} teams:")
        for failed in failed_teams[:10]:  # Show first 10 failures
            print(f"  - {failed}")
        if len(failed_teams) > 10:
            print(f"  ... and {len(failed_teams) - 10} more")

def analyze_single_team(team_key: str, year: int):
    # Get team events from PostgreSQL
    team_number = int(team_key[3:])
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    total_wins = 0
    total_losses = 0

    for event_key in event_keys:
        try:
            matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            if matches:
                # Calculate overall wins/losses from matches
                for match in matches:
                    if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                        continue
                    
                    alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
                    winning_alliance = match.get("winning_alliance", "")
                    if winning_alliance == alliance:
                        total_wins += 1
                    elif winning_alliance and winning_alliance != alliance:
                        total_losses += 1

                event_epa = calculate_event_epa(matches, team_key)
                event_epa["event_key"] = event_key # Add event key to the result
                event_epa_results.append(event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")

    overall_epa_data = aggregate_overall_epa(event_epa_results)
    overall_epa_data["wins"] = total_wins
    overall_epa_data["losses"] = total_losses

    print(f"\n{'='*50}")
    print(f"EPA Analysis for Team {team_key} ({year})")
    print(f"{'='*50}")
    print(f"\nOverall EPA: {overall_epa_data['overall']}")
    print(f"Overall Confidence: {overall_epa_data['confidence']}")
    print(f"Actual Overall EPA: {overall_epa_data['actual_epa']}")
    print(f"Overall Record: {overall_epa_data['wins']}-{overall_epa_data['losses']}")

    if event_epa_results:
        print(f"\n{'='*50}")
        print("Event-Specific EPA Breakdowns")
        print(f"{'='*50}")
        for event_epa in event_epa_results:
            print(f"\nEvent: {event_epa['event_key']}")
            print(f"  Overall: {event_epa['overall']}")
            print(f"  Auto: {event_epa['auto']}")
            print(f"  Teleop: {event_epa['teleop']}")
            print(f"  Endgame: {event_epa['endgame']}")
            print(f"  Confidence: {event_epa['confidence']}")
            print(f"  Actual EPA: {event_epa['actual_epa']}")
            print("  Confidence Breakdown:")
            weights = event_epa["weights"]
            print(f"    → Consistency:     {round(event_epa['consistency'], 3)} × {weights['consistency']} = {round(weights['consistency'] * event_epa['consistency'], 4)}")
            print(f"    → Record Align:    {round(event_epa['record_alignment'], 3)} × {weights['record_alignment']} = {round(weights['record_alignment'] * event_epa['record_alignment'], 4)}")
            print(f"    → Veteran Boost:   {round(event_epa['veteran_boost'], 3)} ({event_epa['years_experience']} years) × {weights['veteran']} = {round(weights['veteran'] * event_epa['veteran_boost'], 4)}")
            print(f"    → Dominance:       {round(event_epa['dominance'], 3)} × {weights['dominance']} = {round(weights['dominance'] * event_epa['dominance'], 4)}")
            print(f"    → Event Boost:     {round(event_epa['event_boost'], 3)} × {weights['events']} = {round(weights['events'] * event_epa['event_boost'], 4)}")
            print(f"    → Confidence Total: {round(event_epa['raw_confidence'], 4)} → Capped: {round(event_epa['confidence'], 3)}")
    else:
        print("\nNo event-specific EPA data found for this team.")

    # Calculate and print overall confidence breakdown
    if event_epa_results:
        weights = event_epa_results[0]["weights"]  # Weights are constant across events
        components = overall_epa_data["confidence_components"]
        
        print(f"\n{'='*50}")
        print("Overall Confidence Breakdown (Weighted Average)")
        print(f"{'='*50}")
        print(f"→ Consistency:     {round(overall_epa_data['avg_consistency'], 3)} × {weights['consistency']} = {round(components['consistency'], 4)}")
        print(f"→ Record Align:    {round(overall_epa_data['avg_record_alignment'], 3)} × {weights['record_alignment']} = {round(components['record'], 4)}")
        print(f"→ Veteran Boost:   {round(overall_epa_data['avg_veteran_boost'], 3)} × {weights['veteran']} = {round(components['veteran'], 4)}")
        print(f"→ Dominance:       {round(overall_epa_data['avg_dominance'], 3)} × {weights['dominance']} = {round(components['dominance'], 4)}")
        print(f"→ Event Boost:     {round(overall_epa_data['avg_event_boost'], 3)} × {weights['events']} = {round(components['event'], 4)}")
        print(f"→ Confidence Total: {round(components['raw'], 4)} → Capped: {round(overall_epa_data['confidence'], 3)}")

def main():
    print("\nEPA Calculator")
    print("="*20)
    
    mode = input("\nSelect mode:\n1. Single Team Analysis\n2. Process Entire JSON\nEnter choice (1 or 2): ").strip()
    
    if mode not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2.")
        return
        
    year = input("Enter year (e.g., 2025): ").strip()
    try:
        year = int(year)
    except ValueError:
        print("Invalid year. Please enter a valid year.")
        return
        
    if mode == '1':
        team_key = input("Enter team key (e.g., frc254): ").strip().lower()
        if not team_key.startswith('frc'):
            team_key = f"frc{team_key}"
        
        analyze_single_team(team_key, year)
        
    else:
        fetch_and_store_team_data(year)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Command-line mode
        mode = sys.argv[1]
        if mode == '1':
            # Single team analysis: python epa.py 1 2025 frc254
            if len(sys.argv) < 4:
                print("Usage: python epa.py 1 <year> <team_key>")
                sys.exit(1)
            try:
                year = int(sys.argv[2])
            except ValueError:
                print("Year must be an integer.")
                sys.exit(1)
            team_key = sys.argv[3].strip().lower()
            if not team_key.startswith('frc'):
                team_key = f"frc{team_key}"
            analyze_single_team(team_key, year)
        elif mode == '2':
            # Process all teams: python epa.py 2 2025
            if len(sys.argv) < 3:
                print("Usage: python epa.py 2 <year>")
                sys.exit(1)
            try:
                year = int(sys.argv[2])
            except ValueError:
                print("Year must be an integer.")
                sys.exit(1)
            fetch_and_store_team_data(year)
        else:
            print("Unknown mode. Use '1' for single team or '2' for all teams.")
            sys.exit(1)
    else:
        main()