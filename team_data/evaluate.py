import json
import statistics
from typing import Dict, List, Tuple
import math
from tqdm import tqdm
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os

def effective_epa(team_infos):
        if not team_infos:
            return 0
        
        weighted_epas = []
        for t in team_infos:
            epa = t["epa"]
            conf = t["confidence"]
            reliability = 1.0 * conf
            weighted_epas.append(epa)
        
        return np.mean(weighted_epas)
    
def predict_win_probability(red_info, blue_info):
    red_eff = effective_epa(red_info)
    blue_eff = effective_epa(blue_info)

    if red_eff + blue_eff == 0:
        return 0.5, 0.5

    diff = red_eff - blue_eff
    p_red = 1 / (1 + math.exp(-diff))
    return p_red, 1 - p_red


def load_team_epas(year: int) -> Dict[str, Dict]:
    """Load all team EPAs from the epa_teams.sqlite database for a specific year."""
    team_epas = {}
    try:
        conn = sqlite3.connect("epa_teams.sqlite")
        cursor = conn.cursor()
        
        # Debug: Print available tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\nAvailable tables in database: {[t[0] for t in tables]}")
        
        # Get all teams and their event EPAs for the specified year
        table_name = f"epa_{year}"
        print(f"\nAttempting to query table: {table_name}")
        
        cursor.execute(f"SELECT team_number, event_epas FROM {table_name}")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows in {table_name}")
        
        for team_number, event_epas_json in rows:
            try:
                event_epas = json.loads(event_epas_json)
                # Store event-specific EPAs with confidence
                team_epas[str(team_number)] = {
                    "event_epas": {
                        event["event_key"]: {
                            "epa": event["actual_epa"],
                            "confidence": event["confidence"]
                        } for event in event_epas
                    }
                }
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON for team {team_number}: {e}")
                continue
                
        conn.close()
        return team_epas
    except Exception as e:
        print(f"Error loading team EPAs for {year}: {e}")
        return {}

def get_matches_for_year(year: int) -> List[Dict]:
    """Get all matches for a specific year from the events.sqlite database."""
    matches = []
    try:
        conn = sqlite3.connect("../events.sqlite")
        cursor = conn.cursor()
        
        # Get all matches for the specified year
        cursor.execute("""
            SELECT k, rt, bt, rs, bs, cl 
            FROM m 
            WHERE k LIKE ?
        """, (f"{year}%",))
        
        for row in cursor.fetchall():
            match_key, red_teams, blue_teams, red_score, blue_score, comp_level = row
            
            # Skip matches with empty team lists
            if not red_teams or not blue_teams:
                continue
                
            try:
                # Parse team numbers from comma-separated strings, filtering out empty strings
                red_team_nums = [int(t) for t in red_teams.split(',') if t.strip()]
                blue_team_nums = [int(t) for t in blue_teams.split(',') if t.strip()]
                
                # Skip matches with no valid team numbers
                if not red_team_nums or not blue_team_nums:
                    continue
                
                matches.append({
                    "key": match_key,
                    "alliances": {
                        "red": {
                            "team_keys": [f"frc{num}" for num in red_team_nums],
                            "score": red_score
                        },
                        "blue": {
                            "team_keys": [f"frc{num}" for num in blue_team_nums],
                            "score": blue_score
                        }
                    },
                    "comp_level": comp_level
                })
            except ValueError:
                # Skip matches with invalid team numbers
                continue
            
        conn.close()
        return matches
    except Exception as e:
        print(f"Error loading matches for year {year}: {e}")
        return []

def predict_match_score(team_epas: Dict[str, Dict], match: Dict) -> Tuple[float, float, float, float]:
    """Predict the score for both alliances in a match using event-specific EPAs."""
    red_teams = match["alliances"]["red"]["team_keys"]
    blue_teams = match["alliances"]["blue"]["team_keys"]
    event_key = match["key"].split('_')[0]  # Extract event key from match key
    
    # Get event-specific EPA info for each team
    red_info = []
    for team in red_teams:
        team_num = team[3:]  # Remove "frc" prefix
        team_data = team_epas.get(team_num, {"event_epas": {}})
        if event_key in team_data["event_epas"]:
            red_info.append(team_data["event_epas"][event_key])
    
    blue_info = []
    for team in blue_teams:
        team_num = team[3:]  # Remove "frc" prefix
        team_data = team_epas.get(team_num, {"event_epas": {}})
        if event_key in team_data["event_epas"]:
            blue_info.append(team_data["event_epas"][event_key])
    
    # Calculate effective EPAs
    red_eff = effective_epa(red_info)
    blue_eff = effective_epa(blue_info)
    
    # Get win probabilities
    red_win_prob, blue_win_prob = predict_win_probability(red_info, blue_info)
    
    return red_eff, blue_eff, red_win_prob, blue_win_prob

