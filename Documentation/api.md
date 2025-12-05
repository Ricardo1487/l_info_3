# API-Dokumentation

Dieses Dokument beschreibt die HTTP-Endpunkte der Boxenverwaltungs-
Applikation. Der Schwerpunkt liegt auf den Flask-Routen, ihren Parametern
und dem fachlichen Verhalten. Die Anwendung ist primär serverseitig
gerendert (HTML-Seiten und Formulare) und stellt zusätzlich einen JSON-
Endpunkt für die Verfügbarkeitsabfrage einer Box bereit.

---

## 1. Authentifizierung & Sessions

### 1.1 `GET /login`

Rendert die Login-Seite.

**Antwort**

- `200 OK` – HTML-Seite mit Login-Formular

---

### 1.2 `POST /login`

Meldet einen Benutzer an und startet eine Session.

**Form-Felder**

| Feld     | Typ    | Pflicht | Beschreibung        |
|----------|--------|---------|---------------------|
| email    | string | ja      | Login-E-Mail        |
| password | string | ja      | Passwort im Klartext |

**Verhalten**

- Prüft, ob Benutzer existiert und Passwort korrekt ist.
- Bei Erfolg: setzt Session (z. B. `session["user_id"]`, Rolle) und leitet auf `/` um.
- Bei Fehler: rendert `login.html` erneut mit Fehlermeldung.

**Antworten**

- `302 Found` – Redirect auf `/` bei Erfolg  
- `200 OK` – HTML mit Fehlermeldung bei ungültigen Daten

---

### 1.3 `GET /logout`

Beendet die aktuelle Session.

**Verhalten**

- `session.clear()`
- Setzt Flash-Nachricht (z. B. „Abgemeldet“)
- Redirect zurück auf `/login`

**Antwort**

- `302 Found` – Redirect auf `/login`

---

## 2. Benutzerverwaltung (Admin)

Alle folgenden Routen sind nur mit Admin-Rolle erreichbar und werden
durch einen Decorator wie `@admin_required` geschützt.

### 2.1 `GET /admin/users`

Zeigt eine Übersicht aller Benutzer.

**Verhalten**

- Lädt alle User (z. B. über `list_users()` im Service-Layer).
- Rendert `admin_users.html`.

**Antwort**

- `200 OK` – HTML mit Benutzerliste  
- `403 Forbidden` – falls aktueller User kein Admin ist

---

### 2.2 `POST /admin/users/<int:user_id>/delete`

Löscht einen Benutzer (oder markiert ihn als entfernt, je nach
Implementierung).

**Verhalten**

- Prüft, ob User existiert.
- Ruft Service-Funktion wie `delete_user(user_id)` auf.
- Setzt Flash-Meldung.
- Redirect auf `/admin/users`.

**Antwort**

- `302 Found` – Redirect auf `/admin/users`  
- `404 Not Found` – falls Benutzer nicht existiert

---

### 2.3 `GET /change-password`

Zeigt das Formular zur Passwortänderung für den aktuell eingeloggten
Benutzer.

**Antwort**

- `200 OK` – HTML-Formular

---

### 2.4 `POST /change-password`

Ändert das Passwort des aktuell eingeloggten Nutzers.

**Form-Felder**

| Feld                 | Typ    | Pflicht | Beschreibung                         |
|----------------------|--------|---------|--------------------------------------|
| current_password     | string | ja      | aktuelles Passwort                   |
| new_password         | string | ja      | neues Passwort                       |
| new_password_confirm | string | ja      | Bestätigung des neuen Passworts      |

**Verhalten**

- Prüft, ob `new_password == new_password_confirm`.
- Holt aktuellen User aus der Session.
- Prüft das bisherige Passwort (z. B. mit `bcrypt`).
- Aktualisiert das Passwort im Service.
- Bei Erfolg: Redirect auf `/` mit Erfolgsmeldung.
- Bei Fehlern: rendert `change_password.html` erneut mit Fehlermeldung.

---

## 3. Dashboard & Übersicht

### 3.1 `GET /`

