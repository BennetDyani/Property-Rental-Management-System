from src import database


def test_init_database_creates_tables_once(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(database, "_schema_initialized", False)
    monkeypatch.setattr(database.Base.metadata, "create_all", lambda bind: calls.append(bind))

    database.init_database()
    database.init_database()

    assert calls == [database.engine]


def test_get_db_initializes_schema_before_session(monkeypatch):
    order: list[str] = []

    class DummySession:
        def close(self):
            order.append("close")

    def fake_init_database():
        order.append("init")

    def fake_session_local():
        order.append("session")
        return DummySession()

    monkeypatch.setattr(database, "init_database", fake_init_database)
    monkeypatch.setattr(database, "SessionLocal", fake_session_local)

    generator = database.get_db()
    session = next(generator)

    assert isinstance(session, DummySession)
    assert order == ["init", "session"]

    with __import__("pytest").raises(StopIteration):
        next(generator)

    assert order == ["init", "session", "close"]
