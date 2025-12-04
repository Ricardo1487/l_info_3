import base64
import json
import os
from openai import OpenAI


def _get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt in .env")
    return OpenAI(
        api_key=api_key,
        base_url="https://xinference.ostfalialabs.org/v1"
    )


def analyze_image_file(file_storage):
    """
    Erkennt Gegenstände auf einem Bild.
    Gibt JSON zurück nach Schema:
    {
      "objects": [
        {"label": "HDMI Kabel", "confidence": 0.94, "quantity": 2},
        ...
      ]
    }
    """
    # Datei einlesen
    data = file_storage.read()
    file_storage.stream.seek(0)

    b64_img = base64.b64encode(data).decode("utf-8")
    client = _get_client()

    prompt = (
        "Erkenne alle Gegenstände auf dem Bild. "
        "Gib NUR gültiges JSON im Format:\n\n"
        "{\n"
        "  \"objects\": [\n"
        "    {\"label\": \"string\", \"confidence\": 0.95, \"quantity\": 1},\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Keine Erklärungen, kein Markdown."
    )

    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
        }
    ]

    response = client.chat.completions.create(
        model="qwen2.5-vl-instruct",
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )

    # Inhalt robust auslesen – je nach API-Version kann content ein String oder eine Liste sein
    msg_content = response.choices[0].message.content

    if isinstance(msg_content, str):
        raw = msg_content.strip()
    elif isinstance(msg_content, list):
        # z. B. [{"type": "text", "text": "..."}]
        texts = []
        for part in msg_content:
            # OpenAI-Client: part kann ein Objekt mit .text oder ein dict mit "text" sein
            t = getattr(part, "text", None)
            if t:
                texts.append(t)
            elif isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
        raw = "\n".join(texts).strip()
    else:
        raw = str(msg_content).strip()

    # Falls das Modell ```json ... ``` zurückgibt → abschälen
    if raw.startswith("```"):
        raw = raw.strip("`")
        parts = raw.split("\n", 1)
        if len(parts) == 2 and parts[0].lower().startswith("json"):
            raw = parts[1].strip()

    print("RAW ANALYSIS STRING:", raw)

    data = json.loads(raw)

    # Sicherheit: Immer ein Dict mit 'objects' liefern
    # Wenn das Modell KEIN Dict zurückgibt (z.B. eine Liste) ODER
    # ein Dict ohne "objects"-Key, dann wrappen wir es.
    if not isinstance(data, dict) or "objects" not in data:
        data = {"objects": data}

    return data


