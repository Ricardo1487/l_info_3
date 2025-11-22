from datetime import date
import os
from flask import Flask, render_template, request, redirect, url_for, abort

from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    extend_loan
)

from app.services.boxes import (
    get_box_id_by_code,
    create_box
)

from sqlalchemy import text
from app.config.database import SessionLocal

app = Flask(__name__)


@app.route("/")
def home():
    loans = list_loans()
    return render_template("index.html", title="Übersicht", loans=loans)



# ---------------------------------------------------
# Neue Leihe
# ---------------------------------------------------
@app.route("/new-loan")
def new_loan():
    return render_template(
        "new_loan.html",
        title="Neue Leihe",
        current_date=date.today().isoformat()
    )



@app.route("/save-loan", methods=["POST"])
def save_loan():
    box_code = request.form.get("box_code", "").strip()
    if not box_code:
        abort(400, "Box-Code fehlt.")

    # Foto holen
    photo = request.files.get("photo")
    if not photo:
        abort(400, "Foto muss hochgeladen werden!")

    # Temporär speichern
    os.makedirs("uploads/tmp", exist_ok=True)
    tmp_filename = f"tmp_{box_code}_{date.today()}.jpg"
    tmp_path = os.path.join("uploads/tmp", tmp_filename)
    photo.save(tmp_path)

    # Prüfen ob Box existiert
    existing_box_id = get_box_id_by_code(box_code)

    if existing_box_id is None:
        # Box NICHT vorhanden → Nachfragen
        return render_template(
            "confirm_new_box.html",
            title="Neue Box anlegen?",
            box_code=box_code,
            tmp_filename=tmp_filename,
            form_data=request.form
        )

    # Box existiert → weiter
    return process_loan_creation(existing_box_id, request.form, tmp_filename)



@app.route("/confirm-new-box", methods=["POST"])
def confirm_new_box():
    decision = request.form.get("decision")
    box_code = request.form.get("box_code")
    tmp_filename = request.form.get("tmp_filename")

    # Ursprüngliche Felder wiederherstellen
    form_data = {
        "box_code": request.form.get("box_code"),
        "email": request.form.get("email"),
        "ausgabe": request.form.get("ausgabe"),
        "rueckgabe": request.form.get("rueckgabe"),
    }

    if decision == "no":
        # Temp löschen
        tmp_path = os.path.join("uploads/tmp", tmp_filename)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        return render_template("new_loan.html", title="Neue Leihe")

    if decision == "yes":
        # Neue Box erstellen → AUTOMATISCH
        new_box_id = create_box(box_code)

        return process_loan_creation(new_box_id, form_data, tmp_filename)

    abort(400, "Ungültige Auswahl.")



# ---------------------------------------------------
# Zentrale Leihe-Erstellung
# ---------------------------------------------------
def process_loan_creation(box_id, form_data, tmp_filename):

    # Ausgabedatum validieren
    ausgabe = date.fromisoformat(form_data["ausgabe"])
    if ausgabe < date.today():
        abort(400, "Ausgabedatum kann nicht in der Vergangenheit liegen.")

    # Box darf nur 1 offene/überfällige Leihe haben
    with SessionLocal() as session:
        active = session.execute(
            text("""
                SELECT 1 FROM loans
                WHERE box_id = :bid
                  AND status IN ('OPEN', 'OVERDUE')
                LIMIT 1
            """),
            {"bid": box_id}
        ).first()

        if active:
            abort(400, "Diese Box ist bereits ausgeliehen!")

    # Temporäre Datei verschieben
    tmp_path = os.path.join("uploads/tmp", tmp_filename)
    final_dir = "uploads"
    os.makedirs(final_dir, exist_ok=True)

    final_filename = f"loan_{box_id}_{date.today()}.jpg"
    final_path = os.path.join(final_dir, final_filename)

    if os.path.exists(tmp_path):
        os.rename(tmp_path, final_path)
    else:
        abort(400, "Temporäres Foto nicht gefunden.")

    # Rest speichern
    email = form_data["email"]
    rueckgabe = date.fromisoformat(form_data["rueckgabe"])

    create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=ausgabe,
        planned_end_date=rueckgabe,
        created_by_user_id=2
    )

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
        actual_end = date.today()
        return_loan(
            loan_id=loan_id,
            actual_end_date=actual_end,
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

#seeyuuuh

if __name__ == "__main__":
    app.run(debug=True)

