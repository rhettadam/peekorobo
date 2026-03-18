from typing import List, Optional
from pydantic import BaseModel


class EventPerfInfo(BaseModel):
    team_number: int
    event_key: str
    raw: Optional[float] = None
    ace: Optional[float] = None
    confidence: Optional[float] = None
    auto_raw: Optional[float] = None
    teleop_raw: Optional[float] = None
    endgame_raw: Optional[float] = None


class EventPerfsResponse(BaseModel):
    event_key: str
    perfs: List[EventPerfInfo]
