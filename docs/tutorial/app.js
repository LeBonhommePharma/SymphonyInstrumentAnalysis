const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const TOUR = [
  {
    title: "We will not play a song over yours",
    body: "Whatever this device is already making — Now Playing through the speaker, a piano, voices, noise — gets drawn. We never put a demo song under it.",
    seconds: 10,
  },
  {
    title: "Time is a waveform track, like Logic",
    body: "Each lane is a layer scrolling left. The white line on the right is now. There is no time slider. The wiggles are the clock.",
    seconds: 12,
  },
  {
    title: "No tune? We still draw the live sound",
    body: "Random noise and voices are still this device, right now. We do not invent a melody. If Now Playing is on, turn the speaker up so the mic can hear it.",
    seconds: 14,
  },
  {
    title: "A song is a sandwich. That is the useful part.",
    body: "Boom on the bottom is left-hand / bass. The middle is the tune you can hum. The top is sparkle. Practice one layer at a time.",
    seconds: 12,
  },
  {
    title: "Piano superpower",
    body: "If a clear pitch appears, 440 Hz is the A key. Find it. Play it. Match it. Live guessing stays hard when many pitches stack.",
    seconds: 12,
  },
];

const TRACK_DEFS = [
  { id: "mix", label: "Mix", color: "#fdba74" },
  { id: "boom", label: "Boom", color: "#f97316" },
  { id: "tune", label: "Tune", color: "#2dd4bf" },
  { id: "sparkle", label: "Sparkle", color: "#c4b5fd" },
];
const WINDOW_SEC = 20;
const HEADER_W = 76;

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
const gate = document.getElementById("gate");

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
let history = TRACK_DEFS.map(() => new Float32Array(colCount));
let writeCol = 0;
let colAccum = [0, 0, 0, 0];
let colStart = 0;
const shareVideo = document.getElementById("shareVideo");

function hzToNote(f) {
  const midi = Math.round(69 + 12 * Math.log2(f / 440));
  return NOTE_NAMES[((midi % 12) + 12) % 12] + String(Math.floor(midi / 12) - 1);
}

function resetHistory() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const header = HEADER_W * dpr;
  colCount = Math.max(240, Math.floor(tracksCanvas.width - header));
  history = TRACK_DEFS.map(() => new Float32Array(colCount));
  writeCol = 0;
  colAccum = [0, 0, 0, 0];
  colStart = performance.now();
}

function resizeCanvases() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  for (const canvas of [tracksCanvas, specCanvas]) {
    const rect = canvas.getBoundingClientRect();
    const fallbackH = canvas === tracksCanvas ? 320 : 150;
    canvas.width = Math.max(320, Math.floor(rect.width * dpr));
    canvas.height = Math.max(120, Math.floor((rect.height || fallbackH) * dpr));
  }
  resetHistory();
  drawTracks(0);
}

function buildPiano() {
  pianoEl.innerHTML = "";
  const start = 48;
  const end = 72;
  const whites = [];
  for (let midi = start; midi <= end; midi += 1) {
    if (!NOTE_NAMES[midi % 12].includes("#")) whites.push(midi);
  }
  whites.forEach((midi) => {
    const key = document.createElement("div");
    key.className = "white-key";
    key.dataset.midi = String(midi);
    pianoEl.appendChild(key);
  });
  const n = whites.length;
  whites.forEach((midi, i) => {
    const sharp = midi + 1;
    if (sharp > end || !NOTE_NAMES[sharp % 12].includes("#")) return;
    const key = document.createElement("div");
    key.className = "black-key";
    key.dataset.midi = String(sharp);
    key.style.left = `${((i + 0.7) / n) * 100}%`;
    key.style.width = `${(0.58 / n) * 100}%`;
    pianoEl.appendChild(key);
  });
}

