/* US ANSI + Canadian French CSA. Geometry, glyph tables and the finger gate
   mirror scripts/dual_keyboard.py; the octave shift and the live glyph layer
   below are web-only and have no Python counterpart.
   Character keys are bound to crayon notes (KeyZ = Do3, KeyD = Do4, KeyQ = La4).
   10 fingers max unless the extra key is well clustered.

   INPUT IS LAYOUT-INDEPENDENT. Notes are keyed on `KeyboardEvent.code`, the
   physical key position, which does not change when the OS keyboard layout
   changes. Verified on macOS 27 by sending the same virtual keycodes through
   both the U.S. and the Canadian-CSA input sources: `code` was identical for
   every key, `key` changed on 6 of 9 (VK 50 -> Backquote/`` ` `` vs
   Backquote/ù; VK 44 -> Slash/'/' vs Slash/'é', and so on). So both boards are
   live at the same time and there is nothing to detect for input purposes —
   `keyByCodeAny` resolves against the union of the layouts.

   THE PICKER IS A LABELLING CHOICE ONLY. It decides which glyphs are painted
   on the caps; it must never decide which keys produce notes.

   GLYPH TABLES BELOW ARE THE PC/ISO CONVENTION AND ARE WRONG ON APPLE ISO
   HARDWARE for exactly two keys. Read from macOS's own Canadian-CSA layout via
   UCKeyTranslate: virtual keycode 50 (-> code `Backquote`) produces "ù", and
   virtual keycode 10 / kVK_ISO_Section (-> code `IntlBackslash`) produces
   "/" "\" "|". The table below has those two the other way round, because
   Apple ISO boards put `Backquote` left of Z and `IntlBackslash` left of
   Digit1, the reverse of a PC ISO board. Rather than fork the table per
   platform, the live glyph layer (`loadLayoutMap` / `observeGlyph`) overrides
   it at runtime with the browser's own values. */
