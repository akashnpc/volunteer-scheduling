from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config


def make_engine(url: str = config.DATABASE_URL):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # pool_pre_ping: free-tier Postgres drops idle connections.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
