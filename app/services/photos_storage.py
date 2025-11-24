# app/services/photos_storage.py

import os
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


def _sanitize_box_code(box_code: str) -> str:
    """Erlaubt nur einfache Zeichen im Dateinamen."""
    return "".join(c for c in box_code if c.isalnum() or c in ("-", "_"))  ###fix der unterstiche


# -------------------------------------------------
# 1) Upload eines Fotos in temp/ im Bucket
# -------------------------------------------------
def upload_temp_photo(file_storage, box_code: str) -> str:
    """
    Nimmt ein Flask-FileStorage-Objekt (photo) entgegen,
    speichert es kurz lokal und lädt es dann in den Supabase-Bucket
    unter temp/ hoch.

    Rückgabe:
      - bucket_key, z.B. "temp/BOX-001_20251123_183012_originalname.jpg"
    """
    safe_code = _sanitize_box_code(box_code or "BOX")

    # Dateiname vorbereiten
    original_name = file_storage.filename or "upload.jpg"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    local_filename = f"{safe_code}_{ts}_{original_name}"

    # Lokaler Temp-Pfad (nutzen wir /tmp, das gibt es auch bei Render)
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, local_filename)

    # 1) Upload-Objekt auf Platte schreiben
    file_storage.save(local_path)

    # 2) Bucket-Key (Pfad im Supabase-Bucket)
    bucket_key = f"temp/{local_filename}"

    # 3) In Supabase hochladen – die Library erwartet einen Pfad (str)
    supabase.storage.from_(SUPABASE_BUCKET).upload(bucket_key, local_path)

    # 4) Lokale Datei wieder entfernen
    try:
        os.remove(local_path)
    except FileNotFoundError:
        pass

    return bucket_key


# -------------------------------------------------
# 2) temp/ → loans/<loan_id>/initial_... verschieben
# -------------------------------------------------
def promote_temp_to_initial(temp_key: str, loan_id: int) -> str:
    """
    Verschiebt ein Bild im Bucket von temp/ nach loans/<loan_id>/initial_...

    temp_key:
      - z.B. "temp/BOX-001_20251123_183012_upload.jpg"

    Rückgabe:
      - final_key, z.B. "loans/42/initial_BOX-001_20251123_183012_upload.jpg"
    """
    file_name = os.path.basename(temp_key)
    final_key = f"loans/{loan_id}/initial_{file_name}"

    supabase.storage.from_(SUPABASE_BUCKET).move(temp_key, final_key)

    return final_key


# -------------------------------------------------
# 3) Temp-Foto verwerfen
# -------------------------------------------------
def delete_temp_photo(temp_key: Optional[str]) -> None:
    """
    Löscht ein temporäres Foto im Bucket (wenn der User z.B. "Nein"
    bei 'Neue Box anlegen?' klickt).

    Fehler (z.B. Datei schon weg) werden still ignoriert.
    """
    if not temp_key:
        return

    try:
        # remove erwartet eine Liste von Pfaden
        supabase.storage.from_(SUPABASE_BUCKET).remove([temp_key])
    except Exception:
        # Für euer Uni-Projekt reicht es, hier still zu schlucken.
        # Optional: logging einbauen.
        pass