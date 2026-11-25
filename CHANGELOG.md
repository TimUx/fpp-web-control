# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [Unreleased]

---

## [1.11.0] - 2026-11-25

### Added
- **Ersatzadresse für den FPP** (`FPP_FALLBACK_URLS`): Antwortet der FPP unter `FPP_BASE_URL` nicht (z. B. Netzwerkkabel getrennt), wechselt die App zur nächsten Adresse desselben FPP, etwa seiner WLAN-Adresse, und kehrt zur ersten zurück, sobald sie wieder antwortet (Prüfung jede Minute). Die Statusabfrage gibt bei einem gezogenen Kabel nach 3 Sekunden auf statt nach 8. `/api/control` zeigt die genutzte Adresse (`fppUrl`).

### Changed
- **Laufschrift vor dem Wunsch ruckelt nicht mehr:** Der FPP zeichnet den Titel jetzt selbst (Overlay-Effekt *Text*, geglättete Schrift in Matrixhöhe) und schiebt ihn gleichmäßig Pixel für Pixel, statt dass die App jedes Bild über das Netzwerk schickt. Die Geschwindigkeit passt den Titel in den Vorspann. Ältere FPP ohne den Effekt bekommen automatisch die bisherige Methode (`FPP_WISH_TITLE_RENDERER`, `FPP_WISH_TITLE_FONT`).
- **Lautstärke per FPP-Befehl *Volume Set*:** `/api/system/volume` schrieb bei jeder Änderung die FPP-Einstellungen samt Backup auf die SD-Karte. Nach einer Unterbrechung zum FPP setzt die App die Lautstärke neu, weil ein neu gestarteter FPP mit der gespeicherten Lautstärke beginnt.

---

## [1.10.0] - 2026-11-25

### Added
- **Wunschliste: Suche und Sortierung.** Ein Suchfeld filtert beim Tippen (ohne Rücksicht auf Groß-/Kleinschreibung, Akzente und Wortreihenfolge). Sortiert wird standardmäßig alphabetisch mit Buchstaben-Trennern (englische Artikel wie „The“ zählen nicht mit); alternativ „Beliebt“ (am häufigsten gewünscht, aus der Statistik) und „Kurz zuerst“. Die gewählte Sortierung merkt sich das Gerät. `/api/requests/songs` liefert dafür `wishes`.

### Changed
- **Wunschliste:** Kopf mit Überschrift, Suche und Sortierung bleibt beim Scrollen oben stehen. Solange die Liste offen ist, sind Zeiten & Adresse, Countdown und allgemeine Hinweise ausgeblendet. Nach dem Wunsch geht es zurück an den Anfang der Startseite.

---

## [1.9.0] - 2026-11-23

### Added
- **Testmodus** (`/api/control/test/on` und `/api/control/test/off`, gleicher `CONTROL_TOKEN` wie der Handbetrieb): Show-Knöpfe und Liedwünsche funktionieren auch außerhalb der Showzeiten, damit sie sich live testen lassen. Er läuft `TEST_MODE_MINUTES` lang (Standard 60, per `?minutes=` änderbar) und schaltet sich dann selbst ab. Die Seite zeigt „Testmodus bis …“; Testläufe außerhalb der Showzeiten zählen nicht in der Statistik.

### Changed
- README: Die Anleitung für FPP-Presets nennt den Befehl **Trigger Command Preset**.

---

## [1.8.0] - 2026-11-22

### Added
- **Handbetrieb** (`CONTROL_TOKEN`, `/api/control/off` und `/api/control/on`): Für Veranstaltungen, bei denen der FPP von Hand gesteuert wird, lässt sich die App abschalten. Sie startet dann keine Shows, Wünsche oder geplanten Shows, fasst Hintergrund, Lautstärke und Matrix nicht an und zeigt den Besuchern einen Hinweis; wartende Wünsche werden verworfen. Nach dem Wiedereinschalten läuft alles wie gewohnt. Der Schalter übersteht einen Neustart und lässt sich aus dem FPP heraus (Befehl *URL* im Scheduler oder in einer Playlist) oder per Lesezeichen umlegen.
- **Spielzeit auf den Show-Knöpfen**: Unter der Beschriftung steht, wie lange die Show dauert (z. B. „22 Min.“ oder „1 Std. 5 Min.“), ausgelesen aus der FPP-Playlist und einmal pro Minute aktualisiert.

---

## [1.7.0] - 2026-11-20

### Added
- **Sonder-Shows** (`"special": true` in `FPP_SHOWS`): Shows neben den Haupt-Shows, etwa nach Genre oder mit Liedern vergangener Jahre, bekommen einen dezenteren Knopf (gleich groß, gedeckte Farbe), damit die Haupt-Shows vorne stehen.

---

## [1.6.0] - 2026-11-20

