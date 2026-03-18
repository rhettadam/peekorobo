from typing import List
from pydantic import BaseModel

class TeamEventsResponse(BaseModel):
    team_number: int
    events: List[str]
