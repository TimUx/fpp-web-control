# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [Unreleased]

### Added
- **Musik auf dem Besucher-Gerät (FalconBeat):** Erkennt das FPP-Plugin `fpp-plugin-FalconBeat` und zeigt bei laufender Show einen Lautsprecher-Button, der die Musik synchron im Browser abspielt (`falconbeat-audio.js`, Einrichtung siehe `deploy/README.md`)
- **Tagescode an der Pixel-Matrix:** täglich wechselnder Zugangscode, der im Leerlauf an einem FPP-Overlay-Modell angezeigt wird (`CODE_MATRIX_MODEL`, `code_matrix.py`); der feste `ACCESS_CODE` bleibt optional gültig
- Sperre nach 6 falschen Codes pro Anschluss für 10 Minuten
- Neue Einstellungen `FALCONBEAT_MODE`, `FALCONBEAT_SERVER_URL`, `FALCONBEAT_CLIENT_BASE`
- Docker Secrets: jede Variable kann als `<NAME>_FILE` gesetzt werden (z. B. `ACCESS_CODE_FILE`)
- `POST /api/access` prüft den Zugangscode serverseitig
- `/api/state` meldet `fppReachable` und `falconbeat.available`; die Oberfläche zeigt an, wenn FPP nicht erreichbar ist
- Umfassende Dokumentations-Überarbeitung mit strukturierter Gliederung
- Neue `ARCHITECTURE.md` mit technischer System-Dokumentation
- Neue `CONTRIBUTING.md` mit Richtlinien für Beiträge
- Neue `CHANGELOG.md` für Versions-Historie
- Detaillierte API-Dokumentation in README
- Erweiterte Deployment-Optionen (Docker Compose, Docker Run, Manual, Reverse Proxy, Systemd)
- FAQ-Sektion mit häufigen Problemen und Lösungen
- Vergleichstabelle für Benachrichtigungsmethoden

- Zeitplan der automatischen Shows ist konfigurierbar (`FPP_SHOW_SCHEDULE` / `showSchedule`)
- Optionale Aufbewahrungsfrist für Statistiken (`STATISTICS_RETENTION_DAYS`)
- Docker-`HEALTHCHECK` auf `/health`
- Barrierefreiheit: Live-Regionen für Status und Hinweise, sichtbarer Tastaturfokus, `prefers-reduced-motion`
- `app.js` mit gemeinsamen Helfern für alle Seiten (ersetzt duplizierten Code)

- „Jetzt läuft“-Karte oben auf der Startseite mit Liedtitel, Restzeit und Musik-Knopf; gesperrte Knöpfe werden klein
- Knöpfe mit Symbolen und klarer Rangfolge; „Spenden“ als dezenter Knopf am Ende
- Eigene Wünsche sind in der Warteschlange markiert, bereits gewünschte Lieder in der Liste gesperrt
- Grenzen für Wünsche: `MAX_WISHES_PER_DEVICE` (Standard 2) und `MAX_QUEUE_LENGTH` (Standard 10)
- Titel ohne Note fallen auf den Sequenznamen ohne Dateiendung zurück

- Geschätzte Wartezeit je Wunsch, Countdown nennt Showart und Uhrzeit, „Wird gestartet …“ als Rückmeldung
- Kopfbereich auf dem Handy kürzer: Zeiten und Adresse aufklappbar
- Seitentitel aus `SITE_NAME`, Symbol, Farbe der Browserleiste, Link-Vorschau (`SITE_DESCRIPTION`, optional `SITE_IMAGE_URL`)

- `docker-compose.yml` lädt die Einstellungen aus `.env` und nutzt das fertige Image; neue `docker-stack.yml` für Docker Swarm mit allen Variablen, Secrets und Traefik-Labels

