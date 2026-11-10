# 🔔 Benachrichtigungen - Komplett-Anleitung

Erhalte Push-Benachrichtigungen auf dein Smartphone, wenn Besucher deine Lichtershow steuern!

FPP Web Control kann dich automatisch benachrichtigen, wenn:
- 🎄 Ein Besucher eine Show startet
- 🎵 Ein Besucher ein Lied wünscht

---

> **Wo werden die Einstellungen gesetzt?**
> Die Beispiele in dieser Anleitung zeigen Umgebungsvariablen (`NOTIFY_…`). Jede davon lässt sich
> auf drei Wegen setzen:
>
> - in **`config/config.json`** unter dem entsprechenden Schlüssel in camelCase, z. B.
>   `NOTIFY_NTFY_TOPIC` → `"notifyNtfyTopic"`, `NOTIFY_MQTT_USE_TLS` → `"notifyMqttUseTls"`,
> - als **Umgebungsvariable** des Containers (`environment:` oder `env_file:` in der
>   Compose-Datei; die mitgelieferte `docker-compose.yml` lädt `.env`, in `docker-stack.yml`
>   stehen die Variablen direkt in der Datei),
> - als **Docker Secret** über `<VARIABLE>_FILE`, z. B. `NOTIFY_NTFY_TOKEN_FILE=/run/secrets/ntfy_token`.
>
> Ein Wert in `config.json` hat Vorrang. Änderungen wirken nach einem Neustart des Containers.
> Im Vorschau-Modus werden keine Benachrichtigungen versendet.

---

## 📖 Inhaltsverzeichnis

