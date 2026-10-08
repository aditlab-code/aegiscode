import { computed, reactive, ref } from "vue";

export const THEME_KEY = "aegis-theme";
export const THEME_CONFIG_KEY = "aegis-theme-config";
export const WALLPAPER_KEY = "aegis-wallpaper";

export const THEMES = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});

export const THEME_MODES = Object.freeze({
  PRESET: "preset",
  CUSTOM: "custom",
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
    preview: { primary: "#b5a1ed", secondary: "#bcbcca", bg: "#181922" },
  },
  {
    id: CURATED_PRESETS.DEFAULT_LIGHT,
    name: "Aegis Orbit Light",
    family: "Aegis",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#8261bb", secondary: "#555168", bg: "#eae5f4" },
  },
  {
    id: CURATED_PRESETS.TOKYO_NIGHT_DARK,
    name: "Tokyo Night",
    family: "Tokyo Night",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#7aa2f7", secondary: "#bb9af7", bg: "#1a1b26" },
  },
  {
    id: CURATED_PRESETS.TOKYO_NIGHT_LIGHT,
    name: "Tokyo Night Light",
    family: "Tokyo Night",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#34548a", secondary: "#5a4a78", bg: "#d5d6db" },
  },
  {
    id: CURATED_PRESETS.NORD_DARK,
    name: "Nordic Dark",
    family: "Nord",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#88c0d0", secondary: "#81a1c1", bg: "#2e3440" },
  },
  {
    id: CURATED_PRESETS.NORD_LIGHT,
    name: "Nordic Light",
    family: "Nord",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#5e81ac", secondary: "#81a1c1", bg: "#eceff4" },
  },
  {
    id: CURATED_PRESETS.ATOM_DARK,
    name: "Atom One Dark",
    family: "Atom One",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#61afef", secondary: "#c678dd", bg: "#282c34" },
  },
  {
    id: CURATED_PRESETS.ATOM_LIGHT,
    name: "Atom One Light",
    family: "Atom One",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#4078f2", secondary: "#a626a4", bg: "#fafafa" },
  },
  {
    id: CURATED_PRESETS.HIGH_CONTRAST_DARK,
    name: "High Contrast Dark",
    family: "High Contrast",
    variant: "dark",
    foundation: BASE_FOUNDATIONS.DARK,
    preview: { primary: "#00ffff", secondary: "#ffff00", bg: "#000000" },
  },
  {
    id: CURATED_PRESETS.HIGH_CONTRAST_LIGHT,
    name: "High Contrast Light",
    family: "High Contrast",
    variant: "light",
    foundation: BASE_FOUNDATIONS.LIGHT,
    preview: { primary: "#0000ee", secondary: "#990000", bg: "#ffffff" },
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
  if (!rgb) return `rgba(0, 0, 0, ${alpha})`;
  return `rgba(${clampRgb(rgb.r)}, ${clampRgb(rgb.g)}, ${clampRgb(rgb.b)}, ${alpha})`;
}

/**
 * Default color channels for custom mode
 */
export const DEFAULT_CUSTOM_COLORS = Object.freeze({
  dark: {
    primary: { r: 181, g: 161, b: 237 },    // #b5a1ed
    secondary: { r: 188, g: 188, b: 202 },  // #bcbcca
    accent: { r: 193, g: 164, b: 223 },     // #c1a4df
  },
  light: {
    primary: { r: 130, g: 97, b: 187 },     // #8261bb
    secondary: { r: 85, g: 81, b: 104 },    // #555168
    accent: { r: 154, g: 96, b: 173 },      // #9a60ad
  },
});

/**
 * Default initial theme configuration
 * @returns {object}
 */
export function getDefaultThemeConfig() {
  return {
    mode: THEME_MODES.PRESET,
    preset: CURATED_PRESETS.DEFAULT_DARK,
    foundation: BASE_FOUNDATIONS.DARK,
    customColors: {
      primary: { ...DEFAULT_CUSTOM_COLORS.dark.primary },
      secondary: { ...DEFAULT_CUSTOM_COLORS.dark.secondary },
      accent: { ...DEFAULT_CUSTOM_COLORS.dark.accent },
    },
  };
}

/**
 * Read the full persisted theme configuration safely across browser and SSR.
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
        if (legacy === THEMES.LIGHT) foundation = BASE_FOUNDATIONS.LIGHT;
        else if (legacy === THEMES.DARK) foundation = BASE_FOUNDATIONS.DARK;

        let preset = typeof parsed.preset === "string" ? parsed.preset : CURATED_PRESETS.DEFAULT_DARK;
        if (preset === CURATED_PRESETS.DEFAULT_DARK && foundation === BASE_FOUNDATIONS.LIGHT) {
          preset = CURATED_PRESETS.DEFAULT_LIGHT;
        } else if (preset === CURATED_PRESETS.DEFAULT_LIGHT && foundation === BASE_FOUNDATIONS.DARK) {
          preset = CURATED_PRESETS.DEFAULT_DARK;
        }

        return {
          mode: parsed.mode === THEME_MODES.CUSTOM ? THEME_MODES.CUSTOM : THEME_MODES.PRESET,
          preset,
          foundation,
          customColors: {
            primary: {
              r: clampRgb(parsed.customColors?.primary?.r ?? DEFAULT_CUSTOM_COLORS.dark.primary.r),
              g: clampRgb(parsed.customColors?.primary?.g ?? DEFAULT_CUSTOM_COLORS.dark.primary.g),
              b: clampRgb(parsed.customColors?.primary?.b ?? DEFAULT_CUSTOM_COLORS.dark.primary.b),
            },
            secondary: {
              r: clampRgb(parsed.customColors?.secondary?.r ?? DEFAULT_CUSTOM_COLORS.dark.secondary.r),
              g: clampRgb(parsed.customColors?.secondary?.g ?? DEFAULT_CUSTOM_COLORS.dark.secondary.g),
              b: clampRgb(parsed.customColors?.secondary?.b ?? DEFAULT_CUSTOM_COLORS.dark.secondary.b),
            },
            accent: {
              r: clampRgb(parsed.customColors?.accent?.r ?? DEFAULT_CUSTOM_COLORS.dark.accent.r),
              g: clampRgb(parsed.customColors?.accent?.g ?? DEFAULT_CUSTOM_COLORS.dark.accent.g),
              b: clampRgb(parsed.customColors?.accent?.b ?? DEFAULT_CUSTOM_COLORS.dark.accent.b),
            },
          },
        };
      }
    }

    // Fallback: check legacy single theme key ("dark" | "light")
    if (legacy === THEMES.LIGHT) {
      return {
        ...fallback,
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
    window.localStorage.setItem(THEME_CONFIG_KEY, JSON.stringify(config));
    // Keep legacy key updated
    window.localStorage.setItem(THEME_KEY, config.foundation || THEMES.DARK);
  } catch (_) {
    // Ignore storage errors in restricted contexts
  }
}

/**
 * Apply full theme configuration to document DOM (datasets and CSS variables).
 * SSR-safe.
 * @param {object} config
 */
export function applyThemeConfig(config) {
  if (typeof document === "undefined" || !document.documentElement) return;
  const root = document.documentElement;
  const foundation = config.foundation === BASE_FOUNDATIONS.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;

  // Set foundation on dataset
  if (root.dataset) {
    root.dataset.theme = foundation;
    root.dataset.themeMode = config.mode;
    if (config.mode === THEME_MODES.PRESET && config.preset) {
      root.dataset.themePreset = config.preset;
    } else {
      delete root.dataset.themePreset;
    }
  } else {
    root.setAttribute("data-theme", foundation);
    root.setAttribute("data-theme-mode", config.mode);
    if (config.mode === THEME_MODES.PRESET && config.preset) {
      root.setAttribute("data-theme-preset", config.preset);
    } else {
      root.removeAttribute("data-theme-preset");
    }
  }

  // Handle CSS variable overrides
  if (root.style) {
    if (config.mode === THEME_MODES.CUSTOM && config.customColors) {
      const { primary, secondary, accent } = config.customColors;
      const primaryHex = rgbToHex(primary);
      const secondaryHex = rgbToHex(secondary);
      const accentHex = rgbToHex(accent);

      if (typeof root.style.setProperty === "function") {
        // 1. Primary Colors (Interactive buttons, active states, branding highlights)
        root.style.setProperty("--accent", primaryHex);
        root.style.setProperty("--accent-muted", primaryHex);
        root.style.setProperty("--primary", primaryHex);
        root.style.setProperty("--accent-soft", rgbaString(primary, 0.16));
        root.style.setProperty("--border-hover", rgbaString(primary, 0.4));
        root.style.setProperty("--selection", rgbaString(primary, 0.22));

        // 2. Secondary Colors (Muted text, passive borders, subtle chrome)
        root.style.setProperty("--secondary", secondaryHex);
        root.style.setProperty("--text-dim", secondaryHex);
        root.style.setProperty("--muted", rgbaString(secondary, 0.75));
        root.style.setProperty("--btn-outline-muted", rgbaString(secondary, 0.35));
        root.style.setProperty("--border-soft", rgbaString(secondary, 0.2));

        // 3. Accent Colors (Secondary accent, tags, badge highlights)
        root.style.setProperty("--accent-2", accentHex);
        root.style.setProperty("--accent-dim", accentHex);
        root.style.setProperty("--accent-2-dim", accentHex);
        root.style.setProperty("--accent-2-soft", rgbaString(accent, 0.18));
        root.style.setProperty("--accent-2-bright", accentHex);
      }
    } else if (typeof root.style.removeProperty === "function") {
      // Clear inline custom overrides to let preset or base theme stylesheet rules take effect
      const customProps = [
        "--accent", "--accent-muted", "--primary", "--accent-soft", "--border-hover", "--selection",
        "--secondary", "--text-dim", "--muted", "--btn-outline-muted", "--border-soft",
        "--accent-2", "--accent-dim", "--accent-2-dim", "--accent-2-soft", "--accent-2-bright",
      ];
      for (const prop of customProps) {
        root.style.removeProperty(prop);
      }
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
    // if using default preset, keep it aligned with foundation
    preset: current.mode === THEME_MODES.PRESET && (current.preset === CURATED_PRESETS.DEFAULT_DARK || current.preset === CURATED_PRESETS.DEFAULT_LIGHT)
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

/**
 * Create reactive theme and wallpaper state for components.
 */
export function createThemeState() {
  const initialConfig = getStoredThemeConfig();
  applyThemeConfig(initialConfig);

  const themeConfig = reactive({
    mode: initialConfig.mode,
    preset: initialConfig.preset,
    foundation: initialConfig.foundation,
    customColors: {
      primary: { ...initialConfig.customColors.primary },
      secondary: { ...initialConfig.customColors.secondary },
      accent: { ...initialConfig.customColors.accent },
    },
  });

  const isDark = computed(() => themeConfig.foundation === BASE_FOUNDATIONS.DARK);
  const initialWallpaper = initWallpaper(true);
  const isWallpaperEnabled = ref(initialWallpaper);

  function persist() {
    saveThemeConfig(themeConfig);
    applyThemeConfig(themeConfig);
  }

  function setTheme(theme) {
    themeConfig.foundation = theme === THEMES.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
    if (themeConfig.mode === THEME_MODES.PRESET) {
      if (themeConfig.preset === CURATED_PRESETS.DEFAULT_DARK && theme === THEMES.LIGHT) {
        themeConfig.preset = CURATED_PRESETS.DEFAULT_LIGHT;
      } else if (themeConfig.preset === CURATED_PRESETS.DEFAULT_LIGHT && theme === THEMES.DARK) {
        themeConfig.preset = CURATED_PRESETS.DEFAULT_DARK;
      }
    }
    persist();
  }

  function toggleTheme() {
    setTheme(isDark.value ? THEMES.LIGHT : THEMES.DARK);
  }

  function setPreset(presetId) {
    const found = PRESET_CATALOG.find((p) => p.id === presetId);
    themeConfig.mode = THEME_MODES.PRESET;
    themeConfig.preset = presetId;
    if (found) {
      themeConfig.foundation = found.foundation;
    }
    persist();
  }

  function setCustomMode() {
    themeConfig.mode = THEME_MODES.CUSTOM;
    persist();
  }

  function setCustomFoundation(foundation) {
    themeConfig.mode = THEME_MODES.CUSTOM;
    themeConfig.foundation = foundation === BASE_FOUNDATIONS.LIGHT ? BASE_FOUNDATIONS.LIGHT : BASE_FOUNDATIONS.DARK;
    persist();
  }

  function updateCustomColor(channel, colorObj) {
    if (!themeConfig.customColors[channel]) return;
    themeConfig.mode = THEME_MODES.CUSTOM;
    themeConfig.customColors[channel].r = clampRgb(colorObj.r);
    themeConfig.customColors[channel].g = clampRgb(colorObj.g);
    themeConfig.customColors[channel].b = clampRgb(colorObj.b);
    persist();
  }

  function resetTheme() {
    const def = getDefaultThemeConfig();
    themeConfig.mode = def.mode;
    themeConfig.preset = def.preset;
    themeConfig.foundation = def.foundation;
    themeConfig.customColors.primary = { ...def.customColors.primary };
    themeConfig.customColors.secondary = { ...def.customColors.secondary };
    themeConfig.customColors.accent = { ...def.customColors.accent };
    persist();
  }

  function setWallpaper(enabled) {
    isWallpaperEnabled.value = Boolean(enabled);
    applyWallpaper(isWallpaperEnabled.value);
  }

  function toggleWallpaper() {
    setWallpaper(!isWallpaperEnabled.value);
  }

  return {
    isDark,
    themeConfig,
    setTheme,
    toggleTheme,
    setPreset,
    setCustomMode,
    setCustomFoundation,
    updateCustomColor,
    resetTheme,
    isWallpaperEnabled,
    setWallpaper,
    toggleWallpaper,
    PRESET_CATALOG,
  };
}
