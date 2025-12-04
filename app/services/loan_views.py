# app/services/loan_views.py
from datetime import date
from typing import Optional
from datetime import timedelta


def compute_loan_stats(loans: list[dict]) -> dict:
    """
    Berechnet einfache Statistiken für eine Liste von Leihen.
    """
    today = date.today()
    return {
        "total": len(loans),
        "open": sum(
            1 for l in loans
            if l.get("status") == "OPEN"
            and not (l.get("planned_start_date") and l["planned_start_date"] > today)
        ),
        "returned": sum(1 for l in loans if l.get("status") == "RETURNED"),
        "missing": sum(1 for l in loans if l.get("status") == "MISSING_ITEMS"),
        "overdue": sum(1 for l in loans if l.get("status") == "OVERDUE"),
        "upcoming": sum(
            1 for l in loans
            if l.get("planned_start_date") and l["planned_start_date"] > today
        ),
        "recent": sum(
            1 for l in loans
            if l.get("status") == "RETURNED"
            and l.get("actual_end_date")
            and (today - l["actual_end_date"]).days <= 7
        )
    }


def filter_loans(loans: list[dict], contact: Optional[str], status: Optional[str]) -> list[dict]:
    """
    Filtert Leihen nach Kontakt-E-Mail und Status.
    """
    result = list(loans)

    if contact:
        search = contact.lower()
        result = [
            l for l in result
            if search in l.get("contact_email", "").lower()
        ]

    if status:
        if status == "UPCOMING":
            today = date.today()
            result = [
                l for l in result
                if l.get("planned_start_date") and l["planned_start_date"] > today
            ]
            return result

        if status == "OPEN":
            today = date.today()
            result = [
                l for l in result
                if l.get("status") == "OPEN"
                and not (l.get("planned_start_date") and l["planned_start_date"] > today)
            ]
            return result

        if status == "RECENT":
            today = date.today()
            result = [
                l for l in result
                if l.get("status") == "RETURNED"
                and l.get("actual_end_date")
                and (today - l["actual_end_date"]).days <= 7
            ]
            return result

        result = [l for l in result if l.get("status") == status]

    return result


def sort_loans(loans: list[dict], sort_field: str, sort_dir: str) -> list[dict]:
    """
    Sortiert Leihen nach
      - Ausgabedatum (issue_date)
      - Rückgabedatum (return_date)
      - Leih-ID / Erstelldatum (loan_id)
      - Box-Nummer (box_number)
    """
    def get_issue_date(loan):
        return loan.get("planned_start_date")

    def get_return_date(loan):
        return loan.get("planned_end_date")

    def get_loan_id(loan):
        """Leih-ID als Zahl (für Sortierung nach Erstelldatum)."""
        value = loan.get("id")
        try:
            return int(value)
        except (TypeError, ValueError):
            # Fallback: Leihen ohne sinnvolle ID ganz nach hinten
            return 10**12

    def get_box_number(loan):
        """
        Box-Code wie 'BOX-001' -> 1
        Wir extrahieren alle Ziffern und machen daraus eine Zahl.
        Fallback: alphabetische Sortierung nach Box-Code.
        """
        code = (loan.get("box_code") or "").strip()
        digits = "".join(ch for ch in code if ch.isdigit())

        if digits:
            try:
                num = int(digits)
                # (0, num) sorgt dafür, dass numerische Codes vor "komischen" Codes kommen
                return (0, num)
            except ValueError:
                pass

        # Keine oder ungültige Zahl -> nach Code sortieren, aber hinter den Zahlen
        return (1, code)

    # ---------------- Feld wählen ----------------
    # Wichtig: wir ändern das Verhalten nicht für vorhandene Werte
    if sort_field == "issue_date":
        key_func = get_issue_date
        field_type = "date"
    elif sort_field == "loan_id":
        key_func = get_loan_id
        field_type = "number"
    elif sort_field == "box_number":
        key_func = get_box_number
        field_type = "number"
    else:
        # Fallback + Standard: Rückgabedatum
        sort_field = "return_date"
        key_func = get_return_date
        field_type = "date"

    sort_dir = (sort_dir or "asc").lower()
    reverse = sort_dir == "desc"

    # ---------------- Sortierung anwenden ----------------
    if field_type == "date":
        # wie vorher: fehlende Datumswerte ans Ende/Anfang
        if sort_dir == "asc":
            return sorted(loans, key=lambda l: key_func(l) or date.max)
        else:
            return sorted(loans, key=lambda l: key_func(l) or date.min, reverse=True)
    else:
        # numerisch / Box-Nummer: normale Sortierung
        return sorted(loans, key=key_func, reverse=reverse)

def log_overdue_loans(loans: list[dict]) -> None:
    """
    Gibt im Terminal eine Info für alle Leihen aus,
    deren geplantes Rückgabedatum in der Vergangenheit liegt
    und die noch nicht abgeschlossen sind.
    """
    today = date.today()


    overdue_loans = [
        l for l in loans
        if l.get("planned_end_date") is not None
        and l["planned_end_date"] < today
        and l.get("status") in ("OPEN", "OVERDUE")
    ]

    # Wenn nichts überfällig ist, still sein
    if not overdue_loans:
        return

    print("\n" + "=" * 70)
    print("[OVERDUE CHECK] Es gibt überfällige Leihen:")
    print(f"Heutiges Datum: {today.isoformat()}")
    for loan in overdue_loans:
        box_code = loan.get("box_code", "UNBEKANNT")
        contact = loan.get("contact_email", "kein Kontakt hinterlegt")
        loan_id = loan.get("id", "?")
        end_date = loan.get("planned_end_date")
        print(
            f"  - Leih-ID #{loan_id} | Box {box_code} | "
            f"Kontakt: {contact} | geplante Rückgabe: {end_date}"
        )
    print("=" * 70 + "\n")
