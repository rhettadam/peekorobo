from typing import List, Optional
from pydantic import BaseModel


class TeamAwardsQuery(BaseModel):
    year: Optional[int] = None
    district_key: Optional[str] = None


class TeamAwardData(BaseModel):
    event_key: str
    award_name: str
    event_name: Optional[str] = None


class TeamAwardsResponse(BaseModel):
    team_number: int
    awards: List[TeamAwardData]