def plot_prediction_accuracy(results: Dict, save_dir: str = "plots"):
    """Create plots to visualize EPA prediction accuracy."""
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Convert lists to numpy arrays and ensure they're all the same length
    min_length = min(len(results['score_errors']), 
                    len(results['actual_scores']), 
                    len(results['predicted_scores']), 
                    len(results['score_diffs']), 
                    len(results['correct_winners']), 
                    len(results['win_probs']), 
                    len(results['actual_wins']))
    
    score_errors = np.array(results['score_errors'][:min_length])
    actual_scores = np.array(results['actual_scores'][:min_length])
    predicted_scores = np.array(results['predicted_scores'][:min_length])
    score_diffs = np.array(results['score_diffs'][:min_length])
    correct_winners = np.array(results['correct_winners'][:min_length])
    win_probs = np.array(results['win_probs'][:min_length])
    actual_wins = np.array(results['actual_wins'][:min_length])
    
    # 1. Score Error Distribution
    plt.figure(figsize=(10, 6))
    plt.hist(score_errors, bins=50, alpha=0.7)
    plt.title('Distribution of Score Prediction Errors')
    plt.xlabel('Absolute Error (points)')
    plt.ylabel('Number of Matches')
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{save_dir}/score_error_dist_{timestamp}.png")
    plt.close()
    
    # 2. Predicted vs Actual Scores
    plt.figure(figsize=(10, 6))
    plt.scatter(actual_scores, predicted_scores, alpha=0.5)
    max_score = max(np.max(actual_scores), np.max(predicted_scores))
    plt.plot([0, max_score], [0, max_score], 'r--')
    plt.title('Predicted vs Actual Scores')
    plt.xlabel('Actual Score')
    plt.ylabel('Predicted Score')
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{save_dir}/predicted_vs_actual_{timestamp}.png")
    plt.close()
    
    # 3. Error by Score Range
    score_ranges = [(0, 50), (51, 100), (101, 150), (151, 200), (201, float('inf'))]
    range_errors = []
    range_counts = []
    
    for low, high in score_ranges:
        mask = (actual_scores >= low) & (actual_scores < high)
        if np.any(mask):
            range_errors.append(np.mean(score_errors[mask]))
            range_counts.append(np.sum(mask))
    
    if range_errors:  # Only plot if we have data
        plt.figure(figsize=(10, 6))
        x = [f"{low}-{high if high != float('inf') else '+'}" for low, high in score_ranges[:len(range_errors)]]
        plt.bar(x, range_errors)
        plt.title('Average Error by Score Range')
        plt.xlabel('Score Range')
        plt.ylabel('Mean Absolute Error')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{save_dir}/error_by_range_{timestamp}.png")
        plt.close()
    
    # 4. Winner Prediction Accuracy by Score Difference
    diff_ranges = [(0, 10), (11, 20), (21, 30), (31, 40), (41, float('inf'))]
    diff_accuracies = []
    diff_counts = []
    
    for low, high in diff_ranges:
        mask = (score_diffs >= low) & (score_diffs < high)
        if np.any(mask):
            diff_accuracies.append(np.mean(correct_winners[mask]))
            diff_counts.append(np.sum(mask))
    
    if diff_accuracies:  # Only plot if we have data
        plt.figure(figsize=(10, 6))
        x = [f"{low}-{high if high != float('inf') else '+'}" for low, high in diff_ranges[:len(diff_accuracies)]]
        plt.bar(x, diff_accuracies)
        plt.title('Winner Prediction Accuracy by Score Difference')
        plt.xlabel('Score Difference Range')
        plt.ylabel('Accuracy')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{save_dir}/accuracy_by_diff_{timestamp}.png")
        plt.close()
    
    # 5. Win Probability Calibration
    prob_ranges = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    actual_probs = []
    predicted_probs = []
    
    for low, high in prob_ranges:
        mask = (win_probs >= low) & (win_probs < high)
        if np.any(mask):
            actual_probs.append(np.mean(actual_wins[mask]))
            predicted_probs.append((low + high) / 2)
    
    if actual_probs and predicted_probs:  # Only plot if we have data
        plt.figure(figsize=(10, 6))
        plt.scatter(predicted_probs, actual_probs)
        plt.plot([0, 1], [0, 1], 'r--')
        plt.title('Win Probability Calibration')
        plt.xlabel('Predicted Win Probability')
        plt.ylabel('Actual Win Rate')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{save_dir}/win_prob_calibration_{timestamp}.png")
        plt.close()

