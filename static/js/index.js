'use strict';

const { config, access, showToast } = FPPApp;
const headline = document.getElementById('headline');
const subtitle = document.getElementById('subtitle');
const btnShow = document.getElementById('btn-show');
const btnKids = document.getElementById('btn-kids');
const btnRequest = document.getElementById('btn-request');
const btnDonate = document.getElementById('btn-donate');
const previewBanner = document.getElementById('preview-banner');
const scheduledShowBanner = document.getElementById('scheduled-show-banner');
const showRunningBanner = document.getElementById('show-running-banner');
const quietBanner = document.getElementById('quiet-banner');
const outsideWindowBanner = document.getElementById('outside-window-banner');
const statusBox = document.getElementById('status');
const statusText = document.getElementById('status-text');
const statusDetails = document.getElementById('status-details');
const note = document.getElementById('note');
const countdownEl = document.getElementById('countdown');
const accessGate = document.getElementById('access-gate');
const accessInput = document.getElementById('access-input');
const accessSubmit = document.getElementById('access-submit');
const accessError = document.getElementById('access-error');
const mainContent = document.getElementById('main-content');
const queueSection = document.getElementById('queue-section');
const queueList = document.getElementById('queue-list');
const queueEmpty = document.getElementById('queue-empty');
const queueCount = document.getElementById('queue-count');

const statusPollMs = Math.max(3000, Number(config.statusPollMs || 10000));
const previewMode = Boolean(config.previewMode);
let countdownTimer;
let pollHandle;

const authHeaders = access.headers;

// The server rejected the stored code (e.g. it was changed): ask again.
function handleAccessDenied() {
  access.clear();
  closeRequestPanel();
  showAccessGate(accessOnMatrix
    ? 'Der Code wechselt täglich – bitte den heutigen Code eingeben.'
    : 'Bitte Zugangscode erneut eingeben.');
}

headline.textContent = FPPApp.siteName;
subtitle.textContent = `${config.siteSubtitle || 'Fernsteuerung für den Falcon Player'}`;
// Phones: keep the header short, times and address open on tap.
const siteInfo = document.getElementById('site-info');
siteInfo.open = !window.matchMedia('(max-width: 540px)').matches;
document.getElementById('btn-show-label').textContent = config.buttonPlaylist1Text || 'Playlist 1 starten';
document.getElementById('btn-kids-label').textContent = config.buttonPlaylist2Text || 'Playlist 2 starten';

function setButtonsDisabled(disabled, message) {
  [btnShow, btnKids, btnRequest].forEach((btn) => btn.disabled = disabled);
  if (message !== undefined) {
    note.textContent = message;
  }
}

function applyLocks(locks) {
  const disableAll = Boolean(locks && locks.disableAllButtons);
  const disableShows = Boolean(locks && locks.disableShowButtons);
  btnShow.disabled = disableAll || disableShows;
  btnKids.disabled = disableAll || disableShows;
  btnRequest.disabled = disableAll;
  return locks && locks.reason ? locks.reason : '';
}

function entryTitle(entry, fallback) {
  if (!entry) return fallback || '';
  return entry.title || entry.song || entry.mediaName || entry.sequenceName || fallback || '';
}

