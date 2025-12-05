# Testdokumentation

Dieses Dokument beschreibt die Teststrategie, die Testabdeckung und die
wichtigsten technischen Entscheidungen rund um die automatisierten Tests
der Boxenverwaltungs-Applikation.

Die Tests werden mit **pytest** ausgeführt und konzentrieren sich auf
Unit- und Service-Tests, die ohne echte externe Systeme (Datenbank,
Supabase, OpenAI) laufen. Zusätzlich gibt es leichte Integrations- und
View-Tests mit dem Flask-Testclient.

---

## 1. Ziel der Tests

Die Tests sollen sicherstellen, dass

- die Kernlogik für **Leihen**, **Boxen**, **Benutzer**, **Status** und
  **KI-Auswertung** korrekt funktioniert,
- externe Abhängigkeiten (Datenbank, Supabase, OpenAI, E-Mail) sauber
  gekapselt und für Tests mockbar sind,
- kritische Pfade wie **Statuswechsel**, **Datumslogik** und
  **Validierung** robust sind,
- die Anwendung stabil in CI/CD läuft (`pytest` in GitHub Actions).

---

## 2. Test-Setup & Ausführung

### 2.1 Voraussetzungen

- Python-Abhängigkeiten installiert (`pip install -r requirements.txt`)
- Virtuelle Umgebung (empfohlen)
- Kein echter Zugang zu Supabase/OpenAI notwendig – wird gemockt

### 2.2 Tests lokal ausführen

Im Projektverzeichnis:

```bash
pytest
```

Optional mit ausführlicherer Ausgabe:

```bash
pytest -vv
```

Optional mit Coverage (falls `pytest-cov` installiert ist):

```bash
pytest --cov=app
```

Die Tests sind so geschrieben, dass sie **ohne echte Netzwerkzugriffe**
und **ohne echte Datenbank** laufen. Die notwendigen Umgebungsvariablen
(Supabase, OpenAI) werden in den Tests bzw. in `conftest.py` gesetzt
oder gemockt.

---

## 3. Teststruktur

Die Tests liegen im Verzeichnis `tests/` und sind grob nach
Verantwortlichkeiten gruppiert:

| Datei                      | Getesteter Bereich                                  |
|---------------------------|-----------------------------------------------------|
| `conftest.py`             | zentrales Test-Setup (Dummy-Supabase)               |
| `test_database_config.py` | DB-Konfiguration & `SessionLocal`                   |
| `test_boxes.py`           | Box-Service (Boxcodes, QR, create_box)              |
| `test_loans.py`           | Loan-Service (Erstellen, Status, Inhalte)           |
| `test_loan_views.py`      | Filter & Sortierung im Dashboard, Statistiken       |
| `test_loan_status.py`     | Status-Logik (OVERDUE, RETURNED, MISSING…)          |
| `test_users_service.py`   | User-Service (CRUD, Passwort-Update)                |
| `test_photos_storage.py`  | Supabase-Storage-Wrapper                            |
| `test_image_analysis.py`  | KI-Anbindung (OpenAI-Client, JSON-Parsing)          |
| `test_email_mock.py`      | E-Mail-/Reminder-Mock (Logfile-Schreiben)           |
| `test_web_home.py`        | View-/Home-Tests mit Flask-Testclient               |
| `test_placeholder.py`     | Minimaler Sanity-Check                              |

---

## 4. zentrales Test-Setup (`conftest.py`)

`conftest.py` sorgt dafür, dass Tests **ohne echte Supabase-Bibliothek**
laufen können:

- Setzt Dummy-Umgebungsvariablen:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_KEY`
  - `SUPABASE_BUCKET`
- Erzeugt ein Dummy-Modul `supabase` mit:
  - `DummySupabaseClient`
  - `create_client(...)`
- Registriert das Dummy-Modul über `sys.modules["supabase"] = dummy_module`

Dadurch können Module wie `photos_storage` ganz normal importiert
werden, ohne dass echte Supabase-Clients oder Secrets benötigt werden.

---

## 5. Tests nach Themenbereich

### 5.1 Datenbank-Konfiguration (`test_database_config.py`)

Ziele:

- Sicherstellen, dass `app.config.database` korrekt mit ENV-Werten
  umgeht.
- Prüfen, dass bei gültiger `DATABASE_URL`:
  - eine `Engine` erzeugt wird,
  - `SessionLocal` ein `sessionmaker` ist,
  - Session-Objekte erzeugt werden können.

Techniken:

- `monkeypatch` für `os.environ`
- `importlib.reload`, um `app.config.database` mit neuen Env-Werten neu
  zu laden.

---

### 5.2 Box-Service (`test_boxes.py`)

Ziele:

- Korrekte Generierung der QR-Payload:
  - Verwendung von `PUBLIC_BASE_URL`
  - korrekte URL wie `/new-loan?box_code=...`
- Validierung von Boxcodes:
  - gültige Formate (`BOX-###`, numerische IDs)
  - invalide Codes → `ValueError`
