from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from typing import Generator
from app.config import settings


class Base(DeclarativeBase):
    pass


# NullPool is imported for use in testing (no connection pooling in tests prevents
# cross-test database state leakage). In production, the default QueuePool is used.
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,   # Verify connections before use (handles dropped connections)
    echo=settings.DEBUG,  # SQL query logging in DEBUG mode only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """FastAPI dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_test_engine(database_url: str):
    """Create a NullPool engine for use in tests (prevents connection reuse)."""
    return create_engine(database_url, poolclass=NullPool)
