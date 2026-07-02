from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=settings.debug)
_schema_lock = Lock()
_schema_initialized = False


def init_database() -> None:
    global _schema_initialized

    if _schema_initialized:
        return

    with _schema_lock:
        if _schema_initialized:
            return

        import src.models  # Ensure model metadata is registered before create_all.

        Base.metadata.create_all(bind=engine)
        _schema_initialized = True


class _InitializingSessionMaker(sessionmaker):
    def __call__(self, **local_kw):
        init_database()
        return super().__call__(**local_kw)


SessionLocal = _InitializingSessionMaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    init_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()