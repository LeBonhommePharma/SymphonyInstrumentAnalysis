/**
 * Silent live listen — audio only, density-clustered tracks, soft auto-gain.
 * Never plays sound. Lane count follows spectral density (no fixed instrument cap).
 */
(function () {
  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const WINDOW_SEC = 18;
  const HEADER_W = 108;
  const LANE_CSS_PX = 64;
  const RULER_CSS_PX = 28;
  const DROP_AFTER_MS = 1800;
  const CLUSTER_CENTS = 85;
  const PRACTICAL_LANE_SOFT_MAX = 16;
  const LANE_COLORS = [
    "#f97316", "#2dd4bf", "#a78bfa", "#60a5fa", "#f472b6",
    "#fbbf24", "#34d399", "#fb7185", "#38bdf8", "#c084fc",
    "#facc15", "#4ade80", "#e879f9", "#22d3ee", "#fdba74", "#94a3b8",
  ];

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
  const statusEl = document.getElementById("status");
  const tracksHeadingEl = document.getElementById("tracksHeading");
  const meterFill = document.getElementById("meterFill");
  const gainEl = document.getElementById("gainReadout");
  const livePill = document.getElementById("livePill");
  const bootstrap = document.getElementById("bootstrap");

  let audioCtx = null;
  let analyser = null;
  let sourceNode = null;
  let stream = null;
  let raf = 0;
  let freq = new Uint8Array(2048);
  let time = new Uint8Array(2048);
  let listenStartedAt = 0;
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
  let noiseFloor = 0.004;
  let softGain = 1;
  let displayGain = 1;
  let lastClusters = [];

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
      case "bass": return t("familyBass");
      case "body": return t("familyBody");
      case "tune": return t("familyTune");
      case "air": return t("familyAir");
      case "noise": return t("familyNoise");
      default: return t("laneEmpty");
    }
  }

  function instrumentCountLabel(n) {
    if (n <= 0) return t("nInstrument0");
    if (n === 1) return t("nInstrument1");
    return t("nInstruments", { n: n });
  }

  function updateTracksHeading() {
    tracksHeadingEl.textContent = t("tracksHeading", {
      count: instrumentCountLabel(instruments.length),
    });
  }

  function setStatusKey(key) {
    lastStatusKey = key;
    statusEl.textContent = t(key);
  }

  function setListeningUi(on) {
    document.body.classList.toggle("is-listening", on);
    if (livePill) {
      livePill.hidden = !on;
      livePill.textContent = on ? t("hudLive") : t("hudOff");
    }
    if (bootstrap) bootstrap.classList.toggle("hidden", on || demoMode);
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
    specCanvas.height = Math.max(120, Math.floor((specRect.height || 180) * dpr));
    updateTracksHeading();
    drawTracks(lastElapsed);
  }

  function resetHistory() {
    instruments = [];
    nextInstrumentId = 1;
    writeCol = 0;
    colStart = performance.now();
    noiseFloor = 0.004;
    softGain = 1;
    displayGain = 1;
    lastClusters = [];
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

  function lightPiano(midiSet) {
    const set = midiSet instanceof Set ? midiSet : new Set(midiSet == null ? [] : [midiSet]);
    pianoEl.querySelectorAll("[data-midi]").forEach(function (el) {
      el.classList.toggle("on", set.has(Number(el.dataset.midi)));
    });
  }

  function rmsOfTime() {
    let s = 0;
    for (let i = 0; i < time.length; i += 1) {
      const v = time[i] / 128 - 1;
      s += v * v;
    }
    return Math.sqrt(s / time.length);
  }

  function updateAutoGain(rms) {
    // Track a slow noise floor and raise soft gain so headphone bleed / quiet rooms still draw.
    const alphaFloor = rms < noiseFloor * 1.35 ? 0.06 : 0.012;
    noiseFloor = noiseFloor * (1 - alphaFloor) + rms * alphaFloor;
    const target = 0.045;
    const needed = Math.min(48, Math.max(1, target / Math.max(0.0008, noiseFloor * 2.8)));
    softGain = softGain * 0.92 + needed * 0.08;
    displayGain = softGain;
    if (gainEl) gainEl.textContent = "×" + displayGain.toFixed(1);
    if (meterFill) {
      const level = Math.min(1, rms * softGain * 4.2);
      meterFill.style.transform = "scaleX(" + level.toFixed(3) + ")";
      meterFill.classList.toggle("hot", level > 0.82);
    }
  }

  function extractPeaks(sampleRate, gain) {
    const n = freq.length;
    const nyquist = sampleRate / 2;
    const peaks = [];
    let energy = 0;
    for (let i = 2; i < n - 2; i += 1) {
      const f = i * (nyquist / n);
      if (f < 35 || f > 6000) continue;
      const mag = Math.min(255, freq[i] * gain);
      energy += mag;
      if (
        mag > freq[i - 1] * gain &&
        mag > freq[i + 1] * gain &&
        mag >= freq[i - 2] * gain &&
        mag >= freq[i + 2] * gain &&
        mag > 10
      ) {
        peaks.push({ f: f, mag: mag, logF: Math.log2(f) });
      }
    }
    peaks.sort(function (a, b) {
      return b.mag - a.mag;
    });
    // De-duplicate harmonics within ~1 semitone before clustering.
    const uniq = [];
    peaks.forEach(function (p) {
      if (uniq.some(function (q) {
        return Math.abs(p.logF - q.logF) < 1 / 12;
      })) return;
      uniq.push(p);
    });
    return { peaks: uniq.slice(0, 48), energy: energy };
  }

  /**
   * Density-based clustering in log-frequency (cents).
   * Bandwidth adapts from local peak density — lane count is discovered, not fixed.
   */
  function densityCluster(peaks) {
    if (!peaks.length) return [];
    const pts = peaks
      .map(function (p) {
        return { f: p.f, mag: p.mag, x: 1200 * Math.log2(p.f / 440) };
      })
      .sort(function (a, b) {
        return a.x - b.x;
      });

    // Adaptive bandwidth from median nearest-neighbor gap in cents.
    const gaps = [];
    for (let i = 1; i < pts.length; i += 1) {
      gaps.push(pts[i].x - pts[i - 1].x);
    }
    gaps.sort(function (a, b) {
      return a - b;
    });
    const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : CLUSTER_CENTS;
    const bandwidth = Math.max(55, Math.min(140, medianGap * 1.35 || CLUSTER_CENTS));

    const assigned = new Array(pts.length).fill(-1);
    const clusters = [];
    for (let i = 0; i < pts.length; i += 1) {
      if (assigned[i] >= 0) continue;
      const seed = pts[i];
      if (seed.mag < 12) continue;
      // Core: neighbors within bandwidth that are also dense relative to seed.
      const members = [i];
      assigned[i] = clusters.length;
      for (let j = 0; j < pts.length; j += 1) {
        if (assigned[j] >= 0) continue;
        if (Math.abs(pts[j].x - seed.x) <= bandwidth && pts[j].mag > seed.mag * 0.22) {
          assigned[j] = clusters.length;
          members.push(j);
        }
      }
      // Expand once more from members (simple DBSCAN-ish).
      for (let m = 0; m < members.length; m += 1) {
        const mid = members[m];
        for (let j = 0; j < pts.length; j += 1) {
          if (assigned[j] >= 0) continue;
          if (Math.abs(pts[j].x - pts[mid].x) <= bandwidth * 0.85 && pts[j].mag > 11) {
            assigned[j] = clusters.length;
            members.push(j);
          }
        }
      }
      let wSum = 0;
      let fSum = 0;
      let magMax = 0;
      members.forEach(function (idx) {
        const p = pts[idx];
        const w = p.mag;
        wSum += w;
        fSum += p.f * w;
        if (p.mag > magMax) magMax = p.mag;
      });
      clusters.push({
        f: fSum / (wSum || 1),
        mag: magMax,
        n: members.length,
        density: members.length / Math.max(1, bandwidth),
      });
    }

    clusters.sort(function (a, b) {
      return b.mag * (1 + b.density) - a.mag * (1 + a.density);
    });

    // Keep clusters that clear a relative density floor; soft UI cap only.
    if (!clusters.length) return [];
    const topScore = clusters[0].mag * (1 + clusters[0].density);
    return clusters
      .filter(function (c) {
        return c.mag >= 11 && c.mag * (1 + c.density) >= topScore * 0.16;
      })
      .slice(0, PRACTICAL_LANE_SOFT_MAX);
  }

  function liveKind(rms, clusters) {
    const boosted = rms * softGain;
    if (boosted < 0.006 && (!clusters.length || clusters[0].mag < 14)) return "quiet";
    if (!clusters.length || clusters[0].mag < 18) return "noise";
    return "pitch";
  }

  function matchCluster(cluster, usedIds) {
    let best = null;
    let bestDist = 1 / 10;
    instruments.forEach(function (inst) {
      if (usedIds.has(inst.id) || inst.family === "noise" || inst.hz <= 0) return;
      const dist = Math.abs(Math.log2(cluster.f / inst.hz));
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

  function syncInstruments(clusters, rms, now) {
    const kind = liveKind(rms, clusters);
    lastClusters = clusters;
    if (kind === "quiet") {
      // Still keep a faint room lane so the UI never looks frozen.
      let room = instruments.find(function (inst) {
        return inst.family === "noise";
      });
      if (!room && rms * softGain > 0.002) {
        room = makeInstrument(0, "noise");
        instruments = [room];
      }
      instruments.forEach(function (inst) {
        inst.pendingAmp = inst.family === "noise" ? Math.min(0.35, rms * softGain * 8) : 0;
        if (inst.family === "noise") inst.lastSeen = now;
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
        instruments = instruments.filter(function (inst) {
          return inst.family === "noise";
        });
        if (!instruments.length) {
          instruments = [noise];
        }
      }
      noise.pendingAmp = Math.min(1, rms * softGain * 5.5);
      noise.lastSeen = now;
      return kind;
    }

    instruments = instruments.filter(function (inst) {
      return inst.family !== "noise";
    });
    const used = new Set();
    clusters.forEach(function (cluster) {
      const match = matchCluster(cluster, used);
      if (match) {
        used.add(match.id);
        match.hz = cluster.f * 0.4 + match.hz * 0.6;
        match.family = familyForHz(match.hz);
        match.pendingAmp = Math.min(1, (cluster.mag / 255) * softGain * 1.5);
        match.lastSeen = now;
        return;
      }
      const inst = makeInstrument(cluster.f, familyForHz(cluster.f));
      inst.pendingAmp = Math.min(1, (cluster.mag / 255) * softGain * 1.5);
      inst.lastSeen = now;
      used.add(inst.id);
      instruments.push(inst);
    });
    instruments.forEach(function (inst) {
      if (!used.has(inst.id)) inst.pendingAmp = Math.max(0, inst.pendingAmp * 0.4);
    });
    dropStale(now);
    // Soft UI trim if clustering exploded.
    if (instruments.length > PRACTICAL_LANE_SOFT_MAX) {
      instruments = displayLanes().slice(0, PRACTICAL_LANE_SOFT_MAX);
    }
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
    ctx.fillStyle = "#0c1017";
    ctx.fillRect(0, 0, width, height);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const header = HEADER_W * dpr;
    const rulerH = 26 * dpr;
    const lanes = displayLanes();
    const laneCount = Math.max(1, lanes.length);
    const laneH = (height - rulerH) / laneCount;
    const laneW = width - header;

    ctx.fillStyle = "#090c12";
    ctx.fillRect(0, 0, width, rulerH);
    ctx.textBaseline = "middle";
    const secStep = 2;
    for (let s = 0; s <= WINDOW_SEC; s += secStep) {
      const x = header + (s / WINDOW_SEC) * laneW;
      ctx.fillStyle = "rgba(148,163,184,0.12)";
      ctx.fillRect(x, rulerH, Math.max(1, dpr), height - rulerH);
      ctx.fillStyle = "#94a3b8";
      ctx.font = 10 * dpr + "px ui-monospace, SFMono-Regular, Menlo, monospace";
      const label = s === WINDOW_SEC ? t("rulerNow") : "-" + (WINDOW_SEC - s) + "s";
      ctx.fillText(label, x - (s === WINDOW_SEC ? 26 * dpr : 8 * dpr), rulerH / 2);
    }

    if (!lanes.length) {
      const mid = rulerH + laneH / 2;
      ctx.fillStyle = "#121722";
      ctx.fillRect(0, rulerH, width, laneH);
      ctx.fillStyle = "#0b0f16";
      ctx.fillRect(0, rulerH, header, laneH);
      ctx.fillStyle = "#64748b";
      ctx.font = "600 " + 12 * dpr + "px ui-sans-serif, system-ui, sans-serif";
      ctx.fillText(t("laneEmpty"), 12 * dpr, mid);
    } else {
      lanes.forEach(function (track, lane) {
        const y0 = rulerH + lane * laneH;
        const mid = y0 + laneH / 2;
        ctx.fillStyle = lane % 2 === 0 ? "#121722" : "#0e131c";
        ctx.fillRect(0, y0, width, laneH);
        ctx.fillStyle = "#0b0f16";
        ctx.fillRect(0, y0, header, laneH);

        ctx.fillStyle = track.color;
        ctx.beginPath();
        ctx.arc(14 * dpr, mid, 4 * dpr, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = "600 " + 11 * dpr + "px ui-sans-serif, system-ui, sans-serif";
        const name =
          track.family === "noise" || track.hz <= 0
            ? familyLabel(track.family)
            : familyLabel(track.family) + " · " + hzToNote(track.hz);
        ctx.fillText(name, 24 * dpr, mid - 6 * dpr);
        ctx.fillStyle = "#64748b";
        ctx.font = 9 * dpr + "px ui-monospace, Menlo, monospace";
        ctx.fillText(
          track.hz > 0 ? track.hz.toFixed(0) + " Hz" : "room",
          24 * dpr,
          mid + 10 * dpr
        );

        ctx.strokeStyle = "rgba(148,163,184,0.12)";
        ctx.beginPath();
        ctx.moveTo(header, y0);
        ctx.lineTo(width, y0);
        ctx.stroke();
        ctx.beginPath();
        ctx.strokeStyle = "rgba(255,255,255,0.04)";
        ctx.moveTo(header, mid);
        ctx.lineTo(width, mid);
        ctx.stroke();

        const ampScale = laneH * 0.44;
        ctx.beginPath();
        let started = false;
        for (let x = 0; x < laneW; x += 1) {
          const age = laneW - 1 - x;
          const idx = (writeCol - 1 - age + colCount * 8) % colCount;
          const amp = track.history[idx] || 0;
          const h = Math.max(dpr * 0.5, amp * ampScale);
          const px = header + x;
          if (!started) {
            ctx.moveTo(px, mid - h);
            started = true;
          } else {
            ctx.lineTo(px, mid - h);
          }
        }
        for (let x = laneW - 1; x >= 0; x -= 1) {
          const age = laneW - 1 - x;
          const idx = (writeCol - 1 - age + colCount * 8) % colCount;
          const amp = track.history[idx] || 0;
          const h = Math.max(dpr * 0.5, amp * ampScale);
          ctx.lineTo(header + x, mid + h);
        }
        ctx.closePath();
        ctx.fillStyle = track.color;
        ctx.globalAlpha = 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;
      });
    }

    const playX = width - 3 * dpr;
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(playX, rulerH, Math.max(2, dpr), height - rulerH);
    ctx.fillStyle = "#64748b";
    ctx.font = 10 * dpr + "px ui-monospace, Menlo, monospace";
    ctx.fillText(t("liveElapsed", { n: elapsedSec.toFixed(0) }), 10 * dpr, rulerH / 2);
  }

  function drawSpec(clusters, sampleRate) {
    const { width, height } = specCanvas;
    specCtx.fillStyle = "#0c1017";
    specCtx.fillRect(0, 0, width, height);
    const n = freq.length;
    const nyquist = sampleRate / 2;
    const maxBin = Math.min(n, Math.floor((6000 / nyquist) * n));
    const barW = width / maxBin;
    for (let i = 0; i < maxBin; i += 1) {
      const f = (i / n) * nyquist;
      const h = Math.min(height, ((freq[i] * softGain) / 255) * height);
      if (f < 250) specCtx.fillStyle = "#f97316";
      else if (f < 2000) specCtx.fillStyle = "#2dd4bf";
      else specCtx.fillStyle = "#a78bfa";
      specCtx.globalAlpha = 0.9;
      specCtx.fillRect(i * barW, height - h, Math.max(barW, 1), h);
    }
    specCtx.globalAlpha = 1;
    clusters.slice(0, 8).forEach(function (c) {
      const x = (c.f / 6000) * width;
      specCtx.strokeStyle = "rgba(248,250,252,0.55)";
      specCtx.beginPath();
      specCtx.moveTo(x, 0);
      specCtx.lineTo(x, height);
      specCtx.stroke();
    });
    if (clusters[0]) {
      specCtx.fillStyle = "#f8fafc";
      specCtx.font = Math.max(12, Math.floor(height / 10)) + "px ui-sans-serif";
      specCtx.fillText(
        hzToNote(clusters[0].f) + "  " + clusters[0].f.toFixed(1) + " Hz · " + clusters.length + " src",
        12,
        20
      );
    }
  }

  function tick() {
    if (!analyser || !audioCtx) return;
    analyser.getByteFrequencyData(freq);
    analyser.getByteTimeDomainData(time);
    const rms = rmsOfTime();
    updateAutoGain(rms);
    const extracted = extractPeaks(audioCtx.sampleRate, softGain);
    const clusters = densityCluster(extracted.peaks);
    const now = performance.now();
    const kind = syncInstruments(clusters, rms, now);
    pushColumn();
    maybeRelayout();
    lastElapsed = (now - listenStartedAt) / 1000;
    drawTracks(lastElapsed);
    drawSpec(clusters, audioCtx.sampleRate);

    if (kind !== "quiet") heardSound = true;
    if (kind === "pitch") {
      quietEl.textContent = t("quietPitch");
      const f = clusters[0].f;
      noteEl.textContent = hzToNote(f);
      hzEl.textContent = f.toFixed(1) + " Hz";
      const midiSet = new Set(
        clusters.slice(0, 6).map(function (c) {
          return Math.round(69 + 12 * Math.log2(c.f / 440));
        })
      );
      lightPiano(midiSet);
      peaksEl.textContent = clusters
        .slice(0, 10)
        .map(function (c) {
          return hzToNote(c.f).padEnd(4, " ") + "  " + c.f.toFixed(1) + " Hz";
        })
        .join("\n");
      if (clusters.length >= 4) hardEl.textContent = t("hardMany", { n: clusters.length });
      else hardEl.textContent = t("hardClear");
    } else if (kind === "noise") {
      quietEl.textContent = t("quietNoise");
      noteEl.textContent = "—";
      hzEl.textContent = t("hzNoPitch");
      lightPiano([]);
      peaksEl.textContent = t("peaksNoise");
      hardEl.textContent = t("hardNoise");
    } else {
      quietEl.textContent = heardSound ? t("quietAfter") : t("quietIdle");
      noteEl.textContent = "—";
      hzEl.textContent = t("hzWaitingDevice");
      lightPiano([]);
    }
    raf = requestAnimationFrame(tick);
  }

  function canShareTabAudio() {
    const isiOS =
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
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
    if (!Ctor) throw new Error(t("errNoAudioCtx"));
    return new Ctor();
  }

  function audioOnlyStream(mediaStream) {
    const audioTracks = mediaStream.getAudioTracks();
    mediaStream.getVideoTracks().forEach(function (track) {
      track.stop();
    });
    if (!audioTracks.length) {
      mediaStream.getTracks().forEach(function (track) {
        track.stop();
      });
      throw new Error(t("errNoAudioTrack"));
    }
    return new MediaStream(audioTracks);
  }

  async function startFromStream(mediaStream, statusKey) {
    stopListen();
    demoMode = false;
    stream = mediaStream;
    audioCtx = makeAudioContext();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 4096;
    analyser.smoothingTimeConstant = 0.55;
    analyser.minDecibels = -100;
    analyser.maxDecibels = -20;
    freq = new Uint8Array(analyser.frequencyBinCount);
    time = new Uint8Array(analyser.fftSize);
    sourceNode = audioCtx.createMediaStreamSource(mediaStream);
    // Analysis only — never connect to destination (page stays silent).
    sourceNode.connect(analyser);
    setStatusKey(statusKey);
    setListeningUi(true);
    listenStartedAt = performance.now();
    heardSound = false;
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
    setListeningUi(false);
  }

  async function listenMic() {
    const mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        // Browser AGC off — we apply soft gain in analysis so quiet / headphone bleed still draws.
        autoGainControl: false,
        channelCount: 1,
      },
      video: false,
    });
    await startFromStream(mediaStream, "statusMicOn");
  }

  async function listenSystemAudio() {
    if (!canShareTabAudio()) {
      const err = new Error(t("errNoTabShare"));
      err.name = "NotSupportedError";
      throw err;
    }
    // Audio-first. Prefer audio-only constraints. Some browsers still require a video track
    // for getDisplayMedia — if so, discard video immediately and keep only audio.
    let mediaStream = null;
    try {
      mediaStream = await navigator.mediaDevices.getDisplayMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
        video: false,
      });
    } catch (firstErr) {
      try {
        mediaStream = await navigator.mediaDevices.getDisplayMedia({
          audio: true,
          video: true,
          preferCurrentTab: true,
        });
      } catch (secondErr) {
        throw firstErr;
      }
    }
    const audioStream = audioOnlyStream(mediaStream);
    await startFromStream(audioStream, "statusTabOn");
  }

  function fillExampleTracks() {
    demoMode = true;
    setListeningUi(true);
    quietEl.textContent = t("demoQuiet");
    setStatusKey("demoStatus");
    const demo = [
      { hz: 55, family: "bass", wave: function (x) { return 0.22 + 0.65 * Math.abs(Math.sin(x * Math.PI * 2)); } },
      { hz: 110, family: "bass", wave: function (x) { return 0.16 + 0.5 * Math.abs(Math.sin(x * Math.PI * 2.4 + 0.3)); } },
      { hz: 196, family: "body", wave: function (x) { return 0.14 + 0.48 * Math.abs(Math.sin(x * Math.PI * 3)); } },
      { hz: 329.6, family: "tune", wave: function (x) { return 0.12 + 0.55 * Math.abs(Math.sin(x * Math.PI * 4.2)); } },
      { hz: 440, family: "tune", wave: function (x) {
        const beat = Math.max(0.2, Math.sin(x * Math.PI * 8));
        return 0.12 + 0.8 * beat * (0.4 + 0.6 * Math.abs(Math.sin(x * Math.PI * 3)));
      } },
      { hz: 659.3, family: "tune", wave: function (x) { return 0.08 + 0.42 * Math.abs(Math.sin(x * Math.PI * 5.5)); } },
      { hz: 1046.5, family: "air", wave: function (x) { return 0.06 + 0.32 * Math.abs(Math.sin(x * Math.PI * 11)); } },
      { hz: 2093, family: "air", wave: function (x) { return 0.04 + 0.22 * Math.abs(Math.sin(x * Math.PI * 17)); } },
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
    softGain = 2.4;
    writeCol = 0;
    lastElapsed = 12;
    noteEl.textContent = "A4";
    hzEl.textContent = "440.0 Hz";
    lightPiano(new Set([69, 76, 81]));
    peaksEl.textContent = demo
      .map(function (row) {
        return hzToNote(row.hz).padEnd(4, " ") + "  " + row.hz.toFixed(1) + " Hz";
      })
      .join("\n");
    hardEl.textContent = t("demoHard");
    updateTracksHeading();
    drawTracks(12);
    drawSpec(
      demo.map(function (row) {
        return { f: row.hz, mag: 180, n: 1, density: 1 };
      }),
      48000
    );
  }

  function refreshI18n() {
    updateTracksHeading();
    if (lastStatusKey) statusEl.textContent = t(lastStatusKey);
    if (livePill && !livePill.hidden) livePill.textContent = t("hudLive");
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
    document.querySelectorAll("[data-action='mic']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        listenMic().catch(showListenError);
      });
    });
    document.querySelectorAll("[data-action='system']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        listenSystemAudio().catch(showListenError);
      });
    });
    document.querySelectorAll("[data-action='stop']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        stopListen();
        demoMode = false;
        setStatusKey("statusStopped");
      });
    });
    setStatusKey("footerHint");
    quietEl.textContent = t("quietIdle");
    peaksEl.textContent = t("peaksWaiting");
    hardEl.textContent = t("hardDefault");
    hzEl.textContent = t("hzWaiting");
    updateTracksHeading();
    setListeningUi(false);
    if (new URLSearchParams(window.location.search).has("demo")) {
      fillExampleTracks();
    }
  }

  wire();
})();
