# app/services/loan_status.py

from datetime import date
from sqlalchemy import text
from app.config.database import SessionLocal

# ---------------------------------------------------------
#  Alle überfälligen Leihen auf 'OVERDUE' setzen
# ---------------------------------------------------------
def mark_overdue_loans(today: date) -> int:
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
#  UPCOMING → OPEN aktivieren, sobald Startdatum erreicht ist
# ---------------------------------------------------------
def activate_upcoming_loans(today: date) -> int:
    """
    Setzt Leihen, deren Startdatum erreicht/überschritten ist,
    automatisch von UPCOMING auf OPEN.
    """
    with SessionLocal() as session:
        result = session.execute(
            text("""
                UPDATE loans
                SET status = 'OPEN'
                WHERE
                    status = 'UPCOMING'
                    AND planned_start_date <= :today
                    AND actual_start_date IS NULL
            """),
            {"today": today},
        )
        session.commit()
        return result.rowcount


# ---------------------------------------------------------
#  Interne Helper-Funktion: Leihe schließen
# ---------------------------------------------------------
def _close_loan(
    *,
    loan_id: int,
    new_status: str,
    actual_end_date: date,
    closed_by_user_id: int,
) -> None:
    """
    Gemeinsame Logik zum Schließen einer Leihe:
    setzt Status, actual_end_date und closed_by_user_id.
    """
    with SessionLocal() as session:
        session.execute(
            text("""
                UPDATE loans
                SET
                    status = :status,
                    actual_end_date = :actual_end_date,
                    closed_by_user_id = :closed_by_user_id
                WHERE id = :loan_id
            """),
            {
                "loan_id": loan_id,
                "status": new_status,
                "actual_end_date": actual_end_date,
                "closed_by_user_id": closed_by_user_id,
            }
        )
        session.commit()


# ---------------------------------------------------------
#  „Normale“ Rückgabe: alles vollständig da
# ---------------------------------------------------------
def return_loan(
    *,
    loan_id: int,
    actual_end_date: date,
    closed_by_user_id: int,
) -> None:
    """
    Markiert eine Leihe als vollständig zurückgegeben (RETURNED).
    """
    _close_loan(
        loan_id=loan_id,
        new_status="RETURNED",
        actual_end_date=actual_end_date,
        closed_by_user_id=closed_by_user_id,
    )


# ---------------------------------------------------------
#  Rückgabe mit fehlenden Teilen
# ---------------------------------------------------------
def return_with_missing_items(
    *,
    loan_id: int,
    actual_end_date: date,
    closed_by_user_id: int,
) -> None:
    """
    Schließt eine Leihe als MISSING_ITEMS ab.
    (Teile fehlen bei der Rückgabe.)
    """
    _close_loan(
        loan_id=loan_id,
        new_status="MISSING_ITEMS",
        actual_end_date=actual_end_date,
        closed_by_user_id=closed_by_user_id,
    )