Startseite / Dashboard.

**Query-Parameter (optional)**

| Parameter  | Typ    | Beschreibung                                |
|------------|--------|---------------------------------------------|
| sort_field | string | Sortierfeld (z. B. `planned_end_date`)      |
| sort_dir   | string | `asc` oder `desc`                           |
| contact    | string | Filter nach Kontakt-E-Mail                  |
| status     | string | Filter nach Leihstatus                      |
| box        | string | Filter nach Box-Code                        |

**Verhalten**

- Aktualisiert überfällige Leihen (z. B. via `mark_overdue_loans(...)`).
- Lädt alle Leihen (z. B. `list_loans()`).
- Wendet Filter & Sortierung an.
- Berechnet Statistiken (z. B. offene, überfällige, zurückgegebene Leihen).
- Rendert `index.html`.

**Antwort**

- `200 OK` – HTML-Dashboard

---

## 4. Boxen

### 4.1 `GET /boxes`

Übersicht aller Boxen mit Statusinformationen.

**Verhalten**

- Lädt alle Boxen.
- Verknüpft relevante Leihinformationen (z. B. aktuelle und künftige Leihen).
- Rendert `boxes.html`.

**Antwort**

- `200 OK` – HTML mit Boxenübersicht

---

### 4.2 `GET /boxes/<int:box_id>/created`

Bestätigungsseite nach dem Anlegen einer Leihe (optional mit QR-Hinweis).

**Verhalten**

- Lädt Box über `box_id`.
- Rendert `box_created.html`.

**Antwort**

- `200 OK` – HTML  
- `404 Not Found` – falls Box nicht existiert

---

### 4.3 `GET /boxes/<box_code>/qr`

Liefert einen QR-Code als PNG-Bild zurück.

**Pfadparameter**

| Name      | Typ    | Beschreibung             |
|-----------|--------|--------------------------|
| box_code  | string | z. B. `BOX-023` oder `23` |

**Verhalten**

- Ermittelt QR-Payload (falls leer: Fallback-URL auf Dashboard mit Box-Filter).
- Generiert QR-Code.
- Gibt Bild per `send_file` zurück.

**Antwort**

- `200 OK` – `image/png`  
- `404 Not Found` – falls Box nicht existiert

---

## 5. Leihvorgänge – Anlegen & Bearbeiten

### 5.1 `GET /new-loan`

Zeigt das Formular zum Anlegen einer neuen Leihe.

**Query-Parameter (optional)**

| Parameter | Typ    | Beschreibung                         |
|-----------|--------|--------------------------------------|
| box_code  | string | vorbefüllter Box-Code (z. B. aus QR) |

**Verhalten**

- Normalisiert Box-Code zur Anzeige.
- Setzt Standardwerte (z. B. heutiges Datum).
- Rendert `new_loan.html`.

**Antwort**

- `200 OK` – HTML-Formular

---

### 5.2 `POST /start-loan`

Verarbeitet das Formular zur Erstellung einer neuen Leihe.

**Form-Felder**

| Feld      | Typ    | Pflicht | Beschreibung                          |
|-----------|--------|---------|---------------------------------------|
| box_code  | string | ja      | Box-Nummer / Box-Code                 |
| email     | string | ja      | Kontakt-E-Mail des Entleihers         |
| ausgabe   | string | ja      | Ausgabedatum (`YYYY-MM-DD`)           |
| rueckgabe | string | ja      | geplantes Rückgabedatum (`YYYY-MM-DD`)|

**Verhalten**

- Normalisiert `box_code` (z. B. numerisch → `BOX-XYZ`).
- Validiert Box-Code.
- Prüft, ob Box existiert:
  - Falls **nicht vorhanden**: rendert Bestätigungsseite `confirm_new_box.html`.
  - Falls vorhanden: erstellt Leihe über Service (`create_loan_with_validation(...)`) und leitet auf `/loan/<id>/photo` um.

**Antwort**

