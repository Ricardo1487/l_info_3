# tests/test_web_home.py

import sys
import types
from datetime import date

import pytest

# ---------------------------------------------------------------------------
# 1) Dummy-"supabase"-Modul registrieren, bevor app.web importiert wird
# ---------------------------------------------------------------------------

dummy_supabase = types.ModuleType("supabase")


class DummySupabaseClient:
    """
    Minimaler Client, genug damit app.services.photos_storage
    beim Import nicht crasht.
    """

    class _DummyStorageBucket:
        def upload(self, *args, **kwargs):
            return {"ok": True}

        def remove(self, *args, **kwargs):
            return {"ok": True}

    class _DummyStorage:
        def from_(self, bucket_name):
            return DummySupabaseClient._DummyStorageBucket()

    def __init__(self, *args, **kwargs):
        # wird bei create_client(...) aufgerufen
        self.storage = DummySupabaseClient._DummyStorage()


def dummy_create_client(url, key):
    # Wird beim Import von photos_storage einmal aufgerufen
    return DummySupabaseClient()


dummy_supabase.Client = DummySupabaseClient
dummy_supabase.create_client = dummy_create_client

# Dieses Modul wird benutzt, wenn "from supabase import create_client, Client"
# irgendwo im Code steht.
sys.modules.setdefault("supabase", dummy_supabase)

# ---------------------------------------------------------------------------
# 2) Jetzt erst Flask-App importieren
# ---------------------------------------------------------------------------

import app.web as web_module  # noqa: E402


# ---------------------------------------------------------------------------
# 3) Gemeinsame Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """
    Flask test_client mit eingeloggt-Session und gemockten Services
    für die home()-Route.
    """

    # Dummy-Leihen, so wie sie list_loans() liefern könnte
    loans = [
        {
            "id": 1,
            "box_code": "BOX-001",
            "contact_email": "alice@example.org",
            "status": "OPEN",
            "planned_start_date": date(2025, 1, 1),
            "planned_end_date": date(2025, 1, 10),
        },
        {
            "id": 2,
            "box_code": "BOX-002",
            "contact_email": "bob@example.org",
            "status": "RETURNED",
            "planned_start_date": date(2025, 2, 1),
            "planned_end_date": date(2025, 2, 10),
        },
    ]

    # Funktionen, die home() benutzt, stubben:
    monkeypatch.setattr(web_module, "list_loans", lambda: loans)
    monkeypatch.setattr(web_module, "mark_overdue_loans", lambda today: None)
    monkeypatch.setattr(web_module, "log_overdue_loans", lambda _loans: None)

    def fake_compute_stats(_loans):
        return {
            "total": len(_loans),
            "open": sum(1 for l in _loans if l["status"] == "OPEN"),
            "returned": sum(1 for l in _loans if l["status"] == "RETURNED"),
            "missing": 0,
            "overdue": 0,
        }

    monkeypatch.setattr(web_module, "compute_loan_stats", fake_compute_stats)

    def fake_filter(loans_arg, contact, status):
        result = list(loans_arg)
        if contact:
            s = contact.lower()
            result = [l for l in result if s in l["contact_email"].lower()]
        if status:
            result = [l for l in result if l["status"] == status]
        return result

    monkeypatch.setattr(web_module, "filter_loans", fake_filter)

    def fake_sort(loans_arg, sort_field, sort_dir):
        # Für diesen Test reicht eine einfache Sortierung nach ID
        return sorted(loans_arg, key=lambda l: l["id"], reverse=(sort_dir == "desc"))

    monkeypatch.setattr(web_module, "sort_loans", fake_sort)

    # get_initial_contents_for_all_loans wird in home() dynamisch importiert
    import app.services.loans as loans_service

    monkeypatch.setattr(
        loans_service,
        "get_initial_contents_for_all_loans",
        lambda: {1: {"mouse": 1}, 2: {"keyboard": 1}},
    )

    # Test-Client mit Session (damit login_required zufrieden ist)
    app = web_module.app
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["user_role"] = web_module.ROLE_ADMIN
            sess["user_name"] = "Test User"
        yield client


# ---------------------------------------------------------------------------
# 4) Tests für die home()-Route
# ---------------------------------------------------------------------------


def test_home_redirects_to_login_when_not_logged_in():
    """Ohne Session soll / auf /login umleiten."""
    app = web_module.app
    with app.test_client() as c:
        resp = c.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


def test_home_renders_overview(client):
    """Mit Session liefert / einen 200er und die Übersicht."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Überschrift aus index.html
    assert "Boxenübersicht" in html
    # Dummy-Leihen sollten auftauchen
    assert "BOX-001" in html
    assert "alice@example.org" in html


def test_home_filters_by_box_parameter(client):
    """
    Wenn ?box=BOX-002 gesetzt ist, soll nur diese Box
    in der Liste der Leihen auftauchen.
    """
    resp = client.get("/?box=BOX-002")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    assert "BOX-002" in html
    # durch den Boxfilter sollte BOX-001 verschwinden
    assert "BOX-001" not in html
