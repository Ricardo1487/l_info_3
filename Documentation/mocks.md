# Mocks & Test-Doubles

Dieses Dokument beschreibt alle Mock- und Test-Dummy-Komponenten der
Boxenverwaltungs-Applikation. Ziel ist, externe Abhängigkeiten so zu
kapseln, dass

- **keine echten E-Mails** verschickt werden,
- **keine echten Cloud-Services** (Supabase, OpenAI) angesprochen werden,
- **keine echte Datenbank** für Unit-Tests benötigt wird,
- Tests schnell, deterministisch und CI-freundlich bleiben.

---

## 1. Übersicht der Mock-Bereiche

Die Anwendung nutzt Mocks und Test-Doubles in vier Hauptbereichen:

1. **E-Mail-Mock** – simuliert ein zukünftiges E-Mail-System (Produktivcode)
2. **Supabase-Mock** – ersetzt den echten Supabase-Client in Tests
3. **KI-/OpenAI-Mock** – ersetzt den OpenAI-Client in Tests
4. **Datenbank- & Storage-Dummies** – einfache Session- und FileStorage-Dummys,
   die SQL und Uploads nachbilden, ohne echte Ressourcen zu benutzen

---

## 2. E-Mail-Mock (`app/services/email_mock.py`)

Der E-Mail-Mock ist **Teil der eigentlichen Applikation** (nicht nur
Testcode) und erfüllt die Laboranforderung:

> „Es muss ein Mock im Programmcode enthalten sein, welcher eine
> zukünftige E-Mail-Funktion simulieren soll.“

### 2.1 Zweck

- Es werden **keine echten E-Mails** verschickt.
- Stattdessen werden strukturierte Log-Einträge erzeugt:
  - im Python-Logging (`logger.info(...)`)
  - zusätzlich in einer Logdatei (standardmäßig `logs/email_mock.log`)

Damit kann die App bereits so tun, als ob Reminder- oder
Benachrichtigungs-Mails verschickt würden, ohne einen SMTP-Server oder
echte Empfänger zu benötigen.

### 2.2 Hauptfunktion `send_email(...)`

Signatur (vereinfacht):

```python
def send_email(
    to: str,
    subject: str,
    body: str,
    category: str = "generic",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    ...
```

Verhalten:

1. Baut einen Log-Eintrag als Dictionary auf:

   ```python
   entry = {
       "to": to,
       "subject": subject,
       "body": body,
       "category": category,
       "metadata": metadata or {},
       "timestamp": datetime.now(timezone.utc).isoformat(),
   }
   ```

2. Schreibt den Eintrag als JSON-String ins Logging:

   ```python
   logger.info("EMAIL_MOCK %s", json.dumps(entry, ensure_ascii=False))
   ```

3. Übergibt den Eintrag an `_write_to_file(entry)`.

### 2.3 Logdatei (`LOG_FILE`) & `_write_to_file(...)`

- `LOG_FILE` ist ein `Path` (z. B. `Path("logs/email_mock.log")`).
- `_write_to_file(entry)`:
  - erstellt das Zielverzeichnis bei Bedarf (`mkdir(parents=True, exist_ok=True)`),
  - öffnet `LOG_FILE` im Append-Modus,
  - schreibt pro Eintrag **eine Zeile** (`JSONL`-Format).

Dadurch entsteht eine Logdatei, in der alle simulierten E-Mails
nachvollziehbar gespeichert sind.

### 2.4 Verwendung in der Business-Logik

Eine wichtige Integration ist z. B. `log_overdue_loans(loans)` in
`loan_views`:

- durchläuft eine Liste von Leihen,
- erkennt überfällige Leihen,
- ruft für jede überfällige Leihe `email_mock.send_email(...)` auf,
- schreibt so „Overdue Notices“ in das E-Mail-Log, ohne echte
  Nachrichten zu versenden.

### 2.5 Testbarkeit

In `test_email_mock.py` wird der E-Mail-Mock wie folgt getestet:

- `LOG_FILE` wird über `monkeypatch` auf eine temporäre Datei
  (`tmp_path / "emails.log"`) umgebogen.
- `send_email(...)` wird mit Testparametern aufgerufen.
- Danach wird geprüft:
  - **Existiert die Logdatei?**
  - **Enthält sie die richtige E-Mail-Adresse, den Betreff bzw.
    Schlüsselworte wie „overdue“?**