function renderQueue(currentRequest, queue) {
  queueList.innerHTML = '';
  const items = [];

  if (currentRequest) {
    items.push({ title: entryTitle(currentRequest, 'Aktueller Wunsch'), label: 'Läuft jetzt', mine: currentRequest.mine });
  }

  (queue || []).forEach((entry, idx) => {
    const title = entryTitle(entry, `Wunsch ${idx + 1}`);
    const isCurrent = currentRequest && entryTitle(currentRequest) === entryTitle(entry) && idx === 0;
    if (!isCurrent) {
      const wait = typeof entry.waitSeconds === 'number' && entry.waitSeconds > 0
      ? ` · ca. ${Math.max(1, Math.round(entry.waitSeconds / 60))} Min.` : '';
    items.push({ title, label: `Platz ${idx + 1}${wait}`, mine: entry.mine });
    }
  });

  queueSection.classList.toggle('hidden', !items.length);
  if (!items.length) {
    queueSection.classList.add('queue-empty');
    queueEmpty.classList.remove('hidden');
    queueCount.textContent = '';
    return;
  }

  queueSection.classList.remove('queue-empty');
  queueEmpty.classList.add('hidden');
  queueCount.textContent = `${items.length} offen`;

  items.forEach((item) => {
    const li = document.createElement('li');
    li.className = item.mine ? 'queue-item queue-item-mine' : 'queue-item';
    const titleEl = document.createElement('div');
    titleEl.className = 'queue-title';
    titleEl.textContent = item.title;
    const badge = document.createElement('span');
    badge.className = 'queue-badge';
    badge.textContent = item.mine ? `Dein Wunsch · ${item.label}` : item.label;
    li.appendChild(titleEl);
    li.appendChild(badge);
    queueList.appendChild(li);
  });
}

function markStatus(type, text) {
  statusBox.classList.remove('running', 'error');
  if (type) statusBox.classList.add(type);
  statusText.textContent = text;
}

// "Jetzt läuft": readable title and a local countdown between two polls.
let nowPlayingTimer = null;

function formatRemaining(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function showNowPlaying(nowPlaying) {
  clearInterval(nowPlayingTimer);
  nowPlayingTimer = null;
  if (!nowPlaying) {
    statusDetails.textContent = '';
    return;
  }
  const kind = nowPlaying.kind === 'wish' ? 'Wunsch' : 'Show';
  let remaining = typeof nowPlaying.secondsRemaining === 'number' ? nowPlaying.secondsRemaining : null;
  const render = () => {
    statusDetails.textContent = remaining !== null && remaining > 0
      ? `${kind} · noch ${formatRemaining(remaining)}`
      : kind;
  };
  render();
  if (remaining !== null) {
    nowPlayingTimer = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
    }, 1000);
  }
}

function formatCountdown(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
  const seconds = String(totalSeconds % 60).padStart(2, '0');
  // More than a day away: "3 Tagen" reads better than "74:12:09"
  const days = Math.floor(totalSeconds / 86400);
  if (days >= 2) return `${days} Tagen`;
  return `${hours}:${minutes}:${seconds}`;
}

function updateCountdown(nextShow, scheduledShowsEnabled = true) {
  clearInterval(countdownTimer);
  if (!scheduledShowsEnabled) {
    countdownEl.textContent = 'Aktuell keine automatische Show geplant.';
    return;
  }
  if (!nextShow || !nextShow.time) {
    countdownEl.textContent = 'Nächste Show wird berechnet …';
    return;
  }
  const target = new Date(nextShow.time);
  const showName = nextShow.kind === 'playlist2' ? 'Nächste Kindershow'
    : nextShow.kind === 'other' && nextShow.label ? `Nächste Show „${nextShow.label}“` : 'Nächste Show';
  const startTime = target.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  const sameDay = target.toDateString() === new Date().toDateString();
  const when = sameDay ? `um ${startTime} Uhr`
    : `am ${target.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })} um ${startTime} Uhr`;
  countdownTimer = setInterval(() => {
    const diff = target - new Date();
    if (diff <= 0) {
      countdownEl.textContent = 'Geplante Show startet jetzt …';
      return;
    }
    countdownEl.textContent = `${showName} ${when} · in ${formatCountdown(diff)}`;
  }, 1000);
}

function renderSampleState() {
  const now = new Date();
  const next = new Date(now.getTime() + 18 * 60 * 1000);
  const queue = [{ title: 'Jingle Bells (Wunsch)' }, { title: 'Carol of the Bells (Wunsch)' }];
  markStatus('', 'Bereit (Vorschau).');
  showNowPlaying(null);
  updateCountdown({ time: next.toISOString(), label: 'Show' });
  previewBanner.textContent = 'Dies ist eine Vorschau ohne Verbindung zum FPP.';
  previewBanner.classList.remove('hidden');
  applyLocks({ disableAllButtons: false, disableShowButtons: false });
  renderQueue(queue[0], queue);
}

