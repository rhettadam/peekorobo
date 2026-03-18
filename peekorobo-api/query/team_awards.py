from typing import List
from pydantic import BaseModel

class TeamAwardData(BaseModel):
    event_key: str
    award_name: str

class TeamAwardsResponse(BaseModel):
    team_number: int
    awards: List[TeamAwardData]
