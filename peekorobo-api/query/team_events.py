from typing import List, Optional
from pydantic import BaseModel

class TeamEventsQuery(BaseModel):
    year: Optional[int] = None

class TeamEventsResponse(BaseModel):
    team_number: int
    events: List[str]
