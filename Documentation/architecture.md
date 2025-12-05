# Architektur der Boxenverwaltungs-Applikation

Dieses Dokument beschreibt die Systemarchitektur der Boxenverwaltungs-App.
Die Architektur ist modular, testbar und klar schichtorientiert. Sie verbindet
klassische serverseitige Webentwicklung mit KI-gestützter Objekterkennung.

---

# 1. Systemüberblick

Die Anwendung verwaltet Laborboxen und deren Leihvorgänge.  
Zentrale Funktionen:

- Erstellung & Verwaltung von Boxen
- Starten und Abschließen von Leihen
- Fotoaufnahme (Initial & Rückgabe)
- KI-basierte Objekterkennung & Vergleich
- Statusmanagement (OPEN, RETURNED, OVERDUE, MISSING_ITEMS)
- Rollenbasierte Benutzerverwaltung (ADMIN / HIWI)
- Reminder-System über ein Mock-E-Mail-Modul

Die App läuft vollständig im Web, ohne lokale Installation:

- **Backend:** Python / Flask  
- **Frontend:** HTML, CSS, Jinja2 Templates  
- **Datenbank:** PostgreSQL (Supabase)  
- **Dateispeicher:** Supabase Object Storage  
- **KI-Service:** OpenAI Vision  
- **Deployment:** Render  

---

# 2. Architekturkonzept

Das System folgt einem klaren **Three-Layer-Architecture Pattern**:

```
┌──────────────────────────────┐
│  Web Layer (Presentation)     │
├──────────────────────────────┤
│  Service Layer (Business)     │
├──────────────────────────────┤
│  Infrastructure Layer (Data)  │
└──────────────────────────────┘
```

Diese Struktur ermöglicht:

- gute Testbarkeit
- klare Verantwortlichkeiten
- einfache Erweiterbarkeit
- saubere Trennung zwischen UI, Logik und Daten

---

# 3. Web Layer (Presentation)

**Ort:** `app/web.py`, `app/templates/`, `app/static/`

Der Web Layer steuert die komplette User Experience.

### Verantwortlichkeiten:

- HTTP-Routing (Flask)
- Rollen- & Session-Handling (ADMIN/HIWI)
- HTML-Rendering per Jinja2
- Formvalidierung & Fehlerrückmeldung
- Upload der Fotos an den Service Layer

### Wichtige Views:

| Route | Funktion |
|-------|----------|
| `/` | Übersicht aller Boxen & Leihen |
| `/loan/new` | Neue Leihe anlegen |
| `/loan/<id>` | Detailansicht & KI-Ergebnisse |
| `/loan/<id>/return` | Rückgabefoto aufnehmen & verarbeiten |
| `/admin/users` | Benutzerverwaltung |

---

# 4. Service Layer (Business Logic)

**Ort:** `app/services/`

Der Service Layer implementiert alle fachlichen Regeln und Geschäftsprozesse.  
Er enthält keine UI, keine SQL, keine HTTP-Logik — nur **reine Fachlogik**.

## 4.1 Loan-Management

Module: `loans.py`, `loan_status.py`, `loan_views.py`

### Aufgaben:

- Leihe erstellen, bearbeiten und abschließen
- Verknüpfung von Box, Nutzer, Fotos und KI-Daten
- Statusübergänge anhand definierter Regeln:

```
UPCOMING → OPEN → RETURNED
                     ↘
                  MISSING_ITEMS

OPEN → OVERDUE   (wenn Rückgabedatum überschritten)
```

- Abgleich Initialfoto ↔ Rückgabefoto  
- Bestimmung fehlender oder veränderter Gegenstände

---

## 4.2 Box-Management

Module: `boxes.py`

### Aufgaben:

- CRUD für Boxen
- Boxcodes verwalten
- Zustand „aktiv/inaktiv“ für Archivierung

---

## 4.3 Benutzerverwaltung

Module: `users.py`

### Aufgaben:

- Benutzer erstellen & löschen
- Passwort-Hashing (bcrypt)
- Rollenprüfung (ADMIN/HIWI)
- Login-Authentifizierung

