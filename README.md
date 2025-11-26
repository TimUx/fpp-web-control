# Falcon Player Web Control

Serverseitige (Python/Flask) Steuer-Seite für den Falcon Player (FPP). Der Container kapselt alle API-Aufrufe, verwaltet Wunsch-Queue und Scheduling und liefert die festliche Mobil-Oberfläche direkt aus.

**Netzwerk-Hinweis:** Diese Web-Applikation sollte im gleichen LAN wie der Falcon Player betrieben werden. Über Port-Weiterleitungen im Router und DynDNS kann die lokal betriebene Web-Applikation für Besucher über das Internet erreichbar gemacht werden, ohne dass diese direkt mit dem Falcon Player kommunizieren müssen.

```
                                    ┌─────────────────────────────────────────────────┐
                                    │              Lokales Netzwerk (LAN)             │
                                    │                                                 │
  ┌──────────────┐                  │   ┌─────────────────┐     ┌─────────────────┐   │
  │   Besucher   │                  │   │  FPP Web        │     │  Falcon Player  │   │
  │   (Handy/    │   ──────────►    │   │  Control        │ ──► │  (FPP)          │   │
  │   Browser)   │   Internet       │   │  Container      │     │  192.168.x.x    │   │
  └──────────────┘                  │   │  :8080          │     └─────────────────┘   │
         │                          │   └─────────────────┘                           │
         │                          │            ▲                                    │
         │                          └────────────│────────────────────────────────────┘
         │                                       │
         │        ┌─────────────────┐            │
         └──────► │     Router      │ ───────────┘
    DynDNS /      │  Port-Weiter-   │   Port 8080
    öffentl. IP   │  leitung :8080  │
                  └─────────────────┘
```
**Vorteile dieser Architektur:**
- Besucher kommunizieren nur mit der Web-App, nicht direkt mit dem FPP
- Der Falcon Player bleibt im geschützten LAN
- Die Web-App übernimmt Authentifizierung und Zugangskontrolle

## Funktionen
- Drei große Aktions-Buttons: "Show starten", "Kids-Show starten" und "Lied wünschen".
- Header mit konfigurierbarem Namen (z.B. "Brauns Lichtershow").
- Serverseitig verwaltete Wunsch-Queue: Songs aus der Wunsch-Playlist werden aus dem FPP geladen, in der Web-App als Liste angezeigt (Titel + Dauer) und können einzeln angefordert werden. Vor jedem Wunsch werden Effekte gestoppt und Ausgänge deaktiviert; Wünsche laufen nacheinander.
- Warteschlange unter dem Status sichtbar: aktueller Wunsch und weitere offene Wünsche werden direkt auf der Startseite gelistet.
- Countdown zur nächsten vollen Stunde mit automatischem Start der geplanten Show (17:00 Kids-Show; 18/19/20/21 Uhr Standardshow). Laufende Wünsche werden dabei unterbrochen und danach fortgesetzt. Nach 21:00 gibt es keine Automatik mehr.
- Nach dem letzten Wunsch wird automatisch der definierte Background-Effekt (Sequence "background") wieder gestartet.
- Minimaler Client: der Browser ruft nur noch die Backend-Endpunkte auf und pollt serverseitige Statusdaten.
- Spenden-Button mit eigener Detailseite, konfigurierbarem PayPal-Pool-Link, Kampagnen-Namen und Beschreibungstext.
- Wunschseite als eigene HTML-Seite (ähnlich der Spenden-Seite) mit Songliste, Wunsch-Buttons und "Zurück"-Button zur Startseite.
- Fällt die FPP-Playlist-Anfrage aus (z.B. für Demos ohne Backend), wird automatisch eine Beispiel-Songliste angezeigt, damit eine Vorschau möglich bleibt. Im optionalen Vorschau-Modus werden alle Seiten mit Demo-Inhalten befüllt, ohne dass ein FPP erreichbar sein muss.
- Automatische Sperren: läuft ein Wunsch, sind Show/Kids-Buttons deaktiviert; läuft eine Standard-Show, sind alle drei Buttons bis zum Ende gesperrt. Ab 22:00 Uhr (bis 16:30 Uhr) sind alle Buttons deaktiviert, damit nichts mehr abgespielt wird.

