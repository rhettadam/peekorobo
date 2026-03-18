from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.environ["DB_URL"]
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, pool_size=10, max_overflow=0)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
