# 🔔 Notifications – complete guide

[Deutsch](NOTIFICATIONS.de.md) · **English**

Get push notifications on your phone when visitors control your light show!

FPP Web Control can notify you automatically when:
- 🎄 a visitor starts a show
- 🎵 a visitor requests a song

---

> **Where are the settings made?**
> The examples in this guide show environment variables (`NOTIFY_…`). Each of them can be set
> in three ways:
>
> - in **`config/config.json`** under the matching key in camelCase, e.g.
>   `NOTIFY_NTFY_TOPIC` → `"notifyNtfyTopic"`, `NOTIFY_MQTT_USE_TLS` → `"notifyMqttUseTls"`,
> - as an **environment variable** of the container (`environment:` or `env_file:` in the
>   Compose file; the included `docker-compose.yml` loads `.env`, in `docker-stack.yml`
>   the variables are written directly into the file),
> - as a **Docker secret** via `<VARIABLE>_FILE`, e.g. `NOTIFY_NTFY_TOKEN_FILE=/run/secrets/ntfy_token`.
>
> A value in `config.json` takes precedence. Changes take effect after the container restarts.
> In preview mode no notifications are sent.
>
> **Language:** title and text of the notifications use `APP_DEFAULT_LANGUAGE` (default `en`),
> or the fixed language from `APP_LANGUAGE`.

---

## 📖 Contents

