from __future__ import annotations

import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

# Use environment variable or fallback to local default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/rental_ai"
)

# Create the engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

# Session factory - simple and non-recursive
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

def init_database():
    """Initialize the database schema and enable required extensions."""
    with engine.connect() as conn:
        # 1. Enable pgvector extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

        # 2. Create all tables defined in Base
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully.")

def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()