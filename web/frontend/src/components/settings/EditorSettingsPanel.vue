<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import {
  DEFAULT_EDITOR_SETTINGS,
  LOCAL_FONTS,
  getStoredEditorSettings,
  saveEditorSettings,
  toMonacoOptions,
} from "../../services/editorSettingsService.js";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const initial = getStoredEditorSettings();

const form = reactive({
  fontSize: initial.fontSize,
  fontFamily: initial.fontFamily,
  wordWrap: initial.wordWrap,
  lineHeight: initial.lineHeight,
  minimap: {
    enabled: initial.minimap.enabled,
    side: initial.minimap.side,
    renderCharacters: initial.minimap.renderCharacters,
    scale: initial.minimap.scale,
  },
});

const isCustomFont = ref(!LOCAL_FONTS.some((f) => f.value === form.fontFamily));
const customFontValue = ref(isCustomFont.value ? form.fontFamily : "");

const selectedFontKey = computed({
  get() {
    if (isCustomFont.value) return "__custom__";
    const found = LOCAL_FONTS.find((f) => f.value === form.fontFamily);
    return found ? found.value : "__custom__";
  },
  set(val) {
    if (val === "__custom__") {
      isCustomFont.value = true;
      if (customFontValue.value) form.fontFamily = customFontValue.value;
    } else {
      isCustomFont.value = false;
      form.fontFamily = val;
    }
  },
});

function onCustomFontInput(e) {
  customFontValue.value = e.target.value;
  form.fontFamily = e.target.value;
}

const notice = ref("");

function applyAndSave() {
  saveEditorSettings({
    fontSize: Number(form.fontSize),
    fontFamily: form.fontFamily,
    wordWrap: form.wordWrap,
    lineHeight: Number(form.lineHeight),
    minimap: {
      enabled: form.minimap.enabled,
      side: form.minimap.side,
      renderCharacters: form.minimap.renderCharacters,
      scale: Number(form.minimap.scale),
    },
  });
  notice.value = "Editor settings applied.";
  setTimeout(() => {
    notice.value = "";
  }, 2500);
}

// Sample code preview lines
const sampleCode = `// AegisCode Studio — Workbench Code Sample
import { defineTask } from "./tasks.js";

export async function executeTask(task) {
  console.log("Analyzing task requirements with local pipeline...");
  const result = await defineTask(task);
  return { success: true, verified: result.status === "completed" };
}`;

// Monaco Live Code Preview Instance
const previewContainer = ref(null);
const monacoLoaded = ref(false);
let monaco = null;
let previewEditor = null;
let previewModel = null;
let themeObserver = null;
let resizeObserver = null;
let disposed = false;

async function mountPreviewEditor() {
  if (typeof window === "undefined" || !previewContainer.value) return;
  try {
    const mod = await import("../../monacoSetup.js");
    if (disposed || !previewContainer.value) return;
    monaco = mod.getMonaco();
    const uri = monaco.Uri.parse("inmemory://aegis/preview/sampleTask.ts");
    const existing = monaco.editor.getModel(uri);
    if (existing) existing.dispose();
    previewModel = monaco.editor.createModel(sampleCode, "typescript", uri);
    const isLight = typeof document !== "undefined" && document.documentElement.dataset.theme === "light";
    const userOpts = toMonacoOptions(form);

    previewEditor = monaco.editor.create(previewContainer.value, {
      ...mod.EDITOR_OPTIONS,
      ...userOpts,
      theme: isLight ? mod.AEGIS_LIGHT_THEME : mod.AEGIS_THEME,
      model: previewModel,
      readOnly: true,
      domReadOnly: true,
      contextmenu: false,
      scrollBeyondLastLine: false,
      automaticLayout: true,
      glyphMargin: false,
      folding: false,
      renderLineHighlight: "none",
    });

    monacoLoaded.value = true;

    if (typeof MutationObserver !== "undefined" && typeof document !== "undefined") {
      themeObserver = new MutationObserver(() => {
        const lightNow = document.documentElement.dataset.theme === "light";
        monaco.editor.setTheme(lightNow ? mod.AEGIS_LIGHT_THEME : mod.AEGIS_THEME);
      });
      themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
      });
    }

    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        if (previewEditor) previewEditor.layout();
      });
      resizeObserver.observe(previewContainer.value);
    }
  } catch (_) {
    monacoLoaded.value = false;
  }
}

