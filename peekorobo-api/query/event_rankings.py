from typing import List, Optional
from pydantic import BaseModel

class EventRankingsQuery(BaseModel):
    team_number: Optional[int] = None

class TeamRankingInfo(BaseModel):
    team_number : int
    rank : int
    wins : int
    losses : int
    ties : int
    dq : int

class EventRankingsResponse(BaseModel):
    event_key : str
    event_rankings : List[TeamRankingInfo]
