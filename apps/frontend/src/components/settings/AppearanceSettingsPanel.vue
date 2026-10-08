<script setup>
/**
 * AppearanceSettingsPanel.vue — Unified Design
 *
 * Tab pengaturan Appearance & Theming IDE AEGIS yang selaras dengan
 * standar Unified Settings (seperti EditorSettingsPanel & GlobalSettingsPanel):
 * 1. Card & Header terpadu (<AppCard variant="panel" class="settings-panel">).
 * 2. Header dengan title terpadu dan aksi Reset to Defaults di panel-actions.
 * 3. Scope banner & sub-section bergaris pemisah standar (.ap-sub-divider).
 * 4. Mode Presets Kurasi & Mode Custom RGB Sliders (Primary, Secondary, Accent).
 * 5. SVG icons murni (zero emoji) dan live preview instan.
 */
import { computed } from "vue";
import {
  createThemeState,
  PRESET_CATALOG,
  THEME_MODES,
  BASE_FOUNDATIONS,
  CURATED_PRESETS,
  rgbToHex,
  rgbaString,
} from "../../services/themeService.js";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const themeState = createThemeState();
const themeConfig = themeState.themeConfig;

const isPresetMode = computed(() => themeConfig.mode === THEME_MODES.PRESET);
const isCustomMode = computed(() => themeConfig.mode === THEME_MODES.CUSTOM);

// Swatches & Color Formats for Custom Palette
const primaryHex = computed(() => rgbToHex(themeConfig.customColors.primary));
const secondaryHex = computed(() => rgbToHex(themeConfig.customColors.secondary));
const accentHex = computed(() => rgbToHex(themeConfig.customColors.accent));

function selectPreset(presetId) {
  themeState.setPreset(presetId);
}

function switchToCustom() {
  themeState.setCustomMode();
}

function switchToPresets() {
  if (themeConfig.mode !== THEME_MODES.PRESET) {
    themeState.setPreset(themeConfig.preset || CURATED_PRESETS.DEFAULT_DARK);
  }
}

function setCustomBase(foundation) {
  themeState.setCustomFoundation(foundation);
}

function onRgbChange(channel, colorKey, value) {
  const current = { ...themeConfig.customColors[channel] };
  current[colorKey] = Number(value);
  themeState.updateCustomColor(channel, current);
}

function handleReset() {
  if (window.confirm("Kembalikan tema ke setelan default Aegis Orbit?")) {
    themeState.resetTheme();
  }
}
</script>

