import statistics
import math

def auto_2025(breakdowns, team_count):
    def score_per_breakdown(b):
        reef = b.get("autoReef", {})
        trough = reef.get("trough", 0)
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        coral_score = trough * 3 + bot * 4 + mid * 6 + top * 7
        mobility = b.get("autoMobilityPoints", 0)
        
        # Scale entire contribution based on alliance size
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (mobility + coral_score) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in teleop
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)


def teleop_2025(breakdowns, team_count):
    def score_per_breakdown(b):
        reef = b.get("teleopReef", {})
        bot = reef.get("tba_botRowCount", 0)
        mid = reef.get("tba_midRowCount", 0)
        top = reef.get("tba_topRowCount", 0)
        trough = reef.get("trough", 0)
        net = b.get("netAlgaeCount", 0)
        processor = b.get("wallAlgaeCount", 0)
        estimated_teleop = (bot * 3 + mid * 4 + top * 5 + trough * 2 + net * 4 + processor * 2.5)
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return estimated_teleop * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Smoothed trimming based on match count
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]  # trim from low-end only

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2025(breakdown, index):
    robot_endgame = breakdown.get(f"endGameRobot{index}", "None")
    actual_endgame = {"DeepCage": 12, "ShallowCage": 6, "Parked": 2}.get(robot_endgame, 0)

    return actual_endgame

def auto_2024(breakdowns, team_count):
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

def teleop_2024(breakdowns, team_count):
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

def endgame_2024(breakdown, team_count):
    if not breakdown:
        return 0

    park_points = breakdown.get("endGameParkPoints", 0)
    onstage_points = breakdown.get("endGameOnStagePoints", 0)
    spotlight_points = breakdown.get("endGameSpotLightBonusPoints", 0)
    harmony_points = breakdown.get("endGameHarmonyPoints", 0)
    trap_points = breakdown.get("endGameNoteInTrapPoints", 0)

    return park_points + onstage_points + spotlight_points + harmony_points + trap_points / team_count

def auto_2023(breakdowns, team_count):
    leave_points = []
    scored_rows = {"B": 3, "M": 4, "T": 6}

    for b in breakdowns:
        # Mobility (3 pts per Yes)
        mobility = sum(1 for i in range(1, 4) if b.get(f"mobilityRobot{i}") == "Yes") * 3
        leave_points.append(mobility)

    median_mobility = statistics.median(leave_points) if leave_points else 0

    # Estimate speaker scoring (less reliable, but balanced)
    game_piece_scores = []
    for b in breakdowns:
        score = 0
        auto_comm = b.get("autoCommunity", {})
        for row, row_vals in auto_comm.items():
            row_score = scored_rows.get(row, 0)
            score += sum(1 for v in row_vals if v != "None") * row_score
        game_piece_scores.append(score)

    median_auto_score = statistics.median(game_piece_scores) if game_piece_scores else 0

    estimated_auto = (median_mobility + (median_auto_score / team_count))
    return estimated_auto

def teleop_2023(breakdowns, team_count):
    game_piece_scores = []
    scored_rows = {"B": 2, "M": 3, "T": 5}

    for b in breakdowns:
        score = 0
        teleop_comm = b.get("teleopCommunity", {})
        for row, cells in teleop_comm.items():
            row_score = scored_rows.get(row, 0)
            score += sum(1 for val in cells if val != "None") * row_score
        game_piece_scores.append(score)

    median_teleop_score = statistics.median(game_piece_scores) if game_piece_scores else 0
    estimated_teleop = median_teleop_score / team_count
    return estimated_teleop

def endgame_2023(breakdowns, team_count):
    charge_scores = []
    
    for b in breakdowns:
        score = 0
        for i in range(1, 4):
            state = b.get(f"endGameChargeStationRobot{i}", "None")
            if state == "Docked":
                score += 6
            elif state == "Engaged":
                score += 10
            elif state == "Park":
                score += 2
        charge_scores.append(score)

    median_charge_score = statistics.median(charge_scores) if charge_scores else 0
    estimated_endgame = median_charge_score / team_count
    return estimated_endgame

