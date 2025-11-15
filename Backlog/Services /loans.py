# app/services/loans.py
from __future__ import annotations
from datetime import date
import re
import uuid
from sqlalchemy import text

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Dates must be in YYYY-MM-DD format") from exc

def create_loan(data: dict, session):
    """
    Legt eine neue Box-Leihe an und speichert sie in der Tabelle 'loans'.

    Erwartete Felder:
      - box_id: str
      - contact_email: str (einfach validiert)
      - checkout_date: str (YYYY-MM-DD)
      - due_date: str (YYYY-MM-DD)

    Rückgabe:
      Dict mit typisierten Feldern (date-Objekte) und status='active'.
    """
    # Pflichtfelder prüfen
    required = ("box_id", "contact_email", "checkout_date", "due_date")
    for f in required:
        if f not in data:
            raise ValueError(f"Missing field: {f}")

    box_id = str(data["box_id"]).strip()
    contact_email = str(data["contact_email"]).strip()
    checkout_date_raw = str(data["checkout_date"]).strip()
    due_date_raw = str(data["due_date"]).strip()

    # Email prüfen
    if not _EMAIL_RE.match(contact_email):
        raise ValueError("Invalid email address")

    # Datum parsen & prüfen
    checkout_date = _parse_iso_date(checkout_date_raw)
    due_date = _parse_iso_date(due_date_raw)
    if due_date <= checkout_date:
        raise ValueError("Due date must be after checkout date")

    loan_id = str(uuid.uuid4())

    # In DB schreiben
    session.execute(
        text("""
            INSERT INTO loans (id, box_id, contact_email, checkout_date, due_date, status)
            VALUES (:id, :box_id, :contact_email, :checkout_date, :due_date, :status)
        """),
        {
            "id": loan_id,
            "box_id": box_id,
            "contact_email": contact_email,
            "checkout_date": checkout_date,
            "due_date": due_date,
            "status": "active",
        },
    )
    session.commit()

    # Rückgabe
    return {
        "id": loan_id,
        "box_id": box_id,
        "contact_email": contact_email,
        "checkout_date": checkout_date,
        "due_date": due_date,
        "status": "active",
    }