onMounted(() => {
  nextTick(() => {
    mountPreviewEditor();
  });
});

onBeforeUnmount(() => {
  disposed = true;
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (previewEditor) {
    previewEditor.dispose();
    previewEditor = null;
  }
  if (previewModel) {
    previewModel.dispose();
    previewModel = null;
  }
});

// Auto-save & update preview editor whenever form reactive values change
watch(
  () => [
    form.fontSize,
    form.fontFamily,
    form.wordWrap,
    form.lineHeight,
    form.minimap.enabled,
    form.minimap.side,
    form.minimap.renderCharacters,
    form.minimap.scale,
  ],
  () => {
    applyAndSave();
    if (previewEditor) {
      previewEditor.updateOptions(toMonacoOptions(form));
    }
  }
);

function resetDefaults() {
  form.fontSize = DEFAULT_EDITOR_SETTINGS.fontSize;
  form.fontFamily = DEFAULT_EDITOR_SETTINGS.fontFamily;
  form.wordWrap = DEFAULT_EDITOR_SETTINGS.wordWrap;
  form.lineHeight = DEFAULT_EDITOR_SETTINGS.lineHeight;
  form.minimap.enabled = DEFAULT_EDITOR_SETTINGS.minimap.enabled;
  form.minimap.side = DEFAULT_EDITOR_SETTINGS.minimap.side;
  form.minimap.renderCharacters = DEFAULT_EDITOR_SETTINGS.minimap.renderCharacters;
  form.minimap.scale = DEFAULT_EDITOR_SETTINGS.minimap.scale;
  isCustomFont.value = false;
  customFontValue.value = "";
  applyAndSave();
  if (previewEditor) {
    previewEditor.updateOptions(toMonacoOptions(form));
  }
}
</script>

