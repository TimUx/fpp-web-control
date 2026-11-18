'use strict';

const { config, t } = FPPApp;
const headline = document.getElementById('headline');
const donationText = document.getElementById('donation-text');
const donationLinks = document.getElementById('donation-links');
const subtitle = document.getElementById('subtitle');
const campaignName = document.getElementById('campaign-name');
const backHome = document.getElementById('back-home');


const poolId = (config.donationPoolId || '').trim();
const campaignTitle = (config.donationCampaignName || '').trim();

headline.textContent = FPPApp.siteName;
subtitle.textContent = config.donationSubtitle || t('donation.defaultSubtitle');
campaignName.textContent = campaignTitle || '';
const donationMessage = (config.donationText || '').trim() || t('donation.defaultText');
if (donationMessage) {
  donationText.textContent = donationMessage;
} else {
  donationText.remove();
}

if (poolId) {
  const link = document.createElement('a');
  link.className = 'donation-link';
  link.href = `https://www.paypal.com/pool/${poolId}`;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';

  const icon = document.createElement('span');
  icon.className = 'paypal-icon';
  icon.setAttribute('aria-hidden', 'true');

  const label = document.createElement('span');
  label.className = 'donation-label';
  label.textContent = t('donation.paypal');

  link.appendChild(icon);
  link.appendChild(label);
  donationLinks.appendChild(link);
}

// Buy Me a Coffee Button
const bmcUsername = (config.buyMeACoffeeUsername || '').trim();
// Validate username: only alphanumeric characters, underscores and hyphens allowed
const isValidBmcUsername = bmcUsername && /^[a-zA-Z0-9_-]+$/.test(bmcUsername);
if (isValidBmcUsername) {
  const bmcLink = document.createElement('a');
  bmcLink.className = 'donation-link bmc-link';
  bmcLink.href = `https://buymeacoffee.com/${encodeURIComponent(bmcUsername)}`;
  bmcLink.target = '_blank';
  bmcLink.rel = 'noopener noreferrer';

  const bmcIcon = document.createElement('span');
  bmcIcon.className = 'bmc-icon';
  bmcIcon.setAttribute('aria-hidden', 'true');

  const bmcLabel = document.createElement('span');
  bmcLabel.className = 'donation-label';
  bmcLabel.textContent = 'Buy me a Coffee';

  bmcLink.appendChild(bmcIcon);
  bmcLink.appendChild(bmcLabel);
  donationLinks.appendChild(bmcLink);

  // Add hint text for Buy Me a Coffee
  const bmcHint = document.createElement('p');
  bmcHint.className = 'bmc-hint note';
  bmcHint.textContent = t('donation.bmcHint');
  donationLinks.parentNode.insertBefore(bmcHint, donationLinks.nextSibling);
}

if (!poolId && !isValidBmcUsername) {
  const none = document.createElement('p');
  none.textContent = t('donation.none');
  donationLinks.replaceChildren(none);
}

backHome.addEventListener('click', () => {
  window.location.href = '/';
});

FPPApp.renderSocialFooter();
