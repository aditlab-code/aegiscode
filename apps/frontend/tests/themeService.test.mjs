import test from "node:test";
import assert from "node:assert/strict";

import {
  THEME_KEY,
  THEME_CONFIG_KEY,
  THEMES,
  THEME_MODES,
  BASE_FOUNDATIONS,
  CURATED_PRESETS,
  PRESET_CATALOG,
  clampRgb,
  rgbToHex,
  hexToRgb,
  rgbaString,
  getDefaultThemeConfig,
  getStoredThemeConfig,
  saveThemeConfig,
  applyThemeConfig,
  getStoredTheme,
  applyTheme,
  initTheme,
  createThemeState,
} from "../src/services/themeService.js";

test("themeService: RGB math and clamping helpers", () => {
  // Clamping
  assert.equal(clampRgb(-10), 0);
  assert.equal(clampRgb(300), 255);
  assert.equal(clampRgb(128), 128);
  assert.equal(clampRgb("200"), 200);
  assert.equal(clampRgb("invalid"), 0);

  // rgbToHex
  assert.equal(rgbToHex({ r: 255, g: 0, b: 128 }), "#ff0080");
  assert.equal(rgbToHex({ r: 0, g: 0, b: 0 }), "#000000");
  assert.equal(rgbToHex(null), "#000000");

  // hexToRgb
  assert.deepEqual(hexToRgb("#ff0080"), { r: 255, g: 0, b: 128 });
  assert.deepEqual(hexToRgb("ff0080"), { r: 255, g: 0, b: 128 });
  assert.deepEqual(hexToRgb("#fff"), { r: 255, g: 255, b: 255 });
  assert.deepEqual(hexToRgb("invalid"), { r: 0, g: 0, b: 0 });

  // rgbaString
  assert.equal(rgbaString({ r: 100, g: 150, b: 200 }, 0.5), "rgba(100, 150, 200, 0.5)");
  assert.equal(rgbaString(null, 1), "rgba(0, 0, 0, 1)");
});

test("themeService: Curated presets catalog completeness", () => {
  assert.ok(Array.isArray(PRESET_CATALOG));
  assert.equal(PRESET_CATALOG.length, 10);

  const ids = PRESET_CATALOG.map((p) => p.id);
  assert.ok(ids.includes(CURATED_PRESETS.DEFAULT_DARK));
  assert.ok(ids.includes(CURATED_PRESETS.DEFAULT_LIGHT));
  assert.ok(ids.includes(CURATED_PRESETS.TOKYO_NIGHT_DARK));
  assert.ok(ids.includes(CURATED_PRESETS.TOKYO_NIGHT_LIGHT));
  assert.ok(ids.includes(CURATED_PRESETS.NORD_DARK));
  assert.ok(ids.includes(CURATED_PRESETS.NORD_LIGHT));
  assert.ok(ids.includes(CURATED_PRESETS.ATOM_DARK));
  assert.ok(ids.includes(CURATED_PRESETS.ATOM_LIGHT));
  assert.ok(ids.includes(CURATED_PRESETS.HIGH_CONTRAST_DARK));
  assert.ok(ids.includes(CURATED_PRESETS.HIGH_CONTRAST_LIGHT));

  for (const preset of PRESET_CATALOG) {
    assert.ok(preset.name, `Preset ${preset.id} must have a name`);
    assert.ok(preset.foundation === "dark" || preset.foundation === "light");
    assert.ok(preset.preview.primary.startsWith("#"));
    assert.ok(preset.preview.secondary.startsWith("#"));
    assert.ok(preset.preview.accent.startsWith("#"));
    assert.ok(preset.preview.bg.startsWith("#"));
    assert.ok(preset.preview.surface.startsWith("#"));
  }
});

