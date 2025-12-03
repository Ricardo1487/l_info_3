from datetime import date
from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    extend_loan,
    mark_missing_items
)


def main():
    print("=== Bestehende Leihen ===")
    for loan in list_loans():
        print(loan)

    print("\n=== Neue Leihe anlegen ===")
    new_id = create_loan(
        box_id=1,
        contact_email="student3@th-koeln.de",
        planned_start_date=date(2025, 12, 1),
        planned_end_date=date(2025, 12, 10),
        created_by_user_id=2,
    )
    print(f"Neue Loan-ID: {new_id}")

    print("\n=== Loan Details ===")
    print(get_loan_by_id(new_id))

    print("\n=== Loan verlängern ===")
    extend_loan(loan_id=new_id, new_end_date=date(2025, 12, 15))
    print(get_loan_by_id(new_id))

    print("\n=== Loan zurückgeben ===")
    return_loan(
        loan_id=new_id,
        actual_end_date=date(2025, 12, 14),
        closed_by_user_id=2
    )
    print(get_loan_by_id(new_id))

    print("\n=== Loan als fehlend markieren ===")
    mark_missing_items(loan_id=new_id)
    print(get_loan_by_id(new_id))


if __name__ == "__main__":
    main()