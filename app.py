import hashlib
import hmac
import html
import json
import logging
import os
import threading
import time
from datetime import datetime as dt_datetime
from datetime import timedelta as dt_timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, Response, jsonify, redirect, request, send_from_directory, g

from code_matrix import CodeMatrix, parse_color

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ["true", "1", "yes", "on"]


def _load_runtime_config() -> Dict[str, Any]:
    config_path = Path(os.getenv("APP_CONFIG_PATH", "/app/config/config.json"))
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            logging.getLogger(__name__).info("Loaded runtime config from %s", config_path)
            return data
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to read runtime config %s: %s", config_path, exc)
    return {}


RUNTIME_CONFIG = _load_runtime_config()


def _read_secret_file(env_key: str) -> Optional[str]:
    """Return the content of the file named by ``<ENV_KEY>_FILE`` (Docker secrets)."""
    file_path = os.getenv(f"{env_key}_FILE", "").strip()
    if not file_path:
        return None
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        logging.getLogger(__name__).warning("Failed to read %s_FILE (%s): %s", env_key, file_path, exc)
        return None


def _cfg(key: str, env_key: str, default: Any = "") -> Any:
    """Resolve a setting: config.json > <ENV>_FILE (secret) > ENV > default."""
    if key in RUNTIME_CONFIG:
        return RUNTIME_CONFIG[key]
    secret = _read_secret_file(env_key)
    if secret is not None:
        return secret
    return os.getenv(env_key, default)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# No implicit static folder: only the explicitly routed files are public.
# (A static folder of '.' would expose app.py, config/ and data/.)
app = Flask(__name__, static_folder=None)

