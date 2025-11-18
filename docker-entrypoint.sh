#!/bin/sh
set -e

: "${SITE_NAME:=Brauns Lichtershow}"
: "${SITE_SUBTITLE:=Fernsteuerung für den Falcon Player}"
: "${FPP_BASE_URL:=http://localhost}"
: "${FPP_PLAYLIST_SHOW:=show 1}"
: "${FPP_PLAYLIST_KIDS:=show 2}"
: "${FPP_PLAYLIST_REQUESTS:=all songs}"
: "${FPP_PLAYLIST_IDLE:=background}"
: "${FPP_POLL_INTERVAL_MS:=30000}"
: "${CLIENT_STATUS_POLL_MS:=10000}"
: "${DONATION_POOL_ID:=}"
: "${DONATION_CAMPAIGN_NAME:=}"
: "${DONATION_TEXT:=Vielen Dank für deine Unterstützung!}"
: "${PREVIEW_MODE:=false}"
: "${ACCESS_CODE:=}"

# generate config.js for the frontend
python - <<'PY'
import json
import os

config = {
    "siteName": os.getenv("SITE_NAME", "Brauns Lichtershow"),
    "siteSubtitle": os.getenv(
        "SITE_SUBTITLE", "Fernsteuerung für den Falcon Player"
    ),
    "statusPollMs": int(os.getenv("CLIENT_STATUS_POLL_MS", "10000")),
    "donationPoolId": os.getenv("DONATION_POOL_ID", ""),
    "donationCampaignName": os.getenv("DONATION_CAMPAIGN_NAME", ""),
    "donationText": os.getenv(
        "DONATION_TEXT", "Vielen Dank für deine Unterstützung!"
    ),
    "previewMode": os.getenv("PREVIEW_MODE", "false").lower()
    in ["true", "1", "yes", "on"],
    "accessCode": os.getenv("ACCESS_CODE", ""),
}

with open("config.js", "w", encoding="utf-8") as f:
    f.write("window.FPP_CONFIG = ")
    json.dump(config, f, ensure_ascii=False, indent=2)
    f.write(";\n")
PY

exec "$@"
