from typing import List
from pydantic import BaseModel

class AwardData(BaseModel):
    team_number : int
    award_name : str

class EventAwardsResponse(BaseModel):
    event_key : str
    teams_and_awards : List[AwardData]