SITE_NAME = str(_cfg("siteName", "SITE_NAME", "FPP Lichtershow"))
# Shown in search results and link previews (WhatsApp, Signal, ...)
SITE_DESCRIPTION = str(_cfg("siteDescription", "SITE_DESCRIPTION", "Lichtershow starten, Lieder wünschen und die Musik direkt am Handy hören."))
# Optional absolute URL of a preview picture for shared links
SITE_IMAGE_URL = str(_cfg("siteImageUrl", "SITE_IMAGE_URL", "")).strip()
FPP_BASE_URL = str(_cfg("fppBaseUrl", "FPP_BASE_URL", "http://fpp.local"))
PLAYLIST_1 = str(_cfg("playlist1", "FPP_PLAYLIST_1", "show 1"))
PLAYLIST_2 = str(_cfg("playlist2", "FPP_PLAYLIST_2", "show 2"))
PLAYLIST_REQUESTS = str(_cfg("playlistRequests", "FPP_PLAYLIST_REQUESTS", "all songs"))
BACKGROUND_EFFECT = str(_cfg("backgroundEffect", "FPP_BACKGROUND_EFFECT", "background"))
SHOW_START_DATE = str(_cfg("showStartDate", "FPP_SHOW_START_DATE", "")) or None
SHOW_END_DATE = str(_cfg("showEndDate", "FPP_SHOW_END_DATE", "")) or None
SHOW_START_TIME = str(_cfg("showStartTime", "FPP_SHOW_START_TIME", "16:30"))
SHOW_END_TIME = str(_cfg("showEndTime", "FPP_SHOW_END_TIME", "22:00"))
SCHEDULED_SHOWS_ENABLED = _parse_bool(_cfg("scheduledShowsEnabled", "SCHEDULED_SHOWS_ENABLED", "true"), True)
PREVIEW_MODE = _parse_bool(_cfg("previewMode", "PREVIEW_MODE", "false"), False)
POLL_INTERVAL_SECONDS = max(5, int(_cfg("fppPollIntervalMs", "FPP_POLL_INTERVAL_MS", "15000")) // 1000)
# While a show or wish is running the status is polled faster, so the UI
# (locks, queue, speaker button) follows FPP without a long delay.
ACTIVE_POLL_INTERVAL_SECONDS = min(5, POLL_INTERVAL_SECONDS)
REQUEST_TIMEOUT = 8
# Scheduled shows, e.g. "17:00=playlist2,19:00=playlist1" (or a JSON list in
# config.json). Empty = built-in default (17:00 playlist 2, 18-21:00 playlist 1).
SHOW_SCHEDULE_RAW = _cfg("showSchedule", "FPP_SHOW_SCHEDULE", "")
# 0 = keep statistics forever; otherwise entries older than N days are dropped.
STATISTICS_RETENTION_DAYS = max(0, int(_cfg("statisticsRetentionDays", "STATISTICS_RETENTION_DAYS", "0") or 0))

# FalconBeat (synchronised show audio on visitor devices)
# mode: "auto" = use it when the FPP plugin is installed + enabled,
#       "on"   = skip the plugin check (server URL must be configured),
#       "off"  = never offer audio.
FALCONBEAT_MODE = str(_cfg("falconbeatMode", "FALCONBEAT_MODE", "auto")).strip().lower() or "auto"
FALCONBEAT_SERVER_URL = str(_cfg("falconbeatServerUrl", "FALCONBEAT_SERVER_URL", "")).strip()
FALCONBEAT_CLIENT_BASE = str(_cfg("falconbeatClientBase", "FALCONBEAT_CLIENT_BASE", "/falconbeat")).strip()
FALCONBEAT_PLUGIN_NAME = "fpp-plugin-FalconBeat"
FALCONBEAT_CHECK_INTERVAL_SECONDS = 30
SONG_CACHE_TTL_SECONDS = 60
# Fairness: how many wishes one device may have waiting, and how long the
# queue may get in total (0 = unlimited).
MAX_WISHES_PER_DEVICE = max(0, int(_cfg("maxWishesPerDevice", "MAX_WISHES_PER_DEVICE", "2") or 0))
MAX_QUEUE_LENGTH = max(0, int(_cfg("maxQueueLength", "MAX_QUEUE_LENGTH", "10") or 0))

# Notification Configuration
NOTIFY_ENABLED = _parse_bool(_cfg("notifyEnabled", "NOTIFY_ENABLED", "false"), False)
NOTIFY_MQTT_ENABLED = _parse_bool(_cfg("notifyMqttEnabled", "NOTIFY_MQTT_ENABLED", "false"), False)
NOTIFY_MQTT_BROKER = str(_cfg("notifyMqttBroker", "NOTIFY_MQTT_BROKER", ""))
NOTIFY_MQTT_PORT = int(_cfg("notifyMqttPort", "NOTIFY_MQTT_PORT", "1883"))
NOTIFY_MQTT_USERNAME = str(_cfg("notifyMqttUsername", "NOTIFY_MQTT_USERNAME", ""))
NOTIFY_MQTT_PASSWORD = str(_cfg("notifyMqttPassword", "NOTIFY_MQTT_PASSWORD", ""))
NOTIFY_MQTT_TOPIC = str(_cfg("notifyMqttTopic", "NOTIFY_MQTT_TOPIC", "fpp-control/notifications"))
NOTIFY_MQTT_USE_TLS = _parse_bool(_cfg("notifyMqttUseTls", "NOTIFY_MQTT_USE_TLS", "false"), False)

NOTIFY_NTFY_ENABLED = _parse_bool(_cfg("notifyNtfyEnabled", "NOTIFY_NTFY_ENABLED", "false"), False)
NOTIFY_NTFY_URL = str(_cfg("notifyNtfyUrl", "NOTIFY_NTFY_URL", "https://ntfy.sh"))
NOTIFY_NTFY_TOPIC = str(_cfg("notifyNtfyTopic", "NOTIFY_NTFY_TOPIC", ""))
NOTIFY_NTFY_TOKEN = str(_cfg("notifyNtfyToken", "NOTIFY_NTFY_TOKEN", ""))

NOTIFY_HOMEASSISTANT_ENABLED = _parse_bool(_cfg("notifyHomeassistantEnabled", "NOTIFY_HOMEASSISTANT_ENABLED", "false"), False)
NOTIFY_HOMEASSISTANT_URL = str(_cfg("notifyHomeassistantUrl", "NOTIFY_HOMEASSISTANT_URL", ""))
NOTIFY_HOMEASSISTANT_TOKEN = str(_cfg("notifyHomeassistantToken", "NOTIFY_HOMEASSISTANT_TOKEN", ""))

NOTIFY_WEBHOOK_ENABLED = _parse_bool(_cfg("notifyWebhookEnabled", "NOTIFY_WEBHOOK_ENABLED", "false"), False)
NOTIFY_WEBHOOK_URL = str(_cfg("notifyWebhookUrl", "NOTIFY_WEBHOOK_URL", ""))
NOTIFY_WEBHOOK_METHOD = str(_cfg("notifyWebhookMethod", "NOTIFY_WEBHOOK_METHOD", "POST")).upper()
NOTIFY_WEBHOOK_HEADERS = str(_cfg("notifyWebhookHeaders", "NOTIFY_WEBHOOK_HEADERS", ""))

# Initialize MQTT client if enabled
mqtt_client = None
if NOTIFY_ENABLED and NOTIFY_MQTT_ENABLED and MQTT_AVAILABLE and NOTIFY_MQTT_BROKER:
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if NOTIFY_MQTT_USERNAME and NOTIFY_MQTT_PASSWORD:
            mqtt_client.username_pw_set(NOTIFY_MQTT_USERNAME, NOTIFY_MQTT_PASSWORD)
        if NOTIFY_MQTT_USE_TLS:
            mqtt_client.tls_set()
        mqtt_client.connect(NOTIFY_MQTT_BROKER, NOTIFY_MQTT_PORT, 60)
        mqtt_client.loop_start()
    except (AttributeError, TypeError):
        # Fallback for older paho-mqtt versions without CallbackAPIVersion
        try:
            mqtt_client = mqtt.Client()
            if NOTIFY_MQTT_USERNAME and NOTIFY_MQTT_PASSWORD:
                mqtt_client.username_pw_set(NOTIFY_MQTT_USERNAME, NOTIFY_MQTT_PASSWORD)
            if NOTIFY_MQTT_USE_TLS:
                mqtt_client.tls_set()
            mqtt_client.connect(NOTIFY_MQTT_BROKER, NOTIFY_MQTT_PORT, 60)
            mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            mqtt_client = None
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        mqtt_client = None


ACCESS_CODE = str(_cfg("accessCode", "ACCESS_CODE", "")).strip()

# Daily access code shown on a pixel matrix (an FPP overlay model). Enabled by
# naming the model; the code changes every day and is displayed whenever
# nothing is playing, so only people in front of the house can read it.
CODE_MATRIX_MODEL = str(_cfg("codeMatrixModel", "CODE_MATRIX_MODEL", "")).strip()
CODE_MATRIX_DIGITS = min(6, max(2, int(_cfg("codeMatrixDigits", "CODE_MATRIX_DIGITS", "3") or 3)))
CODE_MATRIX_COLOR = parse_color(str(_cfg("codeMatrixColor", "CODE_MATRIX_COLOR", "#FFFFFF")))
# Real wiring of the matrix; empty = use what FPP knows about the model.
CODE_MATRIX_STRINGS = int(_cfg("codeMatrixStrings", "CODE_MATRIX_STRINGS", "0") or 0) or None
CODE_MATRIX_STRANDS_PER_STRING = int(_cfg("codeMatrixStrandsPerString", "CODE_MATRIX_STRANDS_PER_STRING", "0") or 0) or None
CODE_MATRIX_ORIENTATION = str(_cfg("codeMatrixOrientation", "CODE_MATRIX_ORIENTATION", "")).strip().upper()[:1] or None
CODE_MATRIX_START_CORNER = str(_cfg("codeMatrixStartCorner", "CODE_MATRIX_START_CORNER", "")).strip().upper()[:2] or None
# Secret the daily code is derived from; empty = generated once and kept in data/.
CODE_SECRET = str(_cfg("codeSecret", "CODE_SECRET", "")).strip()
DAILY_CODE_ENABLED = bool(CODE_MATRIX_MODEL) and not PREVIEW_MODE
ACCESS_REQUIRED = bool(ACCESS_CODE) or DAILY_CODE_ENABLED
# Wrong codes per client before it has to wait.
ACCESS_MAX_FAILURES = 6
ACCESS_LOCKOUT_SECONDS = 10 * 60


def send_notification(title: str, message: str, action_type: str = "info", extra_data: Optional[Dict[str, Any]] = None) -> None:
    """Send notification via configured channels.
    
    This function sends notifications through all enabled notification channels
    simultaneously. Channels include MQTT, ntfy.sh, Home Assistant webhooks,
    and generic webhooks. Each channel operates independently, so a failure
    in one channel does not affect others.
    
    Args:
        title: Short notification title (e.g., "Show gestartet")
        message: Full notification message body
        action_type: Type of action for categorization. Common values:
            - "show_start": Show was started via button
            - "song_request": Song was requested by visitor
            - "info": General information notification
        extra_data: Optional dict with additional data to include in payload.
            For show_start: {"playlist": "show1", "playlist_type": "playlist1"}
            For song_request: {"song_title": "...", "duration": 180, "queue_position": 2}
    
    Example:
        >>> send_notification(
        ...     title="Hauptshow gestartet",
        ...     message="Ein Besucher hat 'show 1' gestartet.",
        ...     action_type="show_start",
        ...     extra_data={"playlist": "show 1"}
        ... )
    
    Note:
        - All notification failures are logged but do not raise exceptions
        - Notifications are sent asynchronously (non-blocking)
        - Requires NOTIFY_ENABLED=true in environment configuration
    """
    if not NOTIFY_ENABLED:
        return
    
    # Skip notifications in preview mode
    if PREVIEW_MODE:
        logger.info(f"Preview mode: Skipping notification - {title}")
        return
    
    timestamp = dt_datetime.now().isoformat()
    payload = {
        "title": title,
        "message": message,
        "action_type": action_type,
        "timestamp": timestamp,
        "site_name": SITE_NAME,
    }
    
    if extra_data:
        payload.update(extra_data)
    
    # Send via MQTT
    if NOTIFY_MQTT_ENABLED and mqtt_client:
        try:
            mqtt_payload = json.dumps(payload, ensure_ascii=False)
            result = mqtt_client.publish(NOTIFY_MQTT_TOPIC, mqtt_payload, qos=1, retain=False)
            # Check if message was successfully queued (result code 0 = success)
            if result.rc != 0:
                logger.error(f"MQTT publish failed with return code: {result.rc}")
        except Exception as e:
            logger.error(f"Failed to send MQTT notification: {e}")
    
    # Send via ntfy.sh
    if NOTIFY_NTFY_ENABLED and NOTIFY_NTFY_TOPIC:
        try:
            # ntfy.sh API: POST to topic URL with message as text body
            # Headers are used for title, priority, and tags
            url = f"{NOTIFY_NTFY_URL}/{NOTIFY_NTFY_TOPIC}"
            
            headers = {
                "Title": title,
                "Priority": "default",
                "Tags": action_type
            }
            
            if NOTIFY_NTFY_TOKEN:
                headers["Authorization"] = f"Bearer {NOTIFY_NTFY_TOKEN}"
            
            # Send message as plain text body (not JSON)
            response = requests.post(
                url, 
                data=message,
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"ntfy.sh notification failed: HTTP {response.status_code} - {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Failed to send ntfy notification: Timeout after 5 seconds")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to send ntfy notification: Connection error - {e}")
        except Exception as e:
            logger.error(f"Failed to send ntfy notification: {e}")
    
    # Send via Home Assistant
    if NOTIFY_HOMEASSISTANT_ENABLED and NOTIFY_HOMEASSISTANT_URL and NOTIFY_HOMEASSISTANT_TOKEN:
        try:
            headers = {
                "Authorization": f"Bearer {NOTIFY_HOMEASSISTANT_TOKEN}",
                "Content-Type": "application/json",
            }
            ha_payload = {
                "title": title,
                "message": message,
                "data": payload,
            }
            requests.post(NOTIFY_HOMEASSISTANT_URL, json=ha_payload, headers=headers, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Home Assistant notification: {e}")
    
    # Send via generic webhook
    if NOTIFY_WEBHOOK_ENABLED and NOTIFY_WEBHOOK_URL:
        try:
            headers = {"Content-Type": "application/json"}
            if NOTIFY_WEBHOOK_HEADERS:
                try:
                    custom_headers = json.loads(NOTIFY_WEBHOOK_HEADERS)
                    headers.update(custom_headers)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse NOTIFY_WEBHOOK_HEADERS as JSON: {e}")
            
            if NOTIFY_WEBHOOK_METHOD == "GET":
                requests.get(NOTIFY_WEBHOOK_URL, params=payload, headers=headers, timeout=5)
            else:
                requests.post(NOTIFY_WEBHOOK_URL, json=payload, headers=headers, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")


state_lock = threading.RLock()
state: Dict[str, Any] = {
    "queue": [],
    "current_request": None,
    "scheduled_show_active": False,
    "last_status": {},
    "next_show": None,
    "note": "",
    "background_active": False,
    "fpp_reachable": None,
    "code_visible": False,
    "now_playing": None,
    "falconbeat": {"available": False, "installed": False, "enabled": False, "server_ok": False},
}

# Statistics storage
# STATISTICS_FILE uses a data directory that can be mounted as a volume in Docker
# Falls back to app directory if data directory doesn't exist (for development)
STATISTICS_DIR = os.path.join(os.path.dirname(__file__), "data")
if not os.path.exists(STATISTICS_DIR):
    os.makedirs(STATISTICS_DIR, exist_ok=True)
STATISTICS_FILE = os.path.join(STATISTICS_DIR, "statistics.json")
statistics_lock = threading.RLock()


def _load_code_secret() -> str:
    """Return the secret for the daily code, creating it on first use."""
    if CODE_SECRET:
        return CODE_SECRET
    secret_file = os.path.join(STATISTICS_DIR, "code_secret")
    try:
        with open(secret_file, "r", encoding="utf-8") as f:
            secret = f.read().strip()
        if secret:
            return secret
    except OSError:
        pass
    secret = os.urandom(32).hex()
    try:
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(secret)
        os.chmod(secret_file, 0o600)
    except OSError as exc:
        logger.warning("Could not persist the code secret (%s); the daily code changes on restart.", exc)
    return secret


_CODE_SECRET_VALUE = _load_code_secret() if DAILY_CODE_ENABLED else ""


def daily_code(day: Optional[Any] = None) -> str:
    """The access code of a day: derived from the secret, same for everyone."""
    day = day or dt_datetime.now().astimezone().date()
    digest = hmac.new(_CODE_SECRET_VALUE.encode("utf-8"), day.isoformat().encode("utf-8"), hashlib.sha256).digest()
    return str(int.from_bytes(digest[:8], "big") % (10 ** CODE_MATRIX_DIGITS)).zfill(CODE_MATRIX_DIGITS)

def load_statistics() -> Dict[str, Any]:
    """Load statistics from persistent storage."""
    if not os.path.exists(STATISTICS_FILE):
        return {"show_starts": [], "song_requests": []}
    try:
        with open(STATISTICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load statistics: {e}")
        return {"show_starts": [], "song_requests": []}

def _prune_statistics(stats: Dict[str, Any]) -> None:
    """Drop entries older than STATISTICS_RETENTION_DAYS (0 = keep everything)."""
    if not STATISTICS_RETENTION_DAYS:
        return
    cutoff = (dt_datetime.now() - dt_timedelta(days=STATISTICS_RETENTION_DAYS)).isoformat()
    for key in ("show_starts", "song_requests"):
        entries = stats.get(key)
        if isinstance(entries, list):
            # ISO timestamps sort lexicographically; entries without one are kept.
            stats[key] = [e for e in entries if not isinstance(e, dict) or str(e.get("timestamp") or cutoff) >= cutoff]


def save_statistics(stats: Dict[str, Any]) -> None:
    """Save statistics to persistent storage with atomic write.
    
    Note: Writes immediately on each event. For typical home automation usage with low
    event frequency (few show starts/song requests per hour), this is acceptable.
    For high-traffic scenarios, consider implementing a write buffer.
    """
    try:
        _prune_statistics(stats)
        # Atomic write: write to temp file first, then rename
        temp_file = STATISTICS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, STATISTICS_FILE)
    except Exception as e:
        logger.error(f"Failed to save statistics: {e}")

def log_show_start(playlist: str, playlist_type: str) -> None:
    """Log a show start event."""
    with statistics_lock:
        stats = load_statistics()
        stats["show_starts"].append({
            "timestamp": dt_datetime.now().isoformat(),
            "playlist": playlist,
            "playlist_type": playlist_type
        })
        save_statistics(stats)

def log_song_request(song_title: str, duration: Optional[int]) -> None:
    """Log a song request event."""
    with statistics_lock:
        stats = load_statistics()
        stats["song_requests"].append({
            "timestamp": dt_datetime.now().isoformat(),
            "song_title": song_title,
            "duration": duration
        })
        save_statistics(stats)


def normalize(name: Optional[str]) -> str:
    if isinstance(name, str):
        return name.strip().lower()
    if isinstance(name, dict):
        for key in ["playlist", "name", "title"]:
            if isinstance(name.get(key), str):
                return name[key].strip().lower()
    return str(name or "").strip().lower() if name is not None else ""


def format_duration(duration: Optional[int]) -> str:
    """Format duration in seconds to MM:SS string.
    
    Args:
        duration: Duration in seconds, or None
        
    Returns:
        Formatted string like "3:25" or "unbekannt" if duration is None
    """
    if duration is None:
        return "unbekannt"
    minutes = duration // 60
    seconds = duration % 60
    return f"{minutes}:{seconds:02d}"


def extract_playlist_name(payload: Dict[str, Any]) -> str:
    for key in ["playlist", "current_playlist", "playlist_name"]:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            for inner_key in ["playlist", "name", "title"]:
                inner_value = value.get(inner_key)
                if isinstance(inner_value, str) and inner_value:
                    return inner_value
    return ""


def local_now() -> dt_datetime:
    return dt_datetime.now().astimezone()


def _parse_date(date_str: Optional[str]):
    if not date_str:
        return None
    try:
        return dt_datetime.fromisoformat(date_str).date()
    except ValueError:
        return None


SHOW_START = _parse_date(SHOW_START_DATE)
SHOW_END = _parse_date(SHOW_END_DATE)


def _parse_time(time_str: Optional[str], default_hour: int, default_minute: int) -> dt_time:
    """Parse a time string in HH:MM format."""
    if not time_str:
        return dt_time(hour=default_hour, minute=default_minute)
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return dt_time(hour=hour, minute=minute)
    except (ValueError, IndexError):
        return dt_time(hour=default_hour, minute=default_minute)


SHOW_TIME_START = _parse_time(SHOW_START_TIME, 16, 30)
SHOW_TIME_END = _parse_time(SHOW_END_TIME, 22, 0)


def is_within_show_window(moment: Optional[dt_datetime] = None) -> bool:
    now = moment or local_now()
    current_date = now.date()
    if SHOW_START and current_date < SHOW_START:
        return False
    if SHOW_END and current_date > SHOW_END:
        return False
    return True


def is_quiet_hours(now: Optional[dt_datetime] = None) -> bool:
    """Return True if controls/playback should be disabled for quiet time.

    Quiet hours are outside the configured show time window (SHOW_TIME_START to SHOW_TIME_END).
    """

    current = now or local_now()
    start_t = SHOW_TIME_START.replace(tzinfo=current.tzinfo)
    end_t = SHOW_TIME_END.replace(tzinfo=current.tzinfo)
    current_t = current.timetz()
    # If end is after start (e.g., 16:30 to 22:00), we're in quiet hours if outside that range
    if start_t <= end_t:
        return current_t < start_t or current_t >= end_t
    else:
        # If end is before start (crosses midnight), we're in quiet hours if current >= end and current < start
        return current_t >= end_t and current_t < start_t


DEFAULT_SHOW_SCHEDULE = "17:00=playlist2,18:00=playlist1,19:00=playlist1,20:00=playlist1,21:00=playlist1"


def _parse_show_schedule(raw: Any) -> List[Any]:
    """Parse the show schedule into a sorted list of ``(time, playlist name)``.

    Accepts ``"17:00=playlist2,19:00=playlist1"`` or a list of
    ``{"time": "17:00", "playlist": "playlist2"}``. The playlist is either the
    alias ``playlist1``/``playlist2`` or the literal name of an FPP playlist.
    Invalid entries are skipped with a warning.
    """
    items: List[Any] = []
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                raw = json.loads(text)
            except ValueError:
                logger.warning("Show schedule is not valid JSON: %s", text)
                raw = []
        else:
            for part in text.replace(";", ",").split(","):
                if "=" in part:
                    time_part, playlist_part = part.split("=", 1)
                    items.append({"time": time_part, "playlist": playlist_part})
                elif part.strip():
                    logger.warning("Ignoring show schedule entry without '=': %s", part.strip())
    if isinstance(raw, list):
        items = raw

    aliases = {"playlist1": PLAYLIST_1, "playlist2": PLAYLIST_2}
    schedule = []
    for item in items:
        if not isinstance(item, dict):
            continue
        time_str = str(item.get("time", "")).strip()
        playlist = str(item.get("playlist", "")).strip()
        try:
            hour_str, _, minute_str = time_str.partition(":")
            show_time = dt_time(hour=int(hour_str), minute=int(minute_str or 0))
        except ValueError:
            logger.warning("Ignoring show schedule entry with invalid time: %r", time_str)
            continue
        if not playlist:
            logger.warning("Ignoring show schedule entry without playlist: %r", time_str)
            continue
        schedule.append((show_time, aliases.get(playlist.lower(), playlist)))
    return sorted(schedule, key=lambda entry: entry[0])


SHOW_SCHEDULE = _parse_show_schedule(SHOW_SCHEDULE_RAW) or _parse_show_schedule(DEFAULT_SHOW_SCHEDULE)


def compute_next_show(now: Optional[dt_datetime] = None) -> Dict[str, Any]:
    now = now or local_now()
    if not is_within_show_window(now):
        # If we are before the window, calculate from the first valid day.
        if SHOW_START and now.date() < SHOW_START:
            now = dt_datetime.combine(SHOW_START, dt_time(0, tzinfo=now.tzinfo))
        else:
            return {}

    for day_offset in range(0, 14):
        day = (now + dt_timedelta(days=day_offset)).date()
        if SHOW_START and day < SHOW_START:
            continue
        if SHOW_END and day > SHOW_END:
            break
        for show_time, playlist in SHOW_SCHEDULE:
            candidate = dt_datetime.combine(day, show_time.replace(tzinfo=now.tzinfo))
            if candidate > now:
                return {"time": candidate, "playlist": playlist, "label": playlist}

    return {}


def compute_locks(status: Dict[str, Any], queue: List[Dict[str, Any]], current_request: Any) -> Dict[str, Any]:
    playlist_norm = normalize(status.get("playlist_name"))
    playlist1_norm = normalize(PLAYLIST_1)
    playlist2_norm = normalize(PLAYLIST_2)
    request_norm = normalize(PLAYLIST_REQUESTS)
    temp_norm = normalize("__wish_single__")

    standard_running = status.get("is_running") and playlist_norm in {playlist1_norm, playlist2_norm}
    wish_running = (status.get("is_running") and playlist_norm in {request_norm, temp_norm}) or bool(current_request)
    quiet = is_quiet_hours()
    outside_window = not is_within_show_window()

    # Format show period info for display
    start_time_str = SHOW_TIME_START.strftime("%H:%M")
    end_time_str = SHOW_TIME_END.strftime("%H:%M")
    start_date_str = SHOW_START.strftime("%d.%m.%Y") if SHOW_START else ""
    end_date_str = SHOW_END.strftime("%d.%m.%Y") if SHOW_END else ""

    reason = None
    if outside_window:
        date_range = f"{start_date_str} - {end_date_str}" if start_date_str and end_date_str else ""
        time_range = f"{start_time_str} - {end_time_str}"
        period_info = f"{date_range} | {time_range}" if date_range else time_range
        reason = f"Außerhalb des Showzeitraums\n{period_info}\nAktuell keine Wiedergabe möglich."
    elif quiet:
        reason = f"Ruhezeit {end_time_str}–{start_time_str} – keine Wiedergabe möglich."
    elif standard_running:
        reason = "Aktuell läuft eine Show – alle Aktionen sind gesperrt."
    elif wish_running:
        reason = "Ein Wunsch läuft – Shows können nicht gestartet werden."

    return {
        "disableAllButtons": bool(standard_running or quiet or outside_window),
        "disableShowButtons": bool(standard_running or wish_running or quiet or outside_window),
        "outsideShowWindow": outside_window,
        "quiet": quiet,
        "reason": reason,
        "showPeriod": {
            "startDate": start_date_str,
            "endDate": end_date_str,
            "startTime": start_time_str,
            "endTime": end_time_str,
        },
    }


def _access_code_matches(provided: Any) -> bool:
    """True for the permanent access code or today's code from the matrix."""
    if not ACCESS_REQUIRED:
        return True
    if provided is None:
        return False
    candidate = str(provided).strip().encode("utf-8")
    ok = False
    if ACCESS_CODE:
        ok = hmac.compare_digest(candidate, ACCESS_CODE.encode("utf-8"))
    if DAILY_CODE_ENABLED:
        ok = hmac.compare_digest(candidate, daily_code().encode("utf-8")) or ok
    return ok


_access_failures_lock = threading.Lock()
_access_failures: Dict[str, List[float]] = {}


def _client_id() -> str:
    """Address of the client. Behind a reverse proxy the last X-Forwarded-For
    entry is the one the proxy added itself, so it cannot be spoofed."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.remote_addr or "unknown"


def _access_lockout_remaining(client: str) -> int:
    """Seconds this client still has to wait after too many wrong codes."""
    now = time.monotonic()
    with _access_failures_lock:
        recent = [t for t in _access_failures.get(client, []) if now - t < ACCESS_LOCKOUT_SECONDS]
        if recent:
            _access_failures[client] = recent
        else:
            _access_failures.pop(client, None)
        if len(recent) >= ACCESS_MAX_FAILURES:
            return int(ACCESS_LOCKOUT_SECONDS - (now - recent[0])) + 1
    return 0


def _register_access_failure(client: str) -> None:
    now = time.monotonic()
    with _access_failures_lock:
        if len(_access_failures) > 5000:  # bound memory under a flood
            _access_failures.clear()
        _access_failures.setdefault(client, []).append(now)


def enforce_access_code(payload: Optional[Dict[str, Any]] = None):
    if not ACCESS_REQUIRED:
        return None
    if getattr(g, "_access_checked", False):
        return None  # already verified for this request (before_request)

    client = _client_id()
    wait = _access_lockout_remaining(client)
    if wait:
        minutes = max(1, round(wait / 60))
        response = jsonify({"ok": False, "message": f"Zu viele Fehlversuche. Bitte in {minutes} Min. erneut versuchen.", "retryAfter": wait})
        response.headers["Retry-After"] = str(wait)
        return response, 429

    provided_code = (
        request.headers.get("X-Access-Code")
        or request.headers.get("X-Access-Token")
        or request.args.get("accessCode")
        or request.args.get("access_code")
    )

    if provided_code is None and payload:
        provided_code = payload.get("accessCode") or payload.get("access_code")

    if _access_code_matches(provided_code):
        g._access_checked = True
        return None

    if provided_code:
        _register_access_failure(client)
    return jsonify({"ok": False, "message": "Access code required."}), 403


def _get_cached_payload() -> Dict[str, Any]:
    if hasattr(g, "_cached_json_payload"):
        return g._cached_json_payload
    payload = request.get_json(force=True, silent=True) or {}
    g._cached_json_payload = payload
    return payload

PROTECTED_ENDPOINTS = {("api_show", "POST"), ("api_requests", "POST")}
PROTECTED_PATHS = {"/api/show", "/api/requests"}


@app.before_request
def enforce_access_code_on_control_routes():
    if not ACCESS_REQUIRED:
        return None

    if request.method == "OPTIONS":
        return None

    endpoint = request.endpoint
    if (endpoint, request.method) not in PROTECTED_ENDPOINTS and request.path not in PROTECTED_PATHS:
        return None

    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def fetch_fpp_status() -> Dict[str, Any]:
    resp = requests.get(f"{FPP_BASE_URL}/api/fppd/status", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    name = normalize(payload.get("status_name") or payload.get("status") or "")
    playlist_raw = extract_playlist_name(payload)
    playlist_name = normalize(playlist_raw)
    is_running = name in {"playing", "running", "playing playlist", "playlist"}
    return {
        "is_running": is_running,
        "is_idle": name == "idle",
        "seconds_remaining": _to_int(payload.get("seconds_remaining")),
        "playlist_name": playlist_name,
        "mode_name": payload.get("mode_name") or payload.get("mode"),
        "current_sequence": payload.get("current_sequence") or payload.get("current_song"),
        "playlist_label": playlist_raw,
    }


code_matrix: Optional[CodeMatrix] = None
if DAILY_CODE_ENABLED:
    code_matrix = CodeMatrix(
        FPP_BASE_URL,
        CODE_MATRIX_MODEL,
        color=CODE_MATRIX_COLOR,
        strings=CODE_MATRIX_STRINGS,
        strands_per_string=CODE_MATRIX_STRANDS_PER_STRING,
        orientation=CODE_MATRIX_ORIENTATION,
        start_corner=CODE_MATRIX_START_CORNER,
    )

CODE_DISPLAY_POLL_SECONDS = 1.5      # how quickly the end/start of a song is noticed
CODE_DISPLAY_REFRESH_SECONDS = 30    # re-send the picture (e.g. after an fppd restart)
CODE_DISPLAY_SUPPRESS_SECONDS = 8    # after starting a playlist, until FPP reports "playing"
_code_display_lock = threading.Lock()
# "dirty": the overlay may be switched on at FPP (unknown after a restart or a
# failed request), so it must be switched off before a show takes the matrix.
_code_display = {"shown": None, "shown_at": 0.0, "suppress_until": 0.0, "dirty": True}


def hide_code_display(suppress_seconds: float = CODE_DISPLAY_SUPPRESS_SECONDS) -> None:
    """Remove the code from the matrix (never raises)."""
    if code_matrix is None:
        return
    with _code_display_lock:
        _code_display["suppress_until"] = time.monotonic() + suppress_seconds
        if not _code_display["dirty"]:
            return
        try:
            code_matrix.hide()
            _code_display["dirty"] = False
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Access code could not be removed from the matrix: %s", exc)
        _code_display["shown"] = None
    with state_lock:
        state["code_visible"] = False


def _show_code_display(code: str) -> None:
    with _code_display_lock:
        now = time.monotonic()
        if now < _code_display["suppress_until"]:
            return
        if _code_display["shown"] == code and now - _code_display["shown_at"] < CODE_DISPLAY_REFRESH_SECONDS:
            return
        _code_display["dirty"] = True
        code_matrix.show(code)
        _code_display["shown"] = code
        _code_display["shown_at"] = now
    with state_lock:
        state["code_visible"] = True


def code_display_worker():
    """Show today's code on the matrix whenever FPP is idle during show hours.

    Polls FPP itself (quickly) so the code also appears in the short gap
    between two songs and disappears as soon as anything starts playing,
    including playlists started by FPP's own scheduler.
    """
    try:
        logger.info("Daily access code on %s", code_matrix.describe())
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Access code matrix not ready yet: %s", exc)

    failures = 0
    while True:
        if is_quiet_hours() or not is_within_show_window():
            hide_code_display(suppress_seconds=0)
            time.sleep(20)
            continue
        try:
            status = fetch_fpp_status()
            if status.get("is_idle"):
                _show_code_display(daily_code())
            else:
                hide_code_display(suppress_seconds=0)
            failures = 0
        except (requests.RequestException, ValueError) as exc:
            failures += 1
            if failures in (1, 20) or failures % 400 == 0:
                logger.warning("Access code could not be shown on the matrix: %s", exc)
            with _code_display_lock:
                _code_display["shown"] = None  # unknown state: redraw when FPP is back
            with state_lock:
                state["code_visible"] = False
            time.sleep(min(15, CODE_DISPLAY_POLL_SECONDS * failures))
            continue
        time.sleep(CODE_DISPLAY_POLL_SECONDS)


def start_playlist(name: str) -> None:
    """Start a playlist using documented FPP endpoints.

    Preferred path is the documented ``GET /api/playlist/:PlaylistName/start``.
    For older command-driven flows, fall back to the command API using
    ``Start Playlist`` as described in the commands list.
    """

    # The matrix belongs to the show now: take the access code off first.
    hide_code_display()

    playlist_slug = requests.utils.quote(name, safe="")
    errors: List[str] = []

    # Documented playlist start endpoint.
    try:
        resp = requests.get(
            f"{FPP_BASE_URL}/api/playlist/{playlist_slug}/start", timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return
    except requests.RequestException as exc:
        errors.append(str(exc))

    # Fallback via command API.
    try:
        resp = requests.post(
            f"{FPP_BASE_URL}/api/command/Start%20Playlist/{playlist_slug}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return
    except requests.RequestException as exc:
        errors.append(str(exc))

    raise requests.RequestException("; ".join(errors))


def stop_effects_and_blackout() -> None:
    stop_background_effect()
    for path in ["Effects%20Stop", "Stop%20Now", "Outputs%20Off"]:
        try:
            requests.get(f"{FPP_BASE_URL}/api/command/{path}", timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue

    try:
        requests.get(f"{FPP_BASE_URL}/api/playlists/stop", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass


def stop_background_effect() -> None:
    if not BACKGROUND_EFFECT:
        return
    slug = requests.utils.quote(BACKGROUND_EFFECT, safe="")
    try:
        requests.get(
            f"{FPP_BASE_URL}/api/command/FSEQ%20Effect%20Stop/{slug}",
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        pass
    with state_lock:
        state["background_active"] = False


def start_background_effect() -> None:
    if not BACKGROUND_EFFECT or is_quiet_hours():
        return
    with state_lock:
        if state.get("background_active"):
            return

    slug = requests.utils.quote(BACKGROUND_EFFECT, safe="")
    # Argumente: effect / loop / bg (Playlists haben Vorrang vor dem Effekt)
    try:
        resp = requests.get(
            f"{FPP_BASE_URL}/api/command/FSEQ%20Effect%20Start/{slug}/true/true",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        with state_lock:
            state["background_active"] = True
    except requests.RequestException:
        pass


def resume_background_effect() -> None:
    if is_quiet_hours():
        stop_background_effect()
        return
    start_background_effect()


def delete_playlist(name: str) -> None:
    slug = requests.utils.quote(name, safe="")
    try:
        requests.delete(f"{FPP_BASE_URL}/api/playlist/{slug}", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass


def build_single_song_playlist(entry: Dict[str, Any]) -> str:
    """Create a temporary playlist containing only the requested song.

    Returns the name of the temporary playlist.
    """

    temp_name = "__wish_single__"
    delete_playlist(temp_name)

    seq = entry.get("sequenceName") or entry.get("sequence")
    media = entry.get("mediaName") or entry.get("media")
    duration = entry.get("duration")

    body = {
        "name": temp_name,
        "mainPlaylist": [
            {
                "type": "both" if seq and media else "sequence",
                "enabled": 1,
                "playOnce": 1,
                "sequenceName": seq,
                "mediaName": media,
                "duration": duration,
            }
        ],
        "playlistInfo": {"total_items": 1},
    }

    slug = requests.utils.quote(temp_name, safe="")
    resp = requests.post(
        f"{FPP_BASE_URL}/api/playlist/{slug}", json=body, timeout=REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    return temp_name


def start_request_song(entry: Dict[str, Any]) -> None:
    stop_effects_and_blackout()

    seq = entry.get("sequenceName") or entry.get("sequence")
    media = entry.get("mediaName") or entry.get("media")

    if seq or media:
        playlist_name = build_single_song_playlist(entry)
        start_playlist(playlist_name)
    else:
        # Fallback: play the full wishlist playlist when sequence/media are missing.
        start_playlist(PLAYLIST_REQUESTS)

def update_next_show():
    with state_lock:
        state["next_show"] = compute_next_show()


def mark_note(message: str) -> None:
    with state_lock:
        state["note"] = message


_title_cache_lock = threading.Lock()
_title_cache: Dict[str, Any] = {}
TITLE_CACHE_TTL_SECONDS = 300


def _playlist_titles(playlist: str) -> Dict[str, str]:
    """Map sequence/media file names of a playlist to their display titles (cached)."""
    key = normalize(playlist)
    if not key:
        return {}
    with _title_cache_lock:
        cached = _title_cache.get(key)
        if cached and time.monotonic() - cached["at"] < TITLE_CACHE_TTL_SECONDS:
            return cached["titles"]
    titles: Dict[str, str] = {}
    try:
        slug = requests.utils.quote(playlist, safe="")
        resp = requests.get(f"{FPP_BASE_URL}/api/playlist/{slug}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        entries: List[Any] = []
        if isinstance(data, dict):
            for section in ("leadIn", "mainPlaylist", "leadOut"):
                if isinstance(data.get(section), list):
                    entries.extend(data[section])
        if not entries:
            entries = _extract_entries(data)
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            song = _extract_song(entry, idx)
            for file_name in (song.get("sequenceName"), song.get("mediaName")):
                if file_name:
                    titles[normalize(file_name)] = song["title"]
    except (requests.RequestException, ValueError) as exc:
        logger.debug("Titles of playlist '%s' not available: %s", playlist, exc)
        with _title_cache_lock:
            if key in _title_cache:
                return _title_cache[key]["titles"]
    with _title_cache_lock:
        _title_cache[key] = {"titles": titles, "at": time.monotonic()}
    return titles


def build_now_playing(status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What visitors see as "Jetzt läuft": a readable title and the time left."""
    if not status.get("is_running"):
        return None
    playlist_norm = status.get("playlist_name") or ""
    is_wish = playlist_norm in {normalize(PLAYLIST_REQUESTS), normalize("__wish_single__")}
    sequence = status.get("current_sequence") or ""

    title = ""
    if playlist_norm == normalize("__wish_single__"):
        with state_lock:
            current = state.get("current_request") or {}
        title = _clean_text(current.get("title"))
    if not title and sequence:
        title = _playlist_titles(status.get("playlist_label") or "").get(normalize(sequence), "")
    if not title and sequence:
        # e.g. the temporary wish playlist: look the file up in the wish list
        title = _playlist_titles(PLAYLIST_REQUESTS).get(normalize(sequence), "")
    if not title:
        title = _strip_extension(sequence)

    return {
        "title": title,
        "kind": "wish" if is_wish else "show",
        "secondsRemaining": status.get("seconds_remaining"),
        "updatedAt": time.time(),
    }


status_wake = threading.Event()


def wake_status_worker(delay: float = 3.0) -> None:
    """Ask the status worker to poll FPP soon (after an action changed its state).

    The delay gives FPP time to actually start the playlist; polling too early
    would look like "nothing is running" and end the wish prematurely.
    """
    timer = threading.Timer(delay, status_wake.set)
    timer.daemon = True
    timer.start()


def _status_sleep(active: bool) -> None:
    status_wake.wait(ACTIVE_POLL_INTERVAL_SECONDS if active else POLL_INTERVAL_SECONDS)
    status_wake.clear()


def status_worker():
    update_next_show()
    while True:
        try:
            status = fetch_fpp_status()
        except Exception:
            with state_lock:
                state["fpp_reachable"] = False
                state["now_playing"] = None
            _status_sleep(False)
            continue

        now_playing = build_now_playing(status)

        # Plan actions without holding the lock during network calls.
        action = None
        entry_to_start: Optional[Dict[str, Any]] = None
        delete_temp = False

        with state_lock:
            state["last_status"] = status
            state["fpp_reachable"] = True
            state["now_playing"] = now_playing
            queue: List[Dict[str, Any]] = state["queue"]
            current_request = state.get("current_request")
            scheduled_active = state.get("scheduled_show_active", False)

            playlist_match_requests = normalize(PLAYLIST_REQUESTS) == status.get("playlist_name")
            playlist_match_temp = normalize("__wish_single__") == status.get("playlist_name")

            if status.get("is_running"):
                # If a scheduled show is running, ensure queue is paused.
                if scheduled_active and (playlist_match_requests or playlist_match_temp):
                    # Unexpected playlist; mark for restart after schedule.
                    state["current_request"] = None
                if current_request and not (playlist_match_requests or playlist_match_temp):
                    # request was interrupted
                    state["current_request"] = None
            else:
                delete_temp = True
                # No playlist running: advance queue or resume after schedule.
                if is_quiet_hours():
                    state["current_request"] = None
                    action = "stop_background"
                elif scheduled_active:
                    state["scheduled_show_active"] = False
                    if queue:
                        # resume queued wishes
                        entry_to_start = queue[0]
                        action = "start_entry"
                    else:
                        action = "resume_background"
                elif current_request:
                    # request finished
                    if queue and queue[0] == current_request:
                        queue.pop(0)
                    state["current_request"] = None
                    if queue:
                        entry_to_start = queue[0]
                        action = "start_entry"
                    else:
                        action = "resume_background"
                elif queue and not is_quiet_hours():
                    entry_to_start = queue[0]
                    action = "start_entry"
                else:
                    action = "resume_background"

        # Execute slow operations outside the lock to avoid blocking /api/state.
        if delete_temp:
            delete_playlist("__wish_single__")

        if action == "stop_background":
            stop_background_effect()
        elif action == "resume_background":
            resume_background_effect()
        elif action == "start_entry" and entry_to_start:
            try:
                start_request_song(entry_to_start)
                with state_lock:
                    state["current_request"] = entry_to_start
            except requests.RequestException:
                with state_lock:
                    state["current_request"] = None

        with state_lock:
            active = bool(status.get("is_running") or state["queue"] or state.get("current_request"))
        _status_sleep(active)


def scheduler_worker():
    update_next_show()
    while True:
        # Skip scheduled shows if disabled - use longer sleep since no work is needed
        if not SCHEDULED_SHOWS_ENABLED:
            time.sleep(300)
            continue
        with state_lock:
            info = state.get("next_show")
        now = local_now()
        if info and info.get("time") <= now:
            if is_quiet_hours(info.get("time")):
                update_next_show()
                time.sleep(1)
                continue
            playlist = info.get("playlist")
            with state_lock:
                state["scheduled_show_active"] = True
                state["current_request"] = None
            try:
                stop_effects_and_blackout()
                start_playlist(playlist)
                wake_status_worker()
            except requests.RequestException:
                mark_note("Geplante Show konnte nicht gestartet werden.")
            update_next_show()
        time.sleep(1)


def _send_page(filename: str):
    return send_from_directory(APP_DIR, filename)


_page_cache: Dict[str, Any] = {}


def _render_page(filename: str) -> Response:
    """Serve an HTML page with the site name/description filled into its head."""
    path = os.path.join(APP_DIR, filename)
    mtime = os.path.getmtime(path)
    cached = _page_cache.get(filename)
    if not cached or cached[0] != mtime:
        with open(path, "r", encoding="utf-8") as f:
            page = f.read()
        og_image = ""
        if SITE_IMAGE_URL.startswith(("http://", "https://")):
            og_image = f'  <meta property="og:image" content="{html.escape(SITE_IMAGE_URL, quote=True)}">\n'
        page = (
            page.replace("{{OG_IMAGE}}", og_image)
            .replace("{{SITE_NAME}}", html.escape(SITE_NAME, quote=True))
            .replace("{{SITE_DESCRIPTION}}", html.escape(SITE_DESCRIPTION, quote=True))
        )
        cached = (mtime, page)
        _page_cache[filename] = cached
    response = Response(cached[1], mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.after_request
def add_security_headers(response: Response) -> Response:
    """Everything is served from this origin, so the policy can be strict."""
    host = request.host
    connect = ["'self'", f"ws://{host}", f"wss://{host}"]
    if FALCONBEAT_CLIENT_BASE.startswith(("http://", "https://")):
        origin = "/".join(FALCONBEAT_CLIENT_BASE.split("/")[:3])
        connect += [origin, origin.replace("http", "ws", 1)]
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "media-src 'self' data: blob:; "
        f"connect-src {' '.join(connect)}; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    return response


@app.route("/")
def root():
    return _render_page("index.html")


@app.route("/styles.css")
def styles():
    return _send_page("styles.css")


@app.route("/static/<path:filename>")
def static_files(filename: str):
    """Self-hosted fonts, icons and libraries (nothing is loaded from third parties)."""
    response = send_from_directory(os.path.join(APP_DIR, "static"), filename)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


@app.route("/app.js")
def app_js():
    return _send_page("app.js")


@app.route("/falconbeat-audio.js")
def falconbeat_audio_js():
    return _send_page("falconbeat-audio.js")


@app.route("/donation")
def donation_page():
    return _render_page("donation.html")


@app.route("/requests")
def requests_page():
    # The wish list is a panel on the main page now (keeps audio playing).
    return redirect("/#wunsch", code=302)


@app.route("/statistics")
def statistics_page():
    return _render_page("statistics.html")


@app.route("/config.js")
def config_js():
    response = _send_page("config.js")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/api/access", methods=["POST"])
def api_access():
    """Validate the access code server-side (it is never shipped to the client)."""
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    return jsonify({"ok": True})


def _device_id() -> str:
    """Anonymous id the browser generated for itself (falls back to the address)."""
    raw = request.headers.get("X-Device-Id", "").strip()
    if raw and len(raw) <= 64 and all(c.isalnum() or c == "-" for c in raw):
        return "dev:" + raw
    return "ip:" + _client_id()


def _public_entry(entry: Optional[Dict[str, Any]], device: str) -> Optional[Dict[str, Any]]:
    """Queue entry as sent to browsers: no owner id, only "is it mine"."""
    if not entry:
        return None
    return {
        "title": entry.get("title"),
        "duration": entry.get("duration"),
        "mine": bool(entry.get("owner")) and entry.get("owner") == device,
    }


def _public_queue(info: Dict[str, Any], device: str, now_playing: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Queue for browsers, each entry with its estimated waiting time in seconds."""
    queue = info.get("queue", [])
    current = info.get("current_request")
    # During a main show only the rest of the current song is known, not the
    # rest of the show: no honest estimate possible.
    known = not (now_playing and now_playing.get("kind") == "show")
    wait = 0
    if now_playing:
        remaining = now_playing.get("secondsRemaining")
        wait = remaining if isinstance(remaining, int) else 0
    result = []
    for idx, entry in enumerate(queue):
        public = _public_entry(entry, device)
        is_current = idx == 0 and current is not None and entry.get("title") == current.get("title")
        if is_current:
            public["waitSeconds"] = 0
        else:
            public["waitSeconds"] = wait if known else None
            wait += int(entry.get("duration") or 0)
        result.append(public)
    return result


def _next_show_kind(playlist: Optional[str]) -> Optional[str]:
    if not playlist:
        return None
    if normalize(playlist) == normalize(PLAYLIST_1):
        return "playlist1"
    if normalize(playlist) == normalize(PLAYLIST_2):
        return "playlist2"
    return "other"


@app.route("/api/state")
def api_state():
    with state_lock:
        info = state.copy()
    next_show = info.get("next_show")
    next_show_time = next_show["time"].isoformat() if next_show else None
    locks = compute_locks(info.get("last_status", {}), info.get("queue", []), info.get("current_request"))
    device = _device_id()
    now_playing = info.get("now_playing")
    if now_playing and now_playing.get("secondsRemaining") is not None:
        # Count down from the moment FPP reported it, so the browser needs no clock sync.
        elapsed = max(0, time.time() - now_playing.get("updatedAt", time.time()))
        now_playing = {**now_playing, "secondsRemaining": max(0, int(now_playing["secondsRemaining"] - elapsed))}
    if now_playing:
        now_playing = {k: v for k, v in now_playing.items() if k != "updatedAt"}
    return jsonify(
        {
            "siteName": SITE_NAME,
            "queue": _public_queue(info, device, now_playing),
            "currentRequest": _public_entry(info.get("current_request"), device),
            "nowPlaying": now_playing,
            "limits": {"maxWishesPerDevice": MAX_WISHES_PER_DEVICE, "maxQueueLength": MAX_QUEUE_LENGTH},
            "scheduledShowActive": info.get("scheduled_show_active", False),
            "scheduledShowsEnabled": SCHEDULED_SHOWS_ENABLED,
            "note": info.get("note", ""),
            "status": info.get("last_status", {}),
            "fppReachable": info.get("fpp_reachable"),
            "falconbeat": {"available": bool((info.get("falconbeat") or {}).get("available"))},
            "accessCode": {"onMatrix": DAILY_CODE_ENABLED, "visible": bool(info.get("code_visible"))},
            "nextShow": {
                "time": next_show_time,
                "playlist": next_show.get("playlist") if next_show else None,
                "label": next_show.get("label") if next_show else None,
                "kind": _next_show_kind(next_show.get("playlist")) if next_show else None,
            },
            "locks": locks,
        }
    )


@app.route("/api/show", methods=["POST"])
def api_show():
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    kind = payload.get("type", "playlist1")
    playlist = PLAYLIST_2 if kind == "playlist2" else PLAYLIST_1
    playlist_label = "Hauptshow" if kind == "playlist1" else "Kids-Show"
    
    # Log show start to statistics
    log_show_start(playlist, kind)
    
    # Send notification (before FPP operations, so it works in preview mode too)
    send_notification(
        title=f"{playlist_label} gestartet",
        message=f"Ein Besucher hat '{playlist}' gestartet.",
        action_type="show_start",
        extra_data={"playlist": playlist, "playlist_type": kind}
    )
    
    with state_lock:
        state["scheduled_show_active"] = False
    try:
        stop_effects_and_blackout()
        start_playlist(playlist)
        mark_note(f"Playlist '{playlist}' wurde gestartet.")
        wake_status_worker()
        return jsonify({"ok": True, "message": f"{playlist} gestartet."})
    except requests.RequestException as exc:
        logger.warning("Playlist '%s' could not be started: %s", playlist, exc)
        return jsonify({"ok": False, "message": "Playlist konnte nicht gestartet werden."}), 502


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strip_extension(filename: Any) -> str:
    """'Last Christmas.fseq' -> 'Last Christmas' (only a real file ending is removed)."""
    name = _clean_text(filename)
    stem, dot, ending = name.rpartition(".")
    if dot and stem and ending.isalnum() and len(ending) <= 5:
        return stem.strip()
    return name


def _extract_song(entry: Dict[str, Any], idx: int) -> Dict[str, Any]:
    # Preferred: the entry's "Note" from the FPP playlist editor. Without a
    # note, fall back to the sequence (or media) file name without its ending.
    title = (
        _clean_text(entry.get("note"))
        or _clean_text(entry.get("name"))
        or _clean_text(entry.get("song"))
        or _clean_text(entry.get("title"))
        or _strip_extension(entry.get("sequenceName") or entry.get("sequence"))
        or _strip_extension(entry.get("mediaName") or entry.get("media"))
        or f"Titel {idx + 1}"
    )
    duration = entry.get("duration")
    if duration is None:
        duration = entry.get("seconds") or entry.get("length") or entry.get("time")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    return {
        "title": title,
        "duration": duration,
        "sequenceName": entry.get("sequenceName") or entry.get("sequence"),
        "mediaName": entry.get("mediaName") or entry.get("media"),
    }


def _extract_entries(data: Any) -> List[Dict[str, Any]]:
    """Return playlist entries regardless of FPP schema variants.

    Different FPP versions expose playlist contents under slightly different
    keys/shapes. This helper tries common shapes before falling back to an
    empty list.
    """

    candidates: List[Any] = []

    # Raw list response
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Direct keys on root
        for key in [
            "playlist",
            "entries",
            "sequence",
            "sequences",
            "items",
            "entry",
            "Seqs",
            "mainPlaylist",
        ]:
            if key in data:
                candidates.append(data.get(key))

        # Nested playlist object
        playlist_obj = data.get("playlist") or data.get("Playlist")
        if isinstance(playlist_obj, dict):
            for key in [
                "playlist",
                "entries",
                "sequence",
                "sequences",
                "items",
                "entry",
                "Seqs",
                "mainPlaylist",
            ]:
                if key in playlist_obj:
                    candidates.append(playlist_obj.get(key))

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate

    return []


_song_cache_lock = threading.Lock()
_song_cache: Dict[str, Any] = {"songs": None, "fetched_at": 0.0}


def fetch_request_songs(max_age: float = SONG_CACHE_TTL_SECONDS) -> List[Dict[str, Any]]:
    """Return the songs of the wish playlist (cached briefly).

    Raises ``requests.RequestException`` when FPP is unreachable and no cached
    copy exists.
    """
    with _song_cache_lock:
        cached = _song_cache["songs"]
        if cached is not None and time.monotonic() - _song_cache["fetched_at"] < max_age:
            return cached

    playlist_slug = requests.utils.quote(PLAYLIST_REQUESTS, safe="")
    try:
        resp = requests.get(f"{FPP_BASE_URL}/api/playlist/{playlist_slug}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        entries = _extract_entries(resp.json())
    except (requests.RequestException, ValueError) as exc:
        with _song_cache_lock:
            if _song_cache["songs"] is not None:
                return _song_cache["songs"]
        raise requests.RequestException(str(exc))

    songs = [_extract_song(entry, idx) for idx, entry in enumerate(entries) if isinstance(entry, dict)]
    with _song_cache_lock:
        _song_cache["songs"] = songs
        _song_cache["fetched_at"] = time.monotonic()
    return songs


@app.route("/api/requests/songs")
def api_requests_songs():
    try:
        return jsonify({"songs": fetch_request_songs()})
    except requests.RequestException as exc:
        logger.warning("Wish playlist could not be loaded: %s", exc)
        return jsonify({"songs": [], "error": "Wunschliste konnte nicht geladen werden."}), 502


@app.route("/api/requests", methods=["POST"])
def api_requests():
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    requested_title = payload.get("song")

    if not isinstance(requested_title, str) or not requested_title.strip():
        return jsonify({"ok": False, "message": "song fehlt"}), 400

    if compute_locks(state.get("last_status", {}), [], None).get("disableAllButtons"):
        return jsonify({"ok": False, "message": "Wünsche sind aktuell nicht möglich."}), 409

    # Only songs of the wish playlist may be requested. Sequence/media names
    # and the title always come from FPP, never from the client.
    try:
        songs = fetch_request_songs()
    except requests.RequestException:
        return jsonify({"ok": False, "message": "Wunschliste konnte nicht geladen werden."}), 502

    wanted = normalize(requested_title)
    match = next((song for song in songs if normalize(song.get("title")) == wanted), None)
    if match is None:
        return jsonify({"ok": False, "message": "Dieses Lied steht nicht auf der Wunschliste."}), 400

    title = str(match.get("title"))
    sequence_name = match.get("sequenceName")
    media_name = match.get("mediaName")
    duration = match.get("duration")

    device = _device_id()
    entry = {
        "title": title,
        "sequenceName": sequence_name,
        "mediaName": media_name,
        "duration": duration,
        "owner": device,
    }
    
    # Check for duplicates in current_request and queue
    with state_lock:
        current_request = state.get("current_request")
        queue: List[Dict[str, Any]] = state["queue"]
        
        # Check if song is currently playing
        if current_request and normalize(current_request.get("title")) == normalize(title):
            return jsonify({"ok": False, "message": f"'{title}' wird gerade abgespielt."}), 409
        
        # Check if song is already in queue
        for queued_song in queue:
            if normalize(queued_song.get("title")) == normalize(title):
                return jsonify({"ok": False, "message": f"'{title}' ist bereits in der Warteschlange."}), 409
        
        if MAX_QUEUE_LENGTH and len(queue) >= MAX_QUEUE_LENGTH:
            return jsonify({"ok": False, "message": "Die Warteschlange ist gerade voll. Bitte versuche es nach dem nächsten Lied noch einmal."}), 409
        if MAX_WISHES_PER_DEVICE:
            own = sum(1 for queued_song in queue if queued_song.get("owner") == device)
            if own >= MAX_WISHES_PER_DEVICE:
                limit_text = "ein Wunsch" if MAX_WISHES_PER_DEVICE == 1 else f"{MAX_WISHES_PER_DEVICE} Wünsche"
                return jsonify({"ok": False, "message": f"Du hast schon {limit_text} in der Warteschlange. Sobald einer gespielt wurde, kannst du dir wieder etwas wünschen."}), 409

        queue.append(entry)
        position = len(queue)
        should_start = position == 1 and not state.get("scheduled_show_active", False)
    
    # Log song request to statistics
    log_song_request(title, duration)
    
    # Send notification for song request (before FPP operations, so it works in preview mode too)
    duration_str = format_duration(duration)
    send_notification(
        title=f"Neuer Liedwunsch",
        message=f"Ein Besucher wünscht sich: '{title}' (Dauer: {duration_str})\nPosition in Warteschlange: {position}",
        action_type="song_request",
        extra_data={
            "song_title": title,
            "duration": duration,
            "queue_position": position,
            "sequence_name": sequence_name,
            "media_name": media_name,
        }
    )
    
    if should_start:
        try:
            start_request_song(entry)
            with state_lock:
                state["current_request"] = entry
            wake_status_worker()
        except requests.RequestException as exc:
            logger.warning("Wish could not be started: %s", exc)
            return jsonify({"ok": False, "message": "Wunsch konnte nicht gestartet werden."}), 502
    
    return jsonify({"ok": True, "position": position, "message": f"Wunsch '{title}' wurde hinzugefügt."})


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/statistics")
def api_statistics():
    """Return aggregated statistics for user interactions."""
    with statistics_lock:
        stats = load_statistics()
    
    # Process show starts
    show_starts = stats.get("show_starts", [])
    show_stats = {}
    show_timeline = []
    
    for entry in show_starts:
        playlist = entry.get("playlist", "Unknown")
        if playlist not in show_stats:
            show_stats[playlist] = 0
        show_stats[playlist] += 1
        show_timeline.append({
            "timestamp": entry.get("timestamp"),
            "playlist": playlist,
            "playlist_type": entry.get("playlist_type", "unknown")
        })
    
    # Process song requests
    song_requests = stats.get("song_requests", [])
    song_stats = {}
    song_timeline = []
    
    for entry in song_requests:
        song = entry.get("song_title", "Unknown")
        if song not in song_stats:
            song_stats[song] = {"count": 0, "total_duration": 0}
        song_stats[song]["count"] += 1
        duration = entry.get("duration", 0) or 0
        song_stats[song]["total_duration"] += duration
        song_timeline.append({
            "timestamp": entry.get("timestamp"),
            "song_title": song,
            "duration": duration
        })
    
    # Get top 5 songs
    top_songs = sorted(
        [{"song": k, "count": v["count"], "total_duration": v["total_duration"]} 
         for k, v in song_stats.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:5]
    
    return jsonify({
        "show_starts": {
            "total": len(show_starts),
            "by_playlist": show_stats,
            "timeline": show_timeline
        },
        "song_requests": {
            "total": len(song_requests),
            "by_song": song_stats,
            "timeline": song_timeline,
            "top_5": top_songs
        }
    })


def _normalize_server_url(addr: str) -> str:
    """Turn a plugin ``serverAddr`` (host, host:port, ws://, http://) into an http(s) base URL."""
    addr = (addr or "").strip().rstrip("/")
    if not addr:
        return ""
    lowered = addr.lower()
    if lowered.startswith("wss://"):
        return "https://" + addr[6:]
    if lowered.startswith("ws://"):
        return "http://" + addr[5:]
    if lowered.startswith(("http://", "https://")):
        return addr
    return "http://" + addr


def _falconbeat_plugin_setting(name: str) -> str:
    slug = requests.utils.quote(FALCONBEAT_PLUGIN_NAME, safe="")
    resp = requests.get(f"{FPP_BASE_URL}/api/plugin/{slug}/settings/{name}", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return str(data.get(name, "")) if isinstance(data, dict) else ""


def check_falconbeat() -> Dict[str, Any]:
    """Detect whether synced audio can be offered.

    Available means: the FalconBeat plugin is installed and enabled on FPP
    (skipped in mode "on") and the FalconBeat server answers ``/health``.
    """
    result = {"available": False, "installed": False, "enabled": False, "server_ok": False}
    if FALCONBEAT_MODE == "off" or PREVIEW_MODE:
        return result

    server_url = _normalize_server_url(FALCONBEAT_SERVER_URL)

    if FALCONBEAT_MODE == "on":
        result["installed"] = result["enabled"] = True
    else:
        resp = requests.get(f"{FPP_BASE_URL}/api/plugin", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        plugins = resp.json()
        names = {normalize(p) for p in plugins} if isinstance(plugins, list) else set()
        result["installed"] = normalize(FALCONBEAT_PLUGIN_NAME) in names
        if not result["installed"]:
            return result
        result["enabled"] = _parse_bool(_falconbeat_plugin_setting("enabled"), False)
        if not result["enabled"]:
            return result
        if not server_url:
            server_url = _normalize_server_url(_falconbeat_plugin_setting("serverAddr"))

    if not server_url:
        return result

    health = requests.get(f"{server_url}/health", timeout=REQUEST_TIMEOUT)
    result["server_ok"] = health.ok
    result["available"] = bool(result["installed"] and result["enabled"] and result["server_ok"])
    return result


def falconbeat_worker():
    last_logged: Optional[bool] = None
    while True:
        try:
            result = check_falconbeat()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("FalconBeat check failed: %s", exc)
            result = {"available": False, "installed": False, "enabled": False, "server_ok": False}
        with state_lock:
            state["falconbeat"] = result
        if result["available"] != last_logged:
            logger.info("FalconBeat audio %s (%s)", "available" if result["available"] else "not available", result)
            last_logged = result["available"]
        time.sleep(FALCONBEAT_CHECK_INTERVAL_SECONDS)


def boot_threads():
    threading.Thread(target=status_worker, daemon=True).start()
    threading.Thread(target=scheduler_worker, daemon=True).start()
    if FALCONBEAT_MODE != "off":
        threading.Thread(target=falconbeat_worker, daemon=True).start()
    if code_matrix is not None:
        threading.Thread(target=code_display_worker, daemon=True).start()


boot_threads()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