def evaluate_predictions(team_epas: Dict[str, Dict], matches: List[Dict], year: int) -> Dict:
    """Evaluate the EPA model's predictive performance."""
    # Metrics
    total_matches = 0
    correct_winners = []
    score_errors = []
    red_score_errors = []
    blue_score_errors = []
    matches_with_missing_epas = 0
    actual_scores = []
    predicted_scores = []
    score_diffs = []
    win_probs = []
    actual_wins = []
    
    print(f"\nEvaluating EPA predictions for {year} matches...")
    print(f"Number of teams with EPA data: {len(team_epas)}")
    
    # Debug: Print first few team numbers with EPA data
    if team_epas:
        print("Sample team numbers with EPA data:", list(team_epas.keys())[:5])
    
    # Track statistics about skipped matches
    skipped_matches = {
        "invalid_teams": 0,
        "missing_epas": 0,
        "no_scores": 0,
        "non_qual": 0
    }
    
    # Process matches without tqdm
    total_matches_to_process = len(matches)
    for i, match in enumerate(matches):
        # Print progress every 1000 matches
        if i % 1000 == 0:
            print(f"Processing match {i}/{total_matches_to_process}...")
            
        # Skip non-qualification matches
        if match["comp_level"] != "qm":
            skipped_matches["non_qual"] += 1
            continue
            
        # Skip matches without scores
        if not match["alliances"]["red"]["score"] or not match["alliances"]["blue"]["score"]:
            skipped_matches["no_scores"] += 1
            continue
            
        # Check if we have EPAs for all teams in this match
        event_key = match["key"].split('_')[0]
        all_teams_have_epa = True
        missing_teams = []
        invalid_teams = []
        
        # Check both alliances
        for alliance in ["red", "blue"]:
            for team in match["alliances"][alliance]["team_keys"]:
                team_num = team[3:]  # Remove "frc" prefix
                
                # Skip invalid team numbers (0, 9999, etc.)
                if team_num in ['0', '9999', '9998', '9997', '9996', '9995', '9994', '9993']:
                    invalid_teams.append(team_num)
                    all_teams_have_epa = False
                    continue
                
                # Check if team has EPA data for this event
                if event_key not in team_epas.get(team_num, {"event_epas": {}})["event_epas"]:
                    missing_teams.append(team_num)
                    all_teams_have_epa = False
        
        if invalid_teams:
            skipped_matches["invalid_teams"] += 1
            if skipped_matches["invalid_teams"] <= 5:  # Only print first 5 cases
                print(f"Skipping match with invalid team numbers: {invalid_teams}")
            continue
            
        if not all_teams_have_epa:
            skipped_matches["missing_epas"] += 1
            if skipped_matches["missing_epas"] <= 5:  # Only print first 5 cases
                print(f"Missing EPA data for teams {missing_teams} in event {event_key}")
            continue
            
        total_matches += 1
        
        # Get actual scores
        red_actual = match["alliances"]["red"]["score"]
        blue_actual = match["alliances"]["blue"]["score"]
        
        # Get predicted scores and win probabilities
        red_pred, blue_pred, red_win_prob, blue_win_prob = predict_match_score(team_epas, match)
        
        # Calculate errors
        red_error = abs(red_pred - red_actual)
        blue_error = abs(blue_pred - blue_actual)
        total_error = red_error + blue_error
        score_errors.append(total_error)
        red_score_errors.append(red_error)
        blue_score_errors.append(blue_error)
        
        # Store scores for plotting
        actual_scores.append((red_actual + blue_actual) / 2)  # Average score per match
        predicted_scores.append((red_pred + blue_pred) / 2)   # Average predicted score per match
        
        # Calculate score difference
        score_diff = abs(red_actual - blue_actual)
        score_diffs.append(score_diff)
        
        # Store win probability and actual result
        win_probs.append(red_win_prob)
        actual_wins.append(red_actual > blue_actual)
        
        # Check if winner prediction was correct
        correct_winner = (red_pred > blue_pred and red_actual > blue_actual) or \
                        (red_pred < blue_pred and red_actual < blue_actual) or \
                        (red_pred == blue_pred and red_actual == blue_actual)
        correct_winners.append(correct_winner)
    
    # Print match filtering statistics
    print("\nMatch Filtering Statistics:")
    print(f"Total matches processed: {len(matches)}")
    print(f"Non-qualification matches skipped: {skipped_matches['non_qual']}")
    print(f"Matches without scores skipped: {skipped_matches['no_scores']}")
    print(f"Matches with invalid team numbers skipped: {skipped_matches['invalid_teams']}")
    print(f"Matches with missing EPA data skipped: {skipped_matches['missing_epas']}")
    print(f"Matches used for evaluation: {total_matches}")
    
    if total_matches == 0:
        return {
            "total_matches": 0,
            "accuracy": 0.0,
            "mae": 0.0,
            "rmse": 0.0,
            "red_mae": 0.0,
            "blue_mae": 0.0,
            "matches_with_missing_epas": matches_with_missing_epas
        }
    
    # Calculate metrics
    accuracy = sum(correct_winners) / total_matches
    mae = statistics.mean(score_errors)
    rmse = math.sqrt(statistics.mean([e * e for e in score_errors]))
    red_mae = statistics.mean(red_score_errors)
    blue_mae = statistics.mean(blue_score_errors)
    
    # Create plots
    plot_data = {
        "score_errors": score_errors,
        "actual_scores": actual_scores,
        "predicted_scores": predicted_scores,
        "score_diffs": score_diffs,
        "correct_winners": correct_winners,
        "win_probs": win_probs,
        "actual_wins": actual_wins
    }
    plot_prediction_accuracy(plot_data)
    
    return {
        "total_matches": total_matches,
        "accuracy": accuracy,
        "mae": mae,
        "rmse": rmse,
        "red_mae": red_mae,
        "blue_mae": blue_mae,
        "matches_with_missing_epas": matches_with_missing_epas
    }

