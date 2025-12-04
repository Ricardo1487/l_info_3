## Boxenverwaltung – Lager- & Ausleihmanagement mit KI-Unterstützung

Web-Applikation zur Verwaltung von Boxen, Leihvorgängen, Nutzern und KI-basierter Fotoanalyse.

---
### Inhaltsverzeichnis

1. Projektüberblick
2. Features
3. Technologien
4. Architektur
5. Projektstruktur
6. Installation
7. Deployment
8. Tests
9. KI-Bildanalyse (OpenAI Vision)
10. E-Mail Mock-System
11. Team
----
### 1. Projektüberblick

Die Boxenverwaltung ist eine Web-Applikation zur Verwaltung  von Laborboxen und Ausleihprozessen.
Die Software entsteht im Rahmen des Moduls L-Ingenieurinformatik III.


Sie deckt den gesamten Ablauf ab:

- Box anlegen
- Leihe starten
- Foto aufnehmen
- KI erkennt Gegenstände
- Rückgabefoto vergleichen
- fehlende Objekte automatisch erkennen

-----
### 2. Features

#### Boxenverwaltung

- automatische & manuelle Boxcodes
- QR-Code-Erzeugung
- Statusübersicht (frei, ausgeliehen, überfällig, fehlende Teile)
- Boxdetails

#### Leihmanagement

- Leihen anlegen inkl. Validierung
- Statuswechsel: UPCOMING → OPEN → RETURNED / OVERDUE / MISSING_ITEMS
- automatische Erkennung überfälliger Leihen
- Verlängerungen möglich
- Rückgabeprozess mit Fotovergleich
- automatische Bereinigung abgeschlossener Leihen

#### Benutzerverwaltung

- Rollen: ADMIN, HIWI
- Benutzer anlegen, löschen, Passwort ändern
- sichere Passwörter (bcrypt)

#### Fotoanalyse mit KI

- Initial- & Rückgabefotos
- automatische Objekterkennung
- Vergleich des Objektsatzes
- Erkennung fehlender Gegenstände

#### Mock-System

- simuliert ein zukünftiges E-Mail-System
- keine echten E-Mails
- vorbereitet für spätere echte Implementierung

---
### 3. Technologien
| Bereich            | Technologien       |
| ------------------ | ------------------ |
| **Backend**        | Python, Flask      |
| **Frontend**       | HTML, CSS, Jinja2  |
| **KI**             | OpenAI Vision      |
| **Datenbank**      | SQLAlchemy Core, PostgreSQL |
| **Storage**        | Supabase Object Storage |
| **Authentication** | Flask Sessions, bcrypt |
| **Testing**        | pytest             |
| **Deployment**     | Render             |

---
### 4. Architektur

Die Anwendung ist in drei Ebenen gegliedert:

#### 1. Web Layer 
- web.py
- HTML / CSS / Jinja2

#### 2. Service Layer
- boxes.py
- loans.py
- loan_status.py
- users.py
- photos_storage.py
- loan_views.py

#### 3. Infrastruktur / Daten
- database.py
- Supabase Storage
- SQL - Skripte in db
- image_analysis.py
-----
### 5. Projektstruktur

```text
.
+- app/
|  +- config/
|  |  +- database.py
|  |  +- image_analysis.py
|  |
|  +- services/
|  |  +- boxes.py
|  |  +- loans.py
|  |  +- loan_status.py
|  |  +- loan_views.py
|  |  +- photos_storage.py
|  |  +- users.py
|  |
|  +- static/
|  |  +- style.css
|  |
|  +- templates/
|  |  +- base.html (Hauptlayout)
|  |  ...weitere HTML-Templates (UI-Seiten, Formulare, Detailansichten)
|  +- web.py
|
+- db/
|  +- 001_init_schema.sql
|  +- 002_testdata.sql
|
+- scripts/
|  +- db_check.py
|  +- loan_demo.py
|
+- tests/
|   enthält die automatisierten pytest-Tests des Projekts:
|  +- Service-Tests (Boxen, Leihen, Nutzer)
|  +- Datenbank- und Konfigurations-Tests
|  +- KI-/Bildanalyse-Tests
|  +- Web-Routing-Tests
|
+- .github/
|  +- workflows/
|  | +- ci.yml
|
+- render.yaml
+- requirements.txt
+- runtime.txt
+- README.md

```
----
### 6. Installation


