from datetime import date

from flask import Flask, render_template, request, redirect, url_for, abort

from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
    delete_loan_if_fully_returned,
    mark_overdue_loans,
)

from app.services.boxes import get_or_create_box_id, create_box

app = Flask(__name__)


@app.route("/")
def home():
    """
    Übersichtsseite: zeigt alle aktuellen Leihen aus der Datenbank.
    """
    mark_overdue_loans(date.today())

    loans = list_loans()  # direkt aus Supabase über den Service
    return render_template("index.html", title="Übersicht", loans=loans)


@app.route("/new-loan")
def new_loan():
    """
    Formular für eine neue Leihe anzeigen.
    """
    return render_template("new_loan.html", title="Neue Leihe")


@app.route("/save-loan", methods=["POST"])
def save_loan():
    """
    Formulardaten für eine neue Leihe entgegennehmen.
    Wenn die Box noch nicht existiert, zuerst nachfragen,
    ob sie angelegt werden soll.
    """

    # --- Formularwerte auslesen ---
    try:
        box_code = request.form["box_code"].strip()
        email = request.form["email"]
        ausgabe_str = request.form["ausgabe"]
        rueckgabe_str = request.form["rueckgabe"]
    except KeyError:
        abort(400, description="Fehlende Formularfelder")

    try:
        planned_start = date.fromisoformat(ausgabe_str)
        planned_end = date.fromisoformat(rueckgabe_str)
    except ValueError:
        abort(400, description="Datumsformat muss YYYY-MM-DD sein")

    # --- Prüfen, ob Box existiert ---
    box_id = get_box_id_by_code(box_code)

    # Hat der User schon bestätigt, dass Box erstellt werden soll?
    confirm = request.form.get("confirm_create_box")  # kann None, "yes", "no" sein

    if box_id is None and confirm is None:
        # 1. Runde: Box existiert nicht, noch keine Bestätigung -> Nachfrage anzeigen
        return render_template(
            "confirm_new_box.html",
            title="Neue Box anlegen?",
            box_code=box_code,
            email=email,
            ausgabe=ausgabe_str,
            rueckgabe=rueckgabe_str,
        )

    if box_id is None and confirm == "no":
        # User hat abgebrochen -> zurück zum Formular
        return redirect(url_for("new_loan"))

    if box_id is None and confirm == "yes":
        # User hat zugestimmt -> Box jetzt anlegen
        box_id = create_box(box_code)

    # Ab hier ist garantiert: box_id ist eine gültige int
    created_by_user_id = 2  # TODO: später aus Login

    create_loan(
        box_id=box_id,
        contact_email=email,
        planned_start_date=planned_start,
        planned_end_date=planned_end,
        created_by_user_id=created_by_user_id,
    )

    return redirect(url_for("home"))


@app.route("/return/<int:loan_id>", methods=["GET", "POST"])
def return_box(loan_id: int):
    """
    Rückgabe einer Leihe.
    GET:  Bestätigungsseite anzeigen.
    POST: Leihe als zurückgegeben markieren.
    """
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, description="Leihe nicht gefunden")

    if request.method == "POST":
        # Fürs erste: Rückgabedatum = heute.
        actual_end = date.today()

        # TODO: closed_by_user_id später aus Login ermitteln.
        closed_by_user_id = 2

        return_loan(
            loan_id=loan_id,
            actual_end_date=actual_end,
            closed_by_user_id=closed_by_user_id,
        )
        return redirect(url_for("home"))

    # GET: Rückgabe-Template anzeigen
    return render_template(
        "return.html",
        title="Rückgabe",
        loan=loan,
    )


if __name__ == "__main__":
    # Lokaler Entwicklungsstart:
    # python -m app.web
    app.run(debug=True)
