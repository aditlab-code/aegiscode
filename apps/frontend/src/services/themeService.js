import { computed, reactive, ref } from "vue";

export const THEME_KEY = "aegis-theme";
export const THEME_CONFIG_KEY = "aegis-theme-config";
export const WALLPAPER_KEY = "aegis-wallpaper";

export const THEMES = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});

/**
 * @deprecated All themes are now unified as template presets.
 */
export const THEME_MODES = Object.freeze({
  PRESET: "preset",
});

export const BASE_FOUNDATIONS = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});

export const CURATED_PRESETS = Object.freeze({
  DEFAULT_DARK: "default-dark",
  DEFAULT_LIGHT: "default-light",
  TOKYO_NIGHT_DARK: "tokyo-night-dark",
  TOKYO_NIGHT_LIGHT: "tokyo-night-light",
  NORD_DARK: "nord-dark",
  NORD_LIGHT: "nord-light",
  ATOM_DARK: "atom-dark",
  ATOM_LIGHT: "atom-light",
  HIGH_CONTRAST_DARK: "high-contrast-dark",
  HIGH_CONTRAST_LIGHT: "high-contrast-light",
});

export const PRESET_CATALOG = Object.freeze([
  {
    id: CURATED_PRESETS.DEFAULT_DARK,
    name: "Aegis Orbit",
    family: "Aegis",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#b5a1ed", secondary: "#bcbcca", accent: "#c1a4df", bg: "#181922", surface: "#1f202c" },
  },
  {
    id: CURATED_PRESETS.DEFAULT_LIGHT,
    name: "Aegis Orbit Light",
    family: "Aegis",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#8261bb", secondary: "#555168", accent: "#9a60ad", bg: "#eae5f4", surface: "#f5f3fa" },
  },
  {
    id: CURATED_PRESETS.TOKYO_NIGHT_DARK,
    name: "Tokyo Night",
    family: "Tokyo Night",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#7aa2f7", secondary: "#bb9af7", accent: "#7dcfff", bg: "#1a1b26", surface: "#24283b" },
  },
  {
    id: CURATED_PRESETS.TOKYO_NIGHT_LIGHT,
    name: "Tokyo Night Light",
    family: "Tokyo Night",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#34548a", secondary: "#565a6e", accent: "#5a4a78", bg: "#d5d6db", surface: "#e9e9ed" },
  },
  {
    id: CURATED_PRESETS.NORD_DARK,
    name: "Nordic Dark",
    family: "Nord",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#88c0d0", secondary: "#e5e9f0", accent: "#b48ead", bg: "#2e3440", surface: "#3b4252" },
  },
  {
    id: CURATED_PRESETS.NORD_LIGHT,
    name: "Nordic Light",
    family: "Nord",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#5e81ac", secondary: "#81a1c1", accent: "#88c0d0", bg: "#eceff4", surface: "#e5e9f0" },
  },
  {
    id: CURATED_PRESETS.ATOM_DARK,
    name: "Atom One Dark",
    family: "Atom One",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#61afef", secondary: "#9da5b4", accent: "#c678dd", bg: "#282c34", surface: "#21252b" },
  },
  {
    id: CURATED_PRESETS.ATOM_LIGHT,
    name: "Atom One Light",
    family: "Atom One",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#4078f2", secondary: "#696c77", accent: "#a626a4", bg: "#fafafa", surface: "#f0f0f0" },
  },
  {
    id: CURATED_PRESETS.HIGH_CONTRAST_DARK,
    name: "High Contrast Dark",
    family: "High Contrast",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#00ffff", secondary: "#ffffff", accent: "#ffff00", bg: "#000000", surface: "#0a0a0a" },
  },
  {
    id: CURATED_PRESETS.HIGH_CONTRAST_LIGHT,
    name: "High Contrast Light",
    family: "High Contrast",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#0000ee", secondary: "#990000", accent: "#008800", bg: "#ffffff", surface: "#f2f2f2" },
  },
]);

/**
 * Clamp a number to an integer between 0 and 255
 * @param {number|string} val
 * @returns {number}
 */
