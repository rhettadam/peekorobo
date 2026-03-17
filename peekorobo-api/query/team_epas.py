from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class TeamPerfInfo(BaseModel):
    year : int
    raw : Optional[float]
    ace : Optional[float]
    confidence : Optional[float]
    auto_raw : Optional[float]
    teleop_raw : Optional[float]
    endgame_raw : Optional[float]
    wins : Optional[int]
    losses : Optional[int]
    ties : Optional[int]
    event_perf : Optional[List[Dict[str, Any]]] = None

class TeamPerfRequest(BaseModel):
    year : Optional[int] = None

class TeamPerfResponse(BaseModel):
    team_number : int
    team_perfs : List[TeamPerfInfo]
