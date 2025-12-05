# tests/test_photos_storage.py

from datetime import datetime
from types import SimpleNamespace
import io

import pytest


# ---------------------------------------------------------
# Dummy-Helfer für die Tests
# ---------------------------------------------------------

class DummyFileStorage:
    """
    Simuliert das FileStorage-Objekt von Flask.
    """
    def __init__(self, filename="foto.jpg", mimetype="image/jpeg", data=b"dummy-bytes"):
        self.filename = filename
        self.mimetype = mimetype
        self._data = data
        # wird von unserer Funktion zwar nicht genutzt, aber real existiert es auch
        self.stream = io.BytesIO(data)

    def read(self):
        # In unserem Produktivcode wird read() genau einmal aufgerufen
        return self._data


class DummyBucket:
    """
    Simuliert den Bucket: .upload(), .remove(), .get_public_url()
    und speichert die Aufrufe, damit wir sie prüfen können.
    """
    def __init__(self):
        self.upload_calls = []
        self.remove_calls = []
        self.public_url_calls = []

    def upload(self, key, file_bytes, options):
        self.upload_calls.append((key, file_bytes, options))
        # echte Supabase-Client gibt irgendwas zurück; wir geben ein dict ohne error zurück
        return {}

    def remove(self, paths):
        self.remove_calls.append(list(paths))
        return {}

    def get_public_url(self, key):
        self.public_url_calls.append(key)
        return f"https://cdn.example.com/{key}"


class DummyStorage:
    """
    Simuliert supabase.storage.from_(bucket_name).
    """
    def __init__(self, bucket: DummyBucket):
        self.bucket = bucket
        self.last_bucket_name = None

    def from_(self, bucket_name: str):
        self.last_bucket_name = bucket_name
        return self.bucket


# ---------------------------------------------------------
# Fixture: Modul + gemockter Supabase-Client
# ---------------------------------------------------------

@pytest.fixture
def photos_module(monkeypatch):
    """
    Lädt app.services.photos_storage und ersetzt darin:
      - supabase durch einen Dummy
      - SUPABASE_BUCKET durch 'test-bucket'
    """
    import app.services.photos_storage as ps

    bucket = DummyBucket()
    storage = DummyStorage(bucket)
    dummy_supabase = SimpleNamespace(storage=storage)

    # supabase-Client im Modul ersetzen
    monkeypatch.setattr(ps, "supabase", dummy_supabase)
    # Bucket-Name fix setzen, damit wir ihn prüfen können
    monkeypatch.setattr(ps, "SUPABASE_BUCKET", "test-bucket")

    return ps, bucket, storage


# ---------------------------------------------------------
# Tests für _sanitize_filename
# ---------------------------------------------------------

def test_sanitize_filename_normal_chars(photos_module):
    ps, _, _ = photos_module

    result = ps._sanitize_filename("Box Foto!!.jpg")
    # "!" ist nicht erlaubt → wird entfernt
    assert result == "Box Foto.jpg"


def test_sanitize_filename_all_invalid_falls_back_to_default(photos_module):
    ps, _, _ = photos_module

    result = ps._sanitize_filename("???###")
    # alles ungültige Zeichen → Fallback "upload.jpg"
    assert result == "upload.jpg"


# ---------------------------------------------------------
# Tests für Upload-Funktionen
# ---------------------------------------------------------

def test_upload_initial_photo_builds_correct_key_and_calls_supabase(photos_module, monkeypatch):
    ps, bucket, storage = photos_module

    # Zeit einfrieren, damit wir einen deterministischen Pfad bekommen
    class FakeDatetime:
        @classmethod
        def utcnow(cls):
            return datetime(2025, 1, 2, 3, 4, 5)  # 20250102_030405

        # strftime muss auf dem Rückgabewert laufen → das ist ein echtes datetime-Objekt
        # FakeDatetime selbst braucht kein strftime

    # Modul-internen Namen "datetime" überschreiben
    monkeypatch.setattr(ps, "datetime", FakeDatetime)

    file_obj = DummyFileStorage(
        filename="Box Foto!!.jpg",
        mimetype="image/png",
        data=b"test-bytes",
    )

    key = ps.upload_initial_photo_for_loan(42, file_obj)

    # Pfad sollte exakt so aussehen:
    assert key == "loans/42/initial_20250102_030405_Box Foto.jpg"

    # Richtiger Bucket wurde verwendet
    assert storage.last_bucket_name == "test-bucket"

    # Upload wurde genau einmal aufgerufen
    assert len(bucket.upload_calls) == 1
    up_key, up_bytes, up_options = bucket.upload_calls[0]
    assert up_key == key
    assert up_bytes == b"test-bytes"
    assert up_options["content-type"] == "image/png"


def test_upload_return_photo_uses_return_prefix(photos_module, monkeypatch):
    ps, bucket, storage = photos_module

    class FakeDatetime:
        @classmethod
        def utcnow(cls):
            return datetime(2025, 1, 2, 3, 4, 5)

    monkeypatch.setattr(ps, "datetime", FakeDatetime)

    file_obj = DummyFileStorage(filename="adapter.jpg")

    key = ps.upload_return_photo_for_loan(7, file_obj)

    assert key == "loans/7/return_20250102_030405_adapter.jpg"
    assert storage.last_bucket_name == "test-bucket"
    assert len(bucket.upload_calls) == 1
    assert bucket.upload_calls[0][0] == key


# ---------------------------------------------------------
# Tests für delete_photo_from_storage und get_public_url
# ---------------------------------------------------------

def test_delete_photo_from_storage_calls_remove(photos_module):
    ps, bucket, _ = photos_module

    ps.delete_photo_from_storage("loans/1/initial_foo.jpg")

    assert bucket.remove_calls == [["loans/1/initial_foo.jpg"]]


def test_get_public_url_returns_value_from_supabase(photos_module):
    ps, bucket, _ = photos_module

    url = ps.get_public_url("loans/3/initial_bar.jpg")

    assert url == "https://cdn.example.com/loans/3/initial_bar.jpg"
    assert bucket.public_url_calls == ["loans/3/initial_bar.jpg"]


def test_get_public_url_none_if_empty_path(photos_module):
    ps, bucket, _ = photos_module

    url = ps.get_public_url("")
    assert url is None
    # es darf kein Call an Supabase stattfinden
    assert bucket.public_url_calls == []
