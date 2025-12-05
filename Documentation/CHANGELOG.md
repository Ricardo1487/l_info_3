# Changelog

Alle bedeutenden Änderungen dieses Projekts werden in diesem Dokument
festgehalten.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com)
und die Versionierung folgt [Semantic Versioning](https://semver.org/).

---

## [1.0.0] – 2025-12-05

### Added
- Möglichkeit, beim Review einer Leihe **beide Fotos (Initial & Rückgabe)** parallel anzuzeigen.
- Vollständiges **E-Mail-Mock-System** inklusive eigener Logdatei und zugehöriger Tests.
- Feinschliff an den **Status-/Filter-Karten** im Dashboard für den Status *Returned*.

### Changed
- README überarbeitet und mit finalen Hinweisen zur Nutzung und Konfiguration ergänzt.
- Kleinere UI-Verbesserungen im Loan-Review-Flow.

### Fixed
- Diverse kleinere „fixes“-Commits (Layout-Fehler, Textkorrekturen, Feinjustierung im Filter- und Statistikbereich).

---

## [0.9.0] – 2025-12-04

### Added
- Neue Tests:
  - `test_loan_status` (Statusautomat, Overdue-Erkennung)
  - `test_loans` (Loan-Erstellung, Overlap-Checks, Objekt-Handling)
  - Tests für Boxes und Users
  - Tests für Photo-Storage
- Erweiterte API-Dokumentation und interne Anpassungen („API Commit“).

### Changed
- README weiter verbessert (Struktur, Hinweise zu .env und Setup).
- UI-Optimierungen:
  - Mobile-Darstellung der User-Liste verbessert.
  - Darstellung der Filter-Karten überarbeitet.

### Fixed
- Fehler in `image_analysis` behoben.
- Kleinere Test-Fixes und Stabilitätsverbesserungen in `test_boxes.py`.

---

## [0.8.0] – 2025-12-02

### Added
- Fertigstellung der **Box-Erstellungs- und Verwaltungsflows**:
  - `new_box`-Button im Base-Template,
  - eigene Seite `box_created.html` für neu angelegte Boxen,
  - eigene `new_box`-Seite für die Boxerstellung.
- Erweiterung der QR-Code-Funktion:
  - Nutzung einer konfigurierbaren Base-URL aus `.env`.
- API für Box-Verfügbarkeiten fertiggestellt.

### Changed
- Aktualisierung der `.env`-Konfiguration (Base-URL).
- `requirements.txt` um `qrcode[pil]` ergänzt.

---

## [0.7.0] – 2025-11-30

### Added
- Integration des **OpenAI-SDKs** in die `requirements.txt`.
- Detailkarte für Loans im Dashboard, die mehr Informationen zur Leihe anzeigt.
- Login-Feld „Passwort“ in der Login-Maske visuell und funktional korrigiert.

### Changed
- Feinschliff am Loan-Dashboard (Detaildarstellung).

---

## [0.6.0] – 2025-11-29

### Added
- Vollständige Implementierung des **Rückgabe-Workflows mit fehlenden Objekten**:
  - „Return with missing items“.
  - Anzeige fehlender Gegenstände auf Basis des KI-Vergleichs.
- Fertige **KI-Upload-Pipeline** für Rückgabefotos.
- Funktion, Leihen automatisch als **überfällig** zu markieren.

### Changed
- Filterkarten-Farben angepasst und konsistenter gestaltet.
- `requirements.txt` für Render-Deployment bereinigt.

---

## [0.5.0] – 2025-11-27

### Added
- **Statusfilter** im Dashboard:
  - Filter nach offenen, zurückgegebenen und überfälligen Leihen.
  - Anzeige der Gesamtanzahl der Leihen in der Statusleiste.
- Erweiterte Filterfunktion in `web.py`:
  - Kombination aus Status, Kontakt und Box-Code.

### Changed
- Bezeichnung „Zurück“ in „Überfällig“ geändert, um die Bedeutung klarer zu machen.
- Weitere Optimierungen der Filterlogik für offene und zurückgegebene Boxen.

---

## [0.4.0] – 2025-11-26

### Added
- Möglichkeit, nach dem Upload ein Foto direkt anzuzeigen (Preview nach Upload).
- Neue Darstellungsoptionen für Leihen und Box-Bilder im Frontend.
- Entfernen von nicht mehr benötigtem `main.py` aus dem Projekt.

### Changed
- Anpassungen an Loans-/New-Loans-Ansichten (z. B. Box-ID-Darstellung).
- Fixes hinsichtlich Supabase-Version und Render-Rebuild.

---

## [0.3.0] – 2025-11-25

### Added
- **Inhaltsprüfung für Leihen**:
  - Feature „Inhalt prüfen“ im Loan-Overview (Button),
  - Logik zur Auswertung der von der KI erkannten Objekte.
- Überarbeitung und Integration des API-Keys in `.env`.
- Refactor von `image_compare.py` / Bildvergleichslogik.

### Changed
- Kleinere Aufräumarbeiten („cleanup“).
- Konsolidierung der KI- und Vergleichslogik.

---

## [0.2.0] – 2025-11-24

### Added
- Neues UI-Farbschema für die Anwendung.
- Login- und Register-Templates inkl. angepasstem Styling.
- Sortierfunktion für die Startseite (Loans können nach verschiedenen Kriterien sortiert werden).

### Changed
- Anpassungen im Foto-Upload:
  - Entfernen der direkten „add photo“-Option aus `new_loan.html`,
  - neue, stabilere Upload-Methode.
- Verbesserte Robustheit beim Foto-Handling:
  - Entfernung temporärer Datei-Speicherung,
  - Windows-Probleme beim Speichern von Bildern behoben.

---

## [0.1.2] – 2025-11-22

### Added
- Einführung von `boxes.py` und entsprechende Anpassungen in `web.py`.
- Logik zum automatischen Anlegen einer Box, falls der angegebene Box-Code nicht existiert.
- Bereinigung der Box-Beschreibungen.

### Changed
- Anpassungen in `.env` (z. B. zusätzliche Parameter).

---

## [0.1.1] – 2025-11-19

### Added
- **Render-Deployment-Konfiguration**:
  - Hinzufügen von `render.yaml` und zugehörigen Dateien.
  - Mehrere Iterationen („v2“, „v3“), bis die Deploy-Konfiguration stabil war.

---

## [0.1.0] – 2025-10-16 bis 2025-11-18

### Added
- Initiale Projektstruktur:
  - Flask-Grundstruktur (`web.py`),
  - erste HTML-Templates,
  - Basis-README mit Projektinformationen.
- Erste Datenbank-Artefakte:
  - `db/001_init_schema.sql`,
  - `Datenbank schema version 001`,
  - Testdaten-Füller für `boxes`, `users`, `loans`.
- Aufgabenverteilung und Dokumentation:
  - README-Erweiterungen mit Zuständigkeiten und Backend-Notizen.
  - Hinweise zu `.env` und Projektkonfiguration.

### Changed
- Mehrere Iterationen an `README.md` (Korrektur von Rechtschreibung, besseres Wording).
- Aufräumen und Umbenennen von ersten Dateien, um die Basis-Struktur zu festigen.

