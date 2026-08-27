/* Shared mix-peak + density cluster. Ports scripts/density_cluster.py
   and crayon_piano_lib.extract_cluster_peaks. Fixtures: piano/cluster_fixtures.json */
(function (global) {
  const MIXED_LO_HZ = 27.5;
  const MIXED_HI_HZ = 5000;

  function bandNoiseFloor(specArr, i0, i1) {
    const step = Math.max(1, Math.floor((i1 - i0) / 72));
    const samples = [];
    for (let i = i0; i <= i1; i += step) samples.push(specArr[i]);
    if (!samples.length) return -90;
    samples.sort(function (a, b) { return a - b; });
    return samples[Math.floor(samples.length * 0.5)];
  }

  function extractClusterPeaks(specArr, binHz) {
    const i0 = Math.max(2, Math.floor(MIXED_LO_HZ / binHz));
    const i1 = Math.min(specArr.length - 2, Math.ceil(MIXED_HI_HZ / binHz));
    const floor = bandNoiseFloor(specArr, i0, i1);
    const minDb = Math.max(-78, floor + 10);
    const peaks = [];
    for (let i = i0; i <= i1; i++) {
      const db = specArr[i];
      if (db < minDb) continue;
      if (db > specArr[i - 1] && db >= specArr[i + 1] && db > specArr[i - 2] && db >= specArr[i + 2]) {
        const denom = specArr[i - 1] - 2 * db + specArr[i + 1];
        const delta = denom ? 0.5 * (specArr[i - 1] - specArr[i + 1]) / denom : 0;
        const f = (i + delta) * binHz;
        if (f >= MIXED_LO_HZ && f <= MIXED_HI_HZ) {
          peaks.push({ f: f, db: db, logF: Math.log2(f) });
        }
      }
    }
    peaks.sort(function (a, b) { return b.db - a.db; });
    return peaks.slice(0, 512);
  }

  function centsAbs(a, b) {
    if (a <= 0 || b <= 0) return 1e9;
    return Math.abs(1200 * Math.log2(a / b));
  }

  function fillFundStats(g) {
    let w = 0;
    let fSum = 0;
    g.members.forEach(function (m) {
      const mag = Math.pow(10, m.db / 20);
      w += mag;
      fSum += m.f * mag;
    });
    g.centroid = fSum / (w || 1);
    g.harm = Math.min(1, (g.members.length - 1) / 5);
    g.logF = Math.log2(Math.max(g.f0, 1e-6));
    g.logC = Math.log2(Math.max(g.centroid, 1));
  }

  function refineFundF0(g) {
    const freqs = g.members.map(function (m) { return m.f; }).filter(function (f) { return f > 0; });
    if (!freqs.length) return;
    const cands = freqs.slice();
    freqs.forEach(function (f) { cands.push(f / 2); });
    let best = g.f0;
    let bestScore = -1e18;
    cands.forEach(function (cand) {
      if (cand < 20) return;
      let hits = 0;
      let oddHi = 0;
      let hasSelf = false;
      freqs.forEach(function (f) {
        const n = Math.round(f / cand);
        if (n >= 1 && n <= 16 && centsAbs(f, n * cand) < 35) {
          hits += 1;
          if (n === 1) hasSelf = true;
          if (n >= 3 && n % 2 === 1) oddHi += 1;
        }
      });
      if (hits < 2) return;
      if (!hasSelf && oddHi < 1) return;
      const score = hits * 1000 + oddHi * 10 - cand;
      if (score > bestScore) {
        bestScore = score;
        best = cand;
      }
    });
    g.f0 = best;
  }

  function mergeOctaveFunds(funds) {
    funds = funds.slice().sort(function (a, b) { return a.f0 - b.f0; });
    const used = {};
    const out = [];
    for (let i = 0; i < funds.length; i++) {
      if (used[i]) continue;
      const a = funds[i];
      for (let j = i + 1; j < funds.length; j++) {
        if (used[j]) continue;
        const b = funds[j];
        const n = a.f0 ? Math.round(b.f0 / a.f0) : 0;
        if (n < 1 || n > 8) continue;
        if (centsAbs(b.f0, n * a.f0) < 35) {
          a.members = a.members.concat(b.members);
          if (b.db > a.db) a.db = b.db;
          used[j] = true;
        }
      }
      fillFundStats(a);
      out.push(a);
    }
    return out;
  }

  function groupHarmonicFunds(peaks) {
    const funds = [];
    peaks.slice().sort(function (a, b) { return b.db - a.db; }).forEach(function (p) {
      let bestIdx = -1;
      let bestCents = 35;
      for (let k = 0; k < funds.length; k++) {
        const f0 = funds[k].f0;
        const n = Math.round(p.f / f0);
        if (n < 2 || n > 16) continue;
        const cents = centsAbs(p.f, n * f0);
        if (cents < bestCents) {
          bestCents = cents;
          bestIdx = k;
        }
      }
      if (bestIdx >= 0) {
        funds[bestIdx].members.push(p);
        if (p.db > funds[bestIdx].db) funds[bestIdx].db = p.db;
      } else {
        funds.push({ f0: p.f, db: p.db, members: [p] });
      }
    });
    funds.forEach(function (g) {
      refineFundF0(g);
      fillFundStats(g);
    });
    return mergeOctaveFunds(funds);
  }

  function heuristicLabel(f0, harm, centroid) {
    if (harm < 0.18 && f0 > 180) return "bruit";
    if (f0 < 90) return "grave";
    const voiceLike = f0 >= 85 && f0 <= 280 && harm >= 0.45
      && centroid != null && centroid >= 250 && centroid <= 1400 && centroid > f0 * 1.8;
    if (voiceLike) return "voix";
    if (f0 < 450) return "corps";
    if (harm >= 0.55) return "nylon";
    if (f0 > 1400) return "air";
    return "";
  }

  function featOf(g) {
    return [g.logF * 0.42, g.harm * 1.8, g.logC * 0.35];
  }

  function featDist(a, b) {
    let s = 0;
    for (let i = 0; i < a.length; i++) {
      const d = a[i] - b[i];
      s += d * d;
    }
    return Math.sqrt(s);
  }

  function fundsAsClusters(funds) {
    return funds
      .filter(function (g) { return g.db > -90; })
      .map(function (g) {
        return { f0: g.f0, db: g.db, harm: g.harm, n: g.members.length, centroid: g.centroid };
      })
      .sort(function (a, b) { return b.db - a.db; });
  }

  const DBSCAN_MIN_PTS = 3;
  const MIN_F0_CENTS = 70;

  function densityClusterFunds(funds) {
    if (!funds.length) return [];
    const pts = funds.map(function (g) {
      return { g: g, x: featOf(g) };
    });
    const gaps = [];
    for (let i = 0; i < pts.length; i++) {
      let best = 1e9;
      for (let j = 0; j < pts.length; j++) {
        if (i === j) continue;
        const d = featDist(pts[i].x, pts[j].x);
        if (d < best) best = d;
      }
      if (best < 1e9) gaps.push(best);
    }
    gaps.sort(function (a, b) { return a - b; });
    const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0.28;
    const eps = Math.max(0.28, Math.min(0.85, (medianGap * 0.9) || 0.28));
    const n = pts.length;
    const labels = new Array(n).fill(-1);
    function neighbors(i) {
      const out = [];
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        if (Math.abs(1200 * (pts[i].g.logF - pts[j].g.logF)) > MIN_F0_CENTS) continue;
        if (featDist(pts[i].x, pts[j].x) <= eps) out.push(j);
      }
      return out;
    }
    // neighbors exclude self; +1 counts the point. minPts=3 means a pair of
    // notes is not a core (avoids single-linkage A~B~C chains).
    const core = new Array(n).fill(false);
    for (let i = 0; i < n; i++) core[i] = neighbors(i).length + 1 >= DBSCAN_MIN_PTS;
    let cid = 0;
    for (let i = 0; i < n; i++) {
      if (labels[i] !== -1 || !core[i]) continue;
      labels[i] = cid;
      const seed = neighbors(i).slice();
      let s = 0;
      while (s < seed.length) {
        const j = seed[s++];
        if (labels[j] === -1) {
          labels[j] = cid;
          if (core[j]) {
            const nb2 = neighbors(j);
            for (let k = 0; k < nb2.length; k++) {
              if (seed.indexOf(nb2[k]) < 0) seed.push(nb2[k]);
            }
          }
        }
      }
      cid += 1;
    }
    for (let i = 0; i < n; i++) {
      if (labels[i] === -1) labels[i] = cid++;
    }
    const buckets = [];
    for (let i = 0; i < n; i++) {
      const id = labels[i];
      if (!buckets[id]) buckets[id] = [];
      buckets[id].push(pts[i].g);
    }
    const clusters = [];
    buckets.forEach(function (members) {
      if (!members || !members.length) return;
      members.sort(function (a, b) { return b.db - a.db; });
      const head = members[0];
      let db = -120;
      let harm = 0;
      members.forEach(function (g) {
        if (g.db > db) db = g.db;
        harm += g.harm;
      });
      clusters.push({
        f0: head.f0,
        db: db,
        harm: harm / members.length,
        centroid: head.centroid
      });
    });
    clusters.sort(function (a, b) { return b.db - a.db; });
    return clusters.filter(function (c) { return c.db > -90; });
  }

  function clusterPeaks(peaks, mergeNearby) {
    const funds = groupHarmonicFunds(peaks);
    if (mergeNearby === false) return fundsAsClusters(funds);
    return densityClusterFunds(funds);
  }

  function hzToMidiA4(freq, a4) {
    return 69 + 12 * Math.log2(Math.max(1e-6, freq) / (a4 || 440));
  }

  /**
   * Need-notes from a float-dB spectrum. Same gate as the HTML/iOS loop:
   * smooth 0.62/0.38, sensitivity 0.58, absGate = −48 − s·36, rel 10 + s·18.
   * `opts.smooth` is mutated so a caller can settle across frames.
   */
  function pickLitMidis(specArr, binHz, opts) {
    opts = opts || {};
    const midiLo = opts.midiLo != null ? opts.midiLo : 21;
    const midiHi = opts.midiHi != null ? opts.midiHi : 108;
    const a4 = opts.a4 || 440;
    const nKeys = midiHi - midiLo + 1;
    const smooth = opts.smooth || new Float32Array(nKeys);
    if (smooth.length !== nKeys) throw new Error("pickLitMidis: smooth length");
    if (!opts.smooth) {
      for (let z = 0; z < nKeys; z++) smooth[z] = -120;
    }
    const maxN = opts.maxN != null ? opts.maxN : 8;
    const sens = opts.sens != null ? opts.sens : 0.58;
    const inBand = opts.inBand || function () { return true; };
    const fold = !!opts.fold;
    const score = new Float32Array(nKeys);
    const scoreHz = new Float32Array(nKeys);
    score.fill(-120);
    const i0 = Math.max(2, Math.floor(MIXED_LO_HZ / binHz));
    const i1 = Math.min(specArr.length - 2, Math.ceil(MIXED_HI_HZ / binHz));
    const peaks = [];
    function midiFromHz(freq) {
      let m = hzToMidiA4(freq, a4);
      if (!isFinite(m)) return -1;
      if (fold) {
        while (m < midiLo) m += 12;
        while (m > midiHi) m -= 12;
      }
      return Math.round(m);
    }
    for (let i = i0; i <= i1; i++) {
      const freq = i * binHz;
      if (!inBand(freq)) continue;
      const db = specArr[i];
      if (db > specArr[i - 1] && db >= specArr[i + 1] && db > specArr[i - 2] && db >= specArr[i + 2]) {
        const denom = specArr[i - 1] - 2 * db + specArr[i + 1];
        const delta = denom ? 0.5 * (specArr[i - 1] - specArr[i + 1]) / denom : 0;
        const pf = (i + delta) * binHz;
        if (inBand(pf)) peaks.push({ freq: pf, db: db });
      }
      const midi = midiFromHz(freq);
      if (midi >= midiLo && midi <= midiHi) {
        const idx = midi - midiLo;
        if (db > score[idx]) {
          score[idx] = db;
          scoreHz[idx] = freq;
        }
      }
    }
    peaks.sort(function (a, b) { return b.db - a.db; });
    for (let p = 0; p < peaks.length; p++) {
      const midi = midiFromHz(peaks[p].freq);
      if (midi < midiLo || midi > midiHi) continue;
      const idx = midi - midiLo;
      if (peaks[p].db + 2 > score[idx]) {
        score[idx] = peaks[p].db + 2;
        scoreHz[idx] = peaks[p].freq;
      }
    }
    let loudest = -120;
    for (let i = 0; i < nKeys; i++) {
      smooth[i] = 0.62 * smooth[i] + 0.38 * score[i];
      if (smooth[i] > loudest) loudest = smooth[i];
    }
    const absGate = -48 - sens * 36;
    const relDb = 10 + sens * 18;
    const gate = Math.max(absGate, loudest - relDb);
    const candidates = [];
    for (let i = 0; i < nKeys; i++) {
      const s = smooth[i];
      if (s < gate) continue;
      const left = i > 0 ? smooth[i - 1] : -999;
      const right = i < nKeys - 1 ? smooth[i + 1] : -999;
      if (s >= left && s >= right) {
        candidates.push({
          midi: i + midiLo,
          s: s,
          freq: scoreHz[i] || 440 * Math.pow(2, (i + midiLo - 69) / 12)
        });
      }
    }
    candidates.sort(function (a, b) { return b.s - a.s; });
    const lit = candidates.slice(0, maxN);
    return { lit: lit, gate: gate, absGate: absGate, loudest: loudest, smooth: smooth };
  }

  function settleLitMidis(specArr, binHz, opts) {
    opts = opts || {};
    const midiLo = opts.midiLo != null ? opts.midiLo : 21;
    const midiHi = opts.midiHi != null ? opts.midiHi : 108;
    if (!opts.smooth) {
      opts.smooth = new Float32Array(midiHi - midiLo + 1);
      opts.smooth.fill(-120);
    }
    const frames = opts.frames != null ? opts.frames : 12;
    let out = null;
    for (let i = 0; i < frames; i++) out = pickLitMidis(specArr, binHz, opts);
    return out;
  }

  function selfTest(fixtures) {
    const cases = (fixtures && fixtures.cases) || [];
    if (!cases.length) throw new Error("crayon_dsp: missing fixtures");
    cases.forEach(function (c) {
      const got = clusterPeaks(c.peaks, c.merge_nearby !== false);
      if (got.length !== c.expect_n) {
        throw new Error(c.name + " expected " + c.expect_n + " got " + got.length);
      }
      (c.expect_f0 || []).forEach(function (want, i) {
        if (Math.abs(got[i].f0 - want) > 1.0) {
          throw new Error(c.name + " f0[" + i + "] " + got[i].f0 + " != " + want);
        }
      });
    });
    const sr = 48000;
    const fftSize = 8192;
    const binHz = sr / fftSize;
    const spec = new Float32Array(fftSize / 2 + 1);
    spec.fill(-120);
    const k = Math.round(440 / binHz);
    spec[k - 2] = -28;
    spec[k - 1] = -14;
    spec[k] = -4;
    spec[k + 1] = -14;
    spec[k + 2] = -28;
    const lit = settleLitMidis(spec, binHz);
    const midis = lit.lit.map(function (c) { return c.midi; });
    if (midis.indexOf(69) < 0) {
      throw new Error("pickLitMidis should light A4 (69), got " + midis.join(","));
    }
    return "crayon_dsp.js: " + cases.length + " fixtures OK, pickLitMidis A4";
  }

  global.CRAYON_DSP = {
    MIXED_LO_HZ: MIXED_LO_HZ,
    MIXED_HI_HZ: MIXED_HI_HZ,
    bandNoiseFloor: bandNoiseFloor,
    extractClusterPeaks: extractClusterPeaks,
    groupHarmonicFunds: groupHarmonicFunds,
    densityClusterFunds: densityClusterFunds,
    clusterPeaks: clusterPeaks,
    pickLitMidis: pickLitMidis,
    settleLitMidis: settleLitMidis,
    heuristicLabel: heuristicLabel,
    selfTest: selfTest
  };

  if (typeof process !== "undefined" && process.argv && /crayon_dsp\.js$/.test(String(process.argv[1] || ""))) {
    const fs = require("fs");
    const path = require("path");
    const fixPath = path.join(__dirname, "..", "piano", "cluster_fixtures.json");
    const fixtures = JSON.parse(fs.readFileSync(fixPath, "utf8"));
    console.log(selfTest(fixtures));
  }
})(typeof window !== "undefined" ? window : globalThis);