- [Overview](#-overview)
- [Quick start with ntfy.sh](#-quick-start-with-ntfysh-recommended)
- [Home Assistant integration](#-home-assistant-integration)
- [Other notification methods](#-other-notification-methods)
- [Payload format](#-payload-format)
- [Troubleshooting](#-troubleshooting)
- [Security notes](#-security-notes)
- [Several methods at once](#-several-methods-at-once)

---

## 🎯 Overview

### Supported methods

| Method | Difficulty | Pros | Cons |
|---------|--------------|----------|-----------|
| **ntfy.sh** | ⭐ Very easy | No sign-up, works right away | Public service (you choose the topic) |
| **MQTT (Home Assistant)** | ⭐⭐ Medium | Full control, local | Needs an MQTT broker |
| **Home Assistant webhook** | ⭐⭐ Medium | Direct HA integration | Needs Home Assistant |
| **Generic webhook** | ⭐⭐⭐ Advanced | Maximum flexibility | You build the integration |

### Recommendation

**Beginners**: start with **ntfy.sh** – set up in 5 minutes.

**Home Assistant users**: **MQTT** or **webhook** for a seamless integration.

**Advanced users**: a **generic webhook** for your own systems (Signal, Telegram, etc.).

---

## 🚀 Quick start with ntfy.sh (recommended)

ntfy.sh is the simplest method and works without registration or a server of your own.

### Step 1: install the ntfy app

- **Android:** [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- **iOS:** [Apple App Store](https://apps.apple.com/us/app/ntfy/id1625396347)
- **Web:** https://ntfy.sh (no installation)

### Step 2: choose a topic name

A topic is like a private channel the notifications are sent through.

**Important:** ntfy.sh is public, so choose a **unique** topic name!

- Good: `smith-lightshow-2026-secret-xyz123`, `my-show-xmas-abc456`
- Bad (too generic): `lightshow`, `christmas`, `test`

### Step 3: subscribe to the topic in the app

1. Open the ntfy app
2. Tap **"+"** (bottom right)
3. **Server**: `ntfy.sh` (default)
4. Enter the **topic name**
5. Tap **"Subscribe"**

### Step 4: configure FPP Web Control

Add to your `.env` file:

```bash
# switch notifications on
NOTIFY_ENABLED=true

# ntfy.sh
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_URL=https://ntfy.sh
NOTIFY_NTFY_TOPIC=smith-lightshow-2026-xyz  # your topic
```

**Optional – token for protected topics** ([access tokens](https://docs.ntfy.sh/publish/#access-tokens)):

```bash
NOTIFY_NTFY_TOKEN=your_access_token
```

### Step 5: restart the container

```bash
docker compose down
docker compose up -d
```

### Step 6: test

Open FPP Web Control, start a show or request a song – the push notification should arrive right away. 🎉

### Advanced: your own ntfy server

For more privacy you can [host ntfy yourself](https://docs.ntfy.sh/install/):

```bash
docker run -d --name ntfy -p 8080:80 -v /var/cache/ntfy:/var/cache/ntfy binwiederhier/ntfy serve
```

Then in `.env`: `NOTIFY_NTFY_URL=http://your-server-ip:8080`

---

## 🏠 Home Assistant integration

With Home Assistant you have two options: **MQTT** or a **webhook**.

### Option A: MQTT (recommended for HA)

MQTT gives the best integration, because automations can trigger directly on MQTT messages.

**Requirements:** Home Assistant, an MQTT broker (e.g. the Mosquitto add-on), the Home Assistant Companion app on your phone.

#### Step 1: check the MQTT broker

Home Assistant → **Settings → Devices & services** → MQTT should be configured. If not: **Add integration → MQTT → Mosquitto broker**.

#### Step 2: MQTT credentials

With the Mosquitto add-on:
- **Broker**: IP of Home Assistant (e.g. `192.168.1.100` or `homeassistant.local`)
- **Port**: `1883`
- **User name / password**: a Home Assistant user, or a user set up in the Mosquitto add-on

#### Step 3: configure FPP Web Control

```bash
NOTIFY_ENABLED=true
NOTIFY_MQTT_ENABLED=true
NOTIFY_MQTT_BROKER=192.168.1.100
NOTIFY_MQTT_PORT=1883
NOTIFY_MQTT_USERNAME=fpp-control
NOTIFY_MQTT_PASSWORD=a-strong-password
NOTIFY_MQTT_TOPIC=fpp-control/notifications
NOTIFY_MQTT_USE_TLS=false                 # true for an encrypted connection
```

Then `docker compose restart`.

#### Step 4: create a Home Assistant automation

**YAML (`automations.yaml`):**

```yaml
automation:
  # show started
  - id: fpp_show_notification
    alias: "FPP show started"
    trigger:
      - platform: mqtt
        topic: "fpp-control/notifications"
    condition:
      - condition: template
        value_template: "{{ trigger.payload_json.action_type == 'show_start' }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "{{ trigger.payload_json.title }}"
          message: "{{ trigger.payload_json.message }}"
          data:
            priority: high
            notification_icon: mdi:christmas-tree

  # song requested
  - id: fpp_song_notification
    alias: "FPP song request"
    trigger:
      - platform: mqtt
        topic: "fpp-control/notifications"
    condition:
      - condition: template
        value_template: "{{ trigger.payload_json.action_type == 'song_request' }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "{{ trigger.payload_json.title }}"
          message: "{{ trigger.payload_json.message }}"
          data:
            notification_icon: mdi:music-note
```

Replace `mobile_app_your_phone` with the name of your device (Settings → Devices & services → Mobile App → your phone, e.g. `mobile_app_pixel_8`).

**In the UI:** Settings → Automations & scenes → Add automation → trigger **MQTT** with topic `fpp-control/notifications`, condition **Template** `{{ trigger.payload_json.action_type == 'show_start' }}`, action **Send notification** with title `{{ trigger.payload_json.title }}` and message `{{ trigger.payload_json.message }}`.

#### Step 5: test

Start a show and watch the message under **Developer tools → MQTT → Listen to a topic** `fpp-control/notifications`.

#### MQTT with TLS

```bash
NOTIFY_MQTT_USE_TLS=true
NOTIFY_MQTT_PORT=8883
```

Your broker must support TLS and have certificates configured.

### Option B: Home Assistant webhook

1. **Create the webhook**: Settings → Automations & scenes → Add automation → trigger **Webhook**, webhook ID e.g. `fpp_control_notification`. The URL is `http://homeassistant.local:8123/api/webhook/fpp_control_notification`.
2. **Create a long-lived access token**: your profile (bottom left) → **Long-lived access tokens** → **Create token**, name `FPP Web Control`. Copy it – it is shown only once.
3. **Configure FPP Web Control:**

   ```bash
   NOTIFY_ENABLED=true
   NOTIFY_HOMEASSISTANT_ENABLED=true
   NOTIFY_HOMEASSISTANT_URL=http://192.168.1.100:8123/api/webhook/fpp_control_notification
   NOTIFY_HOMEASSISTANT_TOKEN=your_long_lived_access_token
   ```

4. **Finish the automation** with an action:

   ```yaml
   action:
     - service: notify.mobile_app_your_phone
       data:
         title: "{{ trigger.json.title }}"
         message: "{{ trigger.json.message }}"
   ```

---

## 🔧 Other notification methods

All of these use the generic webhook. The app sends its own JSON payload (see below); services that expect a different format may need a small adapter in between (e.g. an n8n or Node-RED flow).

### Signal (via [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api))

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=http://signal-api:8080/v2/send
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json"}
```

### Telegram bot

1. In Telegram, message **@BotFather**, send `/newbot`, choose a name, copy the **bot token**.
2. Find your chat ID (e.g. with @userinfobot).

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json"}
```

### Nextcloud Talk

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://your-nextcloud.example/ocs/v2.php/apps/spreed/api/v1/bot/<TOKEN>/message
NOTIFY_WEBHOOK_METHOD=POST
NOTIFY_WEBHOOK_HEADERS={"Content-Type": "application/json", "OCS-APIRequest": "true"}
```

### Generic webhook

```bash
NOTIFY_ENABLED=true
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://your-api.example/notifications
NOTIFY_WEBHOOK_METHOD=POST          # or GET: the data is then sent as query parameters
NOTIFY_WEBHOOK_HEADERS={"Authorization": "Bearer YOUR_TOKEN", "Content-Type": "application/json"}
```

---

## 📦 Payload format

Every notification carries a JSON payload with this structure (texts in `APP_DEFAULT_LANGUAGE`).

### Show start

```json
{
  "title": "Main show started",
  "message": "A visitor started “show 1”.",
  "action_type": "show_start",
  "timestamp": "2026-12-24T18:00:00+01:00",
  "site_name": "Smith Light Show",
  "playlist": "show 1",
  "playlist_type": "playlist1"
}
```

### Song request

```json
{
  "title": "New song request",
  "message": "A visitor requested: “Jingle Bells” (length: 3:25)\nPosition in the queue: 2",
  "action_type": "song_request",
  "timestamp": "2026-12-24T18:05:15+01:00",
  "site_name": "Smith Light Show",
  "song_title": "Jingle Bells",
  "duration": 205,
  "queue_position": 2,
  "sequence_name": "jingle-bells.fseq",
  "media_name": "jingle-bells.mp3"
}
```

### Fields

| Field | Type | Description | Always present |
|------|-----|-------------|----------------|
| `title` | string | Short title | ✅ yes |
| `message` | string | Full message | ✅ yes |
| `action_type` | string | `show_start` or `song_request` | ✅ yes |
| `timestamp` | string | ISO timestamp | ✅ yes |
| `site_name` | string | Name of the show (`SITE_NAME`) | ✅ yes |
| `playlist` | string | Playlist name | only for `show_start` |
| `playlist_type` | string | `playlist1` or `playlist2` | only for `show_start` |
| `song_title` | string | Song title | only for `song_request` |
| `duration` | number | Length in seconds | only for `song_request` |
| `queue_position` | number | Position in the queue | only for `song_request` |
| `sequence_name` | string | FSEQ file name | only for `song_request` |
| `media_name` | string | Audio file name | only for `song_request` |

---

## 🔍 Troubleshooting

### Notifications don't arrive

1. **Check the logs:** `docker compose logs -f fpp-control`. Look for `send_notification called:`, `ntfy.sh notification sent successfully`, `Failed to send ntfy notification`, `MQTT publish failed with return code: X`.
2. **Check the configuration:** `docker compose exec fpp-control env | grep NOTIFY` – `NOTIFY_ENABLED=true`, at least one method enabled, topic/URL set.
3. **Common problems:**
   - **"Connection error" or "Timeout"** – usually DNS inside the container. Test with `docker compose exec fpp-control getent hosts ntfy.sh`; if needed set DNS servers in the Compose file (`dns: [1.1.1.1, 8.8.8.8]`) and recreate the container.
   - **"HTTP 404" or "HTTP 403"** – wrong topic name or URL, or a protected topic without token.
   - **No log lines at all** – notifications are not enabled (`NOTIFY_ENABLED` and a method's `…_ENABLED`).
   - **MQTT doesn't connect** – wrong broker data or a firewall. Test from outside the container: `mosquitto_pub -h 192.168.1.100 -p 1883 -u user -P password -t test -m "Test"`. With TLS the port is usually 8883.
4. **Manual test from the container:**

   ```bash
   docker compose exec fpp-control python3 -c "
   import requests
   r = requests.post('https://ntfy.sh/your-topic', data='Test from the container'.encode(), headers={'Title': 'Test'}, timeout=5)
   print(r.status_code, r.text)
   "
   ```

   Or from your desktop: `curl -d "Test from desktop" https://ntfy.sh/your-topic`

### Preview mode

With `PREVIEW_MODE=true` **no** notifications are sent. To test notifications without a connected FPP, set `PREVIEW_MODE=false` – they are sent even if FPP isn't reachable.

---

## 🔐 Security notes

- **ntfy.sh:** use unique topic names – public topics can be subscribed to by anybody. Better: a [self-hosted instance](https://docs.ntfy.sh/install/) or [protected topics](https://docs.ntfy.sh/publish/#access-tokens) with a token.
- **MQTT:** enable TLS (`NOTIFY_MQTT_USE_TLS=true`, port 8883), use strong passwords, restrict the MQTT user to the topics it needs.
- **Webhooks:** use HTTPS, never put tokens into public repositories, use secrets management (Docker secrets).
- **Home Assistant:** keep long-lived tokens safe, choose webhook IDs that are hard to guess, keep HA on the LAN if you can.

---

## 🎛️ Several methods at once

You can enable several methods in parallel:

```bash
NOTIFY_ENABLED=true

# ntfy for push notifications
NOTIFY_NTFY_ENABLED=true
NOTIFY_NTFY_TOPIC=my-show-123

# MQTT for Home Assistant
NOTIFY_MQTT_ENABLED=true
NOTIFY_MQTT_BROKER=192.168.1.100
NOTIFY_MQTT_TOPIC=fpp-control/notifications

# webhook for your own logging API
NOTIFY_WEBHOOK_ENABLED=true
NOTIFY_WEBHOOK_URL=https://my-api.example/log
NOTIFY_WEBHOOK_METHOD=POST
```

All enabled methods receive the notification at the same time; an error in one doesn't affect the others.

---

**Good luck with your notifications! 🔔✨**
