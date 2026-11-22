'use strict';

const { config, access, showToast, t } = FPPApp;
const locale = FPPApp.locale;
const headline = document.getElementById('headline');
const subtitle = document.getElementById('subtitle');
// One button per configured show (rendered by the server, data-show = its id).
const showButtons = Array.from(document.querySelectorAll('[data-show]'));
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
const accessDialog = document.getElementById('access-dialog');
const accessForm = document.getElementById('access-form');
const accessCancel = document.getElementById('access-cancel');
const accessInput = document.getElementById('access-input');
const accessSubmit = document.getElementById('access-submit');
const accessError = document.getElementById('access-error');
const queueSection = document.getElementById('queue-section');
const queueList = document.getElementById('queue-list');
const queueEmpty = document.getElementById('queue-empty');
const queueCount = document.getElementById('queue-count');

const statusPollMs = Math.max(3000, Number(config.statusPollMs || 10000));
const previewMode = Boolean(config.previewMode);
let countdownTimer;
let pollHandle;

const authHeaders = access.headers;

// The server rejected the stored code (e.g. the daily code changed):
// forget it and ask again; the caller retries the action once.
function handleAccessDenied() {
  access.clear();
  return requireAccess(accessOnMatrix ? t('access.retryDaily') : t('access.retry'));
}

headline.textContent = FPPApp.siteName;
subtitle.textContent = config.siteSubtitle || t('site.defaultSubtitle');
// Times & address: open outside show hours (that is when people need them),
// collapsed during show hours so the controls move up. A manual toggle wins.
const siteInfo = document.getElementById('site-info');
siteInfo.open = true;
let siteInfoTouched = false;
let siteInfoShowTime = null;
siteInfo.querySelector('summary').addEventListener('click', () => { siteInfoTouched = true; });

function updateSiteInfo(inShowTime) {
  if (siteInfoTouched || inShowTime === siteInfoShowTime) return;
  siteInfoShowTime = inShowTime;
  siteInfo.open = !inShowTime;
}

function setButtonsDisabled(disabled, message) {
  [...showButtons, btnRequest].forEach((btn) => btn.disabled = disabled);
  if (message !== undefined) {
    note.textContent = message;
  }
}