- Ermitteln einer `box_id` zu einem Box-Code (`get_box_id_by_code`)
- Anlegen einer neuen Box (`create_box`):
  - verwendung des höchsten existierenden `box_id` zur neuen Nummer
  - validiert den Code vor dem Insert
  - committed die Session korrekt

Techniken:

- Dummy-Session-Klassen (mit `.execute`, `.commit`)
- `monkeypatch` für `SessionLocal`

---

### 5.3 Loan-Service (`test_loans.py`)

Sehr umfangreicher Testbereich. Es werden u. a. geprüft:

- **`create_loan`**
  - Unterscheidung:
    - Startdatum heute / in der Vergangenheit → Status `OPEN`
    - Startdatum in der Zukunft → Status `UPCOMING`
  - Datumslogik:
    - `planned_end_date < planned_start_date` → `ValueError`
- **`create_loan_with_validation`**
  - Prüft, ob sich Leihzeiträume überschneiden
  - Bei Overlap → `ValueError`
  - Bei keiner Überlappung → neue Leihe wird angelegt
- **`get_detected_objects_for_photo`**
  - Aggregation von KI-Ergebnissen zu einem Mapping
    (`{"Kabel": 3, "Adapter": 1}`)
- **`delete_loan_if_fully_returned`**
  - Verhalten, wenn die Leihe nicht existiert → `False`
  - Verhalten, wenn sie existiert und zurückgegeben ist:
    - dazugehörige Fotos werden geladen
    - Storage-Pfade werden gelöscht (via Photos-Storage)
    - Datenbank-Entry wird gelöscht
- **`get_initial_contents_for_all_loans`**
  - Baut ein verschachteltes Dict:
    - `{loan_id: {label: qty, ...}, ...}`
- **`update_loan_basic_data`**
  - Aktualisiert Kontakt-E-Mail & geplante Daten
  - Commit-Verhalten wird geprüft

Techniken:

- Dummy-Result-Klassen (`DummyResultFirst`, `DummyResultMappingsAll`)
- Dummy-Sessions mit `.execute`, `.commit`
- `monkeypatch` für `SessionLocal` und für Servicefunktionen wie
  `create_loan`

---

### 5.4 Loan-Views (`test_loan_views.py`)

Getestet werden:

- **`compute_loan_stats`**
  - Zählt verschiedene Status:
    - `OPEN`, `RETURNED`, `MISSING_ITEMS`, `OVERDUE`, `UPCOMING`
  - Erkennt „recent“ zurückgegebene Leihen (z. B. innerhalb der letzten
    X Tage)
- **`filter_loans`**
  - Filter nach:
    - Status
    - Kontakt-E-Mail (`contact`)
    - Box-Code
  - Kombination von Filtern
- **`sort_loans`**
  - Sortierung nach:
    - Boxnummer (numerisch aus `BOX-XYZ`)
    - Rückgabedatum
    - Leih-ID
  - auf- und absteigend (`asc` / `desc`)

Hier werden reine Python-Funktionen getestet, ohne DB oder HTTP.

---

### 5.5 Loan-Status (`test_loan_status.py`)

Ziele:

- **`close_loan` (interne Funktion wie `_close_loan`)**
  - committed genau einmal
  - setzt korrekt:
    - Status
    - `actual_end_date`
    - `closed_by_user_id`
- **`mark_overdue_loans`**
  - setzt Status auf `OVERDUE`, wenn `planned_end_date < heute` und
    Status noch `OPEN` ist
  - berücksichtigt `rowcount`, um zu erkennen, wie viele Leihen
    betroffen sind
- **`return_with_missing_items`**
  - ruft intern `_close_loan` mit Status `MISSING_ITEMS` auf
  - übergibt korrekt `loan_id`, Datum und User-ID

Techniken:

- Dummy-Result mit `rowcount`
- Monkeypatch für `_close_loan` (stellt sicher, dass richtige Parameter
  übergeben werden)

---

### 5.6 User-Service (`test_users_service.py`)

Getestete Funktionen u. a.:

- `list_users`
  - liefert alle Benutzer als Liste von Dicts
- `get_user_by_email`
  - findet User anhand der E-Mail oder gibt `None` zurück
- `create_user`
  - legt neuen Nutzer mit Rolle und gehashtem Passwort an
- `update_password`
  - aktualisiert `password_hash` per UPDATE-Statement
  - `commit` wird genau einmal ausgeführt

Techniken:

- Dummy-Result mit `.mappings().first() / all() / scalar_one()`
- Dummy-Sessions (`executed`-Liste wird ausgewertet)
- Prüfung, dass SQL grob korrekt ist (z. B. `"UPDATE users SET password_hash"` enthalten)

---

### 5.7 Photos-Storage (`test_photos_storage.py`)

Ziele:

- korrekte Pfadgenerierung für Uploads:
  - z. B. `loans/<loan_id>/<filename>`
- Interaktion mit Supabase-Storage:
  - `upload(...)` wird mit den richtigen Parametern aufgerufen
  - `remove([...])` löscht die richtigen Pfade
  - `get_public_url(key)` liefert eine URL, die im Frontend genutzt
    werden kann
- Verhalten bei leerem Pfad:
  - `get_public_url("")` → `None`
  - es darf kein Call an Supabase erfolgen

Techniken:

- DummyFileStorage (simuliert Flask `FileStorage`)
- DummyBucket (`upload_calls`, `remove_calls`, `public_url_calls`)
- DummyStorage (simuliert `supabase.storage.from_(...)`)

---

### 5.8 Image-Analysis (`test_image_analysis.py`)

Ziele:

- **`_get_client`**
  - ohne `OPENAI_API_KEY` → `RuntimeError`
  - mit `OPENAI_API_KEY` → OpenAI-Client wird erstellt
- **`analyze_image_file`**
  - sendet ein Bild an den Client
  - kann verschiedene Antwortformate verarbeiten:
    - reines JSON
    - JSON innerhalb eines ```json-Codeblocks
    - Listen von Content-Chunks
  - Ergebnisformat:
    - `{"objects": [{"label": "...", "quantity": ..., "confidence": ...}]}`

Techniken:

- Dummy-Client-Klassen, die `responses` simulieren
- DummyFileStorage mit `.stream`
- `monkeypatch` für `_get_client`, um keine echten API-Calls zu machen

---

### 5.9 Placeholder (`test_placeholder.py`)

Ein minimaler Test:

```python
def test_placeholder():
    assert True
```

Zweck:

- Sicherstellen, dass `pytest` auch dann nicht mit Exit-Code 5 (keine
  Tests gefunden) fehlschlägt, falls in frühen Stadien Tests temporär
  entfernt oder umbenannt werden.

---

### 5.10 E-Mail-Mock & Overdue-Logging (`test_email_mock.py`)

Ziele:

- Sicherstellen, dass das **E-Mail-Mock-System** korrekt in ein Logfile
  schreibt (statt echte Mails zu versenden).
- Überprüfen, dass **überfällige Leihen** über `log_overdue_loans`
  sauber protokolliert werden.

Getestet wird u. a.:

- **`email_mock.send_email(...)`**
  - `LOG_FILE` wird im Test per `monkeypatch` auf ein temporäres File
    umgebogen (`tmp_path / "emails.log"`).
  - Aufruf von `send_email(to=..., subject=..., body=..., category=...)`
    erzeugt eine neue Zeile im Logfile.
  - Das Logfile existiert danach und ist nicht leer.

- **`loan_views.log_overdue_loans(loans)`**
  - bekommt eine Liste von Loan-Dictionaries mit Feldern wie:
    - `contact_email`
    - `planned_end_date`
    - `status`
  - nur Leihen, die **überfällig** sind (z. B. `planned_end_date < heute`
    und Status `OPEN`), lösen Schreiboperationen ins Logfile aus.
  - Der Test prüft, dass:
    - das Logfile angelegt wurde,
    - die betroffene E-Mail-Adresse im Inhalt vorkommt,
    - Hinweise wie `"overdue"` oder `"notice"` im Text vorhanden sind.

Techniken:

- `tmp_path`-Fixture für isolierte Logfiles
- `monkeypatch.setattr(email_mock, "LOG_FILE", test_log)`
- Einfacher End-to-End-Test für den Pfad „Überfällige Leihen → E-Mail-Mock-Log“.

---

### 5.11 Web-/Home-Tests mit Flask-Testclient (`test_web_home.py`)

Ziele:

- Basis-Integrationstest der Startseite (`/`) und des Login-Flows.
- Sicherstellen, dass das Dashboard auch mit komplett gemockten
  Hintergrundfunktionen (DB, Services) fehlerfrei rendert.
- Prüfen des Login-Verhaltens über die echte `/login`-Route.

Kernelement ist eine `client`-Fixture:

```python
@pytest.fixture
def client(monkeypatch):
    import app.web as web_module
    ...
    return web_module.app.test_client()
