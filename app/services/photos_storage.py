# app/services/photos_storage.py

import os
import tempfile
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

# -------------------------------
# Supabase-Konfiguration
# -------------------------------
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
    """Erlaubt nur einfache Zeichen im Dateinamen."""
    if not name:
        return "upload.jpg"
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", "."))


def _upload_file_storage_to_key(file_storage, key: str) -> str:
    """
    Nimmt ein Flask-FileStorage-Objekt entgegen und lädt es
    unter dem gegebenen Bucket-Key hoch.

    Wir nutzen kurz eine echte Temp-Datei auf dem System (z.B. /tmp),
    weil die Supabase-Python-Library einen Dateipfad erwartet.
    """
    # 1) sichere Temp-Datei anlegen
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
        # Inhalt des Uploads auf Platte schreiben
        file_storage.save(tmp_path)

    try:
        # 2) Datei zu Supabase hochladen
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            key,
            tmp_path,
            {"upsert": True},   # falls ihr später ersetzen wollt
        )
    finally:
        # 3) lokale Temp-Datei löschen
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass

    return key


# -------------------------------------------------
# 1) INITIAL-Foto direkt an eine Leihe hängen
# -------------------------------------------------
def upload_initial_photo(file_storage, loan_id: int) -> str:
    """
    Lädt das erste Foto einer Leihe direkt in den Bucket
    unter: loans/<loan_id>/initial_<timestamp>_<filename>

    Rückgabe:
      - der Bucket-Pfad (key), z.B.
        "loans/42/initial_20251123_190102_BOX-001_front.jpg"
    """
    original_name = _sanitize_filename(getattr(file_storage, "filename", "upload.jpg"))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    key = f"loans/{loan_id}/initial_{ts}_{original_name}"

    return _upload_file_storage_to_key(file_storage, key)


# -------------------------------------------------
# 2) INITIAL-Foto ersetzen
# -------------------------------------------------
def replace_initial_photo(
    file_storage,
    loan_id: int,
    old_key: Optional[str] = None,
) -> str:
    """
    Ersetzt das INITIAL-Foto einer Leihe:

      - optional: altes Bild im Bucket löschen (old_key)
      - neues Bild direkt hochladen
      - gibt den neuen Bucket-Pfad zurück

    Achtung:
      - Die Aktualisierung des Eintrags in der Tabelle 'photos'
        macht ihr im Web/Service-Code, nicht hier.
    """

    # Altes Foto im Bucket entfernen (falls angegeben)
    if old_key:
        try:
            supabase.storage.from_(SUPABASE_BUCKET).remove([old_key])
        except Exception:
            # Für euer Projekt reicht es, Fehler hier zu ignorieren.
            # Optional: logging einbauen.
            pass

    # Neues Bild hochladen
    return upload_initial_photo(file_storage, loan_id)