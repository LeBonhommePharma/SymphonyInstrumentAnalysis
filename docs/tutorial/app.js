const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const TOUR = [
  {
    title: "We will not play a song over yours",
    body: "Play anything already on this device: a piano key, a video, a speaker. This page only draws the air that is wiggling right now.",
    seconds: 10,
  },
  {
    title: "Those wiggles have a speed",
    body: "Hertz (Hz) is how many wiggles happen in one second. Piano A is 440 Hz. If a number lights up, that is your sound, not a fake demo.",
    seconds: 12,
  },
  {
    title: "A song is a sandwich. That is the useful part.",
    body: "Boom on the bottom is left-hand / bass. The middle is the tune you can hum. The top is sparkle. The real tool writes that recipe so you can practice one layer at a time instead of a blur.",
    seconds: 14,
  },
  {
    title: "Live guessing is the hard part",
    body: "Notes stack. Piano keys also ring extra high copies (overtones). The computer needs a little bite of sound before it can guess — like reading a page that is still being flipped. So the grown-up tool records, then looks. Better answers, tiny delay.",
    seconds: 14,
  },
  {
    title: "Piano superpower",
    body: "If the loudest wiggle is 440, that is the A key. Find it. Play it. Match it. That is ear training: hearing a map, not a blob. Keep playing. Watch the keys light up.",
    seconds: 12,
  },
];

const waveCanvas = document.getElementById("wave");
const specCanvas = document.getElementById("spec");
const waveCtx = waveCanvas.getContext("2d");
const specCtx = specCanvas.getContext("2d");
const noteEl = document.getElementById("note");
const hzEl = document.getElementById("hz");
const quietEl = document.getElementById("quiet");
const peaksEl = document.getElementById("peaks");
const hardEl = document.getElementById("hard");
const bassBar = document.getElementById("bassBar");
const tuneBar = document.getElementById("tuneBar");
const sparkleBar = document.getElementById("sparkleBar");
const bassPct = document.getElementById("bassPct");
const tunePct = document.getElementById("tunePct");
const sparklePct = document.getElementById("sparklePct");
const pianoEl = document.getElementById("piano");
const tourStepEl = document.getElementById("tourStep");
const tourTitleEl = document.getElementById("tourTitle");
const tourBodyEl = document.getElementById("tourBody");
const tourFill = document.getElementById("tourFill");
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
const shareVideo = document.getElementById("shareVideo");

function hzToNote(f) {
  const midi = Math.round(69 + 12 * Math.log2(f / 440));
  return NOTE_NAMES[((midi % 12) + 12) % 12] + String(Math.floor(midi / 12) - 1);
}

function resizeCanvases() {
  for (const canvas of [waveCanvas, specCanvas]) {
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(320, Math.floor(rect.width * dpr));
    canvas.height = Math.max(120, Math.floor(rect.height * dpr || 160 * dpr));
  }
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

function drawWave() {
  const { width, height } = waveCanvas;
  waveCtx.fillStyle = "#111827";
  waveCtx.fillRect(0, 0, width, height);
  waveCtx.strokeStyle = "#fdba74";
  waveCtx.lineWidth = 2;
  waveCtx.beginPath();
  const slice = width / time.length;
  for (let i = 0; i < time.length; i += 1) {
    const v = time[i] / 128 - 1;
    const x = i * slice;
    const y = height / 2 + v * (height * 0.42);
    if (i === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
  }
  waveCtx.stroke();
}

function analyzeFrame(sampleRate) {
  const n = freq.length;
  const nyquist = sampleRate / 2;
  const binHz = nyquist / n;
  let bass = 0;
  let tune = 0;
  let sparkle = 0;
  const peaks = [];
  for (let i = 2; i < n - 2; i += 1) {
    const f = i * binHz;
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
  return { bass, tune, sparkle, tot, top, binHz };
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

function rmsOfTime() {
  let s = 0;
  for (let i = 0; i < time.length; i += 1) {
    const v = time[i] / 128 - 1;
    s += v * v;
  }
  return Math.sqrt(s / time.length);
}

function tick() {
  if (!analyser || !audioCtx) return;
  analyser.getByteFrequencyData(freq);
  analyser.getByteTimeDomainData(time);
  const rms = rmsOfTime();
  const info = analyzeFrame(audioCtx.sampleRate);
  drawWave();
  drawSpec(info.top, audioCtx.sampleRate);

  const b = (100 * info.bass) / info.tot;
  const t = (100 * info.tune) / info.tot;
  const s = (100 * info.sparkle) / info.tot;
  bassBar.style.width = `${b}%`;
  tuneBar.style.width = `${t}%`;
  sparkleBar.style.width = `${s}%`;
  bassPct.textContent = `${b.toFixed(0)}%`;
  tunePct.textContent = `${t.toFixed(0)}%`;
  sparklePct.textContent = `${s.toFixed(0)}%`;

  if (rms > 0.02 && info.top[0]) {
    heardSound = true;
    quietEl.textContent = "Hearing this device right now.";
    const f = info.top[0].f;
    noteEl.textContent = hzToNote(f);
    hzEl.textContent = `${f.toFixed(1)} Hz`;
    const midi = Math.round(69 + 12 * Math.log2(f / 440));
    lightPiano(midi);
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
  } else {
    quietEl.textContent = heardSound
      ? "Quiet now. Play again on the device."
      : "Nothing loud yet. Play a song, a video, or a piano key on this device.";
    noteEl.textContent = "—";
    hzEl.textContent = "waiting for this device";
    lightPiano(-1);
  }

  const elapsed = (performance.now() - tourStartedAt) / 1000;
  const scene = TOUR[tourIndex];
  const local = elapsed - TOUR.slice(0, tourIndex).reduce((a, x) => a + x.seconds, 0);
  const total = TOUR.reduce((a, x) => a + x.seconds, 0);
  tourFill.style.width = `${Math.min(100, (elapsed / total) * 100)}%`;
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
  // Do not connect to destination: we visualize only, we never play over the device.
  statusEl.textContent = label;
  gate.classList.add("hidden");
  tourStartedAt = performance.now();
  showTour(0);
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
    "Listening with the mic (piano, speakers, the room). Nothing is played back."
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
    "Listening to shared tab/window audio from this device. This page stays silent."
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
}

wire();
