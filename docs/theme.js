/**
 * Dark-only pin.
 *
 * The five-scene Day/Light/Dark/Night/Stealth switcher was removed in the
 * FlexAID∆S refresh: the instrument reads on one near-black bed so the twelve
 * crayon note-colours stay the only saturated thing on screen.
 *
 * This file deliberately no longer reads or writes `crayon-theme` /
 * `crayon-theme-mode`. Existing values are left untouched in localStorage so
 * nothing downstream (iOS, TUI) loses state; they are simply ignored here.
 */
(function (global) {
  "use strict";

  var root = global.document && global.document.documentElement;
  if (root) {
    root.setAttribute("data-theme", "dark");
    root.setAttribute("data-scheme", "dark");
  }

  // Any legacy scene controls left in a page become inert rather than broken.
  function neutralise() {
    if (!global.document) return;
    var stale = global.document.querySelectorAll("[data-theme-set],[data-theme-auto]");
    for (var i = 0; i < stale.length; i++) {
      stale[i].setAttribute("hidden", "hidden");
      stale[i].setAttribute("aria-hidden", "true");
      stale[i].disabled = true;
    }
  }

  if (global.document) {
    if (global.document.readyState === "loading") {
      global.document.addEventListener("DOMContentLoaded", neutralise, { once: true });
    } else {
      neutralise();
    }
  }

  global.CRAYON_THEME = {
    name: "dark",
    scheme: "dark",
    /** Retained so old call sites do not throw; the scene is fixed. */
    set: function () { return "dark"; },
    current: function () { return "dark"; }
  };
})(typeof window !== "undefined" ? window : globalThis);
