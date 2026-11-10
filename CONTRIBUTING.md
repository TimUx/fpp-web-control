# 🤝 Contributing to FPP Web Control

Vielen Dank für dein Interesse, zu FPP Web Control beizutragen! Dieses Dokument erklärt, wie du zum Projekt beitragen kannst.

---

## 📋 Inhaltsverzeichnis

- [Code of Conduct](#code-of-conduct)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Entwicklungsumgebung einrichten](#entwicklungsumgebung-einrichten)
- [Pull Request Prozess](#pull-request-prozess)
- [Coding Guidelines](#coding-guidelines)
- [Testing](#testing)
- [Dokumentation](#dokumentation)

---

## Code of Conduct

Dieses Projekt folgt dem Grundsatz: **Respektvoll, konstruktiv und hilfsbereit.**

- Sei respektvoll gegenüber anderen Mitwirkenden
- Konstruktive Kritik ist willkommen
- Hilf Neulingen, sich zurechtzufinden
- Keine Beleidigungen, Diskriminierung oder unangemessenes Verhalten

---

## Wie kann ich beitragen?

### 🐛 Bugs melden

Wenn du einen Bug findest:

1. **Prüfe bestehende Issues**: Vielleicht wurde der Bug schon gemeldet
2. **Erstelle ein neues Issue** mit:
   - **Titel**: Kurze, präzise Beschreibung
   - **Beschreibung**: Was ist passiert? Was wurde erwartet?
   - **Schritte zur Reproduktion**: Wie kann der Bug nachgestellt werden?
   - **Umgebung**: FPP-Version, Browser, Betriebssystem
   - **Logs**: Relevante Log-Ausgaben (`docker compose logs`)
   - **Screenshots**: Falls relevant (UI-Bugs)

**Beispiel:**

```markdown
### Bug: Liedwunsch-Button bleibt nach Klick deaktiviert

**Beschreibung:**
Nach dem Klick auf einen Liedwunsch-Button bleibt dieser deaktiviert, 
auch wenn der Song bereits in der Queue ist.

**Schritte zur Reproduktion:**
1. Öffne die Liedwunsch-Seite
2. Klicke auf einen Song
3. Gehe zurück zur Liedwunsch-Seite
4. Der Button ist immer noch deaktiviert

**Erwartetes Verhalten:**
Button sollte wieder aktiviert werden, sobald der Song in der Queue ist.

**Umgebung:**
- FPP Web Control: v1.0.0
- FPP: 7.5
- Browser: Chrome 120 (Android)

**Logs:**
```
[Logs hier einfügen]
```
```

### 💡 Feature-Vorschläge

Hast du eine Idee für ein neues Feature?

1. **Prüfe bestehende Feature Requests**: Gibt es bereits einen ähnlichen Vorschlag?
2. **Erstelle ein Issue** mit Label `enhancement`
3. **Beschreibe das Feature**:
   - **Problem**: Welches Problem löst das Feature?
   - **Lösung**: Wie könnte die Lösung aussehen?
   - **Alternativen**: Gibt es andere Lösungsansätze?
   - **Use Case**: Wofür würdest du das Feature nutzen?

**Beispiel:**

```markdown
### Feature Request: Multi-FPP-Unterstützung

**Problem:**
Aktuell kann nur ein FPP pro Instanz gesteuert werden. Bei mehreren 
Lichtershows (z.B. Vorgarten + Hinterhof) müsste man mehrere Container laufen lassen.

**Lösung:**
- Dropdown in der UI zur FPP-Auswahl
- Konfiguration mehrerer FPPs in der Konfiguration
- Separate Queues pro FPP

**Alternativen:**
- Mehrere Container mit verschiedenen Ports
- NGINX Reverse Proxy mit Subdomain pro FPP

**Use Case:**
Ich betreibe zwei Shows (Haupt- und Kindershow) auf separaten FPPs 
und möchte beide über eine UI steuern.
```

### 📝 Dokumentation verbessern

Dokumentation ist genauso wichtig wie Code!

- **Rechtschreibfehler** korrigieren
- **Unklare Abschnitte** verbessern
- **Beispiele** hinzufügen
- **Screenshots** aktualisieren
- **Übersetzungen** (aktuell nur Deutsch)

Kleine Änderungen können direkt als Pull Request eingereicht werden.

### 🛠️ Code beitragen

Du möchtest Code beitragen? Super!

1. **Fork das Repository**
2. **Erstelle einen Feature-Branch**: `git checkout -b feature/dein-feature`
3. **Implementiere deine Änderungen**
4. **Teste deine Änderungen** gründlich
5. **Committe deine Änderungen**: `git commit -m 'Add: Dein Feature'`
6. **Push den Branch**: `git push origin feature/dein-feature`
7. **Öffne einen Pull Request**

---

## Entwicklungsumgebung einrichten

### Voraussetzungen

- **Python 3.11+** (empfohlen: 3.12)
- **Git**
- **Docker & Docker Compose** (optional, für Testing)
- **Falcon Player (FPP)** im Netzwerk oder Preview-Modus

### Setup

1. **Repository klonen:**

   ```bash
   git clone https://github.com/TimUx/fpp-web-control.git
   cd fpp-web-control
   ```

2. **Virtual Environment erstellen:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # oder: venv\Scripts\activate  # Windows
   ```

3. **Dependencies installieren:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Konfiguration anlegen:**

   ```bash
   mkdir -p config data && cp config/config.example.json config/config.json
   ```

   Für Entwicklung **ohne FPP** in `config/config.json` setzen:
   ```json
   "previewMode": true
   ```

5. **Starten:**

   ```bash
   APP_CONFIG_PATH=config/config.json sh docker-entrypoint.sh \
       gunicorn --workers 1 --threads 8 --reload -b 127.0.0.1:8000 app:app
   ```

   `docker-entrypoint.sh` erzeugt `config.js` für den Browser und startet dann den Server
   unter `http://localhost:8000`. `--reload` lädt Python-Änderungen neu; nach Änderungen an der
   Konfiguration den Befehl neu starten.

   Wichtig: immer nur **ein** Worker. Warteschlange, Zeitplan und Status liegen im
   Arbeitsspeicher des Prozesses.

### Entwicklungs-Workflow

**Mit echtem FPP vorsichtig sein:** Die App steuert den FPP aktiv (Hintergrund-Effekt,
Playlists, bei aktivem Tagescode auch die Matrix). Für Arbeiten an der Oberfläche den
Vorschau-Modus oder einen Mock-FPP verwenden.

**Matrix-Verkabelung prüfen, ohne Lichter zu schalten:**
```bash
python code_matrix.py --fpp http://fpp.local --model Matrix --text 123 --dry-run
```

**Docker für Testing:**
```bash
docker compose up --build
```

**Logs verfolgen:**
```bash
docker compose logs -f fpp-control
```

---

## Pull Request Prozess

### 1. Branch benennen

Verwende aussagekräftige Branch-Namen:

- **Feature**: `feature/multi-fpp-support`
- **Bugfix**: `fix/request-button-stuck`
- **Dokumentation**: `docs/update-faq`
- **Refactoring**: `refactor/notification-system`

### 2. Commits

**Commit-Nachricht-Format:**

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: Neues Feature
- `fix`: Bugfix
- `docs`: Dokumentation
- `style`: Formatierung, fehlende Semikolons, etc.
- `refactor`: Code-Refactoring ohne Feature-/Bugfix-Änderung
- `test`: Tests hinzufügen oder ändern
- `chore`: Build-Prozess, Dependencies, etc.

**Beispiele:**

```
feat: Add multi-FPP support

- Add FPP selection dropdown in UI
- Allow multiple FPP configurations
- Separate queues per FPP instance

Closes #42
```

```
fix: Request button remains disabled after song added to queue

The button state was not properly reset after successful API call.
Added state refresh after request submission.

Fixes #38
```

### 3. Pull Request erstellen

**Titel**: Kurz und aussagekräftig (z.B. "Add multi-FPP support")

**Beschreibung sollte enthalten:**

- **Was wurde geändert?** Kurze Zusammenfassung
- **Warum?** Welches Problem wird gelöst?
- **Wie?** Technische Details (bei komplexen Änderungen)
- **Screenshots** (bei UI-Änderungen)
- **Testing**: Wie wurde getestet?
- **Breaking Changes**: Falls vorhanden, klar kennzeichnen
- **Related Issues**: `Closes #123` oder `Fixes #456`

**Template:**

```markdown
## Beschreibung

[Kurze Zusammenfassung der Änderungen]

## Motivation

[Welches Problem wird gelöst? Link zu Issue]

## Änderungen

- [ ] Feature A implementiert
- [ ] Bug B gefixt
- [ ] Dokumentation aktualisiert

## Screenshots

[Falls UI-Änderungen]

## Testing

- [ ] Lokal getestet mit Python 3.12
- [ ] Docker-Build erfolgreich
- [ ] Preview-Modus getestet
- [ ] Mit echtem FPP getestet

## Breaking Changes

[Falls vorhanden, klar beschreiben]

## Checklist

- [ ] Code folgt den Coding Guidelines
- [ ] Dokumentation wurde aktualisiert
- [ ] Tests wurden geschrieben (falls zutreffend)
- [ ] Alle Tests laufen durch
- [ ] Commit-Messages sind aussagekräftig
```

### 4. Code Review

- Pull Requests werden vom Maintainer geprüft
- Feedback konstruktiv annehmen
- Änderungen nach Review einarbeiten
- Bei Unklarheiten nachfragen

### 5. Merge

Nach erfolgreichem Review wird der PR gemerged.

---

## Coding Guidelines

### Python

**Style Guide**: [PEP 8](https://peps.python.org/pep-0008/)

**Wichtige Punkte:**

- **Indentation**: 4 Spaces (keine Tabs)
- **Line Length**: Max. 120 Zeichen (PEP 8: 79, aber bei langen URLs etc. OK)
- **Naming**:
  - `snake_case` für Funktionen, Variablen
  - `PascalCase` für Klassen
  - `UPPER_CASE` für Konstanten
- **Imports**: Gruppiert und alphabetisch sortiert
  ```python
  # Standard library
  import json
  import os
  import threading
  
  # Third-party
  import requests
  from flask import Flask, jsonify
  
  # Local
  from .utils import helper_function
  ```

**Type Hints verwenden:**

```python
from typing import Dict, List, Optional

def get_songs(playlist: str) -> List[Dict[str, Any]]:
    """
    Fetches songs from FPP playlist.
    
    Args:
        playlist: Name of the playlist
    
    Returns:
        List of song dictionaries
    """
    ...
```

**Docstrings** (Google Style):

```python
def send_notification(title: str, message: str, 
                     action_type: str = "info") -> None:
    """
    Sends notification via all configured channels.
    
    Args:
        title: Short notification title
        message: Full notification message
        action_type: Type of action (show_start, song_request, info)
    
    Raises:
        NotificationError: If all notification channels fail
    
    Example:
        >>> send_notification("Show started", "Main show started", "show_start")
    """
    ...
```

**Error Handling:**

```python
try:
    response = fpp_get("/api/fppd/status")
except requests.exceptions.Timeout:
    logger.error("FPP timeout")
    return {"error": "timeout"}
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return {"error": "unknown"}
```

**Logging statt Print:**

```python
# Nicht:
print("Show started")

# Sondern:
logger.info("Show started")
logger.error(f"Failed to start show: {error}")
```

### JavaScript

**Style Guide**: [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript) (locker angewandt)

**Wichtige Punkte:**

- **Indentation**: 2 Spaces
- **Semikolons**: Verwenden (ASI vermeiden)
- **Quotes**: Single quotes `'` bevorzugt, außer bei JSON
- **Naming**:
  - `camelCase` für Variablen, Funktionen
  - `PascalCase` für Klassen (falls verwendet)
  - `UPPER_CASE` für Konstanten

**Moderne Syntax:**

```javascript
// const/let statt var
const config = window.FPP_CONFIG || {};
let currentState = null;

// Arrow Functions
const updateStatus = (data) => {
  // ...
};

// Template Literals
const message = `Next show at ${time}`;

// Destructuring
const { title, message, action_type } = payload;

// Async/Await
const fetchState = async () => {
  try {
    const response = await fetch('/api/state');
    const data = await response.json();
    updateUI(data);
  } catch (error) {
    console.error('Failed to fetch state:', error);
  }
};
```

**Projektregeln (wichtig):**

- **Keine Inline-Skripte und keine `onclick`-Attribute.** Die Content-Security-Policy erlaubt nur
  Skripte aus eigenen Dateien. Seitencode liegt in `static/js/`, gemeinsamer Code in `app.js`.
- **Nichts von fremden Servern laden** (keine CDNs, keine Google Fonts). Bibliotheken, Schriften
  und Symbole gehören nach `static/`, die Lizenz nach `static/LICENSES.md`.
- **Eingaben von Besuchern und Daten vom FPP nie als HTML einfügen.** Immer `textContent`
  verwenden, nie `innerHTML` mit zusammengesetzten Texten.
- **Symbole** kommen aus `static/icons.svg` (`FPPApp.createIcon('name')` oder
  `<svg class="icon"><use href="/static/icons.svg#name"></use></svg>`).
- **Zugangscode und Geräte-Kennung** über `FPPApp.access.headers()` mitsenden.

### HTML/CSS

**HTML:**
- Semantisches HTML verwenden
- ARIA-Labels für Accessibility
- Indentation: 2 Spaces

```html
<button 
  class="action btn-show" 
  id="btn-show"
  aria-label="Hauptshow starten"
>
  Show starten
</button>
```

**CSS:**
- BEM-ähnliche Namenskonvention (nicht strikt)
- CSS-Variablen für Theme-Werte
- Mobile-First Approach

```css
:root {
  --primary-color: #c41e3a;
  --spacing-unit: 1rem;
}

.btn-show {
  background-color: var(--primary-color);
  padding: var(--spacing-unit);
}

@media (min-width: 768px) {
  .btn-show {
    padding: calc(var(--spacing-unit) * 1.5);
  }
}
```

---

## Testing

### Manuelles Testing

**Checklist vor Pull Request:**

- [ ] **Preview-Modus**: Funktioniert ohne FPP (`"previewMode": true`)?

- [ ] **Handy-Ansicht**: Startseite bei 375 px Breite im Leerlauf und bei laufender Show

- [ ] **Browser-Konsole**: keine Fehler, keine Verstöße gegen die Content-Security-Policy

- [ ] **Mit FPP**: Alle Features testen
  - Show-Start (Playlist 1 & 2)
  - Liedwunsch
  - Queue-Verwaltung
  - Scheduled Shows
  - Statistiken
  - Zugangscode (fest und Tagescode an der Matrix), Sperre nach Fehlversuchen
  - Musik auf dem Gerät (FalconBeat), falls vorhanden

- [ ] **Benachrichtigungen**: (wenn geändert)
  - MQTT
  - ntfy.sh
  - Webhooks

- [ ] **Browser-Kompatibilität**:
  - Chrome (Desktop + Mobile)
  - Firefox
  - Safari (iOS)

- [ ] **Docker-Build**:
  ```bash
  docker compose build
  docker compose up
  ```

### Automatisierte Tests

Aktuell: **Keine Unit-Tests** (Future Work)

Geplant:
- `pytest` für Python Backend
- Jest für JavaScript Frontend

**Falls du Tests hinzufügen möchtest:**

Achtung: Beim Import von `app` starten die Hintergrund-Threads und sprechen den konfigurierten
FPP an. Tests sollten deshalb `FPP_BASE_URL` auf einen Mock setzen oder den Vorschau-Modus nutzen.

```python
# tests/test_api.py
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_state(client):
    response = client.get('/api/state')
    assert response.status_code == 200
    data = response.get_json()
    assert 'queue' in data
```

---

## Dokumentation

### Dokumentation aktualisieren

Bei Code-Änderungen **immer** Dokumentation prüfen:

- **README.md**: Features, Configuration, API
- **NOTIFICATIONS.md**: Benachrichtigungs-Setup
- **ARCHITECTURE.md**: Technische Details
- **Code-Kommentare**: Docstrings, Inline-Kommentare

### Dokumentations-Guidelines

**Sprache**: Deutsch (primär), Englisch für Code-Kommentare OK

**Struktur**:
- Klare Überschriften
- Kurze Absätze
- Code-Beispiele
- Screenshots bei UI-Änderungen

**Markdown-Style**:
- Überschriften: `#`, `##`, `###` (nicht unterstrichen)
- Code: \`\`\`python, \`\`\`bash, \`\`\`javascript
- Links: `[Text](URL)`
- Listen: `-` für unordered, `1.` für ordered
- Tabellen für strukturierte Daten

**Beispiele bevorzugen:**

Nicht:
```
Die Funktion send_notification sendet Benachrichtigungen.
```

Sondern:
```python
# Benachrichtigung senden
send_notification(
    title="Show gestartet",
    message="Hauptshow wurde gestartet",
    action_type="show_start"
)
```

---

## Fragen?

- **GitHub Issues**: Für Bugs und Feature Requests
- **GitHub Discussions**: Für allgemeine Fragen und Diskussionen
- **Pull Requests**: Direkt im PR kommentieren

---

**Vielen Dank für deine Beiträge! 🎉**
