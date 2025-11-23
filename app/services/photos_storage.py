from supabase import create_client
import os
import uuid

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "photos")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upload_initial_photo(loan_id: int, file_storage) -> str:
    """
    Lädt ein INITIAL-Foto direkt in Supabase Storage hoch.
    file_storage = Flask FileStorage Objekt (request.files["photo"])
    """

    # eindeutiger Dateiname
    filename = f"initial_{uuid.uuid4()}.jpg"

    # Speicherpfad im Bucket
    storage_path = f"loans/{loan_id}/{filename}"

    # Direkt uploaden, kein tmp speicher auf Server
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        storage_path,
        file_storage.stream  # sehr wichtig: direkter Stream
    )

    return storage_path