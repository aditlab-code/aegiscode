<script setup>
/**
 * AppearanceSettingsPanel.vue — Unified Template Presets Architecture
 *
 * Tab pengaturan Appearance & Theming IDE AEGIS yang selaras dengan
 * standar Unified Settings (EditorSettingsPanel & GlobalSettingsPanel):
 * 1. Card & Header terpadu (<AppCard variant="panel" class="settings-panel">).
 * 2. Header dengan title terpadu dan aksi Reset to Defaults di panel-actions.
 * 3. Unified Template Presets: 10 curated themes dengan circular color wheels 5-warna.
 * 4. Live Preview Mockup yang otomatis sinkron dengan tema aktif.
 * 5. SVG icons murni (zero emoji) dan arsitektur token CSS terpadu.
 */
import { computed } from "vue";
import {
  createThemeState,
  PRESET_CATALOG,
} from "../../services/themeService.js";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const themeState = createThemeState();
const themeConfig = themeState.themeConfig;

const activePreset = computed(() => {
  return PRESET_CATALOG.find((p) => p.id === themeConfig.preset) || PRESET_CATALOG[0];
});

function selectPreset(presetId) {
  themeState.setPreset(presetId);
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
      <!-- Section 1: Template Presets Catalog -->
      <div class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Template Color Presets</div>
          <div class="ap-sub-desc">
            Pilihan palet visual kurasi dengan circular color wheels 5-warna yang seimbang untuk estetika dan ergonomi coding.
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
            :aria-pressed="themeConfig.preset === preset.id"
            @click="selectPreset(preset.id)"
            @keydown.enter="selectPreset(preset.id)"
            @keydown.space.prevent="selectPreset(preset.id)"
          >
            <div class="preset-card-top">
              <span class="preset-name">{{ preset.name }}</span>
              <span class="preset-badge" :class="preset.variant">
                {{ preset.variant === 'dark' ? 'Dark' : 'Light' }}
              </span>
            </div>

            <!-- Color Circular Wheel & 5-Color Swatch Preview -->
            <div class="preset-wheel-card-body">
              <div class="preset-wheel-wrapper" title="Spiral RGB 5-Color Wheel">
                <svg class="preset-color-wheel" viewBox="0 0 44 44" width="46" height="46" aria-hidden="true">
                  <!-- 5 arcs around circle (circumference = 100.53, each arc 17.5, gap 2.6) -->
                  <circle cx="22" cy="22" r="16" fill="none" :stroke="preset.preview.bg" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="0" />
                  <circle cx="22" cy="22" r="16" fill="none" :stroke="preset.preview.surface" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-20.1" />
                  <circle cx="22" cy="22" r="16" fill="none" :stroke="preset.preview.primary" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-40.2" />
                  <circle cx="22" cy="22" r="16" fill="none" :stroke="preset.preview.secondary" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-60.3" />
                  <circle cx="22" cy="22" r="16" fill="none" :stroke="preset.preview.accent" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-80.4" />
                  <!-- Center spiral hub -->
                  <circle cx="22" cy="22" r="7.5" :fill="preset.preview.bg" :stroke="preset.preview.surface" stroke-width="1.2" />
                  <path d="M22 17.5a4.5 4.5 0 0 1 4.5 4.5 3.5 3.5 0 0 1-3.5 3.5 2.5 2.5 0 0 1-2.5-2.5" fill="none" :stroke="preset.preview.primary" stroke-width="1.4" stroke-linecap="round" />
                </svg>
              </div>

              <div class="preset-color-strip">
                <span
                  class="color-dot"
                  :style="{ backgroundColor: preset.preview.bg }"
                  title="Background"
                />
                <span
                  class="color-dot"
                  :style="{ backgroundColor: preset.preview.surface }"
                  title="Surface"
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
                <span
                  class="color-dot"
                  :style="{ backgroundColor: preset.preview.accent }"
                  title="Accent"
                />
              </div>
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

      <div class="ap-sub-divider"></div>

      <!-- Section 2: Live Preview Mockup -->
      <div class="ap-sub-section">
        <div class="ap-sub-header">
          <div class="ap-sub-title">Live Preview Mockup</div>
          <div class="ap-sub-desc">
            Visualisasi real-time penerapan tema aktif pada komponen UI Workbench.
          </div>
        </div>

        <div class="preview-mockup" :style="{ backgroundColor: activePreset.preview.bg }">
          <div class="mock-sidebar" :style="{ backgroundColor: activePreset.preview.surface }">
            <div class="mock-item active" :style="{ color: activePreset.preview.primary }">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span>Explorer</span>
            </div>
            <div class="mock-item" :style="{ color: activePreset.preview.secondary }">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <span>Search</span>
            </div>
            <div class="mock-item" :style="{ color: activePreset.preview.secondary }">
              <svg class="ap-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0 1.5 1z"/>
              </svg>
              <span>Settings</span>
            </div>
          </div>

          <div class="mock-editor-area" :style="{ backgroundColor: activePreset.preview.bg }">
            <div class="mock-tabs" :style="{ backgroundColor: activePreset.preview.surface }">
              <span class="mock-tab active" :style="{ borderBottomColor: activePreset.preview.primary, color: activePreset.preview.primary }">App.vue</span>
              <span class="mock-tab" :style="{ color: activePreset.preview.secondary }">themeService.js</span>
            </div>
            <div class="mock-code-canvas">
              <span class="code-comment" :style="{ color: activePreset.preview.secondary }">// AEGIS Code Editor - Live Theme Synchronized</span>
              <div class="code-line">
                <span class="kw" :style="{ color: activePreset.preview.accent }">const</span>
                <span class="fn" :style="{ color: activePreset.preview.primary }">themeState</span> =
                <span class="fn" :style="{ color: activePreset.preview.primary }">createThemeState</span>();
              </div>
              <div class="mock-buttons-row">
                <button type="button" class="mock-btn primary" :style="{ backgroundColor: activePreset.preview.primary }">Primary Action</button>
                <button type="button" class="mock-btn secondary" :style="{ borderColor: activePreset.preview.secondary, color: activePreset.preview.secondary }">Secondary</button>
                <span class="mock-badge" :style="{ backgroundColor: activePreset.preview.accent }">Accent Tag</span>
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
  background: var(--inset, rgba(0, 0, 0, 0.22));
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

.preset-wheel-card-body {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0 2px 0;
}

.preset-wheel-wrapper {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.preset-card:hover .preset-wheel-wrapper {
  transform: rotate(36deg) scale(1.06);
}

.preset-color-wheel {
  display: block;
}

.preset-color-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.color-dot {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  transition: transform 0.15s ease;
}

.color-dot:hover {
  transform: scale(1.2);
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
