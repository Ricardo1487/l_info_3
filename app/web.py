from dotenv import load_dotenv #erg

load_dotenv() #erg

from datetime import date
import os
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify

from sqlalchemy import text
from app.config.database import SessionLocal

#loans importieren
from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    extend_loan,
    get_planned_periods_for_box,

)
#boxes importieren
from app.services.boxes import (
    get_box_id_by_code,
    create_box,
)
#photos_storage importieren
from app.services.photos_storage import (
    upload_temp_photo,
    promote_temp_to_initial,
    delete_temp_photo,
)


app = Flask(__name__)


# ---------------------------------------------------
# Übersicht
# ---------------------------------------------------
@app.route("/")
def home():
    # Filterwerte aus der URL lesen
    sort = request.args.get("sort", "").strip()
    contact = request.args.get("contact", "").strip()

    # Alle Leihen wie bisher laden
    loans = list_loans()

    # -------------------------------
    # 1) Nach Kontakt (E-Mail) filtern
    # -------------------------------
    if contact:
        search = contact.lower()

        def get_contact_value(loan):
            value = getattr(loan, "contact_email", None)
            return value.lower() if isinstance(value, str) else ""

        loans = [loan for loan in loans if search in get_contact_value(loan)]

    # -------------------------------
    # 2) Sortierfunktionen definieren
    # -------------------------------
    def get_issue_date(loan):
        # Ausgabedatum (geplant)
        return getattr(loan, "planned_start_date", None)

    def get_return_date(loan):
        # Rückgabedatum (geplant)
        return getattr(loan, "planned_end_date", None)

    # -------------------------------
    # 3) Sortierung anwenden
    # -------------------------------
    if sort == "issue_date_asc":
        loans = sorted(
            loans,
            key=lambda l: get_issue_date(l) or date.max
        )
    elif sort == "issue_date_desc":
        loans = sorted(
            loans,
            key=lambda l: get_issue_date(l) or date.min,
            reverse=True,
        )
    elif sort == "return_date_asc":
        loans = sorted(
            loans,
            key=lambda l: get_return_date(l) or date.max
        )
    elif sort == "return_date_desc":
        loans = sorted(
            loans,
            key=lambda l: get_return_date(l) or date.min,
            reverse=True,
        )

    # -------------------------------
    # 4) Template rendern
    # -------------------------------
    return render_template(
        "index.html",
        title="Übersicht",
        loans=loans,
        current_sort=sort,
        current_contact=contact,
    )



# ---------------------------------------------------
# Neue Leihe Formular
# ---------------------------------------------------
@app.route("/new-loan")
def new_loan():
    return render_template(
        "new_loan.html",
        title="Neue Leihe",
        current_date=date.today().isoformat()
    )

# ---------------------------------------------------
# API: Verfügbarkeit einer Box (für Kalender / JS)
# ---------------------------------------------------
@app.route("/api/box/<box_code>/availability")
def api_box_availability(box_code: str):
    """
    Gibt alle geplanten Zeiträume für eine Box als JSON zurück.
    Wird vom Frontend genutzt, um belegte Tage im Kalender darzustellen.
    """
    # Box-ID über den Code holen
    box_id = get_box_id_by_code(box_code)
    if box_id is None:
        return jsonify({"box_id": None, "periods": []})

    # Zeiträume aus loans.py Funktion holen
    periods = get_planned_periods_for_box(box_id)

    # JSON-Antwort erstellen
    return jsonify({
        "box_id": box_id,
        "periods": [
            {
                "start": p["start"].isoformat(),
                "end": p["end"].isoformat(),
            }
            for p in periods
        ]
    })


# ---------------------------------------------------
# Leihe Versuch → Box prüfen
# ---------------------------------------------------
@app.route("/save-loan", methods=["POST"])
def save_loan():

    box_code = request.form.get("box_code", "").strip()
    if not box_code:
        abort(400, "Box-Code fehlt.")

    # Foto holen
    photo = request.files.get("photo")
    if not photo:
        abort(400, "Foto muss hochgeladen werden!")

    # 🔹 Foto direkt nach Supabase in temp/ hochladen
    temp_path = upload_temp_photo(photo, box_code)

    # Box existiert?
    existing_box_id = get_box_id_by_code(box_code)

    if existing_box_id is None:
        # Box NICHT vorhanden → Bestätigungsseite
        return render_template(
            "confirm_new_box.html",
            title="Neue Box anlegen?",
            box_code=box_code,
            temp_path=temp_path,     # statt tmp_filename
            form_data=request.form,
        )

    # Box existiert → direkt Leihe erstellen
    return process_loan_creation(existing_box_id, request.form, temp_path)



