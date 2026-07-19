"""Database access for user favorites (saved teams and events).

Backed by the shared ``saved_items`` table: (user_id, item_type, item_key)
where item_type is 'team' or 'event' and item_key is the team number (as text)
or the event key.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from query.favorites import FavoritesResponse


def list_favorites(db: Session, user_id: int) -> FavoritesResponse:
    rows = db.execute(
        text("SELECT item_type, item_key FROM saved_items WHERE user_id = :uid"),
        {"uid": user_id},
    ).all()
    teams = [r.item_key for r in rows if r.item_type == "team"]
    events = [r.item_key for r in rows if r.item_type == "event"]
    return FavoritesResponse(teams=teams, events=events)


def is_favorited(db: Session, user_id: int, item_type: str, item_key: str) -> bool:
    return db.execute(
        text(
            """
            SELECT 1 FROM saved_items
            WHERE user_id = :uid AND item_type = :t AND item_key = :k
            """
        ),
        {"uid": user_id, "t": item_type, "k": item_key},
    ).first() is not None


def favorite_count(db: Session, item_type: str, item_key: str) -> int:
    return db.execute(
        text(
            """
            SELECT COUNT(*) FROM saved_items
            WHERE item_type = :t AND item_key = :k
            """
        ),
        {"t": item_type, "k": item_key},
    ).scalar() or 0


def add_favorite(db: Session, user_id: int, item_type: str, item_key: str) -> None:
    if is_favorited(db, user_id, item_type, item_key):
        return
    db.execute(
        text(
            """
            INSERT INTO saved_items (user_id, item_type, item_key)
            VALUES (:uid, :t, :k)
            """
        ),
        {"uid": user_id, "t": item_type, "k": item_key},
    )
    db.commit()


def remove_favorite(db: Session, user_id: int, item_type: str, item_key: str) -> None:
    db.execute(
        text(
            """
            DELETE FROM saved_items
            WHERE user_id = :uid AND item_type = :t AND item_key = :k
            """
        ),
        {"uid": user_id, "t": item_type, "k": item_key},
    )
    db.commit()
