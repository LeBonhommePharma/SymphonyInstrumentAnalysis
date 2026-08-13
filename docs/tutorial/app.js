const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const MAX_INSTRUMENTS = 6;
const WINDOW_SEC = 20;
const HEADER_W = 96;
const LANE_CSS_PX = 70;
const RULER_CSS_PX = 28;
const MATCH_RATIO = 1 / 12;
const DROP_AFTER_MS = 1400;
const LANE_COLORS = ["#f97316", "#2dd4bf", "#c4b5fd", "#60a5fa", "#f472b6", "#fbbf24"];
const TOUR_SECONDS = [10, 12, 14, 12, 12];

const tracksCanvas = document.getElementById("tracks");
const specCanvas = document.getElementById("spec");
const tracksCtx = tracksCanvas.getContext("2d");
const specCtx = specCanvas.getContext("2d");
const noteEl = document.getElementById("note");
const hzEl = document.getElementById("hz");
const quietEl = document.getElementById("quiet");
const peaksEl = document.getElementById("peaks");
const hardEl = document.getElementById("hard");
const pianoEl = document.getElementById("piano");
const tourStepEl = document.getElementById("tourStep");
const tourTitleEl = document.getElementById("tourTitle");
const tourBodyEl = document.getElementById("tourBody");
const statusEl = document.getElementById("status");
const tracksHeadingEl = document.getElementById("tracksHeading");
const gate = document.getElementById("gate");
const shareVideo = document.getElementById("shareVideo");

let audioCtx = null;
let analyser = null;
let sourceNode = null;
let stream = null;
let raf = 0;
let freq = new Uint8Array(2048);
let time = new Uint8Array(2048);
let tourIndex = 0;
let tourStartedAt = 0;
let heardSound = false;
let colCount = 480;
let writeCol = 0;
let colStart = 0;
let lastElapsed = 0;
let nextInstrumentId = 1;
let instruments = [];
let demoMode = false;
let lastStatusKey = "footerHint";
let lastLaneCount = -1;

function t(key, vars) {
  if (window.I18N && typeof I18N.t === "function") return I18N.t(key, vars);
  return key;
}

function hzToNote(f) {
  const midi = Math.round(69 + 12 * Math.log2(f / 440));
  return NOTE_NAMES[((midi % 12) + 12) % 12] + String(Math.floor(midi / 12) - 1);
}

function familyForHz(f) {
  if (f <= 0) return "noise";
  if (f < 250) return "bass";
  if (f < 500) return "body";
  if (f < 2000) return "tune";
  return "air";
}

function familyLabel(family) {
  switch (family) {
    case "bass":
      return t("familyBass");
    case "body":
      return t("familyBody");
    case "tune":
      return t("familyTune");
    case "air":
      return t("familyAir");
    case "noise":
      return t("familyNoise");
    default:
      return t("laneEmpty");
  }
}

function instrumentCountLabel(n) {
  if (n <= 0) return t("nInstrument0");
  if (n === 1) return t("nInstrument1");
  return t("nInstruments", { n: n });
}

function updateTracksHeading() {
  tracksHeadingEl.textContent = t("tracksHeading", { count: instrumentCountLabel(instruments.length) });
}

function setStatusKey(key) {
  lastStatusKey = key;
  statusEl.textContent = t(key);
}

function makeInstrument(hz, family, color) {
  const id = nextInstrumentId;
  nextInstrumentId += 1;
  return {
    id: id,
    hz: hz,
    family: family,
    color: color || LANE_COLORS[(id - 1) % LANE_COLORS.length],
    history: new Float32Array(colCount),
    lastSeen: performance.now(),
    accum: 0,
    pendingAmp: 0,
  };
}

function displayLanes() {
  if (!instruments.length) return [];
  return instruments.slice().sort(function (a, b) {
    return b.hz - a.hz;
  });
}

function syncTracksHeight() {
  const n = Math.max(1, instruments.length);
  tracksCanvas.style.height = RULER_CSS_PX + n * LANE_CSS_PX + "px";
}

function ensureColCount() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const header = HEADER_W * dpr;
  const next = Math.max(240, Math.floor(tracksCanvas.width - header));
  if (next === colCount) {
    instruments.forEach(function (inst) {
      if (inst.history.length !== colCount) inst.history = new Float32Array(colCount);
    });
    return;
  }
  colCount = next;
  instruments.forEach(function (inst) {
    inst.history = new Float32Array(colCount);
  });
  writeCol = 0;
  colStart = performance.now();
}