async function fetchState() {
  if (previewMode) {
    renderSampleState();
    return;
  }
  try {
    const response = await fetch('/api/state', { headers: FPPApp.deviceHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    const status = data.status || {};
    const isRunning = Boolean(status.is_running);
    const fppOffline = data.fppReachable === false;
    showIsRunning = isRunning || Boolean(data.currentRequest) || (data.queue || []).length > 0;

    if (fppOffline) {
      markStatus('error', 'Lichtershow-Steuerung ist gerade nicht erreichbar.');
      showNowPlaying(null);
    } else if (isRunning) {
      const nowPlaying = data.nowPlaying || {};
      markStatus('running', nowPlaying.title ? `Jetzt läuft: ${nowPlaying.title}` : 'Show läuft gerade.');
      showNowPlaying(nowPlaying);
    } else {
      const locked = Boolean(data.locks && (data.locks.quiet || data.locks.outsideShowWindow));
      markStatus('', locked ? 'Gerade keine Wiedergabe.' : 'Bereit – such dir etwas aus!');
      showNowPlaying(null);
    }
    queuedTitles = new Set([data.currentRequest, ...(data.queue || [])].filter(Boolean).map((e) => e.title));
    updateAudioAvailability(Boolean(data.falconbeat && data.falconbeat.available), isRunning && !fppOffline);
    updateCountdown(data.nextShow, data.scheduledShowsEnabled !== false);

    const lockReason = applyLocks(data.locks);
    if (fppOffline) setButtonsDisabled(true);
    requestsDisabled = Boolean(data.locks && data.locks.disableAllButtons) || fppOffline;
    updateRequestButtons();
    const isQuiet = Boolean(data.locks && data.locks.quiet);
    const isOutsideWindow = Boolean(data.locks && data.locks.outsideShowWindow);
    const showPeriod = data.locks && data.locks.showPeriod;
    const scheduledShowActive = Boolean(data.scheduledShowActive);

    // Hide preview banner in normal mode
    previewBanner.classList.add('hidden');

    if (isOutsideWindow && showPeriod) {
      const dateRange = showPeriod.startDate && showPeriod.endDate 
        ? `${showPeriod.startDate} - ${showPeriod.endDate}` : '';
      const timeRange = `${showPeriod.startTime} - ${showPeriod.endTime}`;
      const periodInfo = dateRange ? `${dateRange} | ${timeRange}` : timeRange;
      outsideWindowBanner.textContent = '';
      const line1 = document.createElement('span');
      line1.textContent = 'Außerhalb des Showzeitraums';
      const br1 = document.createElement('br');
      const line2 = document.createElement('span');
      line2.textContent = periodInfo;
      const br2 = document.createElement('br');
      const line3 = document.createElement('span');
      line3.textContent = 'Aktuell keine Wiedergabe möglich.';
      outsideWindowBanner.appendChild(line1);
      outsideWindowBanner.appendChild(br1);
      outsideWindowBanner.appendChild(line2);
      outsideWindowBanner.appendChild(br2);
      outsideWindowBanner.appendChild(line3);
      outsideWindowBanner.classList.remove('hidden');
      quietBanner.classList.add('hidden');
      scheduledShowBanner.classList.add('hidden');
      showRunningBanner.classList.add('hidden');
      note.textContent = data.note || '';
    } else if (isQuiet && showPeriod) {
      quietBanner.textContent = `Ruhezeit ${showPeriod.endTime}–${showPeriod.startTime} – keine Wiedergabe möglich.`;
      quietBanner.classList.remove('hidden');
      outsideWindowBanner.classList.add('hidden');
      scheduledShowBanner.classList.add('hidden');
      showRunningBanner.classList.add('hidden');
      note.textContent = data.note || '';
    } else if (scheduledShowActive && isRunning) {
      // Show scheduled show banner when a scheduled show is running
      scheduledShowBanner.textContent = 'Geplante Show gestartet – Wünsche pausiert.';
      scheduledShowBanner.classList.remove('hidden');
      quietBanner.classList.add('hidden');
      outsideWindowBanner.classList.add('hidden');
      showRunningBanner.classList.add('hidden');
      note.textContent = data.note || '';
    } else if (lockReason && !isQuiet && !isOutsideWindow) {
      // Show the lock reason in the banner instead of the note section
      showRunningBanner.textContent = lockReason;
      showRunningBanner.classList.remove('hidden');
      quietBanner.classList.add('hidden');
      outsideWindowBanner.classList.add('hidden');
      scheduledShowBanner.classList.add('hidden');
      note.textContent = data.note || '';
    } else {
      quietBanner.classList.add('hidden');
      outsideWindowBanner.classList.add('hidden');
      scheduledShowBanner.classList.add('hidden');
      showRunningBanner.classList.add('hidden');
      note.textContent = data.note || '';
    }

    renderQueue(data.currentRequest, data.queue || []);
  } catch (err) {
    console.error('Statusfehler', err);
    markStatus('error', 'Status konnte nicht geladen werden.');
    showNowPlaying(null);
    note.textContent = 'Bitte Verbindung zum Server prüfen.';
    setButtonsDisabled(true, '');
    updateAudioAvailability(false, false);
  }
}

async function startShow(type = 'playlist1') {
  if (previewMode) {
    showToast('Vorschau: Playlist würde jetzt starten.');
    return;
  }
  setButtonsDisabled(true, '');
  const startLabel = document.getElementById(type === 'playlist2' ? 'btn-kids-label' : 'btn-show-label');
  const startLabelText = startLabel.textContent;
  startLabel.textContent = 'Wird gestartet …';
  try {
    const response = await fetch('/api/show', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ type })
    });
    if (response.status === 403) {
      handleAccessDenied();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    showToast(data.message || 'Playlist wurde gestartet.');
    fetchState();
  } catch (err) {
    console.error('Startfehler', err);
    showToast('Playlist konnte nicht gestartet werden.');
    markStatus('error', 'Fehler beim Starten.');
  } finally {
    startLabel.textContent = startLabelText;
    // Re-apply the server-side locks instead of blindly re-enabling everything.
    setTimeout(fetchState, 1000);
  }
}