test("themeService: Default configuration and migration from legacy custom format", () => {
  const def = getDefaultThemeConfig();
  assert.equal(def.preset, CURATED_PRESETS.DEFAULT_DARK);
  assert.equal(def.foundation, BASE_FOUNDATIONS.DARK);

  const mockStorage = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (k) => mockStorage.get(k) || null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
      removeItem: (k) => mockStorage.delete(k),
    },
  };

  try {
    // 1. Fallback when storage is empty
    const storedDefault = getStoredThemeConfig();
    assert.equal(storedDefault.preset, CURATED_PRESETS.DEFAULT_DARK);
    assert.equal(storedDefault.foundation, BASE_FOUNDATIONS.DARK);

    // 2. Migration: legacy custom mode JSON in localStorage should gracefully map to valid preset
    mockStorage.set(THEME_CONFIG_KEY, JSON.stringify({
      mode: "custom",
      foundation: "light",
      customColors: { primary: { r: 10, g: 20, b: 30 } },
    }));
    const migratedLight = getStoredThemeConfig();
    assert.equal(migratedLight.preset, CURATED_PRESETS.DEFAULT_LIGHT);
    assert.equal(migratedLight.foundation, BASE_FOUNDATIONS.LIGHT);

    // 3. Migration: legacy single key "dark" / "light"
    mockStorage.delete(THEME_CONFIG_KEY);
    mockStorage.set(THEME_KEY, "light");
    const legacyLight = getStoredThemeConfig();
    assert.equal(legacyLight.preset, CURATED_PRESETS.DEFAULT_LIGHT);
    assert.equal(legacyLight.foundation, BASE_FOUNDATIONS.LIGHT);
  } finally {
    delete globalThis.window;
  }
});

test("themeService: Full browser lifecycle with unified template presets", () => {
  const mockStorage = new Map();
  const mockDataset = {};
  const mockStyleProperties = new Map();

  // Add dummy stale properties to test cleanup
  mockStyleProperties.set("--accent", "#ffffff");
  mockStyleProperties.set("--bg", "#000000");

  globalThis.window = {
    localStorage: {
      getItem: (k) => mockStorage.get(k) || null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
      removeItem: (k) => mockStorage.delete(k),
    },
  };

  globalThis.document = {
    documentElement: {
      dataset: mockDataset,
      style: {
        setProperty: (k, v) => mockStyleProperties.set(k, String(v)),
        removeProperty: (k) => mockStyleProperties.delete(k),
        getPropertyValue: (k) => mockStyleProperties.get(k) || "",
      },
    },
  };

  try {
    // 1. Initial creation
    const state = createThemeState(true);
    assert.equal(state.isDark.value, true);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.DEFAULT_DARK);
    // Stale inline properties must be cleared on applyThemeConfig
    assert.equal(mockStyleProperties.has("--accent"), false);
    assert.equal(mockStyleProperties.has("--bg"), false);

    // 2. Select Tokyo Night Dark
    state.setPreset(CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(state.themeConfig.foundation, "dark");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(mockDataset.theme, "dark");
    assert.ok(mockStorage.has(THEME_CONFIG_KEY));

    // 3. Select Nord Light
    state.setPreset(CURATED_PRESETS.NORD_LIGHT);
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.NORD_LIGHT);
    assert.equal(state.themeConfig.foundation, "light");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.NORD_LIGHT);
    assert.equal(mockDataset.theme, "light");
    assert.equal(state.isDark.value, false);

    // 4. Select High Contrast Dark
    state.setPreset(CURATED_PRESETS.HIGH_CONTRAST_DARK);
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.HIGH_CONTRAST_DARK);
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.HIGH_CONTRAST_DARK);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(state.isDark.value, true);

    // 5. Reset to default
    state.resetTheme();
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.DEFAULT_DARK);
    assert.equal(state.themeConfig.foundation, "dark");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.DEFAULT_DARK);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(state.isDark.value, true);

    // 6. Test shared reactive singleton across components
    const firstInstance = createThemeState();
    const secondInstance = createThemeState();
    assert.equal(firstInstance, secondInstance, "createThemeState must return shared singleton instance");

    // 7. Toggle wallpaper
    const initialWp = state.isWallpaperEnabled.value;
    state.toggleWallpaper();
    assert.equal(state.isWallpaperEnabled.value, !initialWp);
  } finally {
    delete globalThis.window;
    delete globalThis.document;
  }
});