<img src="screenshot.png" height="800px"> <img src="screenshot_2.png" height="800px">

## Konfiguration per `.env`
Alle Werte werden beim Container-Start als Umgebungsvariablen gelesen. Beispiel `.env`:

```
SITE_NAME=Brauns Lichtershow
SITE_SUBTITLE=Fernsteuerung für den Falcon Player
FPP_BASE_URL=http://fpp.local
FPP_PLAYLIST_SHOW=show 1
FPP_PLAYLIST_KIDS=show 2
FPP_PLAYLIST_REQUESTS=all songs
FPP_PLAYLIST_IDLE=background
FPP_SHOW_START_DATE=2024-12-01
FPP_SHOW_END_DATE=2025-01-06
FPP_POLL_INTERVAL_MS=15000
CLIENT_STATUS_POLL_MS=10000
DONATION_POOL_ID='abc?123$=pool'
DONATION_CAMPAIGN_NAME=Winter Lights
DONATION_SUBTITLE=Unterstütze die Lichtershow
# Leer lassen, um keinen Beschreibungstext auf der Spendenseite zu zeigen
DONATION_TEXT=
PREVIEW_MODE=false
ACCESS_CODE=1234
# Social Media Links
SOCIAL_FACEBOOK=https://facebook.com/example
SOCIAL_INSTAGRAM=https://instagram.com/example
SOCIAL_TIKTOK=
SOCIAL_WHATSAPP=
SOCIAL_YOUTUBE=https://youtube.com/@example
SOCIAL_WEBSITE=https://example.com
SOCIAL_EMAIL=kontakt@example.com
```

Eine ausfüllbare Vorlage liegt als `.env.example` bei.

Parameter im Überblick:
- `SITE_NAME`: Text im Seitenkopf.
- `SITE_SUBTITLE`: Unterzeile unter dem Namen.
- `FPP_BASE_URL`: Basis-URL des FPP (z.B. `http://fpp.local`).
- `FPP_PLAYLIST_SHOW`, `FPP_PLAYLIST_KIDS`: Namen der regulären Shows.
- `FPP_PLAYLIST_REQUESTS`: Playlist mit allen verfügbaren Liedern für Wünsche.
- `FPP_PLAYLIST_IDLE`: Name der Idle-Playlist, die außerhalb von Shows/Wünschen laufen soll.
- `FPP_SHOW_START_DATE`, `FPP_SHOW_END_DATE`: Optionales Start-/Enddatum (`YYYY-MM-DD`) für das automatische Stundenscheduling. Außerhalb des Fensters werden keine Shows automatisch gestartet.
- `FPP_POLL_INTERVAL_MS`: Server-seitiges Status-Abfrageintervall in Millisekunden.
- `CLIENT_STATUS_POLL_MS`: Polling-Intervall, mit dem der Browser den Server nach dem Status fragt.
- `DONATION_POOL_ID`: ID des PayPal-Pools. Der Link wird als `https://www.paypal.com/pool/<ID>` erzeugt.
  - Pool-IDs mit Sonderzeichen (`?`, `$`, `=`, `+`, ...) in einfache Anführungszeichen setzen (z.B. `DONATION_POOL_ID='abc?123$=pool'`), damit die Zeichen unverändert in die URL übernommen werden.