// ── Wunschliste (Panel auf der Hauptseite, damit die Musik weiterläuft) ──
const requestPanel = document.getElementById('request-panel');
const requestList = document.getElementById('request-list');
const requestClose = document.getElementById('request-close');
const mainButtons = document.getElementById('main-buttons');
let requestsDisabled = false;
let queuedTitles = new Set();

const sampleSongs = [
  { title: 'Jingle Bells (Fast Remix)', duration: 155 },
  { title: 'Stille Nacht (Orchester)', duration: 241 },
  { title: 'Carol of the Bells', duration: 192 },
  { title: 'O Tannenbaum', duration: 178 },
  { title: 'Feliz Navidad', duration: 203 },
];

function formatDuration(sec) {
  if (typeof sec !== 'number' || Number.isNaN(sec)) return '';
  const minutes = Math.floor(sec / 60);
  const seconds = String(Math.floor(sec % 60)).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function requestMessage(text) {
  const info = document.createElement('p');
  info.className = 'note';
  info.textContent = text;
  requestList.replaceChildren(info);
}

function updateRequestButtons() {
  requestList.querySelectorAll('button').forEach((btn) => {
    const taken = queuedTitles.has(btn.dataset.title);
    btn.disabled = requestsDisabled || taken;
    btn.textContent = taken ? 'Schon gewünscht' : 'Wünschen';
  });
}

function renderRequestList(songs) {
  requestList.replaceChildren();
  songs.forEach((song) => {
    const row = document.createElement('div');
    row.className = 'request-item';

    const label = document.createElement('div');
    label.className = 'request-meta';
    const titleEl = document.createElement('div');
    titleEl.className = 'request-title';
    titleEl.textContent = song.title;
    const durationEl = document.createElement('div');
    durationEl.className = 'request-duration';
    durationEl.textContent = formatDuration(song.duration);
    label.append(titleEl, durationEl);

    const action = document.createElement('button');
    action.type = 'button';
    action.dataset.title = song.title;
    const taken = queuedTitles.has(song.title);
    action.textContent = taken ? 'Schon gewünscht' : 'Wünschen';
    action.disabled = requestsDisabled || taken;
    action.addEventListener('click', () => submitRequest(song, action));

    row.append(label, action);
    requestList.appendChild(row);
  });
}

async function loadRequestSongs() {
  requestMessage('Wird geladen …');
  if (previewMode) {
    renderRequestList(sampleSongs);
    return;
  }
  try {
    const response = await fetch('/api/requests/songs');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const songs = data.songs || [];
    if (!songs.length) {
      requestMessage('Aktuell stehen keine Lieder zur Auswahl.');
      return;
    }
    renderRequestList(songs);
  } catch (err) {
    console.error('Playlist-Ladefehler', err);
    requestMessage('Die Wunschliste konnte nicht geladen werden. Bitte später erneut versuchen.');
  }
}

function openRequestPanel() {
  requestPanel.classList.remove('hidden');
  mainButtons.classList.add('hidden');
  if (location.hash !== '#wunsch') history.replaceState(null, '', '#wunsch');
  loadRequestSongs();
}

function closeRequestPanel() {
  requestPanel.classList.add('hidden');
  mainButtons.classList.remove('hidden');
  if (location.hash === '#wunsch') history.replaceState(null, '', location.pathname + location.search);
}

async function submitRequest(song, button) {
  const title = song.title;
  if (previewMode) {
    showToast(`Vorschau: "${title}" würde hinzugefügt.`);
    closeRequestPanel();
    return;
  }
  button.disabled = true;
  try {
    const response = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ song: title })
    });
    if (response.status === 403) {
      handleAccessDenied();
      return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok && !data.message) throw new Error(`HTTP ${response.status}`);
    showToast(data.message || `Wunsch "${title}" wurde hinzugefügt.`);
    if (response.ok || response.status === 409) {
      closeRequestPanel();
      fetchState();
    }
  } catch (err) {
    console.error('Wunschfehler', err);
    showToast('Wunsch konnte nicht angelegt werden.');
  } finally {
    updateRequestButtons();
  }
}

