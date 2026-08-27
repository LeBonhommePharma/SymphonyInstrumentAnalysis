/* Now-playing / tab-audio capture for Piano-crayon.
   Chrome can share a tab with audio via getDisplayMedia. Safari (macOS and
   iOS) and Firefox do not deliver an audio track — do not pretend they do.
   Captured audio is tapped into an AnalyserNode only; never the speakers. */
(function (global) {
  "use strict";

  function navOf(nav) {
    return nav || (typeof navigator !== "undefined" ? navigator : {});
  }

  function locOf(loc) {
    return loc || (typeof location !== "undefined" ? location : {});
  }

  function isIOS(nav) {
    nav = navOf(nav);
    const ua = nav.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) ||
      (nav.platform === "MacIntel" && (nav.maxTouchPoints || 0) > 1);
  }

  function isAppleWebKit(nav) {
    nav = navOf(nav);
    const ua = nav.userAgent || "";
    const vendor = nav.vendor || "";
    return /Safari/i.test(ua) && /Apple/i.test(vendor) &&
      !/Chrom(e|ium)|Edg|OPR|Firefox|CriOS|FxiOS|EdgiOS|Android/i.test(ua);
  }

  function isFirefox(nav) {
    const ua = navOf(nav).userAgent || "";
    return /Firefox\//.test(ua) && !/Seamonkey/i.test(ua);
  }

  function isChromium(nav) {
    const ua = navOf(nav).userAgent || "";
    return /Chrom(e|ium)|Edg|OPR/.test(ua) && !isAppleWebKit(nav);
  }

  function canCaptureNowPlaying(nav, loc, mediaDevices) {
    nav = navOf(nav);
    loc = locOf(loc);
    if (isIOS(nav) || isAppleWebKit(nav) || isFirefox(nav)) return false;
    const md = mediaDevices || nav.mediaDevices;
    if (!md || typeof md.getDisplayMedia !== "function") return false;
    if (loc.protocol === "file:") return false;
    return true;
  }

  function nowPlayingUnsupportedReason(nav, loc) {
    nav = navOf(nav);
    loc = locOf(loc);
    if (isIOS(nav)) {
      return "iPhone / iPad : Safari ne capte pas l’audio en cours. Écouter = micro (joue à voix haute), ou Chrome sur un ordinateur.";
    }
    if (isAppleWebKit(nav)) {
      return "Safari ne capte pas l’audio de l’onglet ni du système. Ouvre Chrome, clique En cours, partage l’onglet de la chanson (coche « Partager l’audio »). Ou Micro → loopback (BlackHole) puis Écouter.";
    }
    if (isFirefox(nav)) {
      return "Firefox ne livre pas l’audio d’onglet. Ouvre Chrome pour En cours, ou Écouter via un micro loopback.";
    }
    if (loc.protocol === "file:") {
      return "Chrome bloque le partage d’onglet en file://. Sers la page : python3 -m http.server 4173 --directory web";
    }
    return "Ce navigateur ne sait pas suivre l’audio en cours. Chrome (partage d’onglet) ou un micro loopback + Écouter.";
  }

  const AUDIO_EXTRAS = {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
    suppressLocalAudioPlayback: true,
    systemAudio: "include"
  };

  function displayAudioConstraints() {
    return {
      audio: Object.assign({}, AUDIO_EXTRAS),
      video: true
    };
  }

  function audioOnlyStream(mediaStream) {
    if (!mediaStream) throw new Error("Pas d’audio partagé");
    const audioTracks = mediaStream.getAudioTracks ? mediaStream.getAudioTracks() : [];
    if (mediaStream.getVideoTracks) {
      mediaStream.getVideoTracks().forEach(function (t) {
        try { t.stop(); } catch (_) { /* already gone */ }
      });
    }
    if (!audioTracks.length) {
      if (mediaStream.getTracks) {
        mediaStream.getTracks().forEach(function (t) {
          try { t.stop(); } catch (_) { /* already gone */ }
        });
      }
      throw new Error("Pas d’audio partagé. Dans Chrome, choisis l’onglet de la chanson et coche « Partager l’audio de l’onglet ».");
    }
    return typeof MediaStream === "function" ? new MediaStream(audioTracks) : { getAudioTracks: function () { return audioTracks; }, getVideoTracks: function () { return []; }, getTracks: function () { return audioTracks; } };
  }

  async function requestDisplayAudio(mediaDevices) {
    const md = mediaDevices || (typeof navigator !== "undefined" && navigator.mediaDevices);
    if (!md || typeof md.getDisplayMedia !== "function") {
      const err = new Error("getDisplayMedia indisponible");
      err.name = "NotSupportedError";
      throw err;
    }
    let mediaStream = null;
    try {
      mediaStream = await md.getDisplayMedia(displayAudioConstraints());
    } catch (firstErr) {
      try {
        mediaStream = await md.getDisplayMedia({
          audio: true,
          video: true
        });
      } catch (_) {
        try {
          mediaStream = await md.getDisplayMedia({
            audio: Object.assign({}, AUDIO_EXTRAS),
            video: false
          });
        } catch (__) {
          throw firstErr;
        }
      }
    }
    return audioOnlyStream(mediaStream);
  }

  /**
   * Tap a MediaStream into analyser only. Never connect to destination —
   * LP already hears the song in headphones; echoing it would double it.
   */
  function tapSilentStream(audioCtx, analyser, stream) {
    if (!audioCtx || !analyser || !stream) throw new Error("tapSilentStream: missing graph");
    const source = audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);
    return source;
  }

  /**
   * Tap an AudioBuffer into analyser only (self-test / synthetic playback).
   * Looping BufferSource → analyser, no destination.
   */
  function tapSilentBuffer(audioCtx, analyser, buffer) {
    if (!audioCtx || !analyser || !buffer) throw new Error("tapSilentBuffer: missing graph");
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(analyser);
    if (typeof source.start === "function") source.start();
    return source;
  }

  /**
   * Build a MediaStream from an AudioBuffer via MediaStreamDestination.
   * The destination node is NOT the speakers.
   */
  function streamFromBuffer(audioCtx, buffer) {
    if (!audioCtx.createMediaStreamDestination) {
      throw new Error("MediaStreamDestination indisponible");
    }
    const dest = audioCtx.createMediaStreamDestination();
    const src = audioCtx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    src.connect(dest);
    if (typeof src.start === "function") src.start();
    return { stream: dest.stream, source: src, dest: dest };
  }

  function makeToneBuffer(audioCtx, hz, seconds) {
    const sr = audioCtx.sampleRate || 48000;
    const n = Math.max(64, Math.floor(sr * (seconds || 1)));
    const buf = audioCtx.createBuffer(1, n, sr);
    const data = buf.getChannelData(0);
    const twoPi = 2 * Math.PI;
    for (let i = 0; i < n; i++) data[i] = 0.55 * Math.sin(twoPi * hz * i / sr);
    return buf;
  }

  function highlightOf(midi, needed, held) {
    const want = needed && (needed.has ? needed.has(midi) : needed.indexOf(midi) >= 0);
    const have = held && (held.has ? held.has(midi) : held.indexOf(midi) >= 0);
    if (want && have) return "hit";
    if (want) return "need";
    if (have) return "held";
    return "";
  }

  const MELODY_LO_HZ = 196;
  const MELODY_HI_HZ = 2093;

  function pickMelodyCluster(tracks) {
    if (!tracks || !tracks.length) return null;
    const pitched = tracks.filter(function (t) { return t && t.f0 > 0 && !t.spatial; });
    const pool0 = pitched.length ? pitched : tracks.slice();
    const inRange = pool0.filter(function (t) {
      return t.f0 >= MELODY_LO_HZ && t.f0 <= MELODY_HI_HZ;
    });
    let pool = inRange.length ? inRange : pool0.filter(function (t) { return t.f0 >= 90; });
    if (!pool.length) pool = pool0;
    pool.sort(function (a, b) {
      const ea = a.energy || 0;
      const eb = b.energy || 0;
      if (eb !== ea) return eb - ea;
      return (b.f0 || 0) - (a.f0 || 0);
    });
    return pool[0] || null;
  }

  function blackman(n) {
    const w = new Float64Array(n);
    const nm1 = n - 1 || 1;
    for (let i = 0; i < n; i++) {
      w[i] = 0.42 - 0.5 * Math.cos((2 * Math.PI * i) / nm1) + 0.08 * Math.cos((4 * Math.PI * i) / nm1);
    }
    return w;
  }

  function fftRadix2(re, im) {
    const n = re.length;
    let j = 0;
    for (let i = 0; i < n; i++) {
      if (i < j) {
        let tr = re[i]; re[i] = re[j]; re[j] = tr;
        tr = im[i]; im[i] = im[j]; im[j] = tr;
      }
      let m = n >> 1;
      while (m >= 1 && j >= m) {
        j -= m;
        m >>= 1;
      }
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

  /** PCM AudioBuffer channel → float dBFS spectrum (Blackman, coherent gain). */
  function bufferToSpecDb(samples, sr, fftSize) {
    fftSize = fftSize || 8192;
    const n = fftSize;
    const re = new Float64Array(n);
    const im = new Float64Array(n);
    const win = blackman(n);
    let winSum = 0;
    const take = Math.min(samples.length, n);
    const off = samples.length >= n ? samples.length - n : 0;
    for (let i = 0; i < take; i++) {
      const w = win[n - take + i] || win[i];
      re[n - take + i] = samples[off + i] * w;
      winSum += w;
    }
    if (samples.length < n) {
      winSum = 0;
      for (let i = 0; i < n; i++) winSum += win[i];
    } else {
      winSum = 0;
      for (let i = 0; i < n; i++) winSum += win[i];
    }
    fftRadix2(re, im);
    const bins = n / 2 + 1;
    const db = new Float32Array(bins);
    const scale = 2 / (winSum || 1);
    for (let i = 0; i < bins; i++) {
      const mag = Math.sqrt(re[i] * re[i] + im[i] * im[i]) * scale;
      let v = 20 * Math.log10(mag + 1e-12);
      if (v > 0) v = 0;
      if (v < -95) v = -95;
      db[i] = v;
    }
    db[0] = Math.max(-95, 20 * Math.log10(Math.abs(re[0]) / (winSum || 1) + 1e-12));
    return { spec: db, binHz: sr / n };
  }

  function makeTonePcm(hz, sr, n) {
    const x = new Float32Array(n);
    const twoPi = 2 * Math.PI;
    for (let i = 0; i < n; i++) x[i] = Math.sin(twoPi * hz * i / sr);
    return x;
  }

  function mockGraph() {
    const edges = [];
    function node(name) {
      return {
        name: name,
        connect: function (other) {
          edges.push([name, other && other.name ? other.name : "anon"]);
        },
        disconnect: function () {},
        start: function () {},
        stop: function () {},
        buffer: null,
        loop: false
      };
    }
    const destination = node("destination");
    const analyser = node("analyser");
    return {
      edges: edges,
      destination: destination,
      analyser: analyser,
      sampleRate: 48000,
      createMediaStreamSource: function () { return node("streamSource"); },
      createBufferSource: function () { return node("bufferSource"); }
    };
  }

  function selfTest() {
    const safari = {
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
      vendor: "Apple Computer, Inc.",
      platform: "MacIntel",
      maxTouchPoints: 0,
      mediaDevices: { getDisplayMedia: function () {} }
    };
    const chrome = {
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
      vendor: "Google Inc.",
      platform: "MacIntel",
      mediaDevices: { getDisplayMedia: function () {} }
    };
    const ios = {
      userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      vendor: "Apple Computer, Inc.",
      platform: "iPhone",
      mediaDevices: {}
    };
    if (canCaptureNowPlaying(safari, { protocol: "https:" })) {
      throw new Error("Safari must not claim now-playing capture");
    }
    if (!/Safari ne capte pas/.test(nowPlayingUnsupportedReason(safari, { protocol: "https:" }))) {
      throw new Error("Safari reason must be honest");
    }
    if (canCaptureNowPlaying(ios, { protocol: "https:" })) {
      throw new Error("iOS must not claim now-playing capture");
    }
    if (!canCaptureNowPlaying(chrome, { protocol: "https:" })) {
      throw new Error("Chrome https should allow now-playing");
    }
    if (canCaptureNowPlaying(chrome, { protocol: "file:" })) {
      throw new Error("file:// must not claim tab capture");
    }

    const g = mockGraph();
    tapSilentStream(g, g.analyser, { getAudioTracks: function () { return [{ stop: function () {} }]; } });
    if (g.edges.some(function (e) { return e[1] === "destination"; })) {
      throw new Error("now-playing tap must not connect to speakers");
    }
    if (!g.edges.some(function (e) { return e[0] === "streamSource" && e[1] === "analyser"; })) {
      throw new Error("now-playing tap must connect the stream to the analyser");
    }
    const g2 = mockGraph();
    tapSilentBuffer(g2, g2.analyser, { duration: 1 });
    if (g2.edges.some(function (e) { return e[1] === "destination"; })) {
      throw new Error("silent buffer tap must not connect to speakers");
    }

    if (highlightOf(69, [69], []) !== "need") throw new Error("need contract");
    if (highlightOf(69, [69], [69]) !== "hit") throw new Error("hit contract");
    if (highlightOf(60, [69], [60]) !== "held") throw new Error("held contract");
    if (highlightOf(62, [69], [60]) !== "") throw new Error("idle contract");

    const melody = pickMelodyCluster([
      { id: 1, f0: 55, energy: 0.9 },
      { id: 2, f0: 440, energy: 0.5 },
      { id: 3, f0: 2100, energy: 0.8 }
    ]);
    if (!melody || melody.id !== 2) throw new Error("melody cluster should prefer A4 over bass/air");

    const dsp = global.CRAYON_DSP;
    if (!dsp || typeof dsp.settleLitMidis !== "function") {
      throw new Error("now_playing self-test needs CRAYON_DSP.settleLitMidis");
    }
    const sr = 48000;
    const fftSize = 8192;
    const pcm = makeTonePcm(440, sr, fftSize);
    const conv = bufferToSpecDb(pcm, sr, fftSize);
    const settled = dsp.settleLitMidis(conv.spec, conv.binHz, { frames: 16, maxN: 8 });
    const midis = settled.lit.map(function (c) { return c.midi; });
    if (midis.indexOf(69) < 0) {
      throw new Error("AudioBuffer 440 Hz must light A4 need, got " + JSON.stringify(settled.lit));
    }
    const needed = midis;
    if (highlightOf(69, needed, [69]) !== "hit") {
      throw new Error("need/hit contract after analyser path");
    }

    const empty = audioOnlyStream({
      getAudioTracks: function () { return [{ id: "a", stop: function () {} }]; },
      getVideoTracks: function () { return [{ stop: function () { this.stopped = true; } }]; },
      getTracks: function () { return this.getAudioTracks().concat(this.getVideoTracks()); }
    });
    if (!empty.getAudioTracks || empty.getAudioTracks().length !== 1) {
      throw new Error("audioOnlyStream must keep the audio track");
    }

    const cons = displayAudioConstraints();
    if (!cons.audio || cons.audio.suppressLocalAudioPlayback !== true) {
      throw new Error("captured tab audio must not play locally");
    }
    if (cons.audio.systemAudio !== "include") {
      throw new Error("ask Chrome for systemAudio when the OS offers it");
    }

    return "now_playing.js: Safari honest, silent tap, A4 need/hit OK";
  }

  global.NOW_PLAYING = {
    isIOS: isIOS,
    isAppleWebKit: isAppleWebKit,
    isFirefox: isFirefox,
    isChromium: isChromium,
    canCaptureNowPlaying: canCaptureNowPlaying,
    nowPlayingUnsupportedReason: nowPlayingUnsupportedReason,
    displayAudioConstraints: displayAudioConstraints,
    audioOnlyStream: audioOnlyStream,
    requestDisplayAudio: requestDisplayAudio,
    tapSilentStream: tapSilentStream,
    tapSilentBuffer: tapSilentBuffer,
    streamFromBuffer: streamFromBuffer,
    makeToneBuffer: makeToneBuffer,
    makeTonePcm: makeTonePcm,
    bufferToSpecDb: bufferToSpecDb,
    highlightOf: highlightOf,
    pickMelodyCluster: pickMelodyCluster,
    MELODY_LO_HZ: MELODY_LO_HZ,
    MELODY_HI_HZ: MELODY_HI_HZ,
    selfTest: selfTest
  };

  if (typeof process !== "undefined" && process.argv && /now_playing\.js$/.test(String(process.argv[1] || ""))) {
    if (typeof global.CRAYON_DSP === "undefined") {
      require("./crayon_dsp.js");
    }
    console.log(selfTest());
  }
})(typeof window !== "undefined" ? window : globalThis);