<template>
  <AppCard variant="panel" class="settings-panel appearance-panel-root">
    <!-- Unified Panel Header -->
    <template #header>
      <span class="title">Appearance & Themes</span>
      <div class="panel-actions">
        <AppButton
          variant="ghost"
          size="sm"
          title="Kembalikan seluruh tema ke setelan default"
          @click="handleReset"
        >
          Reset to Defaults
        </AppButton>
      </div>
    </template>

    <div class="panel-body">
      <!-- Scope Banner (Identik dengan standar Unified Settings) -->
      <div class="ap-scope">
        <span class="ap-scope-badge">Workspace Theming</span>
        <span class="ap-scope-note">
          Preferensi tema otomatis tersimpan di <span class="mono">localStorage</span> &rarr;
          <span class="mono">aegis-theme-config</span>.
        </span>
      </div>

      <!-- Sub-Section 1: Theme Mode Switcher -->
      <div class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Theme Mode</div>
          <div class="ap-sub-desc">
            Pilih antara palet warna kurasi siap pakai atau sesuaikan sendiri menggunakan slider kanal RGB.
          </div>
        </div>

        <div class="ap-mode-pills">
          <button
            type="button"
            class="ap-mode-pill-btn"
            :class="{ active: isPresetMode }"
            @click="switchToPresets"
          >
            <svg class="ap-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/>
              <circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/>
              <circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>
              <circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/>
              <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.9 0 1.6-.7 1.6-1.6 0-.4-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1 0-.9.7-1.6 1.6-1.6H16c3.3 0 6-2.7 6-6 0-5.5-4.5-10-10-10z"/>
            </svg>
            <span>Curated Presets</span>
          </button>

          <button
            type="button"
            class="ap-mode-pill-btn"
            :class="{ active: isCustomMode }"
            @click="switchToCustom"
          >
            <svg class="ap-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="4" y1="21" x2="4" y2="14"/>
              <line x1="4" y1="10" x2="4" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12" y2="3"/>
              <line x1="20" y1="21" x2="20" y2="16"/>
              <line x1="20" y1="12" x2="20" y2="3"/>
              <line x1="1" y1="14" x2="7" y2="14"/>
              <line x1="9" y1="8" x2="15" y2="8"/>
              <line x1="17" y1="16" x2="23" y2="16"/>
            </svg>
            <span>Custom RGB Sliders</span>
          </button>
        </div>
      </div>

      <div class="ap-sub-divider"></div>

      <!-- Sub-Section 2: Curated Presets Selection -->
      <div v-if="isPresetMode" class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Curated Color Presets</div>
          <div class="ap-sub-desc">
            Pilihan palet visual teruji dengan rasio kontras seimbang untuk kenyamanan ergonomi saat coding.
          </div>
        </div>

        <div class="presets-grid">
          <div
            v-for="preset in PRESET_CATALOG"
            :key="preset.id"
            class="preset-card"
            :class="{
              active: themeConfig.preset === preset.id,
              'is-light': preset.variant === 'light',
            }"
            role="button"
            tabindex="0"
            @click="selectPreset(preset.id)"
            @keydown.enter="selectPreset(preset.id)"
          >
            <div class="preset-card-top">
              <span class="preset-name">{{ preset.name }}</span>
              <span class="preset-badge" :class="preset.variant">
                {{ preset.variant === 'dark' ? 'Dark' : 'Light' }}
              </span>
            </div>

            <div class="preset-color-strip">
              <span
                class="color-dot"
                :style="{ backgroundColor: preset.preview.bg }"
                title="Background"
              />
              <span
                class="color-dot"
                :style="{ backgroundColor: preset.preview.primary }"
                title="Primary"
              />
              <span
                class="color-dot"
                :style="{ backgroundColor: preset.preview.secondary }"
                title="Secondary"
              />
            </div>

            <div v-if="themeConfig.preset === preset.id" class="active-indicator">
              <svg class="active-check-svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>Aktif</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Sub-Section 2: Custom RGB Palette Generator -->
      <div v-else class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Custom Palette Generator</div>
          <div class="ap-sub-desc">
            Sesuaikan warna antarmuka IDE. Pilih fondasi kontras Dark/Light, lalu tentukan warna Primary, Secondary, dan Accent melalui slider RGB.
          </div>
        </div>

        <!-- Foundation Switcher -->
        <div class="foundation-selector-group">
          <label class="group-label">Base Foundation:</label>
          <div class="foundation-options">
            <button
              type="button"
              class="foundation-btn"
              :class="{ active: themeConfig.foundation === BASE_FOUNDATIONS.DARK }"
              @click="setCustomBase(BASE_FOUNDATIONS.DARK)"
            >
              <svg class="ap-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
              <span>Dark Foundation</span>
            </button>
            <button
              type="button"
              class="foundation-btn"
              :class="{ active: themeConfig.foundation === BASE_FOUNDATIONS.LIGHT }"
              @click="setCustomBase(BASE_FOUNDATIONS.LIGHT)"
            >
              <svg class="ap-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
              <span>Light Foundation</span>
            </button>
          </div>
        </div>

        <!-- Sliders List -->
        <div class="sliders-container">
          <!-- 1. Primary Color -->
          <div class="color-slider-block">
            <div class="slider-block-header">
              <div class="header-info">
                <span class="channel-title">Primary Color</span>
                <span class="channel-sub">Mengontrol tombol aksi utama, active tabs, status aktif, dan brand highlight</span>
              </div>
              <div class="swatch-preview">
                <span class="swatch-box" :style="{ backgroundColor: primaryHex }" />
                <code class="hex-text">{{ primaryHex }}</code>
              </div>
            </div>

            <div class="rgb-channel-row">
              <div class="rgb-track">
                <span class="channel-tag r">R</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-red"
                  :value="themeConfig.customColors.primary.r"
                  @input="onRgbChange('primary', 'r', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.primary.r }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag g">G</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-green"
                  :value="themeConfig.customColors.primary.g"
                  @input="onRgbChange('primary', 'g', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.primary.g }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag b">B</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-blue"
                  :value="themeConfig.customColors.primary.b"
                  @input="onRgbChange('primary', 'b', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.primary.b }}</span>
              </div>
            </div>
          </div>

          <!-- 2. Secondary Color -->
          <div class="color-slider-block">
            <div class="slider-block-header">
              <div class="header-info">
                <span class="channel-title">Secondary Color</span>
                <span class="channel-sub">Mengontrol teks redup, label sekunder, outline tombol pasif, dan garis batas</span>
              </div>
              <div class="swatch-preview">
                <span class="swatch-box" :style="{ backgroundColor: secondaryHex }" />
                <code class="hex-text">{{ secondaryHex }}</code>
              </div>
            </div>

            <div class="rgb-channel-row">
              <div class="rgb-track">
                <span class="channel-tag r">R</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-red"
                  :value="themeConfig.customColors.secondary.r"
                  @input="onRgbChange('secondary', 'r', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.secondary.r }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag g">G</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-green"
                  :value="themeConfig.customColors.secondary.g"
                  @input="onRgbChange('secondary', 'g', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.secondary.g }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag b">B</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-blue"
                  :value="themeConfig.customColors.secondary.b"
                  @input="onRgbChange('secondary', 'b', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.secondary.b }}</span>
              </div>
            </div>
          </div>

          <!-- 3. Accent Color -->
          <div class="color-slider-block">
            <div class="slider-block-header">
              <div class="header-info">
                <span class="channel-title">Accent Color</span>
                <span class="channel-sub">Mengontrol badge sorotan, kursor, tag status aksen, dan seleksi sekunder</span>
              </div>
              <div class="swatch-preview">
                <span class="swatch-box" :style="{ backgroundColor: accentHex }" />
                <code class="hex-text">{{ accentHex }}</code>
              </div>
            </div>

            <div class="rgb-channel-row">
              <div class="rgb-track">
                <span class="channel-tag r">R</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-red"
                  :value="themeConfig.customColors.accent.r"
                  @input="onRgbChange('accent', 'r', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.accent.r }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag g">G</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-green"
                  :value="themeConfig.customColors.accent.g"
                  @input="onRgbChange('accent', 'g', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.accent.g }}</span>
              </div>
              <div class="rgb-track">
                <span class="channel-tag b">B</span>
                <input
                  type="range"
                  min="0"
                  max="255"
                  class="rgb-slider slider-blue"
                  :value="themeConfig.customColors.accent.b"
                  @input="onRgbChange('accent', 'b', $event.target.value)"
                />
                <span class="channel-val">{{ themeConfig.customColors.accent.b }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="ap-sub-divider"></div>

      <!-- Sub-Section 3: Live Preview Mockup -->
      <div class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Live Preview Mockup</div>
          <div class="ap-sub-desc">
            Visualisasi real-time penerapan tema aktif pada komponen UI Workbench.
          </div>
        </div>

        <div class="preview-mockup">
          <div class="mock-sidebar">
            <div class="mock-item active">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span>Explorer</span>
            </div>
            <div class="mock-item">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <span>Search</span>
            </div>
            <div class="mock-item">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0 1.5 1z"/>
              </svg>
              <span>Settings</span>
            </div>
          </div>

          <div class="mock-editor-area">
            <div class="mock-tabs">
              <span class="mock-tab active">App.vue</span>
              <span class="mock-tab">themeService.js</span>
            </div>
            <div class="mock-code-canvas">
              <span class="code-comment">// AEGIS Code Editor - Live Theme Synchronized</span>
              <div class="code-line">
                <span class="kw">const</span>
                <span class="fn">themeState</span> =
                <span class="fn">createThemeState</span>();
              </div>
              <div class="mock-buttons-row">
                <button type="button" class="mock-btn primary">Primary Action</button>
                <button type="button" class="mock-btn secondary">Secondary</button>
                <span class="mock-badge">Accent Tag</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppCard>
</template>

<style scoped>
.appearance-panel-root {
  display: flex;
  flex-direction: column;
}

/* Scope Banner */
.ap-scope {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-surface, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 18px;
}

.ap-scope-badge {
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--accent-soft, rgba(181, 161, 237, 0.16));
  color: var(--accent, #b5a1ed);
  border: 1px solid var(--border-hover, rgba(181, 161, 237, 0.35));
}

.ap-scope-note {
  font-size: 12px;
  color: var(--text-dim, #a29eaf);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
  color: var(--text, #dedee9);
}

/* Sub-Sections */
.ap-sub-section {
  padding: 6px 0;
}

.ap-sub-header {
  margin-bottom: 14px;
}

.ap-sub-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text, #dedee9);
}

.ap-sub-desc {
  font-size: 12px;
  color: var(--text-dim, #a29eaf);
  margin-top: 3px;
  line-height: 1.45;
}

.ap-sub-divider {
  height: 1px;
  background: var(--border-soft, rgba(255, 255, 255, 0.08));
  margin: 18px 0;
}

/* Mode Switcher Pills */
.ap-mode-pills {
  display: inline-flex;
  gap: 8px;
  background: var(--bg-deep, rgba(0, 0, 0, 0.2));
  padding: 4px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.05));
}

.ap-mode-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 550;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-dim, #a29eaf);
  cursor: pointer;
  transition: all 0.15s ease;
}