```

Diese Fixture:

- patcht alle kritischen Funktionen im `web`-Modul, z. B.:
  - `list_loans` – liefert eine kleine Dummy-Liste von Leihen
  - `compute_loan_stats` – liefert vordefinierte Zahlen
  - `filter_loans` / `sort_loans` – einfache Durchleiter oder Dummies
  - `mark_overdue_loans` – wird zu einem No-Op
- setzt eine gültige Session (eingeloggter User) über Flask-Testclient
  und `with client.session_transaction() as sess: ...`.

Getestet wird u. a.:

- **`GET /`**
  - Statuscode ist `200`.
  - HTML enthält erwartete Elemente (z. B. Überschriften, Tabellen,
    Filterfelder).

- **`GET /` mit Query-Parametern**
  - z. B. `?status=OPEN&box=23`
  - stellt sicher, dass die Filter-Funktionen aufgerufen werden und die
    Seite trotzdem korrekt rendert.

- **`POST /login`**
  - `get_user_by_email` wird per `monkeypatch` auf einen Dummy-User
    gesetzt.
  - Passwortprüfung über `bcrypt.checkpw` wird auf immer-true gesetzt.
  - Ein POST auf `/login` mit gültigen Daten:
    - gibt Status `302` zurück,
    - `Location`-Header endet auf `/` (Redirect aufs Dashboard).

Damit wird die komplette Kette „Login-Formular → Login-Handler →
Session → Redirect aufs Dashboard“ einmal end-to-end durchgelaufen,
allerdings mit komplett gemockter Business-Logik.

---

## 6. Umgang mit externen Abhängigkeiten

Die Tests vermeiden reale externe Zugriffe:

- **Datenbank**  
  Wird über Dummy-Sessions simuliert (`SessionLocal` wird
  gemonkeypatched).

- **Supabase**  
  Wird über `conftest.py` als Dummy-Modul eingebunden.

- **OpenAI**  
  `OpenAI`-Client wird durch Dummy-Client ersetzt, Antworten sind
  deterministisch.

- **E-Mail**  
  Das E-Mail-System schreibt ausschließlich in eine Logdatei.
  In Tests wird der Pfad per `monkeypatch` auf einen temporären Speicher
  umgeleitet.

Dadurch sind die Tests:

- schnell,
- deterministisch,
- CI-freundlich.

---

## 7. Leitlinien für neue Tests

Beim Schreiben neuer Tests sollte folgendes beachtet werden:

1. **Kein echter Netzwerkzugriff**  
   → immer Dummy-Clients / Monkeypatch verwenden.

2. **Keine echte Datenbankverbindung**  
   → Dummy-Session-Klassen verwenden; nur SQL-/Parameternutzung
   überprüfen.

3. **AAA-Prinzip (Arrange – Act – Assert)**  
   - Arrange: Dummy-Daten & Mocks aufbauen  
   - Act: Funktion/Methode aufrufen  
   - Assert: Verhalten und Rückgabewerte prüfen  

4. **Klare Benennung**  
   - `test_<funktion>_<erwartetes_verhalten>()`

5. **Fehlerfälle nicht vergessen**  
   - z. B. ungültige Eingaben, fehlende Einträge, Overlaps bei Leihen.

---

## 8. Ausblick

Die aktuelle Testbasis deckt die wichtigsten Geschäftsregeln, Services,
Integrationen und den Dashboard-/Login-Flow ab.  
Als Erweiterung bieten sich an:

- weitere View-/Routing-Tests (z. B. für Detailansichten),
- End-to-End-ähnliche Flows (komplette Leihe inkl. KI-Mock),
- zusätzliche Property-based Tests für Datums- und Statuslogik.
