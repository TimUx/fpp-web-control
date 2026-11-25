import hashlib
import hmac
import html
import json
import logging
import os
import re
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
import i18n

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

# Empty name/description = the default text in the visitor's language.
SITE_NAME = str(_cfg("siteName", "SITE_NAME", "")).strip()
# Shown in search results and link previews (WhatsApp, Signal, ...)
SITE_DESCRIPTION = str(_cfg("siteDescription", "SITE_DESCRIPTION", "")).strip()
# Language of the pages: "auto" = the visitor's browser language (with a
# switch on the page), or a fixed code such as "en" or "de". DEFAULT_LANGUAGE
# is used when the browser asks for a language there is no translation for,
# and for notifications to the operator.
LANGUAGE_SETTING = str(_cfg("language", "APP_LANGUAGE", "auto")).strip().lower() or "auto"
DEFAULT_LANGUAGE = i18n.normalize_language(_cfg("defaultLanguage", "APP_DEFAULT_LANGUAGE", "en")) or "en"
FIXED_LANGUAGE = None if LANGUAGE_SETTING == "auto" else i18n.normalize_language(LANGUAGE_SETTING)
LANGUAGE_COOKIE = "fpp-lang"
# Optional absolute URL of a preview picture for shared links
SITE_IMAGE_URL = str(_cfg("siteImageUrl", "SITE_IMAGE_URL", "")).strip()
FPP_BASE_URL = str(_cfg("fppBaseUrl", "FPP_BASE_URL", "http://fpp.local"))
PLAYLIST_1 = str(_cfg("playlist1", "FPP_PLAYLIST_1", "show 1"))
PLAYLIST_2 = str(_cfg("playlist2", "FPP_PLAYLIST_2", "show 2"))
BUTTON_PLAYLIST_1 = str(_cfg("buttonPlaylist1Text", "BUTTON_PLAYLIST_1", "")).strip()
BUTTON_PLAYLIST_2 = str(_cfg("buttonPlaylist2Text", "BUTTON_PLAYLIST_2", "")).strip()
# Any number of show buttons, each starting one FPP playlist. Either
# "Show=Start the show|Kids=Kids' show" (PLAYLIST=LABEL, separated by "|" or
# new lines; the label may be left out) or a JSON list of
# {"playlist": "Kids", "label": "Kids' show", "name": "kids' show", "icon": "child-reaching"};
# "special": true gives a button a quieter colour (side shows next to the main ones).
# Empty = the two classic buttons from FPP_PLAYLIST_1/_2 and BUTTON_PLAYLIST_1/_2.
SHOWS_RAW = _cfg("shows", "FPP_SHOWS", "")
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
# Nothing may be started that would run past the end of the daily show time
# by more than this many minutes, counting what is already playing and the
# wishes waiting in the queue.
SHOW_END_CHECK = _parse_bool(_cfg("showEndCheck", "FPP_SHOW_END_CHECK", "true"), True)
try:
    SHOW_END_TOLERANCE_MINUTES = max(0.0, float(_cfg("showEndToleranceMinutes", "FPP_SHOW_END_TOLERANCE_MINUTES", "5") or 0))
except (TypeError, ValueError):
    SHOW_END_TOLERANCE_MINUTES = 5.0
# Speaker volume at FPP (0-100), set by this app. SHOW_VOLUME applies when a
# show or wish song starts: one number ("80") or any number of periods
# ("16:00-18:00=90,18:00-20:00=75,20:00-21:00=50"). IDLE_VOLUME applies once
# everything is over and the background effect runs again. Empty = the app
# leaves the volume alone.
SHOW_VOLUME_RAW = _cfg("showVolume", "FPP_SHOW_VOLUME", "")
IDLE_VOLUME_RAW = str(_cfg("idleVolume", "FPP_IDLE_VOLUME", "")).strip()
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
# Optional lead-in before every wish. FalconBeat uploads the song when the wish
# playlist starts, so the lead-in is the time visitors' phones have to download
# it before the first note. Either a short sequence (its own length applies),
# optionally with its own music file, or, without one, a plain pause of N
# seconds. Both empty/0 = no lead-in.
WISH_LEAD_IN_SEQUENCE = str(_cfg("wishLeadInSequence", "FPP_WISH_LEAD_IN_SEQUENCE", "")).strip()
WISH_LEAD_IN_MEDIA = str(_cfg("wishLeadInMedia", "FPP_WISH_LEAD_IN_MEDIA", "")).strip()
try:
    WISH_LEAD_IN_SECONDS = max(0, min(60, int(float(_cfg("wishLeadInSeconds", "FPP_WISH_LEAD_IN_SECONDS", "0") or 0))))
except (TypeError, ValueError):
    WISH_LEAD_IN_SECONDS = 0

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
# Secret for switching the app's control of FPP off and on (/api/control),
# e.g. from FPP itself with a "URL" command. Empty = the switch is disabled.
CONTROL_TOKEN = str(_cfg("controlToken", "CONTROL_TOKEN", "")).strip()
# Test mode (/api/control/test/on): shows and wishes work outside the show
# times too, for this many minutes; then it switches itself off.
try:
    TEST_MODE_MINUTES = min(720, max(1, int(float(_cfg("testModeMinutes", "TEST_MODE_MINUTES", "60") or 60))))
except (TypeError, ValueError):
    TEST_MODE_MINUTES = 60
DAILY_CODE_ENABLED = bool(CODE_MATRIX_MODEL) and not PREVIEW_MODE
# During the wish lead-in the title of the wish runs across the same matrix.
WISH_TITLE_ON_MATRIX = _parse_bool(_cfg("wishTitleOnMatrix", "FPP_WISH_TITLE_ON_MATRIX", "false"), False)
_wish_title_color_raw = str(_cfg("wishTitleColor", "FPP_WISH_TITLE_COLOR", "")).strip()
WISH_TITLE_COLOR = parse_color(_wish_title_color_raw, CODE_MATRIX_COLOR) if _wish_title_color_raw else CODE_MATRIX_COLOR
WISH_TITLE_DEFAULT_SECONDS = 8   # lead-in length when FPP cannot tell it
WISH_TITLE_END_MARGIN_SECONDS = 0.6  # the matrix is free again this long before the song
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
        "site_name": site_name(operator_language()),
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
            logger.error("Failed to send ntfy notification: Timeout after 5 seconds")
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
    # The app stopped the background for a show/wish and owes a restart, also
    # when that show ends outside the show times.
    "background_owed": False,
    # Last volume the app set: phase ("show"/"idle", None = not yet), the
    # value and the song it was set for.
    "volume_phase": None,
    "volume_value": None,
    "volume_song": None,
    # False = manual mode: the operator runs FPP by hand, the app keeps out
    # (no shows, wishes, schedule, background, volume or matrix code).
    "control_enabled": True,
    "control_since": None,
    # Test mode runs until this moment (None = off): the show times are
    # ignored, so the buttons and wishes can be tried out live.
    "test_until": None,
    # Playing time of each show button in seconds ({"playlist1": 1260}),
    # read from the FPP playlists; shown on the buttons.
    "show_seconds": {},
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
CONTROL_FILE = os.path.join(STATISTICS_DIR, "control.json")