- [Übersicht](#-übersicht)
- [Schnellstart mit ntfy.sh](#-schnellstart-mit-ntfysh-empfohlen)
- [Home Assistant Integration](#-home-assistant-integration)
- [Weitere Benachrichtigungsmethoden](#-weitere-benachrichtigungsmethoden)
- [Payload-Format](#-payload-format)
- [Fehlersuche](#-fehlersuche)
- [Mehrere Methoden gleichzeitig](#-mehrere-methoden-gleichzeitig)

---

## 🎯 Übersicht

### Unterstützte Benachrichtigungsmethoden

| Methode | Schwierigkeit | Vorteile | Nachteile |
|---------|--------------|----------|-----------|
| **ntfy.sh** | ⭐ Sehr einfach | Keine Registrierung, sofort einsetzbar | Öffentlicher Dienst (Topics wählbar) |
| **MQTT (Home Assistant)** | ⭐⭐ Mittel | Volle Kontrolle, lokal | Erfordert MQTT-Broker |
| **Home Assistant Webhook** | ⭐⭐ Mittel | Direkte HA-Integration | Erfordert HA Installation |
| **Generischer Webhook** | ⭐⭐⭐ Erweitert | Maximale Flexibilität | Eigene Integration erforderlich |

### Empfehlung

Für **Einsteiger**: Beginne mit **ntfy.sh** - Setup in 5 Minuten!

Für **Home Assistant Nutzer**: **MQTT** oder **Webhook** für nahtlose Integration.

Für **Fortgeschrittene**: **Generischer Webhook** für eigene Systeme (Signal, Telegram, etc.).

---

## 🚀 Schnellstart mit ntfy.sh (Empfohlen)

ntfy.sh ist die einfachste Methode und funktioniert ohne Registrierung oder Setup eines eigenen Servers.

### Schritt 1: ntfy.sh App installieren

**Android:**
- [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)

**iOS:**
- [Apple App Store](https://apps.apple.com/us/app/ntfy/id1625396347)

**Alternative: Web-Interface**
- https://ntfy.sh (keine Installation nötig)

### Schritt 2: Topic-Namen wählen

Ein Topic ist wie ein privater Kanal, über den Benachrichtigungen gesendet werden.

**Wichtig**: Da ntfy.sh öffentlich ist, wähle einen **eindeutigen** Topic-Namen!

**Gute Beispiele:**
- `brauns-lichtershow-2024-geheim-xyz123`
- `meine-show-weihnacht-abc456`
- `fpp-control-max-2024-def789`

**Schlechte Beispiele (zu allgemein):**
- `lichtershow` (jeder könnte dies sehen)
- `weihnachten` (zu generisch)
- `test` (wird von vielen genutzt)

### Schritt 3: Topic in der App abonnieren

1. **ntfy.sh App öffnen**
2. **"+" antippen** (unten rechts)
3. **Server**: `ntfy.sh` (Standard)
4. **Topic-Name eingeben**: z.B. `brauns-lichtershow-2024-xyz`
5. **"Subscribe" antippen**

Fertig! Die App ist jetzt bereit, Benachrichtigungen zu empfangen.

### Schritt 4: FPP Web Control konfigurieren

Öffne deine `.env`-Datei und füge hinzu:

```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# ntfy.sh konfigurieren
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_URL=https://ntfy.sh
NOTIFY_NTFY_TOPIC=brauns-lichtershow-2024-xyz  # Dein gewählter Topic
```

**Optional - Token für geschützte Topics:**

Wenn du ein [passwortgeschütztes Topic](https://docs.ntfy.sh/publish/#access-tokens) verwendest:

```bash
NOTIFY_NTFY_TOKEN=dein_access_token_hier
```

### Schritt 5: Container neu starten

```bash
docker compose down
docker compose up -d
```

### Schritt 6: Testen

1. Öffne die FPP Web Control Seite
2. Starte eine Show oder wünsche ein Lied
3. Du solltest sofort eine Push-Benachrichtigung erhalten! 🎉

### Erweitert: Eigener ntfy.sh Server

Für mehr Privatsphäre kannst du [ntfy.sh selbst hosten](https://docs.ntfy.sh/install/):

```bash
# Docker-Setup für eigenen ntfy.sh Server
docker run -d \
  --name ntfy \
  -p 8080:80 \
  -v /var/cache/ntfy:/var/cache/ntfy \
  binwiederhier/ntfy \
  serve
```

Dann in `.env`:
```bash
NOTIFY_NTFY_URL=http://deine-server-ip:8080
```

---

## 🏠 Home Assistant Integration

Wenn du Home Assistant verwendest, hast du zwei Optionen: **MQTT** oder **Webhook**.

### Option A: MQTT (Empfohlen für HA)

MQTT bietet die beste Integration mit Home Assistant, da du Automationen direkt auf MQTT-Messages triggern kannst.

#### Voraussetzungen

- Home Assistant installiert
- MQTT-Broker läuft (z.B. Mosquitto Add-on)
- Home Assistant Companion App auf Smartphone

#### Schritt 1: MQTT-Broker in Home Assistant prüfen

1. **Home Assistant öffnen**
2. **Einstellungen → Geräte & Dienste**
3. **MQTT suchen** - sollte bereits konfiguriert sein
4. Falls nicht: **"Integration hinzufügen" → MQTT → Mosquitto Broker**

#### Schritt 2: MQTT-Zugangsdaten ermitteln

**Standard-Werte** (wenn Mosquitto Add-on verwendet):
- **Broker**: IP von Home Assistant (z.B. `192.168.1.100` oder `homeassistant.local`)
- **Port**: `1883`
- **Username**: Erstellt unter HA → Einstellungen → Personen → [Benutzer] → "Für externe Authentifizierung"
- **Passwort**: Vergibst du beim Erstellen

#### Schritt 3: FPP Web Control konfigurieren

In `.env`:

```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# MQTT konfigurieren
NOTIFY_MQTT_ENABLED=true
NOTIFY_MQTT_BROKER=192.168.1.100          # IP deines Home Assistant
NOTIFY_MQTT_PORT=1883
NOTIFY_MQTT_USERNAME=fpp-control          # Dein MQTT User
NOTIFY_MQTT_PASSWORD=dein-sicheres-passwort
NOTIFY_MQTT_TOPIC=fpp-control/notifications
NOTIFY_MQTT_USE_TLS=false                 # true für verschlüsselte Verbindung
```

#### Schritt 4: Container neu starten

```bash
docker compose restart
```

#### Schritt 5: Home Assistant Automation erstellen

Jetzt musst du in Home Assistant eine Automation erstellen, die auf die MQTT-Messages reagiert.

**Methode 1: YAML (configuration.yaml oder automations.yaml)**

```yaml
automation:
  # Benachrichtigung bei Show-Start
  - id: fpp_show_notification
    alias: "FPP Show gestartet"
    description: "Push-Benachrichtigung wenn ein Besucher eine Show startet"
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
            notification_icon: mdi:christmas-tree
            color: "#c41e3a"

  # Benachrichtigung bei Liedwunsch
  - id: fpp_song_notification
    alias: "FPP Liedwunsch"
    description: "Push-Benachrichtigung wenn ein Besucher ein Lied wünscht"
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
          message: >
            {{ trigger.payload_json.message }}
            Position in Warteschlange: {{ trigger.payload_json.queue_position }}
          data:
            priority: normal
            notification_icon: mdi:music-note
```

**Wichtig**: Ersetze `mobile_app_dein_handy` mit dem Namen deines Geräts.

**Gerätename finden:**
1. Home Assistant → Einstellungen → Geräte & Dienste
2. "Mobile App" suchen
3. Dein Smartphone antippen
4. Oben steht z.B. "mobile_app_pixel_6" - das ist dein Gerätename

**Methode 2: UI-Automation**

1. **Einstellungen → Automatisierungen & Szenen**
2. **"Automation hinzufügen"**
3. **Trigger:**
   - Typ: **MQTT**
   - Topic: `fpp-control/notifications`
4. **Bedingung:**
   - Typ: **Template**
   - Template: `{{ trigger.payload_json.action_type == 'show_start' }}`
5. **Aktion:**
   - Typ: **Benachrichtigung senden**
   - Dienst: `notify.mobile_app_dein_handy`
   - Titel: `{{ trigger.payload_json.title }}`
   - Nachricht: `{{ trigger.payload_json.message }}`

#### Schritt 6: Testen

1. Show in FPP Web Control starten
2. MQTT-Message in HA prüfen: **Entwicklerwerkzeuge → MQTT → Lauschen auf Topic** `fpp-control/notifications`
3. Push-Benachrichtigung sollte auf Smartphone ankommen

#### Erweitert: MQTT mit TLS

Für verschlüsselte Verbindungen:

```bash
NOTIFY_MQTT_USE_TLS=true
NOTIFY_MQTT_PORT=8883  # Standard TLS-Port
```

Stelle sicher, dass dein MQTT-Broker TLS unterstützt und Zertifikate konfiguriert hat.

---

### Option B: Home Assistant Webhook

Webhooks sind eine Alternative zu MQTT, besonders wenn du keinen MQTT-Broker verwenden möchtest.

#### Schritt 1: Webhook in Home Assistant erstellen

1. **Home Assistant → Einstellungen → Automatisierungen & Szenen**
2. **"Automation hinzufügen"**
3. **Trigger: Webhook**
   - Webhook-ID wählen: z.B. `fpp_control_notification`
   - Die URL wird angezeigt: `http://homeassistant.local:8123/api/webhook/fpp_control_notification`

#### Schritt 2: Long-Lived Access Token erstellen

1. **Home Assistant → Profil** (unten links auf deinen Namen klicken)
2. **Ganz nach unten scrollen: "Long-Lived Access Tokens"**
3. **"Token erstellen"**
4. **Name**: `FPP Web Control`
5. **Token kopieren** (wird nur einmal angezeigt!)

#### Schritt 3: FPP Web Control konfigurieren

In `.env`:

```bash
# Benachrichtigungen aktivieren
NOTIFY_ENABLED=true

# Home Assistant Webhook
NOTIFY_HOMEASSISTANT_ENABLED=true
NOTIFY_HOMEASSISTANT_URL=http://192.168.1.100:8123/api/webhook/fpp_control_notification
NOTIFY_HOMEASSISTANT_TOKEN=dein_long_lived_access_token
```

#### Schritt 4: Container neu starten

```bash
docker compose restart
```

#### Schritt 5: Automation in HA vervollständigen

In der Automation vom Schritt 1:

**Aktion hinzufügen:**

```yaml
action:
  - service: notify.mobile_app_dein_handy
    data:
      title: "{{ trigger.json.title }}"
      message: "{{ trigger.json.message }}"
```

Oder im UI:
1. **Aktion: Benachrichtigung senden**
2. **Dienst**: `notify.mobile_app_dein_handy`
3. **Titel**: `{{ trigger.json.title }}`
4. **Nachricht**: `{{ trigger.json.message }}`

---

## 🔧 Weitere Benachrichtigungsmethoden

### Signal Messenger

Über [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api).

#### Voraussetzungen

- signal-cli-rest-api installiert und läuft
- Signal-Nummer registriert

#### Konfiguration

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=http://signal-api:8080/v2/send
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json"}
```

**Hinweis**: Das Standard-Webhook-Payload muss ggf. im Code angepasst werden, um mit der Signal-API kompatibel zu sein.

---

### Telegram Bot

Über Telegram Bot API.

#### Schritt 1: Bot erstellen

1. In Telegram **@BotFather** suchen
2. `/newbot` senden
3. Namen und Username vergeben
4. **Bot-Token** kopieren
5. Chat-ID ermitteln (z.B. über @userinfobot)

#### Schritt 2: Konfiguration

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json"}
```

**Hinweis**: Auch hier muss das Payload-Format ggf. angepasst werden.

---

### Nextcloud Talk

Über Nextcloud Talk Bot.

#### Voraussetzungen

- Nextcloud mit Talk-App
- Bot-Account erstellt

#### Konfiguration

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-nextcloud.de/ocs/v2.php/apps/spreed/api/v1/bot/<TOKEN>/message
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json", "OCS-APIRequest": "true"}
```

---

### Generischer Webhook

Für eigene Integrationen oder APIs.

#### POST-Request

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-api.de/notifications
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Authorization": "Bearer DEIN_TOKEN", "Content-Type": "application/json"}
```

#### GET-Request

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://deine-api.de/notification
NOTIFY_WEBHOOK_METHOD=GET
```

Bei GET-Requests werden die Daten als Query-Parameter übergeben.

---

## 📦 Payload-Format

Alle Benachrichtigungen enthalten ein JSON-Payload mit folgender Struktur.

### Show-Start

```json
{
  "title": "🎄 Hauptshow gestartet",
  "message": "Ein Besucher hat 'show 1' gestartet.",
  "action_type": "show_start",
  "timestamp": "2024-12-24T18:00:00+01:00",
  "site_name": "Brauns Lichtershow",
  "playlist": "show 1",
  "playlist_type": "playlist1"
}
```

### Liedwunsch

```json
{
  "title": "🎵 Neuer Liedwunsch",
  "message": "Ein Besucher wünscht sich: 'Jingle Bells' (Dauer: 3:25)\nPosition in Warteschlange: 2",
  "action_type": "song_request",
  "timestamp": "2024-12-24T18:05:15+01:00",
  "site_name": "Brauns Lichtershow",
  "song_title": "Jingle Bells",
  "duration": 205,
  "queue_position": 2,
  "sequence_name": "jingle-bells.fseq",
  "media_name": "jingle-bells.mp3"
}
```

### Payload-Felder

| Feld | Typ | Beschreibung | Immer vorhanden |
|------|-----|-------------|----------------|
| `title` | string | Kurzer Titel | ✅ Ja |
| `message` | string | Vollständige Nachricht | ✅ Ja |
| `action_type` | string | `show_start` oder `song_request` | ✅ Ja |
| `timestamp` | string | ISO-Zeitstempel | ✅ Ja |
| `site_name` | string | Name der Show (aus `SITE_NAME`) | ✅ Ja |
| `playlist` | string | Playlist-Name | ❌ Nur bei `show_start` |
| `playlist_type` | string | `playlist1` oder `playlist2` | ❌ Nur bei `show_start` |
| `song_title` | string | Liedtitel | ❌ Nur bei `song_request` |
| `duration` | number | Dauer in Sekunden | ❌ Nur bei `song_request` |
| `queue_position` | number | Position in Warteschlange | ❌ Nur bei `song_request` |
| `sequence_name` | string | FSEQ-Dateiname | ❌ Nur bei `song_request` |
| `media_name` | string | Audio-Dateiname | ❌ Nur bei `song_request` |

---

## 🔍 Fehlersuche

### Benachrichtigungen kommen nicht an

#### Schritt 1: Logs prüfen

```bash
docker compose logs -f fpp-control
```

**Suche nach:**
- `send_notification called:` - Zeigt, dass die Funktion aufgerufen wurde
- `ntfy.sh notification sent successfully` - Erfolgreicher Versand via ntfy.sh
- `Failed to send ntfy notification` - Fehler beim ntfy.sh-Versand
- `MQTT publish failed with return code: X` - MQTT-Fehler

#### Schritt 2: Konfiguration prüfen

```bash
docker compose exec fpp-control env | grep NOTIFY
```

**Stelle sicher:**
- `NOTIFY_ENABLED=true`
- Mindestens eine Methode aktiviert (z.B. `NOTIFY_NTFY_ENABLED=true`)
- Topic/URL korrekt gesetzt

#### Schritt 3: Häufige Probleme

##### Problem: "Connection error" oder "Timeout"

**Ursache**: DNS-Problem im Container

**Lösung**:

1. **DNS-Server in docker-compose.yml prüfen** (sollte bereits vorhanden sein):
   ```yaml
   services:
     fpp-control:
       dns:
         - 8.8.8.8
         - 8.8.4.4
   ```

2. **Container komplett neu bauen**:
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

3. **DNS-Auflösung testen**:
   ```bash
   docker compose exec fpp-control getent hosts ntfy.sh
   ```
   Sollte die IP-Adresse ausgeben (z.B. `116.203.183.23`).

4. **Alternative DNS-Server** (falls weiterhin Probleme):
   ```yaml
   dns:
     - 192.168.1.1  # Dein Router
     - 1.1.1.1      # Cloudflare DNS
   ```

##### Problem: "HTTP 404" oder "HTTP 403"

**Ursache**: Falscher Topic-Name oder URL

**Lösung**:
- Prüfe `NOTIFY_NTFY_TOPIC` in `.env`
- Bei Webhook: URL korrekt?
- Bei passwortgeschützten Topics: Token gesetzt?

##### Problem: Keine Logs sichtbar

**Ursache**: Benachrichtigungen nicht aktiviert

**Lösung**:
```bash
# In .env prüfen:
NOTIFY_ENABLED=true
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_TOPIC=dein-topic
```

##### Problem: MQTT verbindet nicht

**Ursache**: Falsche Broker-Daten oder Firewall

**Lösung**:

1. **MQTT-Verbindung von außerhalb Container testen**:
   ```bash
   mosquitto_pub -h 192.168.1.100 -p 1883 \
     -u dein-username -P dein-passwort \
     -t test -m "Test"
   ```

2. **Firewall-Regeln prüfen** (Port 1883 offen?)

3. **TLS-Einstellungen prüfen**:
   - TLS aktiviert? Port meist 8883
   - Zertifikate korrekt?

#### Schritt 4: Manuelle Tests

**ntfy.sh manuell testen** (vom Container aus):

```bash
docker compose exec fpp-control python3 -c "
import requests
response = requests.post(
    'https://ntfy.sh/dein-topic',
    data='Test vom Container'.encode('utf-8'),
    headers={'Title': 'Testbenachrichtigung'},
    timeout=5
)
print(f'Status: {response.status_code}')
print(f'Response: {response.text}')
"
```

Sollte `Status: 200` ausgeben.

**ntfy.sh von außen testen** (vom Desktop):

```bash
curl -d "Test von Desktop" https://ntfy.sh/dein-topic
```

### Preview-Modus und Benachrichtigungen

**Wichtig**: Im `PREVIEW_MODE=true` werden **KEINE** Benachrichtigungen versendet!

Dies verhindert Test-Benachrichtigungen während der Entwicklung.

**Um Benachrichtigungen in Preview-Mode zu testen:**

```bash
# In .env:
PREVIEW_MODE=false
NOTIFY_ENABLED=true
NOTIFY_NTFY_ENABLED=true
```

Benachrichtigungen werden dann auch ohne verbundenen FPP versendet.

---

## 🔐 Sicherheitshinweise

### ntfy.sh

- **Verwende eindeutige Topic-Namen!** Öffentliche Topics können von jedem abonniert werden.
- **Besser**: [Selbst gehostete ntfy.sh-Instanz](https://docs.ntfy.sh/install/) mit Passwortschutz
- **Alternative**: [Passwortgeschützte Topics](https://docs.ntfy.sh/publish/#access-tokens) mit Token

### MQTT

- **Aktiviere TLS** für verschlüsselte Verbindung:
  ```bash
  NOTIFY_MQTT_USE_TLS=true
  NOTIFY_MQTT_PORT=8883
  ```
- **Verwende starke Passwörter** für MQTT-User
- **Beschränke MQTT-User** auf benötigte Topics (Zugriffsrechte in Mosquitto)

### Webhooks

- **Verwende HTTPS** statt HTTP für Webhook-URLs
- **API-Tokens**: Speichere Tokens niemals in öffentlichen Repositories!
- **Nutze Secrets-Management** für Produktion (z.B. Docker Secrets, Vault)

### Home Assistant

- **Long-Lived Tokens** sicher aufbewahren
- **Webhook-IDs** nicht zu einfach wählen (schwer zu erraten)
- **Firewall**: HA nur im LAN erreichbar lassen, wenn möglich

---

## 🎛️ Mehrere Methoden gleichzeitig

Du kannst mehrere Benachrichtigungsmethoden parallel aktivieren!

**Beispiel-Konfiguration:**

```bash
# Globale Aktivierung
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
NOTIFY_WEBHOOK_METHOD=POST
```

**Verhalten:**
- Alle aktivierten Methoden erhalten **gleichzeitig** die Benachrichtigung
- Fehler in einer Methode beeinflussen andere **nicht**
- Jede Methode sendet unabhängig

**Use Case:**
- **ntfy.sh**: Für dich persönlich (Smartphone)
- **MQTT**: Für Home Assistant Automationen (z.B. Licht anschalten)
- **Webhook**: Für Logging/Statistiken in eigener Datenbank

---

## 📝 Zusammenfassung

### Für Einsteiger (5 Minuten Setup)

1. **ntfy.sh App installieren**
2. **Topic wählen und abonnieren**: z.B. `meine-show-xyz123`
3. **In `.env` konfigurieren**:
   ```bash
   NOTIFY_ENABLED=true
   NOTIFY_NTFY_ENABLED=true
   NOTIFY_NTFY_TOPIC=meine-show-xyz123
   ```
4. **Container neu starten**: `docker compose restart`
5. **Testen**: Show starten → Benachrichtigung sollte ankommen!

### Für Home Assistant Nutzer

1. **MQTT-Broker in HA prüfen** (Mosquitto Add-on)
2. **MQTT-Zugangsdaten in `.env` eintragen**
3. **Container neu starten**
4. **Automation in HA erstellen** (siehe [Home Assistant Integration](#option-a-mqtt-empfohlen-für-ha))
5. **Testen**

### Bei Problemen

1. **Logs prüfen**: `docker compose logs -f fpp-control`
2. **DNS-Problem?** Container neu bauen: `docker compose build --no-cache && docker compose up -d`
3. **Konfiguration prüfen**: `docker compose exec fpp-control env | grep NOTIFY`
4. **Siehe [Fehlersuche](#-fehlersuche)** für detaillierte Hilfe

---

**Viel Erfolg mit deinen Benachrichtigungen! 🔔✨**
