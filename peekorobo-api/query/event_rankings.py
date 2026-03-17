from typing import List
from pydantic import BaseModel

class EventRankingsResponse(BaseModel):
    event_key : str
    event_rankings : List[TeamRankingInfo]

class TeamRankingInfo(BaseModel):
    team_number : int
    rank : int
    wins : int
    losses : int
    ties : int
    dq : int