requestClose.addEventListener('click', closeRequestPanel);

// ── Musik auf dem Gerät (FalconBeat) ─────────────────────────────
const btnAudio = document.getElementById('btn-audio');
const audioIcon = document.getElementById('audio-icon');
const audioTooltip = document.getElementById('audio-tooltip');
const audioLabel = document.getElementById('audio-label');
const audioHintKey = 'fpp-audio-hint-shown';
const audioIdleLeaveMs = 5 * 60 * 1000; // stop listening when nothing played for a while
const audioSupported = Boolean(config.falconbeatEnabled !== false && window.FalconBeatAudio && FalconBeatAudio.isSupported());
const audioEngine = audioSupported
  ? FalconBeatAudio.create({ base: config.falconbeatClientBase || '/falconbeat' })
  : null;
let audioAvailable = false;
let audioShowRunning = false;
let audioIdleTimer = null;

function renderAudioButton() {
  if (!audioEngine) return;
  const state = audioEngine.getState();
  // Visible while a show runs; stays visible while listening so it can be switched off.
  const visible = state.joined || (audioAvailable && audioShowRunning);
  btnAudio.classList.toggle('hidden', !visible);
  if (!visible) return;

  let icon = 'volume-xmark';
  let shortLabel = 'Musik hören';
  let label = 'Musik auf diesem Gerät einschalten – der Ton läuft synchron zur Lichtershow.';
  let mode = 'off';
  if (state.joined) {
    if (state.error === 'connection') {
      icon = 'triangle-exclamation';
      shortLabel = 'Kein Ton';
      label = 'Keine Verbindung zur Musik. Tippen zum Ausschalten.';
      mode = 'error';
    } else if (state.phase !== 'ready') {
      icon = 'spinner';
      shortLabel = 'Lädt …';
      label = 'Musik wird verbunden und synchronisiert …';
      mode = 'loading';
    } else if (state.isPlaying) {
      icon = 'volume-high';
      shortLabel = 'Musik an';
      label = 'Musik läuft auf diesem Gerät. Tippen zum Ausschalten.';
      mode = 'on';
    } else if (state.sourcesLoaded < state.sourcesTotal) {
      icon = 'spinner';
      shortLabel = 'Lädt …';
      label = 'Musik wird geladen …';
      mode = 'loading';
    } else {
      icon = 'volume-low';
      shortLabel = 'Musik an';
      label = 'Musik ist eingeschaltet und startet mit dem nächsten Lied. Tippen zum Ausschalten.';
      mode = 'on';
    }
  }
  FPPApp.setIcon(audioIcon, icon, icon === 'spinner');
  audioLabel.textContent = shortLabel;
  btnAudio.dataset.mode = mode;
  btnAudio.setAttribute('aria-pressed', state.joined ? 'true' : 'false');
  btnAudio.setAttribute('aria-label', label);
  audioTooltip.textContent = label;

  // Do not keep the connection (and the screen) alive forever after the show.
  if (state.joined && !state.isPlaying && !audioShowRunning) {
    if (!audioIdleTimer) {
      audioIdleTimer = setTimeout(() => {
        audioIdleTimer = null;
        audioEngine.leave();
      }, audioIdleLeaveMs);
    }
  } else if (audioIdleTimer) {
    clearTimeout(audioIdleTimer);
    audioIdleTimer = null;
  }
}

