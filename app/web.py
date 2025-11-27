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
    # Filterwerte aus der URL lesen
    sort_field = request.args.get("sort_field", "return_date").strip()  # Standard: Rückgabedatum
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()      # Standard: aufsteigend
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    contact = request.args.get("contact", "").strip()
    status_filter = request.args.get("status", "").strip()

    # Loans laden
    loans_raw = list_loans()

    # -- Statistik --
    open_loans = sum(1 for l in loans_raw if l["status"] in ("OPEN", "OVERDUE"))
    returned_loans = sum(1 for l in loans_raw if l["status"] == "RETURNED")
    missing_loans = sum(1 for l in loans_raw if l["status"] == "MISSING_ITEMS")

    # -- Filter nach Kontakt --
    if contact:
        search = contact.lower()
        loans_raw = [
            l for l in loans_raw
            if search in (l.get("contact_email", "").lower())
        ]

    # -- Filter nach Status --
    if status_filter:
        loans_raw = [l for l in loans_raw if l.get("status") == status_filter]

    # -- Sortierfunktionen --
    def get_issue_date(loan):
        return loan.get("planned_start_date")

    def get_return_date(loan):
        return loan.get("planned_end_date")

    # Welches Feld wird sortiert?
    if sort_field == "issue_date":
        key_func = get_issue_date
    else:
        # Fallback + Standard: Rückgabedatum
        sort_field = "return_date"
        key_func = get_return_date

    # -- Sortierung anwenden --
    if sort_dir == "asc":
        loans_raw = sorted(loans_raw, key=lambda l: key_func(l) or date.max)
    else:
        loans_raw = sorted(loans_raw, key=lambda l: key_func(l) or date.min, reverse=True)

    return render_template(
        "index.html",
        title="Übersicht",
        loans=loans_raw,
        current_sort_field=sort_field,
        current_sort_dir=sort_dir,
        current_contact=contact,
        current_status=status_filter,
        open_count=open_loans,
        returned_count=returned_loans,
        missing_count=missing_loans,
        # optional, falls irgendwo noch benutzt:
        current_sort=f"{sort_field}_{sort_dir}",
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
# Hilfsfunktion: Leihe mit Validierung anlegen
# ---------------------------------------------------
def _create_loan_with_validation(box_id: int, form_data: dict) -> int:
    """Validiert Datumslogik + Überschneidungen und legt eine Leihe an."""

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

    # Überlappung prüfen
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

    # OK → Leihe anlegen
    return create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=ausgabe,
        planned_end_date=rueckgabe,
        created_by_user_id=2,
    )



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
        loan_id = _create_loan_with_validation(existing_box_id, form_data)
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
        # Neue Box anlegen, dann Leihe anlegen
        new_box_id = create_box(box_code)
        loan_id = _create_loan_with_validation(new_box_id, form_data)
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