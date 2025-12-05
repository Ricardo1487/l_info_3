# CI/CD-Dokumentation

Dieses Dokument beschreibt den Continuous-Integration- (CI) und
Continuous-Deployment-(CD) Prozess der Boxenverwaltungs-Applikation.

Die Pipeline besteht aus:

- **Continuous Integration über GitHub Actions**
- **Deployment als Webservice auf Render**

---

## 1. Continuous Integration (GitHub Actions)

Die CI-Pipeline ist in `.github/workflows/ci.yml` definiert und läuft
bei jedem Push sowie bei Pull Requests auf zentrale Branches. fileciteturn3file3

### 1.1 Triggers

Die Pipeline wird automatisch gestartet bei:

- jedem `push` auf **alle Branches** (`'**'`)
- jedem `pull_request` auf die Branches:
  - `main`
  - `dev` fileciteturn3file3

Das stellt sicher, dass sowohl Feature-Branches als auch Merges in
wichtige Branches immer mit Tests geprüft werden.

### 1.2 Build-Umgebung

Der CI-Job heißt `tests` und läuft auf:

- Runner: `ubuntu-latest`
- Python-Version: `3.11`
- `PYTHONPATH` wird auf `.` gesetzt, damit das Projekt als Modul
  importiert werden kann. fileciteturn3file3

### 1.3 Pipeline-Schritte

Die CI-Pipeline besteht aus vier Schritten:

1. **Checkout des Repositories**  
   ```yaml
   - uses: actions/checkout@v4
   ```

2. **Python einrichten**  
   ```yaml
   - uses: actions/setup-python@v5
     with:
       python-version: '3.11'
   ```

3. **Abhängigkeiten installieren**  
   ```yaml
   - name: Install dependencies
     run: |
       python -m pip install --upgrade pip
       if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
       pip install pytest
   ```

   Dabei werden alle Dependencies aus `requirements.txt` installiert,
   u. a.:

   - Flask, gunicorn
   - SQLAlchemy, psycopg2-binary
   - OpenAI SDK
   - Supabase SDK
   - bcrypt, qrcode fileciteturn3file2

4. **Tests ausführen**  
   ```yaml
   - name: Run tests
     run: |
       pytest -q
   ```

   Alle Tests im Verzeichnis `tests/` laufen durch und müssen grün sein,
   bevor ein Merge nach `main` oder `dev` sinnvoll ist.

### 1.4 Ergebnisse & Fehlerschutz

- Schlägt ein Schritt fehl (z. B. Tests schlagen fehl oder Dependencies
  lassen sich nicht installieren), markiert GitHub den CI-Run als
  fehlgeschlagen.
- Pull Requests zeigen den CI-Status direkt an, sodass nur geprüfter
  Code in `main`/`dev` landet.

### 1.5 Hinweise / mögliche Erweiterungen

Mögliche Erweiterungen der CI-Pipeline wären:

- Linting (z. B. `flake8`, `ruff`) vor dem Testlauf
- Coverage-Reporting (`pytest-cov`)
- Upload von Coverage-Berichten zu Codecov / GitHub
- Format-Checks (z. B. `black`, `isort`)
- Separater Job für statische Analysen

---

## 2. Continuous Deployment (Render)

Das Deployment erfolgt als **Python-Webservice bei Render**. Die
Konfiguration liegt in `render.yaml`. fileciteturn3file1

### 2.1 Service-Definition

In `render.yaml` ist ein Webservice definiert: fileciteturn3file1

```yaml
services:
  - type: web
    name: l-info-3
    env: python
    plan: starter
    pythonVersion: 3.12.3
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app.web:app
```

Wichtige Punkte:

- **type: web** – HTTP-Webservice
- **env: python** – Python-Umgebung
- **pythonVersion: 3.12.3** – Laufzeitversion bei Render
- **buildCommand:** installiert Dependencies
- **startCommand:** startet die App via Gunicorn (`app.web:app`)

