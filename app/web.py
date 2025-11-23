from datetime import date

from flask import Flask, render_template, request, redirect, url_for, abort

from app.services.loans import (
    list_loans,
    create_loan,
    get_loan_by_id,
    return_loan,
)

app = Flask(__name__)


@app.route("/")
def home():
    """
    Übersichtsseite: zeigt alle aktuellen Leihen aus der Datenbank.
    """
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
    Formulardaten für eine neue Leihe entgegennehmen
    und in der Datenbank speichern.
    Erwartete Form-Felder:
      - box_id      (z. B. "1")
      - email       (Kontakt-E-Mail)
      - ausgabe     (YYYY-MM-DD)
      - rueckgabe   (YYYY-MM-DD)
    """
    try:
        box_id = int(request.form["box_id"])
    except (KeyError, ValueError):
        # Formulardaten unvollständig oder ungültig
        abort(400, description="Ungültige oder fehlende Box-ID")

    try:
        email = request.form["email"]
        ausgabe_str = request.form["ausgabe"]      # "2025-12-01"
        rueckgabe_str = request.form["rueckgabe"]  # "2025-12-10"
    except KeyError:
        abort(400, description="Fehlende Formularfelder")

    try:
        planned_start = date.fromisoformat(ausgabe_str)
        planned_end = date.fromisoformat(rueckgabe_str)
    except ValueError:
        abort(400, description="Datumsformat muss YYYY-MM-DD sein")

    # TODO: created_by_user_id später aus Login ermitteln.
    # Aktuell nutzen wir z. B. den HiWi mit id=2.
    created_by_user_id = 2

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
