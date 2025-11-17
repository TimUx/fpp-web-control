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
    return (name or "").strip().lower()


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
    playlist_name = normalize(
        payload.get("playlist")
        or payload.get("current_playlist")
        or payload.get("playlist_name")
        or ""
    )
    is_running = name in {"playing", "running", "playing playlist", "playlist"}
    return {
        "raw": payload,
        "is_running": is_running,
        "playlist_name": playlist_name,
        "is_idle": playlist_name == normalize(PLAYLIST_IDLE),
    }


def start_playlist(name: str, *, item: Optional[str] = None) -> None:
    url = f"{FPP_BASE_URL}/api/playlists/{requests.utils.quote(name, safe='')}/start"
    body: Dict[str, Any] = {"action": "start"}
    if item:
        body["item"] = item
    resp = requests.post(url, json=body, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()


def stop_effects_and_blackout() -> None:
    for path in ["StopEffects", "StopPlaylist", "DisableOutputs"]:
        try:
            requests.post(f"{FPP_BASE_URL}/api/commands/{path}", timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue


def start_request_song(title: str) -> None:
    stop_effects_and_blackout()
    start_playlist(PLAYLIST_REQUESTS, item=title)


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
            queue: List[str] = state["queue"]
            current_request = state.get("current_request")
            scheduled_active = state.get("scheduled_show_active", False)

            playlist_match_requests = normalize(PLAYLIST_REQUESTS) == status.get("playlist_name")

            if status.get("is_running"):
                # If a scheduled show is running, ensure queue is paused.
                if scheduled_active and playlist_match_requests:
                    # Unexpected playlist; mark for restart after schedule.
                    state["current_request"] = None
                if current_request and not playlist_match_requests:
                    # request was interrupted
                    state["current_request"] = None
            else:
                # No playlist running: advance queue or resume after schedule.
                if scheduled_active:
                    state["scheduled_show_active"] = False
                    if queue:
                        # resume queued wishes
                        title = queue[0]
                        try:
                            start_request_song(title)
                            state["current_request"] = title
                        except requests.RequestException:
                            state["current_request"] = None
                    else:
                        restore_idle_playlist()
                elif current_request:
                    # request finished
                    if queue and queue[0] == current_request:
                        queue.pop(0)
                    state["current_request"] = None
                    if queue:
                        title = queue[0]
                        try:
                            start_request_song(title)
                            state["current_request"] = title
                        except requests.RequestException:
                            state["current_request"] = None
                    else:
                        restore_idle_playlist()
                elif queue:
                    title = queue[0]
                    try:
                        start_request_song(title)
                        state["current_request"] = title
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
        entry.get("name")
        or entry.get("song")
        or entry.get("title")
        or entry.get("sequenceName")
        or f"Titel {idx + 1}"
    )
    duration = entry.get("duration")
    if duration is None:
        duration = entry.get("seconds") or entry.get("length") or entry.get("time")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    return {"title": title, "duration": duration}


@app.route("/api/requests/songs")
def api_requests_songs():
    try:
        resp = requests.get(
            f"{FPP_BASE_URL}/api/playlist/{requests.utils.quote(PLAYLIST_REQUESTS, safe='')}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("playlist") or data.get("entries") or data.get("sequence") or []
        songs = [_extract_song(entry, idx) for idx, entry in enumerate(entries)]
        return jsonify({"songs": songs})
    except requests.RequestException as exc:
        return jsonify({"songs": [], "error": str(exc)}), 502


@app.route("/api/requests", methods=["POST"])
def api_requests():
    payload = request.get_json(force=True, silent=True) or {}
    title = payload.get("song")
    if not title:
        return jsonify({"ok": False, "message": "song fehlt"}), 400
    with state_lock:
        queue: List[str] = state["queue"]
        queue.append(title)
        position = len(queue)
        should_start = position == 1 and not state.get("scheduled_show_active", False)
    if should_start:
        try:
            start_request_song(title)
            with state_lock:
                state["current_request"] = title
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
