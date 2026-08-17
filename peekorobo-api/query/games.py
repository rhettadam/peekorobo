from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class H2HTeamInfo(BaseModel):
    team_number: int
    nickname: str
    city: str = ""
    state_prov: str = ""
    country: str = ""
    district_key: Optional[str] = None
    team_colors: Optional[Dict[str, Any]] = None
    ace: Optional[float] = None
    raw: Optional[float] = None
    wins: Optional[int] = None
    losses: Optional[int] = None
    ties: Optional[int] = None
    rank_global: Optional[int] = None


class H2HMatch(BaseModel):
    match_key: str
    event_key: str
    event_name: Optional[str] = None
    year: int
    week: Optional[int] = None
    comp_level: str
    match_number: int
    set_number: int
    red_teams: List[int]
    blue_teams: List[int]
    red_score: int
    blue_score: int
    winning_alliance: str
    relation: str  # together | against
    a_alliance: str  # red | blue
    b_alliance: str
    youtube_key: Optional[str] = None
    red_win_prob: Optional[float] = None
    blue_win_prob: Optional[float] = None


class H2HTogetherStats(BaseModel):
    matches: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    win_pct: Optional[float] = None
    avg_score: Optional[float] = None
    avg_opp_score: Optional[float] = None
    avg_margin: Optional[float] = None


class H2HAgainstStats(BaseModel):
    matches: int = 0
    a_wins: int = 0
    b_wins: int = 0
    ties: int = 0
    a_win_pct: Optional[float] = None
    avg_a_score: Optional[float] = None
    avg_b_score: Optional[float] = None
    avg_margin: Optional[float] = None


class H2HYearSlice(BaseModel):
    year: int
    together: int = 0
    against: int = 0
    together_wins: int = 0
    a_wins: int = 0
    b_wins: int = 0


class H2HResponse(BaseModel):
    team_a: H2HTeamInfo
    team_b: H2HTeamInfo
    year: Optional[int] = None
    events_shared: int = 0
    together: H2HTogetherStats
    against: H2HAgainstStats
    by_year: List[H2HYearSlice] = []
    matches: List[H2HMatch] = []


class PredictorMatch(BaseModel):
    match_key: str
    event_key: str
    event_name: str = ""
    year: int
    week: Optional[int] = None
    event_type: Optional[str] = None
    comp_level: str
    match_number: int
    set_number: int
    red_teams: List[int]
    blue_teams: List[int]
    red_score: int
    blue_score: int
    winning_alliance: str
    red_win_prob: Optional[float] = None
    blue_win_prob: Optional[float] = None
    red_predicted_score: Optional[float] = None
    blue_predicted_score: Optional[float] = None


class PredictorMatchesResponse(BaseModel):
    year: int
    event_key: Optional[str] = None
    event_name: Optional[str] = None
    nicknames: Dict[str, str] = {}
    matches: List[PredictorMatch] = []


class PredictorQuery(BaseModel):
    year: int
    event_key: Optional[str] = None
    week: Optional[int] = None
    limit: int = Field(12, ge=1, le=80)
    seed: Optional[int] = None
    playoffs_only: bool = False