function lightPiano(midi) {
  pianoEl.querySelectorAll("[data-midi]").forEach((el) => {
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
      peaks.push({ f, mag });
    }
    if (f < 250) bass += mag;
    else if (f < 2000) tune += mag;
    else sparkle += mag;
  }
  peaks.sort((a, b) => b.mag - a.mag);
  const top = peaks.filter((p, idx) => {
    if (idx === 0) return true;
    return !peaks.slice(0, idx).some((q) => Math.abs(Math.log2(p.f / q.f)) < 1 / 12);
  }).slice(0, 6);
  const tot = bass + tune + sparkle || 1;
  return { bass, tune, sparkle, tot, top };
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

function pushColumn(mix, boom, tune, sparkle) {
  const values = [mix, boom, tune, sparkle];
  for (let i = 0; i < 4; i += 1) {
    colAccum[i] = Math.max(colAccum[i], values[i]);
  }
  const elapsed = (performance.now() - colStart) / 1000;
  const colDur = WINDOW_SEC / colCount;
  if (elapsed < colDur) return;
  for (let i = 0; i < 4; i += 1) {
    history[i][writeCol] = Math.min(1, colAccum[i]);
    colAccum[i] = 0;
  }
  writeCol = (writeCol + 1) % colCount;
  history.forEach((lane) => {
    lane[writeCol] = 0;
  });
  colStart = performance.now();
}

function drawTracks(elapsedSec) {
  const { width, height } = tracksCanvas;
  const ctx = tracksCtx;
  ctx.fillStyle = "#141820";
  ctx.fillRect(0, 0, width, height);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const header = HEADER_W * dpr;
  const rulerH = 26 * dpr;
  const laneH = (height - rulerH) / TRACK_DEFS.length;
  const laneW = width - header;

  ctx.fillStyle = "#0f131a";
  ctx.fillRect(0, 0, width, rulerH);
  ctx.fillStyle = "#9ca3af";
  ctx.font = `${11 * dpr}px ui-monospace, SFMono-Regular, Menlo, monospace`;
  ctx.textBaseline = "middle";
  const secStep = WINDOW_SEC <= 20 ? 2 : 5;
  for (let s = 0; s <= WINDOW_SEC; s += secStep) {
    const x = header + (s / WINDOW_SEC) * laneW;
    ctx.fillStyle = "#2a3140";
    ctx.fillRect(x, rulerH, Math.max(1, dpr), height - rulerH);
    ctx.fillStyle = "#9ca3af";
    const label = s === WINDOW_SEC ? "now" : `-${WINDOW_SEC - s}s`;
    ctx.fillText(label, x - (s === WINDOW_SEC ? 28 * dpr : 10 * dpr), rulerH / 2);
  }

  TRACK_DEFS.forEach((track, lane) => {
    const y0 = rulerH + lane * laneH;
    const mid = y0 + laneH / 2;
    ctx.fillStyle = lane % 2 === 0 ? "#171c24" : "#141820";
    ctx.fillRect(0, y0, width, laneH);
    ctx.fillStyle = "#11151c";
    ctx.fillRect(0, y0, header, laneH);
    ctx.fillStyle = track.color;
    ctx.font = `600 ${11 * dpr}px ui-sans-serif, system-ui, sans-serif`;
    ctx.fillText(track.label, 10 * dpr, mid);
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
      const amp = history[lane][idx] || 0;
      if (amp < 0.01) continue;
      const h = Math.max(dpr, amp * ampScale);
      ctx.fillRect(header + x, mid - h, 1, h * 2);
    }
  });

  const playX = width - 3 * dpr;
  ctx.fillStyle = "#f9fafb";
  ctx.fillRect(playX, rulerH, Math.max(2, dpr), height - rulerH);
  ctx.fillStyle = "#6b7280";
  ctx.font = `${10 * dpr}px ui-monospace, Menlo, monospace`;
  ctx.fillText(`${elapsedSec.toFixed(0)}s live`, 10 * dpr, rulerH / 2);
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
    specCtx.font = `${Math.max(12, Math.floor(height / 9))}px ui-sans-serif`;
    specCtx.fillText(`${hzToNote(top[0].f)}  ${top[0].f.toFixed(1)} Hz`, 12, 22);
  }
}

