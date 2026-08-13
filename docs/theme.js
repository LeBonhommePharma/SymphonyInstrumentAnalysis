/**
 * Shared lighting scenes for the public pages (hub, ELI5, live listen).
 * Day / Light / Dark / Night / Stealth. Persists in localStorage.
 */
(function (global) {
  const STORAGE_KEY = "crayon-theme";
  const THEMES = {
    day: { scheme: "light", bg: "#f6ead4", bar: "default" },
    light: { scheme: "light", bg: "#eef1f5", bar: "default" },
    dark: { scheme: "dark", bg: "#1c1e24", bar: "black" },
    night: { scheme: "dark", bg: "#0d1220", bar: "black" },
    stealth: { scheme: "dark", bg: "#121214", bar: "black" },
  };

  function preferred() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && THEMES[saved]) return saved;
    } catch (e) {
      /* ignore */
    }
    if (global.matchMedia && global.matchMedia("(prefers-color-scheme: light)").matches) {
      return "day";
    }
    return "night";
  }

  function apply(name) {
    const id = THEMES[name] ? name : "night";
    const spec = THEMES[id];
    const root = document.documentElement;
    root.setAttribute("data-theme", id);
    root.setAttribute("data-scheme", spec.scheme);
    root.style.colorScheme = spec.scheme;
    root.style.background = spec.bg;
    const theme = document.querySelector('meta[name="theme-color"]');
    if (theme) theme.setAttribute("content", spec.bg);
    const bar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
    if (bar) bar.setAttribute("content", spec.bar);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch (e) {
      /* ignore */
    }
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.getAttribute("data-theme-set") === id ? "true" : "false");
    });
    if (typeof global.onSymphonyThemeChange === "function") {
      global.onSymphonyThemeChange(id);
    }
    return id;
  }

  function label(id) {
    if (global.I18N && typeof I18N.t === "function") {
      const key = {
        day: "themeDay",
        light: "themeLight",
        dark: "themeDark",
        night: "themeNight",
        stealth: "themeStealth",
      }[id];
      if (key) return I18N.t(key);
    }
    return id;
  }

  function paintLabels() {
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      const id = btn.getAttribute("data-theme-set");
      const name = label(id);
      btn.setAttribute("aria-label", name);
      btn.setAttribute("title", name);
    });
    const group = document.querySelector("[data-theme-group]");
    if (group && global.I18N) group.setAttribute("aria-label", I18N.t("themeGroup"));
  }

  function boot() {
    apply(preferred());
    paintLabels();
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      if (btn.getAttribute("data-theme-wired") === "1") return;
      btn.setAttribute("data-theme-wired", "1");
      btn.addEventListener("click", function () {
        apply(btn.getAttribute("data-theme-set"));
      });
    });
  }

  apply(preferred());

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
    apply: apply,
    preferred: preferred,
    paintLabels: paintLabels,
    themes: THEMES,
  };
})(window);