### Security
- Sicherheits-Header (Content-Security-Policy ohne Inline-Skripte, kein Einbetten in fremde Seiten, `nosniff`, Referrer-Policy); Seiten-Skripte liegen dafür in `static/js/`
- Schriften, Symbole und Chart.js werden selbst ausgeliefert (`static/`); Besucher bauen keine Verbindung mehr zu Google Fonts oder CDNs auf
- Die App lieferte ihr gesamtes Verzeichnis statisch aus (`/app.py`, `/config/config.json`, `/data/statistics.json`); jetzt sind nur noch die vorgesehenen Dateien erreichbar
- Der Zugangscode steht nicht mehr im Klartext in `config.js`
- Liedwünsche akzeptieren nur noch Titel aus der Wunsch-Playlist; Sequenz- und Mediennamen kommen ausschließlich von FPP
- Statistikseite gibt gespeicherte Titel als Text statt als HTML aus (Stored XSS)
- Fehlermeldungen der API enthalten keine internen FPP-Adressen mehr

### Changed
- Dokumentation auf den aktuellen Stand gebracht: README neu gegliedert (Konfiguration mit `config.json`-Schlüsseln, Zugangsschutz, FalconBeat, API), ARCHITECTURE.md neu geschrieben, CONTRIBUTING.md und NOTIFICATIONS.md angepasst
- `.env.example`: `FPP_PLAYLIST_IDLE` durch die tatsächlich gelesene Variable `FPP_BACKGROUND_EFFECT` ersetzt
- Liedwünsche sind ein Panel auf der Hauptseite (`/requests` leitet um), damit die Musik weiterläuft
- gunicorn läuft mit einem Worker und 8 Threads (der Zustand liegt im Prozessspeicher, mehrere Worker würden Warteschlange und Scheduler vervielfachen)
- `/api/state` enthält die FPP-Rohantwort nicht mehr
- Status wird schneller aktualisiert: Server und Browser fragen bei laufender Show häufiger ab, direkt nach einer Aktion wird sofort nachgefragt; im Hintergrund-Tab pausiert die Abfrage
- Chart.js wird mit Integritätsprüfung (SRI) geladen
- `config.template.js` entfernt (wurde nicht verwendet, `config.js` erzeugt der Entrypoint)
- Vollständige Umstrukturierung der README.md mit klarer Gliederung
- Verbesserte NOTIFICATIONS.md mit Schritt-für-Schritt-Anleitungen
- Übersichtlichere Darstellung aller Features und Konfigurationsoptionen

---

## [1.0.0] - 2025-12-08

🎉 **Major Release** - Statistiken, Benachrichtigungen und verbesserte Stabilität

### Added
- **Statistik-Seite** (`statistics.html`)
  - Vollständige Erfassung von Show-Starts und Liedwünschen
  - Interaktive Charts mit Chart.js
  - Top-5-Listen (beliebteste Shows und Songs)
  - Zeitverlauf-Diagramme (nach Stunden, Tagen, Wochen)
  - Persistente Speicherung in `statistics.json`
  - Atomare Schreibvorgänge gegen Datenkorruption
- **Benachrichtigungssystem**
  - Multi-Channel-Support: MQTT, ntfy.sh, Home Assistant, Webhooks
  - Benachrichtigungen bei Show-Start und Liedwunsch
  - Detaillierte NOTIFICATIONS.md Dokumentation
  - Preview-Modus überspringt Benachrichtigungen
- **Geplante-Show-Banner**
  - Prominente Anzeige wenn geplante Show läuft
  - "Wünsche pausiert" Hinweis
- **Docker-Verbesserungen**
  - Volume-Unterstützung für persistente Statistiken
  - `docker-compose.yml` mit Volume-Mount
  - Verbessertes `docker-entrypoint.sh`
  - `statistics.html` im Docker-Image enthalten

### Changed
- ntfy.sh-Integration überarbeitet
  - UTF-8 Encoding korrekt
  - Header-basierte API-Nutzung (statt JSON-Body)
  - Stabilere Fehlerbehandlung
- UI-Verbesserungen
  - Übersichtlichere Banner-Logik
  - Footer-Link zur Statistikseite
  - Redundante Hinweise entfernt
- Konfiguration
  - `.env.example` aktualisiert mit neuen Parametern
  - `config.template.js` erweitert

### Fixed
- ntfy.sh Encoding-Probleme
- Doppelte Quiet-Hours-Hinweise
- Statistik-Daten Korruptionsgefahr durch atomare Writes

