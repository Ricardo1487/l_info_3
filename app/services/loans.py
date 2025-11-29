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
            WHERE l.status IN ('OPEN', 'OVERDUE', 'MISSING_ITEMS')
            ORDER BY l.planned_end_date ASC
        """)).mappings().all()

        return [dict(r) for r in rows]

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

def create_loan_with_validation(box_id: int, form_data: dict) -> int:
    ausgabe_str = form_data.get("ausgabe")
    rueckgabe_str = form_data.get("rueckgabe")
    email = form_data.get("email")

    if not ausgabe_str or not rueckgabe_str or not email:
        raise Exception("Bitte alle Felder ausfüllen.")

    ausgabe = date.fromisoformat(ausgabe_str)
    rueckgabe = date.fromisoformat(rueckgabe_str)

    if ausgabe < date.today():
        raise Exception("Ausgabedatum kann nicht in der Vergangenheit liegen.")

    if rueckgabe < ausgabe:
        raise Exception("Rückgabedatum darf nicht vor dem Ausgabedatum liegen.")

    with SessionLocal() as session:
        overlap = session.execute(
            text("""
                SELECT 1 FROM loans
                WHERE box_id = :bid
                  AND status IN ('OPEN', 'OVERDUE')
                  AND (
                        :new_start <= planned_end_date
                    AND :new_end   >= planned_start_date
                  )
                LIMIT 1
            """),
            {"bid": box_id, "new_start": ausgabe, "new_end": rueckgabe}
        ).first()

        if overlap:
            raise Exception("Diese Box ist im angegebenen Zeitraum bereits ausgeliehen!")

    return create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=ausgabe,
        planned_end_date=rueckgabe,
        created_by_user_id=2,
    )


# ---------------------------------------------------------
#  Details einer einzelnen Leihe abrufen
# ---------------------------------------------------------


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
                DELETE FROM loans
                WHERE id = :loan_id
            """),
            {
                "loan_id": loan_id
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
                  AND status IN ('OPEN', 'OVERDUE', 'MISSING_ITEMS')
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



