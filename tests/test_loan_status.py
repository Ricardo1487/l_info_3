# tests/test_loan_status.py

import pytest
from datetime import date

import app.services.loan_status as ls_module


# ---------------------------------------------------
# Hilfs-Klasse für Result mit rowcount
# ---------------------------------------------------
class DummyResultRowcount:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


# ---------------------------------------------------
# mark_overdue_loans
# ---------------------------------------------------
def test_mark_overdue_loans_updates_and_returns_rowcount(monkeypatch):
    """Prüft, dass mark_overdue_loans ein UPDATE ausführt und rowcount zurückgibt."""

    class DummySession:
        def __init__(self):
            self.executed = []
            self.committed = False

        def execute(self, stmt, params=None):
            # Statement grob prüfen
            s = str(stmt)
            assert "UPDATE loans" in s
            assert "SET status = 'OVERDUE'" in s
            assert "planned_end_date < :today" in s
            self.executed.append({"stmt": stmt, "params": params})
            return DummyResultRowcount(5)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(ls_module, "SessionLocal", lambda: dummy_session)

    rc = ls_module.mark_overdue_loans(date(2025, 1, 10))

    assert rc == 5
    assert dummy_session.committed is True
    # Parameterprüfung
    assert dummy_session.executed[0]["params"]["today"] == date(2025, 1, 10)


# ---------------------------------------------------
# activate_upcoming_loans
# ---------------------------------------------------
def test_activate_upcoming_loans_updates_and_returns_rowcount(monkeypatch):
    """Prüft, dass UPCOMING → OPEN aktiviert wird und rowcount zurückkommt."""

    class DummySession:
        def __init__(self):
            self.executed = []
            self.committed = False

        def execute(self, stmt, params=None):
            s = str(stmt)
            assert "UPDATE loans" in s
            assert "SET status = 'OPEN'" in s
            assert "status = 'UPCOMING'" in s
            assert "planned_start_date <= :today" in s
            self.executed.append({"stmt": stmt, "params": params})
            return DummyResultRowcount(3)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(ls_module, "SessionLocal", lambda: dummy_session)

    rc = ls_module.activate_upcoming_loans(date(2025, 2, 1))

    assert rc == 3
    assert dummy_session.committed is True
    assert dummy_session.executed[0]["params"]["today"] == date(2025, 2, 1)


# ---------------------------------------------------
# _close_loan (interne Helper-Funktion)
# ---------------------------------------------------
def test_close_loan_updates_single_loan(monkeypatch):
    """Prüft, dass _close_loan das UPDATE mit den richtigen Parametern ausführt."""

    class DummySession:
        def __init__(self):
            self.executed = []
            self.committed = False

        def execute(self, stmt, params=None):
            self.executed.append({"stmt": stmt, "params": params})
            # rowcount ist egal – wird nirgendwo verwendet
            return DummyResultRowcount(1)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(ls_module, "SessionLocal", lambda: dummy_session)

    ls_module._close_loan(
        loan_id=42,
        new_status="RETURNED",
        actual_end_date=date(2025, 3, 1),
        closed_by_user_id=7,
    )

    assert dummy_session.committed is True
    assert len(dummy_session.executed) == 1
    params = dummy_session.executed[0]["params"]
    assert params["loan_id"] == 42
    assert params["status"] == "RETURNED"
    assert params["actual_end_date"] == date(2025, 3, 1)
    assert params["closed_by_user_id"] == 7


# ---------------------------------------------------
# return_loan
# ---------------------------------------------------
def test_return_loan_calls_close_loan_with_returned(monkeypatch):
    """return_loan soll _close_loan mit Status 'RETURNED' aufrufen."""

    called = {}

    def fake_close_loan(loan_id, new_status, actual_end_date, closed_by_user_id):
        called["loan_id"] = loan_id
        called["status"] = new_status
        called["date"] = actual_end_date
        called["user"] = closed_by_user_id

    # _close_loan im Modul mocken
    monkeypatch.setattr(ls_module, "_close_loan", fake_close_loan)

    ls_module.return_loan(
        loan_id=5,
        actual_end_date=date(2025, 4, 1),
        closed_by_user_id=99,
    )

    assert called["loan_id"] == 5
    assert called["status"] == "RETURNED"
    assert called["date"] == date(2025, 4, 1)
    assert called["user"] == 99


# ---------------------------------------------------
# return_with_missing_items
# ---------------------------------------------------
def test_return_with_missing_items_calls_close_loan_with_missing(monkeypatch):
    """return_with_missing_items soll _close_loan mit Status 'MISSING_ITEMS' aufrufen."""

    called = {}

    def fake_close_loan(loan_id, new_status, actual_end_date, closed_by_user_id):
        called["loan_id"] = loan_id
        called["status"] = new_status
        called["date"] = actual_end_date
        called["user"] = closed_by_user_id

    monkeypatch.setattr(ls_module, "_close_loan", fake_close_loan)

    ls_module.return_with_missing_items(
        loan_id=8,
        actual_end_date=date(2025, 5, 1),
        closed_by_user_id=123,
    )

    assert called["loan_id"] == 8
    assert called["status"] == "MISSING_ITEMS"
    assert called["date"] == date(2025, 5, 1)
    assert called["user"] == 123
