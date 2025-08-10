#!/usr/bin/env python3
"""
Single Team EPA Analysis Module

This module provides functionality to analyze a single team's EPA data.
It imports necessary functions from the main run.py file to avoid code duplication.
"""

from run import (
    get_team_events,
    detect_b_bot_mapping,
    tba_get,
    calculate_event_epa,
    aggregate_overall_epa
)


def analyze_single_team(team_key: str, year: int):
    """
    Analyze EPA data for a single team.
    
    Args:
        team_key (str): The team key (e.g., 'frc254')
        year (int): The competition year
        
    Returns:
        dict: Analysis results containing EPA data and statistics
    """
    # Get team events from PostgreSQL
    team_number = int(team_key[3:])
    event_keys = get_team_events(team_number, year)

    event_epa_results = []
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for event_key in event_keys:
        try:
            # Check if this is a B bot that needs special handling
            b_bot_mapping = detect_b_bot_mapping(event_key, team_number)
            
            if b_bot_mapping:
                # This is a California event with B bot mapping issues
                # Fetch all matches from the event and filter for this team
                all_matches = tba_get(f"event/{event_key}/matches")
                if all_matches:
                    # Find which base number this B bot maps to
                    # Get all B bot team keys from the event teams
                    event_teams = tba_get(f"event/{event_key}/teams")
                    b_bots_in_event = [t for t in event_teams if 9970 <= t.get("team_number", 0) <= 9999]
                    
                    # Sort B bots by team number to get consistent mapping
                    b_bots_in_event.sort(key=lambda x: x.get("team_number", 0))
                    
                    # Find this team's position in the sorted list
                    team_position = None
                    for i, bot in enumerate(b_bots_in_event):
                        if bot.get("team_number") == team_number:
                            team_position = i
                            break
                    
                    if team_position is not None and team_position < len(b_bot_mapping):
                        # Get the corresponding base number and B bot key
                        base_numbers = sorted(b_bot_mapping.keys())
                        if team_position < len(base_numbers):
                            base_num = base_numbers[team_position]
                            b_bot_key = b_bot_mapping[base_num]
                            
                            # Filter matches to only include those where this B bot appears
                            matches = []
                            for match in all_matches:
                                for alliance in ["red", "blue"]:
                                    if b_bot_key in match["alliances"][alliance]["team_keys"]:
                                        matches.append(match)
                                        break
                        else:
                            matches = []
                    else:
                        matches = []
                else:
                    matches = []
            else:
                # Normal case - fetch matches directly for this team
                matches = tba_get(f"team/{team_key}/event/{event_key}/matches")
            
            if matches:
                # Calculate overall wins/losses/ties from matches
                for match in matches:
                    # For B bots in California events, we need to check the B bot key, not the original team key
                    if b_bot_mapping:
                        # Find the B bot key for this team
                        event_teams = tba_get(f"event/{event_key}/teams")
                        b_bots_in_event = [t for t in event_teams if 9970 <= t.get("team_number", 0) <= 9999]
                        b_bots_in_event.sort(key=lambda x: x.get("team_number", 0))
                        
                        team_position = None
                        for i, bot in enumerate(b_bots_in_event):
                            if bot.get("team_number") == team_number:
                                team_position = i
                                break
                        
                        if team_position is not None:
                            base_numbers = sorted(b_bot_mapping.keys())
                            if team_position < len(base_numbers):
                                base_num = base_numbers[team_position]
                                b_bot_key = b_bot_mapping[base_num]
                                
                                # Check if the B bot key is in the alliances
                                if b_bot_key not in match["alliances"]["red"]["team_keys"] and b_bot_key not in match["alliances"]["blue"]["team_keys"]:
                                    continue
                                alliance = "red" if b_bot_key in match["alliances"]["red"]["team_keys"] else "blue"
                            else:
                                continue
                    else:
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
                        winning_alliance = match.get("winning_alliance", "")
                        if winning_alliance == alliance:
                            total_wins += 1
                        elif winning_alliance and winning_alliance != alliance:
                            total_losses += 1
                        elif not winning_alliance:  # Tie
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

    # Print analysis results
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
            print("NOTE: Overall confidence breakdown is zeroed for demo teams.")
        else:
            print(f"→ Consistency:     {round(overall_epa_data['avg_consistency'], 3)} × {weights['consistency']} = {round(components['consistency'], 4)}")
            print(f"→ Record Align:    {round(overall_epa_data['avg_record_alignment'], 3)} × {weights['record_alignment']} = {round(components['record'], 4)}")
            print(f"→ Veteran Boost:   {round(overall_epa_data['avg_veteran_boost'], 3)} × {weights['veteran']} = {round(components['veteran'], 4)}")
            print(f"→ Dominance:       {round(overall_epa_data['avg_dominance'], 3)} × {weights['dominance']} = {round(components['dominance'], 4)}")
            print(f"→ Event Boost:     {round(overall_epa_data['avg_event_boost'], 3)} × {weights['events']} = {round(components['event'], 4)}")
            print(f"→ Confidence Total: {round(components['raw'], 4)} → Capped: {round(overall_epa_data['confidence'], 3)}")

    # Return the analysis results for programmatic use
    return {
        "team_key": team_key,
        "team_number": team_number,
        "year": year,
        "overall_epa_data": overall_epa_data,
        "event_epa_results": event_epa_results,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_ties": total_ties
    }


def main():
    """
    Main function to run single team analysis from command line.
    
    Usage:
        python analyze_single_team.py <team_key> <year>
        
    Example:
        python analyze_single_team.py frc254 2024
    """
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python analyze_single_team.py <team_key> <year>")
        print("Example: python analyze_single_team.py frc254 2024")
        sys.exit(1)
    
    team_key = sys.argv[1]
    try:
        year = int(sys.argv[2])
    except ValueError:
        print("Error: Year must be a valid integer")
        sys.exit(1)
    
    # Validate team key format
    if not team_key.startswith('frc') or not team_key[3:].isdigit():
        print("Error: Team key must be in format 'frc<number>' (e.g., 'frc254')")
        sys.exit(1)
    
    try:
        result = analyze_single_team(team_key, year)
        print(f"\nAnalysis complete for team {team_key} in {year}")
    except Exception as e:
        print(f"Error analyzing team {team_key}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
