from __future__ import annotations

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from src.config import settings

# Create the engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug
)

# Session factory - simple and non-recursive
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def _sync_embedding_dimension(conn) -> None:
    current_type = conn.execute(text("""
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute AS a
        JOIN pg_class AS c ON a.attrelid = c.oid
        JOIN pg_namespace AS n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = 'document_chunks'
          AND a.attname = 'embedding'
          AND a.attnum > 0
          AND NOT a.attisdropped
    """)).scalar_one_or_none()

    expected_type = f"vector({settings.embedding_dimensions})"
    if current_type and current_type != expected_type:
        conn.execute(
            text(
                f"ALTER TABLE document_chunks "
                f"ALTER COLUMN embedding TYPE {expected_type} "
                f"USING embedding::{expected_type}"
            )
        )

def init_database():
    """Initialize the database schema and enable required extensions."""
    with engine.connect() as conn:
        # 1. Enable pgvector extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

        # 2. Create all tables defined in Base
        Base.metadata.create_all(bind=engine)
        _sync_embedding_dimension(conn)
        conn.commit()
        print("✅ Database initialized successfully.")

def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()