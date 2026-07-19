from pydantic import BaseModel


class SeasonSummaryResponse(BaseModel):
    year: int
    team_count: int
    event_count: int
    match_count: int
