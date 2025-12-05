import os
import sys
import types
from pathlib import Path

# Projektwurzel zum Python-Pfad hinzufügen
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Dummy-Umgebungsvariablen für Supabase, damit photos_storage beim Import
# KEIN RuntimeError wirft.
os.environ.setdefault("SUPABASE_URL", "https://dummy-supabase.local")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy-service-key")
os.environ.setdefault("SUPABASE_BUCKET", "photos")

# Für die Tests einen sehr einfachen Dummy-"supabase"-Client bereitstellen.
# Das gilt NUR in pytest, weil conftest.py nur dort geladen wird.
dummy_module = types.ModuleType("supabase")


class DummySupabaseClient:
    def __init__(self):
        # storage.from_(...) soll ein Objekt haben mit upload/remove/get_public_url
        self.storage = types.SimpleNamespace(
            from_=lambda bucket: types.SimpleNamespace(
                upload=lambda *args, **kwargs: {},
                remove=lambda *args, **kwargs: {},
                get_public_url=lambda path: f"https://cdn.example.com/{path}",
            )
        )


def create_client(url, key):
    # URL/Key werden ignoriert – für Tests reicht ein Dummy-Client
    return DummySupabaseClient()


dummy_module.Client = DummySupabaseClient
dummy_module.create_client = create_client

# Echten "supabase"-Import im Testprozess durch unseren Dummy ersetzen
sys.modules["supabase"] = dummy_module
