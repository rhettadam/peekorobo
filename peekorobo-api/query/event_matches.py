from pydantic import BaseModel
from typing import Optional, List, Dict

class PreMatchTeamCompact(BaseModel):
    a: float
    t: float
    e: float
    r: float
    c: float
    ace: float

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
    red_predicted_score : Optional[float] = None
    blue_predicted_score : Optional[float] = None
    pre_match_teams : Optional[Dict[str, PreMatchTeamCompact]] = None

class EventMatchResponse(BaseModel):
    event_key : str
    matches : List[MatchResponse]