### Breaking Changes
- **Statistik-Persistenz**: Bei Docker-Betrieb Volume für `data/` anlegen
- **Benachrichtigungen**: ntfy.sh API-Verwendung geändert (Header statt JSON)
- **Preview-Modus**: Benachrichtigungen werden übersprungen
- **Konfiguration**: Neue Umgebungsvariablen prüfen und übernehmen

---

## [0.9.8] - 2025-12-07

### Added
- Benachrichtigungssystem (Initial-Version)
- Statistik-Tracking für Benutzer-Interaktionen
- Docker-Support für Statistiken

### Changed
- Diagnostische Hinweise aufgeräumt
- Hinweistexte in Banner verschoben

---

## [0.9.6] - 2025-12-06

### Added
- Toast-Benachrichtigungen für Benutzeraktionen
- `SCHEDULED_SHOWS_ENABLED` Toggle
- Duplicate-Detection für Liedwünsche

### Changed
- Verbesserte Sichtbarkeit von Toast-Benachrichtigungen
- Scrolling in Liedwunsch-Liste optimiert

---

## [0.9.5] - 2025-11-27

### Added
- Buy Me a Coffee Button auf Spendenseite
- `BUYMEACOFFEE_USERNAME` Umgebungsvariable

### Changed
- Spendenseite Layout optimiert

---

## [0.9.4] - 2025-11-26

### Added
- Automatische Button-Deaktivierung außerhalb der Show-Zeiten
- Konfigurierbare Button-Texte (`BUTTON_PLAYLIST_1`, `BUTTON_PLAYLIST_2`)
- Show-Zeitraum Konfiguration (`FPP_SHOW_START_DATE`, `FPP_SHOW_END_DATE`)
- Tägliche Show-Zeiten (`FPP_SHOW_START_TIME`, `FPP_SHOW_END_TIME`)

### Changed
- Playlist-Namen über Umgebungsvariablen konfigurierbar
- Verbesserte Hinweise für deaktivierte Buttons

---

## [0.9.3] - 2025-11-26

### Added
- Social-Media-Footer mit Font Awesome Icons
- Konfigurierbare Social-Media-Links via `.env`
  - Facebook, Instagram, TikTok, WhatsApp, YouTube, Website, Email

### Changed
- Footer-Design verbessert

---

## [0.9] - 2025-11-19

🎊 **Erster öffentlicher Release**

### Added
- **Kern-Funktionalität**
  - Zwei konfigurierbare Playlist-Buttons
  - Liedwunsch-System mit Queue-Verwaltung
  - Serverseitige Queue-Verwaltung
  - Automatische Show-Planung
  - Background-Effekt nach letztem Wunsch
  - Countdown zur nächsten Show
- **Zugangscode-Schutz**
  - Optionaler Zugangscode für UI-Zugriff
  - Code-Prüfung auf allen Control-APIs
  - Konfigurierbar via `ACCESS_CODE` Umgebungsvariable
- **Spendenseite**
  - PayPal Pool Integration
  - Konfigurierbare Texte und Kampagnenname
  - Separate Seite mit "Zurück"-Button
- **FPP-API-Integration**
  - Status-Polling (Scheduler, Player)
  - Playlist-Verwaltung (Start, Stop)
  - Song-Details aus Playlists
  - Effekte und Ausgaben steuern
  - Kompatibilität mit älteren FPP-Versionen (Command-API Fallback)
- **UI/UX**
  - Responsive Mobile-First Design
  - Festliches Weihnachts-Theme
    - Schneeflocken-Animation
    - Weihnachtsbaum-Deko
    - Sterne und Ornamente
  - Button-Locking während Playback
  - Scrollbare Layouts
  - Status-Anzeige mit Live-Updates
- **Zeitsteuerung**
  - Scheduling-Window (Start/End-Date, Start/End-Time)
  - Automatische Button-Deaktivierung außerhalb Zeitfenster
  - Quiet-Hours-Hinweis
