from pydantic import BaseModel, Field
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
    rank_global : Optional[int] = None
    rank_country : Optional[int] = None
    rank_state : Optional[int] = None
    rank_district : Optional[int] = None
    count_global : Optional[int] = None
    count_country : Optional[int] = None
    count_state : Optional[int] = None
    count_district : Optional[int] = None

class TeamPerfRequest(BaseModel):
    year : Optional[int] = None

class TeamPerfResponse(BaseModel):
    team_number : int
    team_perfs : List[TeamPerfInfo]

class TeamPerfListRequest(BaseModel):
    year : int
    limit : Optional[int] = Field(100, gt=0, le=500)
    next_team_number : Optional[int] = Field(None, gt=0)
    city : Optional[str] = None
    state_prov : Optional[str] = None
    country : Optional[str] = None
    district_key : Optional[str] = None

class TeamPerfListResponse(BaseModel):
    team_perfs : List[TeamPerfResponse]
    next : Optional[int] = None
