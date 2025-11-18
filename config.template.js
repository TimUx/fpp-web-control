// Generated on container start from environment variables (see docker-entrypoint.sh)
window.FPP_CONFIG = {
  siteName: '${SITE_NAME}',
  siteSubtitle: '${SITE_SUBTITLE:-Fernsteuerung für den Falcon Player}',
  statusPollMs: ${CLIENT_STATUS_POLL_MS:-10000},
  donationPoolId: '${DONATION_POOL_ID:-}',
  donationCampaignName: `${DONATION_CAMPAIGN_NAME:-}`,
  donationText: `${DONATION_TEXT:-Vielen Dank für deine Unterstützung!}`,
  previewMode: ${PREVIEW_MODE:-false},
  accessCode: '${ACCESS_CODE:-}'
};
