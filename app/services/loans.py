# app/Services/loans.py

from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from app.config.database import SessionLocal
from app.services.photos_storage import delete_photo_from_storage

import os
from app.services.photos_storage import get_public_url



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
            WHERE l.status IN ('OPEN', 'OVERDUE', 'MISSING_ITEMS', 'RETURNED')
            ORDER BY l.planned_end_date ASC
        """)).mappings().all()

        return [dict(r) for r in rows]

def get_loan_by_id(loan_id: int) -> Optional[Dict[str, Any]]:
    """
    Holt Details einer einzelnen Leihe inkl. Box-Code und öffentlicher INITIAL-Foto-URL.
    """
    from app.services.photos_storage import get_public_url

    with SessionLocal() as session:
        # Hauptdaten der Leihe abrufen
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

        if not row:
            return None

        loan = dict(row)

        # INITIAL-Foto (file_path)
        init_photo_path = session.execute(
            text("""
                SELECT file_path
                FROM photos
                WHERE loan_id = :loan_id
                  AND type = 'INITIAL'
                ORDER BY id ASC
                LIMIT 1
            """),
            {"loan_id": loan_id}
        ).scalar()

        return_photo_path = session.execute(
            text(
                """
                SELECT file_path
                FROM photos
                WHERE loan_id = :loan_id AND type = 'RETURN'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"loan_id": loan_id},
        ).scalar()

        # Öffentliche URL erzeugen
        if init_photo_path:
            loan["initial_photo"] = get_public_url(init_photo_path)
        else:
            loan["initial_photo"] = None

        if return_photo_path:
            loan["return_photo"] = get_public_url(return_photo_path)
        else:
            loan["return_photo"] = None

        return loan





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

    # UPCOMING if start date is in the future
    today = datetime.now(timezone.utc).date()
    status_value = 'UPCOMING' if planned_start_date > today else 'OPEN'

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
                    :status,
                    :start,
                    :end,
                    :created_by
                )
                RETURNING id
            """),
            {
                "box_id": box_id,
                "contact_email": contact_email,
                "status": status_value,
                "start": planned_start_date,
                "end": planned_end_date,
                "created_by": created_by_user_id
            }
        )

        loan_id = result.scalar_one()
        session.commit()
        return loan_id

def create_loan_with_validation(box_id: int, form_data: dict, created_by_user_id: int) -> int:
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
        created_by_user_id=created_by_user_id,
    )

# ---------------------------------------------------------
#  Frist einer Leihe verlängern
# ---------------------------------------------------------
def update_loan_basic_data(
    *,
    loan_id: int,
    contact_email: Optional[str],
    planned_start_date: Optional[date],
    planned_end_date: Optional[date],
) -> None:
    """
    Aktualisiert die Stammdaten einer Leihe:
      - contact_email
      - planned_start_date
      - planned_end_date

    Einfache Plausibilitätsprüfung:
      - Wenn beide Datumswerte gesetzt sind, darf planned_start_date
        nicht nach planned_end_date liegen.
    """
    if planned_start_date and planned_end_date and planned_start_date > planned_end_date:
        raise ValueError("Ausgabedatum darf nicht nach dem Rückgabedatum liegen.")

    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE loans
                SET contact_email = :email,
                    planned_start_date = :start_date,
                    planned_end_date = :end_date
                WHERE id = :loan_id
                """
            ),
            {
                "loan_id": loan_id,
                "email": contact_email or None,
                "start_date": planned_start_date,
                "end_date": planned_end_date,
            },
        )
        session.commit()

# ---------------------------------------------------------
#  Leihe als "MISSING_ITEMS" markieren
# ---------------------------------------------------------
def mark_missing_items(loan_id: int) -> None:
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

# ---------------------------------------------------------
#  Erkannte Objekte für INITIAL / RETURN-Fotos zusammenfassen
# ---------------------------------------------------------
def get_detected_objects_for_photo(session, loan_id: int, photo_type: str) -> Dict[str, int]:
    """Lädt alle erkannten Objekte für einen Foto-Typ (INITIAL oder RETURN)
    einer bestimmten Leihe und gibt ein Dictionary der Form zurück:

        { "HDMI Kabel": 2, "Adapter": 1 }
    """
    rows = session.execute(
        text(
            """
            SELECT d.label, SUM(d.quantity) AS qty
            FROM photos p
            JOIN detected_objects d ON d.photo_id = p.id
            WHERE p.loan_id = :loan_id
              AND p.type = :ptype
            GROUP BY d.label
            """
        ),
        {"loan_id": loan_id, "ptype": photo_type},
    ).mappings().all()

    return {row["label"]: row["qty"] for row in rows}


# ---------------------------------------------------------
#  Vergleich zwischen INITIAL & RETURN: Was fehlt?
# ---------------------------------------------------------