Damit ist der E-Mail-Mock sowohl für das Labor als auch für das
Kolloquium gut demonstrierbar.

---

## 3. Supabase-Mock (`tests/conftest.py`)

Supabase wird im Produktivcode als File-Storage genutzt, soll aber für
Tests **nicht** wirklich angesprochen werden. Deshalb ersetzt
`conftest.py` das `supabase`-Modul zur Laufzeit durch einen Dummy.

### 3.1 Umgebung & Dummy-Modul

Beim Laden von `pytest`:

- werden Umgebungsvariablen gesetzt:
  - `SUPABASE_URL = "https://dummy-supabase.local"`
  - `SUPABASE_SERVICE_KEY = "dummy-service-key"`
  - `SUPABASE_BUCKET = "photos"`
- es wird ein neues Modul `supabase` erzeugt (`types.ModuleType`),
- dieses Modul definiert:
  - `DummySupabaseClient`
  - `create_client(url, key)` → gibt immer einen Dummy-Client zurück,
- das Dummy-Modul wird in `sys.modules["supabase"]` eingetragen.

Dadurch erhalten alle Importe (`from supabase import create_client`)
innerhalb der Tests den Dummy statt des echten SDKs.

### 3.2 DummySupabaseClient & Storage

Der Dummy-Client simuliert nur die Schnittstellen, die benötigt werden:

- `DummySupabaseClient.storage.from_(bucket_name)` liefert ein
  Objekt mit Methoden wie:
  - `upload(path, file)` – nimmt Daten entgegen, speichert sie aber nur
    in einer Liste (`upload_calls`).
  - `remove(paths)` – protokolliert zu löschende Pfade (`remove_calls`).
  - `get_public_url(path)` – gibt eine konstruierte URL zurück (z. B.
    `"https://cdn.example.com/<path>"`) und protokolliert den Aufruf.

Diese Dummy-Objekte werden in `test_photos_storage.py` intensiv genutzt.

---

## 4. KI-/OpenAI-Mocks (`test_image_analysis.py`)

Die Anbindung an OpenAI Vision wird im Produktivcode über
`image_analysis._get_client()` und `image_analysis.analyze_image_file(...)`
realisiert. In Tests wird **kein echter OpenAI-Call** durchgeführt.

### 4.1 DummyFileStorage & DummyStream

- `DummyFileStorage` simuliert das Upload-Objekt (`FileStorage`) aus
  Flask:
  - besitzt einen Dateinamen (`filename`),
  - stellt einen `stream` zur Verfügung (z. B. `DummyStream`), der die
    Lesezugriffe auf die Bilddaten nachahmt.

- `DummyStream` implementiert die minimal notwendigen Methoden:
  - z. B. `read()`, `seek()`, um das Verhalten eines Datei-Streams
    nachzubilden.

### 4.2 DummyClient (OpenAI-Ersatz)

In den Tests wird `image_analysis._get_client` via `monkeypatch`
überschrieben:

```python
monkeypatch.setattr(ia, "_get_client", lambda: DummyClient(responses))
```

`DummyClient` liefert vorbereitete `responses`, die das typische
Antwortformat des Vision-Modells nachstellen:

