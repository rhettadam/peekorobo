from typing import List, Optional
from pydantic import BaseModel


class TeamNotableData(BaseModel):
    category: str
    label: str
    years: List[int]
    # Impact/Hall of Fame reveal video (Hall of Fame only).
    video: Optional[str] = None


class TeamNotablesResponse(BaseModel):
    team_number: int
    notables: List[TeamNotableData]
