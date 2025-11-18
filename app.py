import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SITE_NAME = os.getenv("SITE_NAME", "FPP Lichtershow")
FPP_BASE_URL = os.getenv("FPP_BASE_URL", "http://fpp.local")
PLAYLIST_SHOW = os.getenv("FPP_PLAYLIST_SHOW", "show 1")
PLAYLIST_KIDS = os.getenv("FPP_PLAYLIST_KIDS", "show 2")
PLAYLIST_REQUESTS = os.getenv("FPP_PLAYLIST_REQUESTS", "all songs")
PLAYLIST_IDLE = os.getenv("FPP_PLAYLIST_IDLE", "background")
POLL_INTERVAL_SECONDS = max(5, int(os.getenv("FPP_POLL_INTERVAL_MS", "15000")) // 1000)
REQUEST_TIMEOUT = 8

state_lock = threading.Lock()
state: Dict[str, Any] = {
    "queue": [],
    "current_request": None,
    "scheduled_show_active": False,
    "last_status": {},
    "next_show": None,
    "note": "",
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


def compute_next_show(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    playlist = PLAYLIST_KIDS if next_hour.astimezone().hour == 17 else PLAYLIST_SHOW
    label = "Kids-Show" if playlist == PLAYLIST_KIDS else "Show"
    return {"time": next_hour, "playlist": playlist, "label": label}


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
        "is_idle": playlist_name == normalize(PLAYLIST_IDLE),
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
    for path in ["StopEffects", "StopPlaylist", "DisableOutputs"]:
        try:
            requests.get(f"{FPP_BASE_URL}/api/command/{path}", timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue

    try:
        requests.get(f"{FPP_BASE_URL}/api/playlists/stop", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass


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

    if seq and media:
        item_type = "both"
    elif seq:
        item_type = "sequence"
    else:
        item_type = "media"

    body = {
        "name": temp_name,
        "mainPlaylist": [
            {
                "type": item_type,
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


def restore_idle_playlist() -> None:
    if not PLAYLIST_IDLE:
        return
    try:
        start_playlist(PLAYLIST_IDLE)
    except requests.RequestException:
        pass


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
                delete_playlist("__wish_single__")
                # No playlist running: advance queue or resume after schedule.
                if scheduled_active:
                    state["scheduled_show_active"] = False
                    if queue:
                        # resume queued wishes
                        entry = queue[0]
                        try:
                            start_request_song(entry)
                            state["current_request"] = entry
                        except requests.RequestException:
                            state["current_request"] = None
                    else:
                        restore_idle_playlist()
                elif current_request:
                    # request finished
                    if queue and queue[0] == current_request:
                        queue.pop(0)
                    state["current_request"] = None
                    delete_playlist("__wish_single__")
                    if queue:
                        entry = queue[0]
                        try:
                            start_request_song(entry)
                            state["current_request"] = entry
                        except requests.RequestException:
                            state["current_request"] = None
                    else:
                        restore_idle_playlist()
                elif queue:
                    entry = queue[0]
                    try:
                        start_request_song(entry)
                        state["current_request"] = entry
                    except requests.RequestException:
                        state["current_request"] = None
                else:
                    restore_idle_playlist()

        time.sleep(POLL_INTERVAL_SECONDS)


def scheduler_worker():
    update_next_show()
    while True:
        with state_lock:
            info = state.get("next_show")
        now = datetime.now(timezone.utc)
        if info and info.get("time") <= now:
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
        }
    )


@app.route("/api/show", methods=["POST"])
def api_show():
    payload = request.get_json(force=True, silent=True) or {}
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
    payload = request.get_json(force=True, silent=True) or {}
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