<template>
  <div class="editor-settings-root">
    <!-- Header panel -->
    <AppCard variant="panel" class="settings-panel">
      <template #header>
        <div class="panel-head">
          <div class="title">Text Editor Settings</div>
          <AppButton variant="ghost" size="sm" @click="resetDefaults">
            Reset to Defaults
          </AppButton>
        </div>
      </template>

      <div class="panel-body">
        <div v-if="notice" class="sv-alert ok" style="margin-bottom: 12px;">{{ notice }}</div>

        <div class="ed-settings-grid">
          <!-- 1. Font Size -->
          <div class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Font Size</span>
              <span class="ed-setting-desc">Controls code text dimension in pixels</span>
            </div>
            <div class="ed-setting-control">
              <input
                v-model.number="form.fontSize"
                type="range"
                min="10"
                max="26"
                step="1"
                class="ed-range"
              />
              <span class="mono ed-val-badge">{{ form.fontSize }}px</span>
            </div>
          </div>

          <!-- 2. Font Family (Local List) -->
          <div class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Font Family</span>
              <span class="ed-setting-desc">Select from local coding typography or custom font</span>
            </div>
            <div class="ed-setting-control ed-font-control">
              <select v-model="selectedFontKey" class="sv-select">
                <option v-for="f in LOCAL_FONTS" :key="f.value" :value="f.value">
                  {{ f.label }}
                </option>
                <option value="__custom__">Custom Local Font…</option>
              </select>
              <input
                v-if="isCustomFont"
                :value="customFontValue"
                type="text"
                class="sv-input"
                placeholder="e.g. 'Victor Mono', 'Iosevka'"
                style="margin-top: 6px;"
                @input="onCustomFontInput"
              />
            </div>
          </div>

          <!-- 3. Line Space Height -->
          <div class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Line Height</span>
              <span class="ed-setting-desc">Vertical spacing between lines of code</span>
            </div>
            <div class="ed-setting-control">
              <input
                v-model.number="form.lineHeight"
                type="range"
                min="16"
                max="34"
                step="1"
                class="ed-range"
              />
              <span class="mono ed-val-badge">{{ form.lineHeight }}px</span>
            </div>
          </div>

          <!-- 4. Word Wrap -->
          <div class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Word Wrap</span>
              <span class="ed-setting-desc">Controls whether lines should wrap or scroll horizontally</span>
            </div>
            <div class="ed-setting-control">
              <select v-model="form.wordWrap" class="sv-select">
                <option value="on">On (Wrap at viewport width)</option>
                <option value="off">Off (Never wrap, horizontal scroll)</option>
                <option value="wordWrapColumn">Word Wrap Column (80 chars)</option>
                <option value="bounded">Bounded (Viewport or 80 chars)</option>
              </select>
            </div>
          </div>

          <!-- 5. Minimap Enabled -->
          <div class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Minimap Overview</span>
              <span class="ed-setting-desc">Display code minimap outline along the editor</span>
            </div>
            <div class="ed-setting-control">
              <label class="switch-toggle" aria-label="Toggle minimap">
                <input v-model="form.minimap.enabled" type="checkbox" />
                <span class="slider round"></span>
              </label>
              <span class="chip chip-sm" :class="form.minimap.enabled ? 'ok' : 'idle'">
                {{ form.minimap.enabled ? "Enabled" : "Disabled" }}
              </span>
            </div>
          </div>

          <!-- 6. Minimap Position (Side) -->
          <div v-if="form.minimap.enabled" class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Minimap Position</span>
              <span class="ed-setting-desc">Display minimap along the right or left edge</span>
            </div>
            <div class="ed-setting-control">
              <select v-model="form.minimap.side" class="sv-select">
                <option value="right">Right</option>
                <option value="left">Left</option>
              </select>
            </div>
          </div>

          <!-- 7. Minimap Scale -->
          <div v-if="form.minimap.enabled" class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Minimap Scale</span>
              <span class="ed-setting-desc">Zoom multiplier for the minimap preview</span>
            </div>
            <div class="ed-setting-control">
              <select v-model.number="form.minimap.scale" class="sv-select">
                <option :value="1">1x (Default)</option>
                <option :value="2">2x (Medium)</option>
                <option :value="3">3x (Large)</option>
              </select>
            </div>
          </div>

          <!-- 8. Render Character Glyphs -->
          <div v-if="form.minimap.enabled" class="ed-setting-row">
            <div class="ed-setting-label">
              <span class="ed-setting-title">Render Glyphs</span>
              <span class="ed-setting-desc">Draw actual characters instead of solid blocks</span>
            </div>
            <div class="ed-setting-control">
              <label class="switch-toggle" aria-label="Toggle character glyphs">
                <input v-model="form.minimap.renderCharacters" type="checkbox" />
                <span class="slider round"></span>
              </label>
              <span class="chip chip-sm" :class="form.minimap.renderCharacters ? 'ok' : 'idle'">
                {{ form.minimap.renderCharacters ? "Enabled" : "Disabled" }}
              </span>
            </div>
          </div>
        </div>

        <div class="ed-sub-divider"></div>

        <!-- Live Code Preview Sub-section -->
        <div class="ed-sub-section">
          <div class="ed-sub-header">
            <div>
              <div class="ed-sub-title">Live Code Preview</div>
              <div class="ed-sub-desc">Interactive rendering of your typography and minimap configuration</div>
            </div>
            <span class="chip chip-sm ok">Live Sync</span>
          </div>
          <div class="ed-preview-frame">
          <div class="ed-preview-topbar">
            <div class="ed-preview-dots">
              <span class="dot red"></span>
              <span class="dot yellow"></span>
              <span class="dot green"></span>
            </div>
            <div class="ed-preview-tab">
              <span class="ed-tab-icon mono">TS</span>
              <span class="ed-tab-title">sampleTask.ts</span>
              <span class="ed-tab-meta">readonly</span>
            </div>
          </div>
          <!-- Real Monaco Container -->
          <div ref="previewContainer" class="ed-monaco-canvas"></div>
          <!-- Fallback when Monaco is not loaded (SSR / test) -->
          <div
            v-if="!monacoLoaded"
            class="ed-preview-fallback"
            :style="{
              fontFamily: form.fontFamily,
              fontSize: form.fontSize + 'px',
              lineHeight: form.lineHeight + 'px',
            }"
          >
            <pre class="ed-code-block"><code>{{ sampleCode }}</code></pre>
          </div>
        </div>
      </div>
    </div>
  </AppCard>
</div>
</template>

