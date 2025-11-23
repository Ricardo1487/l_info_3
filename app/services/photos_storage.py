# app/services/photos_storage.py

import os
import uuid
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "photos")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase-Konfiguration fehlt (SUPABASE_URL / SUPABASE_SERVICE_KEY).")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upload_temp_photo(file_storage, box_code: str) -> str:
    """
    Lädt ein Foto direkt in den Supabase-Bucket unter einem temp-Pfad hoch.
    file_storage: Flask FileStorage (request.files["photo"])
    Rückgabe: Pfad im Bucket, z. B. "temp/BOX-001/<uuid>.jpg"
    """
    ext = ".jpg"  # erstmal fest, später könnte man mimetype auswerten
    filename = f"{uuid.uuid4()}{ext}"

    # Pfad im Bucket
    storage_path = f"temp/{box_code}/{filename}"

    # Upload direkt aus dem FileStorage-Stream
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        storage_path,
        file_storage.stream,
    )

    return storage_path


def promote_temp_to_initial(temp_path: str, loan_id: int) -> str:
    """
    Verschiebt eine Datei von temp/… zu loans/<loan_id>/initial_<filename>.jpg
    im gleichen Bucket.
    Rückgabe: neuer Pfad im Bucket.
    """
    base_name = temp_path.split("/")[-1]  # z.B. "abc123.jpg"
    final_path = f"loans/{loan_id}/initial_{base_name}"

    supabase.storage.from_(SUPABASE_BUCKET).move(
        temp_path,
        final_path,
    )

    return final_path


def delete_temp_photo(temp_path: str) -> None:
    """
    Löscht eine temporäre Datei aus dem Bucket.
    """
    supabase.storage.from_(SUPABASE_BUCKET).remove([temp_path])