function layoutTracksCanvas() {
  syncTracksHeight();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const rect = tracksCanvas.getBoundingClientRect();
  tracksCanvas.width = Math.max(320, Math.floor(rect.width * dpr));
  tracksCanvas.height = Math.max(120, Math.floor((rect.height || 160) * dpr));
  ensureColCount();
  lastLaneCount = instruments.length;
}

function resizeCanvases() {
  layoutTracksCanvas();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const specRect = specCanvas.getBoundingClientRect();
  specCanvas.width = Math.max(320, Math.floor(specRect.width * dpr));
  specCanvas.height = Math.max(120, Math.floor((specRect.height || 150) * dpr));
  updateTracksHeading();
  drawTracks(lastElapsed);
}

function resetHistory() {
  instruments = [];
  nextInstrumentId = 1;
  writeCol = 0;
  colStart = performance.now();
  layoutTracksCanvas();
  updateTracksHeading();
}

function buildPiano() {
  pianoEl.innerHTML = "";
  const start = 48;
  const end = 72;
  const whites = [];
  for (let midi = start; midi <= end; midi += 1) {
    if (!NOTE_NAMES[midi % 12].includes("#")) whites.push(midi);
  }
  whites.forEach(function (midi) {
    const key = document.createElement("div");
    key.className = "white-key";
    key.dataset.midi = String(midi);
    pianoEl.appendChild(key);
  });
  const n = whites.length;
  whites.forEach(function (midi, i) {
    const sharp = midi + 1;
    if (sharp > end || !NOTE_NAMES[sharp % 12].includes("#")) return;
    const key = document.createElement("div");
    key.className = "black-key";
    key.dataset.midi = String(sharp);
    key.style.left = ((i + 0.7) / n) * 100 + "%";
    key.style.width = (0.58 / n) * 100 + "%";
    pianoEl.appendChild(key);
  });
}

function lightPiano(midi) {
  pianoEl.querySelectorAll("[data-midi]").forEach(function (el) {
    el.classList.toggle("on", Number(el.dataset.midi) === midi);
  });
}

function analyzeFrame(sampleRate) {
  const n = freq.length;
  const nyquist = sampleRate / 2;
  let bass = 0;
  let tune = 0;
  let sparkle = 0;
  const peaks = [];
  for (let i = 2; i < n - 2; i += 1) {
    const f = i * (nyquist / n);
    if (f < 40 || f > 5000) continue;
    const mag = freq[i];
    if (mag > freq[i - 1] && mag > freq[i + 1] && mag >= freq[i - 2] && mag >= freq[i + 2] && mag > 18) {
      peaks.push({ f: f, mag: mag });
    }
    if (f < 250) bass += mag;
    else if (f < 2000) tune += mag;
    else sparkle += mag;
  }
  peaks.sort(function (a, b) {
    return b.mag - a.mag;
  });
  const top = peaks.filter(function (p, idx) {
    if (idx === 0) return true;
    return !peaks.slice(0, idx).some(function (q) {
      return Math.abs(Math.log2(p.f / q.f)) < MATCH_RATIO;
    });
  }).slice(0, MAX_INSTRUMENTS);
  const tot = bass + tune + sparkle || 1;
  return { bass: bass, tune: tune, sparkle: sparkle, tot: tot, top: top };
}

function rmsOfTime() {
  let s = 0;
  for (let i = 0; i < time.length; i += 1) {
    const v = time[i] / 128 - 1;
    s += v * v;
  }
  return Math.sqrt(s / time.length);
}

function liveKind(rms, info) {
  if (rms < 0.012) return "quiet";
  if (!info.top[0] || info.top[0].mag < 24) return "noise";
  return "pitch";
}

function matchPeak(peak, usedIds) {
  let best = null;
  let bestDist = MATCH_RATIO;
  instruments.forEach(function (inst) {
    if (usedIds.has(inst.id) || inst.family === "noise" || inst.hz <= 0) return;
    const dist = Math.abs(Math.log2(peak.f / inst.hz));
    if (dist < bestDist) {
      best = inst;
      bestDist = dist;
    }
  });
  return best;
}

function dropStale(now) {
  instruments = instruments.filter(function (inst) {
    return now - inst.lastSeen < DROP_AFTER_MS;
  });
}