- entweder als reines JSON (`{"objects": [...]}`),
- oder eingebettet in einen ```json-Block,
- oder als Liste von Content-Chunks.

`analyze_image_file(file_storage)` muss diese Formate robust parsen und
immer ein konsistentes Ergebnis wie:

```python
{
    "objects": [
        {"label": "Kabel", "quantity": 3, "confidence": 0.9},
        ...
    ]
}
```

liefern. Genau dieses Verhalten wird im Test sichergestellt.

---

## 5. Datenbank- & Session-Dummies (in verschiedenen Tests)

Viele Tests (z. B. `test_loans.py`, `test_boxes.py`,
`test_users_service.py`, `test_loan_status.py`) nutzen **Dummy-Sessions**
statt einer echten Datenbank.

Typische Muster:

- `class DummySession:` mit Methoden:
  - `execute(stmt, params=None)` – speichert SQL und Parameter in einer
    Liste (`executed`),
  - `commit()` – setzt ein Flag (`committed = True`),
  - optional: `rollback()` (falls benötigt).
- `SessionLocal` wird per `monkeypatch` auf eine Factory gesetzt, die
  `DummySession()` zurückgibt.

Dadurch können Tests prüfen:

- welche SQL-Statements aufgerufen würden,
- ob Transaktionen korrekt `commit()` aufrufen,
- ob bestimmte Parameter (IDs, Status, Datumswerte) korrekt
  zusammengebaut werden,

ohne jemals eine echte Datenbankverbindung zu öffnen.

Beispiele:

- `test_database_config.py` prüft nur, **dass** eine Engine/Session
  erzeugt werden kann.
- `test_loans.py` prüft Logik wie:
  - Status-Entscheidungen (`OPEN`, `UPCOMING`, `OVERDUE`)
  - Overlap-Checks (`create_loan_with_validation`)
  - Löschlogik (`delete_loan_if_fully_returned`)
- `test_users_service.py` prüft SQL wie:
  - `UPDATE users SET password_hash = ... WHERE id = ...`

---

## 6. FileStorage-Dummies (`test_photos_storage.py`)

Um Datei-Uploads ohne Flask/WSGI zu testen, wird ein eigener
`DummyFileStorage` verwendet:

- besitzt Attribute:
  - `filename`
  - `stream` (z. B. `io.BytesIO`)
- stellt dieselbe API bereit wie Flask `FileStorage`, soweit vom
  Produktivcode in `photos_storage` genutzt.

Zusammen mit dem Supabase-Dummy-Bucket können so folgende Funktionen
getestet werden:

- Generierung eines Pfads wie `loans/<loan_id>/<filename>`
- Aufruf von `bucket.upload(path, file)`, ohne echten Upload
- Aufruf von `bucket.remove([...])` beim Löschen von Fotos
- Verwendung von `get_public_url(path)` zur Generierung von
  öffentlich abrufbaren URLs

---

## 7. Web-/Client-Mocks (`test_web_home.py`)

Für grundlegende End-to-End-ähnliche Tests wird der Flask-Testclient
verwendet:

- Fixture `client(monkeypatch)`:
  - importiert `app.web`,
  - ersetzt Funktionen wie:
    - `list_loans`
    - `compute_loan_stats`
    - `filter_loans`
    - `sort_loans`
    - `mark_overdue_loans`
  - setzt eine gültige Session (eingeloggter Demo-User).

Damit können Aufrufe wie:

```python
resp = client.get("/")
```

oder

```python
resp = client.post("/login", data={...})
```

getestet werden, ohne DB, OpenAI oder Supabase zu benötigen.

Der Test stellt unter anderem sicher, dass:

- `/` mit Statuscode `200` antwortet,
- `/login` bei korrekten Dummy-Daten einen Redirect (`302`) auf `/`
  auslöst.

---

## 8. Designprinzipien der Mocks

Beim Aufbau aller Mocks wurden folgende Prinzipien beachtet:

1. **Keine „magischen“ Seiteneffekte**  
   Externe Systeme werden nie real aufgerufen.

2. **Gleiche Schnittstelle wie das Original**  
   Dummy-Klassen imitieren nur die Oberfläche, die vom Produktivcode
   wirklich genutzt wird.

3. **Einfache Inspektierbarkeit**  
   Dummys speichern Aufrufe (z. B. `upload_calls`, `executed SQL`),
   sodass Tests gezielt prüfen können, **was** passiert wäre.

4. **Trennung von Produktiv-Mock und Test-Mocks**  
   - `email_mock` gehört zum Produktivcode (Laboranforderung).  
   - Supabase-/OpenAI-/DB-Mocks leben in `tests/` und wirken nur während
     `pytest`.

---

## 9. Fazit

Durch den konsequenten Einsatz von Mocks und Test-Doubles kann die
Boxenverwaltungs-App:

- in CI/CD ohne externe Dienste getestet werden,
- im Kolloquium demonstrieren, wie eine saubere Abstraktion von
  Infrastruktur aussieht,
- später leicht auf „echte“ Implementierungen (SMTP, produktives
  Cloud-Storage, echte E-Mail-Benachrichtigungen) umgestellt werden,
  ohne die Business-Logik anfassen zu müssen.
