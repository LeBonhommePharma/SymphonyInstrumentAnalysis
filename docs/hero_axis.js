/**
 * Hub / ELI5 hero backdrop — the frequency axis, and nothing else.
 *
 * INTEGRITY NOTE. These two pages never open a microphone, so they have no
 * AnalyserNode and therefore no spectrum to draw. The design prototypes filled
 * this canvas with a synthetic 8-partial sine demo; that is exactly the fake
 * data the work order forbids. What is drawn here is real information only —
 * the log-Hz scale, the dBFS ladder, and the 440 Hz concert-A reference — with
 * an explicit "no signal" caption. The live trace lives on Live listen and the
 * Crayon piano, where a real AnalyserNode drives it.
 *
 * No requestAnimationFrame loop: this is static, redrawn on resize only.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var F_LO = 27.5;

  function reduced() {
    return global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function label(key, fallback) {
    if (global.I18N && typeof global.I18N.t === "function") {
      var v = global.I18N.t(key);
      if (v && v !== key) return v;
    }
    return fallback;
  }

  function drawAxis(canvas, fHi) {
    if (!canvas) return;
    var box = canvas.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return;

    var dpr = Math.min(2, global.devicePixelRatio || 1);
    var W = Math.round(box.width * dpr);
    var H = Math.round(box.height * dpr);
    if (canvas.width !== W) canvas.width = W;
    if (canvas.height !== H) canvas.height = H;

    var ctx = canvas.getContext("2d");
    if (!ctx) return;

    var padL = 42 * dpr, padR = 16 * dpr, padT = 20 * dpr, padB = 28 * dpr;
    var plotW = W - padL - padR;
    var plotH = H - padT - padB;
    if (plotW <= 0 || plotH <= 0) return;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#070b12";
    ctx.fillRect(0, 0, W, H);

    var lo2 = Math.log2(F_LO);
    var span = Math.log2(fHi) - lo2;
    function xOf(f) {
      var u = (Math.log2(Math.max(f, F_LO)) - lo2) / span;
      return padL + Math.max(0, Math.min(1, u)) * plotW;
    }
    function yOf(db) {
      var u = (db + 90) / 90;
      return padT + plotH - Math.max(0, Math.min(1, u)) * plotH;
    }

    var mono = (10 * dpr) + "px ui-monospace, SFMono-Regular, Menlo, monospace";

    /* The copy column sits over the left of the canvas, so axis numerals are
       only drawn where the scrim has faded out. Lines run the full width. */
    var legible = padL + plotW * 0.46;

    /* dBFS ladder */
    ctx.font = mono;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    [-90, -60, -30, 0].forEach(function (db) {
      var y = yOf(db);
      ctx.strokeStyle = "rgba(34,211,238,0.10)";
      ctx.lineWidth = Math.max(1, dpr * 0.5);
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
      ctx.fillStyle = "#6b7690";
      ctx.fillText(String(db), legible + 6 * dpr, y);
    });

    /* log-Hz ticks; 440 is the gold reference */
    var ticks = [
      [27.5, "27.5"], [55, "55"], [110, "110"], [220, "220"],
      [440, "440"], [880, "880"], [1760, "1.76k"], [3500, "3.5k"]
    ];
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ticks.forEach(function (t) {
      if (t[0] > fHi) return;
      var x = xOf(t[0]);
      var gold = t[0] === 440;
      ctx.strokeStyle = gold ? "rgba(251,191,36,0.40)" : "rgba(34,211,238,0.08)";
      ctx.lineWidth = Math.max(1, dpr * (gold ? 0.9 : 0.5));
      ctx.beginPath();
      ctx.moveTo(x, padT);
      ctx.lineTo(x, padT + plotH);
      ctx.stroke();
      if (x < legible) return;
      ctx.fillStyle = gold ? "#fbbf24" : "#6b7690";
      ctx.fillText(t[1], x, padT + plotH + 7 * dpr);
    });

    /* Say plainly that there is no signal here. */
    ctx.textAlign = "right";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "rgba(138,147,168,0.75)";
    ctx.font = (10 * dpr) + "px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(label("axisOnly", "no signal on this page — the axis only"), W - padR, padT + 12 * dpr);
  }

  function boot() {
    var page = doc.getElementById("page");
    var canvases = [].slice.call(doc.querySelectorAll("[data-axis]"));
    var hero = doc.getElementById("heroAxis");
    if (hero && canvases.indexOf(hero) === -1) canvases.push(hero);

    function redraw() {
      canvases.forEach(function (c) {
        var fHi = parseFloat(c.getAttribute("data-fhi")) || 5000;
        drawAxis(c, fHi);
      });
    }

    function measure() {
      if (!page) return;
      var w = page.clientWidth;
      page.setAttribute("data-narrow", w < 720 ? "1" : "0");
      page.setAttribute("data-mid", w < 1080 ? "1" : "0");
    }

    function onResize() { measure(); redraw(); }

    measure();
    redraw();

    if (global.ResizeObserver) {
      var ro = new global.ResizeObserver(onResize);
      if (page) ro.observe(page);
      canvases.forEach(function (c) { ro.observe(c); });
    } else {
      global.addEventListener("resize", onResize);
    }

    /* Redraw the caption in the new language. */
    var prev = global.onSymphonyLangChange;
    global.onSymphonyLangChange = function (lang) {
      if (typeof prev === "function") prev(lang);
      redraw();
    };

    /* Reduced motion changes nothing here — there was never a loop. */
    void reduced;
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})(window);