- `200 OK` – HTML-Bestätigungsseite (falls neue Box bestätigt werden muss)  
- `302 Found` – Redirect auf `/loan/<loan_id>/photo` bei erfolgreicher Leihanlage

---

### 5.3 `POST /confirm-new-box`

Bestätigt oder verwirft das Anlegen einer **neuen** Box und der zugehörigen Leihe.

**Form-Felder**

| Feld      | Typ    | Pflicht | Beschreibung                    |
|-----------|--------|---------|---------------------------------|
| decision  | string | ja      | `"yes"` oder `"no"`             |
| box_code  | string | ja      | Box-Code                        |
| email     | string | ja      | Kontakt-E-Mail                  |
| ausgabe   | string | ja      | Ausgabedatum                    |
| rueckgabe | string | ja      | geplantes Rückgabedatum         |

**Verhalten**

- `decision = "no"` → zurück zu `new_loan.html` mit vorbefüllten Werten.
- `decision = "yes"`:
  - legt Box an (falls nicht existent),
  - legt Leihe an,
  - leitet auf `/loan/<loan_id>/photo` weiter.
- Sonst: `400 Bad Request`.

---

### 5.4 `GET /loan/<int:loan_id>`

Detailansicht einer Leihe.

**Verhalten**

- Lädt komplette Loan-Ansicht (Box, E-Mail, Status, Dates, Fotos, erkannte Objekte).
- Berechnet fehlende Objekte basierend auf KI-Ergebnissen.
- Rendert `loan_details.html`.

**Antwort**

- `200 OK` – HTML  
- `404 Not Found` – falls Leihe nicht existiert

---

### 5.5 `POST /loan/<int:loan_id>`

Aktualisiert Basisdaten einer Leihe (E-Mail, Daten).

**Form-Felder**

| Feld               | Typ    | Pflicht | Beschreibung                 |
|--------------------|--------|---------|------------------------------|
| contact_email      | string | ja      | Kontakt-E-Mail               |
| planned_start_date | string | ja      | geplantes Startdatum         |
| planned_end_date   | string | ja      | geplantes Enddatum           |

**Optionale Query-Parameter**

| Parameter | Typ    | Beschreibung            |
|-----------|--------|-------------------------|
| mode      | string | z. B. `"edit"`          |

**Verhalten**

- Aktualisiert die Plan-Daten.
- Rendert `loan_details.html` erneut (ggf. im Edit-/View-Modus).

---

### 5.6 `POST /extend-loan/<int:loan_id>`

Verlängert das geplante Rückgabedatum.

**Form-Feld**

| Feld      | Typ    | Pflicht | Beschreibung                  |
|-----------|--------|---------|-------------------------------|
| new_date  | string | ja      | Neues Enddatum (ISO-Format)   |

**Verhalten**

- Parsed Datum.
- Ruft Service-Funktion zur Verlängerung auf.
- Redirect auf `/`.

---

### 5.7 `POST /loan/<int:loan_id>/delete`

Löscht eine Leihe, sofern sie vollständig zurückgegeben wurde.

**Verhalten**

- Prüft den Status der Leihe.
- Löscht Leihe nur, wenn keine offenen Punkte existieren (z. B. Status `RETURNED`).
- Redirect auf `/` mit Flash-Meldung.

---

## 6. Foto-Upload & KI-Analyse

### 6.1 `GET /loan/<int:loan_id>/photo`

Zeigt das Formular zum Upload des **Initialfotos** (Ausgabezustand der Box).

**Antwort**

- `200 OK` – HTML-Formular

---

### 6.2 `POST /loan/<int:loan_id>/photo`

Lädt das Initialfoto hoch und startet eine KI-Analyse.

**Datei-Feld**

| Feld  | Typ          | Pflicht | Beschreibung                    |
|-------|--------------|---------|---------------------------------|
| photo | file (image) | ja      | Bild der Box beim Ausgeben      |

**Verhalten**

- Speichert Foto in Supabase Storage.
- Legt Eintrag in der Tabelle `photos` (`type = INITIAL`) an.
- Führt `analyze_image_file(...)` aus.
- Speichert erkannte Objekte in `detected_objects`.
- Redirect auf `/loan/<loan_id>/review-initial`.

