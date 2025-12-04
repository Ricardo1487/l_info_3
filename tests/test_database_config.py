# tests/test_database_config.py

import os
import importlib

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

def _reload_database(monkeypatch, env_values: dict):
    """
    Hilfsfunktion: setzt ENV-Variablen und lädt app.config.database neu,
    damit DATABASE_URL / engine mit diesen Werten gebaut werden.
    """
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    # Modul neu laden, damit es die neuen ENV-Werte liest
    import app.config.database as database
    importlib.reload(database)
    return database


def test_database_url_builds_from_env(monkeypatch):
    """
    Testet, dass DATABASE_URL korrekt aus den ENV-Variablen zusammengesetzt wird
    und sslmode=require enthält.
    """
    db = _reload_database(
        monkeypatch,
        {
            "DATABASE_USER": "test_user",
            "DATABASE_PASSWORD": "secret_pw",
            "DATABASE_HOST": "db.example.com",
            "DATABASE_PORT": "6543",
            "DATABASE_NAME": "mydb",
        },
    )

    # Grundstruktur prüfen
    assert db.DATABASE_URL.startswith(
        "postgresql+psycopg2://test_user:secret_pw@db.example.com:6543/mydb"
    )
    assert "sslmode=require" in db.DATABASE_URL


def test_engine_uses_correct_url_and_ssl(monkeypatch):
    """
    Testet, dass der SQLAlchemy-Engine mit der erwarteten URL gebaut wird
    und sslmode=require gesetzt ist.
    """
    db = _reload_database(
        monkeypatch,
        {
            "DATABASE_USER": "another_user",
            "DATABASE_PASSWORD": "pw123",
            "DATABASE_HOST": "host.local",
            "DATABASE_PORT": "5433",
            "DATABASE_NAME": "demo_db",
        },
    )

    # engine ist ein SQLAlchemy-Engine-Objekt
    assert isinstance(db.engine, Engine)

    url = db.engine.url
    # Die URL-Komponenten
    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "another_user"
    assert url.password == "pw123"
    assert url.host == "host.local"
    assert url.port == 5433
    assert url.database == "demo_db"

    # sslmode=require sollte in den Query-Parametern sein
    assert url.query.get("sslmode") == "require"


def test_sessionlocal_is_sessionmaker(monkeypatch):
    """
    Testet, dass SessionLocal ein sessionmaker ist und sich eine Session
    ohne direkten DB-Zugriff erzeugen lässt.
    """
    db = _reload_database(
        monkeypatch,
        {
            "DATABASE_USER": "user_x",
            "DATABASE_PASSWORD": "pw_x",
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "dummy_db",
        },
    )

    # SessionLocal ist eine sessionmaker-Factory
    assert isinstance(db.SessionLocal, sessionmaker)

    # Session-Objekt kann erzeugt werden, ohne dass wir irgendetwas abfragen
    session = db.SessionLocal()
    from sqlalchemy.orm import Session

    assert isinstance(session, Session)
    session.close()
