from typing import List, Optional
from pydantic import BaseModel


class YearSeriesPoint(BaseModel):
    year: int
    team_count: int
    event_count: int
    match_count: int


class AccuracyPoint(BaseModel):
    year: int
    correct: int
    total: int
    pct: Optional[float] = None
    brier: Optional[float] = None


class PredBucket(BaseModel):
    label: str
    correct: int
    total: int
    pct: Optional[float] = None
    brier: Optional[float] = None


class PredSummary(BaseModel):
    correct: int
    total: int
    pct: Optional[float] = None
    brier: Optional[float] = None
    favorite_win_pct: Optional[float] = None
    upset_pct: Optional[float] = None


class PredictionStats(BaseModel):
    summary: PredSummary
    by_year: List[AccuracyPoint]
    by_confidence: List[PredBucket]
    by_comp_level: List[PredBucket]
    by_event_type: List[PredBucket]


class LeaderRow(BaseModel):
    team_number: int
    count: int
    detail: Optional[str] = None


class TeamupRow(BaseModel):
    team_a: int
    team_b: int
    count: int


class InsightsOverviewResponse(BaseModel):
    years: List[YearSeriesPoint]
    prediction_accuracy: List[AccuracyPoint]
    predictions: PredictionStats
    blue_banners: List[LeaderRow]
    championship_wins: List[LeaderRow]
    impact_chairmans: List[LeaderRow]
    regional_dcmp_impact: List[LeaderRow]
    regional_wins: List[LeaderRow]
    district_wins: List[LeaderRow]
    division_wins: List[LeaderRow]
    woodie_flowers: List[LeaderRow]
    einstein_appearances: List[LeaderRow]
    einstein_streaks: List[LeaderRow]
    event_teamups: List[TeamupRow]
    einstein_teamups: List[TeamupRow]
    totals: dict
