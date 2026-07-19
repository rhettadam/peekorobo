from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

load_dotenv()

DB_URL = os.environ["DB_URL"]
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# Neon (and most cloud Postgres) require TLS. Ensure sslmode=require is present
# so SQLAlchemy/psycopg2 do not attempt an insecure startup.
_parsed = urlparse(DB_URL)
_q = dict(parse_qsl(_parsed.query, keep_blank_values=True))
if "neon.tech" in (_parsed.hostname or "") and "sslmode" not in _q:
    _q["sslmode"] = "require"
    DB_URL = urlunparse(_parsed._replace(query=urlencode(_q)))

engine = create_engine(DB_URL, pool_size=10, max_overflow=0)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
