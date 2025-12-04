# tests/test_users_service.py

import pytest

from app.services import users as users_mod


class DummyResult:
    """Simuliert das Ergebnis von db.execute(...).mappings().first()/all()/scalar_one()."""

    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        if self._rows:
            return self._rows[0]
        return None

    def all(self):
        return list(self._rows)

    def scalar_one(self):
        # Wird bei INSERT ... RETURNING id verwendet
        return self._rows[0]["id"]


class DummySession:
    """
    Einfacher Fake für SessionLocal()-Objekte, das:
    - als Context-Manager funktioniert
    - execute() protokolliert
    - commit() zählt
    """

    def __init__(self, rows=None, new_id=123):
        self.rows = rows or []
        self.new_id = new_id
        self.executed = []  # Liste von (sql, params)
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params))

        # Grobe Unterscheidung: INSERT ... RETURNING id vs. SELECT
        if "RETURNING id" in sql:
            return DummyResult([{"id": self.new_id}])
        else:
            return DummyResult(self.rows)

    def commit(self):
        self.commits += 1


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------

def test_get_user_by_email_returns_dict_when_found(monkeypatch):
    dummy_row = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": "hash",
        "role": users_mod.ROLE_ADMIN,
    }

    def fake_SessionLocal():
        return DummySession(rows=[dummy_row])

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    result = users_mod.get_user_by_email("alice@example.com")

    assert result == dummy_row
    assert result["email"] == "alice@example.com"


def test_get_user_by_email_returns_none_when_not_found(monkeypatch):
    def fake_SessionLocal():
        return DummySession(rows=[])

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    result = users_mod.get_user_by_email("nobody@example.com")
    assert result is None


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------

def test_get_user_by_id_returns_dict_when_found(monkeypatch):
    dummy_row = {
        "id": 42,
        "username": "bob",
        "email": "bob@example.com",
        "password_hash": "hash2",
        "role": users_mod.ROLE_HIWI,
    }

    def fake_SessionLocal():
        return DummySession(rows=[dummy_row])

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    result = users_mod.get_user_by_id(42)

    assert result == dummy_row
    assert result["id"] == 42


def test_get_user_by_id_returns_none_when_not_found(monkeypatch):
    def fake_SessionLocal():
        return DummySession(rows=[])

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    result = users_mod.get_user_by_id(999)
    assert result is None


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------

def test_list_users_returns_all_users(monkeypatch):
    rows = [
        {"id": 1, "username": "a", "email": "a@example.com", "role": users_mod.ROLE_ADMIN},
        {"id": 2, "username": "b", "email": "b@example.com", "role": users_mod.ROLE_HIWI},
    ]

    def fake_SessionLocal():
        return DummySession(rows=rows)

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    result = users_mod.list_users()

    assert isinstance(result, list)
    assert result == rows
    assert result[0]["username"] == "a"
    assert result[1]["role"] == users_mod.ROLE_HIWI


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

def test_create_user_raises_value_error_if_email_exists(monkeypatch):
    # get_user_by_email soll so tun, als gäbe es den User schon
    monkeypatch.setattr(
        users_mod,
        "get_user_by_email",
        lambda email: {"id": 1, "email": email},
    )

    with pytest.raises(ValueError):
        users_mod.create_user("test", "dup@example.com", "secret")


def test_create_user_inserts_and_returns_new_id(monkeypatch):
    # E-Mail ist noch nicht vergeben
    monkeypatch.setattr(
        users_mod,
        "get_user_by_email",
        lambda email: None,
    )

    created_sessions = []

    def fake_SessionLocal():
        sess = DummySession(new_id=999)
        created_sessions.append(sess)
        return sess

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    new_id = users_mod.create_user(
        username="newuser",
        email="new@example.com",
        password="secret",
        role=users_mod.ROLE_HIWI,
    )

    # ID aus DummyResult
    assert new_id == 999

    # Es wurde genau eine Session benutzt
    assert len(created_sessions) == 1
    session = created_sessions[0]

    # Es wurde ein Commit ausgeführt
    assert session.commits == 1

    # Es wurde ein INSERT auf die users-Tabelle ausgeführt
    assert any("INSERT INTO users" in sql for sql, _ in session.executed)


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

def test_delete_user_executes_delete_and_commits(monkeypatch):
    created_sessions = []

    def fake_SessionLocal():
        sess = DummySession()
        created_sessions.append(sess)
        return sess

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    users_mod.delete_user(5)

    assert len(created_sessions) == 1
    session = created_sessions[0]

    assert session.commits == 1
    assert any("DELETE FROM users" in sql for sql, _ in session.executed)


# ---------------------------------------------------------------------------
# update_password
# ---------------------------------------------------------------------------

def test_update_password_executes_update_and_commits(monkeypatch):
    created_sessions = []

    def fake_SessionLocal():
        sess = DummySession()
        created_sessions.append(sess)
        return sess

    monkeypatch.setattr(users_mod, "SessionLocal", fake_SessionLocal)

    users_mod.update_password(user_id=7, new_password="neues-passwort")

    assert len(created_sessions) == 1
    session = created_sessions[0]

    assert session.commits == 1
    # SQL grob prüfen
    assert any("UPDATE users SET password_hash" in sql for sql, _ in session.executed)
