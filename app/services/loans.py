# app/Services/loans.py

from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from app.config.database import SessionLocal


# ---------------------------------------------------------
#  Liste aller Leihen abrufen
# ---------------------------------------------------------
def list_loans() -> List[Dict[str, Any]]:
    """
    Gibt alle Leihen inkl. Box-Code zurück.
    Wird für das Dashboard und Tests verwendet.
    """
    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                l.id,
                l.contact_email,
                l.status,
                l.planned_start_date,
                l.planned_end_date,
                l.actual_start_date,
                l.actual_end_date,
                b.box_code
            FROM loans l
            JOIN boxes b ON l.box_id = b.id
            ORDER BY l.planned_end_date ASC
        """)).mappings().all()

        return [dict(r) for r in rows]


# ---------------------------------------------------------
#  Neue Leihe anlegen
# ---------------------------------------------------------
def create_loan(
    *,
    box_id: int,
    contact_email: str,
    planned_start_date: date,
    planned_end_date: date,
    created_by_user_id: int
) -> int:
    """
    Legt eine neue Leihe an und gibt die neue loan-id zurück.
    """

    if planned_end_date < planned_start_date:
        raise ValueError("planned_end_date darf nicht vor planned_start_date liegen")

    with SessionLocal() as session:
        result = session.execute(
            text("""
                INSERT INTO loans (
                    box_id,
                    contact_email,
                    status,
                    planned_start_date,
                    planned_end_date,
                    created_by_user_id
                )
                VALUES (
                    :box_id,
                    :contact_email,
                    'OPEN',
                    :start,
                    :end,
                    :created_by
                )
                RETURNING id
            """),
            {
                "box_id": box_id,
                "contact_email": contact_email,
                "start": planned_start_date,
                "end": planned_end_date,
                "created_by": created_by_user_id
            }
        )

        loan_id = result.scalar_one()
        session.commit()
        return loan_id


# ---------------------------------------------------------
#  Details einer einzelnen Leihe abrufen
# ---------------------------------------------------------
def get_loan_by_id(loan_id: int) -> Optional[Dict[str, Any]]:
    """
    Holt Details einer einzelnen Leihe.
    """
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT
                    l.*,
                    b.box_code
                FROM loans l
                JOIN boxes b ON l.box_id = b.id
                WHERE l.id = :loan_id
            """),
            {"loan_id": loan_id}
        ).mappings().first()

        return dict(row) if row else None


# ---------------------------------------------------------
#  Leihe zurückgeben / abschließen
# ---------------------------------------------------------
def return_loan(
    *,
    loan_id: int,
    actual_end_date: date,
    closed_by_user_id: int
) -> None:
    """
    Markiert die Leihe als zurückgegeben.
    """
    with SessionLocal() as session:
        session.execute(
            text("""
                UPDATE loans
                SET
                    status = 'RETURNED',
                    actual_end_date = :actual_end,
                    closed_by_user_id = :closed_by
                WHERE id = :loan_id
            """),
            {
                "loan_id": loan_id,
                "actual_end": actual_end_date,
                "closed_by": closed_by_user_id
            }
        )
        session.commit()


# ---------------------------------------------------------
#  Frist einer Leihe verlängern
# ---------------------------------------------------------
def extend_loan(
    *,
    loan_id: int,
    new_end_date: date
) -> None:
    """
    Verlängert das geplante Enddatum einer Leihe.
    """

    with SessionLocal() as session:
        session.execute(
            text("""
                UPDATE loans
                SET planned_end_date = :new_date
                WHERE id = :loan_id
            """),
            {
                "loan_id": loan_id,
                "new_date": new_end_date
            }
        )
        session.commit()


# ---------------------------------------------------------
#  Leihe als "MISSING_ITEMS" markieren
# ---------------------------------------------------------
def mark_missing_items(
    *,
    loan_id: int
) -> None:
    """
    Setzt den Status auf 'MISSING_ITEMS',
    wenn nach der Rückgabe Teile fehlen.
    """
    with SessionLocal() as session:
        session.execute(
            text("""
                UPDATE loans
                SET status = 'MISSING_ITEMS'
                WHERE id = :loan_id
            """),
            {"loan_id": loan_id}
        )
        session.commit()


