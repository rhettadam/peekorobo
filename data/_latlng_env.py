import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv


def bootstrap_env():
    """Ensure the env vars run.py needs at import time are present.

    The data pipeline reads DATABASE_URL (and TBA_API_KEYS) from the environment.
    On machines without a root .env we fall back to peekorobo-api/.env, which
    holds the shared Postgres URL as DB_URL. These scripts never call TBA, so a
    placeholder TBA key is enough to satisfy run.py's import-time check.
    """
    load_dotenv()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_env = os.path.join(repo_root, "peekorobo-api", ".env")
    if os.path.exists(api_env):
        load_dotenv(api_env)

    if not os.environ.get("DATABASE_URL"):
        db_url = os.environ.get("DB_URL")
        if db_url:
            os.environ["DATABASE_URL"] = db_url

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL/DB_URL not found in environment or peekorobo-api/.env")

    if not os.environ.get("TBA_API_KEYS"):
        os.environ["TBA_API_KEYS"] = "placeholder"
