import { ref } from "vue";

export const THEME_KEY = "aegis-theme";
export const WALLPAPER_KEY = "aegis-wallpaper";

export const THEMES = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});

/**
 * Read the persisted theme setting safely across browser and SSR environments.
 * @param {string} [fallback='dark']
 * @returns {string}
 */
export function getStoredTheme(fallback = THEMES.DARK) {
  if (typeof window === "undefined" || !window.localStorage) {
    return fallback;
  }
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === THEMES.LIGHT) return THEMES.LIGHT;
    if (saved === THEMES.DARK) return THEMES.DARK;
    return fallback;
  } catch (_) {
    return fallback;
  }
}

/**
 * Apply theme to document element dataset and persist in localStorage.
 * SSR-safe: ignores DOM/storage operations when executed in Node context.
 * @param {string} theme
 */
export function applyTheme(theme) {
  if (typeof document !== "undefined" && document.documentElement) {
    if (document.documentElement.dataset) {
      document.documentElement.dataset.theme = theme;
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
  }
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch (_) {
      // Ignore storage errors in restricted contexts
    }
  }
}

/**
 * Initialize theme from stored preference (or fallback) and apply to DOM.
 * @param {string} [fallback='dark']
 * @returns {string} active theme
 */
export function initTheme(fallback = THEMES.DARK) {
  const theme = getStoredTheme(fallback);
  applyTheme(theme);
  return theme;
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
 * SSR-safe: ignores DOM/storage operations when executed in Node context.
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
 * @returns {{
 *   isDark: import("vue").Ref<boolean>,
 *   setTheme: (theme: string) => void,
 *   toggleTheme: () => void,
 *   isWallpaperEnabled: import("vue").Ref<boolean>,
 *   setWallpaper: (enabled: boolean) => void,
 *   toggleWallpaper: () => void
 * }}
 */
export function createThemeState() {
  const initial = initTheme(THEMES.DARK);
  const isDark = ref(initial === THEMES.DARK);
  const initialWallpaper = initWallpaper(true);
  const isWallpaperEnabled = ref(initialWallpaper);

  function setTheme(theme) {
    isDark.value = theme === THEMES.DARK;
    applyTheme(theme);
  }

  function toggleTheme() {
    setTheme(isDark.value ? THEMES.LIGHT : THEMES.DARK);
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
    setTheme,
    toggleTheme,
    isWallpaperEnabled,
    setWallpaper,
    toggleWallpaper,
  };
}
