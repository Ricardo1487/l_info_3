import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def _get_client() -> OpenAI:
    """Create and return an OpenAI-compatible client.

    Reads the API key from the OPENAI_API_KEY environment variable.
    Raises a RuntimeError with a clear message if the key is missing,
    instead of crashing the app on import.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY ist nicht gesetzt. "
            "Stelle sicher, dass deine .env im Projekt liegt und "
            "OPENAI_API_KEY=... enthält."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://xinference.ostfalialabs.org/v1",
    )


def _encode_image(path: Path) -> str:
    """Read an image from disk and return it as a base64-encoded string."""
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open("rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def compare_images(image_path_1: str, image_path_2: str) -> dict:
    """Compare two images using the vision model and return a JSON dict.

    The result has the structure:

        {
          "vergleich": {
            "gemeinsamkeiten": ["string", ...],
            "unterschiede": ["string", ...],
            "zusammenfassung": "string"
          }
        }

    This function is designed to be called from Flask routes (e.g. /images/compare)
    and must not perform any work on module import.
    """
    client = _get_client()

    b64_1 = _encode_image(Path(image_path_1))
    b64_2 = _encode_image(Path(image_path_2))

    prompt = (
        "Vergleiche die beiden folgenden Bilder und vergleiche, welche Gegenstände zu sehen sind. "
        "Gib mir das Ergebnis ausschließlich als gültiges JSON im folgenden Format zurück und "
        "bezieh dich nur darauf, was das für Gegenstände sind:\n\n"
        "{\n"
        "  \"vergleich\": {\n"
        "    \"gemeinsamkeiten\": [\"string\", \"string\", ... ],\n"
        "    \"unterschiede\": [\"string\", \"string\", ... ],\n"
        "    \"zusammenfassung\": \"string\"\n"
        "  }\n"
        "}\n\n"
        "Erkläre nichts außerhalb des JSON. Keine Einleitung, keine Erklärung, keine Markdown-Formatierung."
    )

    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_1}"},
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_2}"},
        },
    ]

    response = client.chat.completions.create(
        model="qwen2.5-vl-instruct",
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )

    raw = response.choices[0].message.content[0].text.strip()

    # Safety: handle potential ```json ... ``` wrapping
    if raw.startswith("```"):
        raw = raw.strip("`")
        parts = raw.split("\n", 1)
        if len(parts) == 2 and parts[0].lower().startswith("json"):
            raw = parts[1]

    return json.loads(raw)
