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

  function groupHarmonicFunds(peaks) {
    const funds = [];
    peaks.forEach(function (p) {
      let bestIdx = -1;
      let bestCents = 35;
      for (let k = 0; k < funds.length; k++) {
        const f0 = funds[k].f0;
        const n = Math.round(p.f / f0);
        if (n < 2 || n > 16) continue;
        const cents = Math.abs(1200 * Math.log2(p.f / (n * f0)));
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
      let w = 0;
      let fSum = 0;
      g.members.forEach(function (m) {
        const mag = Math.pow(10, m.db / 20);
        w += mag;
        fSum += m.f * mag;
      });
      g.centroid = fSum / (w || 1);
      g.harm = Math.min(1, (g.members.length - 1) / 5);
      g.logF = Math.log2(g.f0);
      g.logC = Math.log2(Math.max(g.centroid, 1));
    });
    return funds;
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
        if (featDist(pts[i].x, pts[j].x) <= eps) out.push(j);
      }
      return out;
    }
    const core = new Array(n).fill(false);
    for (let i = 0; i < n; i++) core[i] = neighbors(i).length + 1 >= 2;
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
    return "crayon_dsp.js: " + cases.length + " fixtures OK";
  }

  global.CRAYON_DSP = {
    MIXED_LO_HZ: MIXED_LO_HZ,
    MIXED_HI_HZ: MIXED_HI_HZ,
    bandNoiseFloor: bandNoiseFloor,
    extractClusterPeaks: extractClusterPeaks,
    groupHarmonicFunds: groupHarmonicFunds,
    densityClusterFunds: densityClusterFunds,
    clusterPeaks: clusterPeaks,
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
