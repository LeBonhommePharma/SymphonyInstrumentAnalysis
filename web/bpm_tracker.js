/* Live BPM counter — port of scripts/bpm_tracker.py (same constants, same math).
   Contract: piano/dsp_contract.json → "bpm". Swift port: ios/…/BpmTracker.swift.

   Two front ends feed one estimator:
     pushPcm(samples, sr)          contiguous PCM (node self-test, workers)
     pushSpectrum(t, db, binHz)    AnalyserNode float-dB frames stamped with
                                   audioCtx.currentTime, resampled onto the
                                   100 Hz onset grid (the pages' rAF loop)
   Both produce the SuperFlux-style onset strength: bin magnitudes averaged
   into log bands (6 per octave, 30 Hz–8 kHz), log1p(100·m) per band, rise
   above the 3-band max of the previous frame minus a 0.05 deadband, 1 s
   running mean removed, half-wave rectified.

   Tempo: 3-tap smoothed envelope, multiplicative tolerant comb
   r(L)·(1 + ½·max r(2L±1) + ¼·max r(4L±2)) over the last 8 s, log-Gaussian
   prior at 128 BPM (σ 0.75 oct), 60–200 BPM, parabolic refine, then the
   halving test (max r at half of L* ± 1 ≥ 0.9·r(L*) → the faster reading).
   Ready needs BOTH r(L*) ≥ 0.12 (confidence) and a beat-phase fold whose
   Shannon entropy collapses (1 − H ≥ 0.12): a stationary tone passes the
   first and fails the second. Display = median of the last 5 estimates. */