export function clampRgb(val) {
  const n = parseInt(val, 10);
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(255, n));
}

/**
 * Convert RGB object {r, g, b} to 6-char hex string #rrggbb
 * @param {{r: number, g: number, b: number}} rgb
 * @returns {string}
 */
export function rgbToHex(rgb) {
  if (!rgb) return "#000000";
  const r = clampRgb(rgb.r).toString(16).padStart(2, "0");
  const g = clampRgb(rgb.g).toString(16).padStart(2, "0");
  const b = clampRgb(rgb.b).toString(16).padStart(2, "0");
  return `#${r}${g}${b}`;
}

/**
 * Parse hex string to RGB object
 * @param {string} hex
 * @returns {{r: number, g: number, b: number}}
 */
export function hexToRgb(hex) {
  if (typeof hex !== "string") return { r: 0, g: 0, b: 0 };
  let clean = hex.replace("#", "").trim();
  if (clean.length === 3) {
    clean = clean.split("").map((c) => c + c).join("");
  }
  if (clean.length !== 6) return { r: 0, g: 0, b: 0 };
  const r = parseInt(clean.substring(0, 2), 16) || 0;
  const g = parseInt(clean.substring(2, 4), 16) || 0;
  const b = parseInt(clean.substring(4, 6), 16) || 0;
  return { r: clampRgb(r), g: clampRgb(g), b: clampRgb(b) };
}

/**
 * Return CSS rgba() string with specified alpha
 * @param {{r: number, g: number, b: number}} rgb
 * @param {number} alpha
 * @returns {string}
 */
export function rgbaString(rgb, alpha = 1) {
  const a = typeof alpha === "number" && !Number.isNaN(alpha) ? Math.max(0, Math.min(1, alpha)) : 1;
  if (!rgb) return `rgba(0, 0, 0, ${a})`;
  return `rgba(${clampRgb(rgb.r)}, ${clampRgb(rgb.g)}, ${clampRgb(rgb.b)}, ${a})`;
}

/**
 * Default initial theme configuration
 * @returns {object}
 */
export function getDefaultThemeConfig() {
  return {
    preset: CURATED_PRESETS.DEFAULT_DARK,
    foundation: BASE_FOUNDATIONS.DARK,
  };
}

/**
 * Read the full persisted theme configuration safely across browser and SSR.
 * Automatically migrates legacy or custom format to a valid curated preset.
 * @returns {object}
 */
export function getStoredThemeConfig() {
  const fallback = getDefaultThemeConfig();
  if (typeof window === "undefined" || !window.localStorage) {
    return fallback;
  }
  try {
    const legacy = window.localStorage.getItem(THEME_KEY);
    const raw = window.localStorage.getItem(THEME_CONFIG_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        let foundation = parsed.foundation === BASE_FOUNDATIONS.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
        if (legacy === BASE_FOUNDATIONS.LIGHT || legacy === BASE_FOUNDATIONS.DARK) {
          foundation = legacy;
        }
        let matchedPreset = PRESET_CATALOG.find((p) => p.id === parsed.preset);
        if (matchedPreset && matchedPreset.foundation !== foundation) {
          matchedPreset = null;
        }
        const preset = matchedPreset
          ? matchedPreset.id
          : (foundation === BASE_FOUNDATIONS.LIGHT ? CURATED_PRESETS.DEFAULT_LIGHT : CURATED_PRESETS.DEFAULT_DARK);

        return {
          preset,
          foundation,
        };
      }
    }

    // Fallback: check legacy single theme key ("dark" | "light")
    if (legacy === THEMES.LIGHT) {
      return {
        preset: CURATED_PRESETS.DEFAULT_LIGHT,
        foundation: BASE_FOUNDATIONS.LIGHT,
      };
    }
    return fallback;
  } catch (_) {
    return fallback;
  }
}

/**
 * Save theme config to localStorage. Also updates legacy key for backward compatibility.
 * @param {object} config
 */
