from pydantic import BaseModel
from typing import List, Literal, Optional


class EventInsightRow(BaseModel):
    event_key: str
    team_count: int
    max_ace: float
    top8_ace: float
    top24_ace: float
    mean_ace: float
    median_ace: float
    iqr_ace: float
    std_ace: float
    # "event" = rolled up from per-event ACE; "season" = season totals fallback
    source: Literal["event", "season"] = "season"


class EventInsightsResponse(BaseModel):
    year: int
    events: List[EventInsightRow]
