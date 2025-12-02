# app/services/boxes.py

import re
import os
from typing import Optional
from sqlalchemy import text
from app.config.database import SessionLocal

BOX_PATTERN = re.compile(r"^BOX-\d{3}$")

def build_qr_payload(box_code: str) -> str:
    """
    Erzeugt die URL, die im QR-Code landen soll.
    Neuer Workflow: QR-Code soll direkt auf das
    'Neue Leihe'-Formular zeigen und die Box vorbelegen.
    Beispiel: https://l-info-3.onrender.com/new-loan?box_code=BOX-023
    """
    base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000")
    # QR führt direkt ins Neue-Leihe-Formular mit gesetztem box_code
    return f"{base_url}/new-loan?box_code={box_code}"


def validate_box_code(box_code: str) -> bool:
    """Akzeptiert entweder BOX-### oder reine Zahlen."""

    # reine Zahl (wird später zu BOX-### gemacht)
    if box_code.isdigit() and 1 <= len(box_code) <= 3:
        return True

    # echtes Format überprüfen
    return bool(re.match(r"^BOX-\d{3}$", box_code))


def get_box_id_by_code(box_code: str) -> Optional[int]:
    """Gibt ID oder None zurück."""
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT id
                FROM boxes
                WHERE box_code = :code
                AND is_active = TRUE
                LIMIT 1
            """),
            {"code": box_code},
        ).mappings().first()

        return row["id"] if row else None

def create_box(box_code: Optional[str] = None, description: Optional[str] = None) -> int:
    """Erstellt eine Box mit Format BOX-###."""
    with SessionLocal() as session:

        # Automatisch generieren (BOX-001 …)
        if not box_code or box_code.strip() == "":
            row = session.execute(
                text("SELECT MAX(id) AS max_id FROM boxes")
            ).mappings().first()

            next_id = (row["max_id"] or 0) + 1
            box_code = f"BOX-{next_id:03d}"

        # Format erzwingen
        if not validate_box_code(box_code):
            raise ValueError("Box-Code muss Format BOX-### haben!")

        qr_payload = build_qr_payload(box_code)

        result = session.execute(
            text("""
                INSERT INTO boxes (box_code, qr_payload, is_active)
                VALUES (:code, :qr_payload, TRUE)
                RETURNING id
            """),
            {"code": box_code, "qr_payload": qr_payload},
        )
        new_id = result.scalar_one()
        session.commit()

        return new_id