### Added
- **Beliebig viele Show-Knöpfe** (`FPP_SHOWS`): Jede Playlist bekommt einen roten Knopf (zwei pro Zeile, alle gleich groß, ein einzelner letzter mittig), mit eigener Beschriftung, optionalem Symbol und Kurznamen für den Countdown. Kurzform `Show=Show starten|Kids=Kids-Show starten|Retro`, ausführlich als JSON-Liste. Für die Knöpfe gibt es neue Symbole: Weihnachten (Baum, Schneeflocke, Glocke, Schlitten, Zuckerstange, Schneemann …), Musik (Gitarre, Schlagzeug, Mikrofon, Schallplatte, Kopfhörer, Mischpult, Blitz, Violine und Klavier für Klassik …) und mehr. Die Knöpfe heißen `playlist1`, `playlist2`, … und lassen sich so auch im Zeitplan verwenden. Ohne `FPP_SHOWS` bleibt es bei den zwei Knöpfen aus `FPP_PLAYLIST_1`/`_2`.

---

## [1.5.1] - 2026-11-18

### Changed
- **Statistik und Sprache als dezente Symbole**: Beide stehen getrennt von den Kanälen als zwei kleine Symbole ganz unten; das Sprach-Symbol wechselt zur jeweils anderen Sprache und nennt sie als Tooltip bzw. für Screenreader. Der Kanäle-Kasten zeigt nur noch die Kanäle und entfällt, wenn keine eingetragen sind.

---

## [1.5.0] - 2026-11-18

### Added
- **Kein Überziehen der Showzeit**: Shows und Wünsche, die über `FPP_SHOW_END_TIME` plus Puffer (`FPP_SHOW_END_TOLERANCE_MINUTES`, Standard 5) hinaus laufen würden, werden abgelehnt; die Meldung nennt, wann sie enden würden. Gerechnet wird mit dem, was gerade läuft (bei Shows mit allen restlichen Liedern der Playlist), und der ganzen Warteschlange. In der Wunschliste stehen solche Lieder als „Zu lang für heute“. Abschaltbar mit `FPP_SHOW_END_CHECK=false`.
- **Show-Start auch im Server gesperrt**, solange eine Show oder ein Wunsch läuft (bisher nur die Knöpfe im Browser).
- **Mehrsprachig (Englisch und Deutsch)**: Alle Seiten, Meldungen des Servers und Benachrichtigungen gibt es auf Englisch und Deutsch. Mit `APP_LANGUAGE=auto` (Standard) bekommt jeder Besucher die Sprache seines Browsers und kann unten auf der Seite umschalten; `APP_DEFAULT_LANGUAGE` gilt für andere Browsersprachen und für Benachrichtigungen. Weitere Sprachen lassen sich als `i18n/<code>.json` ergänzen.
- **Englische Dokumentation**: `README.md`, `NOTIFICATIONS.md` und `deploy/README.md` sind jetzt englisch, die deutschen Fassungen heißen `README.de.md`, `NOTIFICATIONS.de.md` und `deploy/README.de.md`.
- **Anleitung „Aus dem Internet erreichbar machen“** (`docs/internet-access.md`, deutsch `docs/internet-access.de.md`): Cloudflare Tunnel, eigene Domain bzw. DynDNS mit Portfreigabe und Reverse Proxy (Caddy, Nginx Proxy Manager, Traefik), Tailscale Funnel, VPS als Relais, FalconBeat-Pfade, Prüfung des Anschlusses auf DS-Lite/CGNAT und eine Sicherheits-Checkliste.
- **Lautstärke über die App** (`FPP_SHOW_VOLUME`, `FPP_IDLE_VOLUME`): Während Shows und Wünschen setzt die App die Lautstärke des FPP, auf Wunsch in beliebig vielen Zeiträumen (`16:00-18:00=90,18:00-20:00=75,20:00-21:00=50`), jeweils ab Beginn eines Lieds; sobald alles vorbei ist, geht sie auf den Leerlauf-Wert zurück. Auch eine direkt am FPP gestartete Show bekommt die Show-Lautstärke. Standardmäßig aus.

### Changed
- **Standardtexte folgen der Sprache**: Leere Einstellungen für Name, Untertitel, Knopf-Beschriftungen und Spendentexte zeigen jetzt den Standardtext in der Sprache des Besuchers. Wer bisher ohne `SITE_NAME` lief, sieht auf Englisch „FPP Light Show“.
- **Benachrichtigungen** kommen in `APP_DEFAULT_LANGUAGE` (Standard Englisch). Für deutsche Benachrichtigungen `APP_DEFAULT_LANGUAGE=de` setzen.
- **Hintergrund-Effekt außerhalb der Showzeiten**: Die App schaltet ihn nach dem Ende der Showzeit nicht mehr ab und schickt dafür auch nicht mehr alle 15 Sekunden „FSEQ Effect Stop“. Der FPP kann so als normale Weihnachtsbeleuchtung weiterlaufen. Hat die App ihn für eine Show oder einen Wunsch angehalten, der über das Ende der Showzeit hinaus lief, startet sie ihn danach wieder.

### Fixed
- **Hintergrund nach einem FPP-Neustart**: Die App fragt beim FPP nach, ob der Effekt wirklich läuft, statt sich auf ihre eigene Markierung zu verlassen. Bisher startete sie ihn nach einem Neustart des FPP während der Showzeit erst nach der nächsten Show wieder.