# ---------------------------------------------------
# Nutzer klickt auf JA oder NEIN beim Box-Anlegen
# ---------------------------------------------------
@app.route("/confirm-new-box", methods=["POST"])
def confirm_new_box():
    decision = request.form.get("decision")
    box_code = request.form.get("box_code")
    temp_path = request.form.get("temp_path")

    form_data = {
        "box_code": request.form.get("box_code"),
        "email": request.form.get("email"),
        "ausgabe": request.form.get("ausgabe"),
        "rueckgabe": request.form.get("rueckgabe"),
    }

    if decision == "no":
        # Temp-Foto im Bucket löschen
        if temp_path:
            delete_temp_photo(temp_path)
        return render_template("new_loan.html", title="Neue Leihe")

    if decision == "yes":
        new_box_id = create_box(box_code)
        return process_loan_creation(new_box_id, form_data, temp_path)

    abort(400, "Ungültige Auswahl.")



# ---------------------------------------------------
# ZENTRALE LEIHE-ERSTELLUNG (mit Zeitüberschneidung!)
# ---------------------------------------------------
def process_loan_creation(box_id, form_data, temp_path):

    ausgabe = date.fromisoformat(form_data["ausgabe"])
    rueckgabe = date.fromisoformat(form_data["rueckgabe"])

    # Ausgabedatum validieren
    if ausgabe < date.today():
        abort(400, "Ausgabedatum kann nicht in der Vergangenheit liegen.")

    # Rückgabedatum validieren
    if rueckgabe < ausgabe:
        abort(400, "Rückgabedatum darf nicht vor dem Ausgabedatum liegen.")

    # Überlappung prüfen
    with SessionLocal() as session:
        overlap = session.execute(
            text("""
                SELECT 1 FROM loans
                WHERE box_id = :bid
                  AND status IN ('OPEN', 'OVERDUE', 'RETURNED')
                  AND (
                        :new_start <= planned_end_date
                    AND :new_end   >= planned_start_date
                  )
                LIMIT 1
            """),
            {
                "bid": box_id,
                "new_start": ausgabe,
                "new_end": rueckgabe
            }
        ).first()

        if overlap:
            abort(400, "Diese Box ist im angegebenen Zeitraum bereits ausgeliehen!")

    # 1️⃣ Leihe speichern
    email = form_data["email"]

    loan_id = create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=ausgabe,
        planned_end_date=rueckgabe,
        created_by_user_id=2,
    )

    # 2️⃣ Foto von temp/ → loans/<id>/initial_... verschieben
    if not temp_path:
        abort(400, "Kein temporärer Fotopfad übergeben.")

    final_path = promote_temp_to_initial(temp_path, loan_id)

    # 3️⃣ Foto-Eintrag in der DB (photos-Tabelle)
    with SessionLocal() as session:
        session.execute(
            text("""
                INSERT INTO photos (loan_id, type, file_path, created_by_user_id)
                VALUES (:loan_id, 'INITIAL', :file_path, :user_id)
            """),
            {
                "loan_id": loan_id,
                "file_path": final_path,
                "user_id": 2,
            }
        )
        session.commit()

    return redirect(url_for("home"))


# ---------------------------------------------------
# Rückgabe
# ---------------------------------------------------
@app.route("/return/<int:loan_id>", methods=["GET", "POST"])
def return_box(loan_id: int):
    loan = get_loan_by_id(loan_id)

    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    if request.method == "POST":
        return_loan(
            loan_id=loan_id,
            actual_end_date=date.today(),
            closed_by_user_id=2
        )
        return redirect(url_for("home"))

    return render_template("return.html", title="Rückgabe", loan=loan)



# ---------------------------------------------------
# Leihe verlängern
# ---------------------------------------------------
@app.route("/extend-loan/<int:loan_id>", methods=["POST"])
def extend_loan_route(loan_id):
    new_date_str = request.form.get("new_date")
    if not new_date_str:
        abort(400, "Neues Enddatum fehlt.")

    new_date = date.fromisoformat(new_date_str)

    extend_loan(loan_id=loan_id, new_end_date=new_date)

    return redirect(url_for("home"))



if __name__ == "__main__":
    app.run(debug=True)
