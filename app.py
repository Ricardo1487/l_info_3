from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Ordner für Uploads konfigurieren
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Dummy-Datenbank
boxen = []

@app.route('/')
def home():
    return render_template('index.html', boxen=boxen, title="Übersicht")

@app.route('/new-loan')
def new_loan():
    return render_template('new_loan.html', title="Neue Leihe")

@app.route('/save-loan', methods=['POST'])
def save_loan():
    box_id = request.form['box_id']
    email = request.form['email']
    ausgabe = request.form['ausgabe']
    rueckgabe = request.form['rueckgabe']

    # Foto speichern
    file = request.files['photo']
    filename = secure_filename(f"{box_id}.jpg")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Neue Box speichern
    boxen.append({
        'id': box_id,
        'ausgabe': ausgabe,
        'rueckgabe': rueckgabe,
        'status': 'ausgeliehen',
        'email': email,
        'photo': filename
    })

    return redirect(url_for('home'))

# Route zum Abrufen von gespeicherten Bildern
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return app.send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 🔥 WICHTIG: GET + POST erlauben!
@app.route('/return/<box_id>', methods=['GET', 'POST'])
def return_box(box_id):
    if request.method == 'POST':

        # Beispiel: Status auf "zurückgegeben" setzen
        for box in boxen:
            if box['id'] == box_id:
                box['status'] = "zurückgegeben"

        # Später: Rückgabebild speichern + KI vergleichen

        return redirect(url_for('home'))

    # GET → Seite anzeigen
    return render_template('return.html', box_id=box_id, title="Rückgabe")

if __name__ == '__main__':
    # Ordner erstellen, falls nicht vorhanden
    if not os.path.exists('uploads'):
        os.makedirs('uploads')

    app.run(debug=True)
