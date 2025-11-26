#!/bin/sh
set -e

# Site settings
: "${SITE_NAME:=Brauns Lichtershow}"
: "${SITE_SUBTITLE:=Fernsteuerung für den Falcon Player}"
: "${ACCESS_CODE:=}"
: "${PREVIEW_MODE:=false}"

# FPP connection
: "${FPP_BASE_URL:=http://localhost}"
: "${FPP_POLL_INTERVAL_MS:=30000}"
: "${CLIENT_STATUS_POLL_MS:=10000}"

# Playlists
: "${FPP_PLAYLIST_1:=show 1}"
: "${FPP_PLAYLIST_2:=show 2}"
: "${FPP_PLAYLIST_REQUESTS:=all songs}"
: "${FPP_PLAYLIST_IDLE:=background}"

# Show period
: "${FPP_SHOW_START_DATE:=}"
: "${FPP_SHOW_END_DATE:=}"
: "${FPP_SHOW_START_TIME:=16:30}"
: "${FPP_SHOW_END_TIME:=22:00}"

# Button texts
: "${BUTTON_PLAYLIST_1:=Playlist 1 starten}"
: "${BUTTON_PLAYLIST_2:=Playlist 2 starten}"

# Donation settings
: "${DONATION_POOL_ID:=}"
: "${DONATION_CAMPAIGN_NAME:=}"
: "${DONATION_SUBTITLE:=Unterstütze die Lichtershow}"
: "${DONATION_TEXT:=}"

# Social media
: "${SOCIAL_FACEBOOK:=}"
: "${SOCIAL_INSTAGRAM:=}"
: "${SOCIAL_TIKTOK:=}"
: "${SOCIAL_WHATSAPP:=}"
: "${SOCIAL_YOUTUBE:=}"
: "${SOCIAL_WEBSITE:=}"
: "${SOCIAL_EMAIL:=}"

# generate config.js for the frontend
python - <<'PY'
import json
import os

donation_text_env = os.getenv("DONATION_TEXT")

config = {
    "siteName": os.getenv("SITE_NAME", "Brauns Lichtershow"),
    "siteSubtitle": os.getenv(
        "SITE_SUBTITLE", "Fernsteuerung für den Falcon Player"
    ),
    "statusPollMs": int(os.getenv("CLIENT_STATUS_POLL_MS", "10000")),
    "donationPoolId": os.getenv("DONATION_POOL_ID", ""),
    "donationCampaignName": os.getenv("DONATION_CAMPAIGN_NAME", ""),
    "donationSubtitle": os.getenv("DONATION_SUBTITLE", "Unterstütze die Lichtershow"),
    "donationText": "Vielen Dank für deine Unterstützung!"
    if donation_text_env is None
    else donation_text_env,
    "previewMode": os.getenv("PREVIEW_MODE", "false").lower()
    in ["true", "1", "yes", "on"],
    "accessCode": os.getenv("ACCESS_CODE", ""),
    "socialFacebook": os.getenv("SOCIAL_FACEBOOK", ""),
    "socialInstagram": os.getenv("SOCIAL_INSTAGRAM", ""),
    "socialTiktok": os.getenv("SOCIAL_TIKTOK", ""),
    "socialWhatsapp": os.getenv("SOCIAL_WHATSAPP", ""),
    "socialYoutube": os.getenv("SOCIAL_YOUTUBE", ""),
    "socialWebsite": os.getenv("SOCIAL_WEBSITE", ""),
    "socialEmail": os.getenv("SOCIAL_EMAIL", ""),
    "buttonPlaylist1Text": os.getenv("BUTTON_PLAYLIST_1", "Playlist 1 starten"),
    "buttonPlaylist2Text": os.getenv("BUTTON_PLAYLIST_2", "Playlist 2 starten"),
}

with open("config.js", "w", encoding="utf-8") as f:
    f.write("window.FPP_CONFIG = ")
    json.dump(config, f, ensure_ascii=False, indent=2)
    f.write(";\n")
PY

exec "$@"
