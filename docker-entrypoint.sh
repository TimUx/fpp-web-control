#!/bin/sh
set -e

: "${SITE_NAME:=Brauns Lichtershow}"
: "${FPP_BASE_URL:=http://localhost}"
: "${FPP_PLAYLIST_SHOW:=show 1}"
: "${FPP_PLAYLIST_KIDS:=show 2}"
: "${FPP_PLAYLIST_REQUESTS:=all songs}"
: "${FPP_PLAYLIST_IDLE:=background}"
: "${FPP_POLL_INTERVAL_MS:=30000}"
: "${CLIENT_STATUS_POLL_MS:=10000}"
: "${DONATION_PAYPAL:=}"
: "${DONATION_TEXT:=Vielen Dank für deine Unterstützung!}"
: "${PREVIEW_MODE:=false}"
: "${ACCESS_CODE:=}"

# generate config.js for the frontend
python - <<'PY'
import os
config = f"""
window.FPP_CONFIG = {{
  siteName: {os.getenv('SITE_NAME', 'Brauns Lichtershow').__repr__()},
  statusPollMs: {int(os.getenv('CLIENT_STATUS_POLL_MS', '10000'))},
  donationPaypal: {os.getenv('DONATION_PAYPAL', '').__repr__()},
  donationText: {os.getenv('DONATION_TEXT', 'Vielen Dank für deine Unterstützung!').__repr__()},
  previewMode: {os.getenv('PREVIEW_MODE', 'false').lower() in ['true', '1', 'yes', 'on']},
  accessCode: {os.getenv('ACCESS_CODE', '').__repr__()}
}};
"""
with open('config.js', 'w', encoding='utf-8') as f:
    f.write(config)
PY

exec "$@"
