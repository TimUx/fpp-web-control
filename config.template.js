// Generated on container start from environment variables (see docker-entrypoint.sh)
window.FPP_CONFIG = {
  siteName: '${SITE_NAME}',
  statusPollMs: ${CLIENT_STATUS_POLL_MS:-10000},
  donationPaypal: '${DONATION_PAYPAL:-}',
  donationText: `${DONATION_TEXT:-Vielen Dank für deine Unterstützung!}`,
  previewMode: ${PREVIEW_MODE:-false},
  accessCode: '${ACCESS_CODE:-}'
};
