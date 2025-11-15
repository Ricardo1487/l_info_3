from sqlalchemy import text
from config.database import SessionLocal

def main():
    with SessionLocal() as session:
        # 1) Einfache DB-Probe
        result = session.execute(text("SELECT 1"))
        print("SELECT 1 →", result.scalar_one())

        # 2) Test: Users lesen
        users = session.execute(text("SELECT id, username, email, role FROM users")).mappings().all()
        print("Users:")
        for u in users:
            print(dict(u))

        # 3) Test: Loans inkl. Boxes lesen
        loans = session.execute(text("""
            SELECT
                l.id,
                l.contact_email,
                l.status,
                l.planned_start_date,
                l.planned_end_date,
                b.box_code
            FROM loans l
            JOIN boxes b ON l.box_id = b.id
            ORDER BY l.planned_end_date ASC
        """)).mappings().all()

        print("\nLoans:")
        for loan in loans:
            print(dict(loan))

if __name__ == "__main__":
    main()