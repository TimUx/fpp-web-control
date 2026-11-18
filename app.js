/*
 * Shared helpers for all pages (main page, donation, statistics).
 * Exposes window.FPPApp. Requires config.js to be loaded first.
 */
(function (global) {
  'use strict';

  var config = global.FPP_CONFIG || {};
  var i18n = global.FPP_I18N || { lang: 'de', locale: 'de-DE', strings: {}, languages: {} };

  /** Translate a key; {name} placeholders are filled from params. */
  function t(key, params) {
    var text = Object.prototype.hasOwnProperty.call(i18n.strings, key) ? i18n.strings[key] : key;
    if (params) {
      Object.keys(params).forEach(function (name) {
        text = text.split('{' + name + '}').join(String(params[name]));
      });
    }
    return text;
  }

  /** Language symbol: switches to the next language (only when the
   *  language follows the visitor). Its label names that language. */
  function renderLanguageSwitch() {
    var link = document.getElementById('language-switch');
    var codes = Object.keys(i18n.languages || {});
    if (!link || codes.length < 2) return;
    var target = codes[(codes.indexOf(i18n.lang) + 1) % codes.length];
    var name = i18n.languages[target];
    var back = location.pathname + location.search + location.hash;
    link.href = '/lang/' + target + '?next=' + encodeURIComponent(back);
    link.hreflang = target;
    link.title = name;
    link.setAttribute('aria-label', t('footer.language') + ': ' + name);
    link.classList.remove('hidden');
  }
  var ACCESS_FLAG_KEY = 'fpp-access-granted';
  var ACCESS_CODE_KEY = 'fpp-access-code';
  var TOAST_DISPLAY_MS = 4000;
  var TOAST_ANIMATION_MS = 300; // matches the CSS transition

  function storageGet(key) {
    try { return localStorage.getItem(key) || ''; } catch (e) { return ''; }
  }

  function storageSet(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  function storageRemove(key) {
    try { localStorage.removeItem(key); } catch (e) { /* private mode */ }
  }

  // ── Icons (self-hosted sprite, see static/icons.svg) ──────────────
  var SVG_NS = 'http://www.w3.org/2000/svg';
  var ICON_SPRITE = '/static/icons.svg';

  function createIcon(name) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    var use = document.createElementNS(SVG_NS, 'use');
    use.setAttribute('href', ICON_SPRITE + '#' + name);
    svg.appendChild(use);
    return svg;
  }

  /** Switch an existing icon (<svg class="icon"><use></use></svg>) to another symbol. */
  function setIcon(svg, name, spinning) {
    var use = svg.querySelector('use');
    if (use) use.setAttribute('href', ICON_SPRITE + '#' + name);
    svg.classList.toggle('icon-spin', Boolean(spinning));
  }

  // ── Anonymous device id (fair wish limits, "your wish" marker) ─────
  function deviceId() {
    var id = storageGet('fpp-device-id');
    if (!id) {
      id = (global.crypto && typeof global.crypto.randomUUID === 'function')
        ? global.crypto.randomUUID()
        : 'd-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
      storageSet('fpp-device-id', id);
    }
    return id;
  }

  function deviceHeaders() {
    return { 'X-Device-Id': deviceId() };
  }

  // ── Access code ───────────────────────────────────────────────────
  var access = {
    required: Boolean(config.accessRequired),
    code: function () { return storageGet(ACCESS_CODE_KEY); },
    granted: function () { return !access.required || Boolean(access.code()); },
    headers: function () {
      var code = access.code();
      var headers = deviceHeaders();
      if (access.required && code) headers['X-Access-Code'] = code;
      return headers;
    },
    store: function (code) {
      storageSet(ACCESS_CODE_KEY, code);
      storageSet(ACCESS_FLAG_KEY, 'yes');
    },
    clear: function () {
      storageRemove(ACCESS_CODE_KEY);
      storageRemove(ACCESS_FLAG_KEY);
    }
  };

  // ── Toasts ────────────────────────────────────────────────────────
  function showToast(message) {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(function () { toast.classList.add('show'); });
    setTimeout(function () {
      toast.classList.remove('show');
      toast.classList.add('hide');
      setTimeout(function () { toast.remove(); }, TOAST_ANIMATION_MS);
    }, TOAST_DISPLAY_MS);
  }

  // ── Social media footer ───────────────────────────────────────────
  var SOCIAL_LINKS = [
    { key: 'socialFacebook', icon: 'facebook-f', label: 'Facebook' },
    { key: 'socialInstagram', icon: 'instagram', label: 'Instagram' },
    { key: 'socialTiktok', icon: 'tiktok', label: 'TikTok' },
    { key: 'socialWhatsapp', icon: 'whatsapp', label: 'WhatsApp' },
    { key: 'socialYoutube', icon: 'youtube', label: 'YouTube' },
    { key: 'socialWebsite', icon: 'globe', label: t('social.website') },
    { key: 'socialEmail', icon: 'envelope', label: t('social.email'), isEmail: true }
  ];

  function isHttpUrl(url) {
    try {
      var protocol = new URL(url).protocol;
      return protocol === 'http:' || protocol === 'https:';
    } catch (e) {
      return false;
    }
  }

  /**
   * Fill #social-icons from the config and reveal #social-footer (only when
   * there is a channel); also sets up the language symbol.
   */
  function renderSocialFooter() {
    renderLanguageSwitch();
    var footer = document.getElementById('social-footer');
    var icons = document.getElementById('social-icons');
    if (!footer || !icons) return;
    var title = footer.querySelector('.social-footer-title');
    var hasAny = false;

    SOCIAL_LINKS.forEach(function (entry) {
      var value = String(config[entry.key] || '').trim();
      if (!value) return;
      if (!entry.isEmail && !isHttpUrl(value)) return;

      var link = document.createElement('a');
      link.className = 'social-icon';
      link.setAttribute('aria-label', entry.label);
      link.title = entry.label;
      if (entry.isEmail) {
        link.href = 'mailto:' + value;
      } else {
        link.href = value;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }
      link.appendChild(createIcon(entry.icon));
      icons.appendChild(link);
      hasAny = true;
    });

    if (title) title.classList.toggle('hidden', !hasAny);
    if (hasAny) footer.classList.remove('hidden');
  }

  global.FPPApp = {
    config: config,
    siteName: config.siteName || i18n.siteName || t('site.defaultName'),
    t: t,
    lang: i18n.lang,
    locale: i18n.locale || 'de-DE',
    access: access,
    showToast: showToast,
    createIcon: createIcon,
    setIcon: setIcon,
    deviceHeaders: deviceHeaders,
    renderSocialFooter: renderSocialFooter
  };
})(window);