function syncInstruments(info, rms, now) {
  const kind = liveKind(rms, info);
  if (kind === "quiet") {
    instruments.forEach(function (inst) {
      inst.pendingAmp = 0;
    });
    dropStale(now);
    return kind;
  }
  if (kind === "noise") {
    let noise = instruments.find(function (inst) {
      return inst.family === "noise";
    });
    if (!noise) {
      instruments = [makeInstrument(0, "noise")];
      noise = instruments[0];
    } else {
      instruments = [noise];
    }
    noise.pendingAmp = Math.min(1, rms * 6);
    noise.lastSeen = now;
    return kind;
  }
  instruments = instruments.filter(function (inst) {
    return inst.family !== "noise";
  });
  const used = new Set();
  info.top.forEach(function (peak) {
    const match = matchPeak(peak, used);
    if (match) {
      used.add(match.id);
      match.hz = peak.f * 0.35 + match.hz * 0.65;
      match.family = familyForHz(match.hz);
      match.pendingAmp = Math.min(1, (peak.mag / 255) * 1.85);
      match.lastSeen = now;
      return;
    }
    if (instruments.length >= MAX_INSTRUMENTS) return;
    const inst = makeInstrument(peak.f, familyForHz(peak.f));
    inst.pendingAmp = Math.min(1, (peak.mag / 255) * 1.85);
    inst.lastSeen = now;
    used.add(inst.id);
    instruments.push(inst);
  });
  instruments.forEach(function (inst) {
    if (!used.has(inst.id)) inst.pendingAmp = 0;
  });
  dropStale(now);
  return kind;
}

function pushColumn() {
  instruments.forEach(function (inst) {
    inst.accum = Math.max(inst.accum, inst.pendingAmp);
  });
  const elapsed = (performance.now() - colStart) / 1000;
  const colDur = WINDOW_SEC / colCount;
  if (elapsed < colDur) return;
  instruments.forEach(function (inst) {
    if (inst.history.length !== colCount) inst.history = new Float32Array(colCount);
    inst.history[writeCol] = Math.min(1, inst.accum);
    inst.accum = 0;
  });
  writeCol = (writeCol + 1) % colCount;
  instruments.forEach(function (inst) {
    inst.history[writeCol] = 0;
  });
  colStart = performance.now();
}

function maybeRelayout() {
  if (instruments.length === lastLaneCount) return;
  layoutTracksCanvas();
  updateTracksHeading();
}

function drawTracks(elapsedSec) {
  const { width, height } = tracksCanvas;
  const ctx = tracksCtx;
  ctx.fillStyle = "#141820";
  ctx.fillRect(0, 0, width, height);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const header = HEADER_W * dpr;
  const rulerH = 26 * dpr;
  const lanes = displayLanes();
  const laneCount = Math.max(1, lanes.length);
  const laneH = (height - rulerH) / laneCount;
  const laneW = width - header;

  ctx.fillStyle = "#0f131a";
  ctx.fillRect(0, 0, width, rulerH);
  ctx.textBaseline = "middle";
  const secStep = WINDOW_SEC <= 20 ? 2 : 5;
  for (let s = 0; s <= WINDOW_SEC; s += secStep) {
    const x = header + (s / WINDOW_SEC) * laneW;
    ctx.fillStyle = "#2a3140";
    ctx.fillRect(x, rulerH, Math.max(1, dpr), height - rulerH);
    ctx.fillStyle = "#9ca3af";
    ctx.font = 11 * dpr + "px ui-monospace, SFMono-Regular, Menlo, monospace";
    const label = s === WINDOW_SEC ? t("rulerNow") : "-" + (WINDOW_SEC - s) + "s";
    ctx.fillText(label, x - (s === WINDOW_SEC ? 28 * dpr : 10 * dpr), rulerH / 2);
  }

  if (!lanes.length) {
    const y0 = rulerH;
    const mid = y0 + laneH / 2;
    ctx.fillStyle = "#171c24";
    ctx.fillRect(0, y0, width, laneH);
    ctx.fillStyle = "#11151c";
    ctx.fillRect(0, y0, header, laneH);
    ctx.fillStyle = "#9ca3af";
    ctx.font = "600 " + 11 * dpr + "px ui-sans-serif, system-ui, sans-serif";
    ctx.fillText(t("laneEmpty"), 10 * dpr, mid);
  } else {
    lanes.forEach(function (track, lane) {
      const y0 = rulerH + lane * laneH;
      const mid = y0 + laneH / 2;
      ctx.fillStyle = lane % 2 === 0 ? "#171c24" : "#141820";
      ctx.fillRect(0, y0, width, laneH);
      ctx.fillStyle = "#11151c";
      ctx.fillRect(0, y0, header, laneH);
      ctx.fillStyle = track.color;
      ctx.font = "600 " + 11 * dpr + "px ui-sans-serif, system-ui, sans-serif";
      const name = track.family === "noise" || track.hz <= 0 ? familyLabel(track.family) : familyLabel(track.family) + " " + hzToNote(track.hz);
      ctx.fillText(name, 10 * dpr, mid);
      ctx.strokeStyle = "#2a3140";
      ctx.beginPath();
      ctx.moveTo(header, y0);
      ctx.lineTo(width, y0);
      ctx.stroke();
      ctx.beginPath();
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.moveTo(header, mid);
      ctx.lineTo(width, mid);
      ctx.stroke();

      const ampScale = laneH * 0.42;
      ctx.fillStyle = track.color;
      for (let x = 0; x < laneW; x += 1) {
        const age = laneW - 1 - x;
        const idx = (writeCol - 1 - age + colCount * 4) % colCount;
        const amp = track.history[idx] || 0;
        if (amp < 0.01) continue;
        const h = Math.max(dpr, amp * ampScale);
        ctx.fillRect(header + x, mid - h, 1, h * 2);
      }
    });
  }

  const playX = width - 3 * dpr;
  ctx.fillStyle = "#f9fafb";
  ctx.fillRect(playX, rulerH, Math.max(2, dpr), height - rulerH);
  ctx.fillStyle = "#6b7280";
  ctx.font = 10 * dpr + "px ui-monospace, Menlo, monospace";
  ctx.fillText(t("liveElapsed", { n: elapsedSec.toFixed(0) }), 10 * dpr, rulerH / 2);
}

