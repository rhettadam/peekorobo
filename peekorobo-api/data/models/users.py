"""Database access for user accounts.

Uses SQLAlchemy Core (text SQL) rather than the ORM because the ``users`` table
predates this API (it is shared with the legacy Dash app and holds ~1000 rows),
including a ``bytea`` password hash and ``jsonb`` followers/following columns.
Raw SQL keeps the mapping explicit and avoids fighting ORM type coercion.
"""

import json
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from query.auth import UserResponse

# Columns selected for a full user record.
_USER_COLUMNS = (
    "id, username, email, role, team, bio, avatar_key, color, followers, following"
)


def init_user_tables(db: Session) -> None:
    """Create the users/saved_items tables if they do not exist.

    On production these already exist (with data); this is a no-op safety net so
    the API also works against a fresh database. It never drops or mutates data.
    """
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            password_hash BYTEA NOT NULL,
            email VARCHAR(255),
            role VARCHAR(100),
            team VARCHAR(50),
            bio TEXT,
            avatar_key VARCHAR(100),
            color VARCHAR(20),
            followers JSONB DEFAULT '[]'::jsonb,
            following JSONB DEFAULT '[]'::jsonb,
            preferences JSONB,
            higher_lower_highscore INTEGER DEFAULT 0,
            api_key TEXT
        )
        """
    ))
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS saved_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_key TEXT NOT NULL
        )
        """
    ))
    db.execute(text(
        """
        CREATE INDEX IF NOT EXISTS idx_saved_items_user
        ON saved_items (user_id, item_type)
        """
    ))
    db.commit()


def _row_to_user_response(row) -> UserResponse:
    followers = row.followers or []
    following = row.following or []
    return UserResponse(
        id=row.id,
        username=row.username,
        email=row.email,
        role=row.role,
        team=row.team,
        bio=row.bio,
        avatar_key=row.avatar_key,
        color=row.color,
        followers_count=len(followers) if isinstance(followers, list) else 0,
        following_count=len(following) if isinstance(following, list) else 0,
    )


def get_user_by_id(db: Session, user_id: int) -> Optional[UserResponse]:
    row = db.execute(
        text(f"SELECT {_USER_COLUMNS} FROM users WHERE id = :id"),
        {"id": user_id},
    ).first()
    return _row_to_user_response(row) if row else None


def username_exists(db: Session, username: str, exclude_id: Optional[int] = None) -> bool:
    sql = "SELECT 1 FROM users WHERE LOWER(username) = :u"
    params = {"u": username.lower()}
    if exclude_id is not None:
        sql += " AND id != :id"
        params["id"] = exclude_id
    return db.execute(text(sql), params).first() is not None


def email_exists(db: Session, email: str, exclude_id: Optional[int] = None) -> bool:
    sql = "SELECT 1 FROM users WHERE LOWER(email) = :e"
    params = {"e": email.lower()}
    if exclude_id is not None:
        sql += " AND id != :id"
        params["id"] = exclude_id
    return db.execute(text(sql), params).first() is not None


def create_user(db: Session, username: str, password_hash: bytes, email: Optional[str]) -> int:
    row = db.execute(
        text(
            """
            INSERT INTO users (username, password_hash, email, followers, following)
            VALUES (:username, :password_hash, :email, '[]'::jsonb, '[]'::jsonb)
            RETURNING id
            """
        ),
        {"username": username.lower(), "password_hash": password_hash, "email": email},
    ).first()
    db.commit()
    return row.id


def get_login_row(db: Session, username_or_email: str):
    """Return (id, password_hash) for login, matching username or email."""
    return db.execute(
        text(
            """
            SELECT id, password_hash FROM users
            WHERE LOWER(username) = :ident OR LOWER(email) = :ident
            """
        ),
        {"ident": username_or_email.lower().strip()},
    ).first()


def get_user_id_by_username(db: Session, username: str) -> Optional[int]:
    """Strict username lookup (case-insensitive), unlike get_login_row."""
    row = db.execute(
        text("SELECT id FROM users WHERE LOWER(username) = :u"),
        {"u": username.lower().strip()},
    ).first()
    return row.id if row else None


def update_user(db: Session, user_id: int, fields: dict) -> None:
    """Update only the provided columns. ``fields`` maps column -> value.

    ``password_hash`` may be included as bytes to change the password.
    """
    if not fields:
        return
    set_clause = ", ".join(f"{col} = :{col}" for col in fields)
    params = dict(fields)
    params["id"] = user_id
    db.execute(text(f"UPDATE users SET {set_clause} WHERE id = :id"), params)
    db.commit()


# --- Follows (user-to-user) ----------------------------------------------
# followers/following are jsonb arrays of user ids, matching the legacy Dash app.
def get_follow_lists(db: Session, user_id: int) -> Tuple[List[int], List[int]]:
    row = db.execute(
        text("SELECT followers, following FROM users WHERE id = :id"),
        {"id": user_id},
    ).first()
    if not row:
        return [], []
    followers = row.followers if isinstance(row.followers, list) else []
    following = row.following if isinstance(row.following, list) else []
    return followers, following


def is_following(db: Session, follower_id: int, followee_id: int) -> bool:
    _, following = get_follow_lists(db, follower_id)
    return followee_id in following


def set_follow(db: Session, follower_id: int, followee_id: int, follow: bool) -> None:
    """Add/remove the follow relationship on both users, mirroring the old app."""
    followee_followers, _ = get_follow_lists(db, followee_id)
    _, follower_following = get_follow_lists(db, follower_id)
    followers = set(followee_followers)
    following = set(follower_following)
    if follow:
        followers.add(follower_id)
        following.add(followee_id)
    else:
        followers.discard(follower_id)
        following.discard(followee_id)
    db.execute(
        text("UPDATE users SET followers = CAST(:v AS jsonb) WHERE id = :id"),
        {"v": json.dumps(sorted(followers)), "id": followee_id},
    )
    db.execute(
        text("UPDATE users SET following = CAST(:v AS jsonb) WHERE id = :id"),
        {"v": json.dumps(sorted(following)), "id": follower_id},
    )
    db.commit()


def list_users_by_ids(db: Session, ids: List[int]) -> List[dict]:
    """Return {id, username, avatar_key} summaries, ordered by the given ids."""
    if not ids:
        return []
    rows = db.execute(
        text("SELECT id, username, avatar_key FROM users WHERE id = ANY(:ids)"),
        {"ids": ids},
    ).all()
    by_id = {r.id: {"id": r.id, "username": r.username, "avatar_key": r.avatar_key} for r in rows}
    return [by_id[i] for i in ids if i in by_id]


# --- API keys -------------------------------------------------------------
def get_api_key(db: Session, user_id: int) -> Optional[str]:
    row = db.execute(text("SELECT api_key FROM users WHERE id = :id"), {"id": user_id}).first()
    return row.api_key if row else None


def api_key_exists(db: Session, key: str) -> bool:
    return db.execute(
        text("SELECT 1 FROM users WHERE api_key = :k"), {"k": key}
    ).first() is not None


def set_api_key(db: Session, user_id: int, key: Optional[str]) -> None:
    db.execute(
        text("UPDATE users SET api_key = :k WHERE id = :id"),
        {"k": key, "id": user_id},
    )
    db.commit()
