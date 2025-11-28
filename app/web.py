from dotenv import load_dotenv  # .env laden (für Supabase etc.)
load_dotenv()

from datetime import date
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify

from sqlalchemy import text
from app.config.database import SessionLocal

# loans importieren
from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    extend_loan,
    get_planned_periods_for_box,
    create_loan_with_validation,  # falls du sie hier nutzt
)

from app.services.loan_views import (  # NEU
    compute_loan_stats,
    filter_loans,
    sort_loans,
)

# boxes importieren
from app.services.boxes import (
    get_box_id_by_code,
    create_box,
)

# photos_storage importieren – neue Funktion für direkten Upload
from app.services.photos_storage import (
    upload_initial_photo_for_loan,
)

app = Flask(__name__)


# ---------------------------------------------------
# Übersicht
# ---------------------------------------------------
@app.route("/")
def home():
    # 1) Parameter
    sort_field = request.args.get("sort_field", "return_date").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    contact = request.args.get("contact", "").strip()
    status_filter = request.args.get("status", "").strip()

    # 2) Alle Leihen laden
    all_loans = list_loans()

    # 3) Statistiken berechnen (für die Kacheln)
    stats = compute_loan_stats(all_loans)

    # 4) Filter anwenden
    loans = filter_loans(all_loans, contact=contact, status=status_filter)

    # 5) Sortierung anwenden
    loans = sort_loans(loans, sort_field=sort_field, sort_dir=sort_dir)

    # 5b) Datum formatiert hinzufügen (TT.MM.JJJJ)
    for l in loans:
        if isinstance(l.get("planned_start_date"), date):
            l["planned_start_date_formatted"] = l["planned_start_date"].strftime("%d.%m.%Y")
        else:
            l["planned_start_date_formatted"] = l.get("planned_start_date")

        if isinstance(l.get("planned_end_date"), date):
            l["planned_end_date_formatted"] = l["planned_end_date"].strftime("%d.%m.%Y")
        else:
            l["planned_end_date_formatted"] = l.get("planned_end_date")

    # 6) Template rendern
    return render_template(
        "index.html",
        title="Übersicht",
        loans=loans,
        current_sort_field=sort_field,
        current_sort_dir=sort_dir,
        current_sort=f"{sort_field}_{sort_dir}",
        current_contact=contact,
        current_status=status_filter,
        # Statistik-Kacheln
        total_count=stats["total"],
        open_count=stats["open"],
        returned_count=stats["returned"],
        missing_count=stats["missing"],
        overdue_count=stats["overdue"],
    )
# ---------------------------------------------------
# Neue Leihe Formular (Schritt 1 – ohne Foto!)
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
    # Wenn Nutzer eine Zahl eingegeben hat → BOX-###
    if box_code.isdigit():
        box_code = f"BOX-{int(box_code):03d}"
    else:
        box_code = box_code.upper()

    box_id = get_box_id_by_code(box_code)

    if box_id is None:
        return jsonify({"box_id": None, "periods": []})

    periods = get_planned_periods_for_box(box_id)

    return jsonify({
        "box_id": box_id,
        "periods": [
            {"start": p["start"].isoformat(), "end": p["end"].isoformat()}
            for p in periods
        ]
    })




# ---------------------------------------------------
# Schritt 1 POST: Leihdaten verarbeiten, Box prüfen
# ---------------------------------------------------
@app.route("/start-loan", methods=["POST"])
def start_loan():
    from app.services.boxes import validate_box_code

    # Box-Code holen
    box_code_raw = request.form.get("box_code", "").strip()

    # === USER EINGIBT NUR ZAHL ===
    # Beispiel: "23" → "BOX-023"
    if box_code_raw.isdigit():
        box_code = f"BOX-{int(box_code_raw):03d}"
    else:
        box_code = box_code_raw.upper()

    # Formulardaten (für Fehler-Rückgabe)
    form_data = {
        "box_code": box_code_raw,  # User sieht weiterhin seine Eingabe
        "email": request.form.get("email", "").strip(),
        "ausgabe": request.form.get("ausgabe", "").strip(),
        "rueckgabe": request.form.get("rueckgabe", "").strip(),
    }

    # === FORMAT VALIDIEREN ===
    if not validate_box_code(box_code):
        return render_template(
            "new_loan.html",
            title="Neue Leihe",
            error="Bitte nur Zahlen eingeben (1 bis 3 Stellen).",
            **form_data
        )

    # === BOX EXISTIERT? ===
    existing_box_id = get_box_id_by_code(box_code)

    if existing_box_id is None:
        # → Box muss bestätigt werden
        return render_template(
            "confirm_new_box.html",
            title="Neue Box anlegen?",
            box_code=box_code,
            form_data=form_data,
        )

    # === LEIHE ANLEGEN (mit Fehlerbehandlung) ===
    try:
        loan_id = create_loan_with_validation(existing_box_id, form_data)
    except Exception as e:
        return render_template(
            "new_loan.html",
            title="Neue Leihe",
            error=str(e),
            **form_data
        )

    return redirect(url_for("upload_photo", loan_id=loan_id))


# ---------------------------------------------------
# Nutzer klickt auf JA oder NEIN beim Box-Anlegen
# ---------------------------------------------------
@app.route("/confirm-new-box", methods=["POST"])
def confirm_new_box():
    decision = request.form.get("decision")
    box_code = request.form.get("box_code", "").strip()

    form_data = {
        "box_code": box_code,
        "email": request.form.get("email", "").strip(),
        "ausgabe": request.form.get("ausgabe", "").strip(),
        "rueckgabe": request.form.get("rueckgabe", "").strip(),
    }

    if decision == "no":
        # Zurück zum Formular – optional: Werte wieder vorbelegen
        return render_template(
            "new_loan.html",
            title="Neue Leihe",
            current_date=date.today().isoformat(),
            **form_data,
        )

    if decision == "yes":
        new_box_id = create_box(box_code)
        loan_id = create_loan_with_validation(new_box_id, form_data)
        return redirect(url_for("upload_photo", loan_id=loan_id))

    abort(400, "Ungültige Auswahl.")


# ---------------------------------------------------
# Schritt 2: Foto-Seite (GET + POST)
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/photo", methods=["GET", "POST"])
def upload_photo(loan_id: int):
    # Leihe holen, damit wir z. B. Box-Code anzeigen können
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    if request.method == "POST":
        photo = request.files.get("photo")
        if not photo:
            abort(400, "Foto fehlt.")

        # 1) Foto nach Supabase hochladen (direkt unter loans/<id>/...)
        bucket_key = upload_initial_photo_for_loan(loan_id, photo)

        # 2) Foto-Eintrag in der DB (photos-Tabelle)
        with SessionLocal() as session:
            session.execute(
                text("""
                    INSERT INTO photos (loan_id, type, file_path, created_by_user_id)
                    VALUES (:loan_id, 'INITIAL', :file_path, :user_id)
                """),
                {
                    "loan_id": loan_id,
                    "file_path": bucket_key,
                    "user_id": 2,  # TODO: aus Login übernehmen
                }
            )
            session.commit()

        # TODO: hier später KI mit demselben Bild-Upload antriggern

        return redirect(url_for("home"))

    # GET → Template anzeigen
    return render_template(
        "upload_photo.html",
        title="Foto aufnehmen",
        loan=loan,
    )


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