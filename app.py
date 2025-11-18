import json
import os
import threading
import time
from datetime import datetime as dt_datetime
from datetime import timedelta as dt_timedelta
from datetime import time as dt_time
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, request, send_from_directory, g

app = Flask(__name__, static_folder='.', static_url_path='')

SITE_NAME = os.getenv("SITE_NAME", "FPP Lichtershow")
FPP_BASE_URL = os.getenv("FPP_BASE_URL", "http://fpp.local")
PLAYLIST_SHOW = os.getenv("FPP_PLAYLIST_SHOW", "show 1")
PLAYLIST_KIDS = os.getenv("FPP_PLAYLIST_KIDS", "show 2")
PLAYLIST_REQUESTS = os.getenv("FPP_PLAYLIST_REQUESTS", "all songs")
BACKGROUND_EFFECT = os.getenv("FPP_BACKGROUND_EFFECT", "background")
SHOW_START_DATE = os.getenv("FPP_SHOW_START_DATE")
SHOW_END_DATE = os.getenv("FPP_SHOW_END_DATE")
POLL_INTERVAL_SECONDS = max(5, int(os.getenv("FPP_POLL_INTERVAL_MS", "15000")) // 1000)
REQUEST_TIMEOUT = 8
def _load_access_code_from_config() -> str:
    """Return access code from generated frontend config if available."""

    config_path = os.path.join(os.path.dirname(__file__), "config.js")
    if not os.path.exists(config_path):
        return ""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        prefix = "window.FPP_CONFIG ="
        if not raw.startswith(prefix):
            return ""

        json_part = raw[len(prefix) :].strip()
        if json_part.endswith(";"):
            json_part = json_part[:-1]

        config = json.loads(json_part)
        return str(config.get("accessCode", "")).strip()
    except Exception:
        return ""


ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip() or _load_access_code_from_config()

state_lock = threading.RLock()
state: Dict[str, Any] = {
    "queue": [],
    "current_request": None,
    "scheduled_show_active": False,
    "last_status": {},
    "next_show": None,
    "note": "",
    "background_active": False,
}


def normalize(name: Optional[str]) -> str:
    if isinstance(name, str):
        return name.strip().lower()
    if isinstance(name, dict):
        for key in ["playlist", "name", "title"]:
            if isinstance(name.get(key), str):
                return name[key].strip().lower()
    return str(name or "").strip().lower() if name is not None else ""


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

    Quiet hours start at 22:00 local time and last until 16:30 the next day.
    """

    current = now or local_now()
    quiet_start = dt_time(hour=22, minute=0, tzinfo=current.tzinfo)
    quiet_end = dt_time(hour=16, minute=30, tzinfo=current.tzinfo)
    current_t = current.timetz()
    return current_t >= quiet_start or current_t < quiet_end


def compute_next_show(now: Optional[dt_datetime] = None) -> Dict[str, Any]:
    now = now or local_now()
    if not is_within_show_window(now):
        # If we are before the window, calculate from the first valid day.
        if SHOW_START and now.date() < SHOW_START:
            now = dt_datetime.combine(SHOW_START, dt_time(0, tzinfo=now.tzinfo))
        else:
            return {}
    schedule = [
        (17, PLAYLIST_KIDS, "Kids-Show"),
        (18, PLAYLIST_SHOW, "Show"),
        (19, PLAYLIST_SHOW, "Show"),
        (20, PLAYLIST_SHOW, "Show"),
        (21, PLAYLIST_SHOW, "Show"),
    ]

    for day_offset in range(0, 14):
        day = (now + dt_timedelta(days=day_offset)).date()
        if SHOW_START and day < SHOW_START:
            continue
        if SHOW_END and day > SHOW_END:
            break
        for hour, playlist, label in schedule:
            candidate = dt_datetime.combine(day, dt_time(hour=hour, tzinfo=now.tzinfo))
            if candidate > now:
                return {"time": candidate, "playlist": playlist, "label": label}

    return {}


def compute_locks(status: Dict[str, Any], queue: List[Dict[str, Any]], current_request: Any) -> Dict[str, Any]:
    playlist_norm = normalize(status.get("playlist_name"))
    show_norm = normalize(PLAYLIST_SHOW)
    kids_norm = normalize(PLAYLIST_KIDS)
    request_norm = normalize(PLAYLIST_REQUESTS)
    temp_norm = normalize("__wish_single__")

    standard_running = status.get("is_running") and playlist_norm in {show_norm, kids_norm}
    wish_running = (status.get("is_running") and playlist_norm in {request_norm, temp_norm}) or bool(current_request)
    quiet = is_quiet_hours()

    reason = None
    if quiet:
        reason = "Ruhezeit 22:00–16:30 – keine Wiedergabe möglich."
    elif standard_running:
        reason = "Aktuell läuft eine Show – alle Aktionen sind gesperrt."
    elif wish_running:
        reason = "Ein Wunsch läuft – Shows können nicht gestartet werden."

    return {
        "disableAllButtons": bool(standard_running or quiet),
        "disableShowButtons": bool(standard_running or wish_running or quiet),
        "quiet": quiet,
        "reason": reason,
    }


def enforce_access_code(payload: Optional[Dict[str, Any]] = None):
    if not ACCESS_CODE:
        return None

    provided_code = (
        request.headers.get("X-Access-Code")
        or request.headers.get("X-Access-Token")
        or request.args.get("accessCode")
        or request.args.get("access_code")
    )

    if provided_code is None and payload:
        provided_code = payload.get("accessCode") or payload.get("access_code")

    if provided_code == ACCESS_CODE:
        return None

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
    if not ACCESS_CODE:
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


def fetch_fpp_status() -> Dict[str, Any]:
    resp = requests.get(f"{FPP_BASE_URL}/api/fppd/status", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    name = normalize(payload.get("status_name") or payload.get("status") or "")
    playlist_raw = extract_playlist_name(payload)
    playlist_name = normalize(playlist_raw)
    is_running = name in {"playing", "running", "playing playlist", "playlist"}
    return {
        "raw": payload,
        "is_running": is_running,
        "playlist_name": playlist_name,
        "mode_name": payload.get("mode_name") or payload.get("mode"),
        "current_sequence": payload.get("current_sequence") or payload.get("current_song"),
        "playlist_label": playlist_raw,
    }


def start_playlist(name: str) -> None:
    """Start a playlist using documented FPP endpoints.

    Preferred path is the documented ``GET /api/playlist/:PlaylistName/start``.
    For older command-driven flows, fall back to the command API using
    ``Start Playlist`` as described in the commands list.
    """

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
    for path in ["StopEffects", "StopPlaylist", "DisableOutputs"]:
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
    for path in [
        f"{FPP_BASE_URL}/api/command/Stop%20Effect/{slug}",
        f"{FPP_BASE_URL}/api/command/StopEffect/{slug}",
    ]:
        try:
            requests.get(path, timeout=REQUEST_TIMEOUT)
            break
        except requests.RequestException:
            continue
    with state_lock:
        state["background_active"] = False


def start_background_effect() -> None:
    if not BACKGROUND_EFFECT or is_quiet_hours():
        return
    with state_lock:
        if state.get("background_active"):
            return

    slug = requests.utils.quote(BACKGROUND_EFFECT, safe="")
    for path in [
        f"{FPP_BASE_URL}/api/command/Start%20Effect/{slug}",
        f"{FPP_BASE_URL}/api/command/StartEffect/{slug}",
    ]:
        try:
            resp = requests.get(path, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            with state_lock:
                state["background_active"] = True
            return
        except requests.RequestException:
            continue


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


def status_worker():
    update_next_show()
    while True:
        try:
            status = fetch_fpp_status()
        except Exception:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        # Plan actions without holding the lock during network calls.
        action = None
        entry_to_start: Optional[Dict[str, Any]] = None
        delete_temp = False

        with state_lock:
            state["last_status"] = status
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

        time.sleep(POLL_INTERVAL_SECONDS)


def scheduler_worker():
    update_next_show()
    while True:
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
                mark_note("Geplante Show gestartet – Wünsche pausiert.")
            except requests.RequestException:
                mark_note("Geplante Show konnte nicht gestartet werden.")
            update_next_show()
        time.sleep(1)


@app.route("/")
def root():
    return send_from_directory(".", "index.html")


@app.route("/styles.css")
def styles():
    return send_from_directory(".", "styles.css")


@app.route("/donation")
def donation_page():
    return send_from_directory(".", "donation.html")


@app.route("/requests")
def requests_page():
    return send_from_directory(".", "requests.html")


@app.route("/config.js")
def config_js():
    return send_from_directory(".", "config.js")


@app.route("/api/state")
def api_state():
    with state_lock:
        info = state.copy()
    next_show = info.get("next_show")
    next_show_time = next_show["time"].isoformat() if next_show else None
    locks = compute_locks(info.get("last_status", {}), info.get("queue", []), info.get("current_request"))
    return jsonify(
        {
            "siteName": SITE_NAME,
            "queue": info.get("queue", []),
            "currentRequest": info.get("current_request"),
            "scheduledShowActive": info.get("scheduled_show_active", False),
            "note": info.get("note", ""),
            "status": info.get("last_status", {}),
            "nextShow": {
                "time": next_show_time,
                "playlist": next_show.get("playlist") if next_show else None,
                "label": next_show.get("label") if next_show else None,
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
    kind = payload.get("type", "show")
    playlist = PLAYLIST_KIDS if kind == "kids" else PLAYLIST_SHOW
    with state_lock:
        state["scheduled_show_active"] = False
    try:
        stop_effects_and_blackout()
        start_playlist(playlist)
        mark_note(f"Playlist '{playlist}' wurde gestartet.")
        return jsonify({"ok": True, "message": f"{playlist} gestartet."})
    except requests.RequestException as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502


def _extract_song(entry: Dict[str, Any], idx: int) -> Dict[str, Any]:
    title = (
        entry.get("note")
        or entry.get("name")
        or entry.get("song")
        or entry.get("title")
        or entry.get("sequenceName")
        or entry.get("mediaName")
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


@app.route("/api/requests/songs")
def api_requests_songs():
    playlist_slug = requests.utils.quote(PLAYLIST_REQUESTS, safe="")
    try:
        resp = requests.get(f"{FPP_BASE_URL}/api/playlist/{playlist_slug}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        entries = _extract_entries(data)
        songs = [_extract_song(entry, idx) for idx, entry in enumerate(entries)]
        return jsonify({"songs": songs})
    except requests.RequestException as exc:
        return jsonify({"songs": [], "error": str(exc)}), 502


@app.route("/api/requests", methods=["POST"])
def api_requests():
    payload = _get_cached_payload()
    denied = enforce_access_code(payload)
    if denied:
        return denied
    title = payload.get("song")
    sequence_name = payload.get("sequenceName")
    media_name = payload.get("mediaName")
    duration = payload.get("duration")

    if not title:
        return jsonify({"ok": False, "message": "song fehlt"}), 400

    entry = {
        "title": title,
        "sequenceName": sequence_name,
        "mediaName": media_name,
        "duration": duration,
    }
    with state_lock:
        queue: List[Dict[str, Any]] = state["queue"]
        queue.append(entry)
        position = len(queue)
        should_start = position == 1 and not state.get("scheduled_show_active", False)
    if should_start:
        try:
            start_request_song(entry)
            with state_lock:
                state["current_request"] = entry
        except requests.RequestException as exc:
            return jsonify({"ok": False, "message": str(exc)}), 502
    mark_note(f"Wunsch '{title}' wurde hinzugefügt. Position {position}.")
    return jsonify({"ok": True, "position": position})


@app.route("/health")
def health():
    return {"status": "ok"}


def boot_threads():
    threading.Thread(target=status_worker, daemon=True).start()
    threading.Thread(target=scheduler_worker, daemon=True).start()


boot_threads()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
