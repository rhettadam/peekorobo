from sqlalchemy import INT, Text
from sqlalchemy.orm import mapped_column, Mapped
from db import Base

class EventRankings(Base):
    __tablename__ = "event_rankings"

    event_key : Mapped[str] = mapped_column(Text,primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    rank : Mapped[int] = mapped_column(INT)
    wins : Mapped[int] = mapped_column(INT)
    losses : Mapped[int] = mapped_column(INT)
    ties : Mapped[int] = mapped_column(INT)
    dq : Mapped[int] = mapped_column(INT)
