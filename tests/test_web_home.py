# tests/test_web_home.py

from datetime import date

import pytest
from flask import session as flask_session


@pytest.fixture
def client(monkeypatch):
    """
    Stellt einen Flask-Testclient bereit, bei dem:
      - alle Datenbank- und Hintergrundfunktionen gemockt sind
      - eine gültige Sitzung (eingeloggter User) existiert
    """
    import app.web as web_module
    import app.services.loans as loans_module

    # -------------------------------------------------
    # Dummy-Daten für Leihen
    # -------------------------------------------------
    dummy_loans = [
        {
            "id": 1,
            "box_code": "BOX-001",
            "status": "OPEN",
            "planned_start_date": date(2025, 1, 1),
            "planned_end_date": date(2025, 1, 7),
            "contact_email": "alice@example.com",
        },
        {
            "id": 2,
            "box_code": "BOX-002",
            "status": "RETURNED",
            "planned_start_date": date(2025, 1, 3),
            "planned_end_date": date(2025, 1, 10),
            "contact_email": "bob@example.com",
        },
    ]

    # -------------------------------------------------
    # Funktionen aus web.py / loan_views / loans mocken
    # -------------------------------------------------

    # 0) mark_overdue_loans & log_overdue_loans: nichts tun
    monkeypatch.setattr(web_module, "mark_overdue_loans", lambda today: None)
    monkeypatch.setattr(web_module, "log_overdue_loans", lambda loans: None)

    # 1) list_loans: gib unsere Dummy-Leihen zurück
    monkeypatch.setattr(web_module, "list_loans", lambda: dummy_loans)

    # 2) compute_loan_stats: muss alle Keys liefern, die web.py erwartet
    def fake_compute_loan_stats(loans):
        return {
            "total": len(loans),
            "open": sum(1 for l in loans if l.get("status") == "OPEN"),
            "returned": sum(1 for l in loans if l.get("status") == "RETURNED"),
            "missing": sum(1 for l in loans if l.get("status") == "MISSING_ITEMS"),
            "overdue": sum(1 for l in loans if l.get("status") == "OVERDUE"),
            # neue Felder, die in home() verwendet werden:
            "upcoming": 0,
            "recent": [],
        }

    monkeypatch.setattr(web_module, "compute_loan_stats", fake_compute_loan_stats)

    # 3) filter_loans: einfache Filter-Logik nach Kontakt & Status
    def fake_filter_loans(loans, contact=None, status=None):
        result = list(loans)
        if contact:
            result = [
                l
                for l in result
                if contact.lower() in (l.get("contact_email") or "").lower()
            ]
        if status:
            result = [l for l in result if l.get("status") == status]
        return result

    monkeypatch.setattr(web_module, "filter_loans", fake_filter_loans)

    # 4) sort_loans: wir sortieren hier nicht wirklich, geben nur zurück
    def fake_sort_loans(loans, sort_field, sort_dir):
        return list(loans)

    monkeypatch.setattr(web_module, "sort_loans", fake_sort_loans)

    # 5) get_initial_contents_for_all_loans:
    #    wird in home() dynamisch aus app.services.loans importiert
    def fake_get_initial_contents_for_all_loans():
        return {
            1: {"Kabel": 2},
            2: {"Adapter": 1},
        }

    # Wichtig: direkt im loans-Modul patchen
    monkeypatch.setattr(
        loans_module,
        "get_initial_contents_for_all_loans",
        fake_get_initial_contents_for_all_loans,
    )

    # -------------------------------------------------
    # Flask-Testclient mit eingeloggtem User
    # -------------------------------------------------
    app = web_module.app
    app.config["TESTING"] = True
    client = app.test_client()

    # Session füllen, damit @login_required durchgeht
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_role"] = web_module.ROLE_HIWI
        sess["user_name"] = "Test User"

    return client


# --------------------------------------------------------------------
# Tests für die Übersicht (/)
# --------------------------------------------------------------------


def test_home_renders_overview(client):
    """
    Mit Session liefert / einen 200er und zeigt beide Dummy-Leihen an.
    """
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    # Beide Boxen sollten im HTML vorkommen
    assert "BOX-001" in html
    assert "BOX-002" in html


def test_home_filters_by_box_parameter(client):
    """
    Wenn ?box=BOX-002 gesetzt ist, soll nur diese Box
    in der Liste der Leihen auftauchen.
    """
    resp = client.get("/?box=BOX-002")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert "BOX-002" in html
    assert "BOX-001" not in html


def test_home_filters_by_status_parameter(client):
    """
    Wenn ?status=RETURNED gesetzt ist, soll nur die zurückgegebene
    Leihe (BOX-002) angezeigt werden.
    """
    resp = client.get("/?status=RETURNED")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert "BOX-002" in html
    assert "BOX-001" not in html


# --------------------------------------------------------------------
# Tests für /login
# --------------------------------------------------------------------


def test_login_get_renders_login_page(client):
    """
    Ein GET auf /login sollte die Login-Seite anzeigen (Status 200).
    """
    resp = client.get("/login")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert "Login" in html  # grobe Prüfung, hängt vom Template-Text ab


def test_login_invalid_credentials_shows_error(client, monkeypatch):
    """
    Wenn die E-Mail nicht gefunden wird, soll eine Fehlermeldung
    'Ungültige E-Mail oder Passwort.' angezeigt werden.
    """
    import app.web as web_module

    # get_user_by_email soll so tun, als gäbe es keinen User
    monkeypatch.setattr(web_module, "get_user_by_email", lambda email: None)

    resp = client.post(
        "/login",
        data={"email": "unknown@example.com", "password": "geheim"},
        follow_redirects=False,
    )
    # Bleibt auf der Login-Seite
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert "Ungültige E-Mail oder Passwort." in html


def test_login_valid_credentials_redirects_home(client, monkeypatch):
    """
    Bei korrekten Logindaten soll ein Redirect auf die Übersicht (/) erfolgen.
    """
    import app.web as web_module

    # Dummy-User, den get_user_by_email zurückgeben soll
    dummy_user = {
        "id": 99,
        "username": "Demo User",
        "email": "demo@example.com",
        "password_hash": "dummy-hash",
        "role": web_module.ROLE_HIWI,
    }

    # User wird gefunden
    monkeypatch.setattr(web_module, "get_user_by_email", lambda email: dummy_user)
    # Passwort-Check immer erfolgreich machen
    monkeypatch.setattr(web_module.bcrypt, "checkpw", lambda pw, h: True)

    resp = client.post(
        "/login",
        data={"email": "demo@example.com", "password": "irgendwas"},
        follow_redirects=False,
    )

    # Nach erfolgreichem Login sollte ein Redirect kommen
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