function drawSpec(top, sampleRate) {
  const { width, height } = specCanvas;
  specCtx.fillStyle = "#111827";
  specCtx.fillRect(0, 0, width, height);
  const n = freq.length;
  const nyquist = sampleRate / 2;
  const maxBin = Math.min(n, Math.floor((5000 / nyquist) * n));
  const barW = width / maxBin;
  for (let i = 0; i < maxBin; i += 1) {
    const f = (i / n) * nyquist;
    const h = (freq[i] / 255) * height;
    if (f < 250) specCtx.fillStyle = "#f97316";
    else if (f < 2000) specCtx.fillStyle = "#2dd4bf";
    else specCtx.fillStyle = "#c4b5fd";
    specCtx.fillRect(i * barW, height - h, Math.max(barW, 1), h);
  }
  if (top[0]) {
    specCtx.fillStyle = "#ffffff";
    specCtx.font = Math.max(12, Math.floor(height / 9)) + "px ui-sans-serif";
    specCtx.fillText(hzToNote(top[0].f) + "  " + top[0].f.toFixed(1) + " Hz", 12, 22);
  }
}

function tick() {
  if (!analyser || !audioCtx) return;
  analyser.getByteFrequencyData(freq);
  analyser.getByteTimeDomainData(time);
  const rms = rmsOfTime();
  const info = analyzeFrame(audioCtx.sampleRate);
  const now = performance.now();
  const kind = syncInstruments(info, rms, now);
  pushColumn();
  maybeRelayout();
  lastElapsed = (now - tourStartedAt) / 1000;
  drawTracks(lastElapsed);
  drawSpec(info.top, audioCtx.sampleRate);

  if (kind !== "quiet") heardSound = true;
  if (kind === "pitch") {
    quietEl.textContent = t("quietPitch");
    const f = info.top[0].f;
    noteEl.textContent = hzToNote(f);
    hzEl.textContent = f.toFixed(1) + " Hz";
    lightPiano(Math.round(69 + 12 * Math.log2(f / 440)));
    peaksEl.textContent = info.top
      .map(function (p) {
        return hzToNote(p.f).padEnd(4, " ") + "  " + p.f.toFixed(1) + " Hz";
      })
      .join("\n");
    const harmonicHits = info.top.filter(function (p) {
      return info.top.some(function (q) {
        return q !== p && Math.abs(p.f / q.f - 2) < 0.08;
      });
    }).length;
    if (info.top.length >= 4) {
      hardEl.textContent = t("hardMany", { n: info.top.length });
    } else if (harmonicHits) {
      hardEl.textContent = t("hardOvertones");
    } else {
      hardEl.textContent = t("hardClear");
    }
  } else if (kind === "noise") {
    quietEl.textContent = t("quietNoise");
    noteEl.textContent = "—";
    hzEl.textContent = t("hzNoPitch");
    lightPiano(-1);
    peaksEl.textContent = t("peaksNoise");
    hardEl.textContent = t("hardNoise");
  } else {
    quietEl.textContent = heardSound ? t("quietAfter") : t("quietIdle");
    noteEl.textContent = "—";
    hzEl.textContent = t("hzWaitingDevice");
    lightPiano(-1);
  }

  const local = lastElapsed - TOUR_SECONDS.slice(0, tourIndex).reduce(function (a, x) {
    return a + x;
  }, 0);
  if (local >= TOUR_SECONDS[tourIndex] && tourIndex < TOUR_SECONDS.length - 1) {
    showTour(tourIndex + 1);
  }
  raf = requestAnimationFrame(tick);
}