def compare_object_sets(initial: Dict[str, int], returned: Dict[str, int]) -> Dict[str, int]:
    """Vergleicht zwei Objektmengen und liefert die fehlenden Items.

    Beispiel:
      initial  -> {"HDMI Kabel": 2, "Maus": 1}
      returned -> {"HDMI Kabel": 1, "Maus": 1}

    Ergebnis:
      {"HDMI Kabel": 1}
    """
    missing: Dict[str, int] = {}
    for label, initial_qty in initial.items():
        returned_qty = returned.get(label, 0)
        if returned_qty < initial_qty:
            missing[label] = initial_qty - returned_qty
    return missing


def delete_loan_if_fully_returned(loan_id: int) -> bool:
    """
    Löscht eine Leihe und alle verknüpften Daten (Fotos, erkannte Objekte,
    Erinnerungen) **nur**, wenn sie als vollständig zurückgegeben gilt.

    Bedingungen:
      - loans.status = 'RETURNED'
      - loans.actual_end_date IS NOT NULL

    Hinweis für den Prof:
      Theoretisch könnten wir hier auch archivieren statt löschen.
      Aus Performance-/Speichergründen räumen wir aber direkt auf.
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
            print(f"[DEBUG] Loan {loan_id}: existiert nicht, nichts zu löschen.")
            return False

        status = row["status"]
        actual_end_date = row["actual_end_date"]

        # Nur löschen, wenn sie sauber zurückgegeben ist
        if status != "RETURNED" or actual_end_date is None:
            print(f"[DEBUG] Loan {loan_id} nicht löschbar (status={status}, actual_end_date={actual_end_date})")
            return False

        # 2) ZUERST alle Dateipfade der Fotos holen
        photo_paths = session.execute(
            text("""
                SELECT file_path
                FROM photos
                WHERE loan_id = :loan_id
            """),
            {"loan_id": loan_id},
        ).scalars().all()

        print(f"[DEBUG] Loan {loan_id}: gefundene photo_paths: {photo_paths}")

        # 3) Dateien im Storage löschen (INITIAL & RETURN)
        for path in photo_paths:
            try:
                print(f"[DEBUG] Lösche Datei im Storage: {path}")
                delete_photo_from_storage(path)
            except Exception as e:
                print(f"[WARN] Fehler beim Löschen aus Storage für {path}: {e}")

        # 4) Detected Objects löschen (zu Fotos dieser Leihe)
        session.execute(
            text("""
                DELETE FROM detected_objects
                WHERE photo_id IN (
                    SELECT id FROM photos WHERE loan_id = :loan_id
                )
            """),
            {"loan_id": loan_id},
        )

        # 5) Fotos löschen
        session.execute(
            text("""
                DELETE FROM photos
                WHERE loan_id = :loan_id
            """),
            {"loan_id": loan_id},
        )

        # 6) Erinnerungen löschen
        session.execute(
            text("""
                DELETE FROM reminders
                WHERE loan_id = :loan_id
            """),
            {"loan_id": loan_id},
        )

        # 7) Leihe selbst löschen
        session.execute(
            text("""
                DELETE FROM loans
                WHERE id = :loan_id
            """),
            {"loan_id": loan_id},
        )

        session.commit()
        print(f"[DEBUG] Loan {loan_id} und alle verknüpften Daten wurden gelöscht.")
        return True


def get_initial_contents_for_all_loans() -> Dict[int, Dict[str, int]]:
    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT p.loan_id, d.label, SUM(d.quantity) AS qty
            FROM photos p
            JOIN detected_objects d ON d.photo_id = p.id
            WHERE p.type = 'INITIAL'
            GROUP BY p.loan_id, d.label
        """)).mappings().all()

    result: Dict[int, Dict[str, int]] = {}

    for row in rows:
        loan_id = row["loan_id"]
        if loan_id not in result:
            result[loan_id] = {}
        result[loan_id][row["label"]] = row["qty"]

    return result
def update_loan_basic_data(
    *,
    loan_id: int,
    contact_email: Optional[str],
    planned_start_date: Optional[date],
    planned_end_date: Optional[date],
) -> None:
    """
    Aktualisiert die Basisdaten einer Leihe:
      - contact_email
      - planned_start_date
      - planned_end_date

    Einfache Plausibilitätsprüfung:
      - Wenn beide Datumswerte gesetzt sind, darf planned_start_date
        nicht nach planned_end_date liegen.
    """
    if planned_start_date and planned_end_date and planned_start_date > planned_end_date:
        raise ValueError("Ausgabedatum darf nicht nach dem Rückgabedatum liegen.")

    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE loans
                SET contact_email = :email,
                    planned_start_date = :start_date,
                    planned_end_date = :end_date
                WHERE id = :loan_id
                """
            ),
            {
                "loan_id": loan_id,
                "email": contact_email or None,
                "start_date": planned_start_date,
                "end_date": planned_end_date,
            },
        )
        session.commit()