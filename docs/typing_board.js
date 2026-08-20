/**
 * On-screen typing board.
 *
 * Geometry and the note map are NOT redrawn here — they come from
 * window.DUAL (docs/piano/dual_keyboard.js), whose own selfTest() pins
 * KeyZ→48 (Do3), KeyD→60 (Do4), KeyQ→69 (La4) and IntlBackslash→47 (CSA ù).
 * This module only paints caps and forwards held notes.
 *
 * Input never consults the rendered board. A keydown is resolved on its
 * `code` against the union of the layouts, so a US board and a CSA board are
 * both live at once — the picker below decides lettering, nothing else.
 *
 * Lettering comes from the browser where the browser will say: the whole
 * board from navigator.keyboard.getLayoutMap() on Chromium, and per key from
 * the `key` of each real keydown everywhere else, which is what covers Safari
 * and Firefox. The static tables in dual_keyboard.js are only the fallback.
 *
 * layout.x0 is deliberately ignored: it exists for side-by-side dual-board
 * display and would shove a single board 18 units to the right.
 */
(function (global) {
  "use strict";

  var ROWS = 5;

  var CRAYONS = [
    [251, 2, 7], [198, 64, 42], [253, 128, 8], [214, 214, 10],
    [128, 255, 8], [33, 255, 6], [52, 168, 88], [102, 255, 204],
    [102, 204, 255], [0, 0, 255], [128, 0, 255], [251, 2, 255]
  ];

  function crayonFor(midi) { return CRAYONS[((midi % 12) + 12) % 12]; }
  function rgb(c, a) {
    return a == null ? "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")"
                     : "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")";
  }
  function contrastOn(c) {
    var lum = (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
    return lum < 0.5 ? "#f4f7ff" : "#0a0e14";
  }

  /** Prefer what the browser says this physical key prints; fall back to the
      layout table; never return nothing.

      `live` is false once the reader has picked a layout by hand. The browser
      reports the active OS input source, which is not the same thing as the
      legends printed on the board in front of you — plug a CSA keyboard into
      a machine set to U.S. and every cap lies. Clicking the picker is how you
      say so, and an explicit choice has to win over the inference. */
  function glyphOf(key, layout, live) {
    var D = global.DUAL;
    var g = (live && D && D.glyphForCode) ? D.glyphForCode(key.code || key.kid, layout) : null;
    if (g == null || g === "") g = key.base != null ? String(key.base) : (key.kid || "");
    g = String(g);
    if (g.length === 1 && /[a-zà-ÿ]/i.test(g)) return g.toUpperCase();
    if (g.length > 6) return g.slice(0, 6);
    return g;
  }

  function TypingBoard(el, opts) {
    this.el = el;
    this.opts = opts || {};
    this.board = "us";
    this.caps = Object.create(null);
    this.held = new Set();          // MIDI numbers currently down
    this.gate = global.DUAL ? new global.DUAL.FingerGate() : null;
    this.downCodes = Object.create(null);
    this.downNotes = Object.create(null);  // code -> midi it started, for octave changes mid-hold
    this.manual = false;                   // set once the reader picks a layout
    this.render("us");
    this.adoptBrowserLayout();
  }

  /** Ask Chromium for the whole board up front. Elsewhere this is a no-op and
      the per-key correction in `down()` does the work instead. */
  TypingBoard.prototype.adoptBrowserLayout = function () {
    var self = this;
    var D = global.DUAL;
    if (!D || !D.loadLayoutMap) return Promise.resolve(null);
    return D.loadLayoutMap().then(function (report) {
      if (self.manual) return report;
      var want = D.detectLayoutId();
      if (want && want !== self.board) self.render(want);
      else self.relabel();
      self.emitMeta();
      return report;
    });
  };

  /** Repaint glyphs in place — used when a keydown teaches us a new one. */
  TypingBoard.prototype.relabel = function () {
    var D = global.DUAL;
    if (!D) return;
    var layout = D.LAYOUTS[this.board] || D.LAYOUTS.us;
    var self = this;
    Object.keys(this.caps).forEach(function (kid) {
      var key = D.keyById(layout, kid) || D.keyByCodeAny(kid);
      if (!key) return;
      var g = self.caps[kid].querySelector(".cap-glyph");
      if (g) g.textContent = glyphOf(key, layout, !self.manual);
    });
  };

  TypingBoard.prototype.render = function (board) {
    var DUAL = global.DUAL;
    if (!DUAL || !this.el) return;
    var layout = DUAL.LAYOUTS[board] || DUAL.LAYOUTS.us;
    this.board = DUAL.LAYOUTS[board] ? board : "us";
    this.el.setAttribute("data-layout", this.board);
    this.el.textContent = "";
    this.caps = Object.create(null);

    var units = 0;
    layout.keys.forEach(function (k) { units = Math.max(units, k.col + k.w); });
    if (units <= 0) units = 15;

    var live = !this.manual;
    var frag = document.createDocumentFragment();
    layout.keys.forEach(function (k) {
      var midi = DUAL.midiForKid(k.kid);
      // A modifier has no note at any octave; a note key can still be inert
      // because the current octave pushed it off the ends of the piano.
      var isMod = DUAL.baseMidiForKid(k.kid) == null;
      var cap = document.createElement("div");
      cap.className = "cap" + (isMod ? " cap-mod" : "") + (!isMod && midi == null ? " cap-inert" : "");
      cap.setAttribute("data-kid", k.kid);
      if (midi != null) cap.setAttribute("data-midi", String(midi));
      cap.style.left = (k.col / units * 100) + "%";
      cap.style.width = "calc(" + (k.w / units * 100) + "% - 4px)";
      cap.style.top = (k.row / ROWS * 100) + "%";
      cap.style.height = "calc(" + ((k.h || 1) / ROWS * 100) + "% - 4px)";

      var g = document.createElement("span");
      g.className = "cap-glyph";
      g.textContent = glyphOf(k, layout, live);
      cap.appendChild(g);

      var n = document.createElement("span");
      n.className = "cap-note";
      if (midi != null) {
        n.textContent = DUAL.noteLabelFr(midi);
        n.style.color = rgb(crayonFor(midi));
      }
      cap.appendChild(n);

      frag.appendChild(cap);
      this.caps[k.kid] = cap;
    }, this);
    this.el.appendChild(frag);
    this.paint();
  };

  TypingBoard.prototype.paint = function () {
    var self = this;
    Object.keys(this.caps).forEach(function (kid) {
      var cap = self.caps[kid];
      var midi = cap.getAttribute("data-midi");
      if (midi == null) return;
      var m = Number(midi);
      var c = crayonFor(m);
      var note = cap.querySelector(".cap-note");
      if (self.held.has(m)) {
        cap.style.background = rgb(c);
        cap.style.boxShadow = "0 0 16px " + rgb(c, 0.6) + ", inset 0 0 0 2px #b6ff55";
        cap.firstChild.style.color = contrastOn(c);
        // The note name is drawn in its own crayon, which is the fill colour
        // once the key is held — so it has to flip too, or the answer to
        // "what did I just play" vanishes exactly when you press the key.
        if (note) note.style.color = contrastOn(c);
      } else {
        cap.style.background = "";
        cap.style.boxShadow = "";
        cap.firstChild.style.color = "";
        if (note) note.style.color = rgb(c);
      }
    });
  };

  TypingBoard.prototype.setBoard = function (board) {
    this.manual = true;
    this.releaseAll();
    this.render(board);
    this.emitMeta();
  };

  /* ── Octave ───────────────────────────────────────────────────────────
     Notes move, keys do not. Everything held is released first, because a
     note that started at one octave has no sensible end at another. */
  TypingBoard.prototype.setOctave = function (n) {
    var D = global.DUAL;
    if (!D || !D.setOctave) return 0;
    var before = D.getOctave();
    var after = D.setOctave(n);
    if (after !== before) {
      this.releaseAll();
      this.render(this.board);
    }
    this.emitMeta();
    return after;
  };

  TypingBoard.prototype.nudgeOctave = function (d) {
    var D = global.DUAL;
    return this.setOctave((D && D.getOctave ? D.getOctave() : 0) + d);
  };

  TypingBoard.prototype.octave = function () {
    var D = global.DUAL;
    return D && D.getOctave ? D.getOctave() : 0;
  };

  /** Lowest and highest note the computer keyboard can play right now. */
  TypingBoard.prototype.range = function () {
    var D = global.DUAL;
    if (!D) return null;
    var lo = null, hi = null;
    D.allCodes().forEach(function (c) {
      var m = D.midiForKid(c);
      if (m == null) return;
      if (lo == null || m < lo) lo = m;
      if (hi == null || m > hi) hi = m;
    });
    return lo == null ? null : { lo: lo, hi: hi, loLabel: D.noteLabelFr(lo), hiLabel: D.noteLabelFr(hi) };
  };

  TypingBoard.prototype.emitMeta = function () {
    if (this.el) this.el.setAttribute("data-octave", String(this.octave()));
    if (typeof this.opts.onMeta === "function") {
      this.opts.onMeta({
        octave: this.octave(),
        board: this.board,
        range: this.range(),
        glyphs: global.DUAL && global.DUAL.glyphReport ? global.DUAL.glyphReport() : null
      });
    }
  };

  TypingBoard.prototype.releaseAll = function () {
    this.held.clear();
    this.downCodes = Object.create(null);
    this.downNotes = Object.create(null);
    if (this.gate) this.gate.clear();
    this.paint();
    this.emit();
  };

  TypingBoard.prototype.emit = function () {
    if (typeof this.opts.onHeld === "function") this.opts.onHeld(new Set(this.held));
  };

  TypingBoard.prototype.down = function (code) {
    var DUAL = global.DUAL;
    if (!DUAL || this.downCodes[code]) return false;
    var midi = DUAL.midiForKid(code);
    if (midi == null) return false;
    // Resolve against the union, never against the board being painted, so a
    // CSA key is not dead just because the US board is on screen. The gate
    // still needs a geometric position, so fall back to whichever layout
    // carries this code.
    var layout = DUAL.LAYOUTS[this.board] || DUAL.LAYOUTS.us;
    var key = DUAL.keyById(layout, code) || DUAL.keyByCodeAny(code);
    var board = DUAL.keyById(layout, code) ? this.board : (DUAL.keyByCode(DUAL.CSA, code) ? "csa" : "us");
    if (this.gate && key && !this.gate.down(code, { board: board, kid: key.kid })) return false;
    this.downCodes[code] = true;
    this.downNotes[code] = midi;
    this.held.add(midi);
    this.paint();
    this.emit();
    return true;
  };

  TypingBoard.prototype.up = function (code) {
    var DUAL = global.DUAL;
    if (!DUAL || !this.downCodes[code]) return false;
    delete this.downCodes[code];
    if (this.gate) this.gate.up(code);
    // Release the note this key actually started, not the note it would start
    // now — the octave may have moved under it.
    var midi = this.downNotes[code];
    if (midi == null) midi = DUAL.midiForKid(code);
    delete this.downNotes[code];
    var notes = this.downNotes;
    if (midi != null) {
      var stillDown = Object.keys(this.downCodes).some(function (c) {
        return notes[c] === midi;
      });
      if (!stillDown) this.held.delete(midi);
    }
    this.paint();
    this.emit();
    return true;
  };

  /** Octave shortcuts. Chosen from the codes the note map does not use, so
      they cannot shadow a key that plays. */
  var OCTAVE_KEYS = { ArrowDown: -1, ArrowUp: 1, ArrowLeft: -1, ArrowRight: 1 };

  /** Attach hardware key handling. Ignores repeats and modified chords. */
  TypingBoard.prototype.listen = function (target) {
    var self = this;
    var node = target || global;
    var D = global.DUAL;
    node.addEventListener("keydown", function (ev) {
      if (ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (OCTAVE_KEYS[ev.code] != null) {
        self.nudgeOctave(OCTAVE_KEYS[ev.code]);
        ev.preventDefault();
        return;
      }
      // Learn the real glyph for this physical key from the browser's own
      // `key`. This is what makes the caps right on Safari and Firefox, where
      // navigator.keyboard does not exist. It never affects which note plays.
      if (D && D.observeGlyph && D.observeGlyph(ev)) self.relabel();
      if (self.down(ev.code)) ev.preventDefault();
    });
    node.addEventListener("keyup", function (ev) {
      if (self.up(ev.code)) ev.preventDefault();
    });
    global.addEventListener("blur", function () { self.releaseAll(); });
    this.emitMeta();
  };

  global.TypingBoard = TypingBoard;
  global.TypingBoard.crayonFor = crayonFor;
  global.TypingBoard.contrastOn = contrastOn;
})(window);
