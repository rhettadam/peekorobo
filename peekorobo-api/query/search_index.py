from typing import Dict, Optional

from pydantic import BaseModel


class SearchTeamEntry(BaseModel):
    nickname: str
    last_year: Optional[int] = None


class SearchIndexResponse(BaseModel):
    teams: Dict[str, SearchTeamEntry]
    events: Dict[str, str]
