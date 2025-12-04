# app/services/photos_storage.py

import os
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

# ---------------------------------------------------------
# Supabase Setup
# ---------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "photos")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL oder SUPABASE_SERVICE_KEY nicht gesetzt. "
        "Bitte in der .env und den Render-Env-Variablen hinterlegen."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """Entfernt problematische Zeichen aus Dateinamen."""
    safe = "".join(
        c for c in name
        if c.isalnum() or c in ("-", "_", ".", " ")
    ).strip()
    return safe or "upload.jpg"

def _upload_photo_for_loan(loan_id: int, file_storage, kind: str) -> str:
    """
    Gemeinsame Upload-Logik für INITIAL- und RETURN-Fotos.

    kind:
      - "initial"
      - "return"

    Rückgabe:
      - bucket_key (Pfad im Bucket), z.B.:
        "loans/42/initial_20251124_101500_upload.jpg"
        "loans/42/return_20251124_101900_upload.jpg"
    """

    original_name = file_storage.filename or "upload.jpg"
    safe_name = _sanitize_filename(original_name)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bucket_key = f"loans/{loan_id}/{kind.lower()}_{ts}_{safe_name}"

    # Datei als Bytes einlesen
    file_bytes = file_storage.read()
    content_type = file_storage.mimetype or "image/jpeg"

    # Upload zu Supabase mit check
    response = supabase.storage.from_(SUPABASE_BUCKET).upload(
        bucket_key,
        file_bytes,
        {"content-type": content_type},
    )

    # Wenn die Lib ein dict / Objekt mit 'error' zurückgibt:
    if hasattr(response, "get") and response.get("error"):
        raise RuntimeError(f"Fehler beim Upload nach Supabase: {response['error']}")

    return bucket_key


# ---------------------------------------------------------
# Öffentliche Upload-Funktionen
# ---------------------------------------------------------

def upload_initial_photo_for_loan(loan_id: int, file_storage) -> str:
    """Upload eines INITIAL-Fotos."""
    return _upload_photo_for_loan(loan_id, file_storage, kind="initial")


def upload_return_photo_for_loan(loan_id: int, file_storage) -> str:
    """Upload eines RETURN-Fotos."""
    return _upload_photo_for_loan(loan_id, file_storage, kind="return")


# ---------------------------------------------------------
# Lösch- und URL-Utility
# ---------------------------------------------------------

def delete_photo_from_storage(file_path: str) -> None:
    """Löscht eine Datei aus dem Supabase Storage Bucket."""
    print(f"[DEBUG] Supabase: versuche {file_path} zu löschen")
    resp = supabase.storage.from_(SUPABASE_BUCKET).remove([file_path])
    print(f"[DEBUG] Supabase remove response für {file_path}: {resp}")


def get_public_url(file_path: str) -> Optional[str]:
    """Gibt eine öffentliche URL für das Foto zurück (DIRECT URL)."""
    if not file_path:
        return None

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)