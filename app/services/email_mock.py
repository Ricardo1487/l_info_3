
"""
E-Mail-Mock für die Boxenverwaltung.

Simuliert eine zukünftige E-Mail-Funktion:
- verschickt KEINE echten E-Mails
- schreibt nur Log-Einträge
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
LOG_FILE = Path("logs/email_mock.log")


def _write_to_file(entry: Dict[str, Any]) -> None:
    """Schreibt einen Log-Eintrag als JSON-Zeile in LOG_FILE."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # soll die App nicht abbrechen
        logger.warning("EMAIL_MOCK: Konnte nicht in Log-Datei schreiben: %s", exc)


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    category: str = "generic",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Simuliert das Versenden einer E-Mail.

    Es wird:
      - ein strukturierter Log-Eintrag ins Logging geschrieben
      - zusätzlich in logs/email_mock.log gespeichert
    """
    entry = {
        "to": to,
        "subject": subject,
        "body": body,
        "category": category,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("EMAIL_MOCK %s", json.dumps(entry, ensure_ascii=False))
    _write_to_file(entry)
