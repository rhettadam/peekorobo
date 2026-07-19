from typing import List, Optional
from pydantic import BaseModel


class FrcGameInfo(BaseModel):
    year: int
    name: Optional[str] = None
    video: Optional[str] = None
    logo: Optional[str] = None
    manual: Optional[str] = None
    summary: Optional[str] = None


class FrcGamesResponse(BaseModel):
    games: List[FrcGameInfo]