def evaluate_year(year: int) -> Dict:
    """Evaluate EPA predictions for a specific year."""
    try:
        print(f"\nLoading team EPAs for {year}...")
        team_epas = load_team_epas(year)
        
        if not team_epas:
            print(f"No EPA data found for {year}")
            return None
        
        print(f"Loaded EPAs for {len(team_epas)} teams")
        
        print(f"\nLoading matches for {year}...")
        matches = get_matches_for_year(year)
        
        if not matches:
            print(f"No matches found for {year}")
            return None
            
        print(f"Loaded {len(matches)} matches for {year}")
        
        results = evaluate_predictions(team_epas, matches, year)
        
        if results["total_matches"] == 0:
            print(f"No valid matches to evaluate for {year}")
            return None
            
        print(f"\nEPA Model Evaluation Results for {year}")
        print("="*40)
        print(f"Total Matches Evaluated: {results['total_matches']}")
        print(f"Matches Skipped (Missing EPAs): {results['matches_with_missing_epas']}")
        print(f"Winner Prediction Accuracy: {results['accuracy']:.2%}")
        print(f"Mean Absolute Error (Total Score): {results['mae']:.2f} points")
        print(f"Root Mean Square Error: {results['rmse']:.2f} points")
        print(f"Red Alliance MAE: {results['red_mae']:.2f} points")
        print(f"Blue Alliance MAE: {results['blue_mae']:.2f} points")
        print(f"\nPlots have been saved to the 'plots' directory")
        
        return results
        
    except Exception as e:
        print(f"Error evaluating year {year}: {str(e)}")
        return None

def main():
    while True:
        print("\nEPA Evaluation Options:")
        print("1. Evaluate single year")
        print("2. Evaluate year range")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            try:
                year = int(input("Enter year to evaluate (e.g., 2025): ").strip())
                result = evaluate_year(year)
                if result is None:
                    print(f"Could not evaluate year {year}.")
            except ValueError:
                print("Invalid year format. Please enter a valid year number.")
                
        elif choice == "2":
            try:
                start_year = int(input("Enter start year: ").strip())
                end_year = int(input("Enter end year: ").strip())
                
                if start_year > end_year:
                    print("Start year must be less than or equal to end year.")
                    continue
                    
                for year in range(start_year, end_year + 1):
                    result = evaluate_year(year)
                    if result is None:
                        print(f"Could not evaluate year {year}.")
                    
            except ValueError:
                print("Invalid year format. Please enter valid year numbers.")
                
        elif choice == "3":
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main() 