---

### 6.3 `GET /loan/<int:loan_id>/review-initial`

Zeigt die vom KI-System erkannten Gegenstände des Initialfotos.

**Verhalten**

- Lädt Initialfoto und zugehörige erkannte Objekte.
- Rendert `review_initial_contents.html`.

---

### 6.4 `GET /loan/<int:loan_id>/return-photo`

Zeigt das Formular zum Upload des **Rückgabefotos**.

**Antwort**

- `200 OK` – HTML-Formular

---

### 6.5 `POST /loan/<int:loan_id>/return-photo`

Lädt das Rückgabefoto hoch und startet eine erneute KI-Analyse.

**Datei-Feld**

| Feld  | Typ          | Pflicht | Beschreibung                      |
|-------|--------------|---------|-----------------------------------|
| photo | file (image) | ja      | Bild der Box bei Rückgabe        |

**Verhalten**

- Speichert Foto in Supabase Storage (`type = RETURN`).
- Analysiert das Foto mittels KI.
- Speichert erkannte Objekte für das Rückgabefoto.
- Redirect auf `/loan/<loan_id>/review-return`.

---

### 6.6 `GET /loan/<int:loan_id>/review-return`

Zeigt den Vergleich zwischen Initial- und Rückgabefoto.

**Verhalten**

- Lädt erkannte Initial- und Return-Objekte.
- Vergleicht Objektlisten (fehlende Gegenstände).
- Rendert `review_return_contents.html`.

---

### 6.7 `GET /loan/<int:loan_id>/check-contents`

Prüft den Inhalt einer Leihe anhand der gespeicherten KI-Ergebnisse
(ohne neue Fotos).

**Verhalten**

- Lädt Objekte beider Zustände.
- Berechnet Differenz.
- Rendert `check_contents.html`.

---

### 6.8 `GET /return/<int:loan_id>` und `POST /return/<int:loan_id>`

- `GET` → leitet i. d. R. auf den Rückgabe-/Foto-Flow weiter.  
- `POST` → schließt eine Leihe ab (setzt `actual_end_date`, Statusänderung) und
leitet auf `/` um.

---

## 7. JSON-API: Box-Verfügbarkeit

### 7.1 `GET /api/box/<box_code>/availability`

Liefert geplante Belegungszeiträume einer Box als JSON.

**Pfadparameter**

| Name      | Typ    | Beschreibung                |
|-----------|--------|-----------------------------|
| box_code  | string | z. B. `23` oder `BOX-023`   |

**Verhalten**

- Normalisiert Box-Code.
- Sucht Box-ID.
- Falls Box nicht existiert → `box_id = null`, leere Periodenliste.
- Sonst: liest geplante Leihzeiträume und gibt sie als Liste zurück.

**Antwort (Beispiel)**

```json
{
  "box_id": 42,
  "periods": [
    { "start": "2025-01-10T09:00:00", "end": "2025-01-12T16:00:00" },
    { "start": "2025-01-20T09:00:00", "end": "2025-01-21T12:00:00" }
  ]
}
```

---

## 8. Fehlerverhalten (übergreifend)

- `400 Bad Request` – ungültige oder fehlende Pflichtfelder  
- `401/403 Unauthorized/Forbidden` – nicht eingeloggt oder fehlende Rolle  
- `404 Not Found` – nicht existierende Leihen/Boxen/Fotos  
- `500 Internal Server Error` – unerwartete Laufzeitfehler

Fehlermeldungen für Nutzer werden in der Regel über Flash-Messages und
HTML-Templates dargestellt.

---

## 9. Erweiterbarkeit

Die aktuelle API ist primär HTML-basiert.  
Für zukünftige reine JSON-Clients können die wichtigsten Leihprozesse
(Erstellung, Foto-Upload, Statusänderung, Inhaltsprüfung) über neue
`/api/...`-Routen gekapselt werden, die direkt die bestehenden
Servicefunktionen verwenden.