export function saveThemeConfig(config) {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    const payload = {
      preset: config.preset || CURATED_PRESETS.DEFAULT_DARK,
      foundation: config.foundation || BASE_FOUNDATIONS.DARK,
    };
    window.localStorage.setItem(THEME_CONFIG_KEY, JSON.stringify(payload));
    window.localStorage.setItem(THEME_KEY, payload.foundation);
  } catch (_) {
    // Ignore storage errors in restricted contexts
  }
}

/**
 * Properties to clean from root.style when setting presets to ensure zero style leakage
 */
const STALE_INLINE_PROPS = [
  "--accent", "--accent-muted", "--primary", "--accent-soft", "--border-hover", "--selection",
  "--secondary", "--text-dim", "--muted", "--text-faint", "--btn-outline-muted", "--border-soft",
  "--accent-2", "--accent-dim", "--accent-2-dim", "--accent-2-soft", "--accent-2-bright",
  "--bg", "--bg-deep", "--bg-code", "--editor", "--terminal", "--glass-editor-bg",
  "--surface", "--panel", "--bg-surface", "--bg-panel", "--bg-card", "--bg-elev",
  "--bg-secondary", "--bg-sidebar", "--sidebar", "--bg-header", "--bg-drawer",
  "--rail", "--chrome", "--glass-header-bg", "--glass-panel-bg",
];

/**
 * Apply full theme configuration to document DOM (datasets).
 * SSR-safe.
 * @param {object} config
 */
export function applyThemeConfig(config) {
  if (typeof document === "undefined" || !document.documentElement) return;
  const root = document.documentElement;
  const foundation = config.foundation === BASE_FOUNDATIONS.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
  const preset = config.preset || (foundation === BASE_FOUNDATIONS.LIGHT ? CURATED_PRESETS.DEFAULT_LIGHT : CURATED_PRESETS.DEFAULT_DARK);

  // Set foundation and preset on dataset
  if (root.dataset) {
    root.dataset.theme = foundation;
    root.dataset.themePreset = preset;
    delete root.dataset.themeMode;
  } else {
    root.setAttribute("data-theme", foundation);
    root.setAttribute("data-theme-preset", preset);
    root.removeAttribute("data-theme-mode");
  }

  // Clear any leftover inline custom overrides so preset CSS takes pure effect
  if (root.style && typeof root.style.removeProperty === "function") {
    for (const prop of STALE_INLINE_PROPS) {
      root.style.removeProperty(prop);
    }
  }
}

/**
 * Legacy getStoredTheme for backward compatibility.
 * @param {string} [fallback='dark']
 * @returns {string}
 */
export function getStoredTheme(fallback = THEMES.DARK) {
  if (typeof window === "undefined" || !window.localStorage) {
    return fallback;
  }
  try {
    const config = getStoredThemeConfig();
    return config.foundation || fallback;
  } catch (_) {
    return fallback;
  }
}

/**
 * Legacy applyTheme for backward compatibility.
 * @param {string} theme
 */
export function applyTheme(theme) {
  const current = getStoredThemeConfig();
  const foundation = theme === THEMES.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
  const updated = {
    ...current,
    foundation,
    preset: current.preset === CURATED_PRESETS.DEFAULT_DARK || current.preset === CURATED_PRESETS.DEFAULT_LIGHT
      ? (foundation === BASE_FOUNDATIONS.LIGHT ? CURATED_PRESETS.DEFAULT_LIGHT : CURATED_PRESETS.DEFAULT_DARK)
      : current.preset,
  };
  applyThemeConfig(updated);
  saveThemeConfig(updated);
}

/**
 * Initialize theme from stored preference (or fallback) and apply to DOM.
 * @param {string} [fallback='dark']
 * @returns {string} active foundation
 */
export function initTheme(fallback = THEMES.DARK) {
  const config = getStoredThemeConfig();
  applyThemeConfig(config);
  return config.foundation || fallback;
}

/**
 * Read the persisted wallpaper setting safely across browser and SSR environments.
 * @param {boolean} [fallback=true]
 * @returns {boolean}
 */
