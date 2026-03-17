from typing import Optional
from sqlalchemy import Text, INT
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column
from data.db import Base


class EventMatch(Base):
    __tablename__ = "event_matches"

    match_key: Mapped[str] = mapped_column(Text, primary_key=True)
    event_key: Mapped[Optional[str]] = mapped_column(Text)
    comp_level: Mapped[Optional[str]] = mapped_column(Text)
    match_number: Mapped[Optional[int]] = mapped_column(INT)
    set_number: Mapped[Optional[int]] = mapped_column(INT)
    red_teams: Mapped[Optional[str]] = mapped_column(Text)
    blue_teams: Mapped[Optional[str]] = mapped_column(Text)
    red_score: Mapped[Optional[int]] = mapped_column(INT)
    blue_score: Mapped[Optional[int]] = mapped_column(INT)
    winning_alliance: Mapped[Optional[str]] = mapped_column(Text)
    youtube_key: Mapped[Optional[str]] = mapped_column(Text)
    predicted_time: Mapped[Optional[int]] = mapped_column(INT)
    red_win_prob: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
    blue_win_prob: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION)
