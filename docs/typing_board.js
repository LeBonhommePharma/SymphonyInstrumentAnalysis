/**
 * On-screen typing board.
 *
 * Geometry and the note map are NOT redrawn here — they come from
 * window.DUAL (docs/piano/dual_keyboard.js), whose own selfTest() pins
 * KeyZ→48 (Do3), KeyD→60 (Do4), KeyQ→69 (La4) and IntlBackslash→47 (CSA ù).
 * This module only paints caps and forwards held notes.
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

  function glyphOf(key) {
    var g = key.base != null ? String(key.base) : (key.kid || "");
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
    this.render("us");
  }

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

    var frag = document.createDocumentFragment();
    layout.keys.forEach(function (k) {
      var midi = DUAL.midiForKid(k.kid);
      var cap = document.createElement("div");
      cap.className = "cap" + (midi == null ? " cap-mod" : "");
      cap.setAttribute("data-kid", k.kid);
      if (midi != null) cap.setAttribute("data-midi", String(midi));
      cap.style.left = (k.col / units * 100) + "%";
      cap.style.width = "calc(" + (k.w / units * 100) + "% - 4px)";
      cap.style.top = (k.row / ROWS * 100) + "%";
      cap.style.height = "calc(" + ((k.h || 1) / ROWS * 100) + "% - 4px)";

      var g = document.createElement("span");
      g.className = "cap-glyph";
      g.textContent = glyphOf(k);
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
      if (self.held.has(m)) {
        cap.style.background = rgb(c);
        cap.style.boxShadow = "0 0 16px " + rgb(c, 0.6) + ", inset 0 0 0 2px #b6ff55";
        cap.firstChild.style.color = contrastOn(c);
      } else {
        cap.style.background = "";
        cap.style.boxShadow = "";
        cap.firstChild.style.color = "";
      }
    });
  };

  TypingBoard.prototype.setBoard = function (board) {
    this.releaseAll();
    this.render(board);
  };

  TypingBoard.prototype.releaseAll = function () {
    this.held.clear();
    this.downCodes = Object.create(null);
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
    // keyById takes the layout object, not its name.
    var layout = DUAL.LAYOUTS[this.board] || DUAL.LAYOUTS.us;
    var key = DUAL.keyById ? DUAL.keyById(layout, code) : null;
    if (this.gate && key && !this.gate.down(code, key)) return false;
    this.downCodes[code] = true;
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
    var midi = DUAL.midiForKid(code);
    if (midi != null) {
      var stillDown = Object.keys(this.downCodes).some(function (c) {
        return DUAL.midiForKid(c) === midi;
      });
      if (!stillDown) this.held.delete(midi);
    }
    this.paint();
    this.emit();
    return true;
  };

  /** Attach hardware key handling. Ignores repeats and modified chords. */
  TypingBoard.prototype.listen = function (target) {
    var self = this;
    var node = target || global;
    node.addEventListener("keydown", function (ev) {
      if (ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (self.down(ev.code)) ev.preventDefault();
    });
    node.addEventListener("keyup", function (ev) {
      if (self.up(ev.code)) ev.preventDefault();
    });
    global.addEventListener("blur", function () { self.releaseAll(); });
  };

  global.TypingBoard = TypingBoard;
  global.TypingBoard.crayonFor = crayonFor;
  global.TypingBoard.contrastOn = contrastOn;
})(window);
