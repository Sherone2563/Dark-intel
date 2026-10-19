from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_database_url


class Base(DeclarativeBase):
    """Base class for persistent SQLAlchemy models."""


engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def check_database_connection() -> bool:
    """Return whether PostgreSQL responds to a simple query."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
