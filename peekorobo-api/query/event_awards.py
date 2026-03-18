from typing import List, Optional
from pydantic import BaseModel

class EventAwardsQuery(BaseModel):
    team_number: Optional[int] = None

class AwardData(BaseModel):
    team_number : int
    award_name : str

class EventAwardsResponse(BaseModel):
    event_key : str
    teams_and_awards : List[AwardData]
