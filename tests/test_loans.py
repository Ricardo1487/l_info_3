# tests/test_loans.py

import pytest
from datetime import date, datetime, timezone, timedelta

import app.services.loans as loans_module


# -------------------------------------------------------------------
# Hilfs-Klassen für Dummy-Resultate
# -------------------------------------------------------------------


class DummyResultFirst:
    """Result-Objekt mit .first()."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class DummyResultRowcount:
    """Result-Objekt mit .rowcount."""

    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class DummyResultMappingsAll:
    """
    Simuliert SQLAlchemy-Result mit .mappings().all()
    (und optional .first() auf dem Mappings-Objekt).
    """

    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class DummyResultScalarsAll:
    """
    Simuliert SQLAlchemy-Result mit .scalars().all()
    """

    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


# -------------------------------------------------------------------
# create_loan
# -------------------------------------------------------------------


def test_create_loan_sets_status_open_when_start_today(monkeypatch):
    """Wenn planned_start_date == heute, soll Status 'OPEN' sein."""

    fixed_today = date(2025, 1, 1)

    class DummyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 1, 1, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(loans_module, "datetime", DummyDateTime)

    class DummySession:
        def __init__(self):
            self.executed = []
            self.committed = False

        def execute(self, stmt, params=None):
            self.executed.append({"stmt": stmt, "params": params})

            class DummyResult:
                def scalar_one(self_inner):
                    return 42

            return DummyResult()

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    loan_id = loans_module.create_loan(
        box_id=1,
        contact_email="alice@example.com",
        planned_start_date=fixed_today,
        planned_end_date=fixed_today + timedelta(days=7),
        created_by_user_id=99,
    )

    assert loan_id == 42
    assert dummy_session.committed is True
    assert dummy_session.executed[0]["params"]["status"] == "OPEN"


def test_create_loan_sets_status_upcoming_when_start_in_future(monkeypatch):
    """Wenn planned_start_date > heute, soll Status 'UPCOMING' sein."""

    today = date(2025, 1, 1)

    class DummyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 1, 1, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(loans_module, "datetime", DummyDateTime)

    class DummySession:
        def __init__(self):
            self.executed = []

        def execute(self, stmt, params=None):
            self.executed.append({"stmt": stmt, "params": params})

            class DummyResult:
                def scalar_one(self_inner):
                    return 7

            return DummyResult()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    start = today + timedelta(days=3)
    end = today + timedelta(days=10)

    loan_id = loans_module.create_loan(
        box_id=2,
        contact_email="future@example.com",
        planned_start_date=start,
        planned_end_date=end,
        created_by_user_id=1,
    )

    assert loan_id == 7
    assert dummy_session.executed[0]["params"]["status"] == "UPCOMING"


def test_create_loan_raises_if_end_before_start():
    """Wenn planned_end_date < planned_start_date, soll ValueError fliegen."""
    start = date(2025, 1, 10)
    end = date(2025, 1, 5)

    with pytest.raises(ValueError):
        loans_module.create_loan(
            box_id=1,
            contact_email="x@example.com",
            planned_start_date=start,
            planned_end_date=end,
            created_by_user_id=1,
        )


# -------------------------------------------------------------------
# create_loan_with_validation
# -------------------------------------------------------------------


def test_create_loan_with_validation_requires_all_fields():
    form_data = {"ausgabe": "", "rueckgabe": "", "email": ""}
    with pytest.raises(Exception):
        loans_module.create_loan_with_validation(1, form_data, created_by_user_id=1)


def test_create_loan_with_validation_rejects_past_start(monkeypatch):
    today = date.today()
    yesterday = today - timedelta(days=1)
    form_data = {
        "ausgabe": yesterday.isoformat(),
        "rueckgabe": today.isoformat(),
        "email": "x@example.com",
    }

    # SessionLocal wird benutzt, um Overlap zu prüfen – hier aber egal
    class DummySession:
        def execute(self, stmt, params=None):
            return DummyResultFirst(None)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    with pytest.raises(Exception, match="Ausgabedatum kann nicht in der Vergangenheit liegen."):
        loans_module.create_loan_with_validation(1, form_data, created_by_user_id=1)


def test_create_loan_with_validation_rejects_end_before_start(monkeypatch):
    today = date.today()
    form_data = {
        "ausgabe": (today + timedelta(days=2)).isoformat(),
        "rueckgabe": (today + timedelta(days=1)).isoformat(),
        "email": "x@example.com",
    }

    class DummySession:
        def execute(self, stmt, params=None):
            return DummyResultFirst(None)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    with pytest.raises(Exception, match="Rückgabedatum darf nicht vor dem Ausgabedatum liegen."):
        loans_module.create_loan_with_validation(1, form_data, created_by_user_id=1)


def test_create_loan_with_validation_rejects_overlap(monkeypatch):
    today = date.today()
    form_data = {
        "ausgabe": today.isoformat(),
        "rueckgabe": (today + timedelta(days=1)).isoformat(),
        "email": "x@example.com",
    }

    class DummySession:
        def execute(self, stmt, params=None):
            # simuliert, dass ein Overlap gefunden wurde
            return DummyResultFirst((1,))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    with pytest.raises(Exception, match="bereits ausgeliehen"):
        loans_module.create_loan_with_validation(1, form_data, created_by_user_id=1)


def test_create_loan_with_validation_calls_create_loan(monkeypatch):
    today = date.today()
    form_data = {
        "ausgabe": today.isoformat(),
        "rueckgabe": (today + timedelta(days=1)).isoformat(),
        "email": "ok@example.com",
    }

    class DummySession:
        def execute(self, stmt, params=None):
            # kein Overlap
            return DummyResultFirst(None)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    called = {}

    def fake_create_loan(box_id, contact_email, planned_start_date, planned_end_date, created_by_user_id):
        called["args"] = {
            "box_id": box_id,
            "email": contact_email,
            "start": planned_start_date,
            "end": planned_end_date,
            "user": created_by_user_id,
        }
        return 123

    monkeypatch.setattr(loans_module, "create_loan", fake_create_loan)

    loan_id = loans_module.create_loan_with_validation(5, form_data, created_by_user_id=7)
    assert loan_id == 123
    assert called["args"]["box_id"] == 5
    assert called["args"]["email"] == "ok@example.com"
    assert called["args"]["user"] == 7


# -------------------------------------------------------------------
# mark_overdue_loans
# -------------------------------------------------------------------


def test_mark_overdue_loans_updates_and_returns_rowcount(monkeypatch):
    class DummySession:
        def __init__(self):
            self.committed = False

        def execute(self, stmt, params=None):
            assert "UPDATE loans" in str(stmt)
            return DummyResultRowcount(3)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    rc = loans_module.mark_overdue_loans(date(2025, 1, 10))
    assert rc == 3
    assert dummy_session.committed is True


# -------------------------------------------------------------------
# get_planned_periods_for_box
# -------------------------------------------------------------------


def test_get_planned_periods_for_box_returns_periods(monkeypatch):
    class DummySession:
        def execute(self, stmt, params=None):
            rows = [
                {"planned_start_date": date(2025, 1, 1), "planned_end_date": date(2025, 1, 5)},
                {"planned_start_date": date(2025, 1, 10), "planned_end_date": date(2025, 1, 12)},
            ]
            return DummyResultMappingsAll(rows)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    periods = loans_module.get_planned_periods_for_box(1)
    assert periods == [
        {"start": date(2025, 1, 1), "end": date(2025, 1, 5)},
        {"start": date(2025, 1, 10), "end": date(2025, 1, 12)},
    ]


# -------------------------------------------------------------------
# compare_object_sets
# -------------------------------------------------------------------


def test_compare_object_sets_detects_missing():
    initial = {"Kabel": 2, "Maus": 1}
    returned = {"Kabel": 1, "Maus": 1}
    missing = loans_module.compare_object_sets(initial, returned)
    assert missing == {"Kabel": 1}


def test_compare_object_sets_no_missing_if_equal():
    initial = {"Kabel": 2}
    returned = {"Kabel": 2}
    missing = loans_module.compare_object_sets(initial, returned)
    assert missing == {}


# -------------------------------------------------------------------
# get_detected_objects_for_photo
# -------------------------------------------------------------------


def test_get_detected_objects_for_photo_aggregates_quantities():
    """
    Die Funktion erwartet bereits aggregierte Daten (pro label eine Zeile).
    Wir simulieren genau diesen Fall.
    """

    class DummySession:
        def execute(self, stmt, params=None):
            rows = [
                {"label": "Kabel", "qty": 3},
                {"label": "Adapter", "qty": 1},
            ]
            return DummyResultMappingsAll(rows)

    dummy_session = DummySession()

    result = loans_module.get_detected_objects_for_photo(
        dummy_session, loan_id=1, photo_type="INITIAL"
    )

    assert result == {"Kabel": 3, "Adapter": 1}


# -------------------------------------------------------------------
# delete_loan_if_fully_returned
# -------------------------------------------------------------------


def test_delete_loan_if_fully_returned_returns_false_if_not_exists(monkeypatch):
    class DummySession:
        def __init__(self):
            self.calls = 0

        def execute(self, stmt, params=None):
            self.calls += 1
            # erster Aufruf: SELECT status, actual_end_date
            return DummyResultMappingsAll([])  # .first() -> None

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    called_paths = []

    def fake_delete_photo(path):
        called_paths.append(path)

    monkeypatch.setattr(loans_module, "delete_photo_from_storage", fake_delete_photo)

    res = loans_module.delete_loan_if_fully_returned(99)
    assert res is False
    assert dummy_session.calls == 1
    assert called_paths == []


def test_delete_loan_if_fully_returned_returns_false_if_not_returned(monkeypatch):
    class DummySession:
        def __init__(self):
            self.calls = 0

        def execute(self, stmt, params=None):
            self.calls += 1
            # status != 'RETURNED' oder actual_end_date ist None
            row = {"status": "OPEN", "actual_end_date": None}
            return DummyResultMappingsAll([row])

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    res = loans_module.delete_loan_if_fully_returned(1)
    assert res is False
    assert dummy_session.calls == 1


def test_delete_loan_if_fully_returned_deletes_and_returns_true(monkeypatch):
    class DummySession:
        def __init__(self):
            self.calls = 0
            self.committed = False
            self.executed = []

        def execute(self, stmt, params=None):
            self.calls += 1
            self.executed.append({"stmt": stmt, "params": params})

            if self.calls == 1:
                # SELECT status, actual_end_date
                row = {"status": "RETURNED", "actual_end_date": date(2025, 1, 1)}
                return DummyResultMappingsAll([row])
            elif self.calls == 2:
                # SELECT file_path FROM photos
                return DummyResultScalarsAll(["a.jpg", "b.jpg"])
            else:
                # DELETEs – Rückgabewert ist hier egal
                return DummyResultRowcount(1)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    deleted_paths = []

    def fake_delete_photo(path):
        deleted_paths.append(path)

    monkeypatch.setattr(loans_module, "delete_photo_from_storage", fake_delete_photo)

    res = loans_module.delete_loan_if_fully_returned(5)
    assert res is True
    assert deleted_paths == ["a.jpg", "b.jpg"]
    assert dummy_session.committed is True
    # mindestens 2 Aufrufe: SELECT loan, SELECT photos
    assert dummy_session.calls >= 2


# -------------------------------------------------------------------
# get_initial_contents_for_all_loans
# -------------------------------------------------------------------


def test_get_initial_contents_for_all_loans_builds_nested_dict(monkeypatch):
    class DummySession:
        def execute(self, stmt, params=None):
            rows = [
                {"loan_id": 1, "label": "Kabel", "qty": 2},
                {"loan_id": 1, "label": "Adapter", "qty": 1},
                {"loan_id": 2, "label": "Kabel", "qty": 1},
            ]
            return DummyResultMappingsAll(rows)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(loans_module, "SessionLocal", lambda: DummySession())

    data = loans_module.get_initial_contents_for_all_loans()
    assert data == {
        1: {"Kabel": 2, "Adapter": 1},
        2: {"Kabel": 1},
    }


# -------------------------------------------------------------------
# update_loan_basic_data
# -------------------------------------------------------------------


def test_update_loan_basic_data_raises_if_start_after_end():
    start = date(2025, 1, 10)
    end = date(2025, 1, 5)
    with pytest.raises(ValueError):
        loans_module.update_loan_basic_data(
            loan_id=1,
            contact_email="x@example.com",
            planned_start_date=start,
            planned_end_date=end,
        )


def test_update_loan_basic_data_updates_when_valid(monkeypatch):
    class DummySession:
        def __init__(self):
            self.executed = []
            self.committed = False

        def execute(self, stmt, params=None):
            self.executed.append(params)
            return DummyResultRowcount(1)

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_session = DummySession()
    monkeypatch.setattr(loans_module, "SessionLocal", lambda: dummy_session)

    start = date(2025, 1, 1)
    end = date(2025, 1, 10)

    loans_module.update_loan_basic_data(
        loan_id=3,
        contact_email="user@example.com",
        planned_start_date=start,
        planned_end_date=end,
    )

    assert dummy_session.committed is True
    assert dummy_session.executed[0]["loan_id"] == 3
    assert dummy_session.executed[0]["email"] == "user@example.com"
    assert dummy_session.executed[0]["start_date"] == start
    assert dummy_session.executed[0]["end_date"] == end
