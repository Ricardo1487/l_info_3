from pathlib import Path
from app.services import email_mock
from app.services.loan_views import log_overdue_loans
from datetime import date


def test_email_mock_writes_log_file(tmp_path, monkeypatch):
    # LOG_FILE temporär umleiten
    test_log = tmp_path / "emails.log"
    monkeypatch.setattr(email_mock, "LOG_FILE", test_log)

    email_mock.send_email(
        to="test@example.com",
        subject="Test",
        body="Dies ist eine Testmail.",
        category="test",
        metadata={"loan_id": 1},
    )

    assert test_log.exists()
    content = test_log.read_text(encoding="utf-8")
    assert "test@example.com" in content
    assert "Test" in content
    assert "loan_id" in content

def test_log_overdue_loans_triggers_email(tmp_path, monkeypatch):
    """
    Prüft, dass log_overdue_loans den E-Mail-Mock aufruft,
    wenn eine Leihe überfällig ist.
    """

    # LOG_FILE temporär umleiten
    test_log = tmp_path / "emails.log"
    monkeypatch.setattr(email_mock, "LOG_FILE", test_log)

    # Datum von gestern → überfällig
    yesterday = date.today().replace(day=max(1, date.today().day - 1))

    # Dummy-Leihe, die überfällig ist
    loans = [
        {
            "id": 1,
            "box_code": "BOX-001",
            "contact_email": "person@example.com",
            "planned_end_date": yesterday,
            "status": "OPEN",
        }
    ]

    # Funktion ausführen
    log_overdue_loans(loans)

    # Logfile sollte jetzt existieren
    assert test_log.exists()

    # Inhalt prüfen (richtige Mail Adresse und "overdue" in Nachricht)
    content = test_log.read_text(encoding="utf-8")
    assert "person@example.com" in content
    assert "overdue" in content.lower() or "notice" in content.lower()