function tick() {
  if (!analyser || !audioCtx) return;
  analyser.getByteFrequencyData(freq);
  analyser.getByteTimeDomainData(time);
  const rms = rmsOfTime();
  const info = analyzeFrame(audioCtx.sampleRate);
  const tot = info.tot;
  const mix = Math.min(1, rms * 6);
  const boom = Math.min(1, mix * (info.bass / tot) * 2.2);
  const tune = Math.min(1, mix * (info.tune / tot) * 2.2);
  const sparkle = Math.min(1, mix * (info.sparkle / tot) * 2.2);
  pushColumn(mix, boom, tune, sparkle);
  const elapsed = (performance.now() - tourStartedAt) / 1000;
  drawTracks(elapsed);
  drawSpec(info.top, audioCtx.sampleRate);

  const kind = liveKind(rms, info);
  if (kind !== "quiet") heardSound = true;
  if (kind === "pitch") {
    quietEl.textContent = "Hearing this device right now (live sound, including Now Playing if it is coming out of the speaker).";
    const f = info.top[0].f;
    noteEl.textContent = hzToNote(f);
    hzEl.textContent = `${f.toFixed(1)} Hz`;
    lightPiano(Math.round(69 + 12 * Math.log2(f / 440)));
    peaksEl.textContent = info.top
      .map((p) => `${hzToNote(p.f).padEnd(4, " ")}  ${p.f.toFixed(1)} Hz`)
      .join("\n");
    const harmonicHits = info.top.filter((p) =>
      info.top.some((q) => q !== p && Math.abs(p.f / q.f - 2) < 0.08)
    ).length;
    if (info.top.length >= 4) {
      hardEl.textContent = `Live is hard: ${info.top.length} strong pitches at once. The picture is still moving.`;
    } else if (harmonicHits) {
      hardEl.textContent = "Live is hard: this note is ringing extra high copies (overtones), like a piano does.";
    } else {
      hardEl.textContent = "One clear pitch is the easy case. Songs are rarely this tidy.";
    }
  } else if (kind === "noise") {
    quietEl.textContent = "No clear melody. Still drawing the live sound (voices, noise, room). We will not fake a tune.";
    noteEl.textContent = "—";
    hzEl.textContent = "no clear pitch";
    lightPiano(-1);
    peaksEl.textContent = "Energy without a hummable pitch — that is still this device, right now.";
    hardEl.textContent = "Live naming is hard when there is no tune. The tracks keep rolling anyway.";
  } else {
    quietEl.textContent = heardSound
      ? "Quiet now. If Now Playing is on, turn this device’s speaker up — we cannot tap Apple’s Now Playing bus from a web page."
      : "Nothing loud yet. Play Now Playing out loud on this device, or a piano, or a video.";
    noteEl.textContent = "—";
    hzEl.textContent = "waiting for this device";
    lightPiano(-1);
  }

  const scene = TOUR[tourIndex];
  const local = elapsed - TOUR.slice(0, tourIndex).reduce((a, x) => a + x.seconds, 0);
  if (scene && local >= scene.seconds && tourIndex < TOUR.length - 1) {
    showTour(tourIndex + 1);
  }
  raf = requestAnimationFrame(tick);
}

function showTour(i) {
  tourIndex = i;
  const scene = TOUR[i];
  tourStepEl.textContent = String(i + 1);
  tourTitleEl.textContent = scene.title;
  tourBodyEl.textContent = scene.body;
  const colors = ["#f97316", "#0d9488", "#7c3aed", "#2563eb", "#ea580c"];
  tourStepEl.style.background = colors[i % colors.length];
}

function canShareTabAudio() {
  const isiOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return Boolean(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) && !isiOS;
}

function listenError(err) {
  const name = err && err.name;
  const text = String((err && err.message) || err || "");
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Mic permission was denied. On a phone, allow Microphone for this site, then tap listen again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return "This device has no microphone the browser can use.";
  }
  if (name === "SecurityError" || /secure context|https/i.test(text)) {
    return "Browsers only allow the mic on HTTPS (or localhost). Open the public thebonhomme.com link on this phone, not a LAN address.";
  }
  if (name === "NotSupportedError") {
    return "This browser cannot share tab audio. On a phone, use “Listen with the mic” instead.";
  }
  return text;
}

function makeAudioContext() {
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) {
    throw new Error("This browser cannot listen. Try Safari or Chrome on this phone.");
  }
  return new Ctor();
}