def _load_control() -> None:
    """Restore the manual-mode and test-mode switches after a restart."""
    try:
        with open(CONTROL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    if data.get("enabled") is False:
        state["control_enabled"] = False
        state["control_since"] = data.get("since")
        logger.info("Manual mode is on (since %s): the app leaves FPP alone.", data.get("since"))
    try:
        until = dt_datetime.fromisoformat(str(data.get("testUntil") or ""))
    except ValueError:
        until = None
    if until is not None and until.tzinfo is not None and until > local_now():
        state["test_until"] = until
        logger.info("Test mode is on until %s.", until.isoformat(timespec="minutes"))


def _save_control() -> None:
    with state_lock:
        until = state.get("test_until")
        data = {
            "enabled": bool(state.get("control_enabled", True)),
            "since": state.get("control_since"),
            "testUntil": until.isoformat(timespec="seconds") if until else None,
        }
    try:
        with open(CONTROL_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(CONTROL_FILE + ".tmp", CONTROL_FILE)
    except OSError as exc:
        logger.warning("Could not save the control switches (%s); they reset on restart.", exc)


def control_enabled() -> bool:
    with state_lock:
        return bool(state.get("control_enabled", True))


def test_mode_until() -> Optional[dt_datetime]:
    """End of the running test mode, None if it is off (or over)."""
    with state_lock:
        until = state.get("test_until")
    return until if until is not None and until > local_now() else None


def test_mode_active() -> bool:
    return test_mode_until() is not None


def outside_show_time(now: Optional[dt_datetime] = None) -> bool:
    """True outside the show period or in the quiet hours (ignoring test mode)."""
    return is_quiet_hours(now) or not is_within_show_window(now)


def quiet_now() -> bool:
    """Quiet hours, unless test mode lets shows and wishes run anyway."""
    return is_quiet_hours() and not test_mode_active()


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

def _test_run() -> bool:
    """Only possible because of test mode: kept out of the statistics."""
    return test_mode_active() and outside_show_time()


def log_show_start(playlist: str, playlist_type: str) -> None:
    """Log a show start event."""
    if _test_run():
        return
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
    if _test_run():
        return
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


def operator_language() -> str:
    """Language for things no browser asks for (notifications)."""
    return FIXED_LANGUAGE or DEFAULT_LANGUAGE


def request_language() -> str:
    """Language for the current request: fixed setting, the visitor's own
    choice (cookie), their browser language, then DEFAULT_LANGUAGE."""
    if FIXED_LANGUAGE:
        return FIXED_LANGUAGE
    try:
        cached = getattr(g, "_language", None)
    except RuntimeError:  # no request context (worker threads)
        return operator_language()
    if cached:
        return cached
    lang = (
        i18n.normalize_language(request.cookies.get(LANGUAGE_COOKIE))
        or i18n.from_accept_language(request.headers.get("Accept-Language"))
        or DEFAULT_LANGUAGE
    )
    g._language = lang
    return lang


def t(key: str, **params: Any) -> str:
    """Translate for the visitor of the current request."""
    return i18n.translate(request_language(), key, **params)


def site_name(lang: str) -> str:
    return SITE_NAME or i18n.translate(lang, "site.defaultName")


def site_description(lang: str) -> str:
    return SITE_DESCRIPTION or i18n.translate(lang, "site.defaultDescription")


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


_load_control()


def _sprite_icons() -> set:
    try:
        with open(os.path.join(APP_DIR, "static", "icons.svg"), encoding="utf-8") as f:
            return set(re.findall(r'<symbol id="([\w-]+)"', f.read()))
    except OSError:
        return {"star", "child-reaching"}


SHOW_ICONS = _sprite_icons()
DEFAULT_SHOW_ICONS = ("star", "child-reaching")


def _parse_shows(raw: Any) -> List[Dict[str, Any]]:
    """The show buttons: [{"id": "playlist1", "playlist", "label", "name", "icon", "special"}, ...]."""
    items: List[Any] = []
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                raw = json.loads(text)
            except ValueError:
                logger.warning("FPP_SHOWS is not valid JSON: %s", text)
                raw = []
        else:
            for part in re.split(r"[|\n]", text):
                part = part.strip()
                if not part:
                    continue
                playlist, _, label = part.partition("=")
                items.append({"playlist": playlist, "label": label})
    if isinstance(raw, list):
        items = [item if isinstance(item, dict) else {"playlist": item} for item in raw]
    shows = []
    for item in items:
        playlist = str(item.get("playlist") or "").strip()
        if not playlist:
            logger.warning("Ignoring show without playlist: %r", item)
            continue
        position = len(shows)
        icon = str(item.get("icon") or "").strip()
        if icon not in SHOW_ICONS:
            if icon:
                logger.warning("Unknown icon '%s' for show '%s' (available: %s)", icon, playlist, ", ".join(sorted(SHOW_ICONS)))
            icon = DEFAULT_SHOW_ICONS[position] if position < len(DEFAULT_SHOW_ICONS) else "star"
        shows.append({
            "id": f"playlist{position + 1}",
            "playlist": playlist,
            "label": str(item.get("label") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "icon": icon,
            "special": _parse_bool(item.get("special")),
        })
    return shows


SHOWS = _parse_shows(SHOWS_RAW)
LEGACY_SHOWS = not SHOWS
if LEGACY_SHOWS:
    # The two classic buttons; their default texts keep their old wording.
    SHOWS = [
        {"id": "playlist1", "playlist": PLAYLIST_1, "label": BUTTON_PLAYLIST_1, "name": "", "icon": "star", "special": False},
        {"id": "playlist2", "playlist": PLAYLIST_2, "label": BUTTON_PLAYLIST_2, "name": "", "icon": "child-reaching", "special": False},
    ]
SHOWS_BY_ID = {show["id"]: show for show in SHOWS}


def show_for_playlist(playlist: Optional[str]) -> Optional[Dict[str, Any]]:
    wanted = normalize(playlist)
    return next((show for show in SHOWS if normalize(show["playlist"]) == wanted), None) if wanted else None


def show_label(show: Dict[str, Any], lang: str) -> str:
    """Text on the button."""
    if show["label"]:
        return show["label"]
    if LEGACY_SHOWS:
        return i18n.translate(lang, f"button.{show['id']}")
    return i18n.translate(lang, "button.startPlaylist", playlist=show["playlist"])


def show_name(show: Dict[str, Any], lang: str) -> str:
    """Short name of a show for "Next …" ("" = none given)."""
    if show["name"]:
        return show["name"]
    if LEGACY_SHOWS and show["id"] == "playlist2":
        return i18n.translate(lang, "show.kidsName")
    return ""


DEFAULT_SHOW_SCHEDULE = "17:00=playlist2,18:00=playlist1,19:00=playlist1,20:00=playlist1,21:00=playlist1"


def _parse_show_schedule(raw: Any) -> List[Any]:
    """Parse the show schedule into a sorted list of ``(time, playlist name)``.

    Accepts ``"17:00=playlist2,19:00=playlist1"`` or a list of
    ``{"time": "17:00", "playlist": "playlist2"}``. The playlist is either the
    button alias ``playlist1``, ``playlist2`` … or the name of an FPP playlist.
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

    aliases = {show["id"]: show["playlist"] for show in SHOWS}
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


def _parse_volume(raw: str) -> Optional[int]:
    try:
        value = int(float(str(raw).strip().rstrip("%")))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, value))


def _parse_clock(text: str) -> dt_time:
    """"16", "16:30" or "16.30"."""
    parts = text.strip().replace(".", ":").split(":", 1)
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return dt_time(hour % 24, minute)


def _parse_volume_schedule(raw: Any) -> List[Any]:
    """Volume by time of day, as (start, end, volume) periods.

    "80"                                   -> always 80
    "16:00-18:00=90,18:00-20:00=75,20:00-21:00=50"
                                           -> any number of periods; a start
                                              outside all of them leaves the
                                              volume alone
    "16:30=80,19:30=60"                    -> from-times, each until the next
    config.json may also hold a list: [{"from": "16:00", "to": "18:00", "volume": 90}]
    """
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict):
                span = f"{item.get('from', '')}-{item.get('to', '')}" if item.get("to") else str(item.get("from", ""))
                parts.append(f"{span}={item.get('volume', '')}")
        raw = ",".join(parts)
    raw = str(raw).strip()
    if "=" not in raw:
        value = _parse_volume(raw)
        return [(None, None, value)] if value is not None else []
    periods: List[Any] = []
    starts: List[Any] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            when, value = part.split("=", 1)
            volume = _parse_volume(value)
            if volume is None:
                raise ValueError(value)
            if "-" in when:
                start, end = (_parse_clock(x) for x in when.split("-", 1))
                periods.append((start, end, volume))
            else:
                starts.append((_parse_clock(when), volume))
        except ValueError:
            logger.warning("Ignoring volume entry '%s' (expected e.g. 16:00-18:00=90)", part)
    # From-times run until the next one (the last until the first next day).
    starts.sort(key=lambda e: e[0])
    for i, (start, volume) in enumerate(starts):
        periods.append((start, starts[(i + 1) % len(starts)][0], volume))
    return periods


SHOW_VOLUME_SCHEDULE = _parse_volume_schedule(SHOW_VOLUME_RAW)
IDLE_VOLUME = _parse_volume(IDLE_VOLUME_RAW) if IDLE_VOLUME_RAW else None


def _in_period(current: dt_time, start: dt_time, end: dt_time) -> bool:
    if start == end:
        return True  # a single from-time covers the whole day
    if start < end:
        return start <= current < end
    return current >= start or current < end  # crosses midnight


def show_volume(now: Optional[dt_datetime] = None) -> Optional[int]:
    """Volume for a show/wish song starting now (None = leave it alone)."""
    current = (now or local_now()).time()
    for start, end, volume in SHOW_VOLUME_SCHEDULE:
        if start is None or _in_period(current, start, end):
            return volume
    return None


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
    show_playlists = {normalize(show["playlist"]) for show in SHOWS}
    request_norm = normalize(PLAYLIST_REQUESTS)
    temp_norm = normalize("__wish_single__")

    standard_running = status.get("is_running") and playlist_norm in show_playlists
    wish_running = (status.get("is_running") and playlist_norm in {request_norm, temp_norm}) or bool(current_request)
    testing = test_mode_active()
    quiet = is_quiet_hours() and not testing
    outside_window = not is_within_show_window() and not testing

    # Format show period info for display
    lang = request_language()
    start_time_str = i18n.format_time(SHOW_TIME_START, lang)
    end_time_str = i18n.format_time(SHOW_TIME_END, lang)
    start_date_str = i18n.format_date(SHOW_START, lang) if SHOW_START else ""
    end_date_str = i18n.format_date(SHOW_END, lang) if SHOW_END else ""

    reason = None
    if not state.get("control_enabled", True):
        return {
            "disableAllButtons": True,
            "disableShowButtons": True,
            "outsideShowWindow": outside_window,
            "quiet": quiet,
            "manual": True,
            "test": False,
            "reason": t("locks.manual"),
            "showPeriod": {
                "startDate": start_date_str,
                "endDate": end_date_str,
                "startTime": start_time_str,
                "endTime": end_time_str,
            },
        }
    if outside_window:
        date_range = f"{start_date_str} - {end_date_str}" if start_date_str and end_date_str else ""
        time_range = f"{start_time_str} - {end_time_str}"
        period_info = f"{date_range} | {time_range}" if date_range else time_range
        reason = t("locks.outsideWindow", period=period_info)
    elif quiet:
        reason = t("locks.quiet", end=end_time_str, start=start_time_str)
    elif standard_running:
        reason = t("locks.showRunning")
    elif wish_running:
        reason = t("locks.wishRunning")

    return {
        "disableAllButtons": bool(standard_running or quiet or outside_window),
        "disableShowButtons": bool(standard_running or wish_running or quiet or outside_window),
        "outsideShowWindow": outside_window,
        "quiet": quiet,
        "manual": False,
        "test": testing,
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
        response = jsonify({"ok": False, "message": t("access.tooManyMinutes", minutes=minutes), "retryAfter": wait})
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
    return jsonify({"ok": False, "message": t("access.required")}), 403


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
        if (outside_show_time() and not test_mode_active()) or not control_enabled():
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
    cancel_wish_title()
    hide_code_display()
    set_fpp_volume(show_volume(), "show")

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
    cancel_wish_title()
    stop_background_effect()
    with state_lock:
        state["background_owed"] = bool(BACKGROUND_EFFECT)
    for path in ["Effects%20Stop", "Stop%20Now", "Outputs%20Off"]:
        try:
            requests.get(f"{FPP_BASE_URL}/api/command/{path}", timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue

    try:
        requests.get(f"{FPP_BASE_URL}/api/playlists/stop", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass


def set_fpp_volume(volume: Optional[int], phase: str, song: Optional[str] = None) -> None:
    """Set the speaker volume at FPP and remember which phase it is for."""
    if volume is None:
        return
    try:
        resp = requests.post(
            f"{FPP_BASE_URL}/api/system/volume", json={"volume": volume}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Volume could not be set to %s%%: %s", volume, exc)
        return
    with state_lock:
        state["volume_phase"] = phase
        state["volume_value"] = volume
        state["volume_song"] = song
    logger.info("Volume set to %s%% (%s)", volume, phase)


def background_effect_running() -> Optional[bool]:
    """Ask FPP whether the background effect runs (None = unknown)."""
    try:
        resp = requests.get(f"{FPP_BASE_URL}/api/fppd/effects", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        running = resp.json().get("runningEffects")
    except (requests.RequestException, ValueError, AttributeError):
        return None
    if not isinstance(running, list):
        return None
    wanted = normalize(os.path.splitext(BACKGROUND_EFFECT)[0])
    return any(
        normalize(os.path.splitext(str((e or {}).get("name", "")))[0]) == wanted
        for e in running
        if isinstance(e, dict)
    )


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
    if not BACKGROUND_EFFECT:
        return
    # Ask FPP rather than trust our own flag: after an fppd restart the
    # effect is gone while the flag still says it runs.
    running = background_effect_running()
    if running is None:
        with state_lock:
            running = bool(state.get("background_active"))
    if running:
        with state_lock:
            state["background_active"] = True
            state["background_owed"] = False
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
            state["background_owed"] = False
    except requests.RequestException:
        pass


def resume_background_effect() -> None:
    """Everything is over. Within the show times the background always runs;
    outside them it is left alone (FPP may run it as normal Christmas lights
    until late), except that a background the app stopped for its own show
    or wish is put back."""
    with state_lock:
        owed = bool(state.get("background_owed"))
        phase = state.get("volume_phase")
    if phase != "idle":
        set_fpp_volume(IDLE_VOLUME, "idle")
    if is_quiet_hours() and not owed:
        return
    start_background_effect()


def delete_playlist(name: str) -> None:
    slug = requests.utils.quote(name, safe="")
    try:
        requests.delete(f"{FPP_BASE_URL}/api/playlist/{slug}", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass


def wish_lead_in_entry() -> Optional[Dict[str, Any]]:
    """Playlist entry played before a wish (configured sequence or pause), if any."""
    if WISH_LEAD_IN_SEQUENCE:
        name = WISH_LEAD_IN_SEQUENCE
        if not name.lower().endswith(".fseq"):
            name += ".fseq"
        if WISH_LEAD_IN_MEDIA:
            return {
                "type": "both", "enabled": 1, "playOnce": 0,
                "sequenceName": name, "mediaName": WISH_LEAD_IN_MEDIA,
            }
        return {"type": "sequence", "enabled": 1, "playOnce": 0, "sequenceName": name}
    if WISH_LEAD_IN_SECONDS > 0:
        return {"type": "pause", "enabled": 1, "playOnce": 0, "duration": WISH_LEAD_IN_SECONDS}
    return None


_lead_in_seconds_cache: Dict[str, Any] = {"value": None, "at": 0.0}


def wish_lead_in_seconds() -> float:
    """How long the lead-in lasts. A sequence is asked from FPP (cached);
    if that fails, the configured seconds or a default are assumed."""
    entry = wish_lead_in_entry()
    if not entry:
        return 0.0
    if entry["type"] == "pause":
        return float(WISH_LEAD_IN_SECONDS)
    cached = _lead_in_seconds_cache
    if cached["value"] is not None and time.monotonic() - cached["at"] < 600:
        return cached["value"]
    fallback = float(WISH_LEAD_IN_SECONDS or WISH_TITLE_DEFAULT_SECONDS)
    try:
        slug = requests.utils.quote(entry["sequenceName"], safe="")
        resp = requests.get(f"{FPP_BASE_URL}/api/sequence/{slug}/meta", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        meta = resp.json()
        seconds = float(meta["NumFrames"]) * float(meta["StepTime"]) / 1000.0
        if not 0.5 <= seconds <= 120:
            raise ValueError(f"implausible length {seconds}")
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Length of the wish lead-in '%s' unknown (%s), assuming %.0fs",
                       entry["sequenceName"], exc, fallback)
        return fallback  # not cached: ask again next time
    cached["value"] = seconds
    cached["at"] = time.monotonic()
    return seconds


_wish_title_lock = threading.Lock()
_wish_title: Dict[str, Any] = {"token": 0, "thread": None}


def cancel_wish_title() -> None:
    """Stop a running title text (something else is about to use the matrix)."""
    with _wish_title_lock:
        _wish_title["token"] += 1


def show_wish_title(title: str, seconds: float) -> None:
    """Run the title of a wish across the matrix for the length of the lead-in.

    Returns at once; the text is drawn by a background thread and ends on its
    own, a little before the song starts, or as soon as it is cancelled.
    """
    if code_matrix is None or not WISH_TITLE_ON_MATRIX or not _clean_text(title):
        return
    duration = min(60.0, seconds) - WISH_TITLE_END_MARGIN_SECONDS
    if duration < 1.5:
        return
    with _wish_title_lock:
        _wish_title["token"] += 1
        token = _wish_title["token"]
        previous = _wish_title["thread"]

    def run() -> None:
        # A cancelled text gives the matrix back when it ends: let it finish
        # first, or it would switch this one off again.
        if previous is not None and previous.is_alive():
            previous.join(timeout=5)
        try:
            frames = code_matrix.scroll(
                title, duration, color=WISH_TITLE_COLOR,
                should_stop=lambda: _wish_title["token"] != token,
            )
            logger.info("Wish title on the matrix: '%s', %d frames in %.1fs", title, frames, duration)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Wish title could not be shown on the matrix: %s", exc)
            with _code_display_lock:
                _code_display["dirty"] = True  # the overlay may still be on: let the code worker clear it
        finally:
            with _code_display_lock:
                _code_display["shown"] = None  # the matrix was overwritten: redraw the code when idle

    thread = threading.Thread(target=run, daemon=True, name="wish-title")
    with _wish_title_lock:
        _wish_title["thread"] = thread
    thread.start()


def build_single_song_playlist(entry: Dict[str, Any]) -> str:
    """Create a temporary playlist containing only the requested song,
    preceded by the optional lead-in.

    Returns the name of the temporary playlist.
    """

    temp_name = "__wish_single__"
    delete_playlist(temp_name)

    seq = entry.get("sequenceName") or entry.get("sequence")
    media = entry.get("mediaName") or entry.get("media")
    duration = entry.get("duration")

    items: List[Dict[str, Any]] = [
        {
            "type": "both" if seq and media else "sequence",
            "enabled": 1,
            "playOnce": 1,
            "sequenceName": seq,
            "mediaName": media,
            "duration": duration,
        }
    ]
    # Only worth the wait when there is audio to download.
    lead_in = wish_lead_in_entry() if media else None
    if lead_in:
        items.insert(0, lead_in)

    body = {
        "name": temp_name,
        "mainPlaylist": items,
        "playlistInfo": {"total_items": len(items)},
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
        # Ask before the start, so the text begins together with the lead-in.
        title_seconds = wish_lead_in_seconds() if (media and WISH_TITLE_ON_MATRIX and code_matrix is not None) else 0.0
        start_playlist(playlist_name)
        if title_seconds:
            show_wish_title(entry.get("title") or "", title_seconds)
    else:
        # Fallback: play the full wishlist playlist when sequence/media are missing.
        start_playlist(PLAYLIST_REQUESTS)

def update_next_show():
    with state_lock:
        state["next_show"] = compute_next_show()


def mark_note(key: str, **params: Any) -> None:
    """A short note for every visitor, translated when it is shown."""
    with state_lock:
        state["note"] = {"key": key, "params": params}


def _note_text(note: Any) -> str:
    if isinstance(note, dict) and note.get("key"):
        return t(note["key"], **(note.get("params") or {}))
    return str(note or "")


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


_plan_cache: Dict[str, Any] = {}


def playlist_plan(playlist: str) -> Optional[List[Dict[str, Any]]]:
    """Entries of a playlist in play order with their length in seconds
    (lead-in, main part, lead-out; cached). None if FPP can't be asked."""
    key = normalize(playlist)
    if not key:
        return None
    with _title_cache_lock:
        cached = _plan_cache.get(key)
        if cached and time.monotonic() - cached["at"] < TITLE_CACHE_TTL_SECONDS:
            return cached["plan"]
    try:
        slug = requests.utils.quote(playlist, safe="")
        resp = requests.get(f"{FPP_BASE_URL}/api/playlist/{slug}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.debug("Playlist '%s' not available: %s", playlist, exc)
        return cached["plan"] if cached else None
    entries: List[Any] = []
    if isinstance(data, dict):
        for section in ("leadIn", "mainPlaylist", "leadOut"):
            if isinstance(data.get(section), list):
                entries.extend(data[section])
    if not entries:
        entries = _extract_entries(data)
    plan = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("enabled") in (0, "0", False):
            continue
        try:
            seconds = float(entry.get("duration") or 0)
        except (TypeError, ValueError):
            seconds = 0.0
        plan.append({
            "files": {
                normalize(_strip_extension(entry.get(k)))
                for k in ("sequenceName", "mediaName")
                if entry.get(k)
            },
            "seconds": max(0.0, seconds),
        })
    with _title_cache_lock:
        _plan_cache[key] = {"plan": plan, "at": time.monotonic()}
    return plan


def playlist_seconds(playlist: str) -> Optional[float]:
    plan = playlist_plan(playlist)
    if not plan:
        return None
    return sum(e["seconds"] for e in plan)


_show_seconds_checked = {"at": 0.0}
SHOW_SECONDS_REFRESH_SECONDS = 60


def refresh_show_seconds(force: bool = False) -> None:
    """Read the playing time of every show playlist (at most once a minute;
    the playlists themselves are cached for TITLE_CACHE_TTL_SECONDS)."""
    now = time.monotonic()
    if not force and now - _show_seconds_checked["at"] < SHOW_SECONDS_REFRESH_SECONDS:
        return
    _show_seconds_checked["at"] = now
    seconds: Dict[str, int] = {}
    for show in SHOWS:
        total = playlist_seconds(show["playlist"])
        if total and total > 0:
            seconds[show["id"]] = int(round(total))
    with state_lock:
        state["show_seconds"] = seconds


def show_end_deadline(now: Optional[dt_datetime] = None) -> Optional[dt_datetime]:
    """End of today's show time (the one now lies in), None if not in it."""
    now = now or local_now()
    if is_quiet_hours(now):
        return None
    end = dt_datetime.combine(now.date(), SHOW_TIME_END).replace(tzinfo=now.tzinfo)
    if SHOW_TIME_START > SHOW_TIME_END and now.time() >= SHOW_TIME_START:
        end += dt_timedelta(days=1)  # show time crosses midnight
    return end


def wish_seconds(entry: Dict[str, Any]) -> Optional[float]:
    """Length of a wish including its lead-in; None if the song's is unknown."""
    duration = entry.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        return None
    lead_in = wish_lead_in_seconds() if (entry.get("mediaName") or entry.get("media")) else 0.0
    return float(duration) + lead_in


def busy_seconds() -> float:
    """How long what is playing now plus the waiting wishes will still take.
    Unknown lengths count as zero (the check then lets things through)."""
    with state_lock:
        status = dict(state.get("last_status") or {})
        now_playing = dict(state.get("now_playing") or {})
        queue = list(state.get("queue") or [])
        current = state.get("current_request")
    total = 0.0
    if status.get("is_running") and now_playing:
        remaining = now_playing.get("secondsRemaining")
        if isinstance(remaining, (int, float)):
            elapsed = max(0.0, time.time() - now_playing.get("updatedAt", time.time()))
            total += max(0.0, remaining - elapsed)
        playlist = status.get("playlist_label") or ""
        if now_playing.get("kind") != "wish" and playlist:
            # A show: the rest of the current song plus all songs after it.
            plan = playlist_plan(playlist) or []
            sequence = normalize(_strip_extension(status.get("current_sequence")))
            index = next((i for i, e in enumerate(plan) if sequence and sequence in e["files"]), None)
            if index is not None:
                total += sum(e["seconds"] for e in plan[index + 1:])
    for idx, entry in enumerate(queue):
        if idx == 0 and current is not None and entry.get("title") == current.get("title"):
            continue  # playing now, counted above
        total += wish_seconds(entry) or 0.0
    return total


def ends_too_late(
    extra_seconds: Optional[float],
    now: Optional[dt_datetime] = None,
    busy: Optional[float] = None,
) -> Optional[dt_datetime]:
    """The end time if starting `extra_seconds` of playback now (after what is
    already playing or waiting) would run past the show time plus tolerance;
    None if it fits, the check is off or the length is unknown."""
    if not SHOW_END_CHECK or not extra_seconds:
        return None
    now = now or local_now()
    deadline = show_end_deadline(now)
    if deadline is None:
        return None
    end = now + dt_timedelta(seconds=(busy_seconds() if busy is None else busy) + extra_seconds)
    if end > deadline + dt_timedelta(minutes=SHOW_END_TOLERANCE_MINUTES):
        return end
    return None


def _clock(moment: dt_datetime) -> str:
    return i18n.format_time(moment.time(), request_language())


# The wish whose song (not just its lead-in) has been seen playing.
_wish_song_started: Dict[str, Any] = {"entry": None}


def build_now_playing(status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What visitors see as "Jetzt läuft": a readable title and the time left."""
    if not status.get("is_running"):
        return None
    playlist_norm = status.get("playlist_name") or ""
    is_wish = playlist_norm in {normalize(PLAYLIST_REQUESTS), normalize("__wish_single__")}
    sequence = status.get("current_sequence") or ""

    title = ""
    seconds_remaining = status.get("seconds_remaining")
    if playlist_norm == normalize("__wish_single__"):
        with state_lock:
            current = state.get("current_request") or {}
        title = _clean_text(current.get("title"))
        # During the lead-in FPP reports the rest of the lead-in only: add the
        # song itself so the countdown and the waiting times stay honest.
        own_files = {
            normalize(_strip_extension(name))
            for name in (
                current.get("sequenceName"), current.get("sequence"),
                current.get("mediaName"), current.get("media"),
            )
            if name
        }
        duration = current.get("duration")
        if normalize(_strip_extension(sequence)) in own_files:
            # The song itself is on: from now on FPP's value is the truth
            # (also in the short gap after its last note).
            _wish_song_started["entry"] = current
        elif (
            wish_lead_in_entry()
            and own_files
            and _wish_song_started["entry"] is not current
            and isinstance(duration, int)
        ):
            seconds_remaining = (seconds_remaining or 0) + duration
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
        "secondsRemaining": seconds_remaining,
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
        expire_test_mode()
        try:
            status = fetch_fpp_status()
        except Exception:
            with state_lock:
                state["fpp_reachable"] = False
                state["now_playing"] = None
            _status_sleep(False)
            continue

        now_playing = build_now_playing(status)
        refresh_show_seconds()

        if not control_enabled():
            # Manual mode: only report what plays, never act.
            with state_lock:
                state["last_status"] = status
                state["fpp_reachable"] = True
                state["now_playing"] = now_playing
            _status_sleep(False)
            continue

        # Plan actions without holding the lock during network calls.
        action = None
        volume_song: Optional[str] = None
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
                # A show started directly at FPP gets the show volume too, and
                # a new period applies from the next song on (never mid-song).
                target = show_volume()
                song = status.get("current_sequence")
                if state.get("volume_phase") == "show" and state.get("volume_song") is None:
                    # Set at the start, before FPP named the song: it is this one.
                    state["volume_song"] = song
                if target is not None and (
                    state.get("volume_phase") != "show"
                    or (target != state.get("volume_value") and song != state.get("volume_song"))
                ):
                    action = "show_volume"
                    volume_song = song
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
                if quiet_now():
                    # No new wishes outside the show times; whatever ran is over.
                    state["current_request"] = None
                    state["scheduled_show_active"] = False
                    action = "resume_background"
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
                elif queue and not quiet_now():
                    entry_to_start = queue[0]
                    action = "start_entry"
                else:
                    action = "resume_background"

        # Execute slow operations outside the lock to avoid blocking /api/state.
        if delete_temp:
            delete_playlist("__wish_single__")

        if action == "show_volume":
            set_fpp_volume(show_volume(), "show", volume_song)
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
            if is_quiet_hours(info.get("time")) or not control_enabled():
                # Skipped (also in manual mode, so it doesn't start late
                # when the app takes over again).
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
                mark_note("note.scheduledFailed")
            update_next_show()
        time.sleep(1)


_asset_versions: Dict[str, Any] = {}
_ASSET_REF = re.compile(r'(?P<attr>\b(?:src|href))="(?P<url>/?[\w./-]+\.(?:js|css))"')
# Files whose change means "this page is outdated" for an open browser tab.
_BUILD_FILES = (
    "index.html",
    "styles.css",
    "app.js",
    "config.js",
    "falconbeat-audio.js",
    "static/js/index.js",
    "static/icons.svg",
) + tuple(f"i18n/{code}.json" for code in i18n.SUPPORTED)
CACHE_REVALIDATE = "no-cache"
CACHE_FOREVER = "public, max-age=31536000, immutable"


def _asset_version(relative_path: str) -> str:
    """Short content hash of a file below the app directory ('' if missing)."""
    path = os.path.join(APP_DIR, relative_path)
    try:
        stat = os.stat(path)
    except OSError:
        return ""
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _asset_versions.get(relative_path)
    if not cached or cached[0] != key:
        with open(path, "rb") as f:
            cached = (key, hashlib.sha256(f.read()).hexdigest()[:12])
        _asset_versions[relative_path] = cached
    return cached[1]


def build_id() -> str:
    """Changes whenever the page, its scripts/styles or the settings change."""
    joined = "|".join(_asset_version(name) for name in _BUILD_FILES)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _versioned_assets(page: str) -> str:
    """Add ?v=<content hash> to local scripts and stylesheets, so a browser
    can keep them forever and still gets a new file after every update."""

    def add_version(match: "re.Match[str]") -> str:
        url = match.group("url")
        version = _asset_version(url.lstrip("/"))
        if not version:
            return match.group(0)
        return f'{match.group("attr")}="{url}?v={version}"'

    return _ASSET_REF.sub(add_version, page)


def _send_asset(directory: str, filename: str) -> Response:
    """A file requested with ?v=<hash> never changes under that address; any
    other request has to ask the server every time (answered with 304)."""
    response = send_from_directory(directory, filename)
    response.headers["Cache-Control"] = CACHE_FOREVER if request.args.get("v") else CACHE_REVALIDATE
    return response


def _send_page(filename: str) -> Response:
    return _send_asset(APP_DIR, filename)


_page_cache: Dict[str, Any] = {}


_TRANSLATION_REF = re.compile(r"\{\{t:([\w.]+)\}\}")


def _show_buttons_html(lang: str) -> str:
    """One button per configured show, all the same size; special shows quieter."""
    parts = []
    for show in SHOWS:
        label = html.escape(show_label(show, lang))
        classes = "action btn-show btn-special" if show["special"] else "action btn-show"
        parts.append(
            f'        <button class="{classes}" type="button" data-show="{show["id"]}">\n'
            f'          <svg class="icon" aria-hidden="true" focusable="false"><use href="/static/icons.svg#{show["icon"]}"></use></svg>\n'
            f'          <span class="action-label">{label}</span>\n'
            f'        </button>'
        )
    return "\n".join(parts)


def _render_page(filename: str) -> Response:
    """Serve an HTML page in the visitor's language, with the site
    name/description filled into its head."""
    lang = request_language()
    path = os.path.join(APP_DIR, filename)
    mtime = os.path.getmtime(path)
    cache_key = (filename, lang)
    cached = _page_cache.get(cache_key)
    if not cached or cached[0] != mtime:
        with open(path, "r", encoding="utf-8") as f:
            page = f.read()
        og_image = ""
        if SITE_IMAGE_URL.startswith(("http://", "https://")):
            og_image = f'  <meta property="og:image" content="{html.escape(SITE_IMAGE_URL, quote=True)}">\n'
        page = (
            page.replace("{{OG_IMAGE}}", og_image)
            .replace("{{SITE_NAME}}", html.escape(site_name(lang), quote=True))
            .replace("{{SITE_DESCRIPTION}}", html.escape(site_description(lang), quote=True))
            .replace("{{LANG}}", lang)
            .replace("{{SHOW_BUTTONS}}", _show_buttons_html(lang))
            .replace("{{I18N_SRC}}", f"/i18n/{lang}.js?v={_asset_version(f'i18n/{lang}.json')}")
        )
        page = _TRANSLATION_REF.sub(lambda m: html.escape(i18n.translate(lang, m.group(1)), quote=True), page)
        cached = (mtime, page)
        _page_cache[cache_key] = cached
    page = _versioned_assets(cached[1]).replace(
        "</head>", f'  <meta name="app-build" content="{build_id()}">\n</head>', 1
    )
    response = Response(page, mimetype="text/html")
    # no-store also keeps Safari from showing a kept copy when a tab is reopened.
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/i18n/<lang>.js")
def i18n_js(lang: str):
    """The visitor's strings for the page scripts (window.FPP_I18N)."""
    code = i18n.normalize_language(lang)
    if not code or code != lang:
        return Response("Not found", status=404)
    payload = {
        "lang": code,
        "locale": i18n.translate(code, "_locale"),
        "strings": {k: v for k, v in i18n.catalog(code).items() if not k.startswith("_")},
        # The switch is offered only when the language follows the visitor.
        "languages": i18n.language_names(i18n.SUPPORTED) if not FIXED_LANGUAGE else {},
        "siteName": site_name(code),
    }
    body = "window.FPP_I18N = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    response = Response(body, mimetype="application/javascript")
    response.headers["Cache-Control"] = CACHE_FOREVER if request.args.get("v") else CACHE_REVALIDATE
    return response


@app.route("/lang/<lang>")
def set_language(lang: str):
    """Remember the visitor's language choice and go back to the page."""
    target = request.args.get("next", "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    response = redirect(target, code=302)
    code = i18n.normalize_language(lang)
    if code:
        response.set_cookie(LANGUAGE_COOKIE, code, max_age=365 * 86400, samesite="Lax")
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
    if request.path.startswith("/api/") or request.path == "/health":
        response.headers.setdefault("Cache-Control", "no-store")
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
    response = _send_asset(os.path.join(APP_DIR, "static"), filename)
    if filename.startswith(("fonts/", "vendor/")) and not request.args.get("v"):
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
    return _send_page("config.js")


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
    show = show_for_playlist(playlist)
    return show["id"] if show else "other"


def _next_show_name(playlist: Optional[str]) -> str:
    """Short name of the next show for the countdown ("" = none given)."""
    show = show_for_playlist(playlist)
    return show_name(show, request_language()) if show else ""


def _public_test_mode(until: Optional[dt_datetime]) -> Dict[str, Any]:
    if until is None or until <= local_now():
        return {"active": False, "until": None, "untilTime": ""}
    return {
        "active": True,
        "until": until.isoformat(timespec="seconds"),
        "untilTime": i18n.format_time(until.time(), request_language()),
    }


@app.route("/api/state")
def api_state():
    with state_lock:
        info = state.copy()
    next_show = info.get("next_show") if info.get("control_enabled", True) else None
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
            "siteName": site_name(request_language()),
            "build": build_id(),
            "queue": _public_queue(info, device, now_playing),
            "currentRequest": _public_entry(info.get("current_request"), device),
            "nowPlaying": now_playing,
            "limits": {"maxWishesPerDevice": MAX_WISHES_PER_DEVICE, "maxQueueLength": MAX_QUEUE_LENGTH},
            "scheduledShowActive": info.get("scheduled_show_active", False),
            "scheduledShowsEnabled": SCHEDULED_SHOWS_ENABLED and bool(info.get("control_enabled", True)),
            "note": _note_text(info.get("note")),
            "status": info.get("last_status", {}),
            "fppReachable": info.get("fpp_reachable"),
            "falconbeat": {"available": bool((info.get("falconbeat") or {}).get("available"))},
            "accessCode": {"onMatrix": DAILY_CODE_ENABLED, "visible": bool(info.get("code_visible"))},
            "nextShow": {
                "time": next_show_time,
                "playlist": next_show.get("playlist") if next_show else None,
                "label": next_show.get("label") if next_show else None,
                "kind": _next_show_kind(next_show.get("playlist")) if next_show else None,
                "name": _next_show_name(next_show.get("playlist")) if next_show else "",
            },
            "locks": locks,
            "manualMode": not info.get("control_enabled", True),
            "testMode": _public_test_mode(info.get("test_until")),
            "showDurations": info.get("show_seconds") or {},
        }
    )


@app.route("/api/show", methods=["POST"])
def api_show():
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    kind = str(payload.get("type") or "playlist1")
    show = SHOWS_BY_ID.get(kind)
    if show is None:
        return jsonify({"ok": False, "message": t("show.unknown")}), 400
    playlist = show["playlist"]
    with state_lock:
        info = state.copy()
    locks = compute_locks(info.get("last_status", {}), info.get("queue", []), info.get("current_request"))
    if locks.get("disableShowButtons"):
        return jsonify({"ok": False, "message": locks.get("reason") or t("show.startFailed")}), 409
    too_late = ends_too_late(playlist_seconds(playlist))
    if too_late:
        return jsonify({
            "ok": False,
            "message": t("limit.show", end=_clock(too_late), showEnd=i18n.format_time(SHOW_TIME_END, request_language())),
        }), 409
    notify_lang = operator_language()
    playlist_label = show_name(show, notify_lang) or (
        i18n.translate(notify_lang, "notify.mainShow") if LEGACY_SHOWS else playlist
    )
    
    # Log show start to statistics
    log_show_start(playlist, kind)
    
    # Send notification (before FPP operations, so it works in preview mode too)
    send_notification(
        title=i18n.translate(notify_lang, "notify.showStartedTitle", label=playlist_label),
        message=i18n.translate(notify_lang, "notify.showStartedMessage", playlist=playlist),
        action_type="show_start",
        extra_data={"playlist": playlist, "playlist_type": kind}
    )
    
    with state_lock:
        state["scheduled_show_active"] = False
    try:
        stop_effects_and_blackout()
        start_playlist(playlist)
        mark_note("note.playlistStarted", playlist=playlist)
        wake_status_worker()
        return jsonify({"ok": True, "message": t("show.started", playlist=playlist)})
    except requests.RequestException as exc:
        logger.warning("Playlist '%s' could not be started: %s", playlist, exc)
        return jsonify({"ok": False, "message": t("show.startFailed")}), 502


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


def wish_counts() -> Dict[str, int]:
    """How often each song was wished so far (all kept statistics)."""
    with statistics_lock:
        entries = load_statistics().get("song_requests") or []
    counts: Dict[str, int] = {}
    for entry in entries:
        title = entry.get("song_title") if isinstance(entry, dict) else None
        if isinstance(title, str) and title:
            counts[title] = counts.get(title, 0) + 1
    return counts


@app.route("/api/requests/songs")
def api_requests_songs():
    try:
        counts = wish_counts()
        songs = [{**song, "wishes": counts.get(song.get("title"), 0)} for song in fetch_request_songs()]
        if SHOW_END_CHECK:
            # Mark songs that would end too late (same rule as for a request).
            busy = busy_seconds()
            songs = [{**song, "fits": ends_too_late(wish_seconds(song), busy=busy) is None} for song in songs]
        return jsonify({"songs": songs})
    except requests.RequestException as exc:
        logger.warning("Wish playlist could not be loaded: %s", exc)
        return jsonify({"songs": [], "error": t("wish.listFailed")}), 502


@app.route("/api/requests", methods=["POST"])
def api_requests():
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    requested_title = payload.get("song")

    if not isinstance(requested_title, str) or not requested_title.strip():
        return jsonify({"ok": False, "message": t("wish.songMissing")}), 400

    request_locks = compute_locks(state.get("last_status", {}), [], None)
    if request_locks.get("disableAllButtons"):
        message = request_locks.get("reason") if request_locks.get("manual") else t("wish.notPossible")
        return jsonify({"ok": False, "message": message}), 409

    # Only songs of the wish playlist may be requested. Sequence/media names
    # and the title always come from FPP, never from the client.
    try:
        songs = fetch_request_songs()
    except requests.RequestException:
        return jsonify({"ok": False, "message": t("wish.listFailed")}), 502

    wanted = normalize(requested_title)
    match = next((song for song in songs if normalize(song.get("title")) == wanted), None)
    if match is None:
        return jsonify({"ok": False, "message": t("wish.notOnList")}), 400

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
    too_late = ends_too_late(wish_seconds(entry))
    if too_late:
        return jsonify({
            "ok": False,
            "message": t("limit.wish", title=title, end=_clock(too_late), showEnd=i18n.format_time(SHOW_TIME_END, request_language())),
        }), 409
    
    # Check for duplicates in current_request and queue
    with state_lock:
        current_request = state.get("current_request")
        queue: List[Dict[str, Any]] = state["queue"]
        
        # Check if song is currently playing
        if current_request and normalize(current_request.get("title")) == normalize(title):
            return jsonify({"ok": False, "message": t("wish.nowPlaying", title=title)}), 409
        
        # Check if song is already in queue
        for queued_song in queue:
            if normalize(queued_song.get("title")) == normalize(title):
                return jsonify({"ok": False, "message": t("wish.alreadyQueued", title=title)}), 409
        
        if MAX_QUEUE_LENGTH and len(queue) >= MAX_QUEUE_LENGTH:
            return jsonify({"ok": False, "message": t("wish.queueFull")}), 409
        if MAX_WISHES_PER_DEVICE:
            own = sum(1 for queued_song in queue if queued_song.get("owner") == device)
            if own >= MAX_WISHES_PER_DEVICE:
                message = t("wish.limitOne") if MAX_WISHES_PER_DEVICE == 1 else t("wish.limitMany", count=MAX_WISHES_PER_DEVICE)
                return jsonify({"ok": False, "message": message}), 409

        queue.append(entry)
        position = len(queue)
        should_start = position == 1 and not state.get("scheduled_show_active", False)
    
    # Log song request to statistics
    log_song_request(title, duration)
    
    # Send notification for song request (before FPP operations, so it works in preview mode too)
    duration_str = format_duration(duration)
    send_notification(
        title=i18n.translate(operator_language(), "notify.wishTitle"),
        message=i18n.translate(operator_language(), "notify.wishMessage", title=title, duration=duration_str, position=position),
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
            return jsonify({"ok": False, "message": t("wish.startFailed")}), 502
    
    return jsonify({"ok": True, "position": position, "message": t("wish.added", title=title)})


def set_control(enabled: bool) -> bool:
    """Switch the app's control of FPP on or off. Returns True if it changed."""
    with state_lock:
        if bool(state.get("control_enabled", True)) == enabled:
            return False
        since = None if enabled else local_now().isoformat(timespec="seconds")
        state["control_enabled"] = enabled
        state["control_since"] = since
        # Either way the app starts from a clean slate: no wishes waiting,
        # no scheduled show in progress, volume set again by the next song.
        dropped = len(state["queue"])
        state["queue"] = []
        state["current_request"] = None
        state["scheduled_show_active"] = False
        state["background_owed"] = False
        state["volume_phase"] = None
        state["volume_song"] = None
        state["note"] = ""
    _save_control()
    if enabled:
        logger.info("Manual mode off: the app controls FPP again.")
        update_next_show()
        wake_status_worker(0.1)
    else:
        logger.info("Manual mode on: the app leaves FPP alone (%d queued wishes dropped).", dropped)
        cancel_wish_title()
        hide_code_display(suppress_seconds=0)
    lang = operator_language()
    key = "notify.controlOn" if enabled else "notify.controlOff"
    send_notification(
        title=i18n.translate(lang, key + "Title"),
        message=i18n.translate(lang, key + "Message"),
        action_type="control",
        extra_data={"enabled": enabled},
    )
    return True


def set_test_mode(minutes: Optional[int], expired: bool = False) -> bool:
    """Switch test mode on for `minutes` (again: extends it) or off (None).
    Returns True if anything changed."""
    now = local_now()
    dropped = 0
    with state_lock:
        was_on = state.get("test_until") is not None
        if minutes:
            until = now + dt_timedelta(minutes=minutes)
            state["test_until"] = until
        else:
            if not was_on:
                return False
            until = None
            state["test_until"] = None
            if outside_show_time(now):
                # Wishes still waiting would otherwise play when the show
                # time begins; what plays now runs to its end.
                current = state.get("current_request")
                kept = [e for e in state["queue"] if current is not None and e is current]
                dropped = len(state["queue"]) - len(kept)
                state["queue"] = kept
    _save_control()
    lang = operator_language()
    if until is not None:
        logger.info("Test mode on until %s: shows and wishes ignore the show times.", until.isoformat(timespec="minutes"))
        key = "notify.testOn"
        params = {"until": i18n.format_time(until.time(), lang), "minutes": minutes}
        wake_status_worker(0.1)
    else:
        logger.info("Test mode %s (%d waiting wishes dropped).", "expired" if expired else "off", dropped)
        key = "notify.testExpired" if expired else "notify.testOff"
        params = {}
        if outside_show_time(now):
            hide_code_display(suppress_seconds=0)
    send_notification(
        title=i18n.translate(lang, key + "Title"),
        message=i18n.translate(lang, key + "Message", **params),
        action_type="test_mode",
        extra_data={"active": until is not None, "until": until.isoformat(timespec="seconds") if until else None},
    )
    return True


def expire_test_mode() -> None:
    with state_lock:
        until = state.get("test_until")
    if until is not None and until <= local_now():
        set_test_mode(None, expired=True)


def _control_denied():
    """None if the request carries the control token, else an error response."""
    if not CONTROL_TOKEN:
        return jsonify({"ok": False, "message": t("control.notConfigured")}), 404
    client = _client_id()
    wait = _access_lockout_remaining(client)
    if wait:
        response = jsonify({"ok": False, "message": t("access.tooManyMinutes", minutes=max(1, round(wait / 60)))})
        response.headers["Retry-After"] = str(wait)
        return response, 429
    auth = request.headers.get("Authorization", "")
    provided = (
        (auth[7:].strip() if auth.lower().startswith("bearer ") else "")
        or request.headers.get("X-Control-Token")
        or request.args.get("token")
        or str(_get_cached_payload().get("token") or "")
    )
    if provided and hmac.compare_digest(provided.encode("utf-8"), CONTROL_TOKEN.encode("utf-8")):
        return None
    if provided:
        _register_access_failure(client)
    return jsonify({"ok": False, "message": t("control.denied")}), 403


def _control_response(changed: bool, message: Optional[str] = None):
    with state_lock:
        enabled = bool(state.get("control_enabled", True))
        since = state.get("control_since")
    until = test_mode_until()
    if message is None:
        message = t("control.on" if enabled else "control.off")
    return jsonify({"ok": True, "enabled": enabled, "manualMode": not enabled, "since": since,
                    "testMode": until is not None,
                    "testUntil": until.isoformat(timespec="seconds") if until else None,
                    "changed": changed, "message": message})


def _test_minutes(value: Any) -> Optional[int]:
    """Minutes asked for (default TEST_MODE_MINUTES); None if invalid."""
    if value in (None, ""):
        return TEST_MODE_MINUTES
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return None
    return minutes if 1 <= minutes <= 720 else None


def _test_message() -> str:
    until = test_mode_until()
    if until is None:
        return t("control.testOff")
    return t("control.testOn", until=i18n.format_time(until.time(), request_language()))


@app.route("/api/control", methods=["GET", "POST"])
def api_control():
    """GET: is the app in control? POST {"enabled": false}: manual mode on."""
    denied = _control_denied()
    if denied:
        return denied
    changed = False
    if request.method == "POST":
        payload = _get_cached_payload()
        if "enabled" not in payload and "test" not in payload:
            return jsonify({"ok": False, "message": t("control.missing")}), 400
        if "test" in payload:
            minutes = _test_minutes(payload.get("minutes"))
            if minutes is None:
                return jsonify({"ok": False, "message": t("control.testMinutes")}), 400
            changed = set_test_mode(minutes if _parse_bool(payload.get("test")) else None) or changed
        if "enabled" in payload:
            changed = set_control(_parse_bool(payload.get("enabled"))) or changed
    return _control_response(changed)


@app.route("/api/control/test/<switch>", methods=["GET", "POST"])
def api_control_test(switch: str):
    """/api/control/test/on[?minutes=90] and /api/control/test/off."""
    if switch not in ("on", "off"):
        return jsonify({"ok": False, "message": t("control.missing")}), 404
    denied = _control_denied()
    if denied:
        return denied
    minutes = None
    if switch == "on":
        minutes = _test_minutes(request.args.get("minutes") or _get_cached_payload().get("minutes"))
        if minutes is None:
            return jsonify({"ok": False, "message": t("control.testMinutes")}), 400
    changed = set_test_mode(minutes)
    return _control_response(changed, _test_message())


@app.route("/api/control/<switch>", methods=["GET", "POST"])
def api_control_switch(switch: str):
    """/api/control/off and /api/control/on – easy to call from FPP's URL command."""
    if switch not in ("on", "off"):
        return jsonify({"ok": False, "message": t("control.missing")}), 404
    denied = _control_denied()
    if denied:
        return denied
    return _control_response(set_control(switch == "on"))


@app.route("/health")
def health():
    return {"status": "ok"}


def _entry_year(entry: Any) -> Optional[int]:
    """Calendar year of a statistics entry (from its ISO timestamp)."""
    if not isinstance(entry, dict):
        return None
    stamp = str(entry.get("timestamp") or "")
    return int(stamp[:4]) if len(stamp) >= 4 and stamp[:4].isdigit() else None


@app.route("/api/statistics")
def api_statistics():
    """Return aggregated statistics for one calendar year.

    ``?year=YYYY`` selects the year; without it the current year is used.
    ``years`` lists every year with data (plus the current one) for the archive.
    """
    with statistics_lock:
        stats = load_statistics()

    current_year = local_now().year
    try:
        year = int(request.args.get("year", current_year))
    except (TypeError, ValueError):
        year = current_year

    all_entries = list(stats.get("show_starts", [])) + list(stats.get("song_requests", []))
    years = sorted({y for y in (_entry_year(e) for e in all_entries) if y} | {current_year, year}, reverse=True)

    # Process show starts
    show_starts = [e for e in stats.get("show_starts", []) if _entry_year(e) == year]
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
    song_requests = [e for e in stats.get("song_requests", []) if _entry_year(e) == year]
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
        "year": year,
        "currentYear": current_year,
        "years": years,
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
