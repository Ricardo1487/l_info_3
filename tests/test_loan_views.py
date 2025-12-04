# tests/test_loan_views.py

from datetime import date

from app.services.loan_views import (
    compute_loan_stats,
    filter_loans,
    sort_loans,
)


# Hilfsdaten für mehrere Tests
SAMPLE_LOANS = [
    {
        "id": 1,
        "status": "OPEN",
        "contact_email": "alice@example.com",
        "planned_start_date": date(2025, 1, 1),
        "planned_end_date": date(2025, 1, 10),
        "box_code": "BOX-003",
    },
    {
        "id": 2,
        "status": "RETURNED",
        "contact_email": "bob@example.com",
        "planned_start_date": date(2025, 1, 5),
        "planned_end_date": date(2025, 1, 12),
        "box_code": "BOX-001",
    },
    {
        "id": 3,
        "status": "MISSING_ITEMS",
        "contact_email": "charlie@example.com",
        "planned_start_date": date(2025, 1, 3),
        "planned_end_date": date(2025, 1, 8),
        "box_code": "BOX-010",
    },
    {
        "id": 4,
        "status": "OVERDUE",
        "contact_email": "alice@example.com",
        "planned_start_date": date(2025, 1, 2),
        "planned_end_date": date(2025, 1, 4),
        "box_code": "BOX-007",
    },
]


# ------------------------------------------------------------
# compute_loan_stats
# ------------------------------------------------------------

def test_compute_loan_stats_counts_statuses():
    stats = compute_loan_stats(SAMPLE_LOANS)

    assert stats["total"] == 4
    assert stats["open"] == 1          # genau ein "OPEN"
    assert stats["returned"] == 1      # genau ein "RETURNED"
    assert stats["missing"] == 1       # genau ein "MISSING_ITEMS"
    assert stats["overdue"] == 1       # genau ein "OVERDUE"


# ------------------------------------------------------------
# filter_loans
# ------------------------------------------------------------

def test_filter_loans_by_contact_substring_case_insensitive():
    # "alice" kommt in zwei E-Mails vor
    filtered = filter_loans(SAMPLE_LOANS, contact="ALICE", status=None)

    ids = [l["id"] for l in filtered]
    assert set(ids) == {1, 4}


def test_filter_loans_by_status():
    filtered = filter_loans(SAMPLE_LOANS, contact=None, status="RETURNED")

    assert len(filtered) == 1
    assert filtered[0]["id"] == 2


def test_filter_loans_by_contact_and_status():
    # Nur die OVERDUE-Leihe von alice
    filtered = filter_loans(SAMPLE_LOANS, contact="alice", status="OVERDUE")

    assert len(filtered) == 1
    assert filtered[0]["id"] == 4


# ------------------------------------------------------------
# sort_loans – Ausgabedatum / Rückgabedatum
# ------------------------------------------------------------

def test_sort_loans_by_issue_date_asc():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="issue_date", sort_dir="asc")
    ids_in_order = [l["id"] for l in sorted_loans]

    # frühestes Ausgabedatum ist id=1 (01.01.), dann 4 (02.01.), 3 (03.01.), 2 (05.01.)
    assert ids_in_order == [1, 4, 3, 2]


def test_sort_loans_by_issue_date_desc():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="issue_date", sort_dir="desc")
    ids_in_order = [l["id"] for l in sorted_loans]

    assert ids_in_order == [2, 3, 4, 1]


def test_sort_loans_by_return_date_asc():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="return_date", sort_dir="asc")
    ids_in_order = [l["id"] for l in sorted_loans]

    # früheste Rückgabe: id=4 (04.01.), dann 3 (08.01.), 1 (10.01.), 2 (12.01.)
    assert ids_in_order == [4, 3, 1, 2]


def test_sort_loans_by_return_date_desc():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="return_date", sort_dir="desc")
    ids_in_order = [l["id"] for l in sorted_loans]

    assert ids_in_order == [2, 1, 3, 4]


# ------------------------------------------------------------
# sort_loans – Leih-ID und Box-Nummer
# ------------------------------------------------------------

def test_sort_loans_by_loan_id_asc():
    # einfach: IDs 1,2,3,4
    shuffled = [SAMPLE_LOANS[3], SAMPLE_LOANS[1], SAMPLE_LOANS[0], SAMPLE_LOANS[2]]
    sorted_loans = sort_loans(shuffled, sort_field="loan_id", sort_dir="asc")
    ids_in_order = [l["id"] for l in sorted_loans]

    assert ids_in_order == [1, 2, 3, 4]


def test_sort_loans_by_loan_id_desc():
    shuffled = [SAMPLE_LOANS[2], SAMPLE_LOANS[0], SAMPLE_LOANS[3], SAMPLE_LOANS[1]]
    sorted_loans = sort_loans(shuffled, sort_field="loan_id", sort_dir="desc")
    ids_in_order = [l["id"] for l in sorted_loans]

    assert ids_in_order == [4, 3, 2, 1]


def test_sort_loans_by_box_number_asc_uses_numeric_part():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="box_number", sort_dir="asc")
    ids_in_order = [l["id"] for l in sorted_loans]

    # BOX-001 (id=2), BOX-003 (id=1), BOX-007 (id=4), BOX-010 (id=3)
    assert ids_in_order == [2, 1, 4, 3]


def test_sort_loans_by_box_number_desc():
    sorted_loans = sort_loans(list(SAMPLE_LOANS), sort_field="box_number", sort_dir="desc")
    ids_in_order = [l["id"] for l in sorted_loans]

    assert ids_in_order == [3, 4, 1, 2]
