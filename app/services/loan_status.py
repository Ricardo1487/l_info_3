# app/services/loan_status.py

from datetime import date
from sqlalchemy import text
from app.config.database import SessionLocal


# ---------------------------------------------------------
#  Alle überfälligen Leihen auf 'OVERDUE' setzen
# ---------------------------------------------------------
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
#  Einzelne Leihe als "MISSING_ITEMS" markieren
# ---------------------------------------------------------
def mark_missing_items(loan_id: int) -> None:
    """
    Setzt den Status einer Leihe auf 'MISSING_ITEMS',
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