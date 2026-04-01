from pydantic import BaseModel
from typing import Optional, List


class EventTeamsQuery(BaseModel):
    team_number: Optional[int] = None


class EventTeamEntry(BaseModel):
    team_number: int
    nickname: str = ""
    city: str = ""
    state_prov: str = ""
    country: str = ""


class EventTeamsResponse(BaseModel):
    event_key: str
    teams: List[EventTeamEntry]
