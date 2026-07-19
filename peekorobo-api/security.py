"""Authentication helpers: password hashing and stateless JWTs.

Password hashing intentionally mirrors the legacy Dash app (auth.py):
PBKDF2-HMAC-SHA256 with a 32-byte random salt and 100k iterations, stored as
``salt || key`` in a ``bytea`` column. Keeping this scheme means the ~1000
existing production accounts continue to authenticate unchanged. New accounts
use the same (secure) scheme so there is a single verification path.

Auth tokens are stateless HS256 JWTs so the SPA can store the token client-side
and send it as a ``Authorization: Bearer <token>`` header. No server-side
session store is required.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 32
KEY_BYTES = 32

JWT_ALGORITHM = "HS256"
# Token lifetime; long-lived because it is the SPA's persisted login.
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "30"))

# Secret for signing tokens. A stable per-process fallback is generated when the
# env var is missing so local dev works, but production MUST set JWT_SECRET
# (otherwise tokens are invalidated on every restart).
_JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
if not _JWT_SECRET:
    _JWT_SECRET = "peekorobo-dev-insecure-secret-change-me"


def hash_password(password: str) -> bytes:
    """Return ``salt || key`` bytes for storage in the ``password_hash`` column."""
    salt = os.urandom(SALT_BYTES)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return salt + key


def verify_password(password: str, stored_hash: bytes) -> bool:
    """Constant-time verification against a stored ``salt || key`` blob."""
    if stored_hash is None:
        return False
    if isinstance(stored_hash, memoryview):
        stored_hash = stored_hash.tobytes()
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()
    if len(stored_hash) < SALT_BYTES + 1:
        return False
    salt = stored_hash[:SALT_BYTES]
    key = stored_hash[SALT_BYTES:]
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(new_key, key)


def create_access_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Return the token payload, or ``None`` if invalid/expired."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def validate_password_strength(password: str) -> Optional[str]:
    """Return an error message if the password is too weak, else ``None``.

    Mirrors the legacy rules: >= 8 chars with upper, lower, and digit.
    """
    if len(password) < 8 or not any(c.isupper() for c in password) \
            or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return "Password must be at least 8 characters and include upper, lower, and digits."
    return None