(function (global) {
  "use strict";

  const ONSET_HZ = 100;
  const FRAME = 2048;
  const WINDOW_S = 8;
  const MIN_S = 3;
  const UPDATE_S = 0.25;
  const BPM_MIN = 60;
  const BPM_MAX = 200;
  const PRIOR_BPM = 128;
  const PRIOR_SIGMA_OCT = 0.75;
  const FOLD_BINS = 16;
  const COMB_W2 = 0.5;
  const COMB_W4 = 0.25;
  const HALF_RATIO = 0.9;
  const FLUX_MU = 100;
  const FLUX_LO_HZ = 30;
  const FLUX_HI_HZ = 8000;
  const BANDS_PER_OCTAVE = 6;
  const MEAN_TAU_S = 1;
  const FLUX_DEADBAND = 0.05;
  const READY_CONFIDENCE = 0.12;
  const READY_COLLAPSE = 0.12;
  const MEDIAN_N = 5;

  function tempoPrior(bpm) {
    if (!(bpm > 0)) return 0;
    const z = Math.log2(bpm / PRIOR_BPM) / PRIOR_SIGMA_OCT;
    return Math.exp(-0.5 * z * z);
  }

  function autocorrelation(x, maxLag) {
    const n = x.length;
    const r = new Float64Array(maxLag + 1);
    let energy = 0;
    for (let i = 0; i < n; i++) energy += x[i] * x[i];
    if (!(energy > 0) || n === 0) return r;
    const top = Math.min(maxLag, n - 1);
    for (let lag = 0; lag <= top; lag++) {
      let s = 0;
      for (let i = lag; i < n; i++) s += x[i] * x[i - lag];
      r[lag] = s / energy;
    }
    return r;
  }

  /** (1 − normalised Shannon entropy, phase of the loudest bin) of the beat fold. */
  function foldCollapse(env, lag, bins) {
    bins = bins || FOLD_BINS;
    const n = env.length;
    let total = 0;
    for (let i = 0; i < n; i++) total += env[i];
    if (!(total > 0) || !(lag > 0) || n === 0) return { collapse: 0, phase: 0 };
    const hist = new Float64Array(bins);
    for (let i = 0; i < n; i++) {
      const phase = (i / lag) % 1;
      const b = Math.min(bins - 1, Math.floor(phase * bins));
      hist[b] += env[i];
    }
    let h = 0;
    let best = 0;
    for (let b = 0; b < bins; b++) {
      const p = hist[b] / total;
      if (p > 0) h -= p * Math.log(p);
      if (hist[b] > hist[best]) best = b;
    }
    h /= Math.log(bins);
    return { collapse: Math.max(0, Math.min(1, 1 - h)), phase: best / bins };
  }

  const NOT_READY = { bpm: 0, lag: 0, confidence: 0, collapse: 0, phase: 0, ready: false };

  /** 3-tap Hann (¼, ½, ¼) with edge hold — widens 10 ms spikes to ~30 ms. */
  function smooth3(env) {
    const n = env.length;
    const out = new Float64Array(n);
    if (n < 3) {
      out.set(env);
      return out;
    }
    for (let i = 1; i < n - 1; i++) out[i] = 0.25 * env[i - 1] + 0.5 * env[i] + 0.25 * env[i + 1];
    out[0] = 0.75 * env[0] + 0.25 * env[1];
    out[n - 1] = 0.75 * env[n - 1] + 0.25 * env[n - 2];
    return out;
  }

  function estimateTempo(envIn, fps) {
    fps = fps || ONSET_HZ;
    const n = envIn.length;
    const env = new Float64Array(n);
    let sum = 0;
    for (let i = 0; i < n; i++) {
      env[i] = envIn[i] > 0 ? envIn[i] : 0;
      sum += env[i];
    }
    const lagMin = Math.round(fps * 60 / BPM_MAX);
    const lagMax = Math.round(fps * 60 / BPM_MIN);
    if (n < lagMax + 2 || !(sum > 0)) return NOT_READY;
    const smoothed = smooth3(env);
    let mean = 0;
    for (let i = 0; i < n; i++) mean += smoothed[i];
    mean /= n;
    const x = new Float64Array(n);
    let energy = 0;
    for (let i = 0; i < n; i++) {
      x[i] = smoothed[i] - mean;
      energy += x[i] * x[i];
    }
    if (energy <= 1e-12) return NOT_READY;
    const top = Math.min(n - 1, 4 * lagMax);
    const r = autocorrelation(x, top);
    function near(lag, tol) {
      const lo = Math.max(0, lag - tol);
      const hi = Math.min(top, lag + tol);
      let m = -Infinity;
      for (let l = lo; l <= hi; l++) if (r[l] > m) m = r[l];
      return hi >= lo ? m : 0;
    }
    function enhanced(lag) {
      const own = Math.max(0, r[lag]);
      let comb = 1;
      if (2 * lag <= top) comb += COMB_W2 * Math.max(0, near(2 * lag, 1));
      if (4 * lag <= top) comb += COMB_W4 * Math.max(0, near(4 * lag, 2));
      return own * comb;
    }
    // One lag beyond each edge is scored too, so the parabola always has neighbours.
    const lo = Math.max(1, lagMin - 1);
    const hi = Math.min(top, lagMax + 1);
    const score = new Float64Array(hi + 1);
    for (let lag = lo; lag <= hi; lag++) score[lag] = enhanced(lag) * tempoPrior(60 * fps / lag);
    let best = lagMin;
    for (let lag = lagMin; lag <= lagMax; lag++) if (score[lag] > score[best]) best = lag;
    const half = Math.round(best / 2);
    if (half >= lagMin && r[best] > 0 && near(half, 1) >= HALF_RATIO * r[best]) {
      let pick = Math.max(lagMin, half - 1);
      for (let l = pick; l <= Math.min(lagMax, half + 1); l++) if (r[l] > r[pick]) pick = l;
      best = pick;
    }
    let lag = best;
    if (best - 1 >= lo && best + 1 <= hi) {
      const s0 = score[best - 1];
      const s1 = score[best];
      const s2 = score[best + 1];
      const denom = s0 - 2 * s1 + s2;
      if (denom < 0) lag = best + Math.max(-0.5, Math.min(0.5, 0.5 * (s0 - s2) / denom));
    }
    const confidence = Math.max(0, Math.min(1, r[best]));
    const fold = foldCollapse(env, lag, FOLD_BINS);
    const ready = confidence >= READY_CONFIDENCE && fold.collapse >= READY_COLLAPSE;
    return { bpm: 60 * fps / lag, lag: lag, confidence: confidence, collapse: fold.collapse, phase: fold.phase, ready: ready };
  }

  /* ── log bands (shared by both front ends; same plan as bpm_tracker.band_plan) ── */
  /** [[kLo, kHi], …] inclusive bin ranges of the log bands that hold ≥ 1 bin. */
  function bandPlan(binHz, nBins) {
    const kLo = Math.max(1, Math.ceil(FLUX_LO_HZ / binHz));
    const hiHz = Math.min(FLUX_HI_HZ, binHz * (nBins - 1));
    const kHi = Math.floor(hiHz / binHz);
    const plan = [];
    let cur = -1;
    let start = kLo;
    for (let k = kLo; k <= kHi; k++) {
      const b = Math.floor(BANDS_PER_OCTAVE * Math.log2((k * binHz) / FLUX_LO_HZ));
      if (b !== cur) {
        if (cur >= 0) plan.push([start, k - 1]);
        cur = b;
        start = k;
      }
    }
    if (cur >= 0 && kHi >= start) plan.push([start, kHi]);
    return plan;
  }

  /** Mean linear magnitude per band, log-compressed: ln(1 + 100·m_b). */
  function bandLogmag(mag, plan) {
    const out = new Float64Array(plan.length);
    for (let i = 0; i < plan.length; i++) {
      const a = plan[i][0];
      const b = plan[i][1];
      let s = 0;
      for (let k = a; k <= b; k++) s += mag[k];
      out[i] = Math.log1p(FLUX_MU * (s / (b - a + 1)));
    }
    return out;
  }

  /* ── onset strength from log-magnitude frames (shared by both front ends) ── */
  function fluxFrom(logmag, prev) {
    const n = logmag.length;
    let flux = 0;
    for (let k = 0; k < n; k++) {
      let pm = prev[k];
      if (k > 0 && prev[k - 1] > pm) pm = prev[k - 1];
      if (k < n - 1 && prev[k + 1] > pm) pm = prev[k + 1];
      const d = logmag[k] - pm - FLUX_DEADBAND;
      if (d > 0) flux += d;
    }
    return flux;
  }

  function hann(n) {
    const w = new Float64Array(n);
    for (let i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (n - 1));
    return w;
  }

  function fftRadix2(re, im) {
    const n = re.length;
    let j = 0;
    for (let i = 0; i < n; i++) {
      if (i < j) {
        let t = re[i]; re[i] = re[j]; re[j] = t;
        t = im[i]; im[i] = im[j]; im[j] = t;
      }
      let m = n >> 1;
      while (m >= 1 && j >= m) { j -= m; m >>= 1; }
      j += m;
    }
    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1;
      const step = (2 * Math.PI) / size;
      for (let i = 0; i < n; i += size) {
        for (let k = 0; k < half; k++) {
          const ang = step * k;
          const wr = Math.cos(ang);
          const wi = -Math.sin(ang);
          const xr = re[i + k + half];
          const xi = im[i + k + half];
          const tr = wr * xr - wi * xi;
          const ti = wr * xi + wi * xr;
          re[i + k + half] = re[i + k] - tr;
          im[i + k + half] = im[i + k] - ti;
          re[i + k] += tr;
          im[i + k] += ti;
        }
      }
    }
  }

  /** PCM → onset values at ONSET_HZ. Mirrors bpm_tracker.OnsetFrontEnd. */
  function OnsetFrontEnd(sr, opts) {
    opts = opts || {};
    this.sr = sr;
    this.frame = opts.frame || FRAME;
    this.hop = Math.max(1, Math.round(sr / ONSET_HZ));
    this.win = hann(this.frame);
    this.plan = bandPlan(sr / this.frame, this.frame / 2 + 1);
    this.alpha = 1 / (MEAN_TAU_S * ONSET_HZ);
    this.re = new Float64Array(this.frame);
    this.im = new Float64Array(this.frame);
    this.reset();
  }
  OnsetFrontEnd.prototype.reset = function () {
    this.buf = new Float64Array(0);
    this.prev = null;
    this.mean = 0;
    this.primed = false;
  };
  OnsetFrontEnd.prototype.push = function (samples) {
    const out = [];
    if (!samples || !samples.length) return out;
    const joined = new Float64Array(this.buf.length + samples.length);
    joined.set(this.buf, 0);
    for (let i = 0; i < samples.length; i++) joined[this.buf.length + i] = samples[i];
    let off = 0;
    while (joined.length - off >= this.frame) {
      out.push(this.onset(joined.subarray(off, off + this.frame)));
      off += this.hop;
    }
    this.buf = joined.slice(off);
    return out;
  };
  OnsetFrontEnd.prototype.onset = function (frame) {
    const n = this.frame;
    const re = this.re;
    const im = this.im;
    for (let i = 0; i < n; i++) {
      re[i] = frame[i] * this.win[i];
      im[i] = 0;
    }
    fftRadix2(re, im);
    const bins = n / 2 + 1;
    const mag = new Float64Array(bins);
    for (let b = 0; b < bins; b++) mag[b] = Math.sqrt(re[b] * re[b] + im[b] * im[b]) * (4 / n);
    const logmag = bandLogmag(mag, this.plan);
    if (!this.prev) {
      this.prev = logmag;
      return 0;
    }
    const flux = fluxFrom(logmag, this.prev);
    this.prev = logmag;
    if (!this.primed) {
      this.mean = flux;
      this.primed = true;
    } else {
      this.mean += (flux - this.mean) * this.alpha;
    }
    return Math.max(0, flux - this.mean);
  };

  /** AnalyserNode float-dB frames (any fftSize, no smoothing) → onset grid cells. */
  function SpectrumFrontEnd() {
    this.reset();
  }
  SpectrumFrontEnd.prototype.reset = function () {
    this.prev = null;
    this.prevKey = "";
    this.mean = 0;
    this.primed = false;
    this.lastT = -1;
    this.lastCell = -1;
  };
  /** Returns {cell, value} pairs to write on the onset grid (cells between frames read 0). */
  SpectrumFrontEnd.prototype.push = function (t, db, binHz) {
    const key = db.length + ":" + binHz;
    if (!this.plan || this.planKey !== key) {
      this.plan = bandPlan(binHz, db.length);
      this.planKey = key;
    }
    const mag = new Float64Array(db.length);
    for (let k = 0; k < db.length; k++) {
      const v = db[k];
      mag[k] = isFinite(v) ? Math.pow(10, v / 20) : 0;
    }
    const logmag = bandLogmag(mag, this.plan);
    if (!this.prev || this.prevKey !== key || this.lastT < 0 || t < this.lastT) {
      this.prev = logmag;
      this.prevKey = key;
      this.lastT = t;
      this.lastCell = Math.floor(t * ONSET_HZ);
      return [];
    }
    const dt = Math.max(0, t - this.lastT);
    const flux = fluxFrom(logmag, this.prev);
    this.prev = logmag;
    this.lastT = t;
    if (!this.primed) {
      this.mean = flux;
      this.primed = true;
    } else {
      this.mean += (flux - this.mean) * Math.min(1, dt / MEAN_TAU_S);
    }
    const onset = Math.max(0, flux - this.mean);
    const cell = Math.floor(t * ONSET_HZ);
    const out = [];
    if (cell > this.lastCell) {
      for (let c = this.lastCell + 1; c < cell; c++) out.push({ cell: c, value: 0 });
      out.push({ cell: cell, value: onset });
      this.lastCell = cell;
    } else {
      out.push({ cell: this.lastCell, value: onset, merge: true });
    }
    return out;
  };

  function median(values) {
    const s = values.slice().sort(function (a, b) { return a - b; });
    const mid = s.length >> 1;
    return s.length % 2 ? s[mid] : 0.5 * (s[mid - 1] + s[mid]);
  }

  const IDLE = { bpm: null, confidence: 0, collapse: 0, phase: 0, ready: false, seconds: 0 };

  /** Push PCM or spectrum frames; read snapshot() whenever the UI paints. */
  function BpmTracker(sr) {
    this.sr = sr || 48000;
    this.fps = ONSET_HZ;
    this.front = new OnsetFrontEnd(this.sr);
    this.specFront = new SpectrumFrontEnd();
    this.ring = new Float64Array(Math.round(WINDOW_S * this.fps));
    this.reset();
  }
  BpmTracker.prototype.reset = function () {
    this.front.reset();
    this.specFront.reset();
    this.ring.fill(0);
    this.n = 0;
    this.lastUpdate = 0;
    this.estimates = [];
    this.state = IDLE;
  };
  BpmTracker.prototype.pushPcm = function (samples, sr) {
    if (sr && sr !== this.front.sr) {
      this.front = new OnsetFrontEnd(sr);
      this.sr = sr;
    }
    this.pushOnsets(this.front.push(samples));
  };
  BpmTracker.prototype.pushSpectrum = function (t, db, binHz) {
    const cells = this.specFront.push(t, db, binHz);
    const size = this.ring.length;
    let touched = false;
    for (let i = 0; i < cells.length; i++) {
      const c = cells[i];
      if (c.merge) {
        const idx = ((this.n - 1) % size + size) % size;
        if (this.n > 0 && c.value > this.ring[idx]) this.ring[idx] = c.value;
        continue;
      }
      this.ring[this.n % size] = c.value;
      this.n += 1;
      touched = true;
    }
    if (touched) this.maybeUpdate();
  };
  BpmTracker.prototype.pushOnsets = function (values) {
    const size = this.ring.length;
    for (let i = 0; i < values.length; i++) {
      this.ring[this.n % size] = values[i];
      this.n += 1;
    }
    if (values.length) this.maybeUpdate();
  };
  BpmTracker.prototype.maybeUpdate = function () {
    if (this.n - this.lastUpdate >= UPDATE_S * this.fps && this.n >= MIN_S * this.fps) {
      this.lastUpdate = this.n;
      this.update();
    }
  };
  BpmTracker.prototype.window = function () {
    const size = this.ring.length;
    const m = Math.min(this.n, size);
    const out = new Float64Array(m);
    for (let i = 0; i < m; i++) out[i] = this.ring[(this.n - m + i) % size];
    return out;
  };
  BpmTracker.prototype.update = function () {
    const est = estimateTempo(this.window(), this.fps);
    this.estimates.push(est);
    if (this.estimates.length > MEDIAN_N) this.estimates.shift();
    const ready = this.estimates.filter(function (e) { return e.ready; }).map(function (e) { return e.bpm; });
    this.state = {
      bpm: ready.length ? median(ready) : null,
      confidence: est.confidence,
      collapse: est.collapse,
      phase: est.phase,
      ready: est.ready && ready.length > 0,
      seconds: this.n / this.fps
    };
  };
  BpmTracker.prototype.snapshot = function () {
    return this.state;
  };

  /** ♩ — (idle) · ♩ … (settling) · ♩ 140 (locked). */
  function bpmText(state, active) {
    if (active === false) return "♩ —";
    if (!state || !state.ready || state.bpm == null) return "♩ …";
    return "♩ " + Math.round(state.bpm);
  }

  /** Deterministic test signal — same recipe as bpm_tracker.synth_beat:
      a 909-style kick every beat (160→50 Hz sweep with a click), hats on the off-beats, a pad. */
  function synthBeat(sr, seconds, bpm, opts) {
    opts = opts || {};
    const hats = opts.hats !== false;
    const pad = opts.pad !== false;
    const n = Math.floor(sr * seconds);
    const out = new Float64Array(n);
    const beat = 60 / bpm;
    function burst(t0, length, decay, amp, freqs) {
      const i0 = Math.round(t0 * sr);
      const i1 = Math.min(n, i0 + Math.floor(length * sr));
      for (let i = i0; i < i1; i++) {
        const t = (i - i0) / sr;
        let sig = 0;
        for (let f = 0; f < freqs.length; f++) sig += freqs[f][1] * Math.sin(2 * Math.PI * freqs[f][0] * t);
        out[i] += amp * Math.exp(-t / decay) * sig;
      }
    }
    function kick(t0) {
      const i0 = Math.round(t0 * sr);
      const i1 = Math.min(n, i0 + Math.floor(0.25 * sr));
      let phase = 0;
      for (let i = i0; i < i1; i++) {
        const t = (i - i0) / sr;
        const freq = 50 + 110 * Math.exp(-t / 0.04);
        phase += 2 * Math.PI * freq / sr;
        const body = Math.sin(phase) * Math.exp(-t / 0.09);
        const click = Math.exp(-t / 0.003) * (Math.sin(2 * Math.PI * 1800 * t) + 0.6 * Math.sin(2 * Math.PI * 4100 * t));
        out[i] += 0.8 * body + 0.25 * click;
      }
    }
    for (let t0 = 0; t0 < seconds; t0 += beat) {
      kick(t0);
      if (hats) burst(t0 + beat / 2, 0.06, 0.02, 0.12, [[6000, 1], [9300, 0.7]]);
    }
    if (pad) for (let i = 0; i < n; i++) out[i] += 0.1 * Math.sin(2 * Math.PI * 220 * i / sr);
    let peak = 0;
    for (let i = 0; i < n; i++) if (Math.abs(out[i]) > peak) peak = Math.abs(out[i]);
    const g = 0.9 / (peak || 1);
    for (let i = 0; i < n; i++) out[i] *= g;
    return out;
  }

  function trackArray(audio, sr, chunk) {
    chunk = chunk || 4800;
    const tr = new BpmTracker(sr);
    for (let i = 0; i < audio.length; i += chunk) tr.pushPcm(audio.subarray(i, Math.min(audio.length, i + chunk)));
    return tr.snapshot();
  }

  /** Blackman-window float-dB spectrum of the last fftSize samples (AnalyserNode stand-in). */
  function specDbOf(samples, off, fftSize) {
    const re = new Float64Array(fftSize);
    const im = new Float64Array(fftSize);
    let wsum = 0;
    for (let i = 0; i < fftSize; i++) {
      const w = 0.42 - 0.5 * Math.cos((2 * Math.PI * i) / (fftSize - 1)) + 0.08 * Math.cos((4 * Math.PI * i) / (fftSize - 1));
      wsum += w;
      re[i] = (samples[off + i] || 0) * w;
    }
    fftRadix2(re, im);
    const bins = fftSize / 2;
    const db = new Float32Array(bins);
    for (let i = 0; i < bins; i++) {
      const mag = Math.sqrt(re[i] * re[i] + im[i] * im[i]) * 2 / wsum;
      db[i] = Math.max(-95, Math.min(0, 20 * Math.log10(mag + 1e-12)));
    }
    return db;
  }

  function selfTest() {
    function expect(name, state, want, tol, minConf) {
      if (!state.ready || state.bpm == null) throw new Error(name + ": tracker never locked " + JSON.stringify(state));
      if (Math.abs(state.bpm - want) > tol) throw new Error(name + ": " + state.bpm.toFixed(2) + " BPM, wanted " + want + " ± " + tol);
      if (state.confidence < minConf) throw new Error(name + ": confidence " + state.confidence.toFixed(2) + " < " + minConf);
    }
    const env = new Float64Array(800);
    for (let i = 0; i < 800; i += 50) env[i] = 1;
    const est = estimateTempo(env, ONSET_HZ);
    if (!est.ready || Math.abs(est.bpm - 120) > 0.5 || est.collapse < 0.85) {
      throw new Error("impulse envelope should read 120 BPM with a collapsed fold, got " + JSON.stringify(est));
    }
    if (estimateTempo(new Float64Array(800), ONSET_HZ).ready) throw new Error("flat envelope must not be ready");

    const sr = 48000;
    expect("140 BPM kick+hats+pad", trackArray(synthBeat(sr, 10, 140), sr), 140, 1.5, 0.25);
    expect("90 BPM kicks only", trackArray(synthBeat(sr, 12, 90, { hats: false }), sr), 90, 1.5, 0.25);
    expect("172 BPM kick+hats", trackArray(synthBeat(sr, 10, 172), sr), 172, 2, 0.2);
    expect("44.1 kHz 128 BPM", trackArray(synthBeat(44100, 10, 128), 44100), 128, 1.5, 0.25);
    expect("64 BPM", trackArray(synthBeat(sr, 12, 64), sr), 64, 1.5, 0.25);
    expect("138 BPM", trackArray(synthBeat(sr, 10, 138), sr), 138, 1.5, 0.25);
    expect("198 BPM", trackArray(synthBeat(sr, 10, 198), sr), 198, 2, 0.25);

    const tone = new Float64Array(sr * 6);
    for (let i = 0; i < tone.length; i++) tone[i] = 0.3 * Math.sin(2 * Math.PI * 220 * i / sr);
    if (trackArray(tone, sr).ready) throw new Error("a steady 220 Hz tone must not lock a tempo");
    const chord = new Float64Array(sr * 6);
    for (let i = 0; i < chord.length; i++) {
      const t = i / sr;
      chord[i] = 0.2 * (Math.sin(2 * Math.PI * 130.8 * t) + Math.sin(2 * Math.PI * 155.6 * t) + Math.sin(2 * Math.PI * 196 * t));
    }
    if (trackArray(chord, sr).ready) throw new Error("a held chord must not lock a tempo");
    if (trackArray(new Float64Array(sr * 5), sr).ready) throw new Error("silence must not lock a tempo");

    // AnalyserNode path: 2048-pt Blackman dB frames every 1/60 s with audio-clock stamps.
    const beat = synthBeat(sr, 10, 140);
    const spec = new BpmTracker(sr);
    const fftSize = 2048;
    for (let t = fftSize / sr; t < 10; t += 1 / 60) {
      const off = Math.floor(t * sr) - fftSize;
      spec.pushSpectrum(t, specDbOf(beat, off, fftSize), sr / fftSize);
    }
    expect("AnalyserNode frames at 60 fps, 140 BPM", spec.snapshot(), 140, 2, 0.2);
    const specTone = new BpmTracker(sr);
    for (let t = fftSize / sr; t < 6; t += 1 / 60) {
      specTone.pushSpectrum(t, specDbOf(tone, Math.floor(t * sr) - fftSize, fftSize), sr / fftSize);
    }
    if (specTone.snapshot().ready) throw new Error("AnalyserNode path must not lock on a steady tone");

    const tr = new BpmTracker(sr);
    if (bpmText(tr.snapshot()) !== "♩ …" || bpmText(tr.snapshot(), false) !== "♩ —") throw new Error("bpmText idle/settling contract");
    tr.pushPcm(synthBeat(sr, 8, 140));
    if (bpmText(tr.snapshot()) !== "♩ 140") throw new Error("bpmText locked contract, got " + bpmText(tr.snapshot()));
    tr.reset();
    if (tr.snapshot().ready || tr.snapshot().seconds !== 0) throw new Error("reset must forget the previous song");
    return "bpm_tracker.js: 140 / 90 / 172 / 128 BPM locked, tones and silence stay quiet, AnalyserNode path OK";
  }

  global.BPM_TRACKER = {
    ONSET_HZ: ONSET_HZ,
    FRAME: FRAME,
    WINDOW_S: WINDOW_S,
    BPM_MIN: BPM_MIN,
    BPM_MAX: BPM_MAX,
    BpmTracker: BpmTracker,
    OnsetFrontEnd: OnsetFrontEnd,
    SpectrumFrontEnd: SpectrumFrontEnd,
    estimateTempo: estimateTempo,
    foldCollapse: foldCollapse,
    autocorrelation: autocorrelation,
    bandPlan: bandPlan,
    bandLogmag: bandLogmag,
    smooth3: smooth3,
    tempoPrior: tempoPrior,
    bpmText: bpmText,
    synthBeat: synthBeat,
    trackArray: trackArray,
    selfTest: selfTest
  };

  if (typeof process !== "undefined" && process.argv && /bpm_tracker\.js$/.test(String(process.argv[1] || ""))) {
    console.log(selfTest());
  }
})(typeof window !== "undefined" ? window : globalThis);
