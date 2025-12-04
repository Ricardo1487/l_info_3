# tests/test_boxes.py

import os
import pytest

from app.services import boxes as boxes_module


# -------------------------------------------------------------------
# build_qr_payload
# -------------------------------------------------------------------

def test_build_qr_payload_uses_env_base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    result = boxes_module.build_qr_payload("BOX-023")
    assert result == "https://example.com/new-loan?box_code=BOX-023"


def test_build_qr_payload_uses_default_if_env_missing(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    result = boxes_module.build_qr_payload("BOX-001")
    assert result.startswith("http://127.0.0.1:5000")
    assert result.endswith("/new-loan?box_code=BOX-001")


# -------------------------------------------------------------------
# validate_box_code
# -------------------------------------------------------------------

def test_validate_box_code_accepts_box_pattern():
    assert boxes_module.validate_box_code("BOX-001") is True
    assert boxes_module.validate_box_code("BOX-999") is True


def test_validate_box_code_accepts_digits_only():
    # reine Zahlen mit 1–3 Stellen sind erlaubt, inkl. "0"
    for code in ["0", "1", "23", "999"]:
        assert boxes_module.validate_box_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "",
        "0000",
        "BOX-01",
        "BOX-1234",
        "BOX-AB1",
        "BOX_001",
        "abc",
        "BOX-1",
    ],
)
def test_validate_box_code_rejects_invalid_formats(code):
    assert boxes_module.validate_box_code(code) is False


# -------------------------------------------------------------------
# Hilfs-Dummys für DB-Sessions
# -------------------------------------------------------------------

class DummyResultSelectMax:
    """Simuliert SELECT MAX(id) AS max_id FROM boxes"""

    def __init__(self, max_id):
        self._max_id = max_id

    def mappings(self):
        class _M:
            def __init__(self, max_id):
                self._max_id = max_id

            def first(self):
                return {"max_id": self._max_id}

        return _M(self._max_id)


class DummyResultInsert:
    """Simuliert INSERT ... RETURNING id"""

    def __init__(self, new_id):
        self._new_id = new_id

    def scalar_one(self):
        return self._new_id


class DummyResultMappings:
    """Simuliert SELECT id FROM boxes ..."""

    def __init__(self, row):
        self._row = row

    def mappings(self):
        class _M:
            def __init__(self, row):
                self._row = row

            def first(self):
                return self._row

        return _M(self._row)


class DummySessionForCreateBox:
    """
    Simuliert eine Session für create_box():

    1. execute() → SELECT MAX(id) ...
    2. execute() → INSERT ... RETURNING id
    """

    def __init__(self, max_id=0, new_id=1):
        self._max_id = max_id
        self._new_id = new_id
        self.calls = 0
        self.executed = []
        self.committed = False

    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        if self.calls == 0:
            self.calls += 1
            return DummyResultSelectMax(self._max_id)
        else:
            self.calls += 1
            return DummyResultInsert(self._new_id)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class DummySessionForGetBoxId:
    """Simuliert Session für get_box_id_by_code."""

    def __init__(self, row):
        self._row = row
        self.executed = []

    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return DummyResultMappings(self._row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


# -------------------------------------------------------------------
# get_box_id_by_code
# -------------------------------------------------------------------

def test_get_box_id_by_code_returns_id(monkeypatch):
    dummy_session = DummySessionForGetBoxId({"id": 42})
    monkeypatch.setattr(boxes_module, "SessionLocal", lambda: dummy_session)

    result = boxes_module.get_box_id_by_code("BOX-042")
    assert result == 42
    assert len(dummy_session.executed) == 1


def test_get_box_id_by_code_returns_none(monkeypatch):
    dummy_session = DummySessionForGetBoxId(None)
    monkeypatch.setattr(boxes_module, "SessionLocal", lambda: dummy_session)

    result = boxes_module.get_box_id_by_code("BOX-999")
    assert result is None
    assert len(dummy_session.executed) == 1


# -------------------------------------------------------------------
# create_box
# -------------------------------------------------------------------

def test_create_box_auto_generates_code_when_none(monkeypatch):
    """
    Wenn kein box_code übergeben wird, soll automatisch der nächste
    BOX-### Code erzeugt werden.
    """
    dummy_session = DummySessionForCreateBox(max_id=3, new_id=4)
    monkeypatch.setattr(boxes_module, "SessionLocal", lambda: dummy_session)

    new_id = boxes_module.create_box()

    assert new_id == 4
    # zweite execute() sollte das INSERT sein
    assert len(dummy_session.executed) == 2
    _, params = dummy_session.executed[1]
    assert params["code"] == "BOX-004"
    assert dummy_session.committed is True


def test_create_box_with_invalid_code_raises(monkeypatch):
    """
    Ungültige Codes (nicht BOX-### und keine reine Zahl 1–3 Stellen)
    sollen einen ValueError werfen.
    """
    dummy_session = DummySessionForCreateBox(max_id=0, new_id=1)
    monkeypatch.setattr(boxes_module, "SessionLocal", lambda: dummy_session)

    with pytest.raises(ValueError):
        boxes_module.create_box("INVALID-CODE")
