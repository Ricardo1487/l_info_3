from dotenv import load_dotenv

load_dotenv()  # .env laden (lokal); auf Render kommen die Variablen aus den Env-Settings

from datetime import date
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    jsonify,
)

from sqlalchemy import text
from app.config.database import SessionLocal

# Loans importieren
from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    extend_loan,
    get_planned_periods_for_box,
)

# Boxes importieren
from app.services.boxes import (
    get_box_id_by_code,
    create_box,
)

# Photos-Storage importieren (NEUE Variante, ohne temp/)
from app.services.photos_storage import (
    upload_initial_photo,
    replace_initial_photo,
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

    # Alle Leihen laden
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
            key=lambda l: get_issue_date(l) or date.max,
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
            key=lambda l: get_return_date(l) or date.max,
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
        current_date=date.today().isoformat(),
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
    return jsonify(
        {
            "box_id": box_id,
            "periods": [
                {
                    "start": p["start"].isoformat(),
                    "end": p["end"].isoformat(),
                }
                for p in periods
            ],
        }
    )


# ---------------------------------------------------
# Leihe anlegen (Schritt 1 – ohne Foto)
# ---------------------------------------------------
@app.route("/save-loan", methods=["POST"])
def save_loan():
    """
    Legt eine neue Leihe an, OHNE Foto.
    Danach wird auf eine zweite Seite weitergeleitet,
    auf der das Foto für diese Leihe hochgeladen wird.
    """

    box_code = request.form.get("box_code", "").strip()
    email = request.form.get("email", "").strip()
    ausgabe_str = request.form.get("ausgabe", "").strip()
    rueckgabe_str = request.form.get("rueckgabe", "").strip()

    if not box_code:
        abort(400, "Box-Code fehlt.")
    if not email:
        abort(400, "E-Mail fehlt.")
    if not ausgabe_str or not rueckgabe_str:
        abort(400, "Ausgabe- und Rückgabedatum sind Pflichtfelder.")

    try:
        planned_start = date.fromisoformat(ausgabe_str)
        planned_end = date.fromisoformat(rueckgabe_str)
    except ValueError:
        abort(400, "Datumsformat muss YYYY-MM-DD sein.")

    # Gültigkeit prüfen
    if planned_start < date.today():
        abort(400, "Ausgabedatum kann nicht in der Vergangenheit liegen.")
    if planned_end < planned_start:
        abort(400, "Rückgabedatum darf nicht vor dem Ausgabedatum liegen.")

    # Box-ID ermitteln oder neue Box anlegen
    box_id = get_box_id_by_code(box_code)
    if box_id is None:
        # Aktuell: Box ohne weitere Bestätigung anlegen
        box_id = create_box(box_code)

    # Überlappung prüfen:
    # Hier könnt ihr entscheiden, ob RETURNED blockieren soll oder nicht.
    with SessionLocal() as session:
        overlap = session.execute(
            text(
                """
                SELECT 1 FROM loans
                WHERE box_id = :bid
                  AND status IN ('OPEN', 'OVERDUE')
                  AND (
                        :new_start <= planned_end_date
                    AND :new_end   >= planned_start_date
                  )
                LIMIT 1
            """
            ),
            {
                "bid": box_id,
                "new_start": planned_start,
                "new_end": planned_end,
            },
        ).first()

        if overlap:
            abort(400, "Diese Box ist im angegebenen Zeitraum bereits ausgeliehen!")

    # Leihe speichern
    loan_id = create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=planned_start,
        planned_end_date=planned_end,
        created_by_user_id=2,  # später aus Login
    )

    # ➜ Weiter zur Foto-Seite
    return redirect(url_for("upload_loan_photo", loan_id=loan_id))


# ---------------------------------------------------
# Foto-Seite (Schritt 2 – Formular zum Foto-Upload)
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/photo", methods=["GET"])
def upload_loan_photo(loan_id: int):
    """
    Zeigt das Formular zum Hochladen oder Ersetzen des INITIAL-Fotos
    für eine existierende Leihe.
    """
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    return render_template("upload_photo.html", title="Foto hochladen", loan=loan)


# ---------------------------------------------------
# Foto speichern / ersetzen (Schritt 2 – POST)
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/photo", methods=["POST"])
def save_loan_photo(loan_id: int):
    """
    Nimmt das Foto entgegen und:

      - wenn es schon ein INITIAL-Foto gibt → ersetzt es
      - sonst → legt einen neuen Foto-Eintrag an

    In beiden Fällen wird das Bild direkt in den Supabase-Bucket
    unter loans/<loan_id>/... hochgeladen.
    """
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    photo = request.files.get("photo")
    if not photo:
        abort(400, "Foto fehlt.")

    with SessionLocal() as session:
        existing = session.execute(
            text(
                """
                SELECT id, file_path
                FROM photos
                WHERE loan_id = :lid AND type = 'INITIAL'
                LIMIT 1
            """
            ),
            {"lid": loan_id},
        ).mappings().first()

        if existing:
            # Es gibt schon ein Foto → ersetzen
            new_key = replace_initial_photo(
                file_storage=photo,
                loan_id=loan_id,
                old_key=existing["file_path"],
            )

            session.execute(
                text(
                    """
                    UPDATE photos
                    SET file_path = :p
                    WHERE id = :pid
                """
                ),
                {"p": new_key, "pid": existing["id"]},
            )
        else:
            # Noch kein Foto → neu anlegen
            new_key = upload_initial_photo(
                file_storage=photo,
                loan_id=loan_id,
            )

            session.execute(
                text(
                    """
                    INSERT INTO photos (loan_id, type, file_path, created_by_user_id)
                    VALUES (:lid, 'INITIAL', :p, 2)
                """
                ),
                {"lid": loan_id, "p": new_key},
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
            closed_by_user_id=2,  # später aus Login
        )
        return redirect(url_for("home"))

    return render_template("return.html", title="Rückgabe", loan=loan)


# ---------------------------------------------------
# Leihe verlängern
# ---------------------------------------------------
@app.route("/extend-loan/<int:loan_id>", methods=["POST"])
def extend_loan_route(loan_id: int):
    new_date_str = request.form.get("new_date")
    if not new_date_str:
        abort(400, "Neues Enddatum fehlt.")

    try:
        new_date = date.fromisoformat(new_date_str)
    except ValueError:
        abort(400, "Datumsformat muss YYYY-MM-DD sein.")

    extend_loan(loan_id=loan_id, new_end_date=new_date)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)