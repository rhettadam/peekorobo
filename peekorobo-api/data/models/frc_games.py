from sqlalchemy import text
from sqlalchemy.orm import Session

from query.frc_games import FrcGamesResponse, FrcGameInfo


def get_frc_games(db: Session) -> FrcGamesResponse:
    """Season game metadata (name, reveal video, logo, manual, summary).

    Mirrors the old Dash load_frc_games(): reads the frc_games table and returns
    rows newest-first.
    """
    rows = db.execute(
        text(
            "SELECT year, name, video, logo, manual, summary "
            "FROM frc_games ORDER BY year DESC"
        )
    ).fetchall()
    games = [
        FrcGameInfo(
            year=r[0],
            name=r[1],
            video=r[2],
            logo=r[3],
            manual=r[4],
            summary=r[5],
        )
        for r in rows
    ]
    return FrcGamesResponse(games=games)