- **Konfiguration**
  - Umfangreiche `.env` Konfiguration
  - `config.template.js` für Frontend-Config
  - `docker-entrypoint.sh` für Config-Generierung
- **Docker**
  - Dockerfile für Containerisierung
  - docker-compose.yml für einfaches Deployment
  - Gunicorn WSGI Server (4 Worker)
  - Python 3.11 Slim-Image
- **Dokumentation**
  - Ausführliche README.md
  - `.env.example` mit Beispielwerten
  - Screenshots aller Hauptseiten

### Changed
- Migrated from old project structure to fpp-web-control
- UI-Verbesserungen über mehrere Iterationen
  - Button-Styling
  - Layout-Anpassungen
  - Scroll-Verhalten
  - Festive-Overlay Optimierungen

### Fixed
- Config-Generation für valides JSON
- Wishlist-Parsing aus FPP mainPlaylist
- Zeitmanagement mit Standard-time-Modul
- Thread-Safety mit RLock
- Doppelte Quiet-Hours-Hinweise
- Layout-Alignment für korrektes Scrolling

---

## Versions-Schema

Dieses Projekt verwendet [Semantic Versioning](https://semver.org/lang/de/):

- **MAJOR** (1.x.x): Breaking Changes, größere Architektur-Änderungen
- **MINOR** (x.1.x): Neue Features, abwärtskompatibel
- **PATCH** (x.x.1): Bugfixes, kleine Verbesserungen

### Release-Tags

- Stabile Releases: `1.0.0`, `1.1.0`, etc.
- Pre-Releases: `0.9`, `0.9.3`, etc.

---

## Migration & Upgrade-Hinweise

### Von 0.9.x zu 1.0.0

**Wichtige Änderungen:**

1. **Statistiken (Breaking)**
   - Neu: `data/statistics.json` wird erstellt
   - Docker: Volume für `/app/data` empfohlen
     ```yaml
     volumes:
       - ./data:/app/data
     ```
   - Backup bestehender Daten vor Upgrade

2. **Benachrichtigungen (Breaking)**
   - ntfy.sh API geändert: Header statt JSON
   - Neue Umgebungsvariablen prüfen:
     - `NOTIFY_ENABLED`
     - `NOTIFY_NTFY_ENABLED`
     - `NOTIFY_MQTT_ENABLED`
     - etc.
   - Preview-Modus überspringt Benachrichtigungen

3. **Konfiguration**
   - `.env.example` kopieren und anpassen
   - Neue Variablen hinzugefügt (siehe `.env.example`)

4. **Docker**
   - `docker-compose.yml` aktualisiert
   - Volume-Mount für Statistiken hinzufügen
   - Container neu bauen:
     ```bash
     docker compose down
     docker compose build --no-cache
     docker compose up -d
     ```

**Empfohlener Upgrade-Prozess:**

```bash
# 1. Backup
cp data/statistics.json data/statistics.json.backup  # falls vorhanden
cp .env .env.backup

# 2. Code aktualisieren
git pull
git checkout 1.0.0

# 3. Konfiguration prüfen
diff .env.backup .env.example
# Neue Variablen aus .env.example in .env übernehmen

# 4. Docker neu bauen
docker compose down
docker compose build --no-cache
docker compose up -d

# 5. Testen
# - UI öffnen und prüfen
# - Statistik-Seite testen
# - Benachrichtigungen testen
# - Show-Start testen
# - Liedwunsch testen
```

---

## Support & Feedback

- **Issues**: [GitHub Issues](https://github.com/TimUx/fpp-web-control/issues)
- **Discussions**: [GitHub Discussions](https://github.com/TimUx/fpp-web-control/discussions)
- **Pull Requests**: Siehe [CONTRIBUTING.md](CONTRIBUTING.md)

---

[Unreleased]: https://github.com/TimUx/fpp-web-control/compare/1.0.0...HEAD
[1.0.0]: https://github.com/TimUx/fpp-web-control/releases/tag/1.0.0
[0.9.8]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.8
[0.9.6]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.6
[0.9.5]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.5
[0.9.4]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.4
[0.9.3]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.3
[0.9]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9
