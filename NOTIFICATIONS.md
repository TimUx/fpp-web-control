# Benachrichtigungen – Setup-Beispiele

Dieses Dokument enthält Beispielkonfigurationen für verschiedene Benachrichtigungsmethoden.

## 🚀 Schnellstart mit ntfy.sh (Empfohlen für Einsteiger)

ntfy.sh ist die einfachste Methode, um Push-Benachrichtigungen auf dem Smartphone zu erhalten.

### Schritt 1: ntfy.sh App installieren
- **Android**: [Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- **iOS**: [App Store](https://apps.apple.com/us/app/ntfy/id1625396347)

### Schritt 2: Topic abonnieren
1. App öffnen
2. "+" antippen, um einen neuen Topic zu abonnieren
3. Einen eindeutigen Topic-Namen eingeben, z.B.: `meine-lichtershow-xyz123`
   - **Wichtig**: Wähle einen eindeutigen Namen, da ntfy.sh öffentlich ist!
   - Beispiel: `brauns-show-2024-geheim-abc123`

### Schritt 3: Konfiguration in `.env`
```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# ntfy.sh konfigurieren
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_URL=https://ntfy.sh
NOTIFY_NTFY_TOPIC=meine-lichtershow-xyz123
```

### Schritt 4: App neu starten
```bash
docker compose down
docker compose up -d
```

Fertig! Jetzt erhältst du Push-Benachrichtigungen auf deinem Handy, wenn jemand eine Show startet oder ein Lied wünscht.

### 💡 Hinweis: Funktioniert auch im Vorschau-Modus

Benachrichtigungen werden auch gesendet, wenn `PREVIEW_MODE=true` gesetzt ist. So kannst du das Benachrichtigungssystem testen, ohne einen echten FPP zu benötigen.

### ⚠️ Wichtig: DNS-Auflösung in Docker

Die `docker-compose.yml` ist bereits so konfiguriert, dass DNS-Auflösung funktioniert (Google DNS: 8.8.8.8, 8.8.4.4).

**Falls ntfy.sh trotzdem nicht erreichbar ist:**

1. **Container komplett neu bauen:**
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

2. **DNS im Container testen:**
   ```bash
   docker compose exec fpp-control nslookup ntfy.sh
   ```
   Sollte die IP-Adresse von ntfy.sh auflösen.

3. **Container-Logs prüfen:**
   ```bash
   docker compose logs -f fpp-control
   ```
   Suche nach "Failed to send ntfy notification" - der Fehler zeigt das Problem.

4. **Alternative DNS-Server:** Ändere in `docker-compose.yml` bei Bedarf die DNS-Server, z.B. auf deinen Router:
   ```yaml
   dns:
     - 192.168.1.1  # Dein Router
     - 8.8.8.8
   ```

---

## 🏠 Home Assistant mit MQTT

Wenn du Home Assistant mit MQTT-Broker verwendest, kannst du Benachrichtigungen direkt über Home Assistant senden.

### Voraussetzungen
- Home Assistant installiert
- MQTT-Broker läuft (z.B. Mosquitto-Add-on)
- Home Assistant Companion App auf dem Smartphone

### Schritt 1: MQTT-Broker-Details ermitteln
In Home Assistant: Einstellungen → Geräte & Dienste → MQTT
- IP-Adresse deines Home Assistant Servers (z.B. `192.168.1.100`)
- Port (Standard: `1883`)
- Benutzername und Passwort (falls konfiguriert)

### Schritt 2: Konfiguration in `.env`
```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# MQTT konfigurieren
NOTIFY_MQTT_ENABLED=true
NOTIFY_MQTT_BROKER=192.168.1.100
NOTIFY_MQTT_PORT=1883
NOTIFY_MQTT_USERNAME=mqtt-user
NOTIFY_MQTT_PASSWORD=dein-passwort
NOTIFY_MQTT_TOPIC=fpp-control/notifications
NOTIFY_MQTT_USE_TLS=false
```

### Schritt 3: Home Assistant Automation erstellen

In Home Assistant: Einstellungen → Automatisierungen & Szenen → Automation erstellen

**YAML-Modus** (Datei: `automations.yaml`):

```yaml
# Benachrichtigung bei Show-Start
- id: fpp_show_notification
  alias: "FPP Show Benachrichtigung"
  trigger:
    - platform: mqtt
      topic: "fpp-control/notifications"
  condition:
    - condition: template
      value_template: "{{ trigger.payload_json.action_type == 'show_start' }}"
  action:
    - service: notify.mobile_app_dein_handy
      data:
        title: "{{ trigger.payload_json.title }}"
        message: "{{ trigger.payload_json.message }}"
        data:
          priority: high
          ttl: 0
          
# Benachrichtigung bei Liedwunsch
- id: fpp_song_notification
  alias: "FPP Liedwunsch Benachrichtigung"
  trigger:
    - platform: mqtt
      topic: "fpp-control/notifications"
  condition:
    - condition: template
      value_template: "{{ trigger.payload_json.action_type == 'song_request' }}"
  action:
    - service: notify.mobile_app_dein_handy
      data:
        title: "{{ trigger.payload_json.title }}"
        message: "{{ trigger.payload_json.message }} - Position: {{ trigger.payload_json.queue_position }}"
        data:
          priority: normal
```

**Wichtig**: Ersetze `mobile_app_dein_handy` mit dem Namen deines Geräts in Home Assistant.
Den Namen findest du unter: Einstellungen → Geräte & Dienste → Mobile App → [Dein Gerät]

---

## 📱 Signal-Bot über Webhook

Signal-Benachrichtigungen können über den signal-cli REST API Server gesendet werden.

### Voraussetzungen
- [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) installiert
- Signal-Nummer registriert

### Konfiguration in `.env`
```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# Webhook für Signal konfigurieren
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=http://signal-api:8080/v2/send
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json"}
```

**Hinweis**: Du musst die Webhook-URL an die Signal-CLI-REST-API anpassen und ggf. das Payload-Format im Code anpassen.

---

## 🌐 Nextcloud Notifications

Nextcloud hat keine direkte Notification-API über Webhooks, aber du kannst Nextcloud Talk nutzen.

### Option 1: Nextcloud Talk Bot

1. Nextcloud Talk Raum erstellen
2. Bot-Account erstellen
3. Webhook in Nextcloud Talk-Raum generieren
4. In `.env` konfigurieren:

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-nextcloud.de/ocs/v2.php/apps/spreed/api/v1/bot/{token}/message
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json", "OCS-APIRequest": "true"}
```

---

## 🔗 WhatsApp Business API

WhatsApp-Benachrichtigungen erfordern einen WhatsApp Business Account und API-Zugang.

### Mit Meta WhatsApp Business API

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://graph.facebook.com/v17.0/PHONE_NUMBER_ID/messages
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Authorization": "Bearer DEIN_ACCESS_TOKEN", "Content-Type": "application/json"}
```

**Hinweis**: Das Payload-Format muss für WhatsApp angepasst werden. Dies erfordert Code-Änderungen.

---

## 🔧 Generischer Webhook

Für eigene Dienste oder APIs kannst du den generischen Webhook verwenden.

### Beispiel: POST-Request an eigene API
```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-api.de/notifications
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Authorization": "Bearer DEIN_TOKEN", "Content-Type": "application/json"}
```

### Beispiel: GET-Request
```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-api.de/notification
NOTIFY_WEBHOOK_METHOD=GET
```

### Payload-Format

Der Webhook sendet folgendes JSON-Payload:

```json
{
  "title": "🎄 Hauptshow gestartet",
  "message": "Ein Besucher hat 'show 1' gestartet.",
  "action_type": "show_start",
  "timestamp": "2024-12-06T19:30:00+01:00",
  "site_name": "Brauns Lichtershow",
  "playlist": "show 1",
  "playlist_type": "playlist1"
}
```

Für Liedwünsche:
```json
{
  "title": "🎵 Neuer Liedwunsch",
  "message": "Ein Besucher wünscht sich: 'Jingle Bells' (Dauer: 3:25)\nPosition in Warteschlange: 2",
  "action_type": "song_request",
  "timestamp": "2024-12-06T19:31:15+01:00",
  "site_name": "Brauns Lichtershow",
  "song_title": "Jingle Bells",
  "duration": 205,
  "queue_position": 2,
  "sequence_name": "jingle-bells.fseq",
  "media_name": "jingle-bells.mp3"
}
```

---

## 🔒 Sicherheitshinweise

1. **ntfy.sh**: Verwende eindeutige Topic-Namen! Jeder kann öffentliche Topics abonnieren.
   - Besser: Selbst gehostete ntfy.sh-Instanz mit Passwortschutz
   
2. **MQTT**: Aktiviere TLS und verwende starke Passwörter
   ```bash
   NOTIFY_MQTT_USE_TLS=true
   ```

3. **Webhooks**: Verwende HTTPS und API-Tokens

4. **Access Tokens**: Speichere Tokens niemals in öffentlichen Repositories!

---

## 🧪 Testen der Benachrichtigungen

Um zu testen, ob Benachrichtigungen funktionieren:

1. `.env` konfigurieren
2. App neu starten: `docker compose restart`
3. In der Web-App eine Aktion ausführen (z.B. Show starten)
4. Benachrichtigung sollte ankommen

### Fehlersuche

**Benachrichtigung kommt nicht an?**

1. Prüfe die Logs:
   ```bash
   docker compose logs -f fpp-control
   ```
   
2. Suche nach Fehlermeldungen wie:
   - `Failed to send MQTT notification`
   - `Failed to send ntfy notification`
   - `Failed to send webhook notification`

3. Prüfe die Konfiguration:
   - Ist `NOTIFY_ENABLED=true`?
   - Ist mindestens ein Service aktiviert?
   - Sind URLs und Tokens korrekt?

**MQTT verbindet nicht?**
- Prüfe Firewall-Einstellungen
- Teste MQTT-Verbindung mit einem Tool wie `mosquitto_pub`

**ntfy.sh funktioniert nicht?**
- Prüfe, ob der Topic-Name korrekt ist
- Teste manuell: `curl -d "Test" ntfy.sh/dein-topic`
- **DNS-Problem im Docker-Container?**
  - Die `docker-compose.yml` enthält bereits DNS-Server (8.8.8.8, 8.8.4.4)
  - Falls weiterhin Probleme: Container neu bauen: `docker compose down && docker compose up --build`
  - Teste DNS im Container: `docker compose exec fpp-control nslookup ntfy.sh`
  - Alternative: Verwende IP-Adresse statt Hostname (funktioniert aber nur bei eigener ntfy.sh-Instanz)

---

## 📋 Mehrere Methoden gleichzeitig

Du kannst mehrere Benachrichtigungsmethoden gleichzeitig aktivieren:

```bash
NOTIFY_ENABLED=true

# ntfy.sh für Push-Benachrichtigungen
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_TOPIC=meine-show-123

# MQTT für Home Assistant
NOTIFY_MQTT_ENABLED=true
NOTIFY_MQTT_BROKER=192.168.1.100
NOTIFY_MQTT_TOPIC=fpp-control/notifications

# Webhook für eigene Logging-API
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://meine-api.de/log
```

Alle aktivierten Methoden erhalten gleichzeitig die Benachrichtigung.
