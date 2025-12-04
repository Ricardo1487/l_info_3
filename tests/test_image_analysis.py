# tests/test_image_analysis.py

import json
import pytest

from datetime import date


# ------------------------------
# Hilfsklassen für Mocks
# ------------------------------


class DummyStream:
    def __init__(self):
        self.position = None

    def seek(self, pos: int):
        self.position = pos


class DummyFileStorage:
    """Simuliert ein Flask-FileStorage-Objekt."""
    def __init__(self, content: bytes = b"fake-image"):
        self._content = content
        self.stream = DummyStream()

    def read(self) -> bytes:
        return self._content


class DummyMessage:
    def __init__(self, content):
        # content kann String oder Liste sein, genau wie in image_analysis.py
        self.content = content


class DummyChoice:
    def __init__(self, content):
        self.message = DummyMessage(content)


class DummyResponse:
    def __init__(self, content):
        # choices[0].message.content -> content
        self.choices = [DummyChoice(content)]


class DummyCompletionsAPI:
    def __init__(self, content):
        self._content = content

    def create(self, model, messages, temperature):
        # Wir ignorieren model/messages/temperature und geben nur unsere Dummy-Antwort zurück
        return DummyResponse(self._content)


class DummyChatAPI:
    def __init__(self, content):
        self.completions = DummyCompletionsAPI(content)


class DummyClient:
    """Simuliert den OpenAI-Client mit chat.completions.create(...)"""
    def __init__(self, content):
        self.chat = DummyChatAPI(content)


# ------------------------------
# Tests für _get_client()
# ------------------------------


def test_get_client_requires_api_key(monkeypatch):
    """Ohne OPENAI_API_KEY soll ein RuntimeError geworfen werden."""
    import app.config.image_analysis as ia

    # Env-Var entfernen, falls vorhanden
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        ia._get_client()


def test_get_client_uses_env_and_returns_client(monkeypatch):
    """Mit OPENAI_API_KEY wird OpenAI(...) aufgerufen und ein Client zurückgegeben."""
    import app.config.image_analysis as ia

    # Dummy-Klasse anstelle von echtem OpenAI-Client
    class DummyOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.api_key = api_key
            self.base_url = base_url

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    monkeypatch.setattr(ia, "OpenAI", DummyOpenAI)

    client = ia._get_client()

    assert isinstance(client, DummyOpenAI)
    assert client.api_key == "test-key-123"
    assert "xinference" in client.base_url


# ------------------------------
# Tests für analyze_image_file()
# ------------------------------


def test_analyze_image_file_parses_plain_json_string(monkeypatch):
    """
    Prüft, dass ein einfacher JSON-String korrekt geparst wird.
    """
    import app.config.image_analysis as ia

    # Dummy-Inhalt, so als hätte das Modell einfach nur JSON zurückgegeben
    response_content = json.dumps({
        "objects": [
            {"label": "HDMI Kabel", "confidence": 0.9, "quantity": 1}
        ]
    })

    # _get_client() so patchen, dass es unseren DummyClient zurückgibt
    monkeypatch.setattr(
        ia,
        "_get_client",
        lambda: DummyClient(response_content),
    )

    file_storage = DummyFileStorage()

    result = ia.analyze_image_file(file_storage)

    # File-Stream wurde wieder auf Anfang gesetzt
    assert file_storage.stream.position == 0

    # Ergebnis-Struktur prüfen
    assert isinstance(result, dict)
    assert "objects" in result
    assert len(result["objects"]) == 1
    obj = result["objects"][0]
    assert obj["label"] == "HDMI Kabel"
    assert obj["quantity"] == 1


def test_analyze_image_file_parses_json_code_block(monkeypatch):
    """
    Prüft, dass ```json ... ```-Antworten korrekt entpackt und geparst werden.
    """
    import app.config.image_analysis as ia

    inner = json.dumps({
        "objects": [
            {"label": "Netzteil", "confidence": 0.95, "quantity": 2}
        ]
    })

    response_content = f"""```json
{inner}
```"""

    monkeypatch.setattr(
        ia,
        "_get_client",
        lambda: DummyClient(response_content),
    )

    file_storage = DummyFileStorage()
    result = ia.analyze_image_file(file_storage)

    assert "objects" in result
    assert result["objects"][0]["label"] == "Netzteil"
    assert result["objects"][0]["quantity"] == 2


def test_analyze_image_file_wraps_non_dict_result(monkeypatch):
    """
    Prüft den Fall, dass das Modell z.B. eine Liste zurückgibt – dann wird sie
    zu {"objects": [...]} gewrappt.
    """
    import app.config.image_analysis as ia

    raw_list = [
        {"label": "Adapter", "confidence": 0.88, "quantity": 1}
    ]
    response_content = json.dumps(raw_list)

    monkeypatch.setattr(
        ia,
        "_get_client",
        lambda: DummyClient(response_content),
    )

    file_storage = DummyFileStorage()
    result = ia.analyze_image_file(file_storage)

    assert isinstance(result, dict)
    assert "objects" in result
    assert result["objects"][0]["label"] == "Adapter"


def test_analyze_image_file_handles_message_content_list(monkeypatch):
    """
    Prüft den Pfad, bei dem message.content eine Liste von Teilen ist,
    z.B. [{"type": "text", "text": "..."}].
    """
    import app.config.image_analysis as ia

    inner_json = json.dumps({
        "objects": [
            {"label": "Kabel", "confidence": 0.9, "quantity": 3}
        ]
    })

    # content ist hier eine Liste -> wird in analyze_image_file speziell behandelt
    content_list = [
        {"type": "text", "text": inner_json}
    ]

    monkeypatch.setattr(
        ia,
        "_get_client",
        lambda: DummyClient(content_list),
    )

    file_storage = DummyFileStorage()
    result = ia.analyze_image_file(file_storage)

    assert "objects" in result
    assert result["objects"][0]["label"] == "Kabel"
    assert result["objects"][0]["quantity"] == 3
