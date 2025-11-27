# app/services/loan_views.py
from datetime import date


def compute_loan_stats(loans: list[dict]) -> dict:
    """
    Berechnet einfache Statistiken für eine Liste von Leihen.
    """
    return {
        "total": len(loans),
        "open": sum(1 for l in loans if l.get("status") == "OPEN"),
        "returned": sum(1 for l in loans if l.get("status") == "RETURNED"),
        "missing": sum(1 for l in loans if l.get("status") == "MISSING_ITEMS"),
        "overdue": sum(1 for l in loans if l.get("status") == "OVERDUE"),
    }


def filter_loans(loans: list[dict], contact: str | None, status: str | None) -> list[dict]:
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
        result = [l for l in result if l.get("status") == status]

    return result


def sort_loans(loans: list[dict], sort_field: str, sort_dir: str) -> list[dict]:
    """
    Sortiert Leihen nach Ausgabedatum oder Rückgabedatum.
    """
    def get_issue_date(loan):
        return loan.get("planned_start_date")

    def get_return_date(loan):
        return loan.get("planned_end_date")

    # Feld wählen
    if sort_field == "issue_date":
        key_func = get_issue_date
    else:
        sort_field = "return_date"
        key_func = get_return_date

    if sort_dir == "asc":
        return sorted(loans, key=lambda l: key_func(l) or date.max)
    else:
        return sorted(loans, key=lambda l: key_func(l) or date.min, reverse=True)