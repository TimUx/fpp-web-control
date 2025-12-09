# 🏗️ Architektur-Dokumentation

Technische Dokumentation der FPP Web Control Architektur für Entwickler und fortgeschrittene Benutzer.

---

## Inhaltsverzeichnis

- [Übersicht](#übersicht)
- [Systemarchitektur](#systemarchitektur)
- [Komponenten-Beschreibung](#komponenten-beschreibung)
- [Datenflüsse](#datenflüsse)
- [State Management](#state-management)
- [FPP-API-Integration](#fpp-api-integration)
- [Benachrichtigungs-System](#benachrichtigungs-system)
- [Statistik-System](#statistik-system)
- [Sicherheit](#sicherheit)
- [Performance](#performance)

---

## Übersicht

FPP Web Control ist eine **serverseitig verwaltete Web-Applikation**, die als Proxy und Steuerungsschicht zwischen Besuchern und dem Falcon Player (FPP) fungiert.

### Kern-Prinzipien

1. **Server-Side State**: Alle Zustandsverwaltung erfolgt serverseitig
2. **API-Abstraktion**: Besucher kommunizieren nur mit Flask-API, nie direkt mit FPP
3. **Polling-Based**: Statusaktualisierungen via Polling (kein WebSocket)
4. **Stateless Frontend**: Client ist minimal und zustandslos
5. **Single Instance**: Eine App-Instanz pro FPP

### Technologie-Stack

**Backend:**
- **Python 3.11+**: Programmiersprache
- **Flask**: Web-Framework
- **Gunicorn**: WSGI HTTP Server (Produktion)
- **Requests**: HTTP-Client für FPP-API
- **paho-mqtt**: MQTT-Client (optional)

**Frontend:**
- **Vanilla JavaScript**: Keine Frameworks
- **HTML5/CSS3**: Responsive Design
- **Font Awesome**: Icons
- **Chart.js**: Statistik-Visualisierung

**Infrastruktur:**
- **Docker**: Containerisierung
- **Docker Compose**: Multi-Container-Management

---

## Systemarchitektur

### Deployment-Diagramm

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet / WAN                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Port Forwarding (z.B. 8080:8080)
                         │ DynDNS (optional)
                         │
              ┌──────────▼───────────┐
              │       Router         │
              │    (192.168.x.1)     │
              │  - Port Forwarding   │
              │  - Firewall Rules    │
              └──────────┬───────────┘
                         │
                         │ LAN
┌────────────────────────┴─────────────────────────────────────┐
│                    Lokales Netzwerk (LAN)                    │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Docker Host (Server/Raspberry Pi)         │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────┐     │  │
│  │  │      FPP Web Control Container               │     │  │
│  │  │                                              │     │  │
│  │  │  ┌────────────────────────────────────────┐ │     │  │
│  │  │  │         Gunicorn WSGI Server          │ │     │  │
│  │  │  │         (4 Worker Processes)          │ │     │  │
│  │  │  └───────────────┬────────────────────────┘ │     │  │
│  │  │                  │                          │     │  │
│  │  │  ┌───────────────▼────────────────────────┐ │     │  │
│  │  │  │          Flask Application            │ │     │  │
│  │  │  │                                       │ │     │  │
│  │  │  │  ┌─────────────────────────────────┐ │ │     │  │
│  │  │  │  │   REST API Endpoints            │ │ │     │  │
│  │  │  │  │  - /api/state                   │ │ │     │  │
│  │  │  │  │  - /api/show                    │ │ │     │  │
│  │  │  │  │  - /api/requests/songs          │ │ │     │  │
│  │  │  │  │  - /api/requests                │ │ │     │  │
│  │  │  │  │  - /api/statistics              │ │ │     │  │
│  │  │  │  └─────────────────────────────────┘ │ │     │  │
│  │  │  │                                       │ │     │  │
│  │  │  │  ┌─────────────────────────────────┐ │ │     │  │
│  │  │  │  │   Background Threads            │ │ │     │  │
│  │  │  │  │  - Status Poller (15s)          │ │ │     │  │
│  │  │  │  │  - Queue Manager                │ │ │     │  │
│  │  │  │  │  - Scheduler                    │ │ │     │  │
│  │  │  │  └─────────────────────────────────┘ │ │     │  │
│  │  │  │                                       │ │     │  │
│  │  │  │  ┌─────────────────────────────────┐ │ │     │  │
│  │  │  │  │   State Management              │ │ │     │  │
│  │  │  │  │  - In-Memory State Dict         │ │ │     │  │
│  │  │  │  │  - Threading Locks              │ │ │     │  │
│  │  │  │  └─────────────────────────────────┘ │ │     │  │
│  │  │  │                                       │ │     │  │
│  │  │  │  ┌─────────────────────────────────┐ │ │     │  │
│  │  │  │  │   FPP API Client                │ │ │     │  │
│  │  │  │  │  - HTTP Requests Library        │ │ │     │  │
│  │  │  │  │  - Timeout: 8s                  │ │ │     │  │
│  │  │  │  └─────────────────────────────────┘ │ │     │  │
│  │  │  │                                       │ │     │  │
│  │  │  │  ┌─────────────────────────────────┐ │ │     │  │
│  │  │  │  │   Notification System           │ │ │     │  │
│  │  │  │  │  - MQTT Client                  │ │ │     │  │
│  │  │  │  │  - HTTP Webhooks                │ │ │     │  │
│  │  │  │  └─────────────────────────────────┘ │ │     │  │
│  │  │  └───────────────────────────────────────┘ │     │  │
│  │  │                                            │     │  │
│  │  │  ┌─────────────────────────────────────┐  │     │  │
│  │  │  │     Static File Server             │  │     │  │
│  │  │  │  - index.html                      │  │     │  │
│  │  │  │  - requests.html                   │  │     │  │
│  │  │  │  - donation.html                   │  │     │  │
│  │  │  │  - statistics.html                 │  │     │  │
│  │  │  │  - styles.css                      │  │     │  │
│  │  │  │  - config.js (generiert)           │  │     │  │
│  │  │  └─────────────────────────────────────┘  │     │  │
│  │  │                                            │     │  │
│  │  │  Volume: /app/data (persistent)           │     │  │
│  │  │    └─ statistics.json                     │     │  │
│  │  │                                            │     │  │
│  │  │  Port: 8000 (intern) → 8080 (extern)      │     │  │
│  │  └────────────────────────────────────────────┘     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Falcon Player (FPP)                       │  │
│  │              192.168.x.x or fpp.local                  │  │
│  │                                                        │  │
│  │  REST API:                                            │  │
│  │    - /api/fppd/status                                 │  │
│  │    - /api/playlist/:name                              │  │
│  │    - /api/playlist/:name/start                        │  │
│  │    - /api/playlists/stop                              │  │
│  │    - /api/command/*                                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Optional: MQTT Broker / Home Assistant          │  │
│  │       (für Benachrichtigungen)                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘

External Services (über Internet):
┌────────────────────────────────────────────────────────────┐
│  - ntfy.sh (Push-Benachrichtigungen)                       │
│  - Home Assistant Cloud (optional)                         │
│  - Eigene Webhook-Endpunkte                                │
└────────────────────────────────────────────────────────────┘
```

---

## Komponenten-Beschreibung

### 1. Flask Application (app.py)

Haupt-Backend-Komponente mit ca. 1200 Zeilen Code.

#### Struktur

```python
# Imports & Konfiguration
import flask, requests, threading, ...
SITE_NAME = os.getenv("SITE_NAME", "...")
...

# MQTT-Client (optional)
if MQTT_AVAILABLE and NOTIFY_MQTT_ENABLED:
    mqtt_client = mqtt.Client()
    mqtt_client.connect(...)

# State Management
state = {
    "queue": [],
    "current_request": None,
    "scheduled_show_active": False,
    "last_status": {},
    ...
}

# Notification System
def send_notification(title, message, action_type, extra_data):
    # Multi-Channel: MQTT, ntfy.sh, HA, Webhook
    ...

# Statistics System
def load_statistics() -> Dict:
    # JSON-basierte Persistenz
    ...

def save_statistics(stats: Dict):
    # Atomic Write
    ...

# FPP API Client
def fpp_get(endpoint: str) -> Dict:
    # Mit Timeout und Error Handling
    ...

# Background Threads
def status_poller_thread():
    # Pollt FPP-Status alle X Sekunden
    ...

def queue_worker_thread():
    # Verarbeitet Liedwunsch-Queue
    ...

# Flask Routes
@app.route("/api/state")
def api_state():
    # Gibt aktuellen State zurück
    ...

@app.route("/api/show", methods=["POST"])
def api_show():
    # Startet Playlist
    ...

# Static File Server
@app.route("/")
def serve_index():
    return send_from_directory(".", "index.html")

# Startup
if __name__ == "__main__":
    # Start Background Threads
    threading.Thread(target=status_poller_thread, daemon=True).start()
    threading.Thread(target=queue_worker_thread, daemon=True).start()
    
    # Start Flask
    app.run(host="0.0.0.0", port=5000)
```

#### Verantwortlichkeiten

- **REST-API bereitstellen**: Endpunkte für Frontend
- **FPP-Kommunikation**: API-Calls zum Falcon Player
- **State Management**: Zentrale Zustandsverwaltung
- **Queue Management**: Liedwunsch-Warteschlange
- **Scheduling**: Automatische Show-Starts
- **Benachrichtigungen**: Multi-Channel-Versand
- **Statistiken**: Event-Logging und Persistenz
- **Static Files**: HTML/CSS/JS ausliefern

### 2. Status Poller (Background Thread)

```python
def status_poller_thread():
    """
    Pollt FPP-Status alle POLL_INTERVAL_SECONDS Sekunden.
    Aktualisiert globalen State mit FPP-Status.
    """
    while True:
        try:
            with state_lock:
                # FPP Status abrufen
                fpp_status = fpp_get("/api/fppd/status")
                
                # State aktualisieren
                state["last_status"] = fpp_status
                
                # Scheduler-Logik
                if SCHEDULED_SHOWS_ENABLED:
                    check_and_start_scheduled_show()
                
                # Idle-Modus-Prüfung
                if should_start_background():
                    start_background_playlist()
                    
        except Exception as e:
            logger.error(f"Status polling failed: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)
```

**Aufgaben:**
- Regelmäßige FPP-Status-Abfrage
- State-Aktualisierung
- Scheduler-Trigger
- Idle-Modus-Management

### 3. Queue Worker (Background Thread)

```python
def queue_worker_thread():
    """
    Verarbeitet Liedwunsch-Warteschlange.
    Startet nächsten Song, wenn vorheriger beendet.
    """
    while True:
        try:
            with state_lock:
                # Aktuellen Wunsch prüfen
                if state["current_request"]:
                    # Ist Song beendet?
                    if is_request_finished():
                        state["current_request"] = None
                
                # Nächsten aus Queue starten
                if not state["current_request"] and state["queue"]:
                    next_request = state["queue"].pop(0)
                    start_request(next_request)
                    state["current_request"] = next_request
                    
                # Idle nach letztem Wunsch
                elif not state["current_request"] and not state["queue"]:
                    start_background_if_needed()
                    
        except Exception as e:
            logger.error(f"Queue worker failed: {e}")
        
        time.sleep(5)  # Check alle 5 Sekunden
```

**Aufgaben:**
- Queue-Abarbeitung
- Song-Start/-Ende-Erkennung
- Idle-Playlist-Start nach Queue-Ende

### 4. Frontend (HTML/JS)

Vier separate HTML-Seiten mit gemeinsamen CSS.

#### index.html - Hauptseite

```javascript
// Polling-basiertes Status-Update
setInterval(async () => {
    const response = await fetch('/api/state');
    const data = await response.json();
    
    // UI aktualisieren
    updateStatus(data);
    updateQueue(data);
    updateButtons(data);
    updateCountdown(data);
}, CLIENT_STATUS_POLL_MS);

// Button-Handler
document.getElementById('btn-show').addEventListener('click', async () => {
    await fetch('/api/show', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type: 'show'})
    });
});
```

**Features:**
- Status-Polling alle X Sekunden
- Button-Steuerung (Playlists, Liedwünsche, Spenden)
- Countdown-Anzeige
- Queue-Anzeige
- Zugangscode-Schutz

#### requests.html - Liedwunsch-Seite

```javascript
// Songliste laden
const response = await fetch('/api/requests/songs');
const songs = await response.json();

// Song-Buttons generieren
songs.forEach(song => {
    const button = createSongButton(song);
    button.addEventListener('click', async () => {
        await fetch('/api/requests', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(song)
        });
    });
});
```

**Features:**
- Dynamische Songliste aus FPP
- Liedwunsch-Buttons mit Dauer-Anzeige
- Queue-Status
- "Zurück"-Navigation

#### donation.html - Spendenseite

```javascript
// Config laden
const config = window.FPP_CONFIG || {};

// PayPal Link generieren
if (config.donationPoolId) {
    const paypalLink = `https://paypal.me/pools/c/${config.donationPoolId}`;
    createDonationButton(paypalLink);
}

// Buy Me a Coffee Button
if (config.buymeacoffeeUsername) {
    const bmcLink = `https://www.buymeacoffee.com/${config.buymeacoffeeUsername}`;
    createBMCButton(bmcLink);
}
```

**Features:**
- PayPal Pool Integration
- Buy Me a Coffee Button (optional)
- Social Media Footer
- Anpassbare Texte

#### statistics.html - Statistikseite

```javascript
// Statistiken laden
const response = await fetch('/api/statistics');
const stats = await response.json();

// Charts mit Chart.js
createShowStartsChart(stats.show_starts);
createSongRequestsChart(stats.song_requests);
createTimelineChart(stats);
createTopListsChart(stats);
```

**Features:**
- Interaktive Charts (Chart.js)
- Top-5-Listen
- Zeitverlauf-Diagramme
- Gesamtzahlen und Durchschnitte

### 5. Configuration System

Zwei-Schicht-Konfiguration:

#### docker-entrypoint.sh

```bash
#!/bin/bash
# Generiert config.js aus Umgebungsvariablen

cat > /app/config.js << EOF
window.FPP_CONFIG = {
  "siteName": "${SITE_NAME}",
  "siteSubtitle": "${SITE_SUBTITLE}",
  "accessCode": "${ACCESS_CODE}",
  "clientStatusPollMs": ${CLIENT_STATUS_POLL_MS:-10000},
  "donationPoolId": "${DONATION_POOL_ID}",
  ...
};
EOF

# Start Gunicorn
exec gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

**Zweck**: Umgebungsvariablen aus `.env` in JavaScript-Config umwandeln.

#### .env → Backend

```python
SITE_NAME = os.getenv("SITE_NAME", "FPP Lichtershow")
FPP_BASE_URL = os.getenv("FPP_BASE_URL", "http://fpp.local")
...
```

**Zweck**: Backend-Konfiguration zur Laufzeit.

---

## Datenflüsse

### 1. Show-Start durch Besucher

```
┌─────────┐
│ Browser │
└────┬────┘
     │ 1. POST /api/show {"type": "show"}
     │
┌────▼────────────┐
│  Flask API      │
└────┬────────────┘
     │ 2. Statistik loggen (show_start)
     ├─────────────────────────┐
     │                         │
     │                    ┌────▼─────────┐
     │                    │ Statistics   │
     │                    │ (JSON)       │
     │                    └──────────────┘
     │
     │ 3. Benachrichtigung senden
     ├────────────┬────────────┬──────────┐
     │            │            │          │
┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌───▼────┐
│ MQTT    │ │ ntfy.sh │ │   HA    │ │Webhook │
└─────────┘ └─────────┘ └─────────┘ └────────┘
     │
     │ 4. Prüfe: Läuft aktuell etwas?
     ├─────► if queue oder request: pausiere
     │       if show läuft: stoppe
     │
     │ 5. FPP API: Stop Playlist
     ├──────────────────────────────┐
     │                              │
     │                         ┌────▼────┐
     │                         │   FPP   │
     │                         └────┬────┘
     │                              │
     │ 6. FPP API: Start Playlist   │
     ├──────────────────────────────┤
     │                              │
     │ 7. State aktualisieren       │
     │    - scheduled_show_active = true
     │    - queue pausiert
     │
┌────▼────────────┐
│ Global State    │
└─────────────────┘
     │
     │ 8. Response {"status": "ok"}
     │
┌────▼────┐
│ Browser │
└─────────┘
```

### 2. Liedwunsch durch Besucher

```
┌─────────┐
│ Browser │
└────┬────┘
     │ 1. GET /api/requests/songs
     │
┌────▼────────────┐
│  Flask API      │
└────┬────────────┘
     │ 2. FPP API: GET /api/playlist/:name
     │
┌────▼────────────┐
│      FPP        │
└────┬────────────┘
     │ 3. Response: [{title, duration, ...}]
     │
┌────▼────────────┐
│  Flask API      │
└────┬────────────┘
     │ 4. Parse und formatiere Songs
     │
┌────▼────┐
│ Browser │ 5. Benutzer wählt Song
└────┬────┘
     │ 6. POST /api/requests {song: "...", ...}
     │
┌────▼────────────┐
│  Flask API      │
└────┬────────────┘
     │ 7. Statistik loggen (song_request)
     │ 8. Benachrichtigung senden
     │ 9. Zur Queue hinzufügen
     │
┌────▼────────────┐
│ Global State    │
│  queue.push()   │
└────┬────────────┘
     │
     │ Queue Worker Thread (parallel)
     │
     │ 10. Ist Queue leer? Ja → Sofort starten
     ├────────────────────────────────┐
     │                                │
     │ 11. FPP API: StopEffects       │
     ├────────────────────────────────┤
     │                                │
     │ 12. FPP API: DisableOutputs    │
     ├────────────────────────────────┤
     │                                │
     │ 13. FPP API: Stop Playlist     │
     ├────────────────────────────────┤
     │                                │
     │ 14. FPP API: Start Playlist    │
     │     (mit einzelnem Song)       │
     ├────────────────────────────────┤
     │                                │
┌────▼────────────┐              ┌───▼────┐
│ Global State    │              │  FPP   │
│ current_request │              └────────┘
└─────────────────┘
```

### 3. Automatischer Show-Start (Scheduler)

```
┌──────────────────────┐
│ Status Poller Thread │ (läuft alle 15s)
└──────┬───────────────┘
       │
       │ 1. Prüfe Zeit: Ist es volle Stunde?
       │    Prüfe: Innerhalb Show-Zeiten?
       │    Prüfe: SCHEDULED_SHOWS_ENABLED?
       │
       ├─ Ja → Show starten
       │
       │ 2. Prüfe: Läuft aktuell Wunsch?
       ├─────► Ja: Pausiere Wunsch
       │       - FPP API: Stop Playlist
       │       - State: paused_request = current_request
       │       - State: current_request = None
       │
       │ 3. FPP API: Start Playlist (z.B. "show 1")
       │
┌──────▼──────┐
│    FPP      │
└──────┬──────┘
       │
       │ 4. Show läuft...
       │
       │ 5. Status Poller erkennt: Show beendet
       │
┌──────▼──────────────┐
│ Status Poller       │
└──────┬──────────────┘
       │
       │ 6. War Wunsch pausiert?
       ├─────► Ja: Fortsetzen
       │       - FPP API: Start Playlist (paused_request)
       │       - State: current_request = paused_request
       │       - State: paused_request = None
       │
       │ 7. State aktualisieren
       │    - scheduled_show_active = false
       │
┌──────▼──────────────┐
│   Global State      │
└─────────────────────┘
```

---

## State Management

### Globaler State

```python
state = {
    # Liedwunsch-Queue
    "queue": [
        {
            "song": "Jingle Bells",
            "sequenceName": "jingle-bells.fseq",
            "mediaName": "jingle-bells.mp3",
            "duration": 185
        },
        ...
    ],
    
    # Aktueller Liedwunsch
    "current_request": {
        "song": "Silent Night",
        "sequenceName": "silent-night.fseq",
        "duration": 205,
        "started_at": "2024-12-24T18:05:00"
    } or None,
    
    # Pausierter Wunsch (bei scheduled show)
    "paused_request": {...} or None,
    
    # Scheduled Show läuft?
    "scheduled_show_active": False,
    
    # Letzter FPP-Status
    "last_status": {
        "status_name": "playing",
        "current_playlist": {
            "playlist": "show 1",
            "description": "Hauptshow",
            ...
        },
        "current_sequence": "sequence-01.fseq",
        "seconds_played": 45,
        "seconds_remaining": 135,
        ...
    },
    
    # Nächste geplante Show
    "next_show": "2024-12-24T19:00:00",
    
    # Hinweistext für UI
    "note": "Nächste Show um 19:00 Uhr",
    
    # Background läuft?
    "background_active": True,
}
```

### Thread-Safety

```python
import threading

# RLock erlaubt rekursive Locks (ein Thread kann mehrfach locken)
state_lock = threading.RLock()

# Jeder State-Zugriff muss gelockt werden
with state_lock:
    state["queue"].append(new_request)
    current = state["current_request"]
```

**Warum RLock?**
- Erlaubt verschachtelte Locks im selben Thread
- Verhindert Deadlocks bei rekursiven Funktionsaufrufen

### State-Aktualisierung

**Status Poller** (15s-Intervall):
- Aktualisiert `last_status`
- Berechnet `next_show`
- Setzt `scheduled_show_active`

**Queue Worker** (5s-Intervall):
- Verarbeitet `queue`
- Aktualisiert `current_request`
- Setzt `background_active`

**API-Endpunkte** (on-demand):
- Modifizieren `queue`
- Starten Shows (→ `scheduled_show_active`)

---

## FPP-API-Integration

### Verwendete Endpunkte

#### 1. Status-Abfrage

```python
GET /api/fppd/status

Response:
{
  "status_name": "idle" | "playing" | "stopped",
  "current_playlist": {
    "playlist": "show 1",
    "description": "Hauptshow",
    "repeat": 0,
    "loop": 0,
    ...
  },
  "current_sequence": "sequence-01.fseq",
  "current_song": "Jingle Bells.mp3",
  "seconds_played": 45,
  "seconds_remaining": 135,
  "time_elapsed": "00:45",
  "time_remaining": "02:15",
  "scheduler": {
    "enabled": 1,
    "status": "idle",
    "currentPlaylist": {...},
    "nextPlaylist": {...},
    ...
  },
  ...
}
```

**Verwendung**: Status Poller (alle 15s)

#### 2. Playlist-Details

```python
GET /api/playlist/wishlist

Response:
{
  "name": "wishlist",
  "desc": "Alle Lieder zum Wünschen",
  "playlistInfo": {
    "total_duration": 3600,
    "total_items": 20,
    ...
  },
  "mainPlaylist": [
    {
      "type": "sequence",
      "enabled": 1,
      "playOnce": 0,
      "sequenceName": "jingle-bells.fseq",
      "mediaName": "jingle-bells.mp3",
      "duration": 185,
      ...
    },
    ...
  ],
  "leadIn": [],
  "leadOut": []
}
```

**Verwendung**: Liedwunsch-Seite (on-demand)

#### 3. Playlist starten

**Methode 1** (neuere FPP-Versionen):
```python
GET /api/playlist/show%201/start

Response:
{
  "Status": "OK",
  "Message": "Playlist 'show 1' starting"
}
```

**Methode 2** (ältere FPP-Versionen, Fallback):
```python
POST /api/command
{
  "command": "Start Playlist",
  "args": ["show 1"]
}
```

**Verwendung**: Show-Start, Liedwunsch-Start

#### 4. Playlist stoppen

```python
GET /api/playlists/stop

Response:
{
  "Status": "OK"
}
```

**Fallback**:
```python
GET /api/command/Stop%20Playlist
```

**Verwendung**: Vor Show-Start, vor Liedwunsch

#### 5. Effekte stoppen

```python
GET /api/command/StopEffects

Response:
{
  "Status": "OK"
}
```

**Verwendung**: Vor Liedwunsch-Start

#### 6. Ausgänge deaktivieren

```python
GET /api/command/DisableOutputs

Response:
{
  "Status": "OK"
}
```

**Verwendung**: Vor Liedwunsch-Start (für sauberen Übergang)

### Error Handling

```python
def fpp_get(endpoint: str, timeout: int = REQUEST_TIMEOUT) -> Dict:
    """
    FPP API GET Request mit Error Handling.
    """
    try:
        url = f"{FPP_BASE_URL}{endpoint}"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"FPP timeout for {endpoint}")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError:
        logger.error(f"FPP connection error for {endpoint}")
        return {"error": "connection"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"FPP HTTP error {e.response.status_code} for {endpoint}")
        return {"error": f"http_{e.response.status_code}"}
    except Exception as e:
        logger.error(f"FPP unexpected error for {endpoint}: {e}")
        return {"error": "unknown"}
```

**Timeouts:**
- Standard: 8 Sekunden
- Status-Polling: 8 Sekunden
- Playlist-Start: 8 Sekunden

**Fallback bei Fehler:**
- Preview-Mode: Dummy-Daten
- Produktion: Fehler loggen, State beibehalten

---

## Benachrichtigungs-System

### Architektur

```python
def send_notification(
    title: str,
    message: str,
    action_type: str = "info",
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Multi-Channel Notification System.
    Sendet parallel an alle aktivierten Kanäle.
    """
    if not NOTIFY_ENABLED:
        return
    
    # Payload zusammenstellen
    payload = {
        "title": title,
        "message": message,
        "action_type": action_type,  # show_start, song_request
        "timestamp": datetime.now().isoformat(),
        "site_name": SITE_NAME,
    }
    if extra_data:
        payload.update(extra_data)
    
    # Parallel an alle Kanäle senden
    # (jeder Kanal unabhängig, Fehler beeinflussen sich nicht)
    
    if NOTIFY_MQTT_ENABLED:
        send_mqtt_notification(payload)
    
    if NOTIFY_NTFY_ENABLED:
        send_ntfy_notification(title, message)
    
    if NOTIFY_HOMEASSISTANT_ENABLED:
        send_ha_notification(payload)
    
    if NOTIFY_WEBHOOK_ENABLED:
        send_webhook_notification(payload)
```

### Notification-Channels

#### 1. MQTT

```python
def send_mqtt_notification(payload: Dict) -> None:
    """
    Sendet Benachrichtigung via MQTT.
    Für Home Assistant Integration.
    """
    try:
        mqtt_payload = json.dumps(payload, ensure_ascii=False)
        result = mqtt_client.publish(
            NOTIFY_MQTT_TOPIC,
            mqtt_payload,
            qos=1,        # At least once delivery
            retain=False  # Nicht persistent
        )
        if result.rc != 0:
            logger.error(f"MQTT publish failed: {result.rc}")
    except Exception as e:
        logger.error(f"MQTT notification failed: {e}")
```

**QoS 1**: At least once delivery - wichtig für kritische Benachrichtigungen

#### 2. ntfy.sh

```python
def send_ntfy_notification(title: str, message: str) -> None:
    """
    Sendet Push-Benachrichtigung via ntfy.sh.
    Einfachste Methode für Endbenutzer.
    """
    try:
        url = f"{NOTIFY_NTFY_URL}/{NOTIFY_NTFY_TOPIC}"
        headers = {
            "Title": title,
            "Priority": "default",
            "Tags": action_type  # Emoji-Tag
        }
        if NOTIFY_NTFY_TOKEN:
            headers["Authorization"] = f"Bearer {NOTIFY_NTFY_TOKEN}"
        
        response = requests.post(
            url,
            data=message.encode('utf-8'),  # Plain text body
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(f"ntfy notification failed: {e}")
```

**Hinweis**: ntfy.sh erwartet Plain-Text-Body, nicht JSON!

#### 3. Home Assistant Webhook

```python
def send_ha_notification(payload: Dict) -> None:
    """
    Sendet Benachrichtigung an HA Webhook.
    Direktintegration ohne MQTT.
    """
    try:
        headers = {
            "Authorization": f"Bearer {NOTIFY_HOMEASSISTANT_TOKEN}",
            "Content-Type": "application/json"
        }
        ha_payload = {
            "title": payload["title"],
            "message": payload["message"],
            "data": payload  # Komplettes Payload als data
        }
        response = requests.post(
            NOTIFY_HOMEASSISTANT_URL,
            json=ha_payload,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(f"HA notification failed: {e}")
```

#### 4. Generischer Webhook

```python
def send_webhook_notification(payload: Dict) -> None:
    """
    Sendet Benachrichtigung an generischen Webhook.
    Für eigene Integrationen.
    """
    try:
        headers = {"Content-Type": "application/json"}
        if NOTIFY_WEBHOOK_HEADERS:
            custom_headers = json.loads(NOTIFY_WEBHOOK_HEADERS)
            headers.update(custom_headers)
        
        if NOTIFY_WEBHOOK_METHOD == "GET":
            requests.get(
                NOTIFY_WEBHOOK_URL,
                params=payload,
                headers=headers,
                timeout=5
            )
        else:  # POST
            requests.post(
                NOTIFY_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=5
            )
    except Exception as e:
        logger.error(f"Webhook notification failed: {e}")
```

---

## Statistik-System

### Datenmodell

```python
statistics = {
    "show_starts": [
        {
            "timestamp": "2024-12-24T18:00:00+01:00",
            "playlist": "show 1",
            "playlist_type": "playlist1"  # or "playlist2"
        },
        ...
    ],
    "song_requests": [
        {
            "timestamp": "2024-12-24T18:05:15+01:00",
            "song_title": "Jingle Bells",
            "duration": 185,
            "sequence_name": "jingle-bells.fseq",
            "media_name": "jingle-bells.mp3"
        },
        ...
    ]
}
```

### Persistenz

```python
# Atomic Write Pattern
def save_statistics(stats: Dict[str, Any]) -> None:
    """
    Speichert Statistiken atomar.
    Vermeidet korrupte Dateien bei Absturz.
    """
    try:
        # 1. In temporäre Datei schreiben
        temp_file = STATISTICS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 2. Atomar umbenennen (atomic operation)
        os.replace(temp_file, STATISTICS_FILE)
    except Exception as e:
        logger.error(f"Failed to save statistics: {e}")
```

**Warum Atomic Write?**
- Bei Absturz während des Schreibens bleibt alte Datei intakt
- `os.replace()` ist atomar auf POSIX-Systemen

### Performance-Überlegungen

**Aktuell**: Schreibe sofort bei jedem Event
- **Pro**: Kein Datenverlust bei Absturz
- **Contra**: I/O bei jedem Event

**Für hohe Last**: Write-Buffer implementieren
```python
# Puffere Events im RAM
event_buffer = []

# Schreibe alle 60 Sekunden oder bei 100 Events
if len(event_buffer) >= 100 or (time.time() - last_write) > 60:
    save_statistics_batch(event_buffer)
    event_buffer = []
```

---

## Sicherheit

### 1. Zugangscode-Schutz

```python
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()

@app.route("/api/verify-code", methods=["POST"])
def api_verify_code():
    """
    Prüft Zugangscode.
    Bei leerem ACCESS_CODE: Immer erlaubt.
    """
    if not ACCESS_CODE:
        return jsonify({"valid": True})
    
    data = request.get_json() or {}
    code = str(data.get("code", "")).strip()
    
    return jsonify({"valid": code == ACCESS_CODE})
```

**Client-Side:**
```javascript
// Bei leerem ACCESS_CODE: Sofort Zugriff
if (!config.accessCode) {
    showMainContent();
} else {
    showAccessGate();
}
```

**Sicherheitshinweise:**
- Nur Basisschutz gegen zufällige Besucher
- Für echten Schutz: Reverse Proxy mit Auth (Nginx, Caddy)
- HTTPS für Produktivbetrieb empfohlen

### 2. API-Abstraktion

**Besucher → FPP**: NICHT möglich
**Besucher → Web Control → FPP**: Möglich

**Vorteile:**
- Kein direkter FPP-Zugriff für Besucher
- Zusätzliche Validierung möglich
- Rate-Limiting serverseitig implementierbar
- Logging aller Aktionen

### 3. Input-Validierung

```python
@app.route("/api/show", methods=["POST"])
def api_show():
    """
    Startet Playlist mit Input-Validierung.
    """
    data = request.get_json() or {}
    show_type = data.get("type", "")
    
    # Validierung
    if show_type not in ["show", "kids"]:
        return jsonify({"error": "Invalid show type"}), 400
    
    # Weitere Prüfungen
    if is_outside_show_window():
        return jsonify({"error": "Outside show hours"}), 403
    
    # ...
```

### 4. Error Handling

**Nie sensitive Infos im Response:**
```python
try:
    result = fpp_get("/api/fppd/status")
except Exception as e:
    # Interne Logs
    logger.error(f"FPP error: {e}")
    
    # Public Response (kein Stack Trace!)
    return jsonify({"error": "Service temporarily unavailable"}), 503
```

### 5. CORS

Aktuell: **Keine CORS-Beschränkung** (selber Host)

Für Multi-Domain-Setup:
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://deine-domain.com"])
```

---

## Performance

### Aktuelle Metriken (Schätzung)

**Hinweis**: Die folgenden Werte sind Schätzungen basierend auf typischem Betrieb. Für Produktionsumgebungen sollten tatsächliche Messungen durchgeführt werden (z.B. mit `docker stats`, Prometheus, etc.).

**Server:**
- CPU: < 5% (Idle), < 20% (Peak)
- RAM: ~100-200 MB
- Disk: < 1 MB (ohne Statistiken)

**Network:**
- FPP-Polling: ~1 KB/15s = ~0.07 KB/s
- Client-Polling: ~2 KB/10s pro Client
- 10 Clients: ~2 KB/s

**Latenz:**
- API Response: < 100ms (LAN)
- FPP API Call: 50-200ms (LAN)

### Skalierung

**Gunicorn Workers**: 4 (Standard)
```bash
# In docker-entrypoint.sh
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

**Worker-Formel:**
```
workers = (2 * CPU_CORES) + 1
```

Für Raspberry Pi (4 Kerne): 4 Workers OK

**Load Balancing**:
- Aktuell: Single-Instance
- Bei Bedarf: Nginx Reverse Proxy mit mehreren Instanzen

**Caching**:
```python
# Aktuell: In-Memory-State (state dict)
# Bei Bedarf: Redis für Multi-Instance-Setup

import redis
redis_client = redis.Redis(host='redis', port=6379)
```

### Optimierungspotenzial

1. **FPP-Polling**: Intervall erhöhen (15s → 30s)
2. **Client-Polling**: Intervall erhöhen (10s → 20s)
3. **Statistics**: Batch-Write statt sofortiger Save
4. **Caching**: Redis für Multi-Instance
5. **WebSocket**: Ersetze Polling durch Push (komplexer, aber effizienter)

---

## Wartung & Monitoring

### Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Logs in Docker
# docker compose logs -f fpp-control
```

**Log-Levels:**
- `INFO`: Normal operations (Show start, song request, notifications)
- `WARNING`: Recoverable issues (FPP timeout, retries)
- `ERROR`: Failures (FPP unreachable, notification failed)

### Health Checks

Aktuell: **Keine Health-Check-Route**

Empfohlen für Produktion:
```python
@app.route("/health")
def health():
    """
    Health check für Load Balancer / Monitoring.
    """
    fpp_ok = check_fpp_connection()
    
    return jsonify({
        "status": "healthy" if fpp_ok else "degraded",
        "fpp_reachable": fpp_ok,
        "uptime": get_uptime()
    }), 200 if fpp_ok else 503
```

### Metriken

Empfohlen für Monitoring:
- **Prometheus**: Metriken-Export
- **Grafana**: Dashboards
- **Alertmanager**: Benachrichtigungen bei Problemen

```python
# Beispiel: prometheus_flask_exporter
from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics(app)
```

---

**Ende der Architektur-Dokumentation**
