from sqlalchemy import Text, INT
from sqlalchemy.orm import Mapped, mapped_column
from db import Base

class EventTeams(Base):
    __tablename__ = "event_teams"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    nickname : Mapped[str] = mapped_column(Text)
    city : Mapped[str] = mapped_column(Text)
    state_prov : Mapped[str] = mapped_column(Text)
    country : Mapped[str] = mapped_column(Text)