function applyLocks(locks) {
  const disableAll = Boolean(locks && locks.disableAllButtons);
  const disableShows = Boolean(locks && locks.disableShowButtons);
  showButtons.forEach((btn) => { btn.disabled = disableAll || disableShows; });
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
    items.push({ title: entryTitle(currentRequest, t('queue.current')), label: t('queue.playingNow'), mine: currentRequest.mine });
  }

  (queue || []).forEach((entry, idx) => {
    const title = entryTitle(entry, t('queue.wishNumber', { number: idx + 1 }));
    const isCurrent = currentRequest && entryTitle(currentRequest) === entryTitle(entry) && idx === 0;
    if (!isCurrent) {
      const wait = typeof entry.waitSeconds === 'number' && entry.waitSeconds > 0
      ? ` · ${t('queue.wait', { minutes: Math.max(1, Math.round(entry.waitSeconds / 60)) })}` : '';
    items.push({ title, label: `${t('queue.position', { number: idx + 1 })}${wait}`, mine: entry.mine });
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
  queueCount.textContent = t('queue.count', { count: items.length });

  items.forEach((item) => {
    const li = document.createElement('li');
    li.className = item.mine ? 'queue-item queue-item-mine' : 'queue-item';
    const titleEl = document.createElement('div');
    titleEl.className = 'queue-title';
    titleEl.textContent = item.title;
    const badge = document.createElement('span');
    badge.className = 'queue-badge';
    badge.textContent = item.mine ? t('queue.mine', { label: item.label }) : item.label;
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

// "Now playing": readable title and a local countdown between two polls.
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
  const kind = nowPlaying.kind === 'wish' ? t('nowPlaying.wish') : t('nowPlaying.show');
  let remaining = typeof nowPlaying.secondsRemaining === 'number' ? nowPlaying.secondsRemaining : null;
  const render = () => {
    statusDetails.textContent = remaining !== null && remaining > 0
      ? t('nowPlaying.remaining', { kind, time: formatRemaining(remaining) })
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
  // More than a day away: "3 days" reads better than "74:12:09"
  const days = Math.floor(totalSeconds / 86400);
  if (days >= 2) return t('countdown.days', { days });
  return `${hours}:${minutes}:${seconds}`;
}

function updateCountdown(nextShow, scheduledShowsEnabled = true) {
  clearInterval(countdownTimer);
  if (!scheduledShowsEnabled) {
    countdownEl.textContent = t('countdown.none');
    return;
  }
  if (!nextShow || !nextShow.time) {
    countdownEl.textContent = t('countdown.calculating');
    return;
  }
  const target = new Date(nextShow.time);
  // A short name if one is set ("Next kids' show"), the first button's show
  // plainly ("Next show"), any other playlist by its name in quotes.
  const showName = nextShow.name ? t('countdown.nextShowName', { name: nextShow.name })
    : nextShow.kind !== 'playlist1' && nextShow.label ? t('countdown.nextNamed', { name: nextShow.label })
    : t('countdown.next');
  const startTime = target.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  const sameDay = target.toDateString() === new Date().toDateString();
  const when = sameDay ? t('countdown.today', { time: startTime })
    : t('countdown.otherDay', { date: target.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' }), time: startTime });
  countdownTimer = setInterval(() => {
    const diff = target - new Date();
    if (diff <= 0) {
      countdownEl.textContent = t('countdown.startingNow');
      return;
    }
    countdownEl.textContent = t('countdown.line', { show: showName, when, remaining: formatCountdown(diff) });
  }, 1000);
}

function renderSampleState() {
  const now = new Date();
  const next = new Date(now.getTime() + 18 * 60 * 1000);
  const queue = [{ title: t('preview.wish1') }, { title: t('preview.wish2') }];
  markStatus('', t('status.readyPreview'));
  showNowPlaying(null);
  updateCountdown({ time: next.toISOString(), label: 'Show', kind: 'playlist1' });
  previewBanner.textContent = t('banner.preview');
  previewBanner.classList.remove('hidden');
  applyLocks({ disableAllButtons: false, disableShowButtons: false });
  renderQueue(queue[0], queue);
}

// The server names its current build with every status. A tab that was opened
// before an update (or restored from the browser's memory) reloads itself once,
// but never while someone is listening to the music.
const loadedBuild = (document.querySelector('meta[name="app-build"]') || {}).content || '';
const reloadedBuildKey = 'fpp-reloaded-build';

function reloadIfOutdated(serverBuild) {
  if (!serverBuild || !loadedBuild || serverBuild === loadedBuild) return false;
  if (audioEngine && audioEngine.getState().joined) return false;
  try {
    if (sessionStorage.getItem(reloadedBuildKey) === serverBuild) return false; // tried already
    sessionStorage.setItem(reloadedBuildKey, serverBuild);
  } catch (err) {
    return false; // without storage a reload could repeat endlessly
  }
  window.location.reload();
  return true;
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
    if (reloadIfOutdated(data.build)) return;

    const status = data.status || {};
    const isRunning = Boolean(status.is_running);
    const fppOffline = data.fppReachable === false;
    showIsRunning = isRunning || Boolean(data.currentRequest) || (data.queue || []).length > 0;

    if (fppOffline) {
      markStatus('error', t('status.offline'));
      showNowPlaying(null);
    } else if (isRunning) {
      const nowPlaying = data.nowPlaying || {};
      markStatus('running', nowPlaying.title ? t('status.nowPlaying', { title: nowPlaying.title }) : t('status.showRunning'));
      showNowPlaying(nowPlaying);
    } else {
      const locked = Boolean(data.locks && (data.locks.quiet || data.locks.outsideShowWindow || data.locks.manual));
      markStatus('', locked ? t('status.idleLocked') : t('status.ready'));
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
    updateSiteInfo(!isQuiet && !isOutsideWindow);
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
      line1.textContent = t('banner.outsideWindow');
      const br1 = document.createElement('br');
      const line2 = document.createElement('span');
      line2.textContent = periodInfo;
      const br2 = document.createElement('br');
      const line3 = document.createElement('span');
      line3.textContent = t('banner.noPlayback');
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
      quietBanner.textContent = t('banner.quiet', { end: showPeriod.endTime, start: showPeriod.startTime });
      quietBanner.classList.remove('hidden');
      outsideWindowBanner.classList.add('hidden');
      scheduledShowBanner.classList.add('hidden');
      showRunningBanner.classList.add('hidden');
      note.textContent = data.note || '';
    } else if (scheduledShowActive && isRunning) {
      // Show scheduled show banner when a scheduled show is running
      scheduledShowBanner.textContent = t('banner.scheduledShow');
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
    console.error('Status error', err);
    markStatus('error', t('status.loadFailed'));
    showNowPlaying(null);
    note.textContent = t('status.checkConnection');
    setButtonsDisabled(true, '');
    updateAudioAvailability(false, false);
  }
}

async function startShow(type = 'playlist1', retried = false) {
  if (previewMode) {
    showToast(t('show.previewStart'));
    return;
  }
  if (!(await requireAccess())) return;
  setButtonsDisabled(true, '');
  const button = showButtons.find((btn) => btn.dataset.show === type);
  const startLabel = button ? button.querySelector('.action-label') : document.createElement('span');
  const startLabelText = startLabel.textContent;
  startLabel.textContent = t('button.starting');
  try {
    const response = await fetch('/api/show', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ type })
    });
    if (response.status === 403) {
      startLabel.textContent = startLabelText;
      if (!retried && (await handleAccessDenied())) startShow(type, true);
      return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      // e.g. 409: the show would run past the end of the show time
      if (data.message) {
        showToast(data.message);
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }
    showToast(data.message || t('show.startedDefault'));
    fetchState();
  } catch (err) {
    console.error('Start error', err);
    showToast(t('show.startFailed'));
    markStatus('error', t('status.startError'));
  } finally {
    startLabel.textContent = startLabelText;
    // Re-apply the server-side locks instead of blindly re-enabling everything.
    setTimeout(fetchState, 1000);
  }
}

// ── Song requests (a panel on the main page, so the music keeps playing) ──
const requestPanel = document.getElementById('request-panel');
const requestList = document.getElementById('request-list');
const requestClose = document.getElementById('request-close');
const mainButtons = document.getElementById('main-buttons');
let requestsDisabled = false;
let queuedTitles = new Set();

const sampleSongs = [
  { title: t('preview.song1'), duration: 155 },
  { title: t('preview.song2'), duration: 241 },
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

function requestButtonState(title, tooLate) {
  if (queuedTitles.has(title)) return { label: t('request.taken'), disabled: true };
  if (tooLate) return { label: t('request.tooLate'), disabled: true };
  return { label: t('request.wish'), disabled: requestsDisabled };
}

function updateRequestButtons() {
  requestList.querySelectorAll('button').forEach((btn) => {
    const state = requestButtonState(btn.dataset.title, btn.dataset.tooLate === 'true');
    btn.disabled = state.disabled || requestsDisabled;
    btn.textContent = state.label;
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
    // The server marks songs that would end after the show time.
    action.dataset.tooLate = song.fits === false ? 'true' : 'false';
    const state = requestButtonState(song.title, song.fits === false);
    action.textContent = state.label;
    action.disabled = state.disabled || requestsDisabled;
    action.addEventListener('click', () => submitRequest(song, action));

    row.append(label, action);
    requestList.appendChild(row);
  });
}

async function loadRequestSongs() {
  requestMessage(t('request.loading'));
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
      requestMessage(t('request.none'));
      return;
    }
    renderRequestList(songs);
  } catch (err) {
    console.error('Song list error', err);
    requestMessage(t('request.loadFailed'));
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

async function submitRequest(song, button, retried = false) {
  const title = song.title;
  if (previewMode) {
    showToast(t('request.previewAdded', { title }));
    closeRequestPanel();
    return;
  }
  if (!(await requireAccess())) return;
  button.disabled = true;
  try {
    const response = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ song: title })
    });
    if (response.status === 403) {
      if (!retried && (await handleAccessDenied())) submitRequest(song, button, true);
      return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok && !data.message) throw new Error(`HTTP ${response.status}`);
    showToast(data.message || t('request.added', { title }));
    if (response.ok || response.status === 409) {
      closeRequestPanel();
      fetchState();
    }
  } catch (err) {
    console.error('Request error', err);
    showToast(t('request.failed'));
  } finally {
    updateRequestButtons();
  }
}

requestClose.addEventListener('click', closeRequestPanel);

// ── Music on the visitor's device (FalconBeat) ────────────────────
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
  let shortLabel = t('audio.listen');
  let label = t('audio.listenLabel');
  let mode = 'off';
  if (state.joined) {
    if (state.error === 'connection') {
      icon = 'triangle-exclamation';
      shortLabel = t('audio.noSound');
      label = t('audio.noConnection');
      mode = 'error';
    } else if (state.phase !== 'ready') {
      icon = 'spinner';
      shortLabel = t('audio.loading');
      label = t('audio.connecting');
      mode = 'loading';
    } else if (state.isPlaying) {
      icon = 'volume-high';
      shortLabel = t('audio.on');
      label = t('audio.playing');
      mode = 'on';
    } else if (state.sourcesFailed > 0) {
      icon = 'triangle-exclamation';
      shortLabel = t('audio.noSound');
      label = t('audio.trackFailed');
      mode = 'error';
    } else if (state.sourcesLoaded < state.sourcesTotal) {
      icon = 'spinner';
      shortLabel = t('audio.loading');
      label = t('audio.loadingTrack');
      mode = 'loading';
    } else {
      icon = 'volume-low';
      shortLabel = t('audio.on');
      label = t('audio.waiting');
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
      showToast(t('audio.hint'));
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
      showToast(t('audio.unsupported'));
    }
  });
}

