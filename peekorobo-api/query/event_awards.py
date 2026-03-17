from typing import List
from pydantic import BaseModel

class EventAwardsResponse(BaseModel):
    event_key : str
    teams_and_awards : List[AwardData]

class AwardData(BaseModel):
    team_number : int
    award_name : str
