/*
 * FalconBeat audio client for fpp-web-control.
 *
 * Plays the show audio on the visitor's device, in sync with the lights.
 * It talks to a FalconBeat server (https://github.com/GraphicHealer/FalconBeat),
 * which is built on BeatSync (https://github.com/freeman-jiang/beatsync).
 *
 * This file is a dependency-free port of FalconBeat's listener engine
 * (web/src/sync/{engine,clock,audio}.ts), MIT License,
 * Copyright (c) 2026 GraphicHealer. BeatSync: MIT License, (c) freeman-jiang.
 *
 * The server is reached below a base path (default "/falconbeat") that a
 * reverse proxy forwards to the FalconBeat container:
 *   <base>/ws        WebSocket: clock sync + play/pause schedule
 *   <base>/media/*   audio files
 *
 * Usage:
 *   const audio = FalconBeatAudio.create({ base: '/falconbeat' });
 *   audio.subscribe((state) => ...);   // state.phase, state.isPlaying, ...
 *   button.onclick = () => audio.toggle();   // must run inside a user gesture
 */
(function (global) {
  'use strict';

  // ── Protocol constants (beatsync shared/constants.ts) ─────────────
  var NTP = {
    INITIAL_INTERVAL_MS: 50,
    STEADY_STATE_INTERVAL_MS: 2500,
    RESPONSE_TIMEOUT_MS: 3750,
    MAX_MEASUREMENTS: 16,
    PROBE_GAP_MS: 25,
    PROBE_GAP_TOLERANCE_MS: 5
  };
  var ROOM_ID = '000000'; // fixed by the FalconBeat plugin
  var CONNECTION_TIMEOUT_MS = 5000;
  var MAX_RECONNECT_ATTEMPTS = 15;
  var RECONNECT_BASE_MS = 1000;
  var RECONNECT_MAX_MS = 10000;
  // Reported outputLatency above this is garbage (Bluetooth often reports ~650ms)
  var MAX_TRUSTWORTHY_OUTPUT_LATENCY_MS = 100;
  // 1-sample silent WAV: forces the media channel on iOS < 16.4 (mute switch)
  var SILENCE_DATA_URL =
    'data:audio/wav;base64,UklGRiYAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQIAAAAAAA==';

  function epochNow() {
    return performance.timeOrigin + performance.now();
  }

  function isContextPaused(state) {
    return state === 'suspended' || state === 'interrupted';
  }

  function isIOS() {
    var ua = navigator.userAgent.toLowerCase();
    return ua.indexOf('iphone') >= 0 || ua.indexOf('ipad') >= 0 || ua.indexOf('ipod') >= 0 ||
      (ua.indexOf('mac os x') >= 0 && navigator.maxTouchPoints > 0);
  }

  function isSupported() {
    return Boolean((global.AudioContext || global.webkitAudioContext) && global.WebSocket && global.fetch);
  }

  function storageGet(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  function storageSet(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  function randomId() {
    if (global.crypto && typeof global.crypto.randomUUID === 'function') return global.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function create(options) {
    options = options || {};
    var base = String(options.base || '/falconbeat').replace(/\/+$/, '');

    // ── Audio context ───────────────────────────────────────────────
    var ctx = null;
    var masterGain = null;
    var wakeLock = null;
    var wakeLockVisibilityWired = false;
    var silentAudio = null;

    // ── Clock sync ──────────────────────────────────────────────────
    var ws = null;
    var measurements = [];
    var offsetEstimate = 0;
    var rttEstimate = 0;
    var isSynced = false;
    var probeGroupCounter = 0;
    var pendingFirstProbe = null;
    var pendingFirstProbeGroupId = null;
    var heartbeatTimer = null;
    var lastNtpRequestAt = null;
    var reconnectTimer = null;
    var connectWatchdog = null;
    var reconnectAttempt = 0;

    // ── Playback ────────────────────────────────────────────────────
    var joined = false;
    var sources = new Map(); // url -> { status, buffer }
    var currentSource = null;
    var isPlaying = false;
    var currentUrl = null;
    var playbackStartCtxTime = 0;
    var playbackOffset = 0;
    var trackDuration = 0;

    var listeners = new Set();
    var lastError = null;

    // ── State for the UI ────────────────────────────────────────────
    function snapshot() {
      var loaded = 0;
      sources.forEach(function (s) { if (s.status === 'loaded') loaded++; });
      var phase = 'idle';
      if (joined) {
        var connected = ws && ws.readyState === WebSocket.OPEN;
        if (!connected) phase = reconnectAttempt > 0 ? 'reconnecting' : 'connecting';
        else if (!isSynced) phase = 'syncing';
        else phase = 'ready';
      }
      return {
        phase: phase,
        joined: joined,
        isPlaying: isPlaying,
        sourcesLoaded: loaded,
        sourcesTotal: sources.size,
        error: lastError
      };
    }

    function emit() {
      var state = snapshot();
      listeners.forEach(function (cb) {
        try { cb(state); } catch (e) { console.error('FalconBeat listener failed', e); }
      });
    }

    // ── Audio context handling ──────────────────────────────────────
    function getContext() {
      if (!ctx || ctx.state === 'closed') {
        var Ctor = global.AudioContext || global.webkitAudioContext;
        ctx = new Ctor();
        masterGain = ctx.createGain();
        masterGain.gain.value = 1.0;
        masterGain.connect(ctx.destination);
        ctx.onstatechange = function () {
          // iOS can interrupt the context (calls, Control Center). Playback is
          // desynced afterwards: stop and ask the room where it is on resume.
          if (isContextPaused(ctx.state) && isPlaying) {
            stopPlaybackLocal();
            emit();
          }
          if (ctx.state === 'running' && joined) requestSync();
        };
        // iOS 16.4+: play through the media channel even when muted.
        try {
          if (navigator.audioSession) navigator.audioSession.type = 'playback';
        } catch (e) { /* not supported */ }
      }
      return ctx;
    }

    function outputLatencyMs() {
      var raw = ((ctx && ctx.outputLatency) || 0) * 1000;
      return raw > MAX_TRUSTWORTHY_OUTPUT_LATENCY_MS ? 0 : raw;
    }

    function startSilentAudioBypass() {
      // iOS < 16.4 only: a looping silent <audio> forces the media channel.
      if (silentAudio || navigator.audioSession || !isIOS()) return;
      var el = document.createElement('audio');
      el.setAttribute('x-webkit-airplay', 'deny');
      el.loop = true;
      el.preload = 'auto';
      el.src = SILENCE_DATA_URL;
      silentAudio = el;
      el.play().catch(function () { silentAudio = null; });
    }

    function requestWakeLock() {
      // A screen wake lock keeps Wi-Fi out of power-save mode, which would
      // delay packets by 100-300 ms and destroy the sync.
      if (wakeLock || !('wakeLock' in navigator)) return;
      navigator.wakeLock.request('screen').then(function (lock) {
        if (!joined) { lock.release().catch(function () {}); return; }
        wakeLock = lock;
        lock.addEventListener('release', function () { wakeLock = null; });
      }).catch(function () { /* best effort */ });
      if (!wakeLockVisibilityWired) {
        wakeLockVisibilityWired = true;
        document.addEventListener('visibilitychange', function () {
          if (document.visibilityState === 'visible' && joined && !wakeLock) requestWakeLock();
        });
      }
    }

    function releaseWakeLock() {
      if (wakeLock) {
        wakeLock.release().catch(function () {});
        wakeLock = null;
      }
    }

    // ── WebSocket lifecycle ─────────────────────────────────────────
    function clientId() {
      var id = storageGet('falconbeat-client-id');
      if (!id) {
        id = randomId();
        storageSet('falconbeat-client-id', id);
      }
      return id;
    }

    function wsUrl() {
      var absolute = /^https?:\/\//i.test(base) ? base : location.origin + base;
      var id = clientId();
      return absolute.replace(/^http/i, 'ws') + '/ws?roomId=' + ROOM_ID +
        '&username=' + encodeURIComponent('web-' + id.slice(0, 6)) +
        '&clientId=' + encodeURIComponent(id);
    }

    function mediaUrl(url) {
      // Sources are registered relative ("/media/<file>"): serve them from our base path.
      return url.charAt(0) === '/' ? base + url : url;
    }

    function send(message) {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
    }

    function requestSync() {
      send({ type: 'SYNC' });
    }

    function resetProbeState() {
      probeGroupCounter = 0;
      pendingFirstProbe = null;
      pendingFirstProbeGroupId = null;
    }

    function connect() {
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
      teardownSocket();

      var socket;
      try {
        socket = new WebSocket(wsUrl());
      } catch (e) {
        console.error('FalconBeat WebSocket failed', e);
        scheduleReconnect();
        return;
      }
      ws = socket;

      socket.onopen = function () {
        reconnectAttempt = 0;
        clearReconnectTimers();
        scheduleHeartbeat();
        if (isSynced) requestSync();
        emit();
      };
      socket.onclose = function () {
        stopHeartbeat();
        resetProbeState();
        measurements = [];
        offsetEstimate = 0;
        isSynced = false;
        if (joined) scheduleReconnect();
        emit();
      };
      socket.onerror = function () { /* onclose follows */ };
      socket.onmessage = onMessage;
    }

    function teardownSocket() {
      if (!ws) return;
      ws.onclose = ws.onerror = ws.onmessage = ws.onopen = null;
      try { ws.close(); } catch (e) { /* already closed */ }
      ws = null;
      stopHeartbeat();
      resetProbeState();
      measurements = [];
      offsetEstimate = 0;
      isSynced = false;
    }

    function clearReconnectTimers() {
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      if (connectWatchdog) { clearTimeout(connectWatchdog); connectWatchdog = null; }
    }

    function scheduleReconnect() {
      if (reconnectTimer) return;
      reconnectAttempt++;
      if (reconnectAttempt > MAX_RECONNECT_ATTEMPTS) {
        // Give up but stay joined; the next visibility/online event retries.
        lastError = 'connection';
        emit();
        return;
      }
      var delay = Math.min(RECONNECT_BASE_MS * Math.pow(1.5, reconnectAttempt - 1), RECONNECT_MAX_MS);
      delay += Math.random() * 0.15 * delay;
      reconnectTimer = setTimeout(function () {
        reconnectTimer = null;
        connect();
        // Safari can silently drop a connect attempt: retry via watchdog.
        connectWatchdog = setTimeout(function () {
          if (ws && ws.readyState !== WebSocket.OPEN) {
            teardownSocket();
            scheduleReconnect();
          }
        }, CONNECTION_TIMEOUT_MS);
      }, delay);
      emit();
    }

    function reconnectNow() {
      if (!joined) return;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
      reconnectAttempt = 0;
      lastError = null;
      clearReconnectTimers();
      connect();
    }

    // ── NTP heartbeat (coded probe pairs) ───────────────────────────
    function sendProbePair() {
      var socket = ws;
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      var probeGroupId = probeGroupCounter++;
      var compensation = outputLatencyMs() || undefined;
      var probe = function (index) {
        socket.send(JSON.stringify({
          type: 'NTP_REQUEST',
          t0: epochNow(),
          clientRTT: rttEstimate || undefined,
          clientCompensationMs: compensation,
          clientNudgeMs: 0,
          probeGroupId: probeGroupId,
          probeGroupIndex: index
        }));
      };
      probe(0);
      setTimeout(function () {
        if (socket.readyState === WebSocket.OPEN) probe(1);
      }, NTP.PROBE_GAP_MS);
    }

    function scheduleHeartbeat() {
      stopHeartbeat();
      var tick = function () {
        // An unanswered request past the timeout means the socket is dead
        // even if the browser has not noticed: close it to trigger reconnect.
        if (lastNtpRequestAt && Date.now() - lastNtpRequestAt > NTP.RESPONSE_TIMEOUT_MS) {
          if (ws) ws.close();
          return;
        }
        lastNtpRequestAt = Date.now();
        sendProbePair();
        var interval = measurements.length < NTP.MAX_MEASUREMENTS
          ? NTP.INITIAL_INTERVAL_MS : NTP.STEADY_STATE_INTERVAL_MS;
        heartbeatTimer = setTimeout(tick, interval);
      };
      heartbeatTimer = setTimeout(tick, NTP.INITIAL_INTERVAL_MS);
    }

    function stopHeartbeat() {
      if (heartbeatTimer) { clearTimeout(heartbeatTimer); heartbeatTimer = null; }
      lastNtpRequestAt = null;
    }

    function handleNtpResponse(msg) {
      var t3 = epochNow();
      var m = {
        t0: msg.t0,
        t1: msg.t1,
        roundTripDelay: t3 - msg.t0 - (msg.t2 - msg.t1),
        clockOffset: (msg.t1 - msg.t0 + (msg.t2 - t3)) / 2
      };
      lastNtpRequestAt = null;

      // Pair validation: buffer the first probe, compare gaps on the second.
      if (msg.probeGroupIndex === 0) {
        pendingFirstProbe = m;
        pendingFirstProbeGroupId = msg.probeGroupId;
        return;
      }
      var first = pendingFirstProbe;
      if (!first || pendingFirstProbeGroupId !== msg.probeGroupId) return;
      pendingFirstProbe = null;
      pendingFirstProbeGroupId = null;

      // Server inter-arrival gap must match the client inter-departure gap,
      // otherwise queuing corrupted the measurement.
      var gapDrift = Math.abs((m.t1 - first.t1) - (m.t0 - first.t0));
      if (gapDrift > NTP.PROBE_GAP_TOLERANCE_MS) return;

      addMeasurement(first.roundTripDelay <= m.roundTripDelay ? first : m);
    }

    function addMeasurement(m) {
      measurements.push(m);
      if (measurements.length > NTP.MAX_MEASUREMENTS) measurements.shift();

      // Min-RTT selection: the fastest round trip has the least queuing error.
      var minRtt = Infinity;
      var bestOffset = 0;
      measurements.forEach(function (x) {
        if (x.roundTripDelay < minRtt) {
          minRtt = x.roundTripDelay;
          bestOffset = x.clockOffset;
        }
      });
      offsetEstimate = bestOffset;
      rttEstimate = minRtt === Infinity ? 0 : minRtt;

      if (!isSynced && measurements.length >= NTP.MAX_MEASUREMENTS) {
        isSynced = true;
        lastError = null;
        loadAllSources();
        if (joined) requestSync();
        emit();
      }
    }

    // ── Message dispatch ────────────────────────────────────────────
    function onMessage(ev) {
      var msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        return;
      }
      if (!msg || typeof msg !== 'object') return;

      switch (msg.type) {
        case 'NTP_RESPONSE':
          handleNtpResponse(msg);
          break;
        case 'LIVENESS_PING':
          send({ type: 'LIVENESS_PONG' });
          sendProbePair();
          break;
        case 'ROOM_EVENT':
          if (msg.event) onRoomEvent(msg.event);
          break;
        case 'SCHEDULED_ACTION':
          onScheduledAction(msg);
          break;
        default:
          break;
      }
    }

    function onRoomEvent(event) {
      if (event.type === 'SET_AUDIO_SOURCES' && Array.isArray(event.sources)) {
        var live = new Set();
        event.sources.forEach(function (s) {
          if (!s || typeof s.url !== 'string') return;
          live.add(s.url);
          if (!sources.has(s.url)) sources.set(s.url, { status: 'idle', buffer: null });
        });
        // The plugin evicts played tracks: drop their decoded buffers too,
        // otherwise a long show keeps every song in memory.
        Array.from(sources.keys()).forEach(function (url) {
          if (!live.has(url) && url !== currentUrl) sources.delete(url);
        });
        if (joined) loadAllSources();
        emit();
      } else if (event.type === 'LOAD_AUDIO_SOURCE' && event.audioSourceToPlay) {
        var url = event.audioSourceToPlay.url;
        if (typeof url !== 'string') return;
        if (!sources.has(url)) sources.set(url, { status: 'idle', buffer: null });
        loadSource(url);
      }
    }

    function onScheduledAction(msg) {
      var action = msg.scheduledAction;
      if (!action) return;
      if (action.type === 'PLAY') {
        schedulePlay(action.audioSource, Number(action.trackTimeSeconds) || 0, msg.serverTimeToExecute);
      } else if (action.type === 'PAUSE') {
        schedulePause(msg.serverTimeToExecute);
      } else if (action.type === 'GLOBAL_VOLUME_CONFIG' && masterGain && ctx) {
        var volume = Math.max(0, Math.min(1, Number(action.volume)));
        if (!Number.isNaN(volume)) masterGain.gain.value = volume;
      }
    }

    // ── Audio source loading ────────────────────────────────────────
    function loadAllSources() {
      sources.forEach(function (s, url) {
        if (s.status === 'idle' || s.status === 'error') loadSource(url);
      });
    }

    function loadSource(url) {
      var s = sources.get(url);
      if (!s || !joined) return;
      if (s.status === 'loaded') {
        send({ type: 'AUDIO_SOURCE_LOADED', source: { url: url } });
        return;
      }
      if (s.status === 'loading') return;
      s.status = 'loading';
      emit();

      fetch(mediaUrl(url))
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.arrayBuffer();
        })
        .then(function (data) {
          // Callback form: Safari < 14.1 has no promise-based decodeAudioData.
          return new Promise(function (resolve, reject) {
            var p = getContext().decodeAudioData(data, resolve, reject);
            if (p && typeof p.then === 'function') p.then(resolve, reject);
          });
        })
        .then(function (buffer) {
          var cur = sources.get(url);
          if (cur) {
            cur.status = 'loaded';
            cur.buffer = buffer;
          }
          send({ type: 'AUDIO_SOURCE_LOADED', source: { url: url } });
          emit();
        })
        .catch(function (e) {
          var cur = sources.get(url);
          if (cur) cur.status = 'error';
          console.error('FalconBeat: failed to load ' + url, e);
          emit();
        });
    }

    // ── Scheduled playback ──────────────────────────────────────────
    function rawWaitMs(targetServerTime) {
      return Math.max(0, targetServerTime - (epochNow() + offsetEstimate));
    }

    /** Seconds until a server timestamp fires, minus our output latency. */
    function waitSeconds(targetServerTime) {
      return Math.max(0, rawWaitMs(targetServerTime) - outputLatencyMs()) / 1000;
    }

    function schedulePlay(url, trackTimeSeconds, targetServerTime) {
      if (!joined || typeof url !== 'string') return; // SYNC on join covers us

      var waitSec = waitSeconds(targetServerTime);
      if (waitSec < 0.05) {
        var raw = rawWaitMs(targetServerTime);
        if (raw < 50) {
          // Genuinely late: start a bit later at the recomputed position
          // instead of starting behind everyone else.
          var retryDelayMs = Math.min(50 - raw + 200, 2000);
          var elapsedMs = epochNow() + offsetEstimate - targetServerTime;
          startPlayback(url, trackTimeSeconds + (elapsedMs + retryDelayMs) / 1000, retryDelayMs / 1000);
          return;
        }
        waitSec = 0;
      }

      var source = sources.get(url);
      if (!source || source.status !== 'loaded') {
        // Buffer not ready: keep loading and ask the room again shortly.
        if (!source) sources.set(url, { status: 'idle', buffer: null });
        loadSource(url);
        setTimeout(requestSync, 1000);
        return;
      }
      startPlayback(url, trackTimeSeconds, waitSec);
    }

    function startPlayback(url, offsetSec, delaySec) {
      var source = sources.get(url);
      if (!source || !source.buffer) {
        // Late path without a decoded buffer: load and resync.
        if (!source) sources.set(url, { status: 'idle', buffer: null });
        loadSource(url);
        setTimeout(requestSync, 1000);
        return;
      }
      var context = getContext();
      if (context.state !== 'running') return;
      if (offsetSec < 0) offsetSec = 0;
      if (offsetSec >= source.buffer.duration) return;

      var startTime = context.currentTime + delaySec;

      // The outgoing node stops exactly when the new one starts, so a
      // pre-scheduled next song leaves no gap behind the current one.
      var prev = currentSource;
      if (prev) {
        try {
          prev.onended = null;
          prev.stop(startTime);
        } catch (e) { /* already stopped */ }
      }

      var node = context.createBufferSource();
      node.buffer = source.buffer;
      node.connect(masterGain);
      node.onended = function () {
        if (currentSource !== node || !isPlaying) return;
        var expectedEnd = playbackStartCtxTime + (trackDuration - playbackOffset);
        if (Math.abs(context.currentTime - expectedEnd) < 0.5) {
          isPlaying = false;
          currentSource = null;
          emit();
        }
      };
      node.start(startTime, offsetSec);

      currentSource = node;
      isPlaying = true;
      currentUrl = url;
      playbackStartCtxTime = startTime;
      playbackOffset = offsetSec;
      trackDuration = source.buffer.duration;
      emit();
    }

    function schedulePause(targetServerTime) {
      var waitSec = waitSeconds(targetServerTime);
      var node = currentSource;
      if (node && ctx) {
        try { node.stop(ctx.currentTime + waitSec); } catch (e) { /* already stopped */ }
      }
      setTimeout(function () {
        // Only if no newer track took over in the meantime.
        if (currentSource === node) {
          isPlaying = false;
          currentSource = null;
          emit();
        }
      }, waitSec * 1000);
    }

    function stopPlaybackLocal() {
      if (currentSource) {
        try {
          currentSource.onended = null;
          currentSource.stop();
        } catch (e) { /* already stopped */ }
        currentSource = null;
      }
      isPlaying = false;
    }

    // ── Public API ──────────────────────────────────────────────────
    /** Must be called from inside a user gesture (browser autoplay policy). */
    function join() {
      if (joined) return;
      if (!isSupported()) {
        lastError = 'unsupported';
        emit();
        return;
      }
      joined = true;
      lastError = null;
      reconnectAttempt = 0;
      var context = getContext();
      if (isContextPaused(context.state)) {
        context.resume().catch(function (e) { console.warn('AudioContext resume failed', e); });
      }
      startSilentAudioBypass();
      requestWakeLock();
      connect();
      requestSync();
      loadAllSources();
      emit();
    }

    function leave() {
      if (!joined) return;
      joined = false;
      stopPlaybackLocal();
      clearReconnectTimers();
      teardownSocket();
      releaseWakeLock();
      if (silentAudio) {
        silentAudio.pause();
        silentAudio = null;
      }
      // Free decoded audio (several MB per song) and let the device sleep.
      sources.clear();
      currentUrl = null;
      if (ctx && ctx.state === 'running') ctx.suspend().catch(function () {});
      emit();
    }

    function toggle() {
      if (joined) leave(); else join();
    }

    // Wake events fire even when timers are throttled in the background.
    global.addEventListener('online', reconnectNow);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'visible' || !joined) return;
      if (ctx && isContextPaused(ctx.state)) ctx.resume().catch(function () {});
      reconnectNow();
      if (ws && ws.readyState === WebSocket.OPEN) scheduleHeartbeat();
    });
    global.addEventListener('pageshow', function (e) {
      if (e.persisted) reconnectNow();
    });

    return {
      join: join,
      leave: leave,
      toggle: toggle,
      getState: snapshot,
      subscribe: function (cb) {
        listeners.add(cb);
        return function () { listeners.delete(cb); };
      }
    };
  }

  global.FalconBeatAudio = { create: create, isSupported: isSupported };
})(window);