showButtons.forEach((btn) => btn.addEventListener('click', () => startShow(btn.dataset.show)));
btnRequest.addEventListener('click', openRequestPanel);
btnDonate.addEventListener('click', () => {
  if (audioEngine && audioEngine.getState().joined &&
      !window.confirm(t('audio.leaveForDonation'))) {
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
  // Safari shows a page kept in memory when navigating back; refresh it at once.
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) pollOnce();
  });
}

// ── Access code (fixed, or the daily code on the matrix) ──────────
// Everyone sees the page and its controls. The code is asked for only when
// an action needs it (start a show, wish a song), then the action continues.
const accessOnMatrix = Boolean(config.accessOnMatrix);
const accessNote = document.getElementById('access-note');
const accessHint = document.getElementById('access-hint');
let accessHintTimer = null;
let accessResolve = null;

if (accessOnMatrix) {
  accessNote.textContent = config.accessHint || t('access.noteMatrix');
  accessInput.type = 'text';
  accessInput.inputMode = 'numeric';
  accessInput.placeholder = t('access.placeholderMatrix');
  accessInput.setAttribute('aria-label', t('access.ariaMatrix'));
} else {
  accessNote.textContent = t('access.noteFixed');
}

// Tell waiting visitors why the matrix shows no code right now.
async function updateAccessHint() {
  if (!accessOnMatrix || !accessDialog.open) return;
  try {
    const response = await fetch('/api/state');
    if (!response.ok) return;
    const data = await response.json();
    const locks = data.locks || {};
    if (data.accessCode && data.accessCode.visible) {
      accessHint.textContent = t('access.hintVisible');
    } else if (locks.manual) {
      accessHint.textContent = locks.reason || '';
    } else if (locks.outsideShowWindow || locks.quiet) {
      accessHint.textContent = t('access.hintOutside');
    } else if (data.status && data.status.is_running) {
      accessHint.textContent = t('access.hintSongPlaying');
    } else {
      accessHint.textContent = '';
    }
  } catch { /* ignore */ }
}

