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
  assert.ok(PRESET_CATALOG.length >= 8);

  const ids = PRESET_CATALOG.map((p) => p.id);
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
  }
});

test("themeService: Default configuration and storage fallback", () => {
  const def = getDefaultThemeConfig();
  assert.equal(def.mode, THEME_MODES.PRESET);
  assert.equal(def.foundation, BASE_FOUNDATIONS.DARK);
  assert.ok(def.customColors.primary);
  assert.ok(def.customColors.secondary);
  assert.ok(def.customColors.accent);
});

test("themeService: Full browser lifecycle with presets and custom sliders", () => {
  const mockStorage = new Map();
  const mockDataset = {};
  const mockStyleProperties = new Map();

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
    // 1. Inisialisasi awal tanpa storage
    const state = createThemeState();
    assert.equal(state.isDark.value, true);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(state.themeConfig.mode, THEME_MODES.PRESET);

    // 2. Pilih preset Tokyo Night Dark
    state.setPreset(CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(state.themeConfig.foundation, "dark");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.TOKYO_NIGHT_DARK);
    assert.equal(mockDataset.theme, "dark");
    assert.ok(mockStorage.has(THEME_CONFIG_KEY));

    // 3. Pilih preset Nord Light
    state.setPreset(CURATED_PRESETS.NORD_LIGHT);
    assert.equal(state.themeConfig.preset, CURATED_PRESETS.NORD_LIGHT);
    assert.equal(state.themeConfig.foundation, "light");
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.NORD_LIGHT);
    assert.equal(mockDataset.theme, "light");
    assert.equal(state.isDark.value, false);

    // 4. Pilih High Contrast Dark
    state.setPreset(CURATED_PRESETS.HIGH_CONTRAST_DARK);
    assert.equal(mockDataset.themePreset, CURATED_PRESETS.HIGH_CONTRAST_DARK);
    assert.equal(mockDataset.theme, "dark");

    // 5. Beralih ke Mode Custom
    state.setCustomMode();
    assert.equal(state.themeConfig.mode, THEME_MODES.CUSTOM);
    assert.equal(mockDataset.themeMode, "custom");
    assert.equal(mockDataset.themePreset, undefined);

    // Ubah foundation custom ke Light
    state.setCustomFoundation("light");
    assert.equal(state.themeConfig.foundation, "light");
    assert.equal(mockDataset.theme, "light");

    // Atur slider custom RGB untuk primary, secondary, accent
    state.updateCustomColor("accent", { r: 255, g: 64, b: 128 });
    state.updateCustomColor("primary", { r: 32, g: 128, b: 240 });
    state.updateCustomColor("secondary", { r: 80, g: 90, b: 100 });

    assert.equal(mockStyleProperties.get("--accent"), "#2080f0");
    assert.equal(mockStyleProperties.get("--primary"), "#2080f0");
    assert.equal(mockStyleProperties.get("--secondary"), "#505a64");
    assert.equal(mockStyleProperties.get("--text-dim"), "#505a64");
    assert.equal(mockStyleProperties.get("--accent-2"), "#ff4080");
    assert.equal(mockStyleProperties.get("--accent-soft"), "rgba(32, 128, 240, 0.16)");

    // 6. Reset to default
    state.resetTheme();
    assert.equal(state.themeConfig.mode, THEME_MODES.PRESET);
    assert.equal(state.themeConfig.foundation, "dark");
    assert.equal(state.isDark.value, true);
    // Custom inline styles must be cleaned up on reset
    assert.equal(mockStyleProperties.has("--accent"), false);
    assert.equal(mockStyleProperties.has("--accent-dim"), false);
  } finally {
    delete globalThis.window;
    delete globalThis.document;
  }
});
