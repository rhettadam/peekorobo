from pydantic import BaseModel
from typing import Optional, List

class TeamEpaInfo(BaseModel):
    year : int
    normal_epa : Optional[float]
    epa : Optional[float]
    confidence : Optional[float]
    auto_epa : Optional[float]
    teleop_epa : Optional[float]
    endgame_epa : Optional[float]
    wins : Optional[int]
    losses : Optional[int]
    ties : Optional[int]

class TeamEpaRequest(BaseModel):
    year : Optional[int] = None

class TeamEpaResponse(BaseModel):
    team_number : int
    team_epa_infos : List[TeamEpaInfo]