---

## 4.4 Storage & KI-Anbindung

Module: `photos_storage.py`, `image_analysis.py`

### Storage:

- Speichern von Initial- und Rückgabefotos in Supabase Object Storage
- Generieren persistenter URLs

### KI-Analyse:

Die Funktion:

```
analyze_image_file(photo)
```

führt aus:

1. Bild laden & base64-kodieren  
2. Anfrage an OpenAI Vision  
3. Vereinheitlichter Output:

```json
{
  "objects": [
    { "label": "Schraubendreher", "quantity": 1, "confidence": 0.92 }
  ]
}
```

4. Übergabe der Ergebnisse an den Loans-Service

---

# 5. Infrastructure Layer (Database, Storage, External Services)

**Ort:** `app/config/`, `/db`

Dieser Layer kapselt alle externen Systeme.

## 5.1 PostgreSQL-Datenbank

Tabellen:

- `users` – Accounts & Rollen  
- `boxes` – Boxenstammdaten  
- `loans` – Leihprozesse  
- `photos` – Fotometadaten  
- `detected_objects` – KI-Erkennungen  
- `reminders` – Mock-E-Mail-Einträge  

### ER-Überblick:

```
users 1—∞ loans ∞—1 boxes
loans 1—∞ photos 1—∞ detected_objects
loans 1—∞ reminders
```

Die Datenbank bildet **vollständig den Leihfluss** ab und trennt bewusst:

- Metadaten (DB)
- Binärdateien (Storage)
- Analyseergebnisse (detected_objects)

---

## 5.2 Supabase Object Storage

Speichert ausschließlich:

- Initialfotos
- Rückgabefotos

In der Datenbank werden nur Referenzen abgelegt.

Vorteile:

- einfache Skalierung  
- getrennte Zugriffsrechte  
- bessere Performance  

---

## 5.3 OpenAI Vision

Wird genutzt für:

- Bestimmung des Boxinhalts beim Start einer Leihe  
- Vergleich von Initial- und Rückgabefotos  

Die KI wird **nur im Service Layer** verwendet, nie direkt im Web Layer.

---

# 6. Zentrale Datenflüsse

## 6.1 Start einer neuen Leihe

```
UI → Web-Layer → Service Layer
   1. Formular absenden
   2. Leihe anlegen
   3. Initialfoto speichern
   4. KI-Analyse durchführen
   5. Objekte speichern
   6. Status = OPEN
```

---

## 6.2 Rückgabeprozess

```
UI → Upload → Service Layer
   1. Rückgabefoto speichern
   2. KI-Analyse
   3. Vergleich initial vs. return
   4. Status:
        - RETURNED
        - MISSING_ITEMS
```

---

## 6.3 Überfällige Leihen

```
Service Layer:
   if planned_end_date < today and status = OPEN:
       status = OVERDUE
```

Diese Logik kann beim Laden des Dashboards oder bei täglicher Ausführung greifen.

---

# 7. Sicherheit

- Passwort-Hashing via bcrypt  
- Session-Management über Flask  
- Rollenbasierte Zugriffskontrolle  
- Keine echten personenbezogenen Daten  
- Keine echten E-Mails → Mock-System erfüllt Laborvorgaben  

---

# 8. Erweiterbarkeit

Die Architektur erlaubt einfache Erweiterungen:

- Mehrere Rückgabefotos / Vergleichshistorie  
- Echte E-Mail-Benachrichtigungen  
- Export- und Reporting-Module  
- Audit-Log für manuelle Objektkorrekturen  
- KI-Modelle austauschbar (z. B. lokales Modell oder andere Provider)  

---

# 9. Fazit

Die Boxenverwaltung basiert auf einer klaren, robusten und modularen Architektur.  
Durch strikte Trennung der Schichten, klar definierte Services und eine normalisierte Datenbank
ist das System sowohl **testbar**, **skalierbar** als auch **erweiterbar**.

Damit ist die Anwendung technisch sauber dokumentiert und bereit für Deployment,
Bewertung und Kolloquium.
