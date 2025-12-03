# app/services/photos_storage.py

import os
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "photos")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL oder SUPABASE_SERVICE_KEY nicht gesetzt. "
        "Bitte in der .env und den Render-Env-Variablen hinterlegen."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _sanitize_filename(name: str) -> str:
    """Entfernt problematische Zeichen aus Dateinamen."""
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", ".", " ")).strip() or "upload.jpg"


def upload_initial_photo_for_loan(loan_id: int, file_storage) -> str:
    """
    Lädt ein INITIAL-Foto direkt in den Supabase-Bucket hoch,
    unter einem Pfad wie: loans/<loan_id>/initial_<timestamp>_<filename>.

    Rückgabe:
      - bucket_key (Pfad im Bucket), z.B. "loans/42/initial_20251124_101500_boxfoto.jpg"
    """

    # Original-Dateiname & Content-Type vom Upload
    original_name = file_storage.filename or "upload.jpg"
    safe_name = _sanitize_filename(original_name)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bucket_key = f"loans/{loan_id}/initial_{ts}_{safe_name}"

    # Datei als Bytes einlesen
    file_bytes = file_storage.read()
    content_type = file_storage.mimetype or "image/jpeg"

    # Upload zu Supabase
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        bucket_key,
        file_bytes,
        {"content-type": content_type}
    )

    # Hinweis: file_storage-Stream ist nun "verbraucht",
    # aber wir brauchen ihn nach dem Upload auch nicht mehr.

    return bucket_key

# app/services/photos_storage.py

def delete_photo_from_storage(file_path: str) -> None:
    """
    Löscht eine Datei im Storage-Bucket anhand ihres Pfads.
    `file_path` ist derselbe String wie in photos.file_path gespeichert.
    """
    print(f"[DEBUG] Supabase: versuche {file_path} zu löschen")
    resp = supabase.storage.from_(SUPABASE_BUCKET).remove([file_path])
    print(f"[DEBUG] Supabase remove response für {file_path}: {resp}")