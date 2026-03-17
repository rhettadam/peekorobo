from sqlalchemy import Text, INT
from sqlalchemy.orm import Mapped, mapped_column
from db import Base

class EventAwards(Base):
    __tablename__ = "event_awards"

    event_key : Mapped[str] = mapped_column(Text, primary_key=True)
    team_number : Mapped[int] = mapped_column(INT, primary_key=True)
    award_name : Mapped[str] = mapped_column(Text)
