import statistics
import json
import requests
import os
import math
import traceback
from datetime import datetime
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type, stop_after_attempt
from dotenv import load_dotenv
import random
from typing import Dict, List, Optional, Union
import psycopg2
from urllib.parse import urlparse

# Import year models
from yearmodels import *

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS").split(',')

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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_pg_connection():
    url = os.environ.get("DATABASE_URL")
    if url is None:
        raise Exception("DATABASE_URL not set in environment.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    result = urlparse(url)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        connect_timeout=30,
        options='-c statement_timeout=300000'
    )
    return conn

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_experience_pg(team_number, up_to_year):
    """Get team experience from PostgreSQL."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT year) 
        FROM team_epas 
        WHERE team_number = %s AND year <= %s
    """, (team_number, up_to_year))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result and result[0] else 1

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
def get_team_events(team_number, year):
    """Get all events a team participated in for a given year."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT event_key 
        FROM event_teams 
        WHERE team_number = %s AND event_key LIKE %s
        ORDER BY event_key
    """, (team_number, f"{year}%"))
    events = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return events

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"TBA API error for {endpoint}: {r.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout for {endpoint}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Request error for {endpoint}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error for {endpoint}: {e}")
        raise

def get_team_experience(team_number: int, up_to_year: int) -> int:
    """Determine how many years a team has competed up to and including up_to_year."""
    try:
        return get_team_experience_pg(team_number, up_to_year)
    except Exception as e:
        print(f"Failed to get team experience: {e}")
        return 1

def get_veteran_boost(years: int) -> float:
    """Calculate veteran boost based on years of experience."""
    if years <= 1:
        return 0.2
    elif years == 2:
        return 0.4
    elif years == 3:
        return 0.6
    else:
        return 1.0

def calculate_confidence(consistency: float, dominance: float, event_boost: float, team_number: int, wins: int = 0, losses: int = 0, year: int = None) -> tuple[float, float, float]:
    """Calculate confidence score using universal parameters."""
    years = get_team_experience(team_number, year) if year is not None else get_team_experience(team_number, 2025)
    veteran_boost = get_veteran_boost(years)
    
    # Calculate record alignment based on win-loss record
    total_matches = wins + losses
    if total_matches > 0:
        win_rate = wins / total_matches
        record_alignment = 0.7 + (win_rate * 0.3)
    else:
        record_alignment = 0.7
    
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

