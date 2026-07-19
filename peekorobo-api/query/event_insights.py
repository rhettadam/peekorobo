from pydantic import BaseModel
from typing import List


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


class EventInsightsResponse(BaseModel):
    year: int
    events: List[EventInsightRow]
