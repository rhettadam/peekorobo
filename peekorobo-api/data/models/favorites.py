"""Database access for user favorites (saved teams and events).

Backed by the shared ``saved_items`` table: (user_id, item_type, item_key)
where item_type is 'team' or 'event' and item_key is the team number (as text)
or the event key.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from query.favorites import (
    FavoriteCountsResponse,
    FavoriteItemDetailResponse,
    FavoriterUser,
    FavoritesResponse,
)


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


def list_favoriters(
    db: Session, item_type: str, item_key: str, limit: int = 100
) -> FavoriteItemDetailResponse:
    """Public: who favorited this team/event (newest first)."""
    rows = db.execute(
        text(
            """
            SELECT u.id, u.username, u.avatar_key
            FROM saved_items s
            JOIN users u ON u.id = s.user_id
            WHERE s.item_type = :t AND s.item_key = :k
            ORDER BY s.id DESC
            LIMIT :lim
            """
        ),
        {"t": item_type, "k": item_key, "lim": limit},
    ).all()
    users = [
        FavoriterUser(id=int(r.id), username=r.username, avatar_key=r.avatar_key)
        for r in rows
    ]
    total = favorite_count(db, item_type, item_key)
    return FavoriteItemDetailResponse(
        item_type=item_type,  # type: ignore[arg-type]
        item_key=item_key,
        count=total,
        users=users,
    )


def favorite_counts(db: Session, item_type: str) -> FavoriteCountsResponse:
    """Public map of item_key -> favorite count for leaderboards."""
    rows = db.execute(
        text(
            """
            SELECT item_key, COUNT(*) AS c
            FROM saved_items
            WHERE item_type = :t
            GROUP BY item_key
            """
        ),
        {"t": item_type},
    ).all()
    return FavoriteCountsResponse(
        item_type=item_type,  # type: ignore[arg-type]
        counts={str(r.item_key): int(r.c) for r in rows},
    )


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