def calculate_event_epa(matches: List[Dict], team_key: str, team_number: int) -> Dict:
    """Calculate EPA for a team at a specific event."""
    try:
        importance = {"qm": 1.1, "qf": 1.0, "sf": 1.0, "f": 1.0}
        matches = sorted(matches, key=lambda m: m.get("time") or 0)

        if matches:
            print(f"EPA DEBUG: Processing team {team_key} for year {matches[0]['event_key'][:4]}")
        else:
            print(f"EPA DEBUG: Processing team {team_key} (no matches)")

        match_count = 0
        overall_epa = 0.0
        auto_epa = 0.0
        teleop_epa = 0.0
        endgame_epa = 0.0
        contributions, teammate_epas = [], []
        breakdowns = []
        dominance_scores = []
        event_wins = 0
        event_losses = 0
        event_ties = 0

        # Get the year from the first match's event key
        year = matches[0]["event_key"][:4] if matches else "2025"
        try:
            year_int = int(year)
        except Exception:
            year_int = 2025

        # Get the appropriate scoring functions for this year
        try:
            auto_func = globals()[f"auto_{year}"]
            teleop_func = globals()[f"teleop_{year}"]
            endgame_func = globals()[f"endgame_{year}"]
        except KeyError:
            auto_func = auto_2025
            teleop_func = teleop_2025
            endgame_func = endgame_2025

        for match in matches:
            if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                continue

            match_count += 1
            alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
            opponent_alliance = "blue" if alliance == "red" else "red"

            # Track wins/losses/ties
            if year == "2015":
                red_score = match["alliances"]["red"]["score"]
                blue_score = match["alliances"]["blue"]["score"]
                if alliance == "red":
                    if red_score > blue_score:
                        event_wins += 1
                    elif red_score < blue_score:
                        event_losses += 1
                    else:
                        event_ties += 1
                else:
                    if blue_score > red_score:
                        event_wins += 1
                    elif blue_score < red_score:
                        event_losses += 1
                    else:
                        event_ties += 1
            else:
                # Determine win/loss/tie based on scores instead of winning_alliance
                red_score = match["alliances"]["red"]["score"]
                blue_score = match["alliances"]["blue"]["score"]
                
                # Handle disqualifications (score of 0) as ties
                if red_score == 0 or blue_score == 0:
                    event_ties += 1
                elif alliance == "red":
                    if red_score > blue_score:
                        event_wins += 1
                    elif red_score < blue_score:
                        event_losses += 1
                    else:  # Equal scores = tie
                        event_ties += 1
                else:  # alliance == "blue"
                    if blue_score > red_score:
                        event_wins += 1
                    elif blue_score < red_score:
                        event_losses += 1
                    else:  # Equal scores = tie
                        event_ties += 1

            team_keys = match["alliances"][alliance].get("team_keys", [])
            team_count = len(team_keys)
            index = team_keys.index(team_key) + 1

            breakdown = match.get("score_breakdown", {})

            # Legacy years: no breakdown, use alliance score
            if breakdown is None and 1992 <= year_int <= 2014:
                auto = 0
                endgame = 0
                scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
                teleop = match["alliances"][alliance]["score"] * scaling_factor if team_count else 0
                actual_overall = teleop
                opponent_score = match["alliances"][opponent_alliance]["score"] * scaling_factor if team_count else 0
                margin = actual_overall - opponent_score
                scaled_margin = margin / (opponent_score + 1e-6)
                norm_margin = (scaled_margin + 1) / 1.3
                dominance_scores.append(min(1.0, max(0.0, norm_margin)))
                
                if auto_epa is None:
                    auto_epa = 0.0
                if teleop_epa is None:
                    teleop_epa = 0.0
                if endgame_epa is None:
                    endgame_epa = 0.0
                if overall_epa == 0.0 and auto_epa == 0.0 and teleop_epa == 0.0 and endgame_epa == 0.0:
                    overall_epa = actual_overall
                    auto_epa = auto
                    endgame_epa = endgame
                    teleop_epa = teleop
                    continue
                K = 0.4
                try:
                    delta_teleop = K * (teleop - teleop_epa)
                except Exception as e:
                    print(f"EPA DEBUG ERROR: teleop={teleop}, teleop_epa={teleop_epa}, match={match.get('key', 'unknown')}, error={e}")
                    teleop_epa = 0.0
                    delta_teleop = K * (teleop - teleop_epa)
                teleop_epa += delta_teleop
                overall_epa = teleop_epa
                contributions.append(actual_overall)
                continue

            # Modern years: use breakdown
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
            
            if auto_epa is None:
                auto_epa = 0.0
            if teleop_epa is None:
                teleop_epa = 0.0
            if endgame_epa is None:
                endgame_epa = 0.0
            try:
                actual_auto = auto_func(breakdowns, team_count)
                actual_teleop = teleop_func(breakdowns, team_count)
                if year == "2023" or year == "2017" or year == "2016":
                    actual_endgame = endgame_func(breakdowns, team_count)
                else:
                    actual_endgame = endgame_func(alliance_breakdown, index)
                actual_overall = actual_auto + actual_teleop + actual_endgame
                opponent_score = match["alliances"][opponent_alliance]["score"] / team_count
                margin = actual_overall - opponent_score
                scaled_margin = margin / (opponent_score + 1e-6)
                norm_margin = (scaled_margin + 1) / 1.3
                dominance_scores.append(min(1.0, max(0.0, norm_margin)))
                match_importance = importance.get(match.get("comp_level", "qm"), 1.0)
                decay = 1.0
                if overall_epa == 0.0 and auto_epa == 0.0 and teleop_epa == 0.0 and endgame_epa == 0.0:
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
                print(f"EPA DEBUG ERROR: Modern block, match={match.get('key', 'unknown')}, error={e}")

        if not match_count:
            return {
                "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
                "confidence": 0.0, "actual_epa": 0.0,
                "match_count": 0, "raw_confidence": 0.0,
                "consistency": 0.0, "dominance": 0.0,
                "event_boost": 0.0, "veteran_boost": 0.0,
                "years_experience": 0, "weights": {}, "record_alignment": 0.0,
                "wins": 0, "losses": 0, "ties": 0
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
            "losses": event_losses,
            "ties": event_ties
        }
    except Exception as e:
        print(f"EPA FATAL ERROR for team {team_key}: {e}")
        traceback.print_exc()
        print(f"Locals: {locals()}")
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "match_count": 0, "raw_confidence": 0.0,
            "consistency": 0.0, "dominance": 0.0,
            "event_boost": 0.0, "veteran_boost": 0.0,
            "years_experience": 0, "weights": {}, "record_alignment": 0.0,
            "wins": 0, "losses": 0, "ties": 0
        }

