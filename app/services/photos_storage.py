# app/services/photos_storage.py

import os
from datetime import datetime
from typing import Optional, Any

# ----------------------------------------------------
# 1) Supabase-Import robust machen
# ----------------------------------------------------
try:
    from supabase import create_client, Client
    SUPABASE_LIB_AVAILABLE = True
except Exception:
    # Lokale Umgebung ohne funktionierendes Supabase-Paket
    create_client = None  # type: ignore
    Client = Any          # type: ignore
    SUPABASE_LIB_AVAILABLE = False

# ----------------------------------------------------
# 2) Konfiguration aus Umgebungsvariablen
# ----------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "photos")

# Supabase-Client (oder None, wenn lokal kaputt/nicht konfiguriert)
supabase: Optional["Client"] = None

if SUPABASE_LIB_AVAILABLE and SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        # Standardfall: auf Render / richtiger Umgebung
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)  # type: ignore
    except TypeError:
        # typischer Fehler: Client.__init__() got an unexpected keyword argument 'proxy'
        # => lokal benutzen wir einfach keinen Supabase-Client
        supabase = None


def _ensure_supabase() -> None:
    """
    Stellt sicher, dass Supabase verfügbar ist.
    Lokal (wo die Lib-Version Probleme macht) werfen wir eine klare Meldung,
    statt schon beim Import abzustürzen.
    """
    if supabase is None:
        raise RuntimeError(
            "Supabase-Foto-Upload ist in dieser Umgebung nicht verfügbar. "
            "Lokal kannst du die App ohne Foto-Funktion nutzen; "
            "auf dem Server mit korrekt konfigurierter Supabase-Version funktioniert es."
        )


# ----------------------------------------------------
# 3) Hilfsfunktionen + Upload-API
# ----------------------------------------------------
def _sanitize_filename(name: str) -> str:
    """Entfernt problematische Zeichen aus Dateinamen."""
    return "".join(
        c for c in name if c.isalnum() or c in ("-", "_", ".", " ")
    ).strip() or "upload.jpg"


def upload_initial_photo_for_loan(loan_id: int, file_storage) -> str:
    """
    Lädt ein INITIAL-Foto direkt in den Supabase-Bucket hoch,
    unter einem Pfad wie: loans/<loan_id>/initial_<timestamp>_<filename>.

    Rückgabe:
      - bucket_key (Pfad im Bucket), z.B. "loans/42/initial_20251124_101500_boxfoto.jpg"
    """
    # Sicherstellen, dass Supabase überhaupt verfügbar ist
    _ensure_supabase()

    # Original-Dateiname & Content-Type vom Upload
    original_name = file_storage.filename or "upload.jpg"
    safe_name = _sanitize_filename(original_name)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bucket_key = f"loans/{loan_id}/initial_{ts}_{safe_name}"

    # Datei als Bytes einlesen
    file_bytes = file_storage.read()
    content_type = file_storage.mimetype or "image/jpeg"

    # Upload zu Supabase
    supabase.storage.from_(SUPABASE_BUCKET).upload(  # type: ignore[union-attr]
        bucket_key,
        file_bytes,
        {"content-type": content_type},
    )

    # Hinweis: file_storage-Stream ist nun "verbraucht",
    # aber wir brauchen ihn nach dem Upload auch nicht mehr.

    return bucket_key
