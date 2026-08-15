/* US ANSI + Canadian French CSA. Mirrors scripts/dual_keyboard.py.
   10 fingers max unless the extra key is well clustered. */
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
    const before = clusterHeld(held).length;
    const after = clusterHeld(held.concat([incoming])).length;
    if (after <= MAX_FINGERS) return true;
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

  function FingerGate() {
    this.pointers = new Map();
    this.extras = [];
  }

  FingerGate.prototype.held = function () {
    return Array.from(this.pointers.values()).concat(this.extras);
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
    else this.extras.push(key);
    return true;
  };

  FingerGate.prototype.up = function (pointer) {
    this.pointers.delete(pointer);
    this.pruneExtras();
  };

  FingerGate.prototype.pruneExtras = function () {
    const base = Array.from(this.pointers.values());
    const kept = [];
    this.extras.forEach(function (extra) {
      if (base.some(function (x) { return sameHeld(x, extra); })) return;
      if (kept.some(function (x) { return sameHeld(x, extra); })) return;
      const trial = base.concat(kept);
      const before = clusterHeld(trial).length;
      const after = clusterHeld(trial.concat([extra])).length;
      if (after <= before) kept.push(extra);
    });
    this.extras = kept;
  };

  FingerGate.prototype.clear = function () {
    this.pointers.clear();
    this.extras = [];
  };

  global.DUAL = {
    MAX_FINGERS: MAX_FINGERS,
    CLUSTER_EPS: CLUSTER_EPS,
    US: US,
    CSA: CSA,
    LAYOUTS: LAYOUTS,
    keyById: keyById,
    keyByCode: keyByCode,
    center: center,
    clusterHeld: clusterHeld,
    canAccept: canAccept,
    TypeState: TypeState,
    FingerGate: FingerGate,
    sameHeld: sameHeld,
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
    return "dual_keyboard.js: US=" + US.keys.length + " CSA=" + CSA.keys.length + " gate=10+cluster OK";
  }

  if (typeof process !== "undefined" && process.argv && /dual_keyboard\.js$/.test(String(process.argv[1] || ""))) {
    console.log(selfTest());
  }
})(typeof window !== "undefined" ? window : globalThis);