def mark_overdue_loans(today: date) -> int:
    """
    Setzt den Status auf 'OVERDUE' für alle Leihen,
    deren geplantes Rückgabedatum vor 'today' liegt
    und die noch nicht tatsächlich zurückgegeben wurden.

    Rückgabe:
      - Anzahl der aktualisierten Zeilen.
    """
    with SessionLocal() as session:
        result = session.execute(
            text("""
                UPDATE loans
                SET status = 'OVERDUE'
                WHERE
                    status = 'OPEN'
                    AND planned_end_date < :today
                    AND actual_end_date IS NULL
            """),
            {"today": today},
        )
        session.commit()
        return result.rowcount

# ---------------------------------------------------------
#  Leihe + alle zugehörigen Daten löschen,
#  aber nur, wenn sie wirklich vollständig zurückgegeben ist
# ---------------------------------------------------------
def delete_loan_if_fully_returned(loan_id: int) -> bool:
    """
    Löscht eine Leihe und alle verknüpften Daten (Fotos, erkannte Objekte,
    Erinnerungen) **nur**, wenn sie als vollständig zurückgegeben gilt.

    Bedingungen aktuell:
      - loans.status = 'RETURNED'
      - loans.actual_end_date IS NOT NULL

    Rückgabe:
      - True  -> Leihe wurde gelöscht
      - False -> Bedingungen nicht erfüllt, nichts gelöscht
    """
    with SessionLocal() as session:
        # 1) Status und tatsächliches Enddatum prüfen
        row = session.execute(
            text("""
                SELECT status, actual_end_date
                FROM loans
                WHERE id = :loan_id
            """),
            {"loan_id": loan_id},
        ).mappings().first()

        if row is None:
            # Leihe existiert gar nicht
            return False

        status = row["status"]
        actual_end_date = row["actual_end_date"]

        # Nur löschen, wenn sie sauber zurückgegeben ist
        if status != "RETURNED" or actual_end_date is None:
            return False

        # 2) Detected Objects löschen (zu Fotos dieser Leihe)
        session.execute(
            text("""
                DELETE FROM detected_objects
                WHERE photo_id IN (
                    SELECT id FROM photos WHERE loan_id = :loan_id
                )
            """),
            {"loan_id": loan_id},
        )

        # 3) Fotos löschen
        session.execute(
            text("""
                DELETE FROM photos
                WHERE loan_id = :loan_id
            """),
            {"loan_id": loan_id},
        )

        # 4) Erinnerungen löschen
        session.execute(
            text("""
                DELETE FROM reminders
                WHERE loan_id = :loan_id
            """),
            {"loan_id": loan_id},
        )

        # 5) Leihe selbst löschen
        session.execute(
            text("""
                DELETE FROM loans
                WHERE id = :loan_id
            """),
            {"loan_id": loan_id},
        )


        session.commit()
        return True


# ---------------------------------------------------------
#  Verfügbarkeits-Info für eine Box (für Kalender/Frontend)
# ---------------------------------------------------------
def get_planned_periods_for_box(box_id: int) -> List[Dict[str, date]]:
    """
    Gibt alle geplanten Zeiträume (planned_start_date, planned_end_date)
    für eine Box zurück.

    Diese Funktion wird für den Verfügbarkeitskalender benutzt,
    damit im Frontend sichtbar ist, wann eine Box bereits belegt ist.
    """
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT planned_start_date, planned_end_date
                FROM loans
                WHERE box_id = :bid
                  AND status IN ('OPEN', 'OVERDUE', 'RETURNED')
                ORDER BY planned_start_date
            """),
            {"bid": box_id},
        ).mappings().all()

        return [
            {
                "start": r["planned_start_date"],
                "end": r["planned_end_date"],
            }
            for r in rows
        ]