function updateAudioAvailability(available, showRunning) {
  if (!audioEngine) return;
  const wasVisible = !btnAudio.classList.contains('hidden');
  audioAvailable = available;
  audioShowRunning = showRunning;
  renderAudioButton();
  const isVisible = !btnAudio.classList.contains('hidden');
  if (isVisible && !wasVisible && !audioEngine.getState().joined) {
    let hintShown = false;
    try { hintShown = sessionStorage.getItem(audioHintKey) === 'yes'; } catch { /* ignore */ }
    if (!hintShown) {
      showToast('Tipp: Über das Lautsprecher-Symbol hörst du die Musik direkt auf deinem Gerät.');
      try { sessionStorage.setItem(audioHintKey, 'yes'); } catch { /* ignore */ }
    }
  }
}

if (audioEngine) {
  audioEngine.subscribe(renderAudioButton);
  btnAudio.addEventListener('click', () => {
    const wasJoined = audioEngine.getState().joined;
    audioEngine.toggle();
    if (!wasJoined && audioEngine.getState().error === 'unsupported') {
      showToast('Dieser Browser kann die Musik leider nicht abspielen.');
    }
  });
}

btnShow.addEventListener('click', () => startShow('playlist1'));
btnKids.addEventListener('click', () => startShow('playlist2'));
btnRequest.addEventListener('click', openRequestPanel);
btnDonate.addEventListener('click', () => {
  if (audioEngine && audioEngine.getState().joined &&
      !window.confirm('Beim Wechsel zur Spendenseite stoppt die Musik auf diesem Gerät. Fortfahren?')) {
    return;
  }
  window.location.href = '/donation';
});

// Poll faster while a show runs; pause completely while the tab is hidden.
const activePollMs = Math.min(statusPollMs, 4000);
let showIsRunning = false;
let pollingStarted = false;

function scheduleNextPoll() {
  clearTimeout(pollHandle);
  if (document.visibilityState === 'hidden') return;
  pollHandle = setTimeout(pollOnce, showIsRunning ? activePollMs : statusPollMs);
}

async function pollOnce() {
  await fetchState();
  scheduleNextPoll();
}

function startPolling() {
  if (pollingStarted) return;
  pollingStarted = true;
  pollOnce();
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') pollOnce(); else clearTimeout(pollHandle);
  });
}

function unlock() {
  accessGate.classList.add('hidden');
  mainContent.classList.remove('hidden');
  accessError.textContent = '';
  accessHint.textContent = '';
  clearInterval(accessHintTimer);
  accessHintTimer = null;
  startPolling();
  if (location.hash === '#wunsch') openRequestPanel();
}

