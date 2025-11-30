from dotenv import load_dotenv  # .env laden (für Supabase etc.)
load_dotenv()

from datetime import date
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, session, flash

from sqlalchemy import text
from app.config.database import SessionLocal

import os
import bcrypt
from functools import wraps


# loans importieren
from app.services.loans import (
    list_loans,
    get_loan_by_id,
    return_loan,
    extend_loan,
    get_planned_periods_for_box,
    create_loan_with_validation,
)

from app.services.loan_views import (  # NEU
    compute_loan_stats,
    filter_loans,
    sort_loans,
)

from app.services.loan_status import (
    mark_overdue_loans,
    mark_missing_items,
    delete_loan_if_fully_returned
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
# user services importieren
from app.services.users import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    list_users,
    delete_user,
    update_password,
    ROLE_ADMIN,
    ROLE_HIWI,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key_change_me")
# ---------------------------------------------------
# Authentifizierung / User-Helfer
# ---------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Bitte melde dich zuerst an.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Bitte melde dich zuerst an.", "error")
            return redirect(url_for("login"))

        if session.get("user_role") != ROLE_ADMIN:
            abort(403)

        return view_func(*args, **kwargs)
    return wrapper

# =====================================================================
# Authentifizierung – LOGIN / LOGOUT / REGISTER
# =====================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", title="Login")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if not user:
        return render_template(
            "login.html",
            title="Login",
            message="Ungültige E-Mail oder Passwort."
        )

    stored_hash = user["password_hash"]
    if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        return render_template(
            "login.html",
            title="Login",
            message="Ungültige E-Mail oder Passwort."
        )

    # Login successful
    session["user_id"] = user["id"]
    session["user_name"] = user["username"]
    session["user_role"] = user["role"]

    flash("Login erfolgreich!", "success")
    return redirect(url_for("home"))


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Abgemeldet.", "info")
    return redirect(url_for("login"))

# ---------------------------------------------------------------------
# ADMIN: Benutzer anlegen
# ---------------------------------------------------------------------
import secrets

@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    if request.method == "GET":
        return render_template("register.html", title="Benutzer anlegen")

    username = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", ROLE_HIWI)

    if not username or not email:
        return render_template(
            "register.html",
            title="Benutzer anlegen",
            message="Bitte Name und E-Mail ausfüllen.",
            name=username,
            email=email,
            role=role,
        )

    initial_password = secrets.token_urlsafe(8)

    try:
        create_user(username, email, initial_password, role)
    except ValueError as e:
        return render_template(
            "register.html",
            title="Benutzer anlegen",
            message=str(e),
            name=username,
            email=email,
            role=role,
        )

    flash("Benutzer wurde angelegt!", "success")
    return render_template(
        "register.html",
        title="Benutzer anlegen",
        initial_password=initial_password,
    )

# ---------------------------------------------------------------------
# Passwort ändern
# ---------------------------------------------------------------------
@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password_route():
    if request.method == "GET":
        return render_template("change_password.html", title="Passwort ändern")

    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    new_pw_confirm = request.form.get("new_password_confirm", "")

    if new_pw != new_pw_confirm:
        return render_template(
            "change_password.html",
            title="Passwort ändern",
            error="Passwörter stimmen nicht überein."
        )

    user = get_user_by_id(session["user_id"])
    if not user or not bcrypt.checkpw(current_pw.encode("utf-8"),
                                      user["password_hash"].encode("utf-8")):
        return render_template(
            "change_password.html",
            title="Passwort ändern",
            error="Aktuelles Passwort ist falsch."
        )

    update_password(user["id"], new_pw)
    flash("Passwort erfolgreich geändert.", "success")
    return redirect(url_for("home"))

# =====================================================================
# ADMIN USER LIST / DELETE
# =====================================================================

@app.route("/admin/users")
@admin_required
def user_list():
    users = list_users()
    return render_template(
        "user_list.html",
        title="Benutzerverwaltung",
        users=users,
    )


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user_route(user_id):
    if session["user_id"] == user_id:
        flash("Du kannst dein eigenes Benutzerkonto nicht löschen.", "error")
        return redirect(url_for("user_list"))

    delete_user(user_id)
    flash("Benutzer gelöscht.", "success")
    return redirect(url_for("user_list"))

# ---------------------------------------------------
# Übersicht - nur für eingeloggte User
# ---------------------------------------------------
@app.route("/")
@login_required
def home():
    # 0) Stati aktualisieren: alle überfälligen auf OVERDUE setzen
    mark_overdue_loans(date.today())

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
# Loan Details Page
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>")
@login_required
def loan_details(loan_id: int):
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    # Format dates for display
    if isinstance(loan.get("planned_start_date"), date):
        loan["planned_start_date_formatted"] = loan["planned_start_date"].strftime("%d.%m.%Y")
    else:
        loan["planned_start_date_formatted"] = loan.get("planned_start_date")

    if isinstance(loan.get("planned_end_date"), date):
        loan["planned_end_date_formatted"] = loan["planned_end_date"].strftime("%d.%m.%Y")
    else:
        loan["planned_end_date_formatted"] = loan.get("planned_end_date")

    return render_template(
        "loan_details.html",
        title=f"Leihe {loan_id}",
        loan=loan,
    )
# ---------------------------------------------------
# Neue Leihe Formular (Schritt 1 – ohne Foto!)
# ---------------------------------------------------
@app.route("/new-loan")
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def extend_loan_route(loan_id):
    new_date_str = request.form.get("new_date")
    if not new_date_str:
        abort(400, "Neues Enddatum fehlt.")

    new_date = date.fromisoformat(new_date_str)

    extend_loan(loan_id=loan_id, new_end_date=new_date)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)