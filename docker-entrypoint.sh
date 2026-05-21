#!/bin/sh
set -e

mkdir -p /app/config /app/data

python - <<'"'"'PY'"'"'
import json
import os
from pathlib import Path

def parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "on"}

config_path = Path(os.getenv("APP_CONFIG_PATH", "/app/config/config.json"))
runtime_config = {}
if config_path.exists():
    try:
        runtime_config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        runtime_config = {}

def cfg(key, env_key, default=""):
    if key in runtime_config:
        return runtime_config[key]
    return os.getenv(env_key, default)

config = {
    "siteName": cfg("siteName", "SITE_NAME", "Brauns Lichtershow"),
    "siteSubtitle": cfg("siteSubtitle", "SITE_SUBTITLE", "Fernsteuerung für den Falcon Player"),
    "statusPollMs": int(cfg("clientStatusPollMs", "CLIENT_STATUS_POLL_MS", "10000")),
    "donationPoolId": cfg("donationPoolId", "DONATION_POOL_ID", ""),
    "donationCampaignName": cfg("donationCampaignName", "DONATION_CAMPAIGN_NAME", ""),
    "donationSubtitle": cfg("donationSubtitle", "DONATION_SUBTITLE", "Unterstütze die Lichtershow"),
    "donationText": cfg("donationText", "DONATION_TEXT", "Vielen Dank für deine Unterstützung!"),
    "buyMeACoffeeUsername": cfg("buyMeACoffeeUsername", "BUYMEACOFFEE_USERNAME", ""),
    "previewMode": parse_bool(cfg("previewMode", "PREVIEW_MODE", "false"), False),
    "accessCode": cfg("accessCode", "ACCESS_CODE", ""),
    "socialFacebook": cfg("socialFacebook", "SOCIAL_FACEBOOK", ""),
    "socialInstagram": cfg("socialInstagram", "SOCIAL_INSTAGRAM", ""),
    "socialTiktok": cfg("socialTiktok", "SOCIAL_TIKTOK", ""),
    "socialWhatsapp": cfg("socialWhatsapp", "SOCIAL_WHATSAPP", ""),
    "socialYoutube": cfg("socialYoutube", "SOCIAL_YOUTUBE", ""),
    "socialWebsite": cfg("socialWebsite", "SOCIAL_WEBSITE", ""),
    "socialEmail": cfg("socialEmail", "SOCIAL_EMAIL", ""),
    "buttonPlaylist1Text": cfg("buttonPlaylist1Text", "BUTTON_PLAYLIST_1", "Playlist 1 starten"),
    "buttonPlaylist2Text": cfg("buttonPlaylist2Text", "BUTTON_PLAYLIST_2", "Playlist 2 starten"),
}

Path("config.js").write_text("window.FPP_CONFIG = " + json.dumps(config, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
PY

exec "$@"
