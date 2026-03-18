from typing import List, Optional
from pydantic import BaseModel

class TeamEventsQuery(BaseModel):
    year: Optional[int] = None
    district_key: Optional[str] = None

class TeamEventsResponse(BaseModel):
    team_number: int
    events: List[str]
