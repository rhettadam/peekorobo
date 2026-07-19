"""
Minimal Postgres helpers for pipeline scripts (search/leaderboard generators).

Replaces the old Dash-era datagather.DatabaseConnection without pulling in
the rest of that module.
"""
from __future__ import annotations

import os
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
from psycopg2 import pool

load_dotenv()

_connection_pool = None
_pool_lock = threading.Lock()


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL")
    if not url:
        raise Exception("DATABASE_URL (or DB_URL) not set in environment.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_connection_pool():
    url = _database_url()
    result = urlparse(url)
    dbname = (result.path or "/").lstrip("/")
    if "?" in dbname:
        dbname = dbname.split("?", 1)[0]
    host = result.hostname or ""

    pool_config = {
        "database": dbname,
        "user": result.username,
        "password": result.password,
        "host": host,
        "port": result.port or 5432,
        "minconn": 1,
        "maxconn": 10,
        "connect_timeout": 10,
    }
    if "neon.tech" in host or "sslmode=require" in url:
        pool_config["sslmode"] = "require"
    # Neon pooler rejects startup `options` like statement_timeout.
    if "-pooler." not in host:
        pool_config["options"] = "-c statement_timeout=300000"

    return pool.ThreadedConnectionPool(**pool_config)


def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = create_connection_pool()
    return _connection_pool


def get_pg_connection():
    conn = get_connection_pool().getconn()
    if conn is None:
        raise Exception("Failed to get connection from pool")
    return conn


def return_pg_connection(conn):
    if conn is None:
        return
    try:
        get_connection_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


class DatabaseConnection:
    """Context manager yielding a pooled psycopg2 connection."""

    def __init__(self):
        self.conn = None

    def __enter__(self):
        self.conn = get_pg_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            return_pg_connection(self.conn)
            self.conn = None
