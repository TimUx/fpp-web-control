// Generated on container start from environment variables (see docker-entrypoint.sh)
window.FPP_CONFIG = {
  siteName: '${SITE_NAME}',
  siteSubtitle: '${SITE_SUBTITLE:-Fernsteuerung für den Falcon Player}',
  statusPollMs: ${CLIENT_STATUS_POLL_MS:-10000},
  donationPoolId: '${DONATION_POOL_ID:-}',
  donationCampaignName: '${DONATION_CAMPAIGN_NAME:-}',
  donationSubtitle: '${DONATION_SUBTITLE:-Unterstütze die Lichtershow}',
  donationText: '${DONATION_TEXT-}',
  previewMode: ${PREVIEW_MODE:-false},
  accessCode: '${ACCESS_CODE:-}',
  socialFacebook: '${SOCIAL_FACEBOOK:-}',
  socialInstagram: '${SOCIAL_INSTAGRAM:-}',
  socialTiktok: '${SOCIAL_TIKTOK:-}',
  socialWhatsapp: '${SOCIAL_WHATSAPP:-}',
  socialYoutube: '${SOCIAL_YOUTUBE:-}',
  socialWebsite: '${SOCIAL_WEBSITE:-}',
  socialEmail: '${SOCIAL_EMAIL:-}',
  buttonPlaylist1Text: '${BUTTON_PLAYLIST_1:-Playlist 1 starten}',
  buttonPlaylist2Text: '${BUTTON_PLAYLIST_2:-Playlist 2 starten}'
};