<style scoped>
.editor-settings-root {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ed-sub-divider {
  height: 1px;
  background: var(--line, var(--border-soft));
  margin: 18px 0 14px;
}
.ed-sub-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ed-sub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ed-sub-title {
  font-size: 13.5px;
  font-weight: 650;
  color: var(--text);
}
.ed-sub-desc {
  font-size: 11.5px;
  color: var(--text-dim);
  margin-top: 2px;
}

.ed-settings-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ed-setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-soft);
}

.ed-setting-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 0 0 220px;
  min-width: 160px;
}

.ed-setting-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.ed-setting-desc {
  font-size: 10.5px;
  color: var(--text-faint);
  line-height: 1.3;
}

.ed-setting-control {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
}

.ed-font-control {
  flex-direction: column;
  align-items: flex-end;
  max-width: 320px;
  width: 100%;
}

.sv-select {
  width: 100%;
  max-width: 320px;
  padding: 6px 28px 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  background-color: var(--bg-elev, #181524);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  color: var(--text, #f0f0f5);
  font-size: 12px;
  font-family: inherit;
  outline: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  transition: border-color 0.15s ease, background-color 0.15s ease;
  box-sizing: border-box;
}

:global([data-theme="light"]) .sv-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(0,0,0,0.6)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
}

.sv-select:hover {
  border-color: var(--border-hover, rgba(255, 255, 255, 0.22));
}

.sv-select:focus {
  border-color: var(--accent, #2d7d4e);
  box-shadow: 0 0 0 1px var(--accent, #2d7d4e);
}

.sv-select option {
  background: var(--bg-deep, #14121e);
  color: var(--text, #f0f0f5);
  padding: 6px 10px;
}

:global([data-theme="light"]) .sv-select option {
  background: #ffffff;
  color: #1e2029;
}

.sv-input {
  width: 100%;
  max-width: 320px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  background: var(--bg-elev, #181524);
  color: var(--text, #f0f0f5);
  font-size: 12px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s ease;
  box-sizing: border-box;
}

.sv-input:focus {
  border-color: var(--accent, #2d7d4e);
  box-shadow: 0 0 0 1px var(--accent, #2d7d4e);
}

.ed-range {
  flex: 1 1 auto;
  max-width: 220px;
  accent-color: var(--accent);
  cursor: pointer;
}

.ed-val-badge {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-dim);
  background: rgba(255, 255, 255, 0.06);
  padding: 3px 8px;
  border-radius: 5px;
  min-width: 44px;
  text-align: center;
}

/* Switch toggle */
.switch-toggle {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.switch-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider.round {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: rgba(255, 255, 255, 0.15);
  transition: 0.2s;
  border-radius: 20px;
}

.slider.round:before {
  position: absolute;
  content: "";
  height: 14px;
  width: 14px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.2s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: var(--accent);
}

input:checked + .slider:before {
  transform: translateX(16px);
}

/* Live Code Preview Frame */
.ed-preview-frame {
  display: flex;
  flex-direction: column;
  background: var(--bg-deep, #100e18);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  width: 100%;
}

.ed-preview-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 30px;
  padding: 0 12px;
  background: var(--bg-surface, #181524);
  border-bottom: 1px solid var(--border-soft);
  user-select: none;
}

.ed-preview-dots {
  display: flex;
  align-items: center;
  gap: 5px;
}

.ed-preview-dots .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
}

.ed-preview-dots .dot.red { background: #e06c75; opacity: 0.8; }
.ed-preview-dots .dot.yellow { background: #e5c07b; opacity: 0.8; }
.ed-preview-dots .dot.green { background: #98c379; opacity: 0.8; }

.ed-preview-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 4px;
  background: var(--bg-deep, #100e18);
  border: 1px solid var(--border-soft);
  font-size: 11px;
}

.ed-tab-icon {
  font-size: 10px;
  font-weight: 700;
  color: #3178c6;
}

.ed-tab-title {
  color: var(--text);
  font-weight: 500;
}

.ed-tab-meta {
  font-size: 9.5px;
  color: var(--text-faint);
  background: rgba(255, 255, 255, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

.ed-monaco-canvas {
  width: 100%;
  height: 280px;
  min-height: 260px;
  background: var(--bg-deep, #100e18);
}

.ed-preview-fallback {
  padding: 14px 18px;
  color: var(--text);
  min-height: 180px;
  overflow-x: auto;
}

.ed-code-block {
  margin: 0;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
}
</style>
