from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class MapTeam(BaseModel):
    team_number: int
    nickname: Optional[str] = None
    city: Optional[str] = None
    state_prov: Optional[str] = None
    country: Optional[str] = None
    lat: float
    lng: float


class MapTeamsResponse(BaseModel):
    count: int
    teams: List[MapTeam]


class MapEvent(BaseModel):
    event_key: str
    name: Optional[str] = None
    city: Optional[str] = None
    state_prov: Optional[str] = None
    country: Optional[str] = None
    lat: float
    lng: float
    event_type: Optional[str] = None
    week: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class MapEventsResponse(BaseModel):
    year: int
    count: int
    events: List[MapEvent]