async function startFromStream(mediaStream, label) {
  stopListen();
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
  statusEl.textContent = label;
  gate.classList.add("hidden");
  tourStartedAt = performance.now();
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
    stream.getTracks().forEach((t) => t.stop());
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
  await startFromStream(
    mediaStream,
    "Mic on this device. Now Playing / speakers / room are the input. Nothing is played back."
  );
}

async function listenDevice() {
  if (!canShareTabAudio()) {
    const err = new Error("Tab audio sharing is not available on this phone. Use the mic.");
    err.name = "NotSupportedError";
    throw err;
  }
  const mediaStream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 1, width: 16, height: 16 },
    audio: true,
    preferCurrentTab: false,
  });
  mediaStream.getVideoTracks().forEach((t) => {
    t.enabled = false;
  });
  if (!mediaStream.getAudioTracks().length) {
    mediaStream.getTracks().forEach((t) => t.stop());
    throw new Error("No audio track. Share a tab or window with sound, and turn audio sharing on.");
  }
  shareVideo.srcObject = mediaStream;
  await startFromStream(
    mediaStream,
    "Shared tab/window audio from this device. This page stays silent."
  );
}

function wire() {
  buildPiano();
  resizeCanvases();
  window.addEventListener("resize", resizeCanvases);
  if (!canShareTabAudio()) {
    document.querySelectorAll(".share-only").forEach((el) => {
      el.hidden = true;
    });
  }
  document.getElementById("btnMic").addEventListener("click", () => {
    listenMic().catch((err) => {
      statusEl.textContent = listenError(err);
    });
  });
  document.getElementById("btnShare").addEventListener("click", () => {
    listenDevice().catch((err) => {
      statusEl.textContent = listenError(err);
    });
  });
  document.getElementById("btnStop").addEventListener("click", () => {
    stopListen();
    shareVideo.srcObject = null;
    statusEl.textContent = "Stopped. Play something on the device, then listen again.";
    gate.classList.remove("hidden");
  });
  document.getElementById("btnNext").addEventListener("click", () => {
    const next = Math.min(TOUR.length - 1, tourIndex + 1);
    showTour(next);
    tourStartedAt = performance.now() - TOUR.slice(0, next).reduce((a, x) => a + x.seconds, 0) * 1000;
  });
  document.getElementById("btnMicGate").addEventListener("click", () => {
    listenMic().catch((err) => {
      statusEl.textContent = listenError(err);
    });
  });
  document.getElementById("btnShareGate").addEventListener("click", () => {
    listenDevice().catch((err) => {
      statusEl.textContent = listenError(err);
    });
  });
  showTour(0);
  if (new URLSearchParams(window.location.search).has("demo")) {
    fillExampleTracks();
  }
}

function fillExampleTracks() {
  gate.classList.add("hidden");
  quietEl.textContent = "Example layout only — not live audio. Real use: Listen with the mic on the device that is playing.";
  statusEl.textContent = "Preview of Mix / Boom / Tune / Sparkle tracks. Time is the waveform. No slider. No song is playing.";
  showTour(2);
  for (let i = 0; i < colCount; i += 1) {
    const t = i / colCount;
    const beat = Math.max(0, Math.sin(t * Math.PI * 8));
    const hum = 0.35 + 0.45 * Math.abs(Math.sin(t * Math.PI * 3.2));
    history[0][i] = Math.min(1, 0.25 + 0.75 * beat * hum);
    history[1][i] = Math.min(1, 0.15 + 0.7 * Math.abs(Math.sin(t * Math.PI * 2.1)));
    history[2][i] = Math.min(1, 0.1 + 0.85 * hum * (0.4 + 0.6 * beat));
    history[3][i] = Math.min(1, 0.08 + 0.35 * Math.abs(Math.sin(t * Math.PI * 11)));
  }
  freq.fill(10);
  freq[10] = 160;
  freq[38] = 210;
  freq[56] = 90;
  writeCol = 0;
  noteEl.textContent = "A4";
  hzEl.textContent = "440.0 Hz";
  lightPiano(69);
  peaksEl.textContent = "A4   440.0 Hz\nE5   659.3 Hz\nA3   220.0 Hz";
  hardEl.textContent = "Example: several pitches at once. Live naming is hard because the picture keeps moving.";
  drawTracks(12);
  drawSpec([{ f: 440, mag: 200 }], 48000);
}

wire();
