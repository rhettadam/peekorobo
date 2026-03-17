from pydantic import BaseModel
from typing import Optional, List

class EventTeamsQuery(BaseModel):
    team_number : Optional[int] = None

class EventTeamsResponse(BaseModel):
    event_key : str
    teams : List[int]