(function (global) {
  const MAX_FINGERS = 10;
  const CLUSTER_EPS = 1.2;
  const BOARD_GAP = 18;

  function spec(kid, row, col, w, extra) {
    const e = extra || {};
    return {
      kid: kid,
      row: row,
      col: col,
      w: w == null ? 1 : w,
      h: e.h || 1,
      kind: e.kind || "char",
      base: e.base || "",
      shift: e.shift || "",
      altgr: e.altgr || "",
      dead: e.dead || "",
      shiftDead: e.shiftDead || "",
      code: e.code || kid
    };
  }

  function usAnsi() {
    return {
      id: "us",
      name: "US",
      nameFr: "É.-U.",
      geometry: "ansi",
      x0: 0,
      keys: [
        spec("Backquote", 0, 0, 1, { base: "`", shift: "~" }),
        spec("Digit1", 0, 1, 1, { base: "1", shift: "!" }),
        spec("Digit2", 0, 2, 1, { base: "2", shift: "@" }),
        spec("Digit3", 0, 3, 1, { base: "3", shift: "#" }),
        spec("Digit4", 0, 4, 1, { base: "4", shift: "$" }),
        spec("Digit5", 0, 5, 1, { base: "5", shift: "%" }),
        spec("Digit6", 0, 6, 1, { base: "6", shift: "^" }),
        spec("Digit7", 0, 7, 1, { base: "7", shift: "&" }),
        spec("Digit8", 0, 8, 1, { base: "8", shift: "*" }),
        spec("Digit9", 0, 9, 1, { base: "9", shift: "(" }),
        spec("Digit0", 0, 10, 1, { base: "0", shift: ")" }),
        spec("Minus", 0, 11, 1, { base: "-", shift: "_" }),
        spec("Equal", 0, 12, 1, { base: "=", shift: "+" }),
        spec("Backspace", 0, 13, 2, { kind: "backspace", base: "⌫" }),
        spec("Tab", 1, 0, 1.5, { kind: "tab", base: "⇥" }),
        spec("KeyQ", 1, 1.5, 1, { base: "q", shift: "Q" }),
        spec("KeyW", 1, 2.5, 1, { base: "w", shift: "W" }),
        spec("KeyE", 1, 3.5, 1, { base: "e", shift: "E" }),
        spec("KeyR", 1, 4.5, 1, { base: "r", shift: "R" }),
        spec("KeyT", 1, 5.5, 1, { base: "t", shift: "T" }),
        spec("KeyY", 1, 6.5, 1, { base: "y", shift: "Y" }),
        spec("KeyU", 1, 7.5, 1, { base: "u", shift: "U" }),
        spec("KeyI", 1, 8.5, 1, { base: "i", shift: "I" }),
        spec("KeyO", 1, 9.5, 1, { base: "o", shift: "O" }),
        spec("KeyP", 1, 10.5, 1, { base: "p", shift: "P" }),
        spec("BracketLeft", 1, 11.5, 1, { base: "[", shift: "{" }),
        spec("BracketRight", 1, 12.5, 1, { base: "]", shift: "}" }),
        spec("Backslash", 1, 13.5, 1.5, { base: "\\", shift: "|" }),
        spec("CapsLock", 2, 0, 1.75, { kind: "caps", base: "⇪" }),
        spec("KeyA", 2, 1.75, 1, { base: "a", shift: "A" }),
        spec("KeyS", 2, 2.75, 1, { base: "s", shift: "S" }),
        spec("KeyD", 2, 3.75, 1, { base: "d", shift: "D" }),
        spec("KeyF", 2, 4.75, 1, { base: "f", shift: "F" }),
        spec("KeyG", 2, 5.75, 1, { base: "g", shift: "G" }),
        spec("KeyH", 2, 6.75, 1, { base: "h", shift: "H" }),
        spec("KeyJ", 2, 7.75, 1, { base: "j", shift: "J" }),
        spec("KeyK", 2, 8.75, 1, { base: "k", shift: "K" }),
        spec("KeyL", 2, 9.75, 1, { base: "l", shift: "L" }),
        spec("Semicolon", 2, 10.75, 1, { base: ";", shift: ":" }),
        spec("Quote", 2, 11.75, 1, { base: "'", shift: "\"" }),
        spec("Enter", 2, 12.75, 2.25, { kind: "enter", base: "⏎" }),
        spec("ShiftLeft", 3, 0, 2.25, { kind: "shift", base: "⇧" }),
        spec("KeyZ", 3, 2.25, 1, { base: "z", shift: "Z" }),
        spec("KeyX", 3, 3.25, 1, { base: "x", shift: "X" }),
        spec("KeyC", 3, 4.25, 1, { base: "c", shift: "C" }),
        spec("KeyV", 3, 5.25, 1, { base: "v", shift: "V" }),
        spec("KeyB", 3, 6.25, 1, { base: "b", shift: "B" }),
        spec("KeyN", 3, 7.25, 1, { base: "n", shift: "N" }),
        spec("KeyM", 3, 8.25, 1, { base: "m", shift: "M" }),
        spec("Comma", 3, 9.25, 1, { base: ",", shift: "<" }),
        spec("Period", 3, 10.25, 1, { base: ".", shift: ">" }),
        spec("Slash", 3, 11.25, 1, { base: "/", shift: "?" }),
        spec("ShiftRight", 3, 12.25, 2.75, { kind: "shift", base: "⇧" }),
        spec("ControlLeft", 4, 0, 1.5, { kind: "ctrl", base: "ctrl" }),
        spec("AltLeft", 4, 1.5, 1.5, { kind: "alt", base: "alt" }),
        spec("Space", 4, 3, 9, { kind: "space", base: " " }),
        spec("AltRight", 4, 12, 1.5, { kind: "alt", base: "alt" }),
        spec("ControlRight", 4, 13.5, 1.5, { kind: "ctrl", base: "ctrl" })
      ]
    };
  }

  function csaIso() {
    return {
      id: "csa",
      name: "Canadian French",
      nameFr: "Canadien français",
      geometry: "iso",
      x0: BOARD_GAP,
      keys: [
        spec("Backquote", 0, 0, 1, { base: "/", shift: "\\", altgr: "|" }),
        spec("Digit1", 0, 1, 1, { base: "1", shift: "!" }),
        spec("Digit2", 0, 2, 1, { base: "2", shift: "@", altgr: "²" }),
        spec("Digit3", 0, 3, 1, { base: "3", shift: "#", altgr: "³" }),
        spec("Digit4", 0, 4, 1, { base: "4", shift: "$" }),
        spec("Digit5", 0, 5, 1, { base: "5", shift: "%" }),
        spec("Digit6", 0, 6, 1, { base: "6", shift: "?" }),
        spec("Digit7", 0, 7, 1, { base: "7", shift: "&", altgr: "{" }),
        spec("Digit8", 0, 8, 1, { base: "8", shift: "*", altgr: "}" }),
        spec("Digit9", 0, 9, 1, { base: "9", shift: "(", altgr: "[" }),
        spec("Digit0", 0, 10, 1, { base: "0", shift: ")", altgr: "]" }),
        spec("Minus", 0, 11, 1, { base: "-", shift: "_" }),
        spec("Equal", 0, 12, 1, { base: "=", shift: "+" }),
        spec("Backspace", 0, 13, 2, { kind: "backspace", base: "⌫" }),
        spec("Tab", 1, 0, 1.5, { kind: "tab", base: "⇥" }),
        spec("KeyQ", 1, 1.5, 1, { base: "q", shift: "Q" }),
        spec("KeyW", 1, 2.5, 1, { base: "w", shift: "W" }),
        spec("KeyE", 1, 3.5, 1, { base: "e", shift: "E", altgr: "€" }),
        spec("KeyR", 1, 4.5, 1, { base: "r", shift: "R" }),
        spec("KeyT", 1, 5.5, 1, { base: "t", shift: "T" }),
        spec("KeyY", 1, 6.5, 1, { base: "y", shift: "Y" }),
        spec("KeyU", 1, 7.5, 1, { base: "u", shift: "U" }),
        spec("KeyI", 1, 8.5, 1, { base: "i", shift: "I" }),
        spec("KeyO", 1, 9.5, 1, { base: "o", shift: "O", altgr: "œ" }),
        spec("KeyP", 1, 10.5, 1, { base: "p", shift: "P" }),
        spec("BracketLeft", 1, 11.5, 1, { base: "^", shift: "¨", dead: "circ", shiftDead: "uml" }),
        spec("BracketRight", 1, 12.5, 1, { base: "¸", shift: "ˇ", dead: "cedilla", shiftDead: "caron" }),
        spec("Enter", 1, 13.5, 1.5, { kind: "enter", base: "⏎", h: 2 }),
        spec("CapsLock", 2, 0, 1.75, { kind: "caps", base: "⇪" }),
        spec("KeyA", 2, 1.75, 1, { base: "a", shift: "A" }),
        spec("KeyS", 2, 2.75, 1, { base: "s", shift: "S" }),
        spec("KeyD", 2, 3.75, 1, { base: "d", shift: "D" }),
        spec("KeyF", 2, 4.75, 1, { base: "f", shift: "F" }),
        spec("KeyG", 2, 5.75, 1, { base: "g", shift: "G" }),
        spec("KeyH", 2, 6.75, 1, { base: "h", shift: "H" }),
        spec("KeyJ", 2, 7.75, 1, { base: "j", shift: "J" }),
        spec("KeyK", 2, 8.75, 1, { base: "k", shift: "K" }),
        spec("KeyL", 2, 9.75, 1, { base: "l", shift: "L" }),
        spec("Semicolon", 2, 10.75, 1, { base: ";", shift: ":", altgr: "~" }),
        spec("Quote", 2, 11.75, 1, { base: "è", shift: "È" }),
        spec("Backslash", 2, 12.75, 0.75, { base: "à", shift: "À" }),
        spec("ShiftLeft", 3, 0, 1.25, { kind: "shift", base: "⇧" }),
        spec("IntlBackslash", 3, 1.25, 1, { base: "ù", shift: "Ù", altgr: "\\" }),
        spec("KeyZ", 3, 2.25, 1, { base: "z", shift: "Z" }),
        spec("KeyX", 3, 3.25, 1, { base: "x", shift: "X" }),
        spec("KeyC", 3, 4.25, 1, { base: "c", shift: "C" }),
        spec("KeyV", 3, 5.25, 1, { base: "v", shift: "V" }),
        spec("KeyB", 3, 6.25, 1, { base: "b", shift: "B" }),
        spec("KeyN", 3, 7.25, 1, { base: "n", shift: "N" }),
        spec("KeyM", 3, 8.25, 1, { base: "m", shift: "M" }),
        spec("Comma", 3, 9.25, 1, { base: ",", shift: "'", altgr: "«" }),
        spec("Period", 3, 10.25, 1, { base: ".", shift: ".", altgr: "»" }),
        spec("Slash", 3, 11.25, 1, { base: "é", shift: "É" }),
        spec("ShiftRight", 3, 12.25, 2.75, { kind: "shift", base: "⇧" }),
        spec("ControlLeft", 4, 0, 1.5, { kind: "ctrl", base: "ctrl" }),
        spec("AltLeft", 4, 1.5, 1.5, { kind: "alt", base: "alt" }),
        spec("Space", 4, 3, 7.5, { kind: "space", base: " " }),
        spec("AltRight", 4, 10.5, 2.25, { kind: "altgr", base: "alt gr" }),
        spec("ControlRight", 4, 12.75, 2.25, { kind: "ctrl", base: "ctrl" })
      ]
    };
  }

  const DEAD_MAP = {
    circ: { a: "â", e: "ê", i: "î", o: "ô", u: "û", A: "Â", E: "Ê", I: "Î", O: "Ô", U: "Û" },
    uml: { a: "ä", e: "ë", i: "ï", o: "ö", u: "ü", y: "ÿ", A: "Ä", E: "Ë", I: "Ï", O: "Ö", U: "Ü", Y: "Ÿ" },
    grave: { a: "à", e: "è", i: "ì", o: "ò", u: "ù", A: "À", E: "È", I: "Ì", O: "Ò", U: "Ù" },
    cedilla: { c: "ç", C: "Ç" },
    caron: { c: "č", C: "Č", s: "š", S: "Š", z: "ž", Z: "Ž" }
  };
  const DEAD_MARK = { circ: "^", uml: "¨", grave: "`", cedilla: "¸", caron: "ˇ" };

  const US = usAnsi();
  const CSA = csaIso();
  const LAYOUTS = { us: US, csa: CSA };

  function keyById(layout, kid) {
    for (let i = 0; i < layout.keys.length; i++) {
      if (layout.keys[i].kid === kid) return layout.keys[i];
    }
    return null;
  }

  function keyByCode(layout, code) {
    for (let i = 0; i < layout.keys.length; i++) {
      if (layout.keys[i].code === code) return layout.keys[i];
    }
    return null;
  }

  /* Resolve a physical `code` against the union of every layout, so a CSA
     board and a US board are both live no matter which one the picker is
     painting. CSA is searched first because it is the superset (it is the only
     one carrying IntlBackslash). */
  function keyByCodeAny(code) {
    return keyByCode(CSA, code) || keyByCode(US, code);
  }

  function allCodes() {
    const seen = Object.create(null);
    const out = [];
    [CSA, US].forEach(function (l) {
      l.keys.forEach(function (k) {
        if (!seen[k.code]) { seen[k.code] = 1; out.push(k.code); }
      });
    });
    return out;
  }

  function center(layout, key) {
    return [layout.x0 + key.col + key.w / 2, key.row + key.h / 2];
  }

  function dist(a, b) {
    const dx = a[0] - b[0];
    const dy = a[1] - b[1];
    return Math.sqrt(dx * dx + dy * dy);
  }

  function clusterPoints(points, eps) {
    const n = points.length;
    if (!n) return [];
    const e = eps == null ? CLUSTER_EPS : eps;
    const labels = new Array(n).fill(-1);
    function neighbors(i) {
      const out = [];
      for (let j = 0; j < n; j++) {
        if (dist(points[i], points[j]) <= e) out.push(j);
      }
      return out;
    }
    let cid = 0;
    for (let i = 0; i < n; i++) {
      if (labels[i] !== -1) continue;
      labels[i] = cid;
      const seed = neighbors(i).slice();
      let s = 0;
      while (s < seed.length) {
        const j = seed[s++];
        if (labels[j] === -1) {
          labels[j] = cid;
          const nb = neighbors(j);
          for (let k = 0; k < nb.length; k++) {
            if (seed.indexOf(nb[k]) < 0) seed.push(nb[k]);
          }
        }
      }
      cid += 1;
    }
    return labels;
  }

  function heldPoint(h) {
    const layout = LAYOUTS[h.board];
    const key = keyById(layout, h.kid);
    return center(layout, key);
  }

  function clusterHeld(held) {
    if (!held.length) return [];
    const labels = clusterPoints(held.map(heldPoint));
    const buckets = [];
    held.forEach(function (h, i) {
      const lab = labels[i];
      if (!buckets[lab]) buckets[lab] = [];
      buckets[lab].push(h);
    });
    return buckets.filter(Boolean);
  }

  function sameHeld(a, b) {
    return a.board === b.board && a.kid === b.kid;
  }

  function canAccept(held, incoming) {
    for (let i = 0; i < held.length; i++) {
      if (sameHeld(held[i], incoming)) return true;
    }
    if (held.length < MAX_FINGERS) return true;
    const before = clusterHeld(held).length;
    const after = clusterHeld(held.concat([incoming])).length;
    return after <= before;
  }

  function TypeState() {
    this.shift = false;
    this.caps = false;
    this.altgr = false;
    this.dead = "";
    this.text = "";
  }

  TypeState.prototype.glyph = function (key) {
    if (key.kind === "space") return " ";
    if (key.kind !== "char") return "";
    if (this.altgr && key.altgr) return key.altgr;
    const isAlpha = key.base.length > 0 && Array.from(key.base).every(function (ch) {
      return /\p{L}/u.test(ch);
    });
    const upper = !!(this.shift ^ (this.caps && isAlpha));
    if (upper) return key.shift || key.base.toUpperCase();
    return key.base;
  };

  TypeState.prototype.apply = function (key) {
    if (key.kind === "shift") {
      this.shift = true;
      return "";
    }
    if (key.kind === "caps") {
      this.caps = !this.caps;
      return "";
    }
    if (key.kind === "altgr") {
      this.altgr = true;
      return "";
    }
    if (key.kind === "backspace") {
      if (this.dead) {
        this.dead = "";
        return "";
      }
      this.text = this.text.slice(0, -1);
      return "";
    }
    if (key.kind === "enter") {
      this.text += "\n";
      return "\n";
    }
    if (key.kind === "tab") {
      this.text += "\t";
      return "\t";
    }
    if (key.kind === "space") {
      if (this.dead) {
        const mark = DEAD_MARK[this.dead] || "";
        this.dead = "";
        this.text += mark + " ";
        return mark + " ";
      }
      this.text += " ";
      return " ";
    }
    if (key.kind !== "char") return "";
    let deadId = "";
    if (this.shift && key.shiftDead) deadId = key.shiftDead;
    else if (!this.shift && key.dead) deadId = key.dead;
    if (deadId && !this.altgr) {
      this.dead = deadId;
      return "";
    }
    let ch = this.glyph(key);
    if (this.dead) {
      const combo = DEAD_MAP[this.dead] && DEAD_MAP[this.dead][ch];
      this.dead = "";
      if (combo) ch = combo;
    }
    if (!ch) return "";
    this.text += ch;
    return ch;
  };

  TypeState.prototype.release = function (key) {
    if (key.kind === "shift") this.shift = false;
    if (key.kind === "altgr") this.altgr = false;
  };

  const KEY_Z_MIDI = 48;
  const INTL_BACKSLASH_MIDI = 47;
  const NOTE_FR = ["Do", "Do♯", "Ré", "Ré♯", "Mi", "Fa", "Fa♯", "Sol", "Sol♯", "La", "La♯", "Si"];
  const NOTE_KIDS = [
    "KeyZ", "KeyX", "KeyC", "KeyV", "KeyB", "KeyN", "KeyM", "Comma", "Period", "Slash",
    "KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyH", "KeyJ", "KeyK", "KeyL", "Semicolon", "Quote",
    "KeyQ", "KeyW", "KeyE", "KeyR", "KeyT", "KeyY", "KeyU", "KeyI", "KeyO", "KeyP",
    "BracketLeft", "BracketRight", "Backslash",
    "Backquote", "Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "Digit6", "Digit7",
    "Digit8", "Digit9", "Digit0", "Minus", "Equal"
  ];
  const NOTE_INDEX = {};
  NOTE_KIDS.forEach(function (kid, i) { NOTE_INDEX[kid] = i; });

  /* ── Octave shift ──────────────────────────────────────────────────────
     47 keys cannot cover an 88-key piano. At rest the map spans MIDI 47..94
     (Si2..La#6); the instrument is 21..108 (La0..Do8). Do1 = MIDI 24 is two
     octaves below the resting floor, so it is unreachable without transposing.
     That is arithmetic, not preference — there has to be an octave control.

     Range -3..+2 is chosen so that every one of the 88 keys is reachable:
       -3 puts Slash (base 57) on 21 = La0, the lowest key on the piano
       -2 puts KeyZ  (base 48) on 24 = Do1
       +2 puts Digit2 (base 84) on 108 = Do8, the highest key
     Shifted notes outside 21..108 return null, so a cap that would fall off
     the instrument goes inert instead of playing something that is not there. */
  const PIANO_LO = 21;
  const PIANO_HI = 108;
  const OCTAVE_MIN = -3;
  const OCTAVE_MAX = 2;
  let octave = 0;

  function clampOctave(n) {
    n = Math.round(Number(n) || 0);
    return n < OCTAVE_MIN ? OCTAVE_MIN : n > OCTAVE_MAX ? OCTAVE_MAX : n;
  }
  function getOctave() { return octave; }
  function setOctave(n) { octave = clampOctave(n); return octave; }
  function nudgeOctave(d) { return setOctave(octave + (Number(d) || 0)); }

  /** Untransposed note for a physical key. Never moves. */
  function baseMidiForKid(kid) {
    if (kid === "IntlBackslash") return INTL_BACKSLASH_MIDI;
    const i = NOTE_INDEX[kid];
    return i == null ? null : KEY_Z_MIDI + i;
  }

  /** Note this key plays right now, i.e. base note plus the octave shift. */
  function midiForKid(kid) {
    const base = baseMidiForKid(kid);
    if (base == null) return null;
    const m = base + 12 * octave;
    return m < PIANO_LO || m > PIANO_HI ? null : m;
  }

  function kidForBaseMidi(base) {
    if (base === INTL_BACKSLASH_MIDI) return "IntlBackslash";
    const i = base - KEY_Z_MIDI;
    if (i < 0 || i >= NOTE_KIDS.length) return null;
    return NOTE_KIDS[i];
  }

  function kidForMidi(midi) {
    return kidForBaseMidi(midi - 12 * octave);
  }

  /* ── Glyph labelling ───────────────────────────────────────────────────
     The static tables above are a fallback. The truth about what a physical
     key prints is whatever the browser says, and there are two ways to ask:

       1. navigator.keyboard.getLayoutMap() — exact, whole-board, but Chromium
          only and needs a secure context.
       2. the `key` of a real keydown — universal, but only tells you about
          keys the user has actually pressed.

     Both are used. (1) seeds the board where available; (2) corrects it as
     the user plays, which is what carries Safari and Firefox. Neither can
     produce a blank cap: an unknown code falls back to the static glyph. */
  const liveGlyphs = Object.create(null);
  let layoutMapSize = 0;
  let layoutMapSupported = null;

  function printable(g) {
    return typeof g === "string" && g.length > 0 && g.length <= 2 && g !== " " &&
      !/^[A-Z][a-z]+$/.test(g);            // rejects "Enter", "Shift", "Dead"
  }

  function setLiveGlyph(code, g) {
    if (!code || !printable(g)) return false;
    if (liveGlyphs[code] === g) return false;
    liveGlyphs[code] = g;
    return true;
  }

  /** Record what a real keydown says this physical key prints. */
  function observeGlyph(ev) {
    if (!ev || ev.altKey || ev.metaKey || ev.ctrlKey) return false;
    let g = ev.key;
    if (!printable(g)) return false;
    if (g.length === 1 && g.toLowerCase() !== g.toUpperCase()) g = g.toLowerCase();
    return setLiveGlyph(ev.code, g);
  }

  /** Chromium-only whole-board read. Resolves to a report, never rejects. */
  function loadLayoutMap() {
    const nav = typeof navigator !== "undefined" ? navigator : null;
    const kb = nav && nav.keyboard;
    if (!kb || typeof kb.getLayoutMap !== "function") {
      layoutMapSupported = false;
      return Promise.resolve({
        supported: false, size: 0,
        secureContext: typeof isSecureContext !== "undefined" ? isSecureContext : null
      });
    }
    return kb.getLayoutMap().then(function (map) {
      layoutMapSupported = true;
      let n = 0;
      map.forEach(function (glyph, code) { if (setLiveGlyph(code, glyph)) n++; });
      layoutMapSize = map.size;
      return { supported: true, size: map.size, applied: n };
    }).catch(function () {
      layoutMapSupported = false;
      return { supported: false, size: 0, error: true };
    });
  }

  /** What to paint on the cap for `code`, under `layout` as the fallback. */
  function glyphForCode(code, layout) {
    if (liveGlyphs[code]) return liveGlyphs[code];
    const k = layout ? keyByCode(layout, code) : keyByCodeAny(code);
    if (k && k.base) return k.base;
    return code;
  }

  /* Which board to paint, from evidence rather than from a guess. Only the
     glyphs that actually differ between the two layouts are consulted; every
     one of these was read back from a real browser under both input sources.
     `Backquote: ù` is the Apple-ISO CSA signature, `IntlBackslash: ù` the PC
     one — either is decisive. */
  const CSA_SIGNATURE = {
    Backquote: ["ù"], IntlBackslash: ["ù"], Slash: ["é"],
    Quote: ["è"], Backslash: ["à"], BracketRight: ["ç"], BracketLeft: ["^"]
  };

  function detectLayoutId() {
    const codes = Object.keys(CSA_SIGNATURE);
    for (let i = 0; i < codes.length; i++) {
      const g = liveGlyphs[codes[i]];
      if (g && CSA_SIGNATURE[codes[i]].indexOf(g) >= 0) return "csa";
    }
    return liveGlyphs.Backquote || liveGlyphs.Slash ? "us" : null;
  }

  function glyphReport() {
    return {
      supported: layoutMapSupported,
      size: layoutMapSize,
      observed: Object.keys(liveGlyphs).length,
      detected: detectLayoutId()
    };
  }

  function noteLabelFr(midi) {
    return NOTE_FR[((midi % 12) + 12) % 12] + (Math.floor(midi / 12) - 1);
  }

  function FingerGate() {
    this.pointers = new Map();
    this.extras = new Map();
  }

  FingerGate.prototype.held = function () {
    return Array.from(this.pointers.values()).concat(Array.from(this.extras.values()));
  };

  FingerGate.prototype.at = function (pointer) {
    return this.pointers.get(pointer) || this.extras.get(pointer);
  };

  FingerGate.prototype.clusters = function () {
    return clusterHeld(this.held());
  };

  FingerGate.prototype.down = function (pointer, key) {
    if (this.pointers.has(pointer)) {
      const prev = this.pointers.get(pointer);
      if (sameHeld(prev, key)) return true;
      this.pointers.delete(pointer);
      if (canAccept(this.held(), key)) {
        this.pointers.set(pointer, key);
        return true;
      }
      this.pointers.set(pointer, prev);
      return false;
    }
    if (this.held().some(function (h) { return sameHeld(h, key); })) return true;
    if (!canAccept(this.held(), key)) return false;
    if (this.pointers.size < MAX_FINGERS) this.pointers.set(pointer, key);
    else this.extras.set(pointer, key);
    return true;
  };

  FingerGate.prototype.up = function (pointer) {
    this.pointers.delete(pointer);
    this.extras.delete(pointer);
    this.pruneExtras();
  };

  FingerGate.prototype.pruneExtras = function () {
    const base = Array.from(this.pointers.values());
    const kept = new Map();
    this.extras.forEach(function (extra, pointer) {
      if (base.some(function (x) { return sameHeld(x, extra); })) return;
      const already = Array.from(kept.values());
      if (already.some(function (x) { return sameHeld(x, extra); })) return;
      const trial = base.concat(already);
      const before = clusterHeld(trial).length;
      const after = clusterHeld(trial.concat([extra])).length;
      if (after <= before) kept.set(pointer, extra);
    });
    this.extras = kept;
  };

  FingerGate.prototype.clear = function () {
    this.pointers.clear();
    this.extras.clear();
  };

  global.DUAL = {
    MAX_FINGERS: MAX_FINGERS,
    CLUSTER_EPS: CLUSTER_EPS,
    US: US,
    CSA: CSA,
    LAYOUTS: LAYOUTS,
    keyById: keyById,
    keyByCode: keyByCode,
    keyByCodeAny: keyByCodeAny,
    allCodes: allCodes,
    center: center,
    clusterHeld: clusterHeld,
    canAccept: canAccept,
    TypeState: TypeState,
    FingerGate: FingerGate,
    sameHeld: sameHeld,
    midiForKid: midiForKid,
    baseMidiForKid: baseMidiForKid,
    kidForMidi: kidForMidi,
    noteLabelFr: noteLabelFr,
    KEY_Z_MIDI: KEY_Z_MIDI,
    PIANO_LO: PIANO_LO,
    PIANO_HI: PIANO_HI,
    OCTAVE_MIN: OCTAVE_MIN,
    OCTAVE_MAX: OCTAVE_MAX,
    getOctave: getOctave,
    setOctave: setOctave,
    nudgeOctave: nudgeOctave,
    loadLayoutMap: loadLayoutMap,
    observeGlyph: observeGlyph,
    glyphForCode: glyphForCode,
    detectLayoutId: detectLayoutId,
    glyphReport: glyphReport,
    selfTest: selfTest
  };

  function selfTest() {
    function held(board, kid) { return { board: board, kid: kid }; }
    if (US.geometry !== "ansi" || CSA.geometry !== "iso") throw new Error("geometry");
    if (US.keys.some(function (k) { return k.kid === "IntlBackslash"; })) throw new Error("US ISO key");
    if (!CSA.keys.some(function (k) { return k.kid === "IntlBackslash" && k.base === "ù"; })) throw new Error("CSA ù");
    const asdf = ["KeyA", "KeyS", "KeyD", "KeyF"].map(function (k) { return held("us", k); });
    if (clusterHeld(asdf).length !== 1) throw new Error("ASDF must be one cluster");
    const hands = asdf.concat(["KeyJ", "KeyK", "KeyL"].map(function (k) { return held("us", k); }));
    if (clusterHeld(hands).length !== 2) throw new Error("two hands must be two clusters");
    const tenHome = ["KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyJ", "KeyK", "KeyL", "Semicolon", "Quote"].map(function (k) {
      return held("us", k);
    });
    if (clusterHeld(tenHome).length !== 2) throw new Error("two-hand home row is two clusters");
    if (canAccept(tenHome, held("us", "Digit1"))) throw new Error("11th isolated on a two-cluster board must fail");
    if (!canAccept(tenHome, held("us", "KeyQ"))) throw new Error("clustered 11th on home row must pass");
    const tenKids = ["Digit1", "Digit3", "Digit5", "Digit7", "Digit9", "KeyZ", "KeyC", "KeyB", "KeyM", "Slash"];
    const ten = tenKids.map(function (k) { return held("us", k); });
    if (clusterHeld(ten).length !== 10) throw new Error("ten isolated keys");
    if (canAccept(ten, held("csa", "KeyA"))) throw new Error("11th isolated must fail");
    if (!canAccept(ten, held("us", "Backquote"))) throw new Error("clustered 11th must pass");
    if (clusterHeld([held("us", "KeyA"), held("csa", "KeyA")]).length !== 2) throw new Error("two boards");
    const gate = new FingerGate();
    ten.forEach(function (k, i) { if (!gate.down(i, k)) throw new Error("finger " + i); });
    if (gate.down(99, held("csa", "KeyA"))) throw new Error("gate isolated");
    if (!gate.down(99, held("us", "Backquote"))) throw new Error("gate clustered");
    if (gate.clusters().length !== 10) throw new Error("tracks stay at 10");
    if (gate.held().length !== 11) throw new Error("clustered extra is an 11th touch");
    gate.up(99);
    if (gate.held().length !== 10) throw new Error("lifting the extra finger must release it");
    if (gate.held().some(function (k) { return k.kid === "Backquote"; })) throw new Error("extra pointer lift");
    if (!gate.down(99, held("us", "Backquote"))) throw new Error("re-cluster extra");
    const st = new TypeState();
    st.apply(keyById(CSA, "Slash"));
    if (st.text !== "é") throw new Error("é");
    st.apply(keyById(CSA, "BracketLeft"));
    st.apply(keyById(CSA, "KeyA"));
    if (!st.text.endsWith("â")) throw new Error("^a");
    gate.up(0);
    if (gate.held().some(function (k) { return k.kid === "Backquote"; })) throw new Error("extra lift");
    if (!gate.down(0, held("csa", "KeyA"))) throw new Error("freed finger");
    if (gate.down(98, held("csa", "Digit1"))) throw new Error("still 11th");
    if (midiForKid("KeyZ") !== 48 || noteLabelFr(48) !== "Do3") throw new Error("Z is Do3");
    if (midiForKid("KeyD") !== 60 || noteLabelFr(60) !== "Do4") throw new Error("D is Do4");
    if (midiForKid("KeyQ") !== 69 || noteLabelFr(69) !== "La4") throw new Error("Q is La4");
    if (kidForMidi(60) !== "KeyD") throw new Error("Do4 binds to D");
    if (midiForKid("IntlBackslash") !== 47) throw new Error("CSA ù is Si2");
    if (midiForKid("Space") != null || midiForKid("ShiftLeft") != null) throw new Error("mods are silent");
    US.keys.concat(CSA.keys).forEach(function (k) {
      if (k.kind === "char" && midiForKid(k.kid) == null) throw new Error("unmapped " + k.kid);
    });

    /* ── input is layout-independent ──────────────────────────────────────
       Every code either layout carries must resolve without being told which
       layout is on screen, and must give the same note either way. This is
       the whole point of keying on `code`. */
    setOctave(0);
    const codes = allCodes();
    if (codes.length !== 59) throw new Error("union of codes is 59, got " + codes.length);
    codes.forEach(function (c) {
      if (!keyByCodeAny(c)) throw new Error("union lookup missed " + c);
    });
    if (!keyByCodeAny("IntlBackslash")) throw new Error("IntlBackslash must resolve with no layout named");
    US.keys.forEach(function (k) {
      const viaUS = keyByCode(US, k.code);
      const viaAny = keyByCodeAny(k.code);
      if (!viaAny) throw new Error("shared code unresolved " + k.code);
      if (midiForKid(viaUS.kid) !== midiForKid(viaAny.kid)) {
        throw new Error("same physical key, different note across layouts: " + k.code);
      }
    });

    /* ── octave shift, and Do1 in particular ──────────────────────────── */
    if (getOctave() !== 0) throw new Error("octave starts at 0");
    if (midiForKid("KeyZ") !== 48) throw new Error("octave 0 leaves Z on Do3");
    if (setOctave(-2) !== -2) throw new Error("setOctave(-2)");
    if (midiForKid("KeyZ") !== 24) throw new Error("octave -2 must put Z on MIDI 24");
    if (noteLabelFr(midiForKid("KeyZ")) !== "Do1") throw new Error("MIDI 24 is Do1");
    if (kidForMidi(24) !== "KeyZ") throw new Error("Do1 binds back to Z at octave -2");
    if (setOctave(-3) !== -3) throw new Error("setOctave(-3)");
    if (midiForKid("Slash") !== PIANO_LO) throw new Error("octave -3 must reach La0 = 21");
    if (midiForKid("KeyZ") !== null) throw new Error("notes below the piano must go inert");
    if (setOctave(2) !== 2) throw new Error("setOctave(2)");
    if (midiForKid("Digit2") !== PIANO_HI) throw new Error("octave +2 must reach Do8 = 108");
    if (setOctave(-99) !== OCTAVE_MIN || setOctave(99) !== OCTAVE_MAX) throw new Error("octave clamps");
    // Every one of the 88 keys must be reachable from some octave.
    const reach = {};
    for (let o = OCTAVE_MIN; o <= OCTAVE_MAX; o++) {
      setOctave(o);
      NOTE_KIDS.concat(["IntlBackslash"]).forEach(function (k) {
        const m = midiForKid(k);
        if (m != null) reach[m] = 1;
      });
    }
    for (let m = PIANO_LO; m <= PIANO_HI; m++) {
      if (!reach[m]) throw new Error("MIDI " + m + " (" + noteLabelFr(m) + ") is unreachable");
    }
    setOctave(0);
    if (midiForKid("KeyZ") !== 48) throw new Error("octave resets");

    /* ── glyph layer is labelling only, and never blank ───────────────── */
    if (glyphForCode("KeyZ", US) !== "z") throw new Error("US glyph");
    if (glyphForCode("Slash", CSA) !== "é") throw new Error("CSA glyph");
    if (!glyphForCode("NoSuchCode", US)) throw new Error("unknown code must still label");
    const beforeNote = midiForKid("Slash");
    observeGlyph({ code: "Slash", key: "é" });
    if (glyphForCode("Slash", US) !== "é") throw new Error("observed glyph must win over the static table");
    if (midiForKid("Slash") !== beforeNote) throw new Error("relabelling must not move a note");
    if (detectLayoutId() !== "csa") throw new Error("é on Slash is the CSA signature");
    observeGlyph({ code: "Backquote", key: "ù" });
    if (glyphForCode("Backquote", US) !== "ù") throw new Error("Apple-ISO CSA puts ù on Backquote");
    delete liveGlyphs.Slash;
    delete liveGlyphs.Backquote;

    return "dual_keyboard.js: US=" + US.keys.length + " CSA=" + CSA.keys.length +
      " union=" + codes.length + " gate=10+cluster notes=Z/D/Q octave=" +
      OCTAVE_MIN + ".." + OCTAVE_MAX + " Do1@-2 88/88 reachable OK";
  }

  if (typeof process !== "undefined" && process.argv && /dual_keyboard\.js$/.test(String(process.argv[1] || ""))) {
    console.log(selfTest());
  }
})(typeof window !== "undefined" ? window : globalThis);
