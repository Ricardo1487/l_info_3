from dotenv import load_dotenv  # .env laden (für Supabase etc.)
from sqlalchemy.sql.functions import current_user

load_dotenv()

from datetime import date
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, session, flash

from sqlalchemy import text
from app.config.database import SessionLocal
from app.config.image_analysis import analyze_image_file

import os
import bcrypt
from functools import wraps


# loans importieren
from app.services.loans import (
    list_loans,
    get_loan_by_id,
    extend_loan,
    get_planned_periods_for_box,
    create_loan_with_validation,
    get_detected_objects_for_photo,
    compare_object_sets,
    delete_loan_if_fully_returned
)

from app.services.loan_views import (  # NEU
    compute_loan_stats,
    filter_loans,
    sort_loans,
)

from app.services.loan_status import (
    mark_overdue_loans,
    return_loan,
    return_with_missing_items
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

    # 5c) Erkannte Inhalte aus dem INITIAL-Foto an jede Leihe hängen
    with SessionLocal() as session:
        for l in loans:
            try:
                contents = get_detected_objects_for_photo(session, l["id"], "INITIAL")
            except Exception:
                contents = {}
            l["initial_contents"] = contents

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
        loan_id = create_loan_with_validation(
            existing_box_id,
            form_data,
            created_by_user_id=session["user_id"],)
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
        loan_id = create_loan_with_validation(
            new_box_id,
            form_data,
            created_by_user_id=session["user_id"],
        )
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

        # 0) Bild mit KI analysieren (Inhalt erkennen)
        try:
            analysis = analyze_image_file(photo)
            print("ANALYSIS RESULT:", analysis)
            detected_objects = analysis.get("objects", [])
            print("DETECTED OBJECTS:", detected_objects)
        except Exception as e:
            # Wenn Analyse fehlschlägt, Leihe trotzdem speichern
            print("Fehler bei der Bildanalyse:", e)
            detected_objects = []

        # 1) Foto nach Supabase hochladen (direkt unter loans/<id>/...)
        bucket_key = upload_initial_photo_for_loan(loan_id, photo)

        # 2) Foto-Eintrag in der DB (photos-Tabelle)
        with SessionLocal() as session:
            result = session.execute(
                text("""
                    INSERT INTO photos (loan_id, type, file_path)
                    VALUES (:loan_id, 'INITIAL', :file_path)
                    RETURNING id
                """),
                {
                    "loan_id": loan_id,
                    "file_path": bucket_key,

                }
            )
            photo_id = result.scalar_one()

            for obj in detected_objects:
                session.execute(
                    text("""
                        INSERT INTO detected_objects (photo_id, label, confidence, quantity, is_manually_edited)
                        VALUES (:photo_id, :label, :confidence, :quantity, false)
                    """),
                    {
                        "photo_id": photo_id,
                        "label": obj.get("label"),
                        "confidence": obj.get("confidence"),
                        "quantity": obj.get("quantity", 1),
                    }
                )

            session.commit()

        return redirect(url_for("review_initial_contents", loan_id=loan_id))

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

    # GET: Direkt in den neuen Rückgabe-Foto-Flow verzweigen
    return redirect(url_for("upload_return_photo", loan_id=loan_id))


# ---------------------------------------------------
# Rückgabe-Foto hochladen & KI-Analyse (RETURN)
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/return-photo", methods=["GET", "POST"])
@login_required
def upload_return_photo(loan_id: int):
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    if request.method == "POST":
        photo = request.files.get("photo")
        if not photo:
            abort(400, "Foto fehlt.")

        # Bild mit KI analysieren (Inhalt bei Rückgabe erkennen)
        try:
            analysis = analyze_image_file(photo)
            print("RETURN ANALYSIS:", analysis)
            detected_objects = analysis.get("objects", [])
            print("RETURN OBJECTS:", detected_objects)
        except Exception as e:
            print("Fehler bei der Rückgabe-Bildanalyse:", e)
            detected_objects = []

        # Foto nach Supabase hochladen (wir verwenden die gleiche Helper-Funktion)
        bucket_key = upload_initial_photo_for_loan(loan_id, photo)

        # Foto-Eintrag + erkannte Objekte als RETURN speichern
        with SessionLocal() as session:
            result = session.execute(
                text("""
                    INSERT INTO photos (loan_id, type, file_path)
                    VALUES (:loan_id, 'RETURN', :file_path)
                    RETURNING id
                """),
                {
                    "loan_id": loan_id,
                    "file_path": bucket_key,
                }
            )
            photo_id = result.scalar_one()

            for obj in detected_objects:
                session.execute(
                    text("""
                        INSERT INTO detected_objects (photo_id, label, confidence, quantity, is_manually_edited)
                        VALUES (:photo_id, :label, :confidence, :quantity, false)
                    """),
                    {
                        "photo_id": photo_id,
                        "label": obj.get("label"),
                        "confidence": obj.get("confidence"),
                        "quantity": obj.get("quantity", 1),
                    }
                )

            session.commit()

        # Nach dem Upload/Analyse zur Rückgabe-Review-Seite
        return redirect(url_for("review_return_contents", loan_id=loan_id))

    # GET: Formular zum Rückgabe-Foto hochladen anzeigen (wir nutzen das existierende Template)
    return render_template(
        "upload_photo.html",
        title="Rückgabe-Foto aufnehmen",
        loan=loan,
    )


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


# ---------------------------------------------------
# Foto & erkannte Inhalte nach Upload prüfen/bearbeiten
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/review-initial", methods=["GET", "POST"])
def review_initial_contents(loan_id: int):
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    with SessionLocal() as session:
        # letztes INITIAL-Foto zur Leihe holen
        photo_row = session.execute(
            text(
                """
                SELECT id, file_path
                FROM photos
                WHERE loan_id = :loan_id
                  AND type = 'INITIAL'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"loan_id": loan_id},
        ).mappings().first()

        if photo_row is None:
            abort(404, "Kein Initial-Foto für diese Leihe gefunden.")

        photo_id = photo_row["id"]
        file_path = photo_row["file_path"]

        if request.method == "POST":
            # vorhandene Objekte laden, um sie zu aktualisieren oder zu löschen
            obj_rows = session.execute(
                text(
                    """
                    SELECT id
                    FROM detected_objects
                    WHERE photo_id = :photo_id
                    """
                ),
                {"photo_id": photo_id},
            ).mappings().all()

            for row in obj_rows:
                obj_id = row["id"]
                label = request.form.get(f"label_{obj_id}")
                quantity_raw = request.form.get(f"quantity_{obj_id}")
                delete_flag = request.form.get(f"delete_{obj_id}") == "on"

                if delete_flag:
                    session.execute(
                        text(
                            """
                            DELETE FROM detected_objects
                            WHERE id = :id
                            """
                        ),
                        {"id": obj_id},
                    )
                else:
                    try:
                        quantity = int(quantity_raw) if quantity_raw else 1
                    except ValueError:
                        quantity = 1

                    session.execute(
                        text(
                            """
                            UPDATE detected_objects
                            SET label = :label,
                                quantity = :quantity,
                                is_manually_edited = true
                            WHERE id = :id
                            """
                        ),
                        {
                            "label": label,
                            "quantity": quantity,
                            "id": obj_id,
                        },
                    )

            session.commit()
            return redirect(url_for("home"))

        # GET: erkannte Objekte zum Anzeigen laden
        objects = session.execute(
            text(
                """
                SELECT id, label, quantity, confidence, is_manually_edited
                FROM detected_objects
                WHERE photo_id = :photo_id
                ORDER BY id
                """
            ),
            {"photo_id": photo_id},
        ).mappings().all()

    return render_template(
        "review_initial_contents.html",
        title="Foto & Inhalt prüfen",
        loan=loan,
        photo_path=file_path,
        objects=objects,
    )

# ---------------------------------------------------
# Rückgabe prüfen: INITIAL vs RETURN + Missing Items
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/review-return", methods=["GET", "POST"])
@login_required
def review_return_contents(loan_id: int):
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    with SessionLocal() as session:
        initial_photo = session.execute(
            text(
                """
                SELECT file_path
                FROM photos
                WHERE loan_id = :loan_id AND type = 'INITIAL'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"loan_id": loan_id},
        ).mappings().first()

        return_photo = session.execute(
            text(
                """
                SELECT file_path
                FROM photos
                WHERE loan_id = :loan_id AND type = 'RETURN'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"loan_id": loan_id},
        ).mappings().first()

        initial_objects = get_detected_objects_for_photo(session, loan_id, "INITIAL")
        returned_objects = get_detected_objects_for_photo(session, loan_id, "RETURN")
        missing_objects = compare_object_sets(initial_objects, returned_objects)

        if request.method == "POST":
            today = date.today()

            # Wenn etwas fehlt → Missing Items markieren, sonst ggf. Loan aufräumen
            try:
                if missing_objects:
                    # 🔴 Es fehlen Teile → Leihe als MISSING_ITEMS abschließen
                    return_with_missing_items(
                        loan_id=loan_id,
                        actual_end_date=today,
                        closed_by_user_id=2,  # TODO: session["user_id"]
                    )
                else:
                    # ✅ Alles da → Leihe als RETURNED markieren
                    return_loan(
                        loan_id=loan_id,
                        actual_end_date=today,
                        closed_by_user_id=2,  # TODO: session["user_id"]
                    )

                    delete_loan_if_fully_returned(loan_id)
            except Exception as e:
                print("Fehler beim Markieren/Löschen der Leihe:", e)

            return redirect(url_for("home"))

    return render_template(
        "review_return_contents.html",
        title="Rückgabe prüfen",
        loan=loan,
        initial_photo_path=initial_photo["file_path"] if initial_photo else None,
        return_photo_path=return_photo["file_path"] if return_photo else None,
        initial_objects=initial_objects,
        returned_objects=returned_objects,
        missing_objects=missing_objects,
    )

# ---------------------------------------------------
# Inhalt einer Leihe prüfen (INITIAL vs RETURN)
# ---------------------------------------------------
@app.route("/loan/<int:loan_id>/check-contents")
def check_loan_contents(loan_id: int):
    loan = get_loan_by_id(loan_id)
    if loan is None:
        abort(404, "Leihe nicht gefunden.")

    # INITIAL- und RETURN-Objekte laden und vergleichen
    with SessionLocal() as session:
        initial_objects = get_detected_objects_for_photo(session, loan_id, "INITIAL")
        returned_objects = get_detected_objects_for_photo(session, loan_id, "RETURN")
        missing_objects = compare_object_sets(initial_objects, returned_objects)

    return render_template(
        "check_contents.html",
        title="Inhalt prüfen",
        loan=loan,
        initial_objects=initial_objects,
        returned_objects=returned_objects,
        missing_objects=missing_objects,
    )

if __name__ == "__main__":
    app.run(debug=True)
