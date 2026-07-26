"""Safety helpers: refuse accidental writes to Neon/prod during local ACE work."""

from __future__ import annotations

import os
from urllib.parse import urlparse


def database_url() -> str | None:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("DB_URL")
        or os.environ.get("NEON_URL")
        or None
    )


def is_prod_database_url(url: str | None = None) -> bool:
    """True for hosted Neon (and similar) URLs — not localhost."""
    url = url or database_url() or ""
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    return "neon.tech" in host or os.environ.get("ACE_FORCE_PROD_URL", "").lower() in (
        "1",
        "true",
        "yes",
    )


def assert_safe_db_target(action: str = "write") -> str:
    """Return DATABASE_URL, or exit if it looks like prod without an explicit allow.

    Set ACE_ALLOW_PROD_WRITE=1 only for intentional Neon/production recomputes.
    """
    url = database_url()
    if not url:
        raise SystemExit(
            f"No DATABASE_URL/DB_URL set — cannot {action}. "
            "Point at local Postgres (see data/.env.local.example)."
        )
    if is_prod_database_url(url) and os.environ.get("ACE_ALLOW_PROD_WRITE", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        host = urlparse(url).hostname or "?"
        raise SystemExit(
            f"Refusing to {action} on hosted DB ({host}).\n"
            "Use a local DATABASE_URL (data/.env.local), or set\n"
            "  ACE_ALLOW_PROD_WRITE=1\n"
            "only for an intentional production recompute."
        )
    return url


def describe_db_target() -> str:
    url = database_url()
    if not url:
        return "no DATABASE_URL"
    host = urlparse(url).hostname or "?"
    db = (urlparse(url).path or "/").lstrip("/").split("?", 1)[0]
    kind = "PROD" if is_prod_database_url(url) else "local"
    return f"{kind} -> {host}/{db}"