function showTour(i) {
  tourIndex = i;
  tourStepEl.textContent = String(i + 1);
  tourTitleEl.textContent = t("tour" + i + "Title");
  tourBodyEl.textContent = t("tour" + i + "Body");
  const colors = ["#f97316", "#0d9488", "#7c3aed", "#2563eb", "#ea580c"];
  tourStepEl.style.background = colors[i % colors.length];
}

function canShareTabAudio() {
  const isiOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return Boolean(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) && !isiOS;
}

function listenErrorKey(err) {
  const name = err && err.name;
  const text = String((err && err.message) || err || "");
  if (name === "NotAllowedError" || name === "PermissionDeniedError") return "errMicDenied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "errNoMic";
  if (name === "SecurityError" || /secure context|https/i.test(text)) return "errSecure";
  if (name === "NotSupportedError") return "errNoTabShare";
  return null;
}

function showListenError(err) {
  const key = listenErrorKey(err);
  if (key) {
    setStatusKey(key);
    return;
  }
  lastStatusKey = null;
  statusEl.textContent = String((err && err.message) || err || "");
}

function makeAudioContext() {
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) {
    throw new Error(t("errNoAudioCtx"));
  }
  return new Ctor();
}

async function startFromStream(mediaStream, statusKey) {
  stopListen();
  demoMode = false;
  stream = mediaStream;
  audioCtx = makeAudioContext();
  if (audioCtx.state === "suspended") await audioCtx.resume();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 4096;
  analyser.smoothingTimeConstant = 0.72;
  freq = new Uint8Array(analyser.frequencyBinCount);
  time = new Uint8Array(analyser.fftSize);
  sourceNode = audioCtx.createMediaStreamSource(mediaStream);
  sourceNode.connect(analyser);
  setStatusKey(statusKey);
  gate.classList.add("hidden");
  tourStartedAt = performance.now();
  heardSound = false;
  showTour(0);
  resetHistory();
  cancelAnimationFrame(raf);
  tick();
}

function stopListen() {
  cancelAnimationFrame(raf);
  if (sourceNode) sourceNode.disconnect();
  sourceNode = null;
  if (audioCtx) audioCtx.close();
  audioCtx = null;
  analyser = null;
  if (stream) {
    stream.getTracks().forEach(function (track) {
      track.stop();
    });
    stream = null;
  }
}

async function listenMic() {
  const mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    },
    video: false,
  });
  await startFromStream(mediaStream, "statusMicOn");
}

async function listenDevice() {
  if (!canShareTabAudio()) {
    const err = new Error(t("errNoTabShare"));
    err.name = "NotSupportedError";
    throw err;
  }
  const mediaStream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 1, width: 16, height: 16 },
    audio: true,
    preferCurrentTab: false,
  });
  mediaStream.getVideoTracks().forEach(function (track) {
    track.enabled = false;
  });
  if (!mediaStream.getAudioTracks().length) {
    mediaStream.getTracks().forEach(function (track) {
      track.stop();
    });
    throw new Error(t("errNoAudioTrack"));
  }
  shareVideo.srcObject = mediaStream;
  await startFromStream(mediaStream, "statusTabOn");
}