def auto_2022(breakdowns, team_count):
    def score_per_breakdown(b):
        # 2022 Auto Scoring
        # autoTaxiPoints is typically 6 if all taxis succeed
        auto_taxi = b.get("autoTaxiPoints", 0)
        
        # Sum cargo from all sources (near, far, blue, red) for lower and upper hubs
        auto_cargo_lower = b.get("autoCargoLowerNear", 0) + b.get("autoCargoLowerFar", 0) + b.get("autoCargoLowerBlue", 0) + b.get("autoCargoLowerRed", 0)
        auto_cargo_upper = b.get("autoCargoUpperNear", 0) + b.get("autoCargoUpperFar", 0) + b.get("autoCargoUpperBlue", 0) + b.get("autoCargoUpperRed", 0)
        
        # Points per cargo: Lower = 2, Upper = 4
        auto_cargo_points = (auto_cargo_lower * 2) + (auto_cargo_upper * 4)

        # Total Auto points for the alliance from scoring actions
        # Note: autoPoints field in API breakdown already sums these, but calculating explicitly mirrors rules
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (auto_taxi + auto_cargo_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in teleop
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2022(breakdowns, team_count):
    def score_per_breakdown(b):
        # 2022 Teleop Scoring
        # Sum cargo from all sources (near, far, blue, red) for lower and upper hubs
        teleop_cargo_lower = b.get("teleopCargoLowerNear", 0) + b.get("teleopCargoLowerFar", 0) + b.get("teleopCargoLowerBlue", 0) + b.get("teleopCargoLowerRed", 0)
        teleop_cargo_upper = b.get("teleopCargoUpperNear", 0) + b.get("teleopCargoUpperFar", 0) + b.get("teleopCargoUpperBlue", 0) + b.get("teleopCargoUpperRed", 0)

        # Points per cargo: Lower = 1, Upper = 2
        teleop_cargo_points = (teleop_cargo_lower * 1) + (teleop_cargo_upper * 2)

        # Total Teleop points for the alliance from scoring actions
        # Note: teleopCargoPoints field in API breakdown already sums these, but calculating explicitly mirrors rules
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return teleop_cargo_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Smoothed trimming based on match count
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]  # trim from low-end only

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2022(breakdowns, team_count):
    """Calculate endgame score for 2022 matches."""
    def score_per_breakdown(b):
        # Get endgame status for each robot
        endgame_scores = []
        for i in range(1, 4):  # Check all three robots
            robot_endgame_status = b.get(f"endgameRobot{i}", "None")
            # Use 2022 scoring values
            score = {"Low": 4, "Mid": 6, "High": 10, "Traversal": 15, "None": 0}.get(robot_endgame_status, 0)
            endgame_scores.append(score)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return sum(endgame_scores) * scaling_factor

    # Handle single breakdown case (for individual robot)
    if isinstance(breakdowns, dict):
        return score_per_breakdown(breakdowns)

    # Handle list of breakdowns case (for alliance)
    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2021(breakdowns, team_count):
    """Calculate auto score for 2020 matches."""
    def score_per_breakdown(b):
        # Get auto points directly from breakdown
        auto_points = b.get("autoPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return auto_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2021(breakdowns, team_count):
    """Calculate teleop score for 2020 matches."""
    def score_per_breakdown(b):
        # Calculate teleop points by subtracting endgame from total teleop
        teleop_points = b.get("teleopPoints", 0) - b.get("endgamePoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return teleop_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2021(breakdowns, team_count):
    """Calculate endgame score for 2020 matches."""
    def score_per_breakdown(b):
        # Get endgame points directly from breakdown
        endgame_points = b.get("endgamePoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return endgame_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2020(breakdowns, team_count):
    """Calculate auto score for 2020 matches."""
    def score_per_breakdown(b):
        # Get auto points directly from breakdown
        auto_points = b.get("autoPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return auto_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2020(breakdowns, team_count):
    """Calculate teleop score for 2020 matches."""
    def score_per_breakdown(b):
        # Calculate teleop points by subtracting endgame from total teleop
        teleop_points = b.get("teleopPoints", 0) - b.get("endgamePoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return teleop_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2020(breakdowns, team_count):
    """Calculate endgame score for 2020 matches."""
    def score_per_breakdown(b):
        # Get endgame points directly from breakdown
        endgame_points = b.get("endgamePoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return endgame_points * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2019(breakdowns, team_count):
    """Calculate auto score for 2019 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2019 Auto Scoring: Sandstorm Bonus + Cargo Ship/Rocket Level 1 Scoring
        sandstorm_bonus = b.get("sandStormBonusPoints", 0)
        auto_scored_points = b.get("autoPoints", 0) - sandstorm_bonus
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (sandstorm_bonus + auto_scored_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2019(breakdowns, team_count):
    """Calculate teleop score for 2019 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2019 Teleop Scoring: Cargo Ship and Rocket (all levels) Scoring
        cargo_ship_points = 0
        for i in range(1, 9):
            bay_status = b.get(f"bay{i}", "None")
            if bay_status == "Panel": cargo_ship_points += 2
            if bay_status == "Cargo": cargo_ship_points += 3
            if bay_status == "PanelAndCargo": cargo_ship_points += 2 + 3

        rocket_points = 0
        for level in ["low", "mid", "top"]:
            for side in ["Left", "Right"]:
                for location in ["Near", "Far"]:
                    rocket_status = b.get(f"{level}{side}Rocket{location}", "None")
                    if rocket_status == "Panel": rocket_points += 2
                    if rocket_status == "Cargo": rocket_points += 3
                    if rocket_status == "PanelAndCargo": rocket_points += 2 + 3

        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (cargo_ship_points + rocket_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2019(breakdowns, team_count):
    """Calculate endgame score for 2019 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # Get HAB climb points directly from the breakdown
        hab_climb_points = b.get("habClimbPoints", 0)
        
        # If we don't have habClimbPoints, calculate from individual robot statuses
        if hab_climb_points == 0:
            endgame_scores = []
            for i in range(1, 4):  # Check all three robots
                robot_endgame_status = b.get(f"endgameRobot{i}", "None")
                # Use 2019 HAB Climb scoring values
                score = {"HabLevel1": 3, "HabLevel2": 6, "HabLevel3": 12, "None": 0}.get(robot_endgame_status, 0)
                endgame_scores.append(score)
            hab_climb_points = sum(endgame_scores)
        
        # For endgame, we don't scale by team count since HAB climbs are individual achievements
        # But we do need to divide by 3 since the points are for the entire alliance
        return hab_climb_points / 3

    # Handle single breakdown case (for individual robot)
    if isinstance(breakdowns, dict):
        return score_per_breakdown(breakdowns)

    # Handle list of breakdowns case (for alliance)
    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2018(breakdowns, team_count):
    """Calculate auto score for 2018 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2018 Auto Scoring: Ownership Points + Run Points
        auto_ownership = b.get("autoOwnershipPoints", 0)
        auto_run = b.get("autoRunPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (auto_ownership + auto_run) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2018(breakdowns, team_count):
    """Calculate teleop score for 2018 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2018 Teleop Scoring: Ownership Points + Vault Points
        teleop_ownership = b.get("teleopOwnershipPoints", 0)
        vault_points = b.get("vaultPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (teleop_ownership + vault_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2018(breakdowns, team_count):
    """Calculate endgame score for 2018 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2018 Endgame Scoring: Endgame Points + Face The Boss Bonus
        endgame_points = b.get("endgamePoints", 0)
        face_the_boss = 5 if b.get("faceTheBossRankingPoint", False) else 0
        
        # For endgame, we don't scale by team count since these are alliance achievements
        return endgame_points + face_the_boss

    # Handle single breakdown case (for individual robot)
    if isinstance(breakdowns, dict):
        return score_per_breakdown(breakdowns)

    # Handle list of breakdowns case (for alliance)
    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2017(breakdowns, team_count):
    """Calculate auto score for 2017 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2017 Auto Scoring: Mobility + Rotor + Fuel Points
        mobility_points = b.get("autoMobilityPoints", 0)
        rotor_points = b.get("autoRotorPoints", 0)
        fuel_points = b.get("autoFuelPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (mobility_points + rotor_points + fuel_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2017(breakdowns, team_count):
    """Calculate teleop score for 2017 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2017 Teleop Scoring: Rotor + Fuel Points
        rotor_points = b.get("teleopRotorPoints", 0)
        fuel_points = b.get("teleopFuelPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (rotor_points + fuel_points) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2017(breakdowns, team_count):
    """Calculate endgame score for 2017 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2017 Endgame Scoring: Takeoff Points
        takeoff_points = b.get("teleopTakeoffPoints", 0)
        
        # Divide by team count for per-team contribution, and apply 0.5 scaling
        # based on user feedback that score is consistently too high by factor of 2
        return (takeoff_points / team_count) * 0.5

    # Handle single breakdown case (for individual robot)
    if isinstance(breakdowns, dict):
        # For a single breakdown (e.g., from an individual robot's perspective, if applicable),
        # we still divide by team_count to normalize it as a team's contribution to the alliance's score
        return score_per_breakdown(breakdowns)

    # Handle list of breakdowns case (for alliance)
    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2016(breakdowns, team_count):
    """Calculate auto score for 2016 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2016 Auto Scoring: Boulder Points + Crossing Points
        auto_boulders = b.get("autoBoulderPoints", 0)
        auto_crossing = b.get("autoCrossingPoints", 0)
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (auto_boulders + auto_crossing) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def teleop_2016(breakdowns, team_count):
    """Calculate teleop score for 2016 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2016 Teleop Scoring: Boulder Points + Crossing Points + Breach Bonus
        teleop_boulders = b.get("teleopBoulderPoints", 0)
        teleop_crossing = b.get("teleopCrossingPoints", 0)
        
        # Breach points are applied per alliance and then divided per team in epa2016.py
        breach_bonus = 20 if b.get("breachPoints", 0) else 0
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (teleop_boulders + teleop_crossing + breach_bonus / team_count) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def endgame_2016(breakdowns, team_count):
    """Calculate endgame score for 2016 matches."""
    def score_per_breakdown(b):
        if not isinstance(b, dict):
            return 0
            
        # 2016 Endgame Scoring: Challenge Points + Scale Points + Capture Bonus
        teleop_challenge = b.get("teleopChallengePoints", 0)
        teleop_scale = b.get("teleopScalePoints", 0)
        
        # Capture points are applied per alliance and then divided per team in epa2016.py
        capture_bonus = 25 if b.get("capturePoints", 0) else 0
        
        # Scale based on team count
        scaling_factor = 1 / (1 + math.log(team_count)) if team_count > 1 else 1.0
        return (teleop_challenge + teleop_scale + capture_bonus / team_count) * scaling_factor

    scores = [score_per_breakdown(b) for b in breakdowns]
    n = len(scores)

    if n < 6:
        return round(statistics.mean(scores), 2)

    # Trim low outliers like in other functions
    if n < 12:
        trim_pct = 0.0
    elif n < 25:
        trim_pct = 0.03
    elif n < 40:
        trim_pct = 0.05
    elif n < 60:
        trim_pct = 0.08
    elif n < 100:
        trim_pct = 0.1
    else:
        trim_pct = 0.12

    k = int(n * trim_pct)
    trimmed_scores = sorted(scores)[k:]

    return round(statistics.mean(trimmed_scores), 2)

def auto_2015(breakdowns, team_count):
    # Use the API's auto_points if available, otherwise fall back to manual calculation
    def score_per_breakdown(b):
        if "auto_points" in b and b["auto_points"] is not None:
            return b["auto_points"]
        score = 0
        if b.get("robot_set"):
            score += 4
        if b.get("tote_set"):
            score += 6
        if b.get("container_set"):
            score += 8
        if b.get("tote_stack"):
            score += 20
        return score
    scores = [score_per_breakdown(b) for b in breakdowns if isinstance(b, dict)]
    return round(sum(scores) / (len(scores) * team_count), 2) if scores else 0.0

def teleop_2015(breakdowns, team_count):
    # Use the API's teleop_points if available, otherwise sum up the components
    def score_per_breakdown(b):
        if "teleop_points" in b and b["teleop_points"] is not None:
            return b["teleop_points"]
        tote_points = b.get("tote_points") or 0
        container_points = b.get("container_points") or 0
        litter_points = b.get("litter_points") or 0
        return tote_points + container_points + litter_points
    scores = [score_per_breakdown(b) for b in breakdowns if isinstance(b, dict)]
    return round(sum(scores) / (len(scores) * team_count), 2) if scores else 0.0

def endgame_2015(breakdown, index):
    # No endgame in 2015
    return 0.0

def auto_legacy(breakdowns, team_count):
    # No separate auto score available, so return 0
    return 0.0

def teleop_legacy(breakdowns, team_count):
    # Use the total alliance score as the teleop score
    def score_per_breakdown(b):
        return b.get("score", 0)
    scores = [score_per_breakdown(b) for b in breakdowns]
    # Divide by team count for per-team contribution
    return round(sum(scores) / (len(scores) * team_count), 2) if scores else 0.0

def endgame_legacy(breakdown, index):
    # No endgame in these years
    return 0.0

# Aliases for each year 1992-2014
for y in range(1992, 2015):
    globals()[f"auto_{y}"] = auto_legacy
    globals()[f"teleop_{y}"] = teleop_legacy
    globals()[f"endgame_{y}"] = endgame_legacy