// ── Zugangscode (fest oder Tagescode an der Matrix) ──────────────
const accessOnMatrix = Boolean(config.accessOnMatrix);
const accessNote = document.getElementById('access-note');
const accessHint = document.getElementById('access-hint');
let accessHintTimer = null;

if (accessOnMatrix) {
  accessNote.textContent = config.accessHint ||
    'Gib den Zahlencode ein, der an der Leucht-Matrix am Haus angezeigt wird. Er ändert sich jeden Tag.';
  accessInput.type = 'text';
  accessInput.inputMode = 'numeric';
  accessInput.autocomplete = 'off';
  accessInput.placeholder = 'Code';
  accessInput.setAttribute('aria-label', 'Zahlencode von der Matrix');
}

// Tell waiting visitors why the matrix shows no code right now.
async function updateAccessHint() {
  if (!accessOnMatrix || accessGate.classList.contains('hidden')) return;
  try {
    const response = await fetch('/api/state');
    if (!response.ok) return;
    const data = await response.json();
    const locks = data.locks || {};
    if (data.accessCode && data.accessCode.visible) {
      accessHint.textContent = 'Der Code leuchtet jetzt an der Matrix.';
    } else if (locks.outsideShowWindow || locks.quiet) {
      accessHint.textContent = 'Außerhalb der Showzeiten wird kein Code angezeigt.';
    } else if (data.status && data.status.is_running) {
      accessHint.textContent = 'Gerade läuft ein Lied. Der Code erscheint an der Matrix, sobald es zu Ende ist.';
    } else {
      accessHint.textContent = '';
    }
  } catch { /* ignore */ }
}

function showAccessGate(message) {
  accessGate.classList.remove('hidden');
  mainContent.classList.add('hidden');
  accessError.textContent = message || '';
  if (accessOnMatrix && !accessHintTimer) {
    updateAccessHint();
    accessHintTimer = setInterval(updateAccessHint, 4000);
  }
}

async function validateAccess() {
  if (!access.required) {
    unlock();
    return;
  }
  if (!access.code()) {
    showAccessGate('');
    return;
  }
  // A stored code may be outdated (daily code): let the server decide.
  try {
    const response = await fetch('/api/access', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...access.headers() },
      body: '{}'
    });
    if (response.status === 403) {
      access.clear();
      showAccessGate(accessOnMatrix ? 'Der Code wechselt täglich – bitte den heutigen Code eingeben.' : '');
      return;
    }
  } catch { /* offline: keep the stored code, the next action checks again */ }
  unlock();
}

accessSubmit.addEventListener('click', async () => {
  const value = (accessInput.value || '').trim();
  if (!value) return;
  accessSubmit.disabled = true;
  try {
    const response = await fetch('/api/access', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accessCode: value })
    });
    if (response.ok) {
      access.store(value);
      accessInput.value = '';
      unlock();
    } else if (response.status === 403) {
      accessError.textContent = 'Falscher Code – bitte erneut versuchen.';
      accessInput.focus();
    } else if (response.status === 429) {
      const data = await response.json().catch(() => ({}));
      accessError.textContent = data.message || 'Zu viele Fehlversuche – bitte später erneut versuchen.';
    } else {
      accessError.textContent = 'Der Code konnte nicht geprüft werden. Bitte später erneut versuchen.';
    }
  } catch (err) {
    accessError.textContent = 'Keine Verbindung zum Server.';
  } finally {
    accessSubmit.disabled = false;
  }
});

accessInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    accessSubmit.click();
  }
});

// Check for pending toast from song request
function checkPendingToast() {
  const pendingToast = sessionStorage.getItem('pendingToast');
  if (pendingToast) {
    try {
      const data = JSON.parse(pendingToast);
      sessionStorage.removeItem('pendingToast');
      if (data && typeof data === 'object' && typeof data.message === 'string' && data.message) {
        showToast(data.message);
      }
    } catch (err) {
      console.error('Failed to parse pending toast', err);
      sessionStorage.removeItem('pendingToast');
    }
  }
}

FPPApp.renderSocialFooter({ alwaysShow: true });
validateAccess();
checkPendingToast();
