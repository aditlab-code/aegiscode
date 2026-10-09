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
            :data-theme-preset="preset.id"
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
                  <circle cx="22" cy="22" r="16" fill="none" class="wheel-arc-bg" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="0" />
                  <circle cx="22" cy="22" r="16" fill="none" class="wheel-arc-surface" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-20.1" />
                  <circle cx="22" cy="22" r="16" fill="none" class="wheel-arc-primary" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-40.2" />
                  <circle cx="22" cy="22" r="16" fill="none" class="wheel-arc-secondary" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-60.3" />
                  <circle cx="22" cy="22" r="16" fill="none" class="wheel-arc-accent" stroke-width="4.5" stroke-dasharray="17.5 83" stroke-dashoffset="-80.4" />
                  <!-- Center spiral hub -->
                  <circle cx="22" cy="22" r="7.5" class="wheel-hub-bg" stroke-width="1.2" />
                  <path d="M22 17.5a4.5 4.5 0 0 1 4.5 4.5 3.5 3.5 0 0 1-3.5 3.5 2.5 2.5 0 0 1-2.5-2.5" fill="none" class="wheel-hub-accent" stroke-width="1.4" stroke-linecap="round" />
                </svg>
              </div>

              <div class="preset-color-strip">
                <span class="color-dot dot-bg" title="Background" />
                <span class="color-dot dot-surface" title="Surface" />
                <span class="color-dot dot-primary" title="Primary" />
                <span class="color-dot dot-secondary" title="Secondary" />
                <span class="color-dot dot-accent" title="Accent" />
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
  color: var(--text);
}

.ap-sub-desc {
  font-size: 12px;
  color: var(--text-dim);
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
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
  background: var(--bg-elev);
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
  color: var(--text);
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
  color: var(--text-dim);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.preset-badge.light {
  background: rgba(255, 255, 255, 0.85);
  color: var(--text);
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

.color-dot.dot-bg { background: var(--bg); }
.color-dot.dot-surface { background: var(--bg-surface); }
.color-dot.dot-primary { background: var(--accent); }
.color-dot.dot-secondary { background: var(--text-dim); }
.color-dot.dot-accent { background: var(--accent-2); }

.wheel-arc-bg { stroke: var(--bg); }
.wheel-arc-surface { stroke: var(--bg-surface); }
.wheel-arc-primary { stroke: var(--accent); }
.wheel-arc-secondary { stroke: var(--text-dim); }
.wheel-arc-accent { stroke: var(--accent-2); }
.wheel-hub-bg { fill: var(--bg); stroke: var(--bg-surface); }
.wheel-hub-accent { stroke: var(--accent); }

.active-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
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
  background: var(--bg);
}

.mock-sidebar {
  background: var(--bg-sidebar);
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
  color: var(--text-dim);
}

.mock-item.active {
  background: var(--accent-soft, rgba(181, 161, 237, 0.15));
  color: var(--accent);
  font-weight: 600;
}

.mock-editor-area {
  display: flex;
  flex-direction: column;
}

.mock-tabs {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  display: flex;
  padding: 4px 8px 0;
  gap: 4px;
}

.mock-tab {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 4px 4px 0 0;
  color: var(--text-dim);
}

.mock-tab.active {
  background: var(--bg);
  color: var(--text);
  border-top: 2px solid var(--accent);
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
  color: var(--muted);
  font-style: italic;
}

.code-line .kw { color: var(--syntax-purple); font-weight: 600; }
.code-line .fn { color: var(--accent); }

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
  background: var(--accent);
  color: var(--bg);
  border: none;
}

.mock-btn.secondary {
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border-soft);
}

.mock-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--accent-2-soft, rgba(181, 161, 237, 0.2));
  color: var(--accent-2);
  border: 1px solid var(--border-hover, rgba(181, 161, 237, 0.4));
}
</style>
