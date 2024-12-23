from statbotics import Statbotics
from typing import List, Dict, Any

# Initialize Statbotics client
sb = Statbotics()

print(sb.get_team_year(1912,2024, ['epa_mean']))