function fillExampleTracks() {
  demoMode = true;
  gate.classList.add("hidden");
  quietEl.textContent = t("demoQuiet");
  setStatusKey("demoStatus");
  showTour(1);
  const demo = [
    { hz: 82.4, family: "bass", wave: function (x) { return 0.2 + 0.7 * Math.abs(Math.sin(x * Math.PI * 2.1)); } },
    { hz: 110, family: "bass", wave: function (x) { return 0.15 + 0.55 * Math.abs(Math.sin(x * Math.PI * 2.4 + 0.4)); } },
    { hz: 196, family: "body", wave: function (x) { return 0.12 + 0.5 * Math.abs(Math.sin(x * Math.PI * 3.1)); } },
    { hz: 440, family: "tune", wave: function (x) {
      const beat = Math.max(0.25, Math.sin(x * Math.PI * 8));
      const hum = 0.35 + 0.45 * Math.abs(Math.sin(x * Math.PI * 3.2));
      return 0.1 + 0.85 * hum * beat;
    } },
    { hz: 659.3, family: "tune", wave: function (x) { return 0.08 + 0.45 * Math.abs(Math.sin(x * Math.PI * 5.5)); } },
    { hz: 1046.5, family: "air", wave: function (x) { return 0.06 + 0.35 * Math.abs(Math.sin(x * Math.PI * 11)); } },
  ];
  instruments = demo.map(function (row, i) {
    return makeInstrument(row.hz, row.family, LANE_COLORS[i]);
  });
  layoutTracksCanvas();
  demo.forEach(function (row, lane) {
    for (let i = 0; i < colCount; i += 1) {
      instruments[lane].history[i] = Math.min(1, row.wave(i / colCount));
    }
  });
  freq.fill(10);
  freq[7] = 140;
  freq[9] = 120;
  freq[17] = 90;
  freq[38] = 210;
  freq[56] = 150;
  freq[89] = 80;
  writeCol = 0;
  lastElapsed = 12;
  noteEl.textContent = "A4";
  hzEl.textContent = "440.0 Hz";
  lightPiano(69);
  peaksEl.textContent = "E2    82.4 Hz\nA2   110.0 Hz\nG3   196.0 Hz\nA4   440.0 Hz\nE5   659.3 Hz\nC6  1046.5 Hz";
  hardEl.textContent = t("demoHard");
  updateTracksHeading();
  drawTracks(12);
  drawSpec([{ f: 440, mag: 200 }], 48000);
}

function refreshI18n() {
  showTour(tourIndex);
  updateTracksHeading();
  if (lastStatusKey) statusEl.textContent = t(lastStatusKey);
  if (demoMode) {
    quietEl.textContent = t("demoQuiet");
    hardEl.textContent = t("demoHard");
  } else if (!audioCtx) {
    quietEl.textContent = t("quietIdle");
    peaksEl.textContent = t("peaksWaiting");
    hardEl.textContent = t("hardDefault");
    hzEl.textContent = t("hzWaiting");
  }
  drawTracks(lastElapsed);
}

function wire() {
  buildPiano();
  resizeCanvases();
  window.addEventListener("resize", resizeCanvases);
  window.onSymphonyLangChange = refreshI18n;
  if (!canShareTabAudio()) {
    document.querySelectorAll(".share-only").forEach(function (el) {
      el.hidden = true;
    });
  }
  document.getElementById("btnMic").addEventListener("click", function () {
    listenMic().catch(showListenError);
  });
  document.getElementById("btnShare").addEventListener("click", function () {
    listenDevice().catch(showListenError);
  });
  document.getElementById("btnStop").addEventListener("click", function () {
    stopListen();
    shareVideo.srcObject = null;
    demoMode = false;
    setStatusKey("statusStopped");
    gate.classList.remove("hidden");
  });
  document.getElementById("btnNext").addEventListener("click", function () {
    const next = Math.min(TOUR_SECONDS.length - 1, tourIndex + 1);
    showTour(next);
    tourStartedAt = performance.now() - TOUR_SECONDS.slice(0, next).reduce(function (a, x) {
      return a + x;
    }, 0) * 1000;
  });
  document.getElementById("btnMicGate").addEventListener("click", function () {
    listenMic().catch(showListenError);
  });
  document.getElementById("btnShareGate").addEventListener("click", function () {
    listenDevice().catch(showListenError);
  });
  showTour(0);
  setStatusKey("footerHint");
  quietEl.textContent = t("quietIdle");
  peaksEl.textContent = t("peaksWaiting");
  hardEl.textContent = t("hardDefault");
  hzEl.textContent = t("hzWaiting");
  updateTracksHeading();
  if (new URLSearchParams(window.location.search).has("demo")) {
    fillExampleTracks();
  }
}

wire();