export function getStoredWallpaper(fallback = true) {
  if (typeof window === "undefined" || !window.localStorage) {
    return fallback;
  }
  try {
    const saved = window.localStorage.getItem(WALLPAPER_KEY);
    if (saved === "false" || saved === "disabled") return false;
    if (saved === "true" || saved === "enabled") return true;
    return fallback;
  } catch (_) {
    return fallback;
  }
}

/**
 * Apply wallpaper preference to document element dataset and persist in localStorage.
 * SSR-safe.
 * @param {boolean} enabled
 */
export function applyWallpaper(enabled) {
  const isEnabled = Boolean(enabled);
  if (typeof document !== "undefined" && document.documentElement) {
    if (document.documentElement.dataset) {
      document.documentElement.dataset.wallpaper = isEnabled ? "enabled" : "disabled";
    } else {
      document.documentElement.setAttribute("data-wallpaper", isEnabled ? "enabled" : "disabled");
    }
  }
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.setItem(WALLPAPER_KEY, isEnabled ? "enabled" : "disabled");
    } catch (_) {
      // Ignore storage errors in restricted contexts
    }
  }
}

/**
 * Initialize wallpaper preference from stored preference (or fallback) and apply to DOM.
 * @param {boolean} [fallback=true]
 * @returns {boolean} active wallpaper status
 */
export function initWallpaper(fallback = true) {
  const enabled = getStoredWallpaper(fallback);
  applyWallpaper(enabled);
  return enabled;
}

let sharedThemeState = null;

/**
 * Create reactive theme and wallpaper state for components.
 * Returns a shared reactive singleton by default so that all components (e.g. App.vue and AppearanceSettingsPanel)
 * stay in perfect synchronization without requiring full page reloads.
 * @param {boolean} [forceNew=false]
 */
export function createThemeState(forceNew = false) {
  if (sharedThemeState && !forceNew) {
    sharedThemeState.isWallpaperEnabled.value = getStoredWallpaper(true);
    return sharedThemeState;
  }

  const initialConfig = getStoredThemeConfig();
  applyThemeConfig(initialConfig);

  const themeConfig = reactive({
    preset: initialConfig.preset,
    foundation: initialConfig.foundation,
  });

  const isDark = computed(() => themeConfig.foundation === BASE_FOUNDATIONS.DARK);
  const initialWallpaper = initWallpaper(true);
  const isWallpaperEnabled = ref(initialWallpaper);

  function persist() {
    applyThemeConfig(themeConfig);
    saveThemeConfig(themeConfig);
  }

  function setTheme(theme) {
    themeConfig.foundation = theme === THEMES.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
    if (themeConfig.preset === CURATED_PRESETS.DEFAULT_DARK && theme === THEMES.LIGHT) {
      themeConfig.preset = CURATED_PRESETS.DEFAULT_LIGHT;
    } else if (themeConfig.preset === CURATED_PRESETS.DEFAULT_LIGHT && theme === THEMES.DARK) {
      themeConfig.preset = CURATED_PRESETS.DEFAULT_DARK;
    }
    persist();
  }

  function toggleTheme() {
    setTheme(isDark.value ? THEMES.LIGHT : THEMES.DARK);
  }

  function setPreset(presetId) {
    const found = PRESET_CATALOG.find((p) => p.id === presetId);
    if (!found) return;
    themeConfig.preset = found.id;
    themeConfig.foundation = found.foundation;
    persist();
  }

  function resetTheme() {
    const def = getDefaultThemeConfig();
    themeConfig.preset = def.preset;
    themeConfig.foundation = def.foundation;
    persist();
  }

  function setWallpaper(enabled) {
    isWallpaperEnabled.value = Boolean(enabled);
    applyWallpaper(isWallpaperEnabled.value);
  }

  function toggleWallpaper() {
    setWallpaper(!isWallpaperEnabled.value);
  }

  const instance = {
    isDark,
    themeConfig,
    setTheme,
    toggleTheme,
    setPreset,
    resetTheme,
    isWallpaperEnabled,
    setWallpaper,
    toggleWallpaper,
    PRESET_CATALOG,
  };

  if (!forceNew) {
    sharedThemeState = instance;
  }
  return instance;
}