- `DONATION_CAMPAIGN_NAME`: Optionaler Name der Spendenaktion (zusätzliche Unterüberschrift auf der Spendenseite).
- `DONATION_SUBTITLE`: Unterzeile speziell für die Spendenseite (z.B. "Unterstütze die Lichtershow"). So bleibt die allgemeine Unterzeile der Startseite unverändert.
- `DONATION_TEXT`: Freier Beschreibungstext auf der Spendenseite. Leer lassen, wenn kein Text eingeblendet werden soll.
- `PREVIEW_MODE`: `true`, um generierte Beispielinhalte (Status, Countdown, Wunschliste) anzuzeigen, falls kein FPP angebunden ist oder nur ein schneller Screenshot benötigt wird.
- `ACCESS_CODE`: Optionaler Zugangscode. Wenn gesetzt, zeigt die Startseite zunächst ein großes Eingabefeld; nach korrektem Code wird die Steuerung freigeschaltet (wird pro Gerät im `localStorage` gemerkt).
- `SOCIAL_FACEBOOK`: URL zur Facebook-Seite. Wenn gesetzt, wird im Footer ein Facebook-Icon angezeigt.
- `SOCIAL_INSTAGRAM`: URL zum Instagram-Profil. Wenn gesetzt, wird im Footer ein Instagram-Icon angezeigt.
- `SOCIAL_TIKTOK`: URL zum TikTok-Profil. Wenn gesetzt, wird im Footer ein TikTok-Icon angezeigt.
- `SOCIAL_WHATSAPP`: URL/Link zu WhatsApp (z.B. `https://wa.me/491234567890`). Wenn gesetzt, wird im Footer ein WhatsApp-Icon angezeigt.
- `SOCIAL_YOUTUBE`: URL zum YouTube-Kanal. Wenn gesetzt, wird im Footer ein YouTube-Icon angezeigt.
- `SOCIAL_WEBSITE`: URL zur eigenen Website. Wenn gesetzt, wird im Footer ein Website-Icon angezeigt.
- `SOCIAL_EMAIL`: E-Mail-Adresse für Kontakt. Wenn gesetzt, wird im Footer ein E-Mail-Icon mit `mailto:`-Link angezeigt.

## Betrieb mit Docker Compose

1. `.env` wie oben erstellen.
2. Container starten:

   ```bash
   docker compose up --build
   ```

3. Seite unter `http://localhost:8080/` öffnen.

Das bereitgestellte `docker-entrypoint.sh` schreibt `config.js` mit dem Seitennamen/Poll-Intervall und startet anschließend Gunicorn mit der Flask-App.

### Alternativ: Einzel-Container

```bash
docker build -t fpp-control .
docker run --rm -p 8080:8000 --env-file .env fpp-control
```

## API-Routen der Flask-App
- `GET /api/state`: Liefert aktuellen Status (FPP-Status, Queue, Countdown-Info, Hinweistext) plus UI-Sperrflags für die Buttons.
- `POST /api/show` mit Body `{ "type": "show" | "kids" }`: Startet die entsprechende Playlist und pausiert ggf. Wünsche. 
- `GET /api/requests/songs`: Liest Titel, Dauer sowie Sequence-/Media-Namen aus der Wunsch-Playlist (`FPP_PLAYLIST_REQUESTS`).
- `POST /api/requests` mit Body `{ "song": "Titel", "sequenceName": "file.fseq", "mediaName": "song.mp3", "duration": 180 }`: Fügt einen Wunsch hinzu; wenn frei, startet er sofort.

## Genutzte FPP-API-Endpunkte (laut FPP-Doku)
- `GET /api/fppd/status`: Status-Abfrage für Player/Scheduler. 
- `GET /api/playlist/:PlaylistName`: Playlist-Inhalt (Songliste für Wünsche). 
- `GET /api/playlist/:PlaylistName/start`: Start einer Playlist (Show, Kids-Show, Idle, Wünsche). Für Wunsch-Songs wird zur Laufzeit eine temporäre Single-Song-Playlist gebaut und danach wieder gelöscht.
- Fallback für ältere Installationen: `POST /api/command/Start Playlist/:PlaylistName` aus der Command-API. 
- `GET /api/command/StopEffects`, `GET /api/command/DisableOutputs`: Effekte stoppen bzw. Ausgänge deaktivieren vor Wunsch-Abspielung. 
- `GET /api/command/StopPlaylist`: Stoppt laufende Playlist; zusätzlich nutzt das Backend bei Bedarf `GET /api/playlists/stop` aus der Playlist-API.

## Styling anpassen
Die komplette Optik liegt in `styles.css`. Änderungen werden direkt als statische Datei ausgeliefert.
