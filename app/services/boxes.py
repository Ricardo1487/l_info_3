# app/services/boxes.py

from typing import Optional
from sqlalchemy import text
from app.config.database import SessionLocal


def get_box_id_by_code(box_code: str) -> Optional[int]:
    """
    Gibt die id einer Box zu einem box_code zurück,
    oder None, falls sie nicht existiert.
    """
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
    """
    Legt eine neue Box an. Falls kein Code übergeben wurde,
    wird automatisch BOX-001, BOX-002 ... erzeugt.
    """
    with SessionLocal() as session:

        # Automatisch generieren
        if box_code is None or box_code.strip() == "":
            row = session.execute(
                text("SELECT MAX(id) AS max_id FROM boxes")
            ).mappings().first()

            next_id = (row["max_id"] or 0) + 1
            box_code = f"BOX-{next_id:03d}"

        result = session.execute(
            text("""
                INSERT INTO boxes (box_code, is_active)
                VALUES (:code, TRUE)
                RETURNING id
            """),
            {"code": box_code},
        )
        new_id = result.scalar_one()
        session.commit()
        return new_id