.ap-mode-pill-btn:hover {
  color: var(--text, #dedee9);
  background: var(--hover, rgba(255, 255, 255, 0.06));
}

.ap-mode-pill-btn.active {
  background: var(--bg-surface, #292a36);
  color: var(--accent, #b5a1ed);
  border-color: var(--border-hover, rgba(181, 161, 237, 0.35));
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}

.ap-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}

/* Presets Grid */
.presets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px;
}

.preset-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--bg-surface, #1f202c);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.preset-card:hover {
  border-color: var(--border-hover, rgba(181, 161, 237, 0.45));
  transform: translateY(-1px);
}

.preset-card.active {
  border-color: var(--accent, #b5a1ed);
  box-shadow: 0 0 0 1px var(--accent, #b5a1ed);
  background: var(--bg-elev, #24283b);
}

.preset-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.preset-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text, #dedee9);
}

.preset-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.preset-badge.dark {
  background: rgba(0, 0, 0, 0.4);
  color: #9aa5ce;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.preset-badge.light {
  background: rgba(255, 255, 255, 0.85);
  color: #343b58;
}

.preset-color-strip {
  display: flex;
  gap: 6px;
}

.color-dot {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.active-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent, #b5a1ed);
}

.active-check-svg {
  display: inline-block;
  vertical-align: middle;
}

/* Foundation Selector */
.foundation-selector-group {
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.group-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text, #dedee9);
}

.foundation-options {
  display: flex;
  gap: 8px;
}

.foundation-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  background: var(--bg-surface, #1f202c);
  color: var(--text-dim, #a29eaf);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.foundation-btn:hover {
  background: var(--hover, rgba(255, 255, 255, 0.08));
  color: var(--text, #dedee9);
}

.foundation-btn.active {
  border-color: var(--accent, #b5a1ed);
  color: var(--accent, #b5a1ed);
  background: var(--accent-soft, rgba(181, 161, 237, 0.15));
  font-weight: 600;
}

/* Custom Sliders */
.sliders-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.color-slider-block {
  padding: 12px 14px;
  background: var(--bg-surface, #1f202c);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-sm, 6px);
}

.slider-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.channel-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text, #dedee9);
  display: block;
}

.channel-sub {
  font-size: 11px;
  color: var(--text-dim, #a29eaf);
  display: block;
  margin-top: 1px;
}

.swatch-preview {
  display: flex;
  align-items: center;
  gap: 8px;
}

.swatch-box {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.hex-text {
  font-size: 11.5px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text, #dedee9);
  background: var(--bg-deep, rgba(0, 0, 0, 0.2));
  padding: 2px 6px;
  border-radius: 4px;
}

.rgb-channel-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.rgb-track {
  display: flex;
  align-items: center;
  gap: 8px;
}

.channel-tag {
  font-size: 11px;
  font-weight: 700;
  width: 16px;
  text-align: center;
}

.channel-tag.r { color: #f87171; }
.channel-tag.g { color: #4ade80; }
.channel-tag.b { color: #60a5fa; }

.rgb-slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  accent-color: var(--accent, #b5a1ed);
  cursor: pointer;
}

.channel-val {
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  width: 28px;
  text-align: right;
  color: var(--text-dim, #a29eaf);
}

/* Mockup Live Preview */
.preview-mockup {
  display: grid;
  grid-template-columns: 160px 1fr;
  height: 180px;
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-sm, 6px);
  overflow: hidden;
  background: var(--bg, #181922);
}

.mock-sidebar {
  background: var(--bg-sidebar, #171822);
  border-right: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mock-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 5px 8px;
  border-radius: 4px;
  color: var(--text-dim, #a29eaf);
}

.mock-item.active {
  background: var(--accent-soft, rgba(181, 161, 237, 0.15));
  color: var(--accent, #b5a1ed);
  font-weight: 600;
}

.mock-editor-area {
  display: flex;
  flex-direction: column;
}

.mock-tabs {
  background: var(--bg-surface, #1f202c);
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  display: flex;
  padding: 4px 8px 0;
  gap: 4px;
}

.mock-tab {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 4px 4px 0 0;
  color: var(--text-dim, #a29eaf);
}

.mock-tab.active {
  background: var(--bg, #181922);
  color: var(--text, #dedee9);
  border-top: 2px solid var(--accent, #b5a1ed);
}

.mock-code-canvas {
  flex: 1;
  padding: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.code-comment {
  color: var(--muted, #565f89);
  font-style: italic;
}

.code-line .kw { color: var(--syntax-purple, #c1a4df); font-weight: 600; }
.code-line .fn { color: var(--accent, #b5a1ed); }

.mock-buttons-row {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mock-btn {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  cursor: default;
}

.mock-btn.primary {
  background: var(--accent, #b5a1ed);
  color: #181922;
  border: none;
}

.mock-btn.secondary {
  background: transparent;
  color: var(--secondary, #bcbcca);
  border: 1px solid var(--secondary, #bcbcca);
}

.mock-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--accent-2-soft, rgba(181, 161, 237, 0.2));
  color: var(--accent-2, #b5a1ed);
  border: 1px solid var(--border-hover, rgba(181, 161, 237, 0.4));
}
</style>