1. **Repository klonen**

    ```bash
    git clone <dein-repo-url>
    cd boxenverwaltung
    ```

2. **Virtuelle Umgebung erstellen (optional, empfohlen)**

    ```bash
    python -m venv .venv
    ```

3. **Virtuelle Umgebung aktivieren**

    **Windows:**
    ```bash
    .venv\Scripts\activate
    ```

    **macOS / Linux:**
    ```bash
    source .venv/bin/activate
    ```

4. **Abhängigkeiten installieren**

    ```bash
    pip install -r requirements.txt
    ```

5. **Environment-Datei erstellen**

    ```bash
    cp .env.example .env
    ```

6. **Environment-Variablen ausfüllen**

    ```text
    SUPABASE_URL=
    SUPABASE_SERVICE_KEY=
    SUPABASE_BUCKET=photos

    OPENAI_API_KEY=

    DATABASE_URL=

    FLASK_SECRET_KEY=
    ```

7. **Datenbank initialisieren (optional für lokale Nutzung)**

    ```bash
    psql -f db/001_init_schema.sql
    psql -f db/002_testdata.sql
    ```

8. **Anwendung starten**

    ```bash
    flask run
    ```

    Die Anwendung läuft anschließend unter:

    http://localhost:5000

---
### 7. Deployment

Die Anwendung kann auf Render, Railway oder jedem WSGI-fähigen Server betrieben werden.

Deployment-URL:
<https://l-info-3.onrender.com>

-----

### 8. Tests

**Tests ausführen**

    ```bash
    pytest -q
    ```
**Getestet werden:**

### Getestet werden:

- zentrale Funktionen für Boxen, Leihen und Benutzer  
- korrekte Verbindung zur Datenbank  
- zuverlässige KI-Bildauswertung  
- fehlerfreier Foto-Upload  
- Filtern, Sortieren und Auswerten von Leihen  
- Aufruf und Verhalten wichtiger Seiten  

----
### 9. KI-Bildanalyse (OpenAI Vision)

Die Anwendung nutzt ein Vision-fähiges KI-Modell über die OpenAI-Schnittstelle, um hochgeladene Fotos auszuwerten.
Das Modell liefert eine strukturierte Liste erkannter Gegenstände zurück,
zum Beispiel:

- Bezeichnung des Gegenstands
- geschätzte Anzahl
- Vertrauenswert

Die Analyse wird in der Funktion  analyze_image_file() durchgeführt.
Dort wird das Foto kodiert, an das Modell gesendet und die Antwort
zu einem einheitlichen Format verarbeitet ({"objects": [...]}).

Diese erkannten Objekte werden beim Rückgabeprozess automatisch
mit dem Initialfoto verglichen, um fehlende Gegenstände zu erkennen.

----
### 10. E-Mail Mock-System

Gemäß Aufgabenstellung wird die geplante E-Mail-Funktion noch nicht real implementiert, sondern über ein Mock-System simuliert.
Dieses System dient dazu, den späteren Funktionsumfang vorzubereiten, ohne echte Nachrichten zu versenden.

Das Mock-System:
- verschickt keine echten E-Mails
- schreibt simulierte E-Mail-Aktionen 
- lässt sich problemlos testen, ohne externe Dienste zu benötigen
- vermeidet den Umgang mit echten Nutzerdaten und ist damit datenschutzfreundlich

----

### 11. Team
| Name                 | Rolle                                         |
|----------------------|-----------------------------------------------|
| **Benli, Semih**     | QR-Code-Funktionalität, Boxenübersicht        |
| **Gießler, Ricardo** | API-Anbindung und technische Schnittstellen   |
| **Grosser, Ben**     | Entwicklung der zentralen Services (Kernlogik) |
| **Jerke, Julia**     | Adminfunktionen und Authentifizierung, CI-Integration
| **Scheer, Leonardo** | Frontend, UI-Design, Server-Deployment        |
| **Stöber, Noah**     | Testentwicklung, Filterfunktion, E-Mail Mock