function closeAccessDialog(granted) {
  clearInterval(accessHintTimer);
  accessHintTimer = null;
  if (accessDialog.open) accessDialog.close();
  accessInput.value = '';
  accessError.textContent = '';
  accessHint.textContent = '';
  const resolve = accessResolve;
  accessResolve = null;
  if (resolve) resolve(granted);
}

/**
 * Resolves true when the visitor may act: no code needed, a code is already
 * stored, or they entered a valid one now. Resolves false when they cancel.
 */
function requireAccess(message) {
  if (!access.required || access.code()) return Promise.resolve(true);
  if (accessResolve) return Promise.resolve(false); // dialog already open
  accessError.textContent = message || '';
  if (typeof accessDialog.showModal === 'function') {
    accessDialog.showModal();
  } else {
    accessDialog.setAttribute('open', '');
  }
  accessInput.focus();
  if (accessOnMatrix) {
    updateAccessHint();
    accessHintTimer = setInterval(updateAccessHint, 4000);
  }
  return new Promise((resolve) => { accessResolve = resolve; });
}

accessForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const value = (accessInput.value || '').trim();
  if (!value) {
    accessInput.focus();
    return;
  }
  accessSubmit.disabled = true;
  try {
    const response = await fetch('/api/access', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accessCode: value })
    });
    if (response.ok) {
      access.store(value);
      closeAccessDialog(true);
    } else if (response.status === 403) {
      accessError.textContent = t('access.wrong');
      accessInput.select();
    } else if (response.status === 429) {
      const data = await response.json().catch(() => ({}));
      accessError.textContent = data.message || t('access.tooMany');
    } else {
      accessError.textContent = t('access.checkFailed');
    }
  } catch (err) {
    accessError.textContent = t('access.noServer');
  } finally {
    accessSubmit.disabled = false;
  }
});

accessCancel.addEventListener('click', () => closeAccessDialog(false));
// Esc / back gesture closes the native dialog
accessDialog.addEventListener('cancel', (e) => {
  e.preventDefault();
  closeAccessDialog(false);
});
// Tap on the dimmed backdrop closes it, too
accessDialog.addEventListener('click', (e) => {
  if (e.target === accessDialog) closeAccessDialog(false);
});

// A stored code may be outdated (daily code): check quietly, ask again only
// when the visitor actually wants to do something.
async function checkStoredAccess() {
  if (!access.required || !access.code()) return;
  try {
    const response = await fetch('/api/access', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...access.headers() },
      body: '{}'
    });
    if (response.status === 403) access.clear();
  } catch { /* offline: the next action checks again */ }
}

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

FPPApp.renderSocialFooter();
startPolling();
if (location.hash === '#wunsch') openRequestPanel();
checkStoredAccess();
checkPendingToast();
