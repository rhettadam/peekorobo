from sqlalchemy import Text, INT, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from data.db import Base
from query.notables import TeamNotablesResponse, TeamNotableData

# Only these two categories are surfaced on team profiles (matches the
# production app). Hall of Fame carries the impact/reveal video.
INCLUDED_CATEGORIES: dict[str, str] = {
    "notables_hall_of_fame": "Hall of Fame",
    "notables_world_champions": "World Champions",
}


class Notables(Base):
    __tablename__ = "notables"

    team_key: Mapped[str] = mapped_column(Text, primary_key=True)
    year: Mapped[int] = mapped_column(INT, primary_key=True)
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    video: Mapped[str] = mapped_column(Text, nullable=True)


def get_team_notables(db: Session, team_number: int) -> TeamNotablesResponse:
    team_key = f"frc{team_number}"
    stmt = (
        select(Notables)
        .where(Notables.team_key == team_key)
        .where(Notables.category.in_(list(INCLUDED_CATEGORIES.keys())))
    )
    rows = db.scalars(stmt).all()

    grouped: dict[str, dict] = {}
    for r in rows:
        cat = r.category
        if cat not in INCLUDED_CATEGORIES:
            continue
        entry = grouped.setdefault(cat, {"years": set(), "video": None})
        try:
            entry["years"].add(int(r.year))
        except (TypeError, ValueError):
            pass
        # Hall of Fame keeps the reveal video if present.
        if cat == "notables_hall_of_fame" and r.video:
            entry["video"] = r.video

    notables: list[TeamNotableData] = []
    # Hall of Fame first, then World Champions (stable, matches production order).
    for cat in INCLUDED_CATEGORIES:
        if cat not in grouped:
            continue
        entry = grouped[cat]
        notables.append(
            TeamNotableData(
                category=cat,
                label=INCLUDED_CATEGORIES[cat],
                years=sorted(entry["years"]),
                video=entry["video"],
            )
        )
    return TeamNotablesResponse(team_number=team_number, notables=notables)
