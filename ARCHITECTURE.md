# 🏗️ Architektur

Technischer Aufbau von FPP Web Control. Die Bedienung und alle Einstellungen stehen in der [README](README.md).

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Systembild](#systembild)
- [Backend](#backend)
- [Frontend](#frontend)
- [Abläufe](#abläufe)
- [Zustand](#zustand)
- [FPP-Schnittstelle](#fpp-schnittstelle)
- [Tagescode an der Matrix](#tagescode-an-der-matrix)
- [Musik im Browser (FalconBeat)](#musik-im-browser-falconbeat)
- [Sicherheit](#sicherheit)
- [Betrieb](#betrieb)
- [Grenzen und Ausbaumöglichkeiten](#grenzen-und-ausbaumöglichkeiten)

---

## Überblick

FPP Web Control sitzt zwischen den Besuchern und dem Falcon Player (FPP). Besucher sprechen nur mit dieser App; die App spricht mit dem FPP.

**Grundsätze**

1. **Der Server entscheidet.** Warteschlange, Sperren, Zeitplan und Zugangscode werden auf dem Server verwaltet und geprüft. Der Browser zeigt nur an.
2. **Kein direkter FPP-Zugriff** für Besucher.
3. **Abfragen statt Push:** Der Server fragt den FPP ab, der Browser fragt den Server ab. WebSockets nutzt nur die Musik-Funktion, und die laufen am Backend vorbei direkt zum FalconBeat-Server.
4. **Ein Prozess:** Der gesamte Zustand liegt im Arbeitsspeicher eines Prozesses.
5. **Nichts von fremden Servern:** Schriften, Symbole und Bibliotheken werden selbst ausgeliefert.

**Technik**

| Bereich | Eingesetzt |
|---|---|
| Backend | Python 3.11, Flask, Gunicorn (1 Worker, 8 Threads), requests, paho-mqtt (optional) |
| Frontend | HTML, CSS und JavaScript ohne Framework und ohne Build-Schritt; Chart.js nur auf der Statistikseite |
| Betrieb | Docker; Konfiguration über `config.json`, Umgebungsvariablen oder Docker Secrets |

---

## Systembild

```
 Besucher (Browser)
      │  HTTPS
      ▼
 ┌──────────────────┐
 │  Reverse Proxy   │  z. B. Traefik
 └───┬──────────┬───┘
     │          │  nur /falconbeat/ws und /falconbeat/media/*
     │          ▼
     │   ┌──────────────────┐   Audio + Play/Pause   ┌───────────────────────┐
     │   │ FalconBeat-Server│◄──────────────────────│ FPP-Plugin FalconBeat │
     │   └──────────────────┘                        └───────────┬───────────┘
     ▼                                                           │
 ┌──────────────────────────┐   HTTP (LAN)            ┌──────────┴───────────┐
 │  FPP Web Control         │────────────────────────►│  Falcon Player (FPP) │
 │  Flask + Hintergrund-    │   Status, Playlists,    │                      │
 │  Threads                 │   Effekte, Overlay      └──────────────────────┘
 └───────┬──────────────────┘
         │  optional
         ▼
   ntfy / MQTT / Home Assistant / Webhook
```

FalconBeat ist optional. Ohne es entfallen der rechte Zweig und der Knopf „Musik hören“.

---

## Backend

### Dateien

| Datei | Aufgabe |
|---|---|
| `app.py` | Konfiguration, API, FPP-Anbindung, Warteschlange, Zeitplan, Statistik, Benachrichtigungen, Tagescode |
| `code_matrix.py` | Zeichnet Ziffern auf ein FPP-Overlay-Modell; auch als eigenständiges Testwerkzeug |
| `docker-entrypoint.sh` | Erzeugt beim Start `config.js` mit den Einstellungen für den Browser |

### Konfiguration

`_cfg(key, env_key, default)` löst jede Einstellung in dieser Reihenfolge auf: `config.json` → Datei aus `<ENV>_FILE` → Umgebungsvariable → Standardwert. `docker-entrypoint.sh` nutzt dieselbe Reihenfolge für `config.js`. In `config.js` stehen nur Werte, die der Browser sehen darf. Der Zugangscode gehört nicht dazu, nur die Angabe, *ob* einer nötig ist.

### Hintergrund-Threads

Alle Threads starten beim Import von `app.py` (`boot_threads()`).

| Thread | Takt | Aufgabe |
|---|---|---|
| `status_worker` | 15 s im Leerlauf, 5 s wenn etwas läuft oder wartet; nach einer Aktion nach 3 s geweckt | FPP-Status holen, „Jetzt läuft“ bestimmen, Warteschlange weiterschalten, Hintergrund-Effekt starten oder stoppen |
| `scheduler_worker` | 1 s | Startet geplante Shows zur eingestellten Uhrzeit |
| `falconbeat_worker` | 30 s | Prüft, ob Musik im Browser angeboten werden kann |
| `code_display_worker` | 1,5 s während der Showzeiten | Zeigt den Tagescode an der Matrix, solange der FPP im Leerlauf ist (nur bei gesetztem `CODE_MATRIX_MODEL`) |

Netzwerkzugriffe geschehen außerhalb der Sperre `state_lock`, damit `/api/state` nie auf den FPP warten muss.

### Routen

| Route | Zweck |
|---|---|
| `/`, `/donation`, `/statistics` | HTML-Seiten; Name und Beschreibung der Show werden in den Kopf eingesetzt |
| `/requests` | Leitet auf `/#wunsch` um (die Wunschliste ist Teil der Startseite) |
| `/styles.css`, `/app.js`, `/falconbeat-audio.js`, `/config.js`, `/static/<pfad>` | Statische Dateien. Es gibt bewusst keinen allgemeinen Static-Ordner auf das App-Verzeichnis |
| `GET /api/state` | Gesamter Zustand für die Oberfläche |
| `POST /api/access` | Zugangscode prüfen |
| `POST /api/show` | Show starten |
| `GET /api/requests/songs`, `POST /api/requests` | Wunschliste lesen, Lied wünschen |
| `GET /api/statistics` | Ausgewertete Statistik |
| `GET /health` | Lebenszeichen für den Docker-Healthcheck |

Beispiele für Anfragen und Antworten stehen in der [README](README.md#-api).

---

## Frontend

Drei Seiten ohne Framework. Jede lädt `config.js`, `app.js` und ihr eigenes Skript aus `static/js/`.

| Datei | Aufgabe |
|---|---|
| `index.html` + `static/js/index.js` | Startseite: Code-Eingabe, „Jetzt läuft“-Karte, Show-Knöpfe, Wunschliste als Panel, Warteschlange, Musik-Knopf |
| `donation.html` + `static/js/donation.js` | Spendenlinks |
| `statistics.html` + `static/js/statistics.js` | Diagramme und Tabellen |
| `app.js` | Gemeinsam: Zugangscode und Geräte-Kennung, Toasts, Symbole, Fußbereich (`window.FPPApp`) |
| `falconbeat-audio.js` | Sync-Client für die Musik (`window.FalconBeatAudio`) |
| `styles.css` | Gesamtes Design, Farben als CSS-Variablen |
| `static/` | Schriften, Symbol-Sprite, Chart.js, Lizenzhinweise |

**Abfragen:** Die Startseite fragt `/api/state` im Leerlauf alle 10 s ab (`clientStatusPollMs`), bei laufender Show oder wartenden Wünschen alle 4 s. Im Hintergrund-Tab pausiert die Abfrage.

**Im Browser gespeichert (`localStorage`):** der eingegebene Zugangscode, eine zufällige Geräte-Kennung für die Wunsch-Grenzen und die Kennung des Musik-Clients.

---

## Abläufe

### Show starten

```
Browser                    Backend                         FPP
  │ POST /api/show           │                              │
  │ X-Access-Code ──────────►│ Code prüfen                  │
  │                          │ Statistik + Benachrichtigung │
  │                          │ Effekte und Playlist stoppen►│
  │                          │ Tagescode von Matrix nehmen ►│
  │                          │ Playlist starten ───────────►│
  │◄──── {"ok": true} ───────│ status_worker nach 3 s wecken│
```

### Lied wünschen

1. `POST /api/requests {"song": "<Titel>"}`
2. Der Server prüft Zugangscode und Sperren und sucht den Titel in der Wunsch-Playlist (60 s zwischengespeichert). Sequenz, Musikdatei und Dauer stammen immer vom FPP, nie vom Browser.
3. Abgelehnt wird: unbekannter Titel, schon gewünscht, Warteschlange voll, Grenze pro Gerät erreicht.
4. Der Wunsch kommt in die Warteschlange. Ist er der erste und läuft keine geplante Show, startet er sofort.
5. Zum Abspielen legt der Server die temporäre FPP-Playlist `__wish_single__` mit genau diesem Lied an und startet sie.
6. Der `status_worker` bemerkt das Liedende, entfernt den Wunsch und startet den nächsten. Ist die Warteschlange leer, läuft wieder der Hintergrund-Effekt.

### Geplante Show

Der `scheduler_worker` startet zur Uhrzeit aus dem Zeitplan die Playlist und setzt `scheduled_show_active`. Wünsche pausieren währenddessen; danach wird die Warteschlange fortgesetzt. Shows in der Ruhezeit werden übersprungen.

### Sperren

`compute_locks()` leitet aus Status und Uhrzeit ab, was erlaubt ist:

| Lage | Show-Knöpfe | Wunsch-Knopf |
|---|---|---|
| Außerhalb der Saison oder Ruhezeit | gesperrt | gesperrt |
| Hauptshow läuft | gesperrt | gesperrt |
| Wunsch läuft | gesperrt | frei |
| Leerlauf | frei | frei |

Der Server setzt die Wunsch-Sperre auch selbst durch, nicht nur die Oberfläche.

---

## Zustand

```python
state = {
    "queue": [],                    # Wünsche: title, sequenceName, mediaName, duration, owner
    "current_request": None,        # der Wunsch, der gerade läuft
    "scheduled_show_active": False,
    "last_status": {},              # letzter FPP-Status (gekürzt)
    "now_playing": None,            # title, kind (show|wish), secondsRemaining
    "next_show": None,              # nächste geplante Show
    "note": "",
    "background_active": False,     # Hintergrund-Effekt läuft
    "fpp_reachable": None,
    "code_visible": False,          # Tagescode steht an der Matrix
    "falconbeat": {...},            # installed, enabled, server_ok, available
}
```

- Geschützt durch `state_lock` (`threading.RLock`).
- **Nicht dauerhaft:** Nach einem Neustart ist die Warteschlange leer.
- **Dauerhaft** sind nur `data/statistics.json` (Schreiben über temporäre Datei und Umbenennen) und `data/code_secret`.
- `owner` ist die Geräte-Kennung des Wünschenden. Sie verlässt den Server nie; Browser erhalten nur `mine: true/false`.

---

## FPP-Schnittstelle

| Aufruf | Zweck |
|---|---|
| `GET /api/fppd/status` | Status, laufende Playlist und Sequenz, Restzeit |
| `GET /api/playlist/<name>` | Einträge einer Playlist (Wunschliste, Titel der laufenden Show) |
| `GET /api/playlist/<name>/start` | Playlist starten; Ausweichweg `POST /api/command/Start Playlist/<name>` |
| `POST /api/playlist/__wish_single__`, `DELETE …` | Temporäre Playlist für einen Wunsch anlegen und entfernen |
| `GET /api/command/Effects Stop`, `Stop Now`, `Outputs Off`, `GET /api/playlists/stop` | Vor einem Start alles anhalten |
| `GET /api/command/FSEQ Effect Start/<name>/true/true` (loop, bg), `FSEQ Effect Stop/<name>` | Hintergrund-Effekt (Sequenz `<name>.fseq`) |
| `GET /api/plugin`, `GET /api/plugin/fpp-plugin-FalconBeat/settings/<name>` | FalconBeat-Plugin erkennen (`enabled`, `serverAddr`) |
| `GET /api/overlays/model/<name>` | Beschreibung des Matrix-Modells |
| `PUT /api/overlays/model/<name>/data`, `/state`, `/fill`, `/pixel` | Tagescode zeichnen und wieder entfernen |

**Titel:** `_extract_song()` nimmt die Note des Playlist-Eintrags, sonst den Namen der Sequenz ohne Endung. „Jetzt läuft“ sucht die laufende Sequenz in der laufenden Playlist (5 Minuten zwischengespeichert).

**Fehler:** Ist der FPP nicht erreichbar, bleibt der letzte Status stehen, `fpp_reachable` wird `false`, und die Oberfläche sperrt die Knöpfe mit einem Hinweis. API-Antworten enthalten keine internen Adressen; Einzelheiten stehen im Log.

---

## Tagescode an der Matrix

**Berechnung:** `HMAC-SHA256(Geheimnis, Datum)` modulo 10^Ziffern. Der Code ist damit für alle gleich, wechselt um Mitternacht und übersteht Neustarts. Das Geheimnis kommt aus `CODE_SECRET` oder wird einmalig erzeugt und in `data/code_secret` abgelegt.

**Anzeige** (`code_display_worker`):

- Nur während der Saison und der Showzeiten.
- Der Thread fragt den FPP selbst alle 1,5 s ab. Meldet er `idle`, wird der Code gezeichnet, sonst entfernt. So erscheint der Code auch in der kurzen Lücke zwischen zwei Wunschliedern und verschwindet bei Shows, die der FPP selbst startet.
- `start_playlist()` entfernt den Code vor jedem Start und unterdrückt das Neuzeichnen für 8 s, bis der FPP „playing“ meldet.
- Nach einem Neustart oder einem Fehler gilt die Anzeige als „möglicherweise an“ und wird vor dem nächsten Start sicherheitshalber abgeschaltet.

**Zeichnen** (`code_matrix.py`): FPP beschreibt Matrizen oft anders, als sie gebaut sind. Deshalb:

1. Ziffern in einem 5×7-Raster so groß wie möglich und mittig auf die *echte* Größe zeichnen.
2. Jeden leuchtenden Punkt über die echte Verkabelung in eine Knotennummer umrechnen.
3. Die Knotennummer über FPPs eigene Modellbeschreibung in FPP-Koordinaten zurückrechnen.
4. Das Bild in einem Aufruf schreiben (`…/data`), ersatzweise Pixel für Pixel, und das Modell auf „enabled“ schalten.

`build_node_map()` bildet dafür die Zuordnung nach, die FPP in `PixelOverlayModel` verwendet (Stränge laufen innerhalb eines Strings im Zickzack, jeder String beginnt wieder an der Startseite).

---

## Musik im Browser (FalconBeat)

**Erkennung** (`falconbeat_worker`): Plugin installiert → Plugin aktiviert → Server antwortet auf `/health`. Das Ergebnis steht als `falconbeat.available` in `/api/state`.

**Wiedergabe** (`falconbeat-audio.js`), eine Portierung des FalconBeat-Listener-Clients ohne Abhängigkeiten:

1. Der Tipp auf „Musik hören“ entsperrt den Ton im Browser und öffnet `wss://<host>/falconbeat/ws`.
2. **Uhrenabgleich:** Paare von NTP-Anfragen mit 25 ms Abstand; Paare mit verfälschtem Abstand werden verworfen, aus 16 Messungen zählt die mit der kürzesten Laufzeit.
3. **Vorladen:** Der Server nennt die Audioquellen; der Client lädt sie von `/falconbeat/media/…`, dekodiert sie und meldet „geladen“.
4. **Abspielen:** Der Server sendet einen Startzeitpunkt in Server-Zeit; der Client plant den Start über die Web Audio API sample-genau ein und zieht die Ausgabe-Latenz ab.
5. Wer später dazukommt, fragt mit `SYNC` die aktuelle Position ab.

Das Backend ist an der Wiedergabe nicht beteiligt. Der Reverse Proxy reicht die beiden Pfade direkt an den FalconBeat-Server weiter ([deploy/README.md](deploy/README.md)).

---

## Sicherheit

| Thema | Umsetzung |
|---|---|
| Zugangscode | Prüfung nur auf dem Server (`POST /api/access` und bei jedem schreibenden Aufruf über `X-Access-Code`), Vergleich in konstanter Zeit, nie in `config.js` |
| Fehlversuche | 6 falsche Codes pro Adresse → 10 Minuten Sperre (`429`). Die Adresse ist der letzte Eintrag von `X-Forwarded-For`, also der vom eigenen Proxy gesetzte |
| Liedwünsche | Nur Titel aus der Wunsch-Playlist; Dateinamen kommen nie vom Browser |
| Faire Nutzung | Grenze pro Gerät und für die Warteschlange. Die Geräte-Kennung ist nicht fälschungssicher; die Obergrenze der Warteschlange fängt das ab |
| Ausgabe | Besucher- und FPP-Daten werden nur als Text eingefügt, nie als HTML |
| Dateien | Nur ausdrücklich freigegebene Dateien sind abrufbar, nicht das App-Verzeichnis |
| Header | Content-Security-Policy ohne Inline-Skripte, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, Referrer- und Permissions-Policy |
| Fremde Server | Keine. Der Browser lädt nichts von Dritten |
| Geheimnisse | Über `<VARIABLE>_FILE` aus Dateien lesbar (Docker Secrets) |

**Offen lesbar** sind `/api/state` und `/api/statistics`. Sie enthalten keine personenbezogenen Daten, zeigen aber, wann was lief.

---

## Betrieb

- **Start:** `gunicorn --workers 1 --threads 8 app:app` (im Dockerfile hinterlegt). Mehr als ein Worker oder mehrere Replikas würden Warteschlange, Zeitplan und Matrix-Anzeige vervielfachen.
- **Healthcheck:** Das Image prüft alle 30 s `/health`.
- **Logs:** Standardausgabe, z. B. `docker compose logs -f`. Nützliche Meldungen: `FalconBeat audio available / not available`, `Daily access code on model …`, `Access code could not be shown on the matrix`.
- **Daten:** `data/` einbinden, sonst gehen Statistik und Code-Geheimnis bei jedem Neustart verloren.
- **Last:** Jeder Besucher erzeugt eine kleine JSON-Abfrage alle 4–10 s. Zum FPP gehen unabhängig von der Besucherzahl nur die Abfragen der Hintergrund-Threads.

---

## Grenzen und Ausbaumöglichkeiten

- **Kein dauerhafter Zustand:** Ein Neustart leert die Warteschlange.
- **Eine Instanz pro FPP**, keine Skalierung über mehrere Prozesse. Dafür müsste der Zustand ausgelagert werden, etwa nach Redis.
- **Abfragen statt Push:** Die Oberfläche reagiert mit einigen Sekunden Verzögerung. Server-Sent Events würden das verkürzen.
- **Statistik als JSON-Datei:** Für die üblichen Mengen ausreichend; `STATISTICS_RETENTION_DAYS` begrenzt das Wachstum.
- **Keine automatischen Tests.**