Die gleiche Python-Version wird zusätzlich in `runtime.txt`
konfiguriert: fileciteturn3file0

```text
python-3.12.3
```

### 2.2 Build & Start

Beim Deployment (bei Render z. B. per Git-Connect):

1. Repository wird von Render geklont.
2. `buildCommand` wird ausgeführt:
   ```bash
   pip install -r requirements.txt
   ```
3. Render startet den Webservice mit:
   ```bash
   gunicorn app.web:app
   ```

Dabei werden alle in `requirements.txt` definierten Pakete installiert,
z. B. Flask, gunicorn, SQLAlchemy, OpenAI-SDK, Supabase-SDK, bcrypt,
qrcode usw. fileciteturn3file2

### 2.3 Umgebung & Konfiguration

Produktionsrelevante Environment-Variablen (z. B. Datenbank-URL, OpenAI
API Key, Supabase-Zugang, Secret Key) werden **nicht** in `render.yaml`
gespeichert, sondern über die Render-Oberfläche als „Environment
Variables“ konfiguriert. Das erhöht Sicherheit und Flexibilität.

Typische Variablen:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_BUCKET`
- `OPENAI_API_KEY`
- `FLASK_SECRET_KEY`
- `PUBLIC_BASE_URL` (Basis-URL für QR-Codes)

---

## 3. Zusammenspiel von CI und CD

### 3.1 Versionen & Kompatibilität

- CI läuft aktuell mit **Python 3.11** in GitHub Actions. fileciteturn3file3
- Production-Deployment (Render) nutzt **Python 3.12.3**. fileciteturn3file1turn3file0

Da die verwendeten Pakete (Flask, SQLAlchemy, OpenAI, Supabase usw.)
Python 3.11 und 3.12 unterstützen, ist diese Kombination in der Regel
unproblematisch. fileciteturn3file2

Für maximale Konsistenz könnte die CI-Pipeline perspektivisch auf
Python 3.12.x umgestellt werden, um exakt die gleiche Version wie in
Production zu testen.

### 3.2 Typischer Workflow

1. **Lokal entwickeln** (Feature-Branch)
2. **Commit & Push** → löst CI-Build aus
3. **Pull Request** auf `dev` oder `main`
4. CI muss grün sein (alle Tests bestanden).
5. Merge in `main`
6. Render erkennt neuen Commit auf `main` (je nach Render-Konfiguration)
   und rollt ein neues Deployment aus.

So ist sichergestellt, dass nur getesteter Code live geht.

---

## 4. Lokale Reproduzierbarkeit des Deployments

Um lokal möglichst nah an der Produktionsumgebung zu arbeiten, sollte:

- Python-Version **3.12.3** verwendet werden (wie in `runtime.txt`),
- `_genau dieselben Befehle_` wie in Render laufen:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate
pip install -r requirements.txt
gunicorn app.web:app
```

Für reine Entwicklung reicht weiterhin:

```bash
flask run
```

Die CI-Pipeline nutzt andere Startkommandos (nur `pytest`), ruft aber
genau dieselben Python-Module auf und prüft damit den identischen Code,
der später via Gunicorn in Produktion läuft.

---

## 5. Erweiterungsideen für CI/CD

Mögliche nächste Schritte für ein noch „professionelleres“ Setup:

- **Mehrere Jobs in CI:**
  - `lint` (z. B. ruff/flake8)
  - `tests` (pytest + Coverage)
- **Deployment-Gates:**
  - z. B. nur Deployment, wenn CI auf `main` grün ist
- **Staging-Umgebung:**
  - zweiter Render-Service für Test-Deployments
- **Automatisierte Datenbankmigrationen:**
  - Integrationen mit Alembic & Deployment-Hooks
- **Health-Check-Endpoint & Monitoring**
  - z. B. `/health`-Route, die von Render/externen Tools überwacht wird

Damit wäre die Pipeline komplett auf einem Niveau, wie es auch in
Produktivprojekten üblich ist.