---

## [1.4.2] - 2026-11-16

### Changed
- **„Musik hören“ in eigener Zeile**: Der Lautsprecher-Knopf steht jetzt in voller Breite zwischen „Jetzt läuft“ und den Show-Knöpfen. Bei langen Liedtiteln rutschte er auf dem Handy rechts aus dem Bild; lange Titel ohne Leerzeichen werden außerdem umbrochen.

---

## [1.4.1] - 2026-11-16

### Fixed
- **Veraltete Seite im Browser (vor allem Safari)**: Skripte und Styles tragen jetzt einen Inhalts-Hash in der Adresse (`app.js?v=…`) und werden nach einem Update sofort neu geladen; bisher blieben Teile bis zu einer Woche im Browser-Cache. Seiten und API-Antworten werden nicht mehr zwischengespeichert, Icons bei jedem Aufruf beim Server abgeglichen. Ein noch offener Tab lädt sich nach einem Update einmal selbst neu – nicht, solange darüber Musik läuft.

---

## [1.4.0] - 2026-11-16

### Added
- Vorspann vor Wunschliedern (`FPP_WISH_LEAD_IN_SEQUENCE`, optional mit Musik über `FPP_WISH_LEAD_IN_MEDIA`, oder `FPP_WISH_LEAD_IN_SECONDS`; Standard: aus): eine kurze Sequenz oder Pause vor jedem Wunsch, in der die Handys das Lied von FalconBeat laden, damit der Ton mit dem ersten Takt einsetzt. Restzeit und Wartezeiten rechnen den Vorspann mit ein
- Titel des Wunschs als Laufschrift an der Matrix während des Vorspanns (`FPP_WISH_TITLE_ON_MATRIX`, `FPP_WISH_TITLE_COLOR`; Standard: aus). `code_matrix.py` kann dafür Buchstaben zeichnen und hat den Testmodus `--scroll`

### Fixed
- „Musik hören“ blieb endlos bei „Lädt …“, wenn der FalconBeat-Server die Audiodatei eines Lieds nicht ausliefern konnte. Der Knopf zeigt jetzt „Kein Ton“, die App versucht es mit wachsendem Abstand erneut (statt jede Sekunde) und umgeht dabei den Browser-Cache, damit eine zwischengespeicherte Fehlerantwort das Laden nicht eine Stunde lang blockiert

---

## [1.3.0] - 2026-11-10

### Changed
- Die Statistik zeigt nur noch das aktuelle Kalenderjahr. Frühere Jahre sind über eine Jahresauswahl als Archiv erreichbar (`/statistics?year=JJJJ`, API `GET /api/statistics?year=JJJJ` mit Liste der vorhandenen Jahre)

---

## [1.2.0] - 2026-11-10

### Changed
- Die Startseite zeigt allen Besuchern sofort alle Knöpfe. Der Zugangscode wird erst abgefragt, wenn eine Show gestartet oder ein Lied gewünscht werden soll (Dialog über der Seite), danach läuft die Aktion weiter
- Spenden- und Statistikseite sind ohne Code erreichbar
- „Zeiten & Adresse“ ist außerhalb der Showzeiten aufgeklappt und während der Showzeiten eingeklappt, auf allen Bildschirmgrößen; ein manuelles Auf- oder Zuklappen bleibt erhalten

---

## [1.1.0] - 2026-11-10

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
- paho-mqtt 2.1.0 → 2.2.0
- Neue Screenshots der aktuellen Oberfläche unter `docs/screenshots/` (sieben Ansichten); die alten Bilder im Hauptverzeichnis entfallen
- Countdown nennt bei Shows an einem anderen Tag das Datum und zeigt ab zwei Tagen „in N Tagen“ statt einer dreistelligen Stundenzahl; außerhalb der Showzeiten heißt der Status „Gerade keine Wiedergabe.“ statt „Bereit“; lange Titel in der Warteschlange werden auf dem Handy nicht mehr vom Abzeichen überdeckt
- Aufgeräumt: nicht verwendeter Screenshot, tote CSS-Regeln und Dependabot-Einträge für npm und Composer (das Projekt nutzt beides nicht) entfernt; CI prüft auch `code_matrix.py`
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

[Unreleased]: https://github.com/TimUx/fpp-web-control/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/TimUx/fpp-web-control/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/TimUx/fpp-web-control/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/TimUx/fpp-web-control/compare/v1.4.2...v1.5.0
[1.4.2]: https://github.com/TimUx/fpp-web-control/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/TimUx/fpp-web-control/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/TimUx/fpp-web-control/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/TimUx/fpp-web-control/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/TimUx/fpp-web-control/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/TimUx/fpp-web-control/compare/v1.0.4...v1.1.0
[1.0.0]: https://github.com/TimUx/fpp-web-control/releases/tag/1.0.0
[0.9.8]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.8
[0.9.6]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.6
[0.9.5]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.5
[0.9.4]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.4
[0.9.3]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9.3
[0.9]: https://github.com/TimUx/fpp-web-control/releases/tag/0.9