def aggregate_overall_epa(event_epas: List[Dict], year: int = None, team_number: int = None) -> Dict:
    """Aggregate EPA scores from multiple events into overall team EPA."""
    try:
        if not event_epas:
            return {
                "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
                "confidence": 0.0, "actual_epa": 0.0,
                "wins": 0, "losses": 0, "ties": 0
            }

        # Check if this is a demo team (9970-9999) - return zeroed overall stats
        if team_number is not None and 9970 <= team_number <= 9999:
            return {
                "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
                "confidence": 0.0, "actual_epa": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        # Filter out events with no valid matches or zero EPAs
        valid_events = [
            epa_data for epa_data in event_epas 
            if epa_data.get("match_count", 0) > 0 and (epa_data.get("overall", 0) or 0) > 0
        ]

        if not valid_events:
            return {
                "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
                "confidence": 0.0, "actual_epa": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        total_overall = 0.0
        total_auto = 0.0
        total_teleop = 0.0
        total_endgame = 0.0
        total_actual_epa = 0.0
        total_weighted_match_count = 0.0
        total_confidence = 0.0
        total_consistency = 0.0
        total_dominance = 0.0
        total_veteran_boost = 0.0
        total_event_boost = 0.0
        total_record_alignment = 0.0
        total_events = 0
        total_wins = 0
        total_losses = 0
        total_ties = 0

        # Use chronological weighting if available, otherwise fall back to match count weighting
        for epa_data in valid_events:
            match_count = epa_data.get("match_count", 0)
            if match_count == 0:
                continue
                
            # Get chronological weight if available
            chronological_weight = epa_data.get("chronological_weight", 1.0)
            event_type = epa_data.get("event_type", "unknown")
            
            # Calculate effective weight: chronological_weight * match_count
            effective_weight = chronological_weight * match_count
            
            # Fallback for NoneType values
            overall = epa_data.get("overall", 0.0) or 0.0
            auto = epa_data.get("auto", 0.0) or 0.0
            teleop = epa_data.get("teleop", 0.0) or 0.0
            endgame = epa_data.get("endgame", 0.0) or 0.0
            actual_epa = epa_data.get("actual_epa", 0.0) or 0.0
            confidence = epa_data.get("confidence", 0.0) or 0.0
            consistency = epa_data.get("consistency", 0.0) or 0.0
            dominance = epa_data.get("dominance", 0.0) or 0.0
            veteran_boost = epa_data.get("veteran_boost", 0.0) or 0.0
            event_boost = epa_data.get("event_boost", 0.0) or 0.0
            record_alignment = epa_data.get("record_alignment", 0.0) or 0.0
            wins = epa_data.get("wins", 0) or 0
            losses = epa_data.get("losses", 0) or 0
            ties = epa_data.get("ties", 0) or 0
            
            total_overall += overall * effective_weight
            total_auto += auto * effective_weight
            total_teleop += teleop * effective_weight
            total_endgame += endgame * effective_weight
            total_actual_epa += actual_epa * effective_weight
            total_weighted_match_count += effective_weight
            total_confidence += confidence * effective_weight
            total_consistency += consistency * effective_weight
            total_dominance += dominance * effective_weight
            total_veteran_boost += veteran_boost * effective_weight
            total_event_boost += event_boost * effective_weight
            total_record_alignment += record_alignment * effective_weight
            total_wins += wins
            total_losses += losses
            total_ties += ties
            total_events += 1

        if total_weighted_match_count == 0:
            return {
                "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
                "confidence": 0.0, "actual_epa": 0.0,
                "wins": 0, "losses": 0, "ties": 0,
                "confidence_components": {
                    "consistency": 0.0,
                    "record": 0.0,
                    "veteran": 0.0,
                    "dominance": 0.0,
                    "event": 0.0,
                    "raw": 0.0
                }
            }

        avg_confidence = total_confidence / total_weighted_match_count
        avg_consistency = total_consistency / total_weighted_match_count
        avg_dominance = total_dominance / total_weighted_match_count
        avg_veteran_boost = total_veteran_boost / total_weighted_match_count
        avg_event_boost = total_event_boost / total_weighted_match_count
        avg_record_alignment = total_record_alignment / total_weighted_match_count

        # Calculate the weighted components for display
        weights = valid_events[0].get("weights", {})
        consistency_component = weights.get("consistency", 0.0) * avg_consistency
        record_component = weights.get("record_alignment", 0.0) * avg_record_alignment
        veteran_component = weights.get("veteran", 0.0) * avg_veteran_boost
        dominance_component = weights.get("dominance", 0.0) * avg_dominance
        event_component = weights.get("events", 0.0) * avg_event_boost

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
            "overall": round(total_overall / total_weighted_match_count, 2),
            "auto": round(total_auto / total_weighted_match_count, 2),
            "teleop": round(total_teleop / total_weighted_match_count, 2),
            "endgame": round(total_endgame / total_weighted_match_count, 2),
            "confidence": round(final_confidence, 2),
            "actual_epa": round((total_overall / total_weighted_match_count) * final_confidence, 2),
            "wins": total_wins,
            "losses": total_losses,
            "ties": total_ties,
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
    except Exception as e:
        print(f"FATAL ERROR in aggregate_overall_epa: {e}")
        traceback.print_exc()
        print(f"Locals: {locals()}")
        return {
            "overall": 0.0, "auto": 0.0, "teleop": 0.0, "endgame": 0.0,
            "confidence": 0.0, "actual_epa": 0.0,
            "wins": 0, "losses": 0, "ties": 0,
            "confidence_components": {
                "consistency": 0.0,
                "record": 0.0,
                "veteran": 0.0,
                "dominance": 0.0,
                "event": 0.0,
                "raw": 0.0
            }
        }

def analyze_single_team(team_key: str, year: int):
    """Analyze EPA for a single team."""
    # Get team events from PostgreSQL
    team_number = int(team_key[3:])
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for event_key in event_keys:
        try:
            # Normal case - fetch matches directly for this team
            matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            
            if matches:
                # Calculate overall wins/losses/ties from matches
                for match in matches:
                    # Normal case - check the original team key
                    if team_key not in match["alliances"]["red"]["team_keys"] and team_key not in match["alliances"]["blue"]["team_keys"]:
                        continue
                    alliance = "red" if team_key in match["alliances"]["red"]["team_keys"] else "blue"
                    # 2015: Use scores, not winning_alliance
                    event_year = str(match["event_key"])[:4] if "event_key" in match else str(year)
                    if event_year == "2015":
                        red_score = match["alliances"]["red"]["score"]
                        blue_score = match["alliances"]["blue"]["score"]
                        if alliance == "red":
                            if red_score > blue_score:
                                total_wins += 1
                            elif red_score < blue_score:
                                total_losses += 1
                            else:
                                total_ties += 1
                        else:
                            if blue_score > red_score:
                                total_wins += 1
                            elif blue_score < red_score:
                                total_losses += 1
                            else:
                                total_ties += 1
                    else:
                        # Determine win/loss/tie based on scores instead of winning_alliance
                        red_score = match["alliances"]["red"]["score"]
                        blue_score = match["alliances"]["blue"]["score"]
                        
                        # Handle disqualifications (score of 0) as ties
                        if red_score == 0 or blue_score == 0:
                            total_ties += 1
                        elif alliance == "red":
                            if red_score > blue_score:
                                total_wins += 1
                            elif red_score < blue_score:
                                total_losses += 1
                            else:  # Equal scores = tie
                                total_ties += 1
                        else:  # alliance == "blue"
                            if blue_score > red_score:
                                total_wins += 1
                            elif blue_score < red_score:
                                total_losses += 1
                            else:  # Equal scores = tie
                                total_ties += 1

                event_epa = calculate_event_epa(matches, team_key, team_number)
                event_epa["event_key"] = event_key  # Ensure event_key is included
                event_epa_results.append(event_epa)
        except Exception as e:
            print(f"Failed to fetch matches for team {team_key} at event {event_key}: {e}")

    overall_epa_data = aggregate_overall_epa(event_epa_results, year, team_number)
    overall_epa_data["wins"] = total_wins
    overall_epa_data["losses"] = total_losses
    overall_epa_data["ties"] = total_ties

    print(f"\n{'='*50}")
    print(f"EPA Analysis for Team {team_key} ({year})")
    print(f"{'='*50}")
    print(f"\nOverall EPA: {overall_epa_data['overall']}")
    print(f"Overall Confidence: {overall_epa_data['confidence']}")
    print(f"Actual Overall EPA: {overall_epa_data['actual_epa']}")
    print(f"Overall Record: {overall_epa_data['wins']}-{overall_epa_data['losses']}-{overall_epa_data['ties']}")
    
    # Add note for demo teams
    if 9970 <= team_number <= 9999:
        print(f"\nNOTE: Team {team_number} is a demo team (9970-9999). Overall stats are zeroed out, but event-specific stats are retained below.")

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
            print(f"  Record: {event_epa['wins']}-{event_epa['losses']}-{event_epa['ties']}")
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
        
        # Add note for demo teams in confidence breakdown
        if 9970 <= team_number <= 9999:
            print("⚠️  NOTE: Overall confidence breakdown is zeroed for demo teams.")
        else:
            print(f"→ Consistency:     {round(overall_epa_data['avg_consistency'], 3)} × {weights['consistency']} = {round(components['consistency'], 4)}")
            print(f"→ Record Align:    {round(overall_epa_data['avg_record_alignment'], 3)} × {weights['record_alignment']} = {round(components['record'], 4)}")
            print(f"→ Veteran Boost:   {round(overall_epa_data['avg_veteran_boost'], 3)} × {weights['veteran']} = {round(components['veteran'], 4)}")
            print(f"→ Dominance:       {round(overall_epa_data['avg_dominance'], 3)} × {weights['dominance']} = {round(components['dominance'], 4)}")
            print(f"→ Event Boost:     {round(overall_epa_data['avg_event_boost'], 3)} × {weights['events']} = {round(components['event'], 4)}")
            print(f"→ Confidence Total: {round(components['raw'], 4)} → Capped: {round(overall_epa_data['confidence'], 3)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python single_team_analysis.py <year> <team_key>")
        print("Example: python single_team_analysis.py 2025 frc254")
        sys.exit(1)
    
    try:
        year = int(sys.argv[1])
    except ValueError:
        print("Year must be an integer.")
        sys.exit(1)
    
    team_key = sys.argv[2].strip().lower()
    if not team_key.startswith('frc'):
        team_key = f"frc{team_key}"
    
    analyze_single_team(team_key, year)
