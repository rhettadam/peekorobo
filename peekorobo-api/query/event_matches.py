from pydantic import BaseModel
from typing import Optional, List

class EventMatchesRequest(BaseModel):
    match_key : Optional[str] = None
    team_number : Optional[str] = None

class MatchResponse(BaseModel):
    match_key : str
    comp_level : str
    match_number : int
    set_number : int
    red_teams : List[int]
    blue_teams : List[int]
    red_score : int
    blue_score : int
    winning_alliance : str
    youtube_key : Optional[str] = None
    predicted_time : Optional[int] = None
    red_win_prob : Optional[float] = None
    blue_win_prob : Optional[float] = None

class EventMatchResponse(BaseModel):
    event_key : str
    matches : List[MatchResponse]
