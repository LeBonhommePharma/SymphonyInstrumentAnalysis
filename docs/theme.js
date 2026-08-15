/**
 * Shared lighting scenes: Day / Light / Dark / Night / Stealth + Auto.
 * Auto uses Ambient Light Sensor when permitted, else prefers-color-scheme
 * and hour-of-day. Manual swatch clicks stick until Auto is re-enabled.
 */
(function (global) {
  const STORAGE_KEY = "crayon-theme";
  const MODE_KEY = "crayon-theme-mode";
  const THEMES = {
    day: { scheme: "light", bg: "#f6ead4", bar: "default" },
    light: { scheme: "light", bg: "#eef1f5", bar: "default" },
    dark: { scheme: "dark", bg: "#1c1e24", bar: "black" },
    night: { scheme: "dark", bg: "#0d1220", bar: "black" },
    stealth: { scheme: "dark", bg: "#121214", bar: "black" },
  };

  let mode = "auto";
  let current = "night";
  let lastLux = null;
  let lastAutoName = null;
  let lastAutoAt = 0;
  let sensor = null;
  let hourTimer = 0;

  function prefersLight() {
    return !!(global.matchMedia && global.matchMedia("(prefers-color-scheme: light)").matches);
  }

  function fromHour(date) {
    const h = date.getHours() + date.getMinutes() / 60;
    const light = prefersLight();
    if (h >= 6 && h < 17) return light ? "day" : "light";
    if (h >= 17 && h < 21) return light ? "light" : "night";
    return light ? "night" : "stealth";
  }

  function fromLux(lux) {
    if (!(lux >= 0) || !isFinite(lux)) return fromHour(new Date());
    if (lux >= 20000) return "day";
    if (lux >= 800) return "light";
    if (lux >= 80) return prefersLight() ? "light" : "dark";
    if (lux >= 8) return "night";
    return "stealth";
  }

  function autoTheme() {
    if (lastLux != null) return fromLux(lastLux);
    return fromHour(new Date());
  }

  function readMode() {
    try {
      const saved = localStorage.getItem(MODE_KEY);
      if (saved === "manual" || saved === "auto") return saved;
    } catch (e) { /* ignore */ }
    return "auto";
  }

  function preferred() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && THEMES[saved] && readMode() === "manual") return saved;
    } catch (e) { /* ignore */ }
    return autoTheme();
  }

  function apply(name, opts) {
    const persist = !opts || opts.persist !== false;
    const id = THEMES[name] ? name : "night";
    const spec = THEMES[id];
    current = id;
    const root = document.documentElement;
    if (root.getAttribute("data-theme") !== id) {
      root.setAttribute("data-theme", id);
    }
    root.setAttribute("data-scheme", spec.scheme);
    root.style.colorScheme = spec.scheme;
    root.style.background = spec.bg;
    const theme = document.querySelector('meta[name="theme-color"]');
    if (theme) theme.setAttribute("content", spec.bg);
    const bar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
    if (bar) bar.setAttribute("content", spec.bar);
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, id);
        localStorage.setItem(MODE_KEY, mode);
      } catch (e) { /* ignore */ }
    }
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", mode === "manual" && btn.getAttribute("data-theme-set") === id ? "true" : "false");
    });
    document.querySelectorAll("[data-theme-auto]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", mode === "auto" ? "true" : "false");
    });
    if (typeof global.onSymphonyThemeChange === "function") {
      global.onSymphonyThemeChange(id);
    }
    return id;
  }

  function setManual(name) {
    mode = "manual";
    lastAutoName = null;
    apply(name);
  }

  function setAuto() {
    mode = "auto";
    lastAutoAt = 0;
    const next = autoTheme();
    lastAutoName = next;
    apply(next);
  }

  function maybeAuto(next) {
    if (mode !== "auto") return;
    if (next === current) {
      lastAutoName = next;
      return;
    }
    const now = Date.now();
    if (lastAutoName === next && now - lastAutoAt < 8000) return;
    if (lastAutoAt && now - lastAutoAt < 12000) return;
    lastAutoAt = now;
    lastAutoName = next;
    apply(next, { persist: true });
  }

  function label(id) {
    if (global.I18N && typeof I18N.t === "function") {
      const key = {
        day: "themeDay",
        light: "themeLight",
        dark: "themeDark",
        night: "themeNight",
        stealth: "themeStealth",
        auto: "themeAuto",
      }[id];
      if (key) return I18N.t(key);
    }
    return id === "auto" ? "Auto" : id;
  }

  function paintLabels() {
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      const id = btn.getAttribute("data-theme-set");
      const name = label(id);
      btn.setAttribute("aria-label", name);
      btn.setAttribute("title", name);
    });
    document.querySelectorAll("[data-theme-auto]").forEach(function (btn) {
      const name = label("auto");
      btn.setAttribute("aria-label", name);
      btn.setAttribute("title", name);
    });
    const group = document.querySelector("[data-theme-group]");
    if (group && global.I18N) group.setAttribute("aria-label", I18N.t("themeGroup"));
  }

  function startSensors() {
    if (sensor) return;
    try {
      if (typeof global.AmbientLightSensor === "function") {
        sensor = new global.AmbientLightSensor({ frequency: 0.4 });
        sensor.addEventListener("reading", function () {
          lastLux = sensor.illuminance;
          maybeAuto(fromLux(lastLux));
        });
        sensor.addEventListener("error", function () {
          sensor = null;
        });
        sensor.start();
        return;
      }
    } catch (e) { /* permission / unsupported */ }
    global.addEventListener("devicelight", function (ev) {
      if (ev && typeof ev.value === "number") {
        lastLux = ev.value;
        maybeAuto(fromLux(lastLux));
      }
    });
    if (global.matchMedia) {
      const mq = global.matchMedia("(prefers-color-scheme: light)");
      const onScheme = function () {
        if (lastLux == null) maybeAuto(fromHour(new Date()));
      };
      if (mq.addEventListener) mq.addEventListener("change", onScheme);
      else if (mq.addListener) mq.addListener(onScheme);
    }
    hourTimer = global.setInterval(function () {
      if (lastLux == null) maybeAuto(fromHour(new Date()));
    }, 60000);
  }

  function boot() {
    mode = readMode();
    apply(preferred());
    paintLabels();
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      if (btn.getAttribute("data-theme-wired") === "1") return;
      btn.setAttribute("data-theme-wired", "1");
      btn.addEventListener("click", function () {
        setManual(btn.getAttribute("data-theme-set"));
      });
    });
    document.querySelectorAll("[data-theme-auto]").forEach(function (btn) {
      if (btn.getAttribute("data-theme-wired") === "1") return;
      btn.setAttribute("data-theme-wired", "1");
      btn.addEventListener("click", function () {
        setAuto();
      });
    });
    startSensors();
  }

  mode = readMode();
  apply(preferred(), { persist: false });

  const prevLang = global.onSymphonyLangChange;
  global.onSymphonyLangChange = function (lang) {
    if (typeof prevLang === "function") prevLang(lang);
    paintLabels();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.SYMPHONY_THEME = {
    apply: setManual,
    setAuto: setAuto,
    preferred: preferred,
    paintLabels: paintLabels,
    themes: THEMES,
    get mode() { return mode; },
    get current() { return current; },
  };
})(window);
